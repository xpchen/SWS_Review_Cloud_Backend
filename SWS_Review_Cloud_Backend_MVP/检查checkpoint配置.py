#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查当前数据库中的checkpoint配置
用于诊断重复问题
"""
import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app import db
from app.settings import settings

# Windows控制台编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

_schema = settings.DB_SCHEMA


def check_checkpoints():
    """检查所有checkpoint配置"""
    print("=" * 80)
    print("检查 Checkpoint 配置")
    print("=" * 80)
    print()
    
    # 查询所有启用的checkpoint
    sql = f"""
    SELECT code, name, category, engine_type, review_category, enabled, order_index,
           rule_config_json->>'executor' as executor,
           rule_config_json->'only_checks' as only_checks
    FROM {_schema}.review_checkpoint
    WHERE enabled = true
    ORDER BY order_index NULLS LAST, code
    """
    
    checkpoints = db.fetch_all(sql, {})
    
    if not checkpoints:
        print("❌ 没有找到启用的checkpoint")
        return
    
    print(f"共找到 {len(checkpoints)} 个启用的checkpoint")
    print()
    
    # 按executor分组统计
    executor_groups = {}
    for cp in checkpoints:
        executor = cp.get("executor") or "未配置"
        if executor not in executor_groups:
            executor_groups[executor] = []
        executor_groups[executor].append(cp)
    
    print("=" * 80)
    print("按 Executor 分组统计")
    print("=" * 80)
    print()
    
    for executor, cps in sorted(executor_groups.items()):
        print(f"Executor: {executor}")
        print(f"  数量: {len(cps)} 个checkpoint")
        print()
        
        # 检查是否有only_checks配置
        with_only_checks = [cp for cp in cps if cp.get("only_checks") and len(cp.get("only_checks", [])) > 0]
        without_only_checks = [cp for cp in cps if not cp.get("only_checks") or len(cp.get("only_checks", [])) == 0]
        
        if with_only_checks:
            print(f"  ✅ 已配置 only_checks: {len(with_only_checks)} 个")
            for cp in with_only_checks[:5]:  # 只显示前5个
                only_checks = cp.get("only_checks", [])
                if isinstance(only_checks, str):
                    try:
                        only_checks = json.loads(only_checks)
                    except:
                        only_checks = []
                print(f"     - {cp['code']}: {only_checks}")
            if len(with_only_checks) > 5:
                print(f"     ... 还有 {len(with_only_checks) - 5} 个")
        
        if without_only_checks:
            print(f"  ⚠️  未配置 only_checks: {len(without_only_checks)} 个")
            for cp in without_only_checks[:10]:  # 显示前10个
                print(f"     - {cp['code']}: {cp['name']}")
            if len(without_only_checks) > 10:
                print(f"     ... 还有 {len(without_only_checks) - 10} 个")
        
        print()
    
    # 检查重复问题
    print("=" * 80)
    print("重复问题诊断")
    print("=" * 80)
    print()
    
    # 检查format_review executor
    format_cps = executor_groups.get("format_review", [])
    if format_cps:
        print(f"format_review executor 共有 {len(format_cps)} 个checkpoint")
        without_only = [cp for cp in format_cps if not cp.get("only_checks") or len(cp.get("only_checks", [])) == 0]
        if without_only:
            print(f"⚠️  其中 {len(without_only)} 个没有 only_checks 配置，可能导致重复问题：")
            for cp in without_only:
                print(f"   - {cp['code']}: {cp['name']}")
        else:
            print("✅ 所有checkpoint都已配置 only_checks")
        print()
    
    # 检查content_review executor
    content_cps = executor_groups.get("content_review", [])
    if content_cps:
        print(f"content_review executor 共有 {len(content_cps)} 个checkpoint")
        without_only = [cp for cp in content_cps if not cp.get("only_checks") or len(cp.get("only_checks", [])) == 0]
        if without_only:
            print(f"⚠️  其中 {len(without_only)} 个没有 only_checks 配置，可能导致重复问题：")
            for cp in without_only:
                print(f"   - {cp['code']}: {cp['name']}")
        else:
            print("✅ 所有checkpoint都已配置 only_checks")
        print()
    
    # 检查executor不匹配问题
    print("=" * 80)
    print("Executor 不匹配问题")
    print("=" * 80)
    print()
    
    from app.rule_engine import EXECUTOR_REGISTRY
    valid_executors = set(EXECUTOR_REGISTRY.keys())
    
    unknown_executors = []
    for executor, cps in executor_groups.items():
        if executor != "未配置" and executor not in valid_executors:
            unknown_executors.extend(cps)
    
    if unknown_executors:
        print(f"⚠️  发现 {len(unknown_executors)} 个checkpoint使用了未知的executor：")
        for cp in unknown_executors:
            executor = cp.get("executor")
            print(f"   - {cp['code']}: executor='{executor}' (不存在)")
    else:
        print("✅ 所有checkpoint的executor都是有效的")
    
    print()
    print("=" * 80)
    print("建议")
    print("=" * 80)
    print()
    
    format_without = [cp for cp in executor_groups.get("format_review", []) 
                      if not cp.get("only_checks") or len(cp.get("only_checks", [])) == 0]
    content_without = [cp for cp in executor_groups.get("content_review", []) 
                       if not cp.get("only_checks") or len(cp.get("only_checks", [])) == 0]
    
    if format_without or content_without or unknown_executors:
        print("需要执行以下迁移：")
        if format_without or content_without:
            print("  1. 执行迁移009：为checkpoint添加only_checks配置")
            print("     python 执行迁移009.py")
        if unknown_executors:
            print("  2. 修复executor名称不匹配问题（迁移009已包含）")
        if format_without or content_without:
            print("  3. （可选）执行迁移010：禁用旧的重复checkpoint")
            print("     python 执行迁移010.py")
    else:
        print("✅ 所有checkpoint配置正常，无需迁移")


if __name__ == "__main__":
    try:
        check_checkpoints()
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
