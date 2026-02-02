#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行迁移006：Checkpoint引擎重构
添加 engine_type 和 review_category 字段
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
    """执行迁移006"""
    migration_file = project_root / "docs" / "migrations" / "006_checkpoint_schema_refactor.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print("=" * 60)
    print("执行迁移006：Checkpoint引擎重构")
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
    
    # 分割SQL语句（按分号分割，但要注意函数定义中的分号）
    # 简单处理：按行分割，忽略注释和空行
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        line = line.strip()
        # 跳过注释和空行
        if not line or line.startswith('--'):
            continue
        
        current_statement.append(line)
        
        # 如果行以分号结尾，说明是一个完整的语句
        if line.endswith(';'):
            statement = ' '.join(current_statement)
            if statement.strip():
                statements.append(statement)
            current_statement = []
    
    # 执行每个SQL语句
    print(f"共 {len(statements)} 条SQL语句")
    print()
    
    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                for i, statement in enumerate(statements, 1):
                    print(f"[{i}/{len(statements)}] 执行SQL语句...")
                    try:
                        cur.execute(statement)
                        conn.commit()
                        print(f"   ✅ 成功")
                    except Exception as e:
                        # 如果是"字段已存在"或"索引已存在"的错误，可以忽略
                        error_msg = str(e)
                        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                            print(f"   ⚠️  已存在（可忽略）: {error_msg[:100]}")
                            conn.rollback()
                        else:
                            print(f"   ❌ 失败: {error_msg}")
                            conn.rollback()
                            raise
                    print()
        
        print("=" * 60)
        print("✅ 迁移执行完成！")
        print("=" * 60)
        print()
        print("已添加的字段：")
        print("  - review_checkpoint.engine_type")
        print("  - review_checkpoint.review_category")
        print("  - review_issue.checkpoint_code（如果不存在）")
        print()
        print("现在可以重新运行审查任务了。")
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
