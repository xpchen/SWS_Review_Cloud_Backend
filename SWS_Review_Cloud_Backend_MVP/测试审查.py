#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试文档审查流程
用法：
    python 测试文档审查.py <版本ID> [审查类型]
    审查类型: RULE (规则审查) | AI (AI审查) | MIXED (混合审查)，默认: RULE
"""
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import argparse
from app import db
from app.settings import settings
from app.services import version_service, review_run_service, document_service
from app.worker.review_tasks import run_rule_review_task, _execute_rule_review
from app.worker.ai_review_tasks import run_ai_review_task, _execute_ai_review
from app.utils.celery_diagnostics import diagnose_celery_setup, can_use_celery


def check_version_ready(version_id: int) -> bool:
    """检查版本是否已就绪"""
    version = version_service.get_version(version_id)
    if not version:
        print(f"❌ 版本不存在: {version_id}")
        return False
    
    status = version.get("status")
    if status != "READY":
        print(f"❌ 版本状态为 {status}，需要先完成处理（状态应为 READY）")
        print(f"   当前进度: {version.get('progress', 0)}%")
        print(f"   当前步骤: {version.get('current_step', 'N/A')}")
        return False
    
    return True


def print_version_info(version_id: int):
    """打印版本和文档信息"""
    version = version_service.get_version(version_id)
    if not version:
        print(f"❌ 版本不存在: {version_id}")
        return
    
    document_id = version.get("document_id")
    document = None
    if document_id:
        document = document_service.get_document(document_id)
    
    print("=" * 60)
    print("文档和版本信息")
    print("=" * 60)
    
    if document:
        print(f"文档ID: {document.get('id')}")
        print(f"文档标题: {document.get('title', 'N/A')}")
        print(f"文档类型: {document.get('doc_type', 'N/A')}")
        print(f"项目ID: {document.get('project_id', 'N/A')}")
        print(f"当前版本ID: {document.get('current_version_id', 'N/A')}")
    else:
        print(f"文档ID: {document_id if document_id else 'N/A'}")
        print("⚠️  无法获取文档信息")
    
    print()
    print(f"版本ID: {version.get('id')}")
    print(f"版本号: {version.get('version_no', 'N/A')}")
    print(f"状态: {version.get('status', 'N/A')}")
    print(f"进度: {version.get('progress', 0)}%")
    if version.get('current_step'):
        print(f"当前步骤: {version.get('current_step')}")
    print(f"创建时间: {version.get('created_at', 'N/A')}")
    print(f"更新时间: {version.get('updated_at', 'N/A')}")
    if version.get('error_message'):
        print(f"错误信息: {version.get('error_message')}")
    print("=" * 60)
    print()


def trigger_review(version_id: int, run_type: str = "RULE", direct: bool = False):
    """
    触发审查
    
    Args:
        version_id: 版本ID
        run_type: 审查类型 (RULE/AI/MIXED)
        direct: 是否直接执行（不使用Celery）
    """
    print("=" * 60)
    print("测试：文档审查")
    print("=" * 60)
    
    # 打印文档和版本信息
    print_version_info(version_id)
    
    print(f"审查类型: {run_type}")
    print(f"执行模式: {'直接执行（不使用Celery）' if direct else 'Celery异步执行'}")
    print()
    
    # 检查版本状态
    print("🔍 检查版本状态...")
    if not check_version_ready(version_id):
        return None
    
    print("✅ 版本已就绪，可以开始审查")
    print()
    
    # 如果不是直接执行模式，检查Celery Worker
    if not direct:
        print("🔍 检查 Celery Worker 状态...")
        if not can_use_celery():
            print("⚠️  Celery Worker 不可用")
            print()
            print("提示：")
            print("  - 启动 Celery Worker: celery -A app.worker.app worker --pool=solo --loglevel=info")
            print("  - 或使用 --direct 参数直接执行（推荐用于测试）")
            print()
            print("❌ 无法继续，请启动 Celery Worker 或使用 --direct 参数")
            return None
        else:
            print("✅ Celery Worker 可用")
        print()
    
    # 创建审查运行
    print("📋 创建审查运行...")
    try:
        run_id = review_run_service.create_review_run(version_id, run_type)
        print(f"✅ 审查运行已创建，运行ID: {run_id}")
        print()
    except Exception as e:
        print(f"❌ 创建审查运行失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # 触发审查任务
    if direct:
        print("🚀 直接执行审查任务（同步）...")
        print()
        try:
            if run_type in ("RULE", "MIXED"):
                print("   执行规则审查任务...")
                _execute_rule_review(version_id, run_id, publish_events=False)
                print("   ✅ 规则审查任务已完成")
            
            if run_type in ("AI", "MIXED"):
                print("   执行AI审查任务...")
                _execute_ai_review(version_id, run_id)
                print("   ✅ AI审查任务已完成")
            
            print()
        except Exception as e:
            print(f"❌ 执行审查任务失败: {e}")
            import traceback
            traceback.print_exc()
            review_run_service.update_run_status(run_id, "FAILED", error_message=str(e))
            return None
    else:
        print("🚀 触发审查任务（异步）...")
        try:
            if run_type in ("RULE", "MIXED"):
                print("   启动规则审查任务...")
                run_rule_review_task.delay(version_id, run_id)
                print("   ✅ 规则审查任务已提交到 Celery")
            
            if run_type in ("AI", "MIXED"):
                print("   启动AI审查任务...")
                run_ai_review_task.delay(version_id, run_id)
                print("   ✅ AI审查任务已提交到 Celery")
            
            print()
        except Exception as e:
            print(f"❌ 触发审查任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    return run_id


def monitor_review_progress(run_id: int, poll_interval: int = 2, max_wait: int = 300):
    """监控审查进度"""
    print("=" * 60)
    print("监控审查进度")
    print("=" * 60)
    print(f"运行ID: {run_id}")
    print(f"轮询间隔: {poll_interval} 秒")
    print(f"最大等待时间: {max_wait} 秒")
    print()
    
    start_time = time.time()
    last_progress = -1
    
    while True:
        run = review_run_service.get_review_run(run_id)
        if not run:
            print("❌ 审查运行不存在")
            break
        
        status = run.get("status", "")
        progress = run.get("progress", 0)
        error_message = run.get("error_message")
        
        # 只在进度变化时输出
        if progress != last_progress:
            elapsed = time.time() - start_time
            print(f"[{elapsed:.1f}s] 状态: {status}, 进度: {progress}%")
            last_progress = progress
        
        # 检查是否完成
        if status == "DONE":
            elapsed = time.time() - start_time
            print()
            print("=" * 60)
            print("✅ 审查完成！")
            print("=" * 60)
            print(f"总耗时: {elapsed:.2f} 秒")
            print(f"最终进度: {progress}%")
            if run.get("started_at"):
                print(f"开始时间: {run['started_at']}")
            if run.get("finished_at"):
                print(f"结束时间: {run['finished_at']}")
            return True
        
        elif status == "FAILED":
            print()
            print("=" * 60)
            print("❌ 审查失败")
            print("=" * 60)
            if error_message:
                print(f"错误信息: {error_message}")
            return False
        
        elif status == "CANCELED":
            print()
            print("=" * 60)
            print("⚠️  审查已取消")
            print("=" * 60)
            return False
        
        # 检查超时
        if time.time() - start_time > max_wait:
            print()
            print("=" * 60)
            print("⚠️  等待超时")
            print("=" * 60)
            print(f"当前状态: {status}, 进度: {progress}%")
            print("审查可能仍在进行中，请稍后查询")
            return None
        
        time.sleep(poll_interval)


def show_review_results(version_id: int, run_id: int = None):
    """显示审查结果"""
    print()
    print("=" * 60)
    print("审查结果")
    print("=" * 60)
    
    # 查询问题列表
    _schema = settings.DB_SCHEMA
    sql = f"""
    SELECT id, issue_type, severity, title, description, suggestion, confidence,
           status, page_no, checkpoint_code, created_at
    FROM {_schema}.review_issue
    WHERE version_id = %(version_id)s
    """
    if run_id:
        sql += " AND run_id = %(run_id)s"
    
    sql += " ORDER BY severity DESC, id DESC"
    
    params = {"version_id": version_id}
    if run_id:
        params["run_id"] = run_id
    
    issues = db.fetch_all(sql, params)
    
    if not issues:
        print("✅ 未发现问题")
        return
    
    print(f"共发现 {len(issues)} 个问题：")
    print()
    
    # 按严重程度分组统计
    severity_count = {}
    for issue in issues:
        severity = issue.get("severity", "UNKNOWN")
        severity_count[severity] = severity_count.get(severity, 0) + 1
    
    print("严重程度统计:")
    for severity in ["S1", "S2", "S3", "INFO"]:
        count = severity_count.get(severity, 0)
        if count > 0:
            print(f"  {severity}: {count} 个")
    print()
    
    # 显示前10个问题
    print("问题列表（前10个）:")
    print("-" * 60)
    for i, issue in enumerate(issues[:10], 1):
        issue_id = issue["id"]
        issue_type = issue.get("issue_type", "UNKNOWN")
        severity = issue.get("severity", "UNKNOWN")
        title = issue.get("title", "")
        page_no = issue.get("page_no")
        checkpoint_code = issue.get("checkpoint_code", "")
        confidence = issue.get("confidence", 0.0)
        
        print(f"{i}. [{severity}] {title}")
        print(f"   类型: {issue_type}")
        if page_no:
            print(f"   页码: {page_no}")
        if checkpoint_code:
            print(f"   检查点: {checkpoint_code}")
        print(f"   置信度: {confidence:.2f}")
        if issue.get("description"):
            desc = issue["description"][:100]
            if len(issue["description"]) > 100:
                desc += "..."
            print(f"   描述: {desc}")
        print()
    
    if len(issues) > 10:
        print(f"... 还有 {len(issues) - 10} 个问题未显示")
        print(f"使用 API GET /api/versions/{version_id}/issues 查看完整列表")


def main():
    parser = argparse.ArgumentParser(description="测试文档审查流程")
    parser.add_argument(
        "version_id",
        type=int,
        default=1,
        nargs="?",
        help="版本ID"
    )
    parser.add_argument(
        "run_type",
        type=str,
        nargs="?",
        default="RULE",
        choices=["RULE", "AI", "MIXED"],
        help="审查类型: RULE (规则审查) | AI (AI审查) | MIXED (混合审查)，默认: RULE"
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        default=True, 
        help="直接执行（不使用Celery，同步执行）"
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="诊断 Celery Worker 状态并退出"
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="不监控进度（仅触发）"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=2,
        help="进度轮询间隔（秒），默认: 2"
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=300,
        help="最大等待时间（秒），默认: 300"
    )
    parser.add_argument(
        "--show-results",
        default=True,
        action="store_true",
        help="审查完成后显示结果"
    )
    
    args = parser.parse_args()
    
    # 如果只是诊断，执行诊断后退出
    if args.diagnose:
        diagnose_celery_setup()
        sys.exit(0)
    
    # 触发审查
    run_id = trigger_review(args.version_id, args.run_type, direct=args.direct)
    if not run_id:
        sys.exit(1)
    
    # 直接执行模式下，任务已完成，不需要监控
    if args.direct:
        print()
        print("=" * 60)
        print("✅ 审查完成（直接执行模式）")
        print("=" * 60)
        if args.show_results:
            show_review_results(args.version_id, run_id)
        else:
            print(f"使用 --show-results 参数查看结果")
            print(f"或使用 API: GET /api/versions/{args.version_id}/issues")
        sys.exit(0)
    
    # 监控进度（仅异步模式）
    if not args.no_monitor:
        success = monitor_review_progress(
            run_id,
            poll_interval=args.poll_interval,
            max_wait=args.max_wait
        )
        
        # 显示结果
        if args.show_results or success:
            show_review_results(args.version_id, run_id)
    else:
        print()
        print("=" * 60)
        print("提示")
        print("=" * 60)
        print(f"审查已触发，运行ID: {run_id}")
        print(f"使用以下命令查看进度:")
        print(f"  python 测试审查.py {args.version_id} {args.run_type} --show-results")
        print()
        print(f"或使用 API:")
        print(f"  GET /api/review-runs/{run_id}")
        print(f"  GET /api/versions/{args.version_id}/issues")


if __name__ == "__main__":
    main()