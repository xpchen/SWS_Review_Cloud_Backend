-- kb_source, kb_chunk for RAG (DDS 4.6)
SET search_path = sws, public;

create table if not exists kb_source (
  id bigserial primary key,
  name varchar(255) not null,
  kb_type varchar(16) not null,
  file_id bigint not null references file_object(id),
  status varchar(16) not null default 'PROCESSING',
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists kb_chunk (
  id bigserial primary key,
  kb_source_id bigint not null references kb_source(id) on delete cascade,
  chunk_text text not null,
  meta_json jsonb,
  hash varchar(64) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (kb_source_id, hash)
);
create index if not exists idx_kb_chunk_source on kb_chunk(kb_source_id);
