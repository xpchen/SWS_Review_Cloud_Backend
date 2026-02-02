# 迁移 007: 添加版本进度跟踪字段

## 说明

此迁移为 `document_version` 表添加进度跟踪字段，用于显示文档处理进度。

## 执行迁移

```bash
# 连接到数据库
psql -U sws_app -d sws_review_cloud

# 执行迁移
\i docs/migrations/007_add_version_progress_fields.sql

# 或者直接执行
psql -U sws_app -d sws_review_cloud -f docs/migrations/007_add_version_progress_fields.sql
```

## 添加的字段

1. **progress** (integer, DEFAULT 0)
   - 处理进度百分比（0-100）
   - 用于显示文档处理进度

2. **current_step** (varchar(255))
   - 当前处理步骤描述
   - 例如："DOCX转PDF"、"解析DOCX结构"等

## 约束

- `progress` 字段有 CHECK 约束，确保值在 0-100 范围内

## 向后兼容

如果迁移执行失败或字段已存在，迁移脚本会安全地跳过（使用 `IF NOT EXISTS`）。

## 验证

执行迁移后，可以验证字段是否添加成功：

```sql
-- 查看表结构
\d sws.document_version

-- 查看字段注释
SELECT 
    column_name, 
    data_type, 
    column_default,
    (SELECT obj_description(oid) FROM pg_class WHERE relname = 'document_version')
FROM information_schema.columns 
WHERE table_schema = 'sws' 
  AND table_name = 'document_version'
  AND column_name IN ('progress', 'current_step');
```
