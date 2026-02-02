#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行迁移011: 修复CP_*系列checkpoint的executor字段
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
    """执行迁移011"""
    migration_file = project_root.parent / "docs" / "migrations" / "011_fix_cp_checkpoint_executor.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print("=" * 60)
    print("执行迁移011: 修复CP_*系列checkpoint的executor字段")
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
        
        # 验证修复结果
        print("验证修复结果:")
        print("-" * 60)
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT code, rule_config_json->>'executor' as json_executor
                    FROM sws.review_checkpoint
                    WHERE code IN ('CP_SUM_MISMATCH', 'CP_UNIT_INCONSISTENT', 'CP_MISSING_SECTION')
                    ORDER BY code
                """)
                
                results = cur.fetchall()
                for row in results:
                    code, json_executor = row
                    status = "✅" if json_executor else "❌"
                    print(f"{status} {code}: rule_config_json.executor={json_executor}")
        
        print()
        print("已修复以下checkpoint的executor字段：")
        print("  - CP_SUM_MISMATCH -> sum_mismatch")
        print("  - CP_UNIT_INCONSISTENT -> unit_inconsistent")
        print("  - CP_MISSING_SECTION -> missing_section")
        print()
        print("现在重新运行审查任务应该不会再出现'Unknown executor'警告了。")
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
