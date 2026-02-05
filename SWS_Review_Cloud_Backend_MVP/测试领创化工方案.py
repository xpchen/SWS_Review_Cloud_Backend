#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用本地校核文件「广东领创化工新材料有限公司年产98万吨绿色化工新材料项目(报批稿).docx」做完整测试：
上传 → 文档处理（DOCX→PDF、解析、对齐、事实抽取等）→ AI 规则校验。

默认文档路径：SWS_Review_Cloud_Backend/docs/校核文件/方案/广东领创化工新材料有限公司年产98万吨绿色化工新材料项目(报批稿).docx

用法：
    python 测试领创化工方案.py
    python 测试领创化工方案.py --document-id 2
    python 测试领创化工方案.py --version-id 10
    python 测试领创化工方案.py --skip-review
"""
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 默认使用的本地 docx（相对于 SWS_Review_Cloud_Backend 仓库根目录）
DOCS_ROOT = project_root.parent / "docs"
DEFAULT_DOCX = DOCS_ROOT / "校核文件" / "方案" / "广东领创化工新材料有限公司年产98万吨绿色化工新材料项目(报批稿).docx"

import argparse
from app import db
from app.settings import settings
from app.services import upload_service, version_service, document_service, review_run_service
from app.worker import pipeline
from app.worker.ai_review_tasks import _execute_ai_review
from app.utils.celery_diagnostics import can_use_celery
from app.worker.ai_review_tasks import run_ai_review_task


def get_docx_path(custom_path: str = None) -> Path:
    """解析要测试的 docx 路径。"""
    if custom_path:
        p = Path(custom_path)
        if p.is_absolute():
            return p
        return (project_root / custom_path).resolve()
    return DEFAULT_DOCX


def ensure_document(project_id: int, title: str, document_id: int = None) -> int | None:
    """获取或创建文档，返回 document_id。"""
    if document_id:
        doc = document_service.get_document(document_id)
        if doc:
            return document_id
    # 创建新文档
    try:
        new_id = document_service.create_document(project_id, title)
        print(f"✅ 已创建文档 ID: {new_id}")
        return new_id
    except Exception as e:
        print(f"❌ 创建文档失败: {e}")
        return None


def upload_and_process(document_id: int, file_path: Path, project_id: int = 1) -> int | None:
    """上传 docx 并执行完整 pipeline，返回 version_id；失败返回 None。"""
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return None

    filename = file_path.name
    print(f"📄 读取: {file_path}")
    with open(file_path, "rb") as f:
        file_content = f.read()
    print(f"   大小: {len(file_content):,} 字节")

    print("📤 上传...")
    try:
        result = upload_service.upload_docx(
            document_id=document_id,
            file_content=file_content,
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            trigger_pipeline=False,
        )
        version_id = result["version_id"]
        print(f"✅ 版本 ID: {version_id}")
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    # 手动执行 pipeline（不含 finalize_ready，避免与脚本内触发的审查重复）
    steps = [
        ("DOCX转PDF", pipeline.convert_docx_to_pdf, 10),
        ("解析DOCX结构", pipeline.parse_docx_structure, 25),
        ("提取PDF布局", pipeline.extract_pdf_layout, 40),
        ("对齐块到PDF", pipeline.align_blocks_to_pdf, 55),
        ("抽取事实", pipeline.extract_facts, 70),
        ("构建块和索引", pipeline.build_chunks_and_index, 85),
    ]

    for step_name, step_func, progress in steps:
        print(f"📋 {step_name} ({progress}%)...")
        try:
            version_service.update_version_status(version_id, "PROCESSING", progress=progress, current_step=step_name)
            step_func(version_id)
            print(f"   ✅ 完成")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            version_service.update_version_status(
                version_id, "FAILED", error_message=str(e)[:500], progress=progress, current_step=step_name
            )
            import traceback
            traceback.print_exc()
            return None

    # 设为 READY，不调用 finalize_ready 以免自动触发审查（由脚本统一触发）
    version_service.update_version_status(version_id, "READY", progress=100, current_step="已完成")
    v = version_service.get_version(version_id)
    print(f"✅ 处理完成，版本状态: {v.get('status')}")
    return version_id


def run_ai_review(version_id: int, direct: bool = True) -> bool:
    """触发 AI 规则校验；direct=True 表示直接执行（不通过 Celery）。"""
    print("🔍 触发 AI 规则校验...")
    run_id = review_run_service.create_review_run(version_id, "AI")
    print(f"   审查运行 ID: {run_id}")

    if direct:
        _execute_ai_review(version_id, run_id)
    else:
        run_ai_review_task.delay(version_id, run_id)
        print("   已提交 Celery，等待完成...")
        for _ in range(120):
            time.sleep(2)
            run = review_run_service.get_review_run(run_id)
            status = run.get("status", "")
            progress = run.get("progress", 0)
            print(f"   状态: {status}, 进度: {progress}%")
            if status in ("DONE", "FAILED", "CANCELED"):
                break

    run = review_run_service.get_review_run(run_id)
    status = run.get("status", "")
    print(f"✅ 审查状态: {status}")
    return status == "DONE"


def main():
    parser = argparse.ArgumentParser(description="使用领创化工方案 docx 做上传→处理→AI审查测试")
    parser.add_argument(
        "--docx",
        type=str,
        default=None,
        help=f"docx 路径（默认: {DEFAULT_DOCX}）",
    )
    parser.add_argument(
        "--document-id",
        type=int,
        default=None,
        help="指定文档 ID（不指定则自动创建新文档）",
    )
    parser.add_argument(
        "--version-id",
        type=int,
        default=None,
        help="若提供，则仅对已有版本执行 AI 审查（跳过上传与处理）",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=1,
        help="项目 ID（默认 1）",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="只做上传与处理，不执行 AI 审查",
    )
    parser.add_argument(
        "--celery",
        action="store_true",
        help="审查任务通过 Celery 异步执行（默认直接执行）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("测试：广东领创化工新材料项目(报批稿).docx")
    print("=" * 60)

    version_id = args.version_id

    if version_id is None:
        docx_path = get_docx_path(args.docx)
        print(f"文档路径: {docx_path}")
        title = docx_path.stem if docx_path.exists() else "广东领创化工新材料有限公司年产98万吨绿色化工新材料项目(报批稿)"
        doc_id = ensure_document(args.project_id, title, args.document_id)
        if not doc_id:
            sys.exit(1)
        version_id = upload_and_process(doc_id, docx_path, args.project_id)
        if not version_id:
            sys.exit(1)
        print()
        print("=" * 60)
        print("前端查看审核结果：打开以下链接（将 DOC_ID 替换为下方文档 ID）")
        print(f"  http://localhost:5173/#/pages/review/detail?id={doc_id}")
        print(f"文档 ID: {doc_id}  版本 ID: {version_id}")
        print("=" * 60)
    else:
        v = version_service.get_version(version_id)
        if not v:
            print(f"❌ 版本不存在: {version_id}")
            sys.exit(1)
        doc_id = v.get("document_id")
        print(f"使用已有版本 ID: {version_id}，文档 ID: {doc_id}，状态: {v.get('status')}")
        if doc_id:
            print(f"前端查看: http://localhost:5173/#/pages/review/detail?id={doc_id}")
        if v.get("status") != "READY":
            print("⚠️ 版本未就绪(READY)，AI 审查可能依赖已处理的块数据，建议先完成处理。")

    if args.skip_review:
        print("已跳过 AI 审查 (--skip-review)")
        sys.exit(0)

    success = run_ai_review(version_id, direct=not args.celery)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
