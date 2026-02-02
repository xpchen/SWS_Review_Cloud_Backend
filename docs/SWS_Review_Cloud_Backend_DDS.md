# SWS Review Cloud 后端技术完整详细设计（DDS）

> 产品定位：面向“水土保持方案/报告”的 **AI 辅助编审云平台**（导入即审查、定位即证据）。  
> 前端：uni-app 三栏工作台（左大纲 / 中 PDF / 右校验结果）。  
> 后端：负责文档导入、PDF预览、结构化解析、规则校验、Qwen(RAG) AI校验、问题定位与留痕、导出与运维。  
> 版本：v1.0（MVP 可交付）  
> 日期：2026-01-30

---

## 1. 目标与原则

### 1.1 核心目标
1. **可用的编审工作台**：Word 导入 → 转 PDF 预览 → 目录跳转 → 问题点击定位（至少页码、最好矩形高亮）。
2. **两类校验输出统一问题清单**：
   - 规则校验：合计校验/单位一致/缺项/一致性等确定性检查；
   - AI 校验：合规性、逻辑性、表述质量、缺失内容、规范引用等语义检查（基于 Qwen + RAG）。
3. **证据链闭环**：每条问题必须含 “证据引用”（页码、块ID、原文引用片段；可选 rect 坐标）。
4. **协作与留痕**：问题状态（新建/采纳/忽略/已修复）与理由、操作者、时间戳可追溯。
5. **版本化**：同一文档多次上传形成版本，支持重跑校验、对比、导出。

### 1.2 设计原则
- **展示用 PDF，理解用结构化**：预览与跳转高效稳定；校验输入走结构化文本/表格与 RAG。
- **异步重任务**：转换、解析、向量化、AI 运行全部队列化，不阻塞接口。
- **可配置审查点**：审查点库可扩展/禁用，便于不同地区/不同机构落地。
- **安全优先**：文件访问鉴权；敏感信息脱敏；密钥不落库。

---

## 2. 总体架构

### 2.1 技术栈（推荐，适合文档+AI）
- **API**：Python 3.11 + FastAPI
- **异步任务**：Celery + Redis
- **数据库**：PostgreSQL 14+（免费开源）
- **向量扩展（可选）**：pgvector（MVP建议启用，部署简单）
- **对象存储**：MinIO（私有化）或 阿里 OSS
- **文档转换**：LibreOffice headless（docx→pdf）
- **解析**：
  - python-docx（标题层级/段落/表格）
  - PyMuPDF（PDF页码/文本块bbox/坐标）
- **LLM / Embedding**：阿里通义千问 Qwen（DashScope / Model Studio）

### 2.2 逻辑模块
1. **Auth/RBAC**：用户、项目成员权限
2. **Project/Document/Version**：项目、文档、版本与文件管理
3. **Pipeline**：转换/解析/对齐/切片/索引
4. **Rule Engine**：规则校验插件
5. **AI Review Engine**：Qwen + RAG 输出结构化问题
6. **Workspace**：问题管理（筛选、采纳/忽略、备注、留痕）
7. **Knowledge Base**：规范/模板/案例知识库（切片+向量化+检索）
8. **Export**：导出 issues.xlsx / 审查报告（后续可扩展）

---

## 3. 服务拆分与接口边界

### 3.1 API 服务（FastAPI）
职责：
- 鉴权与权限校验（项目成员）
- 上传、签名URL、元数据管理
- 触发 pipeline / review_run
- 读取 outline / issues / run 状态
- SSE 推送运行进度
- 导出（Excel/报告）

### 3.2 Worker 服务（Celery）
职责：
- docx→pdf 转换（LibreOffice）
- docx 结构化解析（outline/blocks/tables）
- PDF 布局提取（bbox）
- block↔pdf 对齐（页码/矩形）
- 规则校验执行
- AI 校验执行（Qwen + RAG）
- KB 切片与 embedding（可选）

### 3.3 存储服务（MinIO/OSS）
职责：
- 统一保存源文件与产物
- 版本化目录结构
- 提供签名URL或由 API 代理访问

---

## 4. 数据库设计（PostgreSQL DDL）

> 说明：v1.0 采用 `bigserial`；如需跨环境合并建议改 UUID。  
> 时间字段统一 `timestamptz`。  
> pgvector 可选：后面附带启用方式。

### 4.1 用户/项目/成员
```sql
create table if not exists sys_user (
  id bigserial primary key,
  username varchar(64) not null unique,
  password_hash varchar(255) not null,
  display_name varchar(128),
  status varchar(16) not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project (
  id bigserial primary key,
  name varchar(255) not null,
  location varchar(255),
  owner_user_id bigint not null references sys_user(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_member (
  project_id bigint not null references project(id) on delete cascade,
  user_id bigint not null references sys_user(id) on delete cascade,
  project_role varchar(16) not null default 'viewer', -- owner/editor/reviewer/viewer
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (project_id, user_id)
);
```

### 4.2 文件/文档/版本
```sql
create table if not exists file_object (
  id bigserial primary key,
  storage varchar(16) not null, -- minio/oss/local
  bucket varchar(128) not null,
  object_key varchar(512) not null,
  filename varchar(255) not null,
  content_type varchar(128),
  size bigint not null default 0,
  sha256 varchar(64),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document (
  id bigserial primary key,
  project_id bigint not null references project(id) on delete cascade,
  doc_type varchar(32) not null default 'SOIL_WATER_PLAN',
  title varchar(255) not null,
  current_version_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document_version (
  id bigserial primary key,
  document_id bigint not null references document(id) on delete cascade,
  version_no int not null,
  status varchar(16) not null default 'UPLOADED', -- UPLOADED/PROCESSING/READY/FAILED
  source_file_id bigint not null references file_object(id),
  pdf_file_id bigint references file_object(id),
  structure_json_file_id bigint references file_object(id),
  page_map_json_file_id bigint references file_object(id),
  text_full_file_id bigint references file_object(id),
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, version_no)
);
create index if not exists idx_version_doc on document_version(document_id);
create index if not exists idx_version_status on document_version(status);
```

### 4.3 文档结构化：大纲/块/表格
```sql
create table if not exists doc_outline_node (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  node_no varchar(32),      -- "7.1"
  title varchar(255) not null,
  level int not null,
  parent_id bigint references doc_outline_node(id) on delete cascade,
  order_index int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_outline_version on doc_outline_node(version_id);

create table if not exists doc_table (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  outline_node_id bigint references doc_outline_node(id) on delete set null,
  table_no varchar(64), -- "表7.1-2"
  title varchar(255),
  n_rows int,
  n_cols int,
  raw_json jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists doc_block (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  outline_node_id bigint references doc_outline_node(id) on delete set null,
  block_type varchar(16) not null, -- PARA/TABLE/CAPTION/OTHER
  order_index int not null default 0,
  text text,
  table_id bigint references doc_table(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_block_version on doc_block(version_id);

create table if not exists doc_table_cell (
  id bigserial primary key,
  table_id bigint not null references doc_table(id) on delete cascade,
  r int not null,
  c int not null,
  text text,
  num_value double precision,
  unit varchar(32),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (table_id, r, c)
);
```

### 4.4 定位锚点：页码与矩形（高亮）
```sql
create table if not exists block_page_anchor (
  id bigserial primary key,
  block_id bigint not null references doc_block(id) on delete cascade,
  page_no int not null, -- 1-based
  rect_pdf jsonb,       -- {x1,y1,x2,y2} PDF坐标：左下原点，point
  rect_norm jsonb,      -- {l,t,w,h} 归一化：左上原点，0~1
  confidence double precision not null default 0.0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### 4.5 审查点/运行/问题/留痕
```sql
create table if not exists review_checkpoint (
  id bigserial primary key,
  code varchar(64) not null unique,
  name varchar(255) not null,
  category varchar(16) not null, -- FORMAT/TECH/CONSISTENCY/COMPLIANCE
  target_outline_prefix varchar(32), -- "7.1"
  prompt_template text,
  rule_config_json jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists review_run (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  run_type varchar(16) not null, -- RULE/AI/MIXED
  status varchar(16) not null default 'PENDING', -- PENDING/RUNNING/DONE/FAILED/CANCELED
  progress int not null default 0,
  started_at timestamptz,
  finished_at timestamptz,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists review_issue (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  run_id bigint references review_run(id) on delete set null,
  issue_type varchar(64) not null,
  severity varchar(8) not null, -- S1/S2/S3
  title varchar(255) not null,
  description text,
  suggestion text,
  confidence double precision not null default 0.5,
  status varchar(16) not null default 'NEW', -- NEW/ACCEPTED/IGNORED/FIXED
  page_no int,
  evidence_block_ids jsonb,
  evidence_quotes jsonb,
  anchor_rects jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists issue_action_log (
  id bigserial primary key,
  issue_id bigint not null references review_issue(id) on delete cascade,
  action varchar(16) not null, -- ACCEPT/IGNORE/FIX/COMMENT
  action_reason text,
  actor_user_id bigint not null references sys_user(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### 4.6 知识库（RAG）+ pgvector（可选）
```sql
-- create extension if not exists vector;

create table if not exists kb_source (
  id bigserial primary key,
  name varchar(255) not null,
  kb_type varchar(16) not null, -- NORM/TEMPLATE/CASE/FAQ
  file_id bigint not null references file_object(id),
  status varchar(16) not null default 'PROCESSING', -- PROCESSING/READY/FAILED
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists kb_chunk (
  id bigserial primary key,
  kb_source_id bigint not null references kb_source(id) on delete cascade,
  chunk_text text not null,
  meta_json jsonb,
  -- embedding vector(1536),
  hash varchar(64) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (kb_source_id, hash)
);
```

---

## 5. 对象存储（MinIO/OSS）规范

### 5.1 Key 目录
- `projects/{project_id}/documents/{document_id}/versions/{version_id}/source.docx`
- `projects/{project_id}/documents/{document_id}/versions/{version_id}/preview.pdf`
- `projects/{project_id}/documents/{document_id}/versions/{version_id}/structure.json`
- `projects/{project_id}/documents/{document_id}/versions/{version_id}/page_map.json`
- `projects/{project_id}/documents/{document_id}/versions/{version_id}/text_full.txt`
- `kb/{kb_source_id}/source.*`
- `kb/{kb_source_id}/chunks.jsonl`

### 5.2 访问方式
- PDF：API 生成 signed url（短期）给前端 PDF.js viewer 使用。
- 其他产物：仅后端/worker 读取；前端如需调试可提供管理接口（管理员）。

---

## 6. Pipeline 详细设计（异步任务）

### 6.1 任务链（Celery chain）
1) convert_docx_to_pdf(version_id)  
2) parse_docx_structure(version_id)  
3) extract_pdf_layout(version_id)  
4) align_blocks_to_pdf(version_id)  
5) build_chunks_and_index(version_id)  
6) finalize_ready(version_id)

### 6.2 关键实现要点
- `document_version.status`：
  - 上传后立即置 `PROCESSING`
  - 成功置 `READY`
  - 异常置 `FAILED`，记录 `error_message`
- 每步产物写入 `file_object`，并回填到 version 的对应 `*_file_id`
- 每个任务要可重试（例如 2 次），并对“不可重试错误”（docx损坏）直接失败

### 6.3 docx→pdf（LibreOffice）
- 容器内安装 LibreOffice；
- 执行 headless 转换；
- 同步上传结果文件；
- 如果转换失败：记录日志（stderr）到 error_message。

### 6.4 docx 结构化解析
- 标题：根据 paragraph style（Heading 1/2/3…）构建 `doc_outline_node`
- 段落：构建 `doc_block(PARA)`，顺序号 `order_index` 单调递增
- 表格：构建 `doc_table` + `doc_table_cell`，同时生成 `doc_block(TABLE)`
- 数值：尽量解析到 `num_value`（去千分位、括号负数等），单位提取到 `unit`

### 6.5 PDF 布局提取
- PyMuPDF 按页 `page.get_text("dict")` 获取 spans（文本+bbox）
- 保存 `pdf_layout.json` 到 storage（调试与对齐用）

### 6.6 对齐与定位
- MVP：只生成 page_no（章节继承/大纲书签）
- 增强：模糊匹配 block 文本到 spans，合并 bbox 生成 rect_pdf
- 输出 `page_map.json` 并写 `block_page_anchor`（可同时存 DB）

---

## 7. 规则校验（Rule Engine）

### 7.1 Rule 接口（建议）
- 输入：version_id + checkpoint.rule_config_json
- 输出：IssueDraft 列表
- 规则自包含：不依赖前端逻辑

### 7.2 MVP 规则
1. SUM_MISMATCH（表合计）
2. UNIT_INCONSISTENT（单位混用）
3. MISSING_SECTION（必备章节缺失）
4. KEY_FIELD_INCONSISTENT（关键字段一致性）

### 7.3 规则输出规范（IssueDraft）
- issue_type / severity / title / description / suggestion / confidence
- evidence_block_ids（至少1个）
- page_no（至少1个）
- anchor_rects（可选）

---

## 8. AI 编审（Qwen + RAG）详细设计

### 8.1 执行策略
- 按 checkpoint 分批：
  - 取目标章节 blocks 拼成 context（限制长度）
  - RAG 检索 kb_chunk 作为规范上下文
  - 调 Qwen 输出 JSON issues
  - 校验后落库

### 8.2 RAG 召回流程（pgvector可选）
- query：checkpoint.name + 章节标题 + 关键词（表号/术语）
- topK=10（召回）→ 可选 rerank → topN=5
- 将 chunks 以「来源/条款号/页码/文本」结构拼入 prompt

### 8.3 强约束输出（必须 JSON）
```json
{
  "issues": [
    {
      "issue_type": "COMPLIANCE_GAP",
      "severity": "S2",
      "title": "...",
      "description": "...",
      "suggestion": "...",
      "confidence": 0.0,
      "evidence": [{"block_id": 0, "page_no": 0, "quote": "..."}],
      "norm_refs": [{"kb_chunk_id": 0, "ref": "...", "quote": "..."}]
    }
  ]
}
```

### 8.4 防幻觉
- 没 evidence → 必须输出空 issues
- norm_refs.kb_chunk_id 必须存在（后端校验）
- JSON 不合法：自动重试一次并记录“模型输出修复日志”
- 规范条款号 ref 必须来自 kb_chunk.meta_json（禁止编造）

---

## 9. API 详细设计（REST + SSE）

### 9.1 通用响应
```json
{"code":"OK","message":"success","data":{...}}
```

### 9.2 鉴权
- POST /api/auth/login
- GET /api/me

### 9.3 项目/文档/版本
- POST /api/projects
- GET /api/projects
- POST /api/projects/{project_id}/documents
- GET /api/documents/{document_id}
- GET /api/documents/{document_id}/versions

### 9.4 上传与预览
- POST /api/documents/{document_id}/versions/upload  (multipart file)
- GET  /api/versions/{version_id}/status
- GET  /api/versions/{version_id}/pdf  → {url}

### 9.5 大纲与问题
- GET /api/versions/{version_id}/outline
- GET /api/versions/{version_id}/issues?status=&severity=&type=

### 9.6 触发校验与进度
- POST /api/versions/{version_id}/review-runs
- GET  /api/review-runs/{run_id}
- GET  /api/review-runs/{run_id}/events （SSE）

### 9.7 Issue 操作
- GET  /api/issues/{issue_id}
- POST /api/issues/{issue_id}/actions

### 9.8 知识库
- POST /api/kb/sources/upload
- GET  /api/kb/sources
- POST /api/kb/sources/{id}/reindex

### 9.9 导出
- POST /api/versions/{version_id}/export?type=issues.xlsx

---

## 10. SSE 事件定义
- run_progress：{run_id, progress, message}
- issue_created：{issue_id, title, page_no, severity}
- run_done：{run_id}
- run_failed：{run_id, error}

---

## 11. PDF.js 定位协议（后端输出字段）
issue.anchor_rects：
```json
[
  {"page": 94,
   "rect_pdf": {"x1": 80.2, "y1": 420.5, "x2": 520.0, "y2": 455.0},
   "rect_norm": {"l": 0.12, "t": 0.42, "w": 0.76, "h": 0.05}}
]
```
MVP：page_no 必须；rect 后续增强。

---

## 12. 安全与审计
- signed url 过期时间 10~30 分钟
- JWT 过期与刷新策略（access短、refresh长）
- 日志脱敏（手机号/身份证）
- issue_action_log 记录操作留痕

---

## 13. 部署（Docker Compose MVP）
服务：
- api、worker、redis、postgres、minio、nginx(pdfjs)

环境变量：
- DATABASE_URL、REDIS_URL、MINIO_*、QWEN_API_KEY、JWT_SECRET

---

## 14. 验收清单（v1.0）
- docx 上传转 pdf 可预览
- 左侧大纲可用并能跳页
- 规则校验至少两类问题可定位
- AI 校验可生成结构化问题并引用规范chunk
- issue 采纳/忽略留痕
- 导出 issues.xlsx

---

## 15. Issue 返回示例
```json
{
  "id": 10086,
  "issue_type": "SUM_MISMATCH",
  "severity": "S2",
  "title": "表7.1-2 合计计算不一致",
  "description": "表7.1-2 中“合计”金额与各分项金额求和不一致，可能导致投资估算错误。",
  "suggestion": "核对分项金额单位与取整规则，重新计算合计并同步修改相关章节引用。",
  "confidence": 0.92,
  "status": "NEW",
  "page_no": 94,
  "evidence_quotes": [
    {"block_id": 345, "page_no": 94, "quote": "表7.1-2 水土保持投资估算表 … 合计 …"}
  ],
  "anchor_rects": [
    {"page": 94,
     "rect_pdf": {"x1": 80.2, "y1": 420.5, "x2": 520.0, "y2": 455.0},
     "rect_norm": {"l": 0.12, "t": 0.42, "w": 0.76, "h": 0.05}}
  ]
}
```
