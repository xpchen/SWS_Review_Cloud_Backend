#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出checkpoint数据为JSON格式
用于分析和修复重复问题
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

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


def export_checkpoints():
    """导出所有checkpoint数据"""
    print("=" * 60)
    print("导出 Checkpoint 数据")
    print("=" * 60)
    print()
    
    # 查询所有checkpoint（包括禁用的）
    sql = f"""
    SELECT id, code, name, category, engine_type, review_category, 
           target_outline_prefix, prompt_template, enabled, order_index,
           rule_config_json, created_at, updated_at
    FROM {_schema}.review_checkpoint
    ORDER BY enabled DESC, order_index NULLS LAST, code
    """
    
    checkpoints = db.fetch_all(sql, {})
    
    if not checkpoints:
        print("❌ 没有找到checkpoint数据")
        return
    
    print(f"共找到 {len(checkpoints)} 个checkpoint")
    print()
    
    # 转换为可序列化的格式
    export_data = {
        "export_time": datetime.now().isoformat(),
        "total_count": len(checkpoints),
        "enabled_count": sum(1 for cp in checkpoints if cp.get("enabled")),
        "disabled_count": sum(1 for cp in checkpoints if not cp.get("enabled")),
        "checkpoints": []
    }
    
    for cp in checkpoints:
        # 处理rule_config_json（可能是dict或str）
        rule_config = cp.get("rule_config_json")
        if isinstance(rule_config, str):
            try:
                rule_config = json.loads(rule_config)
            except:
                rule_config = {}
        elif rule_config is None:
            rule_config = {}
        
        # 提取关键信息
        cp_data = {
            "id": cp.get("id"),
            "code": cp.get("code"),
            "name": cp.get("name"),
            "category": cp.get("category"),
            "engine_type": cp.get("engine_type"),
            "review_category": cp.get("review_category"),
            "enabled": cp.get("enabled"),
            "order_index": cp.get("order_index"),
            "executor": rule_config.get("executor") if isinstance(rule_config, dict) else None,
            "only_checks": rule_config.get("only_checks") if isinstance(rule_config, dict) else None,
            "has_only_checks": bool(rule_config.get("only_checks") if isinstance(rule_config, dict) else False),
            "rule_config_json": rule_config,
        }
        export_data["checkpoints"].append(cp_data)
    
    # 保存为JSON文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = project_root / f"checkpoint_data_export_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"✅ 数据已导出到: {output_file}")
    print()
    
    # 显示统计信息
    print("统计信息：")
    print(f"  总数量: {export_data['total_count']}")
    print(f"  启用: {export_data['enabled_count']}")
    print(f"  禁用: {export_data['disabled_count']}")
    print()
    
    # 按executor统计
    executor_stats = {}
    for cp in export_data["checkpoints"]:
        if cp["enabled"]:
            executor = cp["executor"] or "未配置"
            if executor not in executor_stats:
                executor_stats[executor] = {"total": 0, "with_only_checks": 0, "without_only_checks": 0}
            executor_stats[executor]["total"] += 1
            if cp["has_only_checks"]:
                executor_stats[executor]["with_only_checks"] += 1
            else:
                executor_stats[executor]["without_only_checks"] += 1
    
    print("按 Executor 统计（仅启用的checkpoint）：")
    for executor, stats in sorted(executor_stats.items()):
        print(f"  {executor}:")
        print(f"    总数: {stats['total']}")
        print(f"    已配置only_checks: {stats['with_only_checks']}")
        print(f"    未配置only_checks: {stats['without_only_checks']}")
        if stats['without_only_checks'] > 0 and executor in ("format_review", "content_review"):
            print(f"    ⚠️  可能导致重复问题！")
        print()
    
    print(f"数据文件位置: {output_file}")
    print("可以将此文件内容发送给我进行分析")


if __name__ == "__main__":
    try:
        export_checkpoints()
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
