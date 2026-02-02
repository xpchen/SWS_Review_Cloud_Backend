#!/usr/bin/env python
"""
单独测试 Word 文档处理流程
用法：
    python 测试文档处理.py <文档ID> <文件路径>
    或
    python 测试文档处理.py --version-id <版本ID>
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

import argparse
from app import db
from app.settings import settings
from app.services import upload_service, version_service, document_service
from app.worker import pipeline


def list_projects_and_documents():
    """列出所有项目和文档"""
    print("=" * 60)
    print("项目和文档列表")
    print("=" * 60)
    
    try:
        # 查询所有项目
        sql = f"SELECT id, name FROM {settings.DB_SCHEMA}.project ORDER BY id"
        projects = db.fetch_all(sql)
        
        if not projects:
            print("❌ 没有找到项目")
            print("\n提示: 需要先创建项目才能上传文档")
            return
        
        for project in projects:
            project_id = project["id"]
            project_name = project["name"]
            print(f"\n📁 项目 ID: {project_id}, 名称: {project_name}")
            
            # 查询项目下的文档
            documents = document_service.list_documents(project_id)
            if documents:
                for doc in documents:
                    print(f"   📄 文档 ID: {doc['id']}, 标题: {doc['title']}")
            else:
                print("   (无文档)")
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()


def get_or_create_document(document_id: int = None, project_id: int = 1, title: str = None):
    """获取或创建文档"""
    if document_id:
        # 检查文档是否存在
        doc = document_service.get_document(document_id)
        if doc:
            return document_id
        else:
            print(f"⚠️  文档 ID {document_id} 不存在")
            if title:
                print(f"📝 将创建新文档: {title}")
            else:
                print("❌ 需要提供文档标题才能创建")
                return None
    else:
        if not title:
            print("❌ 需要提供文档标题")
            return None
    
    # 创建新文档
    try:
        new_doc_id = document_service.create_document(project_id, title or f"测试文档_{document_id}")
        print(f"✅ 已创建文档 ID: {new_doc_id}")
        return new_doc_id
    except Exception as e:
        print(f"❌ 创建文档失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_upload_and_process(document_id: int, file_path: str, project_id: int = 1, auto_create: bool = True):
    """上传文件并处理"""
    print("=" * 60)
    print("测试：上传并处理 Word 文档")
    print("=" * 60)
    print(f"文档ID: {document_id}")
    print(f"文件路径: {file_path}")
    print()
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"❌ 错误: 文件不存在: {file_path}")
        return False
    
    # 读取文件
    print("📄 读取文件...")
    with open(file_path, "rb") as f:
        file_content = f.read()
    
    file_size = len(file_content)
    print(f"   文件大小: {file_size:,} 字节 ({file_size / 1024 / 1024:.2f} MB)")
    
    # 获取文件名
    filename = os.path.basename(file_path)
    print(f"   文件名: {filename}")
    print()
    
    # 检查或创建文档
    print("🔍 检查文档...")
    actual_doc_id = get_or_create_document(
        document_id=document_id,
        project_id=project_id,
        title=filename.replace(".docx", "")  # 使用文件名（去掉扩展名）作为标题
    )
    
    if not actual_doc_id:
        print("❌ 无法获取或创建文档")
        return False
    
    if actual_doc_id != document_id:
        print(f"ℹ️  使用文档 ID: {actual_doc_id} (原请求: {document_id})")
    
    print()
    
    # 上传文件
    print("📤 上传文件...")
    try:
        result = upload_service.upload_docx(
            document_id=actual_doc_id,
            file_content=file_content,
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            trigger_pipeline=False  # 不自动触发，我们手动处理
        )
        version_id = result["version_id"]
        version_no = result["version_no"]
        print(f"✅ 上传成功")
        print(f"   版本ID: {version_id}")
        print(f"   版本号: {version_no}")
        print()
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 手动处理
    return test_process_version(version_id)


def test_process_version(version_id: int):
    """处理指定版本"""
    print("=" * 60)
    print("测试：处理文档版本")
    print("=" * 60)
    print(f"版本ID: {version_id}")
    print()
    
    # 检查版本是否存在
    version = version_service.get_version(version_id)
    if not version:
        print(f"❌ 错误: 版本不存在: {version_id}")
        return False
    
    print(f"版本信息:")
    print(f"   文档ID: {version['document_id']}")
    print(f"   版本号: {version['version_no']}")
    print(f"   状态: {version['status']}")
    print()
    
    # 更新状态为 PROCESSING
    print("🔄 更新状态为 PROCESSING...")
    version_service.update_version_status(
        version_id, 
        "PROCESSING", 
        progress=0, 
        current_step="开始处理"
    )
    print("✅ 状态已更新")
    print()
    
    # 执行处理步骤
    steps = [
        ("DOCX转PDF", pipeline.convert_docx_to_pdf, 10),
        ("解析DOCX结构", pipeline.parse_docx_structure, 25),
        ("提取PDF布局", pipeline.extract_pdf_layout, 40),
        ("对齐块到PDF", pipeline.align_blocks_to_pdf, 55),
        ("抽取事实", pipeline.extract_facts, 70),
        ("构建块和索引", pipeline.build_chunks_and_index, 85),
        ("完成处理", pipeline.finalize_ready, 100),
    ]
    
    try:
        for step_name, step_func, progress in steps:
            print(f"📋 步骤: {step_name} (进度: {progress}%)")
            print("-" * 60)
            
            try:
                # 更新进度
                version_service.update_version_status(
                    version_id,
                    "PROCESSING",
                    progress=progress,
                    current_step=step_name
                )
                
                # 执行步骤
                result = step_func(version_id)
                
                # 如果有返回值，显示
                if result is not None:
                    if isinstance(result, int):
                        print(f"✅ {step_name} 完成 (返回: {result})")
                    else:
                        print(f"✅ {step_name} 完成")
                else:
                    print(f"✅ {step_name} 完成")
                
            except Exception as e:
                print(f"❌ {step_name} 失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 更新状态为失败
                version_service.update_version_status(
                    version_id,
                    "FAILED",
                    error_message=str(e)[:500],
                    progress=progress,
                    current_step=f"{step_name} (失败)"
                )
                return False
            
            print()
        
        print("=" * 60)
        print("✅ 所有步骤完成！")
        print("=" * 60)
        
        # 获取最终状态
        final_version = version_service.get_version(version_id)
        print(f"最终状态: {final_version['status']}")
        print(f"最终进度: {final_version.get('progress', 0)}%")
        print(f"当前步骤: {final_version.get('current_step', 'N/A')}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断处理")
        version_service.update_version_status(
            version_id,
            "FAILED",
            error_message="用户中断",
            progress=progress if 'progress' in locals() else 0,
            current_step="已中断"
        )
        return False
    except Exception as e:
        print(f"\n❌ 处理过程中出错: {e}")
        import traceback
        traceback.print_exc()
        version_service.update_version_status(
            version_id,
            "FAILED",
            error_message=str(e)[:500]
        )
        return False


def main():
    parser = argparse.ArgumentParser(description="测试 Word 文档处理流程")
    parser.add_argument(
        "document_id",
        type=int,
        default="2",
        nargs="?",
        help="文档ID（如果提供文件路径）"
    )
    parser.add_argument(
        "file_path",
        type=str,
        default=r"D:\Workspace\SWS_Review_Cloud_Backend\docs\校核文件\方案\广东科学技术职业学院珠海校区教师家园四期(报批稿).docx",
        nargs="?",
        help="Word 文档文件路径（.docx）"
    )
    parser.add_argument(
        "--version-id",
        type=int,
        help="直接处理指定版本ID（跳过上传）"
    )
    parser.add_argument(
        "--list-documents",
        action="store_true",
        help="列出所有项目和文档"
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=1,
        help="项目ID（默认: 1）"
    )
    parser.add_argument(
        "--no-auto-create",
        action="store_true",
        help="如果文档不存在，不自动创建（默认会自动创建）"
    )
    
    args = parser.parse_args()
    
    # 列出文档
    if args.list_documents:
        list_projects_and_documents()
        return
    
    # 处理指定版本
    if args.version_id:
        success = test_process_version(args.version_id)
        sys.exit(0 if success else 1)
    
    # 上传并处理
    if args.document_id and args.file_path:
        success = test_upload_and_process(
            args.document_id, 
            args.file_path,
            project_id=args.project_id,
            auto_create=not args.no_auto_create
        )
        sys.exit(0 if success else 1)
    
    # 显示帮助
    parser.print_help()
    print("\n示例用法:")
    print("  1. 上传并处理:")
    print("     python 测试文档处理.py <文档ID> <文件路径>")
    print("     例如: python 测试文档处理.py 1 D:\\test.docx")
    print()
    print("  2. 处理已存在的版本:")
    print("     python 测试文档处理.py --version-id <版本ID>")
    print("     例如: python 测试文档处理.py --version-id 5")
    print()
    print("  3. 列出所有文档:")
    print("     python 测试文档处理.py --list-documents")
    sys.exit(1)


if __name__ == "__main__":
    main()
