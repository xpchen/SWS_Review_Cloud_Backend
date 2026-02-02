#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行迁移009：修复checkpoint重复问题
为每个checkpoint添加only_checks配置
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

from app import db
from app.settings import settings

# Windows控制台编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def execute_migration():
    """执行迁移009"""
    migration_file = project_root / "docs" / "migrations" / "009_fix_checkpoint_only_checks.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print("=" * 60)
    print("执行迁移009：修复checkpoint重复问题")
    print("=" * 60)
    print()
    print(f"迁移文件: {migration_file}")
    print()
    
    # 读取SQL文件
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
    except Exception as e:
        print(f"❌ 读取迁移文件失败: {e}")
        return False
    
    # 执行SQL
    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                print("执行SQL语句...")
                cur.execute(sql_content)
                conn.commit()
                print("   ✅ 成功")
        
        print()
        print("=" * 60)
        print("✅ 迁移执行完成！")
        print("=" * 60)
        print()
        print("已为以下checkpoint添加only_checks配置：")
        print("  - FORMAT_STRUCTURE: cover_required_elements, toc_present")
        print("  - FORMAT_NUMBERING: heading_numbering, figure_numbering, table_numbering")
        print("  - FORMAT_REFERENCE: table_referenced, figure_referenced")
        print("  - FORMAT_UNIT: unit_symbol_consistency, table_unit_column_present")
        print("  - FORMAT_TABLE: table_caption_present, table_numbering, table_referenced, table_unit_column_present")
        print("  - FMT_R_001~FMT_R_012: 根据code自动配置only_checks")
        print("  - CONTENT_SECTIONS: required_sections")
        print("  - CONTENT_TRIGGER: trigger_requirements")
        print("  - CONTENT_ELEMENTS: required_elements")
        print()
        print("已修复executor名称不匹配问题：")
        print("  - CP_SUM_MISMATCH: cp_sum_mismatch -> sum_mismatch")
        print("  - CP_UNIT_INCONSISTENT: cp_unit_inconsistent -> unit_inconsistent")
        print("  - CP_MISSING_SECTION: cp_missing_section -> missing_section")
        print()
        print("现在重新运行审查任务应该不会再有重复问题了。")
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 迁移执行失败")
        print("=" * 60)
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
