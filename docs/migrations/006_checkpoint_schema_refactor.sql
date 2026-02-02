-- 006: Checkpoint引擎重构 - 添加engine_type和review_category字段
SET search_path = sws, public;

-- 1. 添加engine_type字段（RULE/AI/SQL）
ALTER TABLE review_checkpoint ADD COLUMN IF NOT EXISTS engine_type varchar(16);
-- 添加review_category字段（FORMAT/CONTENT/CONSISTENCY/TABLE_CALC/FORMULA/BUSINESS/OTHER）
ALTER TABLE review_checkpoint ADD COLUMN IF NOT EXISTS review_category varchar(32);

-- 2. 从现有category字段推断engine_type和review_category
-- category='AI' -> engine_type='AI', review_category从rule_config_json.review_category获取或保持原category
-- 其他 -> engine_type='RULE', review_category=category
UPDATE review_checkpoint
SET 
    engine_type = CASE 
        WHEN category = 'AI' THEN 'AI'
        ELSE 'RULE'
    END,
    review_category = CASE
        WHEN category = 'AI' THEN COALESCE(
            (rule_config_json->>'review_category')::varchar,
            category
        )
        ELSE category
    END
WHERE engine_type IS NULL OR review_category IS NULL;

-- 3. 设置默认值和约束
ALTER TABLE review_checkpoint ALTER COLUMN engine_type SET DEFAULT 'RULE';
ALTER TABLE review_checkpoint ALTER COLUMN review_category SET DEFAULT 'OTHER';

-- 4. 创建索引
CREATE INDEX IF NOT EXISTS idx_review_checkpoint_engine_type ON review_checkpoint(engine_type, enabled);
CREATE INDEX IF NOT EXISTS idx_review_checkpoint_category ON review_checkpoint(review_category);

-- 5. 添加注释
COMMENT ON COLUMN review_checkpoint.engine_type IS '执行引擎类型：RULE（规则引擎）/ AI（AI审查）/ SQL（SQL校验）';
COMMENT ON COLUMN review_checkpoint.review_category IS '审查类别：FORMAT（格式）/ CONTENT（内容）/ CONSISTENCY（一致性）/ TABLE_CALC（表内计算）/ FORMULA（公式计算）/ BUSINESS（业务逻辑）/ OTHER（其它）';

-- 6. 确保review_issue.checkpoint_code字段存在（如果不存在则添加）
ALTER TABLE review_issue ADD COLUMN IF NOT EXISTS checkpoint_code varchar(64);
CREATE INDEX IF NOT EXISTS idx_review_issue_checkpoint ON review_issue(checkpoint_code);

COMMENT ON COLUMN review_issue.checkpoint_code IS '审查点代码：关联review_checkpoint.code，用于统计和回归';
