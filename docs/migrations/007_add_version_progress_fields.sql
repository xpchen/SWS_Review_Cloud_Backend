SET search_path = sws, public;

-- 1) 字段（这些 IF NOT EXISTS 是合法的）
ALTER TABLE document_version
  ADD COLUMN IF NOT EXISTS progress integer DEFAULT 0;

ALTER TABLE document_version
  ADD COLUMN IF NOT EXISTS current_step varchar(255);

-- 2) 默认值（你写的这句可要可不要，因为上面已 DEFAULT 0）
ALTER TABLE document_version
  ALTER COLUMN progress SET DEFAULT 0;

-- 3) 约束：Postgres 不支持 IF NOT EXISTS，需要自己判断
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE c.conname = 'chk_version_progress_range'
      AND t.relname = 'document_version'
      AND n.nspname = 'sws'
  ) THEN
    ALTER TABLE sws.document_version
      ADD CONSTRAINT chk_version_progress_range
      CHECK (progress >= 0 AND progress <= 100);
  END IF;
END $$;

-- 4) 注释
COMMENT ON COLUMN document_version.progress IS '处理进度百分比（0-100）';
COMMENT ON COLUMN document_version.current_step IS '当前处理步骤描述';
