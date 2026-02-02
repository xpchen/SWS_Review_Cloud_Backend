#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理文档相关数据的工具脚本
用法：
    python 清理文档数据.py --version <版本ID>      # 清理特定版本
    python 清理文档数据.py --document <文档ID>     # 清理特定文档
    python 清理文档数据.py --project <项目ID>      # 清理项目下的所有文档
    python 清理文档数据.py --review-only           # 只清理审查数据
    python 清理文档数据.py --stats                 # 查看数据统计
"""
import os
import sys
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

_schema = settings.DB_SCHEMA


def cleanup_version(version_id: int, dry_run: bool = False):
    """清理特定版本的所有数据"""
    print("=" * 60)
    print(f"清理版本 {version_id} 的数据")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  这是预览模式，不会实际删除数据")
        print()
    
    # 检查版本是否存在
    version = db.fetch_one(
        f"SELECT id, document_id, version_no, status FROM {_schema}.document_version WHERE id = %(v)s",
        {"v": version_id}
    )
    if not version:
        print(f"❌ 版本 {version_id} 不存在")
        return False
    
    print(f"版本信息:")
    print(f"  版本ID: {version['id']}")
    print(f"  文档ID: {version['document_id']}")
    print(f"  版本号: {version['version_no']}")
    print(f"  状态: {version['status']}")
    print()
    
    # 统计要删除的数据
    stats = {}
    stats['review_issues'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.review_issue WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    stats['review_runs'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.review_run WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    stats['facts'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.doc_fact WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    stats['blocks'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.doc_block WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    stats['tables'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.doc_table WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    stats['outline_nodes'] = db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM {_schema}.doc_outline_node WHERE version_id = %(v)s",
        {"v": version_id}
    )['cnt']
    
    print("将删除的数据统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    if dry_run:
        print("预览模式：不会实际删除数据")
        return True
    
    # 确认删除
    confirm = input("确认删除？(yes/no): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return False
    
    print("开始删除...")
    
    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                # 按顺序删除（考虑外键约束）
                cur.execute(f"DELETE FROM {_schema}.review_issue WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除审查问题: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.review_run WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除审查运行: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.doc_fact WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除文档事实: {cur.rowcount} 条")
                
                cur.execute(f"""
                    DELETE FROM {_schema}.block_page_anchor 
                    WHERE block_id IN (SELECT id FROM {_schema}.doc_block WHERE version_id = %(v)s)
                """, {"v": version_id})
                print(f"  ✅ 删除块页面锚点: {cur.rowcount} 条")
                
                cur.execute(f"""
                    DELETE FROM {_schema}.doc_table_cell 
                    WHERE table_id IN (SELECT id FROM {_schema}.doc_table WHERE version_id = %(v)s)
                """, {"v": version_id})
                print(f"  ✅ 删除表格单元格: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.doc_block WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除文档块: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.doc_table WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除表格: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.doc_outline_node WHERE version_id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除大纲节点: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.document_version WHERE id = %(v)s", {"v": version_id})
                print(f"  ✅ 删除版本: {cur.rowcount} 条")
                
                conn.commit()
        
        print()
        print("✅ 清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_document(document_id: int, dry_run: bool = False):
    """清理特定文档的所有数据（包括所有版本）"""
    print("=" * 60)
    print(f"清理文档 {document_id} 的所有数据")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  这是预览模式，不会实际删除数据")
        print()
    
    # 检查文档是否存在
    doc = db.fetch_one(
        f"SELECT id, title, project_id FROM {_schema}.document WHERE id = %(d)s",
        {"d": document_id}
    )
    if not doc:
        print(f"❌ 文档 {document_id} 不存在")
        return False
    
    print(f"文档信息:")
    print(f"  文档ID: {doc['id']}")
    print(f"  标题: {doc['title']}")
    print(f"  项目ID: {doc['project_id']}")
    print()
    
    # 统计版本数量
    versions = db.fetch_all(
        f"SELECT id, version_no, status FROM {_schema}.document_version WHERE document_id = %(d)s ORDER BY version_no",
        {"d": document_id}
    )
    print(f"该文档有 {len(versions)} 个版本:")
    for v in versions:
        print(f"  版本 {v['version_no']} (ID: {v['id']}, 状态: {v['status']})")
    print()
    
    if dry_run:
        print("预览模式：不会实际删除数据")
        return True
    
    # 确认删除
    print("⚠️  警告：这将删除该文档的所有版本及其所有相关数据！")
    confirm = input("确认删除？(yes/no): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return False
    
    print("开始删除...")
    
    try:
        # 逐个清理版本
        for v in versions:
            cleanup_version(v['id'], dry_run=False)
        
        # 删除文档
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {_schema}.document WHERE id = %(d)s", {"d": document_id})
                print(f"  ✅ 删除文档: {cur.rowcount} 条")
                conn.commit()
        
        print()
        print("✅ 清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_review_only(dry_run: bool = False):
    """只清理审查数据（保留文档和版本）"""
    print("=" * 60)
    print("清理所有审查数据")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  这是预览模式，不会实际删除数据")
        print()
    
    # 统计
    stats = {}
    stats['issue_action_logs'] = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {_schema}.issue_action_log")['cnt']
    stats['review_issues'] = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {_schema}.review_issue")['cnt']
    stats['review_runs'] = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {_schema}.review_run")['cnt']
    
    print("将删除的数据统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    if dry_run:
        print("预览模式：不会实际删除数据")
        return True
    
    confirm = input("确认删除所有审查数据？(yes/no): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return False
    
    print("开始删除...")
    
    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {_schema}.issue_action_log")
                print(f"  ✅ 删除问题操作日志: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.review_issue")
                print(f"  ✅ 删除审查问题: {cur.rowcount} 条")
                
                cur.execute(f"DELETE FROM {_schema}.review_run")
                print(f"  ✅ 删除审查运行: {cur.rowcount} 条")
                
                conn.commit()
        
        print()
        print("✅ 清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_stats():
    """显示数据统计"""
    print("=" * 60)
    print("数据统计")
    print("=" * 60)
    print()
    
    stats = db.fetch_all(f"""
        SELECT 
            p.id as project_id,
            p.name as project_name,
            COUNT(DISTINCT d.id) as document_count,
            COUNT(DISTINCT dv.id) as version_count,
            COUNT(DISTINCT rr.id) as review_run_count,
            COUNT(DISTINCT ri.id) as issue_count
        FROM {_schema}.project p
        LEFT JOIN {_schema}.document d ON d.project_id = p.id
        LEFT JOIN {_schema}.document_version dv ON dv.document_id = d.id
        LEFT JOIN {_schema}.review_run rr ON rr.version_id = dv.id
        LEFT JOIN {_schema}.review_issue ri ON ri.version_id = dv.id
        GROUP BY p.id, p.name
        ORDER BY p.id
    """)
    
    if not stats:
        print("暂无数据")
        return
    
    print(f"{'项目ID':<10} {'项目名称':<30} {'文档数':<10} {'版本数':<10} {'审查运行':<12} {'问题数':<10}")
    print("-" * 90)
    for row in stats:
        print(f"{row['project_id']:<10} {row['project_name']:<30} {row['document_count']:<10} "
              f"{row['version_count']:<10} {row['review_run_count']:<12} {row['issue_count']:<10}")
    
    print()
    print("总计:")
    total_docs = sum(r['document_count'] for r in stats)
    total_versions = sum(r['version_count'] for r in stats)
    total_runs = sum(r['review_run_count'] for r in stats)
    total_issues = sum(r['issue_count'] for r in stats)
    print(f"  项目数: {len(stats)}")
    print(f"  文档数: {total_docs}")
    print(f"  版本数: {total_versions}")
    print(f"  审查运行数: {total_runs}")
    print(f"  问题数: {total_issues}")


def main():
    parser = argparse.ArgumentParser(description="清理文档相关数据")
    parser.add_argument("--version", type=int, help="清理特定版本的数据")
    parser.add_argument("--document", type=int, help="清理特定文档的所有数据")
    parser.add_argument("--project", type=int, help="清理项目下的所有文档数据")
    parser.add_argument("--review-only", action="store_true", help="只清理审查数据（保留文档和版本）")
    parser.add_argument("--stats", action="store_true", help="查看数据统计")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（不实际删除）")
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.version:
        cleanup_version(args.version, dry_run=args.dry_run)
    elif args.document:
        cleanup_document(args.document, dry_run=args.dry_run)
    elif args.project:
        print("项目级别的清理功能待实现")
        print("请使用SQL脚本：docs/migrations/012_cleanup_document_data.sql")
    elif args.review_only:
        cleanup_review_only(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
