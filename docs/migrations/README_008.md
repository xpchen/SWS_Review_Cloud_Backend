# 迁移 008: 增加字符串字段长度

## 说明

此迁移增加某些字符串字段的长度，以支持更长的值。

## 执行迁移

```bash
# 连接到数据库
psql -U sws_app -d sws_review_cloud

# 执行迁移
\i docs/migrations/008_increase_string_field_lengths.sql

# 或者直接执行
psql -U sws_app -d sws_review_cloud -f docs/migrations/008_increase_string_field_lengths.sql
```

## 修改的字段

1. **doc_outline_node.node_no** (varchar(32) → varchar(64))
   - 原因：某些文档的标题编号可能很长（如 `1.2.3.4.5.6.7.8`）
   - 影响：支持更深的文档层级

2. **doc_table_cell.unit** (varchar(32) → varchar(64))
   - 原因：某些单位可能较长（如 `平方米/公顷`、`元/平方米` 等）
   - 影响：支持更复杂的单位表示

## 向后兼容

此迁移是向后兼容的，只是增加了字段长度，不会影响现有数据。

## 验证

执行迁移后，可以验证字段长度：

```sql
-- 查看字段定义
SELECT 
    column_name, 
    data_type, 
    character_maximum_length
FROM information_schema.columns 
WHERE table_schema = 'sws' 
  AND table_name IN ('doc_outline_node', 'doc_table_cell')
  AND column_name IN ('node_no', 'unit');
```

预期结果：
- `doc_outline_node.node_no`: `varchar(64)`
- `doc_table_cell.unit`: `varchar(64)`
