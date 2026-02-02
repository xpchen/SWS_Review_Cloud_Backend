-- 009: 修复checkpoint重复问题 - 为每个checkpoint添加only_checks配置
SET search_path = sws, public;

-- 更新格式审查checkpoint，为每个添加only_checks配置
-- 注意：如果rule_config_json中已经有only_checks，则保留；否则添加
UPDATE review_checkpoint
SET rule_config_json = 
    CASE 
        WHEN rule_config_json->'only_checks' IS NOT NULL 
             AND rule_config_json->>'only_checks' != 'null' 
             AND rule_config_json->>'only_checks' != '[]' 
             AND jsonb_array_length(rule_config_json->'only_checks') > 0 THEN rule_config_json
        WHEN code = 'FORMAT_STRUCTURE' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["cover_required_elements", "toc_present"]}'::jsonb
        WHEN code = 'FORMAT_NUMBERING' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["heading_numbering", "figure_numbering", "table_numbering"]}'::jsonb
        WHEN code = 'FORMAT_REFERENCE' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["table_referenced", "figure_referenced"]}'::jsonb
        WHEN code = 'FORMAT_UNIT' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["unit_symbol_consistency", "table_unit_column_present"]}'::jsonb
        WHEN code = 'FORMAT_TABLE' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["table_caption_present", "table_numbering", "table_referenced", "table_unit_column_present"]}'::jsonb
        ELSE rule_config_json
    END
WHERE code IN ('FORMAT_STRUCTURE', 'FORMAT_NUMBERING', 'FORMAT_REFERENCE', 'FORMAT_UNIT', 'FORMAT_TABLE')
AND (rule_config_json->>'executor' = 'format_review' OR rule_config_json IS NULL OR rule_config_json = '{}'::jsonb OR rule_config_json->>'executor' IS NULL);

-- 更新内容审查checkpoint
UPDATE review_checkpoint
SET rule_config_json = 
    CASE 
        WHEN rule_config_json->'only_checks' IS NOT NULL THEN rule_config_json
        WHEN code = 'CONTENT_SECTIONS' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["required_sections"]}'::jsonb
        WHEN code = 'CONTENT_TRIGGER' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["trigger_requirements"]}'::jsonb
        WHEN code = 'CONTENT_ELEMENTS' THEN COALESCE(rule_config_json, '{}'::jsonb) || '{"only_checks": ["required_elements"]}'::jsonb
        ELSE rule_config_json
    END
WHERE code IN ('CONTENT_SECTIONS', 'CONTENT_TRIGGER', 'CONTENT_ELEMENTS')
AND (rule_config_json->>'executor' = 'content_review' OR rule_config_json IS NULL OR rule_config_json = '{}'::jsonb OR rule_config_json->>'executor' IS NULL);

-- 修复executor名称不匹配的问题（cp_前缀的checkpoint）
UPDATE review_checkpoint
SET rule_config_json = COALESCE(rule_config_json, '{}'::jsonb) || 
    CASE code
        WHEN 'CP_SUM_MISMATCH' THEN '{"executor": "sum_mismatch"}'::jsonb
        WHEN 'CP_UNIT_INCONSISTENT' THEN '{"executor": "unit_inconsistent"}'::jsonb
        WHEN 'CP_MISSING_SECTION' THEN '{"executor": "missing_section"}'::jsonb
        ELSE '{}'::jsonb
    END
WHERE code IN ('CP_SUM_MISMATCH', 'CP_UNIT_INCONSISTENT', 'CP_MISSING_SECTION')
AND (rule_config_json->>'executor' LIKE 'cp_%' OR rule_config_json->>'executor' IS NULL);

-- 为所有使用format_review但没有only_checks的checkpoint添加默认配置
-- 如果checkpoint code以FMT_R_开头，根据code推断only_checks
UPDATE review_checkpoint
SET rule_config_json = COALESCE(rule_config_json, '{}'::jsonb) ||
    CASE 
        WHEN rule_config_json->'only_checks' IS NOT NULL 
             AND rule_config_json->>'only_checks' != 'null' 
             AND rule_config_json->>'only_checks' != '[]' 
             AND jsonb_array_length(rule_config_json->'only_checks') > 0 THEN '{}'::jsonb
        WHEN code = 'FMT_R_001' THEN '{"only_checks": ["cover_required_elements"]}'::jsonb
        WHEN code = 'FMT_R_002' THEN '{"only_checks": ["toc_present"]}'::jsonb
        WHEN code = 'FMT_R_003' THEN '{"only_checks": ["heading_numbering"]}'::jsonb
        WHEN code = 'FMT_R_004' THEN '{"only_checks": ["figure_numbering"]}'::jsonb
        WHEN code = 'FMT_R_005' THEN '{"only_checks": ["table_numbering"]}'::jsonb
        WHEN code = 'FMT_R_006' THEN '{"only_checks": ["table_caption_present"]}'::jsonb
        WHEN code = 'FMT_R_007' THEN '{"only_checks": ["figure_caption_present"]}'::jsonb
        WHEN code = 'FMT_R_008' THEN '{"only_checks": ["table_referenced"]}'::jsonb
        WHEN code = 'FMT_R_009' THEN '{"only_checks": ["figure_referenced"]}'::jsonb
        WHEN code = 'FMT_R_010' THEN '{"only_checks": ["unit_symbol_consistency"]}'::jsonb
        WHEN code = 'FMT_R_011' THEN '{"only_checks": ["typography_normalization"]}'::jsonb
        WHEN code = 'FMT_R_012' THEN '{"only_checks": ["table_unit_column_present"]}'::jsonb
        ELSE '{}'::jsonb
    END
WHERE (rule_config_json->>'executor' = 'format_review' OR rule_config_json IS NULL OR rule_config_json = '{}'::jsonb OR rule_config_json->>'executor' IS NULL)
AND code LIKE 'FMT_R_%'
AND (rule_config_json->'only_checks' IS NULL 
     OR rule_config_json->>'only_checks' = 'null' 
     OR rule_config_json->>'only_checks' = '[]'
     OR jsonb_array_length(COALESCE(rule_config_json->'only_checks', '[]'::jsonb)) = 0);

-- 注意：一致性审查、表内计算、公式计算等executor通常每个checkpoint执行所有检查
-- 这些不需要only_checks，因为它们本身就是原子检查

COMMENT ON COLUMN review_checkpoint.rule_config_json IS '规则配置JSON，包含executor（执行器名称）、only_checks（只执行指定的检查列表，用于避免重复）等配置';
