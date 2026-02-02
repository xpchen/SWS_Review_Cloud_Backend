-- block_page_anchor for PDF block-to-page alignment (DDS 4.4)
SET search_path = sws, public;

create table if not exists block_page_anchor (
  id bigserial primary key,
  block_id bigint not null references doc_block(id) on delete cascade,
  page_no int not null,
  rect_pdf jsonb,
  rect_norm jsonb,
  confidence double precision not null default 0.0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_block_anchor_block on block_page_anchor(block_id);
