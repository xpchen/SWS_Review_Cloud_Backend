#!/usr/bin/env python
"""
快速执行迁移 007: 添加版本进度跟踪字段
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

import psycopg
from app.settings import settings

def run_migration():
    """执行迁移 007"""
    migration_file = project_root / "docs" / "migrations" / "007_add_version_progress_fields.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        sys.exit(1)
    
    print(f"📄 读取迁移文件: {migration_file}")
    with open(migration_file, "r", encoding="utf-8") as f:
        migration_sql = f.read()
    
    # 从环境变量或设置中获取数据库连接信息
    db_url = settings.DATABASE_URL
    print(f"🔗 连接到数据库: {db_url.split('@')[-1] if '@' in db_url else '***'}")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("🚀 开始执行迁移...")
                cur.execute(migration_sql)
                conn.commit()
                print("✅ 迁移执行成功！")
                
                # 验证字段是否添加成功
                print("\n🔍 验证字段...")
                cur.execute("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = 'document_version'
                      AND column_name IN ('progress', 'current_step')
                    ORDER BY column_name
                """, (settings.DB_SCHEMA,))
                
                rows = cur.fetchall()
                if rows:
                    print("\n已添加的字段:")
                    for row in rows:
                        print(f"  - {row[0]}: {row[1]} (默认值: {row[2]})")
                else:
                    print("⚠️  未找到字段，请检查迁移是否成功执行")
                    
    except psycopg.Error as e:
        print(f"❌ 数据库错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("迁移 007: 添加版本进度跟踪字段")
    print("=" * 60)
    run_migration()
    print("=" * 60)
