-- 010: 禁用旧的重复checkpoint（如果存在新的FMT_R_*系列）
SET search_path = sws, public;

-- 如果存在新的FMT_R_*系列checkpoint，禁用旧的FORMAT_*系列checkpoint
-- 这样可以避免重复问题
UPDATE review_checkpoint
SET enabled = false
WHERE code IN ('FORMAT_STRUCTURE', 'FORMAT_NUMBERING', 'FORMAT_REFERENCE', 'FORMAT_UNIT', 'FORMAT_TABLE')
AND EXISTS (
    SELECT 1 FROM review_checkpoint 
    WHERE code LIKE 'FMT_R_%' 
    AND enabled = true
    LIMIT 1
);

-- 如果存在新的CNT_R_*系列checkpoint，禁用旧的CONTENT_*系列checkpoint
UPDATE review_checkpoint
SET enabled = false
WHERE code IN ('CONTENT_SECTIONS', 'CONTENT_TRIGGER', 'CONTENT_ELEMENTS')
AND EXISTS (
    SELECT 1 FROM review_checkpoint 
    WHERE code LIKE 'CNT_R_%' 
    AND enabled = true
    LIMIT 1
);

COMMENT ON COLUMN review_checkpoint.enabled IS '是否启用：如果存在新的FMT_R_*/CNT_R_*系列checkpoint，建议禁用旧的FORMAT_*/CONTENT_*系列以避免重复';
