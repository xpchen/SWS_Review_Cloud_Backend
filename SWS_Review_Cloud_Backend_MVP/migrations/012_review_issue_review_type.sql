-- 012: review_issue 增加 review_type，用于按 形式/技术 及未来按枚举统计
-- 执行前请根据实际 schema 替换 sws
ALTER TABLE sws.review_issue
ADD COLUMN IF NOT EXISTS review_type varchar(64);

COMMENT ON COLUMN sws.review_issue.review_type IS '规则类型：FORMAT/CONTENT/CONSISTENCY_*/BUSINESS_LOGIC/SUM_MISMATCH_*/MISSING_SECTION/AI_COMPLIANCE_GAP 等，用于形式审查/技术审查统计';
