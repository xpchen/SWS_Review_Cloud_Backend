# 扫描版PDF的OCR工作流（推荐）

本知识库包中有部分PDF被识别为 **IMAGE_ONLY**（扫描件/图片文本），`pdftotext`/PyMuPDF无法直接提取文字，因此这些源目前不会产生chunk。

## 推荐方案：ocrmypdf（最省事）

1) 安装（任选其一）
- Ubuntu/Debian：`sudo apt-get install ocrmypdf tesseract-ocr tesseract-ocr-chi-sim`
- pip：`pip install ocrmypdf`

2) 对每个扫描PDF做OCR，生成可选中文文本的PDF：

```bash
ocrmypdf -l chi_sim --skip-text --deskew --rotate-pages \
  "input.pdf" "output_ocr.pdf"
```

3) 用 `pdftotext` 提取OCR后的文本：

```bash
pdftotext -layout -enc UTF-8 "output_ocr.pdf" "output.txt"
```

4) 把 `output_ocr.pdf`（或原PDF替换为 OCR 版）放回 `/mnt/data` 后，重新运行：

```bash
python tools/build_kb_package_v2.py
```

> 说明：`build_kb_package_v2.py` 当前读取 `/mnt/data` 下固定的10个PDF路径。你可以把 OCR 版覆盖原文件名（最省事），或修改脚本中的路径列表。

## 可选方案：PaddleOCR（更强，但需额外环境）
- 适合版式复杂、表格多、OCR要求更高的PDF。
- 可把OCR结果输出为txt，再用脚本分块入库。
