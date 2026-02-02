-- 003: 添加doc_fact表（FactStore）和review_issue.checkpoint_code字段
SET search_path = sws, public;

-- 1. 添加review_issue.checkpoint_code字段（用于绑定审查点）
ALTER TABLE review_issue ADD COLUMN IF NOT EXISTS checkpoint_code varchar(64);
CREATE INDEX IF NOT EXISTS idx_review_issue_checkpoint ON review_issue(checkpoint_code);

-- 2. 创建doc_fact表（事实抽取存储）
CREATE TABLE IF NOT EXISTS doc_fact (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  fact_key varchar(128) not null,  -- 事实键：如"占地面积"、"投资总额"、"工期"等
  value_num double precision,  -- 数值型事实值
  value_text text,  -- 文本型事实值
  unit varchar(32),  -- 单位
  scope varchar(64),  -- 作用域：如"项目整体"、"某章节"、"某表格"
  source_block_id bigint references doc_block(id) on delete set null,  -- 来源block
  source_table_id bigint references doc_table(id) on delete set null,  -- 来源表格（可选）
  confidence double precision not null default 0.5,  -- 置信度
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (version_id, fact_key, scope)  -- 同一版本同一作用域同一键只能有一条
);
CREATE INDEX IF NOT EXISTS idx_doc_fact_version ON doc_fact(version_id);
CREATE INDEX IF NOT EXISTS idx_doc_fact_key ON doc_fact(fact_key);
CREATE INDEX IF NOT EXISTS idx_doc_fact_block ON doc_fact(source_block_id);

-- 3. 为review_checkpoint添加order_index字段（用于控制执行顺序）
ALTER TABLE review_checkpoint ADD COLUMN IF NOT EXISTS order_index int;
CREATE INDEX IF NOT EXISTS idx_review_checkpoint_order ON review_checkpoint(enabled, order_index NULLS LAST);

COMMENT ON TABLE doc_fact IS '文档事实抽取表：存储从文档中提取的结构化事实（面积、投资、工期等），用于一致性审查和公式计算';
COMMENT ON COLUMN doc_fact.fact_key IS '事实键：如"占地面积"、"投资总额"、"工期"、"是否弃渣"等';
COMMENT ON COLUMN doc_fact.scope IS '作用域：如"项目整体"、"1.2章节"、"表3-1"等';
COMMENT ON COLUMN review_issue.checkpoint_code IS '审查点代码：关联review_checkpoint.code，用于统计和回归';
