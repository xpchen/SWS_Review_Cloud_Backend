#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行迁移012: review_issue 表增加 review_type 列（形式/技术统计用）
若当前数据库用户不是表属主，会提示用表属主账号执行下方 SQL。
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.settings import settings

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_schema = getattr(settings, "DB_SCHEMA", "sws")

SQL = f"""
ALTER TABLE {_schema}.review_issue
ADD COLUMN IF NOT EXISTS review_type varchar(64);
"""


def execute_migration():
    print("执行迁移012: review_issue.review_type")
    try:
        from app import db
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
                conn.commit()
        print("  OK")
        return True
    except Exception as e:
        err = str(e)
        print(f"  FAIL: {err}")
        if "属主" in err or "owner" in err.lower() or "permission" in err.lower():
            print()
            print("当前用户不是表 review_issue 的属主，无法执行 ALTER TABLE。")
            print("请使用表属主账号（或库管理员）在数据库中执行以下 SQL：")
            print("-" * 60)
            print(SQL.strip())
            print("-" * 60)
            print("执行后应用会自动写入 review_type，无需改代码。")
        return False


if __name__ == "__main__":
    execute_migration()
