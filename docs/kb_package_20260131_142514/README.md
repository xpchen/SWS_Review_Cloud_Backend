# 规范知识库包（自动生成）

生成时间：20260131_142514

- kb_sources.json：知识库源文件清单（含sha256/页数/块数）
- kb_chunks.jsonl：分块后的规范文本（每行一个chunk，含meta_json：页码范围、标题路径等）


## 扫描件提示
以下PDF为扫描件（IMAGE_ONLY），需要先OCR后才能形成chunk：
- 《生产建设项目水土保持技术标准》（GB 50433-2018）.pdf
- 《水利工程设计概（估）算编制规定（水土保持工程）》.pdf
- 2017最新版：《土地利用现状分类》（GBT 21010-2017） (1).pdf
- 关于印发《生产建设项目水土保持方案技术审查要点》的通知（水保监〔2020〕63号）.pdf
- 生产建设项目水土保持方案管理办法（2023年1月17日水利部令第53号发布）.pdf
- 生产建设项目水土保持技术文件编写和印制格式规定（办水保【2018】135号） (最新）.pdf
- 生产建设项目水土流失防治标准（GB50433-2018）.pdf

见：tools/ocr_workflow.md

## IMAGE_ONLY 的处理
本包中若某些 source 的 `extract_method = IMAGE_ONLY`，说明PDF为扫描件/图片文本，当前无法直接抽取正文生成chunk。

- 你可以按 `tools/ocr_workflow.md` 用 **ocrmypdf** 先把PDF转成“可复制文本”的OCR版；
- 然后重新运行 `tools/build_kb_package_v2.py` 生成新的kb包并导入。
