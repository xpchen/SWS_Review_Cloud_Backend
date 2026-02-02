#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行迁移010：禁用旧的重复checkpoint
如果存在新的FMT_R_*/CNT_R_*系列，禁用旧的FORMAT_*/CONTENT_*系列
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
    """执行迁移010"""
    migration_file = project_root / "docs" / "migrations" / "010_disable_duplicate_checkpoints.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print("=" * 60)
    print("执行迁移010：禁用旧的重复checkpoint")
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
        print("已禁用以下旧的checkpoint（如果存在新的FMT_R_*/CNT_R_*系列）：")
        print("  - FORMAT_STRUCTURE, FORMAT_NUMBERING, FORMAT_REFERENCE, FORMAT_UNIT, FORMAT_TABLE")
        print("  - CONTENT_SECTIONS, CONTENT_TRIGGER, CONTENT_ELEMENTS")
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
