"""
Pipeline steps: convert_docx_to_pdf, parse_docx_structure, extract_pdf_layout,
align_blocks_to_pdf, build_chunks_and_index (optional), finalize_ready.
"""
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
import fitz  # PyMuPDF

from .. import db
from ..settings import settings
from ..storage import get_storage
from ..services.file_service import create_file_object, get_file_object
from ..services.version_service import (
    get_version,
    update_version_status,
    set_version_pdf_file,
    set_version_structure_file,
    set_version_page_map_file,
)
from ..utils.progress import ProgressReporter, log_step

logger = logging.getLogger(__name__)

_schema = settings.DB_SCHEMA
STORAGE_TYPE = "minio" if settings.STORAGE_TYPE == "minio" else "local"
BUCKET = settings.MINIO_BUCKET if STORAGE_TYPE == "minio" else "local"


def _version_doc(version_id: int) -> tuple[dict, dict]:
    v = get_version(version_id)
    if not v:
        raise ValueError(f"Version {version_id} not found")
    # document 表只有 id 字段，没有 document_id 字段
    sql = f"SELECT project_id FROM {_schema}.document WHERE id = %(document_id)s"
    doc = db.fetch_one(sql, {"document_id": v["document_id"]})
    if not doc:
        raise ValueError("Document not found")
    return v, doc


def _key_base(project_id: int, document_id: int, version_no: int) -> str:
    return f"projects/{project_id}/documents/{document_id}/versions/{version_no}"


def _download_to_bytes(storage, object_key: str) -> bytes:
    stream = storage.get_object(object_key)
    if not stream:
        raise FileNotFoundError(f"Object not found: {object_key}")
    try:
        return stream.read()
    finally:
        if hasattr(stream, "close"):
            stream.close()


def convert_docx_to_pdf(version_id: int) -> None:
    v, doc = _version_doc(version_id)
    project_id, document_id = doc["project_id"], v["document_id"]
    version_no = v["version_no"]
    key_base = _key_base(project_id, document_id, version_no)

    fo = get_file_object(v["source_file_id"])
    if not fo:
        raise ValueError(f"Source file_object not found for version {version_id}, source_file_id={v.get('source_file_id')}")
    object_key = fo.get("object_key")
    if not object_key or object_key == "NULL" or object_key.upper() == "NULL":
        raise ValueError(f"Invalid object_key for version {version_id}")
    storage = get_storage()
    docx_bytes = _download_to_bytes(storage, object_key)
    if not docx_bytes or len(docx_bytes) == 0:
        raise ValueError(f"Downloaded file is empty for version {version_id}, object_key={object_key}")

    base_temp = os.environ.get("TMP", os.environ.get("TEMP", tempfile.gettempdir()))
    base_temp = os.path.abspath(base_temp)
    if os.path.exists(base_temp) and not os.path.isdir(base_temp):
        base_temp = os.path.dirname(base_temp) or tempfile.gettempdir()
    os.makedirs(base_temp, exist_ok=True)
    keep_temp = os.environ.get("DEBUG_KEEP_TEMP", "").strip() in ("1", "true", "yes")
    tmpdir = tempfile.mkdtemp(dir=base_temp)
    try:
        tmpdir = str(Path(tmpdir).resolve())
        docx_path = Path(tmpdir) / "source.docx"
        docx_path.write_bytes(docx_bytes)
        profile_dir = Path(tmpdir) / "lo-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_path_slash = str(profile_dir.resolve()).replace("\\", "/")
        user_installation_url = f"file:///{profile_path_slash}"

        if sys.platform == "win32":
            soffice_path = shutil.which("soffice.exe") or next(
                (p for p in [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                    os.path.expanduser(r"~\AppData\Local\Programs\LibreOffice\program\soffice.exe"),
                ] if os.path.exists(p)), None
            )
        else:
            soffice_path = shutil.which("soffice")
        if not soffice_path or not os.path.exists(soffice_path):
            raise RuntimeError("LibreOffice (soffice) not found. Install LibreOffice.")
        soffice_dir = str(Path(soffice_path).parent)

        cmd = [
            soffice_path,
            "-env:UserInstallation=" + user_installation_url,
            "--headless", "--invisible", "--nologo", "--norestore",
            "--convert-to", "pdf:writer_pdf_Export",
            "--outdir", tmpdir,
            str(docx_path),
        ]
        env = os.environ.copy()
        creationflags = 0
        if sys.platform == "win32":
            env["PATH"] = os.pathsep.join([soffice_dir, str(Path(soffice_path).parent.parent)]) + os.pathsep + env.get("PATH", "")
            env.setdefault("TMP", tempfile.gettempdir())
            env.setdefault("TEMP", env["TMP"])
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        proc = subprocess.Popen(
            cmd,
            cwd=soffice_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **({"creationflags": creationflags} if creationflags else {}),
        )
        pdf_path = Path(tmpdir) / "source.pdf"
        for _ in range(12):
            time.sleep(5)
            if pdf_path.exists():
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass
                break
        else:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            raise RuntimeError("LibreOffice conversion failed: no PDF within 60 seconds")

        pdf_bytes = pdf_path.read_bytes()
        if len(pdf_bytes) == 0:
            raise RuntimeError("Generated PDF file is empty")
    finally:
        if not keep_temp and tmpdir and os.path.isdir(tmpdir):
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    pdf_key = f"{key_base}/preview.pdf"
    storage.put(pdf_key, io.BytesIO(pdf_bytes), content_type="application/pdf", size=len(pdf_bytes))

    file_id = create_file_object(
        storage=STORAGE_TYPE, bucket=BUCKET, object_key=pdf_key,
        filename="preview.pdf", content_type="application/pdf", size=len(pdf_bytes),
    )
    set_version_pdf_file(version_id, file_id)


def _parse_number(s: str) -> tuple[float | None, str | None]:
    """Parse numeric value and unit from cell text. Returns (num_value, unit)."""
    if not s or not isinstance(s, str):
        return None, None
    s = s.strip().replace(",", "").replace("，", "")
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1].strip()
    m = re.search(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([^\d\s\-+.]+)?$", s)
    if not m:
        return None, None
    try:
        num = float(m.group(1))
        if neg:
            num = -num
        unit = (m.group(2) or "").strip() or None
        return num, unit
    except ValueError:
        return None, None


def _iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    Each returned value is either a Paragraph or Table object.
    """
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    
    # 检查是否是 Document 对象（通过检查是否有 element.body 属性）
    if hasattr(parent, 'element') and hasattr(parent.element, 'body'):
        parent_element = parent.element.body
    else:
        parent_element = parent.element
    
    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def parse_docx_structure(version_id: int) -> None:
    """
    按文档body顺序统一迭代Paragraph和Table，确保表格归属正确的章节。
    先清理该version的旧数据，然后按顺序插入。
    """
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    
    log_step(version_id, "解析DOCX结构", "开始")
    v, doc = _version_doc(version_id)
    project_id, document_id = doc["project_id"], v["document_id"]
    version_no = v["version_no"]
    key_base = _key_base(project_id, document_id, version_no)

    # 先清理该version的旧数据（支持重跑）
    log_step(version_id, "解析DOCX结构", "清理旧数据")
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            # 删除顺序：先删依赖表，再删主表
            cur.execute(f"DELETE FROM {_schema}.doc_table_cell WHERE table_id IN (SELECT id FROM {_schema}.doc_table WHERE version_id = %(v)s)", {"v": version_id})
            cur.execute(f"DELETE FROM {_schema}.doc_block WHERE version_id = %(v)s", {"v": version_id})
            cur.execute(f"DELETE FROM {_schema}.doc_table WHERE version_id = %(v)s", {"v": version_id})
            cur.execute(f"DELETE FROM {_schema}.doc_outline_node WHERE version_id = %(v)s", {"v": version_id})

    log_step(version_id, "解析DOCX结构", "加载DOCX文件")
    fo = get_file_object(v["source_file_id"])
    if not fo:
        raise ValueError(f"Source file_object not found for version {version_id}, source_file_id={v.get('source_file_id')}")
    
    object_key = fo.get("object_key")
    if not object_key or object_key == "NULL" or object_key.upper() == "NULL":
        raise ValueError(
            f"Invalid object_key for version {version_id}: "
            f"source_file_id={v.get('source_file_id')}, "
            f"file_object_id={fo.get('id')}, "
            f"object_key={object_key}"
        )
    
    storage = get_storage()
    log_step(version_id, "解析DOCX结构", f"下载文件: {object_key}")
    docx_bytes = _download_to_bytes(storage, object_key)
    
    if not docx_bytes or len(docx_bytes) == 0:
        raise ValueError(f"Downloaded file is empty for version {version_id}, object_key={object_key}")
    
    log_step(version_id, "解析DOCX结构", f"文件大小: {len(docx_bytes)} 字节")
    
    # 验证是否为有效的 DOCX 文件（DOCX 是 ZIP 格式，以 PK 开头）
    if len(docx_bytes) < 4 or docx_bytes[:2] != b'PK':
        raise ValueError(
            f"Invalid DOCX file format for version {version_id}. "
            f"File does not appear to be a valid DOCX/ZIP archive. "
            f"File size: {len(docx_bytes)} bytes, "
            f"First bytes: {docx_bytes[:10] if len(docx_bytes) >= 10 else docx_bytes}"
        )
    
    try:
        docx_doc = DocxDocument(io.BytesIO(docx_bytes))
    except Exception as e:
        raise ValueError(
            f"Failed to parse DOCX file for version {version_id}, "
            f"object_key={object_key}, "
            f"file_size={len(docx_bytes)} bytes. "
            f"Error: {e}"
        ) from e
    log_step(version_id, "解析DOCX结构", "开始解析文档结构")

    outline_order = 0
    block_order = 0
    parent_stack = []  # (level, node_id)
    current_outline_id = None
    level_counters = {}  # {level: count} 分级计数器
    last_para_block_id = None  # 记录上一个段落block_id，用于表题抽取
    outline_to_heading_block = {}  # {outline_node_id: heading_block_id} 映射，用于P0-6
    last_title_info = None  # (title, level, parent_id) 用于去重
    inserted_titles_sequence = []  # 记录已插入的标题序列（用于检测重复大纲）
    in_toc_section = False  # 是否在目录页区域

    # 统计总项目数（用于进度显示）
    items = list(_iter_block_items(docx_doc))
    total_items = len(items)
    log_step(version_id, "解析DOCX结构", f"共 {total_items} 个项目需要处理")
    
    # 创建进度报告器
    progress = ProgressReporter(total_items, "解析DOCX结构", version_id)
    
    # 按body顺序统一迭代Paragraph和Table
    for idx, item in enumerate(items):
        # 每50个项目或到达末尾时更新一次进度
        if (idx + 1) % 50 == 0 or (idx + 1) == total_items:
            if (idx + 1) % 50 == 0:
                progress.update(50, f"已处理 {idx + 1}/{total_items} 个项目")
            else:
                # 处理最后一个批次
                remaining = (idx + 1) - ((idx + 1) // 50) * 50
                if remaining > 0:
                    progress.update(remaining, f"已处理 {idx + 1}/{total_items} 个项目")
        if isinstance(item, Paragraph):
            para = item
            para_text = (para.text or "").strip()
            
            # 检测是否进入目录页区域（通过"目录"字样）
            if para_text and ("目录" in para_text or "目 录" in para_text.replace(" ", "")):
                in_toc_section = True
                logger.info(f"[版本 {version_id}] 检测到目录页区域")
            
            level = _get_heading_level(para)
            if level is not None:
                # 标题：创建outline_node，同时创建HEADING block
                title = para_text
                if not title:
                    continue
                
                # 检测目录页模式：标题后面跟着页码（如"1 综合说明 1"）
                # 匹配模式：标题 + 空格/制表符 + 数字页码（末尾）
                toc_pattern = re.match(r"^(.+?)\s+(\d+)\s*$", title)
                if toc_pattern:
                    title_without_page = toc_pattern.group(1).strip()
                    page_num = toc_pattern.group(2)
                    # 如果标题去掉页码后仍然匹配标题模式，则可能是目录页
                    if _get_heading_level_from_text(title_without_page) is not None:
                        logger.info(f"[版本 {version_id}] 检测到目录页标题（带页码）: {title} -> {title_without_page}")
                        title = title_without_page
                        in_toc_section = True
                
                # 截断 title 到255个字符（数据库字段限制）
                title = title[:255] if title else None
                node_no = _make_node_no(level, parent_stack, level_counters)
                # 截断 node_no 到32个字符（数据库字段限制）
                node_no = node_no[:32] if node_no else None
                while parent_stack and parent_stack[-1][0] >= level:
                    parent_stack.pop()
                parent_id = parent_stack[-1][1] if parent_stack else None
                
                # 去重策略1：如果当前标题与上一个标题完全相同（相同层级、相同父节点），则跳过
                if last_title_info and last_title_info == (title, level, parent_id):
                    logger.warning(f"[版本 {version_id}] 跳过连续重复标题: {title} (level={level}, parent_id={parent_id})")
                    continue
                
                # 去重策略2：目录页内重复标题一律跳过
                if in_toc_section and title in inserted_titles_sequence:
                    logger.warning(f"[版本 {version_id}] 跳过目录页中的重复标题: {title}")
                    continue
                
                # 去重策略3：检测整段重复大纲（如正文前段 2~8 后，再出现 1,2,3...8 整段重复）
                # 若已插入的标题较多，且当前标题已在前 15 个中出现过，视为重复段并跳过
                if len(inserted_titles_sequence) >= 5 and title in inserted_titles_sequence[:15]:
                    logger.warning(f"[版本 {version_id}] 跳过重复大纲段落中的标题: {title}")
                    continue
                sql = f"""
                INSERT INTO {_schema}.doc_outline_node (version_id, node_no, title, level, parent_id, order_index)
                VALUES (%(version_id)s, %(node_no)s, %(title)s, %(level)s, %(parent_id)s, %(order_index)s)
                RETURNING id
                """
                with db.pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, {
                            "version_id": version_id, "node_no": node_no, "title": title,
                            "level": level, "parent_id": parent_id, "order_index": outline_order,
                        })
                        nid = cur.fetchone()[0]
                parent_stack.append((level, nid))
                current_outline_id = nid
                outline_order += 1
                
                # 更新最后标题信息（用于去重）
                last_title_info = (title, level, parent_id)
                
                # 记录已插入的标题序列（保留最近20个，用于检测重复大纲）
                inserted_titles_sequence.append(title)
                if len(inserted_titles_sequence) > 20:
                    inserted_titles_sequence.pop(0)
                
                # 如果插入的是level=1的标题，且不在目录页区域，则标记离开目录页
                if level == 1 and in_toc_section and not re.search(r"\d+\s*$", para_text):
                    # 检查是否是真正的正文标题（不包含页码）
                    in_toc_section = False
                    logger.info(f"[版本 {version_id}] 离开目录页区域，进入正文: {title}")
                
                # 同时插入HEADING block（便于证据引用/检索）
                sql = f"""
                INSERT INTO {_schema}.doc_block (version_id, outline_node_id, block_type, order_index, text)
                VALUES (%(version_id)s, %(outline_node_id)s, 'HEADING', %(order_index)s, %(text)s)
                RETURNING id
                """
                with db.pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, {
                            "version_id": version_id, "outline_node_id": current_outline_id,
                            "order_index": block_order, "text": title[:10000],
                        })
                        heading_block_id = cur.fetchone()[0]
                        # 建立映射：outline_node_id -> heading_block_id（用于P0-6）
                        outline_to_heading_block[current_outline_id] = heading_block_id
                        last_para_block_id = heading_block_id
                block_order += 1
            else:
                # 普通段落
                text = (para.text or "").strip()
                if text:  # 跳过空段落
                    sql = f"""
                    INSERT INTO {_schema}.doc_block (version_id, outline_node_id, block_type, order_index, text)
                    VALUES (%(version_id)s, %(outline_node_id)s, 'PARA', %(order_index)s, %(text)s)
                    RETURNING id
                    """
                    with db.pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql, {
                                "version_id": version_id, "outline_node_id": current_outline_id,
                                "order_index": block_order, "text": text[:10000],
                            })
                            last_para_block_id = cur.fetchone()[0]
                    block_order += 1
        elif isinstance(item, Table):
            # 表格：在当前章节下插入
            table = item
            rows = table.rows
            cols = max(len(r.cells) for r in rows) if rows else 0
            table_no = _infer_table_no(table)
            
            # 抽取表题：检查上一个段落是否是表题（常见模式：表3-1 xxx）
            table_title = None
            if last_para_block_id:
                # 获取上一个段落文本
                last_para = db.fetch_one(
                    f"SELECT text FROM {_schema}.doc_block WHERE id = %(bid)s",
                    {"bid": last_para_block_id}
                )
                if last_para and last_para.get("text"):
                    para_text = last_para["text"].strip()
                    # 检查是否匹配表题模式：表X-X xxx 或 表X-X：xxx
                    table_title_match = re.match(r"^表\s*[\d.\-]+\s*[：:：]?\s*(.+)$", para_text)
                    if table_title_match:
                        table_title = table_title_match.group(1).strip()
                        # 截断 table_title 到255个字符（数据库字段限制）
                        table_title = table_title[:255] if table_title else None
                        # 如果表号还没提取到，从表题中提取
                        if not table_no:
                            table_no_match = re.search(r"表\s*[\d.\-]+", para_text)
                            if table_no_match:
                                table_no = table_no_match.group(0).strip()
            
            sql = f"""
            INSERT INTO {_schema}.doc_table (version_id, outline_node_id, table_no, title, n_rows, n_cols)
            VALUES (%(version_id)s, %(outline_node_id)s, %(table_no)s, %(title)s, %(n_rows)s, %(n_cols)s)
            RETURNING id
            """
            with db.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "version_id": version_id, "outline_node_id": current_outline_id,
                        "table_no": table_no, "title": table_title, "n_rows": len(rows), "n_cols": cols,
                    })
                    tid = cur.fetchone()[0]
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row.cells):
                    text = (cell.text or "").strip()
                    num_val, unit = _parse_number(text)
                    # 截断 unit 到32个字符（数据库字段限制）
                    unit = unit[:32] if unit else None
                    sql = f"""
                    INSERT INTO {_schema}.doc_table_cell (table_id, r, c, text, num_value, unit)
                    VALUES (%(table_id)s, %(r)s, %(c)s, %(text)s, %(num_value)s, %(unit)s)
                    """
                    db.execute(sql, {
                        "table_id": tid, "r": ri, "c": ci, "text": text[:2000] if text else None,
                        "num_value": num_val, "unit": unit,
                    })
            # 插入TABLE block，顺序号与正文一致
            sql = f"""
            INSERT INTO {_schema}.doc_block (version_id, outline_node_id, block_type, order_index, table_id)
            VALUES (%(version_id)s, %(outline_node_id)s, 'TABLE', %(order_index)s, %(table_id)s)
            """
            db.execute(sql, {
                "version_id": version_id, "outline_node_id": current_outline_id,
                "order_index": block_order, "table_id": tid,
            })
            block_order += 1
    
    # 更新最终进度
    progress.finish(f"完成，共解析 {outline_order} 个标题节点，{block_order} 个块")
    
    log_step(version_id, "解析DOCX结构", "生成结构JSON文件")
    structure = {
        "outline": db.fetch_all(
            f"SELECT id, node_no, title, level, parent_id, order_index FROM {_schema}.doc_outline_node WHERE version_id = %(v)s ORDER BY order_index",
            {"v": version_id},
        ),
        "blocks": db.fetch_all(
            f"SELECT id, outline_node_id, block_type, order_index, text, table_id FROM {_schema}.doc_block WHERE version_id = %(v)s ORDER BY order_index",
            {"v": version_id},
        ),
        "tables": db.fetch_all(
            f"SELECT id, outline_node_id, table_no, title, n_rows, n_cols FROM {_schema}.doc_table WHERE version_id = %(v)s",
            {"v": version_id},
        ),
    }
    buf = io.BytesIO(
        json.dumps(structure, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    )
    data = buf.getvalue()
    storage = get_storage()
    struct_key = f"{key_base}/structure.json"
    storage.put(struct_key, io.BytesIO(data), content_type="application/json", size=len(data))
    file_id = create_file_object(STORAGE_TYPE, BUCKET, struct_key, "structure.json", "application/json", len(data))
    set_version_structure_file(version_id, file_id)
    log_step(version_id, "解析DOCX结构", "✅ 完成")


def _get_heading_level(para: Paragraph) -> int | None:
    """从段落样式或文本前缀识别标题层级"""
    try:
        if para.style:
            style_name = para.style.name
            level = _heading_level_from_style(style_name)
            if level is not None:
                return level
    except Exception:
        pass

    text = (para.text or "").strip()
    return _get_heading_level_from_text(text)


def _get_heading_level_from_text(text: str) -> int | None:
    """从文本内容识别标题层级（不依赖段落样式）"""
    if not text:
        return None

    # 附表/附件/附图 及其子项（附表1、附件1 等）
    level = _heading_level_from_appendix_prefix(text)
    if level is not None:
        return level

    # 数字编号：1, 1.1, 1.2.3 等（允许无空格）
    level = _heading_level_from_text_prefix(text)
    if level is not None:
        return level

    return None


def _heading_level_from_style(style_name: str) -> int | None:
    """从样式名称识别标题层级"""
    if not style_name:
        return None
    
    # 支持 "Heading 1", "Heading1", "标题 1", "标题1", "标题 1", "标题1"
    patterns = [
        (r"^Heading\s*(\d+)$", 1),  # Heading 1, Heading1
        (r"^标题\s*(\d+)$", 1),     # 标题 1, 标题1
        (r"^标题\s*(\d+)$", 1),     # 标题 1（全角空格）
    ]
    
    for pattern, group_idx in patterns:
        match = re.match(pattern, style_name, re.IGNORECASE)
        if match:
            try:
                return int(match.group(group_idx))
            except (ValueError, IndexError):
                pass
    
    return None


def _heading_level_from_text_prefix(text: str) -> int | None:
    """
    从文本前缀编号识别标题层级。
    例如："1.2.3 项目概况" -> level=3；"1.1项目简况"（无空格）-> level=2
    
    排除日期格式：
    - "2023年11月9日" -> 不是标题
    - "2023-11-09" -> 不是标题
    - "2023/11/09" -> 不是标题
    """
    # 匹配编号前缀：1, 1.2, 1.2.3 等，允许编号后无空格或有多余空格
    match = re.match(r"^(\d+(?:\.\d+)*)\s*", text)
    if match:
        prefix = match.group(1)
        
        # 排除日期格式：
        # 1. 4位数字开头（年份）且后面跟着"年"字
        if len(prefix) == 4 and prefix.isdigit():
            rest = text[len(prefix):].strip()
            if rest.startswith("年"):
                return None
        
        # 2. 排除数字过大的情况（通常章节编号不会超过100）
        # 检查第一个数字段是否过大
        first_num = prefix.split(".")[0]
        try:
            if int(first_num) > 100:
                return None
        except ValueError:
            pass
        
        # 至少要有编号，且后面紧跟非数字（避免把纯数字段落当标题）
        rest = text[len(prefix) :].strip()
        if not rest or re.match(r"[\u4e00-\u9fa5a-zA-Z]", rest):
            level = prefix.count(".") + 1
            if 1 <= level <= 6:
                return level
    return None


def _heading_level_from_appendix_prefix(text: str) -> int | None:
    """
    识别「附表」「附件」「附图」及其子项（附表1、附件2 等）为标题。
    - 附表 / 附件 / 附图 -> level=1
    - 附表1 单价分析表 / 附件2 备案证 -> level=2
    """
    m = re.match(r"^(附表|附件|附图)\s*(\d*)\s*", text)
    if not m:
        return None
    kind, num = m.group(1), (m.group(2) or "").strip()
    if not num:
        return 1
    return 2


def _make_node_no(level: int, parent_stack: list, level_counters: dict[int, int]) -> str:
    """
    分级计数器算法：每遇到某level标题就递增该层计数，并清零更深层计数。
    
    Args:
        level: 当前标题层级（1,2,3...）
        parent_stack: 父级节点栈 [(level, node_id), ...]
        level_counters: 每层计数器 {level: count}
    
    Returns:
        节点编号字符串，如 "1", "1.2", "1.2.3"
    """
    # 递增当前层计数器
    level_counters[level] = level_counters.get(level, 0) + 1
    
    # 清零更深层计数器
    for l in list(level_counters.keys()):
        if l > level:
            del level_counters[l]
    
    # 构建编号
    if level == 1:
        return str(level_counters[1])
    
    # 从父级栈获取父级编号
    parts = []
    for parent_level, _ in parent_stack:
        if parent_level < level:
            parts.append(str(level_counters[parent_level]))
    
    # 添加当前层编号
    parts.append(str(level_counters[level]))
    
    return ".".join(parts)


def _infer_table_no(table) -> str | None:
    try:
        if table.rows:
            first_cell = table.rows[0].cells[0].text or ""
            m = re.search(r"表\s*[\d.\-]+", first_cell)
            if m:
                return m.group(0).strip()
    except Exception:
        pass
    return None


def _convert_bytes_to_str(obj):
    """
    递归地将字典/列表中的 bytes 对象转换为 base64 编码的字符串
    """
    import base64
    
    if isinstance(obj, bytes):
        # 将 bytes 转换为 base64 编码的字符串
        return base64.b64encode(obj).decode('utf-8')
    elif isinstance(obj, dict):
        return {key: _convert_bytes_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_bytes_to_str(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_bytes_to_str(item) for item in obj)
    else:
        return obj


def extract_pdf_layout(version_id: int) -> None:
    log_step(version_id, "提取PDF布局", "开始")
    v, doc = _version_doc(version_id)
    fo = get_file_object(v.get("pdf_file_id"))
    if not fo:
        raise ValueError("PDF file not found; run convert_docx_to_pdf first")
    storage = get_storage()
    log_step(version_id, "提取PDF布局", "加载PDF文件")
    pdf_bytes = _download_to_bytes(storage, fo["object_key"])
    doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    num_pages = len(doc_pdf)
    log_step(version_id, "提取PDF布局", f"PDF共 {num_pages} 页，开始提取布局")
    
    layout = []
    progress = ProgressReporter(num_pages, "提取PDF布局", version_id)
    for page_idx, page in enumerate(doc_pdf):
        page_dict = page.get_text("dict")
        # 转换 bytes 对象为可序列化的字符串
        page_dict_clean = _convert_bytes_to_str(page_dict)
        layout.append(page_dict_clean)
        # 每10页或到达末尾时更新进度
        if (page_idx + 1) % 10 == 0 or (page_idx + 1) == num_pages:
            if (page_idx + 1) % 10 == 0:
                progress.update(10, f"已处理 {page_idx + 1}/{num_pages} 页")
            else:
                # 处理最后一个批次
                remaining = (page_idx + 1) - ((page_idx + 1) // 10) * 10
                if remaining > 0:
                    progress.update(remaining, f"已处理 {page_idx + 1}/{num_pages} 页")
    
    doc_pdf.close()
    log_step(version_id, "提取PDF布局", "保存布局JSON文件")
    data = json.dumps(layout, ensure_ascii=False).encode("utf-8")
    key_base = _key_base(doc["project_id"], v["document_id"], v["version_no"])
    storage.put(f"{key_base}/pdf_layout.json", io.BytesIO(data), content_type="application/json", size=len(data))
    log_step(version_id, "提取PDF布局", "✅ 完成")


def _norm_text(s: str) -> str:
    """
    归一化文本：去除空白、全角空格、不可见字符
    用于粗筛匹配
    """
    if not s:
        return ""
    # 去全角空格 + 去常见不可见字符
    s = s.replace("\u3000", " ").replace("\ufeff", "")
    # 多个空白 -> 单个空格
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _snip_candidates(text: str) -> list[str]:
    """
    生成多个候选搜索片段（长->短），用于定位/回退
    返回去重后的候选列表，按长度从长到短排序
    """
    t = _norm_text(text)
    if len(t) < 8:
        return []
    
    # 长->短，用于定位/回退
    cands = []
    for n in (40, 30, 20):
        if len(t) >= n:
            cands.append(t[:n])
    
    if not cands:
        cands = [t]
    
    # 去重（保持顺序）
    seen = set()
    result = []
    for x in cands:
        if x not in seen:
            seen.add(x)
            result.append(x)
    
    return result


def _extract_search_snippet(block: dict, table_data: dict | None = None) -> str:
    """
    从block提取单个搜索片段（用于粗筛）
    返回归一化后的文本
    """
    block_type = block.get("block_type")
    text = block.get("text") or ""
    
    if block_type == "TABLE" and table_data:
        # 表格：使用表号/表题
        table_no = table_data.get("table_no") or ""
        table_title = table_data.get("title") or ""
        if table_no and table_title:
            return _norm_text(f"{table_no} {table_title}")
        elif table_no:
            return _norm_text(table_no)
        elif table_title:
            return _norm_text(table_title)
    
    # PARA/HEADING：使用文本
    return _norm_text(text)


def _extract_search_snippets(block: dict, table_data: dict | None = None) -> list[str]:
    """
    从block提取多个候选搜索片段（保留空白，归一化为单空格）。
    返回多个候选，按优先级排序。
    
    对于表格，使用表号/表题。
    对于段落，提取前20/30/50字符的多个候选。
    """
    block_type = block.get("block_type")
    text = block.get("text") or ""
    snippets = []
    
    def normalize_whitespace(s: str) -> str:
        """归一化空白：多个空白/换行/制表符 -> 单个空格"""
        return re.sub(r"[\s\n\r\t]+", " ", s).strip()
    
    if block_type == "TABLE" and table_data:
        # 表格：使用表号/表题
        table_no = table_data.get("table_no") or ""
        table_title = table_data.get("title") or ""
        if table_no:
            snippets.append(normalize_whitespace(table_no))
        if table_title:
            snippets.append(normalize_whitespace(table_title))
        if table_no and table_title:
            snippets.append(normalize_whitespace(f"{table_no} {table_title}"))
    
    # PARA/HEADING：提取多个长度的候选
    if text:
        normalized = normalize_whitespace(text)
        # 移除标点但保留空白（提高匹配率）
        # 提取多个候选：前20/30/50字符
        for length in [20, 30, 50]:
            if len(normalized) >= length:
                snippet = normalized[:length]
                # 移除末尾不完整的词（如果以空格结尾则保留）
                if snippet and not snippet.endswith(" "):
                    # 找到最后一个空格
                    last_space = snippet.rfind(" ")
                    if last_space > 10:  # 至少保留10个字符
                        snippet = snippet[:last_space + 1]
                snippets.append(snippet)
        
        # 如果文本较短，直接使用
        if len(normalized) < 20 and normalized:
            snippets.append(normalized)
    
    # 去重并返回
    seen = set()
    result = []
    for s in snippets:
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    
    return result


def align_blocks_to_pdf(version_id: int) -> None:
    """
    优化的block→PDF页码/矩形定位。
    使用滑窗游标、粗筛候选页、批量写入等优化策略。
    """
    import time
    start_time = time.time()
    
    log_step(version_id, "对齐块到PDF", "开始")
    v, doc = _version_doc(version_id)
    key_base = _key_base(doc["project_id"], v["document_id"], v["version_no"])
    
    # 获取所有blocks（包含table_id用于表格）
    log_step(version_id, "对齐块到PDF", "加载文档块")
    blocks = db.fetch_all(
        f"""
        SELECT b.id, b.outline_node_id, b.order_index, b.block_type, b.text, b.table_id
        FROM {_schema}.doc_block b
        WHERE b.version_id = %(v)s
        ORDER BY b.order_index
        """,
        {"v": version_id}
    )
    total_blocks = len(blocks)
    log_step(version_id, "对齐块到PDF", f"共 {total_blocks} 个块需要对齐")
    
    # 获取所有表格信息（用于表格block的snippet提取）
    tables_map = {}
    if blocks:
        table_ids = [b["table_id"] for b in blocks if b.get("table_id")]
        if table_ids:
            log_step(version_id, "对齐块到PDF", f"加载 {len(table_ids)} 个表格信息")
            tables = db.fetch_all(
                f"SELECT id, table_no, title FROM {_schema}.doc_table WHERE id = ANY(%(ids)s)",
                {"ids": table_ids}
            )
            tables_map = {t["id"]: t for t in tables}
    
    # 清理旧的anchor数据
    if blocks:
        log_step(version_id, "对齐块到PDF", "清理旧的锚点数据")
        block_ids = [b["id"] for b in blocks]
        db.execute(
            f"DELETE FROM {_schema}.block_page_anchor WHERE block_id = ANY(%(ids)s)",
            {"ids": block_ids}
        )
    
    # 加载PDF
    log_step(version_id, "对齐块到PDF", "加载PDF文件")
    try:
        fo = get_file_object(v["pdf_file_id"])
        if not fo:
            raise ValueError("PDF not ready")
        storage = get_storage()
        pdf_bytes = _download_to_bytes(storage, fo["object_key"])
        doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        num_pages = len(doc_pdf)
        log_step(version_id, "对齐块到PDF", f"PDF共 {num_pages} 页")
    except Exception as e:
        # PDF不可用时，生成空的page_map
        log_step(version_id, "对齐块到PDF", f"⚠️ PDF不可用: {e}")
        doc_pdf = None
        num_pages = 0
    
    page_map_blocks = []
    anchors_rows = []  # 批量写入用
    
    # 性能统计
    search_for_calls = 0
    candidate_pages_total = 0
    hit_count = 0
    
    # 创建进度报告器
    progress = ProgressReporter(total_blocks, "对齐块到PDF", version_id)
    
    if doc_pdf and blocks:
        log_step(version_id, "对齐块到PDF", "预提取每页文本（用于粗筛）")
        
        # 1) 预提取每页文本（一次性）
        page_text_norm = []
        for i in range(num_pages):
            page = doc_pdf[i]
            page_text_norm.append(_norm_text(page.get_text("text")))
        
        log_step(version_id, "对齐块到PDF", "开始搜索块在PDF中的位置（优化版）")
        
        # 2) 滑窗 + 粗筛 + 精定位
        last_page = 1
        last_y_by_page = {}  # 同页递进定位
        
        # 窗口阶梯（找不到就扩大）
        windows = [3, 8, 20, num_pages]
        
        for block_idx, block in enumerate(blocks):
            block_id = block["id"]
            table_data = tables_map.get(block["table_id"]) if block.get("table_id") else None
            
            # 提取单个snippet用于粗筛
            snippet = _extract_search_snippet(block, table_data)
            # 生成多个候选片段（长->短）
            cands = _snip_candidates(snippet) if snippet else []
            
            if not cands:
                page_map_blocks.append({"block_id": block_id, "page_no": None})
                continue
            
            found_page = None
            found_rect = None
            confidence = 0.0
            used_cand = None
            
            # 先在 last_page 附近滑窗粗筛候选页（用最短cand，出现概率更高）
            probe = cands[-1] if cands else ""  # 最短的那个
            candidate_pages = []
            
            # 滑窗搜索：从 last_page 附近开始，逐步扩大窗口
            for w in windows:
                start = max(1, last_page - 1)
                end = min(num_pages, start + w - 1)
                candidate_pages = [
                    p for p in range(start, end + 1)
                    if probe in page_text_norm[p - 1]
                ]
                if candidate_pages:
                    break
            
            # 还没有候选页：再全局粗扫一次（仍然比 search_for 快）
            if not candidate_pages:
                candidate_pages = [
                    p for p in range(1, num_pages + 1)
                    if probe in page_text_norm[p - 1]
                ]
            
            candidate_pages_total += len(candidate_pages)
            
            # 对候选页做精定位：用长cand优先 search_for 拿 rect
            for p in candidate_pages:
                page = doc_pdf[p - 1]
                prev_y = last_y_by_page.get(p, -1)
                
                rects = None
                used = None
                for cand in cands:  # 长->短
                    try:
                        search_for_calls += 1
                        rects = page.search_for(cand, flags=fitz.TEXT_DEHYPHENATE)
                    except Exception:
                        rects = None
                    if rects:
                        used = cand
                        break
                
                if not rects:
                    continue
                
                # 同页递进：优先选 y>=prev_y 的第一个
                rects = sorted(rects, key=lambda r: (r.y0, r.x0))
                pick = None
                if prev_y >= 0:
                    for r in rects:
                        if r.y0 >= prev_y - 2:  # 容忍2pt
                            pick = r
                            break
                if pick is None:
                    pick = rects[0]
                
                found_page = p
                found_rect = pick
                used_cand = used
                last_page = p
                last_y_by_page[p] = pick.y0
                
                # 简单置信度：使用的cand越长越高
                confidence = min(1.0, len(used) / 40.0) if used else 0.5
                hit_count += 1
                break
            
            if found_page:
                page = doc_pdf[found_page - 1]
                page_rect = page.rect
                rect_norm = {
                    "x0": found_rect.x0 / page_rect.width,
                    "y0": found_rect.y0 / page_rect.height,
                    "x1": found_rect.x1 / page_rect.width,
                    "y1": found_rect.y1 / page_rect.height,
                }
                anchors_rows.append({
                    "block_id": block_id,
                    "page_no": found_page,
                    "rect_pdf": json.dumps({
                        "x0": found_rect.x0, "y0": found_rect.y0,
                        "x1": found_rect.x1, "y1": found_rect.y1,
                    }),
                    "rect_norm": json.dumps(rect_norm),
                    "confidence": confidence,
                })
                page_map_blocks.append({"block_id": block_id, "page_no": found_page})
            else:
                page_map_blocks.append({"block_id": block_id, "page_no": None})
            
            # 每处理50个块或到达末尾时更新进度
            if (block_idx + 1) % 50 == 0 or (block_idx + 1) == total_blocks:
                if (block_idx + 1) % 50 == 0:
                    progress.update(50, f"已对齐 {block_idx + 1}/{total_blocks} 个块，找到 {hit_count} 个锚点")
                else:
                    remaining = (block_idx + 1) - ((block_idx + 1) // 50) * 50
                    if remaining > 0:
                        progress.update(remaining, f"已对齐 {block_idx + 1}/{total_blocks} 个块，找到 {hit_count} 个锚点")
        
        if doc_pdf:
            doc_pdf.close()
        
        # 3) 批量写入 anchors
        if anchors_rows:
            log_step(version_id, "对齐块到PDF", f"批量写入 {len(anchors_rows)} 个锚点")
            sql = f"""
            INSERT INTO {_schema}.block_page_anchor (block_id, page_no, rect_pdf, rect_norm, confidence)
            VALUES (%(block_id)s, %(page_no)s, %(rect_pdf)s::jsonb, %(rect_norm)s::jsonb, %(confidence)s)
            """
            db.executemany(sql, anchors_rows)
            log_step(version_id, "对齐块到PDF", "✅ 批量写入完成")
    
    # 性能统计日志
    elapsed_time = time.time() - start_time
    avg_candidate_pages = candidate_pages_total / total_blocks if total_blocks > 0 else 0
    hit_rate = (hit_count / total_blocks * 100) if total_blocks > 0 else 0
    
    logger.info(f"[版本 {version_id}] 对齐性能统计:")
    logger.info(f"  总块数: {total_blocks}")
    logger.info(f"  PDF页数: {num_pages}")
    logger.info(f"  平均候选页数: {avg_candidate_pages:.2f}")
    logger.info(f"  search_for调用次数: {search_for_calls}")
    logger.info(f"  命中数: {hit_count}")
    logger.info(f"  命中率: {hit_rate:.2f}%")
    logger.info(f"  耗时: {elapsed_time:.2f}秒")
    
    # 输出到控制台
    print(f"[版本 {version_id}] 对齐性能统计:", file=sys.stderr, flush=True)
    print(f"  总块数: {total_blocks}, PDF页数: {num_pages}", file=sys.stderr, flush=True)
    print(f"  平均候选页数: {avg_candidate_pages:.2f}, search_for调用: {search_for_calls}", file=sys.stderr, flush=True)
    print(f"  命中数: {hit_count}, 命中率: {hit_rate:.2f}%, 耗时: {elapsed_time:.2f}秒", file=sys.stderr, flush=True)
    
    progress.finish(f"完成，共对齐 {hit_count}/{total_blocks} 个块")
    log_step(version_id, "对齐块到PDF", "生成page_map.json文件")
    # 生成page_map.json（向后兼容）
    page_map = {
        "blocks": page_map_blocks,
        "outline_pages": [],  # 可以后续补充
    }
    data = json.dumps(page_map, ensure_ascii=False).encode("utf-8")
    storage = get_storage()
    storage.put(f"{key_base}/page_map.json", io.BytesIO(data), content_type="application/json", size=len(data))
    file_id = create_file_object(STORAGE_TYPE, BUCKET, f"{key_base}/page_map.json", "page_map.json", "application/json", len(data))
    set_version_page_map_file(version_id, file_id)
    log_step(version_id, "对齐块到PDF", "✅ 完成")


def extract_facts(version_id: int) -> int:
    """
    抽取事实到FactStore（doc_fact表）。
    必须在parse_docx_structure和align_blocks_to_pdf之后执行。
    """
    log_step(version_id, "抽取事实", "开始")
    from ..services.fact_service import extract_facts as extract_facts_service
    count = extract_facts_service(version_id)
    log_step(version_id, "抽取事实", f"✅ 完成，共抽取 {count} 条事实")
    return count


def build_chunks_and_index(version_id: int) -> None:
    """Optional: chunk text for RAG. Stub for MVP."""
    log_step(version_id, "构建块和索引", "跳过（MVP暂未实现）")
    pass


def finalize_ready(version_id: int) -> None:
    log_step(version_id, "完成处理", "设置版本状态为READY")
    update_version_status(version_id, "READY", error_message=None, progress=100, current_step="已完成")
    log_step(version_id, "完成处理", "✅ 版本处理完成")
    
    # 仅触发 AI 规则校验（不执行旧规则引擎 RULE/checkpoint）。若日志仍出现 CONSISTENCY_BASIC/sum_mismatch 等，请重启 Celery Worker。
    if settings.AUTO_TRIGGER_REVIEW:
        try:
            from ..services.review_run_service import create_review_run
            from ..worker.ai_review_tasks import run_ai_review_task
            from ..utils.celery_diagnostics import can_use_celery

            log_step(version_id, "完成处理", "自动触发 AI 规则校验")
            run_id = create_review_run(version_id, "AI")
            logger.info(f"[版本 {version_id}] 已创建审查运行，运行ID: {run_id}")

            if can_use_celery():
                run_ai_review_task.delay(version_id, run_id)
                logger.info(f"[版本 {version_id}] AI 规则校验任务已提交到 Celery")
            else:
                logger.warning(f"[版本 {version_id}] Celery Worker 不可用，使用直接执行模式")
                from ..worker.ai_review_tasks import _execute_ai_review
                _execute_ai_review(version_id, run_id)
                logger.info(f"[版本 {version_id}] AI 规则校验任务已完成（直接执行）")

            log_step(version_id, "完成处理", "✅ 已自动触发 AI 规则校验")
        except Exception as e:
            logger.error(f"[版本 {version_id}] 自动触发 AI 规则校验失败: {e}", exc_info=True)
            log_step(version_id, "完成处理", f"⚠️ 自动触发 AI 规则校验失败: {e}")
    else:
        logger.info(f"[版本 {version_id}] 自动触发审查已禁用（AUTO_TRIGGER_REVIEW=False）")
        log_step(version_id, "完成处理", "自动触发审查已禁用")