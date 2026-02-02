import os
import re
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

PDF_PATHS = [
    "/mnt/data/《生产建设项目水土保持技术标准》（GB 50433-2018）.pdf",
    "/mnt/data/《水利工程设计概（估）算编制规定（水土保持工程）》.pdf",
    "/mnt/data/2017最新版：《土地利用现状分类》（GBT 21010-2017） (1).pdf",
    "/mnt/data/GB 51018-2014 水土保持工程设计规范 (2).pdf",
    "/mnt/data/关于印发《生产建设项目水土保持方案技术审查要点》的通知（水保监〔2020〕63号）.pdf",
    "/mnt/data/广东省水利水电工程设计估算编制规定.pdf",
    "/mnt/data/广东省水土保持条例.pdf",
    "/mnt/data/生产建设项目水土保持方案管理办法（2023年1月17日水利部令第53号发布）.pdf",
    "/mnt/data/生产建设项目水土保持技术文件编写和印制格式规定（办水保【2018】135号） (最新）.pdf",
    "/mnt/data/生产建设项目水土流失防治标准（GB50433-2018）.pdf",
]

HEADING_RES = [
    re.compile(r"^(第[一二三四五六七八九十百千0-9]+[章节])\s*.*$"),
    re.compile(r"^(第[一二三四五六七八九十百千0-9]+条)\s*.*$"),
    re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\s+[\u4e00-\u9fff].{0,60}$"),
    re.compile(r"^(附录|附表|附件)\s*[\u4e00-\u9fffA-Za-z0-9（）()]{0,40}$"),
]


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_pdf_page_count(p: str) -> int:
    try:
        out = subprocess.check_output(["pdfinfo", p], stderr=subprocess.STDOUT)
        s = out.decode("utf-8", "ignore")
        m = re.search(r"^Pages:\s+(\d+)\s*$", s, flags=re.MULTILINE)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def pdftotext_pages(p: str) -> List[str]:
    try:
        out = subprocess.check_output(["pdftotext", "-layout", "-enc", "UTF-8", p, "-"], stderr=subprocess.STDOUT)
        text = out.decode("utf-8", "ignore")
        pages = text.split("\f")
        return pages
    except Exception:
        return []


def filter_line(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{1,4}", s):
        return None
    if re.fullmatch(r"第\s*\d+\s*页", s):
        return None
    if re.fullmatch(r"[-—–]{3,}", s):
        return None
    return s


def is_heading_line(line: str) -> bool:
    s = (line or "").strip()
    if not s or len(s) > 80:
        return False
    if re.fullmatch(r"[0-9IVXivx\-—–_ ]{1,10}", s):
        return False
    for r in HEADING_RES:
        if r.match(s):
            return True
    return False


def chunk_text_with_overlap(text: str, target_len: int = 1200, overlap: int = 150) -> List[str]:
    chunks: List[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + target_len, n)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("。"), window.rfind("；"), window.rfind("\n"))
            if cut != -1 and cut > target_len * 0.6:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def extract_blocks(pages: List[str]) -> List[Dict]:
    blocks: List[Dict] = []
    current_heading = ""
    heading_path: List[str] = []
    lines_acc: List[str] = []
    pages_acc: set[int] = set()

    def flush():
        nonlocal lines_acc, pages_acc
        if not lines_acc:
            return
        text = "\n".join(lines_acc).strip()
        if text:
            blocks.append({
                "heading": current_heading,
                "heading_path": heading_path.copy(),
                "page_start": min(pages_acc) if pages_acc else None,
                "page_end": max(pages_acc) if pages_acc else None,
                "text": text,
            })
        lines_acc = []
        pages_acc = set()

    for idx, page_text in enumerate(pages):
        page_no = idx + 1
        for raw_line in (page_text or "").splitlines():
            line = filter_line(raw_line)
            if line is None:
                continue
            if is_heading_line(line):
                flush()
                current_heading = line
                m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\s+", line)
                if m:
                    lvl = m.group(1).count(".") + 1
                    heading_path[:] = heading_path[: max(lvl - 1, 0)]
                    heading_path.append(line)
                else:
                    if re.match(r"^(第.*章)", line):
                        heading_path[:] = [line]
                    elif re.match(r"^(第.*条)", line):
                        if heading_path and re.match(r"^第.*章", heading_path[0]):
                            heading_path[:] = [heading_path[0], line]
                        else:
                            heading_path[:] = [line]
                    else:
                        heading_path[:] = [line]
                continue
            lines_acc.append(line)
            pages_acc.add(page_no)

    flush()
    return blocks


def build(out_base: str = "/mnt/data") -> str:
    ts = "20260131_" + subprocess.check_output(["date", "+%H%M%S"]).decode().strip()
    out_dir = Path(out_base) / f"kb_package_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources: List[Dict] = []
    chunks_out = out_dir / "kb_chunks.jsonl"

    total_chunks = 0
    src_block_counts: Dict[int, int] = {}

    with chunks_out.open("w", encoding="utf-8") as fw:
        for sid, abs_path in enumerate(PDF_PATHS, start=1):
            if not os.path.exists(abs_path):
                continue
            filename = Path(abs_path).name
            doc_title = filename[:-4] if filename.lower().endswith(".pdf") else filename
            meta = {
                "source_local_id": sid,
                "name": doc_title,
                "kb_type": "NORM",
                "filename": filename,
                "abs_path": abs_path,
                "sha256": sha256_file(abs_path),
                "size": os.path.getsize(abs_path),
                "pages": get_pdf_page_count(abs_path),
                "block_count": 0,
            }
            sources.append(meta)

            pages = pdftotext_pages(abs_path)
            blocks = extract_blocks(pages)
            src_block_counts[sid] = len(blocks)

            chunk_index = 0
            for b in blocks:
                for chunk_text in chunk_text_with_overlap(b["text"], 1200, 150):
                    h = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    chunk_meta = {
                        "chunk_index": chunk_index,
                        "page_start": b.get("page_start"),
                        "page_end": b.get("page_end"),
                        "heading": b.get("heading"),
                        "heading_path": b.get("heading_path"),
                        "doc": filename,
                    }
                    fw.write(json.dumps({
                        "kb_source_local_id": sid,
                        "hash": h,
                        "chunk_text": chunk_text,
                        "meta_json": chunk_meta,
                    }, ensure_ascii=False) + "\n")
                    chunk_index += 1

            total_chunks += chunk_index

    for s in sources:
        s["block_count"] = src_block_counts.get(s["source_local_id"], 0)

    (out_dir / "kb_sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps({
        "generated_at": ts,
        "source_count": len(sources),
        "chunk_count": total_chunks,
        "chunk_target_chars": 1200,
        "chunk_overlap_chars": 150,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = f"""# 规范知识库包（自动生成）\n\n生成时间：{ts}\n\n- kb_sources.json：知识库源文件清单（含sha256/页数/块数）\n- kb_chunks.jsonl：分块后的规范文本（每行一个chunk，含meta_json：页码范围、标题路径等）\n"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"[OK] out_dir={out_dir}")
    print(f"[OK] sources={len(sources)} chunks={total_chunks}")
    return str(out_dir)


if __name__ == "__main__":
    build()
