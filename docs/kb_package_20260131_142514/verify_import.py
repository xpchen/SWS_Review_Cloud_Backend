#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证知识库导入结果"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载.env文件
project_root = Path(__file__).resolve().parent.parent.parent
env_file = project_root / "SWS_Review_Cloud_Backend_MVP" / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

db_url = os.getenv('DATABASE_URL')
schema = os.getenv('DB_SCHEMA', 'sws')

if not db_url:
    print("错误: 未找到DATABASE_URL环境变量")
    sys.exit(1)

conn = psycopg.connect(db_url)
cur = conn.cursor()

print("=" * 80)
print("知识库导入验证结果")
print("=" * 80)

# 查询所有知识库源
cur.execute(f"""
    SELECT id, name, status, 
           (SELECT COUNT(*) FROM {schema}.kb_chunk WHERE kb_source_id = {schema}.kb_source.id) as chunk_count
    FROM {schema}.kb_source 
    ORDER BY id
""")
rows = cur.fetchall()

print(f"\n共 {len(rows)} 个知识库源:\n")
for r in rows:
    kb_id, name, status, chunk_count = r
    print(f"  ID: {kb_id:2d} | 状态: {status:12s} | Chunks: {chunk_count:4d} | {name}")

# 查询总chunks数
cur.execute(f"SELECT COUNT(*) FROM {schema}.kb_chunk")
total_chunks = cur.fetchone()[0]

# 查询有embedding的chunks数
try:
    cur.execute(f"SELECT COUNT(*) FROM {schema}.kb_chunk WHERE embedding IS NOT NULL")
    chunks_with_embedding = cur.fetchone()[0]
except:
    chunks_with_embedding = 0

print(f"\n总计:")
print(f"  - 总Chunks数: {total_chunks}")
print(f"  - 已生成Embedding的Chunks数: {chunks_with_embedding}")
print(f"  - 待生成Embedding的Chunks数: {total_chunks - chunks_with_embedding}")

print("=" * 80)

cur.close()
conn.close()
