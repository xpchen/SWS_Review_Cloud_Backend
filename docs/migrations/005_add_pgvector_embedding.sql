-- 005: 添加pgvector支持（embedding列）
SET search_path = sws, public;

-- 确保pgvector扩展已安装
CREATE EXTENSION IF NOT EXISTS vector;

-- 为kb_chunk添加embedding列
ALTER TABLE kb_chunk
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- 创建向量索引（用于相似度搜索）
CREATE INDEX IF NOT EXISTS idx_kb_chunk_embedding 
ON kb_chunk 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

COMMENT ON COLUMN kb_chunk.embedding IS '文本embedding向量（1024维），用于语义搜索';
