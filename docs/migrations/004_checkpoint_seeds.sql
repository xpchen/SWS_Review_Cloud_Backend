-- 004: review_checkpoint种子数据（7类审查规则配置）
SET search_path = sws, public;

-- 清理旧数据（可选，用于重置）
-- DELETE FROM review_checkpoint;

-- 1. 格式审查（Format Review）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json)
VALUES 
('FORMAT_STRUCTURE', '格式审查-结构完整性', 'FORMAT', NULL, true, 10, '{"executor": "format_review", "required_elements": ["项目名称", "建设单位", "编制单位", "版本日期"]}'),
('FORMAT_NUMBERING', '格式审查-编号规范', 'FORMAT', NULL, true, 11, '{"executor": "format_review"}'),
('FORMAT_REFERENCE', '格式审查-引用规范', 'FORMAT', NULL, true, 12, '{"executor": "format_review"}'),
('FORMAT_UNIT', '格式审查-单位符号规范', 'FORMAT', NULL, true, 13, '{"executor": "format_review"}'),
('FORMAT_TABLE', '格式审查-表格格式', 'FORMAT', NULL, true, 14, '{"executor": "format_review"}')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json;

-- 2. 内容审查（Content Review）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json)
VALUES 
('CONTENT_SECTIONS', '内容审查-章节完备性', 'CONTENT', NULL, true, 20, '{"executor": "content_review", "required_sections": {"综合说明": ["综合说明", "概述"], "项目概况": ["项目概况"], "水土流失预测": ["水土流失预测"], "防治措施": ["防治措施"], "投资": ["投资"]}}'),
('CONTENT_TRIGGER', '内容审查-条件触发内容', 'CONTENT', NULL, true, 21, '{"executor": "content_review"}'),
('CONTENT_ELEMENTS', '内容审查-要素齐备', 'CONTENT', NULL, true, 22, '{"executor": "content_review"}')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json;

-- 3. 一致性审查（Consistency Review）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json)
VALUES 
('CONSISTENCY_BASIC', '一致性审查-基础元信息', 'CONSISTENCY', NULL, true, 30, '{"executor": "consistency_review", "tolerance": 0.01}'),
('CONSISTENCY_SCALE', '一致性审查-规模数量', 'CONSISTENCY', NULL, true, 31, '{"executor": "consistency_review", "tolerance": 0.01}'),
('CONSISTENCY_EARTHWORK', '一致性审查-土石方', 'CONSISTENCY', NULL, true, 32, '{"executor": "consistency_review", "tolerance": 0.01}')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json;

-- 4. 表内计算审查（In-table Calculation）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json)
VALUES 
('CALC_TABLE_SUM', '表内计算-合计检查', 'CALCULATION', NULL, true, 40, '{"executor": "sum_mismatch", "tolerance": 0.01, "rounding": 2}'),
('CALC_TABLE_PERCENT', '表内计算-占比检查', 'CALCULATION', NULL, true, 41, '{"executor": "sum_mismatch", "tolerance": 0.01}')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json;

-- 5. 业务逻辑审查（Business Logic Review）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json)
VALUES 
('LOGIC_TRIGGER', '业务逻辑-触发必备论证', 'LOGIC', NULL, true, 50, '{"executor": "business_logic_review"}'),
('LOGIC_PROHIBITION', '业务逻辑-禁止性条款', 'LOGIC', NULL, true, 51, '{"executor": "business_logic_review"}')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json;

-- 6. 公式计算审查（Formula Calculation）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json, prompt_template)
VALUES 
('FORMULA_SIX_INDICATORS', '公式计算-六项指标', 'CALCULATION', NULL, true, 42, '{"executor": "formula_calculation", "formula_type": "six_indicators", "tolerance": 0.01}', NULL),
('FORMULA_BALANCE', '公式计算-平衡公式', 'CALCULATION', NULL, true, 43, '{"executor": "formula_calculation", "formula_type": "balance", "tolerance": 0.01}', NULL),
('FORMULA_PREDICTION', '公式计算-预测计算', 'CALCULATION', NULL, true, 44, '{"executor": "formula_calculation", "formula_type": "prediction", "tolerance": 0.01}', NULL)

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json,
    prompt_template = EXCLUDED.prompt_template;

-- 7. AI审查（AI Review）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json, prompt_template)
VALUES 
('AI_COMPLIANCE', 'AI审查-合规性审查', 'AI', NULL, true, 70, '{"executor": "ai_review", "max_context_length": 8000, "top_k": 5, "kb_keywords": "水土保持 规范 标准"}', NULL),
('AI_ARGUMENT_QUALITY', 'AI审查-论证质量', 'AI', '4', true, 71, '{"executor": "ai_review", "max_context_length": 6000, "top_k": 3, "kb_keywords": "论证 依据 合理性"}', '请审查该章节的论证是否充分，是否缺少关键依据或结论。'),
('AI_MEASURES_COMPLETENESS', 'AI审查-措施完整性', 'AI', '5', true, 72, '{"executor": "ai_review", "max_context_length": 6000, "top_k": 3, "kb_keywords": "防治措施 工程措施 植物措施"}', '请审查该章节的防治措施是否完整，是否缺少必要的工程措施或植物措施。')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json,
    prompt_template = EXCLUDED.prompt_template;

-- 8. 旧规则（向后兼容）
INSERT INTO review_checkpoint (code, name, category, target_outline_prefix, enabled, order_index, rule_config_json, prompt_template)
VALUES 
('UNIT_INCONSISTENT', '单位混用检查', 'LEGACY', NULL, true, 60, '{"executor": "unit_inconsistent"}', NULL),
('MISSING_SECTION', '缺章节检查', 'LEGACY', NULL, true, 61, '{"executor": "missing_section"}', NULL),
('KEY_FIELD_INCONSISTENT', '关键字段不一致', 'LEGACY', NULL, true, 62, '{"executor": "key_field_inconsistent"}', NULL)

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    enabled = EXCLUDED.enabled,
    order_index = EXCLUDED.order_index,
    rule_config_json = EXCLUDED.rule_config_json,
    prompt_template = EXCLUDED.prompt_template;
