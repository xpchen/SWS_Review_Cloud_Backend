-- 011: 修复CP_*系列checkpoint的executor字段（只更新rule_config_json）
SET search_path = sws, public;

-- 修复CP_SUM_MISMATCH: 在rule_config_json中设置executor
UPDATE review_checkpoint
SET rule_config_json = COALESCE(rule_config_json, '{}'::jsonb) || '{"executor": "sum_mismatch"}'::jsonb
WHERE code = 'CP_SUM_MISMATCH'
AND (rule_config_json->>'executor' IS NULL OR rule_config_json->>'executor' = '');

-- 修复CP_UNIT_INCONSISTENT: 在rule_config_json中设置executor
UPDATE review_checkpoint
SET rule_config_json = COALESCE(rule_config_json, '{}'::jsonb) || '{"executor": "unit_inconsistent"}'::jsonb
WHERE code = 'CP_UNIT_INCONSISTENT'
AND (rule_config_json->>'executor' IS NULL OR rule_config_json->>'executor' = '');

-- 修复CP_MISSING_SECTION: 在rule_config_json中设置executor
UPDATE review_checkpoint
SET rule_config_json = COALESCE(rule_config_json, '{}'::jsonb) || '{"executor": "missing_section"}'::jsonb
WHERE code = 'CP_MISSING_SECTION'
AND (rule_config_json->>'executor' IS NULL OR rule_config_json->>'executor' = '');

-- 注意：rule_config_json 必须包含 executor 字段（执行器名称）
