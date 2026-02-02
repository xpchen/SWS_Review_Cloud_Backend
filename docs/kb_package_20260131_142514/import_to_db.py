#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 kb_sources.json + kb_chunks.jsonl 导入到系统数据库

使用方法：
1. 确保数据库连接配置正确（.env文件中的DATABASE_URL）
2. 运行：python import_to_db.py --package_dir <知识库包目录>

说明：
- 本脚本会为每个source创建 file_object（如果不存在）
- 创建 kb_source 记录
- 批量导入 kb_chunk（ON CONFLICT DO NOTHING）
- 将 kb_source 标记为 READY

注意：
- IMAGE_ONLY 的PDF需要先OCR后才能使用
- 本脚本假设PDF文件已经上传到storage（或使用虚拟file_object）
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

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
    # 尝试从当前目录加载
    load_dotenv()

# 尝试使用项目模块，如果失败则使用psycopg直接连接
try:
    sys.path.insert(0, str(project_root / "SWS_Review_Cloud_Backend_MVP"))
    from app import db
    from app.settings import settings
    USE_PROJECT_MODULE = True
except ImportError:
    # 如果无法导入项目模块，使用psycopg直接连接
    try:
        import psycopg
        USE_PROJECT_MODULE = False
    except ImportError:
        print("错误: 需要安装 psycopg 或项目依赖")
        print("请运行: pip install psycopg[binary]")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="导入知识库包到数据库")
    ap.add_argument('--package_dir', type=str, default=str(Path(__file__).resolve().parent))
    ap.add_argument('--storage', type=str, default='LOCAL', help='存储类型：LOCAL 或 minio')
    ap.add_argument('--bucket', type=str, default='kb', help='存储bucket')
    ap.add_argument('--dry_run', action='store_true', help='干运行，不实际导入')
    args = ap.parse_args()

    pkg = Path(args.package_dir)
    sources_file = pkg / 'kb_sources.json'
    chunks_file = pkg / 'kb_chunks.jsonl'

    if not sources_file.exists():
        raise SystemExit(f'kb_sources.json not found in {pkg}')
    if not chunks_file.exists():
        raise SystemExit(f'kb_chunks.jsonl not found in {pkg}')

    sources = json.loads(sources_file.read_text(encoding='utf-8'))
    
    # 获取数据库连接信息
    if USE_PROJECT_MODULE:
        schema = settings.DB_SCHEMA
        db_url = settings.DATABASE_URL
    else:
        # 从环境变量读取
        schema = os.getenv('DB_SCHEMA', 'sws')
        db_url = os.getenv('DATABASE_URL', '')
        if not db_url:
            raise SystemExit('需要设置DATABASE_URL环境变量，或确保可以导入app模块')

    print(f"准备导入 {len(sources)} 个知识库源...")
    print(f"数据库schema: {schema}")
    print(f"存储类型: {args.storage}, bucket: {args.bucket}")

    if args.dry_run:
        print("\n[DRY RUN] 不会实际写入数据库\n")

    total_chunks = 0
    imported_sources = 0

    # 获取数据库连接
    if USE_PROJECT_MODULE:
        conn = db.pool.connection()
    else:
        conn = psycopg.connect(db_url)
    
    with conn:
        if USE_PROJECT_MODULE:
            conn.autocommit = False
        else:
            conn.autocommit = False
        with conn.cursor() as cur:
            for src in sources:
                fname = src['filename']
                source_name = src['name']
                kb_type = src.get('kb_type', 'NORM')
                extract_method = src.get('extract_method', 'TEXT')
                
                print(f"\n处理: {source_name}")
                print(f"  文件: {fname}")
                print(f"  类型: {kb_type}, 提取方法: {extract_method}")
                
                if extract_method == 'IMAGE_ONLY':
                    print(f"  ⚠️  警告: 此文件为扫描件(IMAGE_ONLY)，需要先OCR")
                    print(f"  跳过导入chunks（block_count=0）")
                
                if args.dry_run:
                    print(f"  [DRY] 将创建 kb_source: {source_name}")
                    continue

                # 1) 检查或创建 file_object
                # 先检查是否已存在（通过sha256）
                sha256 = src.get('sha256')
                file_id = None
                
                if sha256:
                    cur.execute(
                        f"SELECT id FROM {schema}.file_object WHERE sha256 = %s LIMIT 1",
                        (sha256,)
                    )
                    row = cur.fetchone()
                    if row:
                        file_id = row[0]
                        print(f"  ✓ 找到已存在的file_object: id={file_id}")
                
                if not file_id:
                    # 创建新的file_object（虚拟，因为PDF文件可能不在storage中）
                    obj_key = f"kb/{fname}"
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.file_object 
                        (storage, bucket, object_key, filename, content_type, size, sha256)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """,
                        (
                            args.storage,
                            args.bucket,
                            obj_key,
                            fname,
                            'application/pdf',
                            int(src.get('size', 0)),
                            sha256
                        )
                    )
                    row = cur.fetchone()
                    if row:
                        file_id = row[0]
                        print(f"  ✓ 创建file_object: id={file_id}")
                    else:
                        # 冲突，重新查询
                        cur.execute(
                            f"SELECT id FROM {schema}.file_object WHERE sha256 = %s LIMIT 1",
                            (sha256,)
                        )
                        row = cur.fetchone()
                        if row:
                            file_id = row[0]
                            print(f"  ✓ 使用已存在的file_object: id={file_id}")

                if not file_id:
                    print(f"  ✗ 无法创建或找到file_object，跳过")
                    continue

                # 2) 检查或创建 kb_source
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.kb_source 
                    WHERE name = %s AND file_id = %s
                    LIMIT 1
                    """,
                    (source_name, file_id)
                )
                row = cur.fetchone()
                
                if row:
                    kb_source_id = row[0]
                    print(f"  ✓ 找到已存在的kb_source: id={kb_source_id}")
                    # 检查是否需要更新状态
                    cur.execute(
                        f"SELECT status FROM {schema}.kb_source WHERE id = %s",
                        (kb_source_id,)
                    )
                    status_row = cur.fetchone()
                    if status_row and status_row[0] != 'READY':
                        cur.execute(
                            f"UPDATE {schema}.kb_source SET status = 'READY', updated_at = now() WHERE id = %s",
                            (kb_source_id,)
                        )
                        print(f"  ✓ 更新kb_source状态为READY")
                else:
                    # 创建新的kb_source
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.kb_source (name, kb_type, file_id, status)
                        VALUES (%s, %s, %s, 'PROCESSING')
                        RETURNING id
                        """,
                        (source_name, kb_type, file_id)
                    )
                    kb_source_id = cur.fetchone()[0]
                    print(f"  ✓ 创建kb_source: id={kb_source_id}")

                # 3) 导入kb_chunk（仅当extract_method不是IMAGE_ONLY时）
                if extract_method == 'IMAGE_ONLY':
                    print(f"  ⚠️  跳过chunks导入（IMAGE_ONLY）")
                    # 标记为READY（即使没有chunks）
                    cur.execute(
                        f"UPDATE {schema}.kb_source SET status = 'READY', updated_at = now() WHERE id = %s",
                        (kb_source_id,)
                    )
                    conn.commit()
                    continue

                # 读取chunks
                source_local_id = src['source_local_id']
                inserted_chunks = 0
                skipped_chunks = 0

                with chunks_file.open('r', encoding='utf-8') as fr:
                    for line_num, line in enumerate(fr, 1):
                        try:
                            obj = json.loads(line.strip())
                            # 兼容两种字段名：kb_source_local_id 或 source_local_id
                            chunk_source_id = obj.get('kb_source_local_id') or obj.get('source_local_id')
                            if chunk_source_id != source_local_id:
                                continue
                            
                            chunk_text = obj.get('chunk_text', '')
                            if not chunk_text:
                                continue
                            meta_json = obj.get('meta_json') or {}
                            hash_val = obj.get('hash')
                            if not hash_val:
                                # 如果没有hash，生成一个
                                import hashlib
                                hash_val = hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()
                            
                            # 插入chunk（embedding字段暂时为NULL，后续可以批量生成）
                            # 检查embedding列是否存在
                            try:
                                cur.execute(
                                    f"""
                                    INSERT INTO {schema}.kb_chunk (kb_source_id, chunk_text, meta_json, hash, embedding)
                                    VALUES (%s, %s, %s::jsonb, %s, NULL)
                                    ON CONFLICT (kb_source_id, hash) DO NOTHING
                                    """,
                                    (
                                        kb_source_id,
                                        chunk_text[:10000],  # 限制长度
                                        json.dumps(meta_json, ensure_ascii=False),
                                        hash_val
                                    )
                                )
                            except Exception as e:
                                # 如果embedding列不存在，使用不带embedding的版本
                                if "embedding" in str(e).lower():
                                    cur.execute(
                                        f"""
                                        INSERT INTO {schema}.kb_chunk (kb_source_id, chunk_text, meta_json, hash)
                                        VALUES (%s, %s, %s::jsonb, %s)
                                        ON CONFLICT (kb_source_id, hash) DO NOTHING
                                        """,
                                        (
                                            kb_source_id,
                                            chunk_text[:10000],
                                            json.dumps(meta_json, ensure_ascii=False),
                                            hash_val
                                        )
                                    )
                                else:
                                    raise
                            if cur.rowcount > 0:
                                inserted_chunks += 1
                            else:
                                skipped_chunks += 1
                                
                        except json.JSONDecodeError as e:
                            print(f"  ⚠️  警告: 第{line_num}行JSON解析失败: {e}")
                            continue
                        except Exception as e:
                            print(f"  ⚠️  警告: 第{line_num}行处理失败: {e}")
                            continue

                # 4) 标记为READY
                cur.execute(
                    f"UPDATE {schema}.kb_source SET status = 'READY', updated_at = now() WHERE id = %s",
                    (kb_source_id,)
                )
                
                if USE_PROJECT_MODULE:
                    conn.commit()
                else:
                    conn.commit()
                total_chunks += inserted_chunks
                imported_sources += 1
                
                print(f"  ✓ 完成: 导入{inserted_chunks}个chunks, 跳过{skipped_chunks}个重复chunks")

    print(f"\n{'='*60}")
    print(f"导入完成!")
    print(f"  成功导入源: {imported_sources}/{len(sources)}")
    print(f"  总chunks数: {total_chunks}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
