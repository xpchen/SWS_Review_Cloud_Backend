#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""\
将 kb_sources.json + kb_chunks.jsonl 导入到 Postgres：sws.file_object / sws.kb_source / sws.kb_chunk

要求：已执行 docs/migrations/002_kb_tables.sql

用法：
  python import_to_postgres.py --dsn "host=... port=5432 dbname=... user=... password=..." --schema sws

说明：
- 本脚本会为每个PDF创建一条 file_object（storage=LOCAL,bucket=kb,object_key=filename）
- 再创建 kb_source（kb_type=NORM,status=PROCESSING）
- 再写入 kb_chunk（ON CONFLICT(kb_source_id,hash) DO NOTHING）
- 最后将 kb_source 标记为 READY
"""

import os, json, argparse
from pathlib import Path
import psycopg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dsn', type=str, default=os.getenv('DATABASE_URL', ''), help='psycopg DSN')
    ap.add_argument('--schema', type=str, default=os.getenv('DB_SCHEMA', 'sws'))
    ap.add_argument('--package_dir', type=str, default=str(Path(__file__).resolve().parent))
    ap.add_argument('--storage', type=str, default='LOCAL')
    ap.add_argument('--bucket', type=str, default='kb')
    ap.add_argument('--object_prefix', type=str, default='')
    ap.add_argument('--dry_run', action='store_true')
    args = ap.parse_args()

    if not args.dsn:
        raise SystemExit('Missing --dsn (or env DATABASE_URL)')

    pkg = Path(args.package_dir)
    sources = json.loads((pkg / 'kb_sources.json').read_text(encoding='utf-8'))

    chunks_path = pkg / 'kb_chunks.jsonl'
    if not chunks_path.exists():
        raise SystemExit('kb_chunks.jsonl not found')

    schema = args.schema

    with psycopg.connect(args.dsn) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            for src in sources:
                fname = src['filename']
                obj_key = f"{args.object_prefix}{fname}" if args.object_prefix else fname

                if args.dry_run:
                    print(f"[DRY] would import source: {fname}")
                    continue

                # 1) file_object
                cur.execute(
                    f"""
                    INSERT INTO {schema}.file_object (storage,bucket,object_key,filename,content_type,size,sha256)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (args.storage, args.bucket, obj_key, fname, 'application/pdf', int(src.get('size', 0)), src.get('sha256'))
                )
                file_id = cur.fetchone()[0]

                # 2) kb_source
                cur.execute(
                    f"""
                    INSERT INTO {schema}.kb_source (name,kb_type,file_id,status)
                    VALUES (%s,%s,%s,'PROCESSING')
                    RETURNING id
                    """,
                    (src['name'], src.get('kb_type','NORM'), file_id)
                )
                kb_source_id = cur.fetchone()[0]

                # 3) kb_chunk batch insert
                inserted = 0
                with chunks_path.open('r', encoding='utf-8') as fr:
                    for line in fr:
                        obj = json.loads(line)
                        if obj.get('source_local_id') != src['source_local_id']:
                            continue
                        chunk_text = obj['chunk_text']
                        meta_json = json.dumps(obj.get('meta_json') or {}, ensure_ascii=False)
                        h = obj['hash']
                        cur.execute(
                            f"""
                            INSERT INTO {schema}.kb_chunk (kb_source_id, chunk_text, meta_json, hash)
                            VALUES (%s,%s,%s,%s)
                            ON CONFLICT (kb_source_id, hash) DO NOTHING
                            """,
                            (kb_source_id, chunk_text[:10000], meta_json, h)
                        )
                        inserted += cur.rowcount

                # 4) mark ready
                cur.execute(f"UPDATE {schema}.kb_source SET status='READY', updated_at=now() WHERE id=%s", (kb_source_id,))
                conn.commit()
                print(f"[OK] imported: {fname} -> kb_source_id={kb_source_id}, chunks_inserted={inserted}")


if __name__ == '__main__':
    main()
