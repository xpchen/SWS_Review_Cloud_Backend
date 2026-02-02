-- 建独立 schema（推荐，避免 public 混乱）
CREATE SCHEMA IF NOT EXISTS sws AUTHORIZATION sws_app;

-- 让 sws_app 默认使用 sws schema
ALTER ROLE sws_app SET search_path = sws, public;

-- 下面开始建表（MVP：与你 DDS 一致）
SET search_path = sws, public;

-- 用户
create table if not exists sys_user (
  id bigserial primary key,
  username varchar(64) not null unique,
  password_hash varchar(255) not null,
  display_name varchar(128),
  status varchar(16) not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 项目
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
  project_role varchar(16) not null default 'viewer',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (project_id, user_id)
);

-- 文件对象
create table if not exists file_object (
  id bigserial primary key,
  storage varchar(16) not null,
  bucket varchar(128) not null,
  object_key varchar(512) not null,
  filename varchar(255) not null,
  content_type varchar(128),
  size bigint not null default 0,
  sha256 varchar(64),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 文档/版本
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
  status varchar(16) not null default 'UPLOADED',
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

-- 大纲/块/表格
create table if not exists doc_outline_node (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  node_no varchar(32),
  title varchar(255) not null,
  level int not null,
  parent_id bigint references doc_outline_node(id) on delete cascade,
  order_index int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists doc_table (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  outline_node_id bigint references doc_outline_node(id) on delete set null,
  table_no varchar(64),
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
  block_type varchar(16) not null,
  order_index int not null default 0,
  text text,
  table_id bigint references doc_table(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

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

-- 审查点/运行/问题/留痕
create table if not exists review_checkpoint (
  id bigserial primary key,
  code varchar(64) not null unique,
  name varchar(255) not null,
  category varchar(16) not null,
  target_outline_prefix varchar(32),
  prompt_template text,
  rule_config_json jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists review_run (
  id bigserial primary key,
  version_id bigint not null references document_version(id) on delete cascade,
  run_type varchar(16) not null,
  status varchar(16) not null default 'PENDING',
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
  severity varchar(8) not null,
  title varchar(255) not null,
  description text,
  suggestion text,
  confidence double precision not null default 0.5,
  status varchar(16) not null default 'NEW',
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
  action varchar(16) not null,
  action_reason text,
  actor_user_id bigint not null references sys_user(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
