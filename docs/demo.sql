SET search_path = sws, public;

-- 1) 确保 admin 用户存在（密码：Admin@123）
WITH ins AS (
  INSERT INTO sys_user (username, password_hash, display_name)
  VALUES (
    'admin',
    '$2b$12$1NtXDspVFwUGKW7ayAasP.JaDPONFowz3Gpoj9Xn6u0aoVZt16Lai',
    '管理员'
  )
  ON CONFLICT (username) DO UPDATE
    SET display_name = EXCLUDED.display_name
  RETURNING id
),
u AS (
  SELECT id FROM ins
  UNION ALL
  SELECT id FROM sys_user WHERE username='admin' AND NOT EXISTS (SELECT 1 FROM ins)
),

-- 2) 创建 Demo 项目
p AS (
  INSERT INTO project(name, location, owner_user_id)
  SELECT 'SWS Demo 项目', '珠海', id FROM u
  RETURNING id, owner_user_id
),

-- 3) 创建 Demo 文档
d AS (
  INSERT INTO document(project_id, doc_type, title)
  SELECT id, 'SOIL_WATER_PLAN', '广东科学技术职业学院珠海校区教师家园四期（水土保持方案）' FROM p
  RETURNING id AS document_id
),

-- 4) 占位 file_object（source docx + preview pdf）
fo_docx AS (
  INSERT INTO file_object(storage,bucket,object_key,filename,content_type,size,sha256)
  VALUES ('local','local','demo/source.docx','source.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',0,null)
  RETURNING id AS source_file_id
),
fo_pdf AS (
  INSERT INTO file_object(storage,bucket,object_key,filename,content_type,size,sha256)
  VALUES ('local','local','demo/preview.pdf','preview.pdf','application/pdf',0,null)
  RETURNING id AS pdf_file_id
),

-- 5) 创建版本（READY）
v AS (
  INSERT INTO document_version(document_id, version_no, status, source_file_id, pdf_file_id)
  SELECT d.document_id, 1, 'READY', fo_docx.source_file_id, fo_pdf.pdf_file_id
  FROM d, fo_docx, fo_pdf
  RETURNING id AS version_id
),

-- 6) 大纲：1 综合说明；1.1 项目简况；7.1 投资估算
n1 AS (
  INSERT INTO doc_outline_node(version_id, node_no, title, level, parent_id, order_index)
  SELECT version_id, '1', '综合说明', 1, NULL, 10 FROM v
  RETURNING id, version_id
),
n11 AS (
  INSERT INTO doc_outline_node(version_id, node_no, title, level, parent_id, order_index)
  SELECT version_id, '1.1', '项目简况', 2, n1.id, 20 FROM n1
  RETURNING id, version_id
),
n71 AS (
  INSERT INTO doc_outline_node(version_id, node_no, title, level, parent_id, order_index)
  SELECT version_id, '7.1', '水土保持投资估算', 2, NULL, 710 FROM v
  RETURNING id, version_id
),

-- 7) 表7.1-2 + 一个 TABLE block
t AS (
  INSERT INTO doc_table(version_id, outline_node_id, table_no, title, n_rows, n_cols, raw_json)
  SELECT n71.version_id, n71.id, '表7.1-2', '水土保持工程总投资估算表', 6, 3,
  jsonb_build_object(
    'unit', '万元',
    'rows', jsonb_build_array(
      jsonb_build_array('项目','金额(万元)','备注'),
      jsonb_build_array('第一部分 工程措施','0.26','-'),
      jsonb_build_array('第二部分 植物措施','79.80','其中植物措施费0.09；植物措施投资0.62（不符）'),
      jsonb_build_array('第三部分 临时措施','0.45','-'),
      jsonb_build_array('小计（分项求和）','80.51','-'),
      jsonb_build_array('表内合计','79.97','-')
    )
  )
  FROM n71
  RETURNING id AS table_id, version_id, outline_node_id
),
b AS (
  INSERT INTO doc_block(version_id, outline_node_id, block_type, order_index, text, table_id)
  SELECT t.version_id, t.outline_node_id, 'TABLE', 1000,
  '表7.1-2 水土保持工程总投资估算表：分项求和=80.51万元，但表内合计=79.97万元；且“植物措施费0.09”与“植物措施投资0.62”不符。',
  t.table_id
  FROM t
  RETURNING id AS block_id, version_id
),

-- 8) 锚点（页码+rect，先给前端做跳页/高亮）
a AS (
  INSERT INTO block_page_anchor(block_id, page_no, rect_pdf, rect_norm, confidence)
  SELECT b.block_id, 94,
    jsonb_build_object('x1',80.2,'y1',420.5,'x2',520.0,'y2',455.0),
    jsonb_build_object('l',0.12,'t',0.42,'w',0.76,'h',0.05),
    0.80
  FROM b
  RETURNING id
),

-- 9) 审查点（checkpoint）——规则闭环至少要有几条可用
cp AS (
  INSERT INTO review_checkpoint(code,name,category,target_outline_prefix,enabled,rule_config_json)
  VALUES
  ('CP_SUM_MISMATCH', '表内合计计算一致性', 'CONSISTENCY', NULL, true, '{"tolerance":0.01}'::jsonb),
  ('CP_UNIT_INCONSISTENT', '单位一致性检查（元/万元等）', 'CONSISTENCY', NULL, true, '{}'::jsonb),
  ('CP_MISSING_SECTION', '必备章节缺失检查', 'TECH', NULL, true, '{"required_prefix":["1","2","7"]}'::jsonb)
  ON CONFLICT (code) DO NOTHING
  RETURNING id
),

-- 10) review_run + review_issue（模拟一次规则运行结果）
r AS (
  INSERT INTO review_run(version_id, run_type, status, progress, started_at, finished_at)
  SELECT v.version_id, 'RULE', 'DONE', 100, now(), now() FROM v
  RETURNING id AS run_id, version_id
)
INSERT INTO review_issue(
  version_id, run_id, issue_type, severity, title, description, suggestion,
  confidence, status, page_no, evidence_block_ids, evidence_quotes, anchor_rects
)
SELECT
  r.version_id,
  r.run_id,
  'SUM_MISMATCH',
  'S2',
  '表7.1-2 合计计算不一致',
  '表7.1-2 中分项求和为 80.51 万元，但表内合计为 79.97 万元；且“植物措施费0.09万元”与“植物措施投资0.62万元”不一致。',
  '核对各分项金额单位与取整/四舍五入规则，重新计算合计并同步修改正文引用；确认“植物措施费/投资”字段含义与口径一致。',
  0.92,
  'NEW',
  94,
  jsonb_build_array(b.block_id),
  jsonb_build_array(jsonb_build_object('block_id',b.block_id,'page_no',94,'quote', '表7.1-2…分项求和=80.51万元…合计=79.97万元…')),
  jsonb_build_array(jsonb_build_object(
    'page',94,
    'rect_pdf', jsonb_build_object('x1',80.2,'y1',420.5,'x2',520.0,'y2',455.0),
    'rect_norm', jsonb_build_object('l',0.12,'t',0.42,'w',0.76,'h',0.05)
  ))
FROM r, b;