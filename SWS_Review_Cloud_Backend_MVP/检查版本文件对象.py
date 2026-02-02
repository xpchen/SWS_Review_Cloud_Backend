#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查版本的文件对象状态
用法: python 检查版本文件对象.py <版本ID>
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
from app.services import version_service, file_service

_schema = settings.DB_SCHEMA


def check_version_files(version_id: int):
    """检查版本的文件对象"""
    print("=" * 60)
    print(f"检查版本 {version_id} 的文件对象")
    print("=" * 60)
    print()
    
    # 获取版本信息
    version = version_service.get_version(version_id)
    if not version:
        print(f"❌ 版本 {version_id} 不存在")
        return
    
    print("版本信息:")
    print(f"  版本ID: {version.get('id')}")
    print(f"  版本号: {version.get('version_no')}")
    print(f"  状态: {version.get('status')}")
    print(f"  文档ID: {version.get('document_id')}")
    print()
    
    # 检查源文件
    source_file_id = version.get("source_file_id")
    print("源文件 (source_file_id):")
    if source_file_id:
        print(f"  文件对象ID: {source_file_id}")
        fo = file_service.get_file_object(source_file_id)
        if fo:
            print(f"  ✅ 文件对象存在")
            print(f"  存储类型: {fo.get('storage')}")
            print(f"  存储桶: {fo.get('bucket')}")
            print(f"  对象键: {fo.get('object_key')}")
            print(f"  文件名: {fo.get('filename')}")
            print(f"  内容类型: {fo.get('content_type')}")
            print(f"  文件大小: {fo.get('size')} 字节")
            
            object_key = fo.get("object_key")
            if not object_key or object_key == "NULL" or object_key.upper() == "NULL":
                print()
                print("  ❌ 错误: object_key 无效!")
                print(f"     当前值: {repr(object_key)}")
                print()
                print("  可能的原因:")
                print("    1. 文件上传时 object_key 未正确设置")
                print("    2. 数据库中的 object_key 字段为 NULL")
                print("    3. 文件对象记录不完整")
                print()
                print("  解决方案:")
                print("    1. 检查文件上传流程")
                print("    2. 重新上传文件")
                print("    3. 检查数据库中的 file_object 表")
            else:
                print(f"  ✅ object_key 有效: {object_key}")
        else:
            print(f"  ❌ 文件对象不存在 (ID: {source_file_id})")
    else:
        print("  ❌ source_file_id 为空")
    
    print()
    
    # 检查PDF文件
    pdf_file_id = version.get("pdf_file_id")
    print("PDF文件 (pdf_file_id):")
    if pdf_file_id:
        print(f"  文件对象ID: {pdf_file_id}")
        fo = file_service.get_file_object(pdf_file_id)
        if fo:
            print(f"  ✅ 文件对象存在")
            print(f"  对象键: {fo.get('object_key')}")
            print(f"  文件名: {fo.get('filename')}")
            print(f"  文件大小: {fo.get('size')} 字节")
        else:
            print(f"  ❌ 文件对象不存在 (ID: {pdf_file_id})")
    else:
        print("  ⚠️  PDF文件尚未生成（正常，如果版本还在处理中）")
    
    print()
    
    # 检查其他文件
    structure_file_id = version.get("structure_json_file_id")
    page_map_file_id = version.get("page_map_json_file_id")
    text_full_file_id = version.get("text_full_file_id")
    
    print("其他文件:")
    if structure_file_id:
        print(f"  结构JSON文件ID: {structure_file_id}")
    if page_map_file_id:
        print(f"  页面映射文件ID: {page_map_file_id}")
    if text_full_file_id:
        print(f"  全文文件ID: {text_full_file_id}")
    if not structure_file_id and not page_map_file_id and not text_full_file_id:
        print("  ⚠️  暂无其他文件（正常，如果版本还在处理中）")
    
    print()
    print("=" * 60)
    
    # 查询数据库中的原始数据
    print()
    print("数据库原始数据:")
    print("-" * 60)
    sql = f"""
    SELECT id, source_file_id, pdf_file_id, structure_json_file_id, 
           page_map_json_file_id, text_full_file_id, status
    FROM {_schema}.document_version
    WHERE id = %(version_id)s
    """
    row = db.fetch_one(sql, {"version_id": version_id})
    if row:
        print(f"source_file_id: {row.get('source_file_id')}")
        print(f"pdf_file_id: {row.get('pdf_file_id')}")
        print(f"structure_json_file_id: {row.get('structure_json_file_id')}")
        print(f"page_map_json_file_id: {row.get('page_map_json_file_id')}")
        print(f"text_full_file_id: {row.get('text_full_file_id')}")
        print(f"status: {row.get('status')}")
    
    print()
    if source_file_id:
        print("文件对象表原始数据:")
        print("-" * 60)
        sql = f"""
        SELECT id, storage, bucket, object_key, filename, content_type, size
        FROM {_schema}.file_object
        WHERE id = %(file_id)s
        """
        fo_row = db.fetch_one(sql, {"file_id": source_file_id})
        if fo_row:
            print(f"id: {fo_row.get('id')}")
            print(f"storage: {fo_row.get('storage')}")
            print(f"bucket: {fo_row.get('bucket')}")
            print(f"object_key: {repr(fo_row.get('object_key'))}")
            print(f"filename: {fo_row.get('filename')}")
            print(f"content_type: {fo_row.get('content_type')}")
            print(f"size: {fo_row.get('size')}")
        else:
            print(f"❌ 文件对象 {source_file_id} 在数据库中不存在")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python 检查版本文件对象.py <版本ID>")
        sys.exit(1)
    
    try:
        version_id = int(sys.argv[1])
        check_version_files(version_id)
    except ValueError:
        print(f"❌ 无效的版本ID: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
