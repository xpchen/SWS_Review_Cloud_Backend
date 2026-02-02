# 修复重复问题和Unknown Executor警告

## 问题分析

根据导出的checkpoint数据，发现了以下问题：

### 1. Unknown Executor警告

以下checkpoint的`executor`字段为`null`，导致出现"Unknown executor"警告：
- `CP_SUM_MISMATCH` (id: 1)
- `CP_UNIT_INCONSISTENT` (id: 2)  
- `CP_MISSING_SECTION` (id: 3)

**原因**: 迁移009只更新了`rule_config_json`中的`executor`字段，但没有同步更新表顶层的`executor`字段。虽然代码会从`rule_config_json`读取executor，但为了数据一致性，两个字段都应该正确设置。

### 2. 重复问题

虽然迁移010已经禁用了旧的`FORMAT_*`和`CONTENT_*`系列checkpoint，但如果你在迁移010执行之前运行了审查，可能会看到重复问题。

**已禁用的checkpoint**（迁移010已处理）:
- `FORMAT_STRUCTURE` ✅ 已禁用
- `FORMAT_REFERENCE` ✅ 已禁用
- `FORMAT_TABLE` ✅ 已禁用
- `CONTENT_SECTIONS` ✅ 已禁用
- `CONTENT_TRIGGER` ✅ 已禁用
- `CONTENT_ELEMENTS` ✅ 已禁用

## 解决方案

### 步骤1: 执行迁移011修复executor字段

运行以下命令修复`CP_*`系列checkpoint的executor字段：

```bash
执行迁移011.bat
```

或者直接运行Python脚本：

```bash
python 执行迁移011.py
```

这个迁移会：
1. 为`CP_SUM_MISMATCH`设置`executor = 'sum_mismatch'`
2. 为`CP_UNIT_INCONSISTENT`设置`executor = 'unit_inconsistent'`
3. 为`CP_MISSING_SECTION`设置`executor = 'missing_section'`
4. 确保`rule_config_json`中也包含对应的`executor`字段

### 步骤2: 验证修复结果

运行以下SQL验证修复结果：

```sql
SELECT code, executor, rule_config_json->>'executor' as json_executor, enabled
FROM sws.review_checkpoint
WHERE code IN ('CP_SUM_MISMATCH', 'CP_UNIT_INCONSISTENT', 'CP_MISSING_SECTION', 
                'FORMAT_STRUCTURE', 'FORMAT_REFERENCE', 'FORMAT_TABLE')
ORDER BY code;
```

预期结果：
- `CP_*`系列的`executor`和`rule_config_json->>'executor'`都应该有值
- `FORMAT_*`系列的`enabled`应该为`false`

### 步骤3: 重新运行审查测试

执行迁移011后，重新运行审查测试：

```bash
测试文档审查.bat --direct 1 RULE
```

现在应该：
- ✅ 不再出现"Unknown executor"警告
- ✅ 不再出现重复问题（因为旧的`FORMAT_*`和`CONTENT_*`checkpoint已禁用）

## 技术细节

### Executor注册表

在`app/rule_engine/__init__.py`中，已经注册了以下executor：

```python
EXECUTOR_REGISTRY = {
    # ... 其他executor ...
    "cp_sum_mismatch": run_sum_mismatch,
    "cp_unit_inconsistent": run_unit_inconsistent,
    "cp_missing_section": run_missing_section,
    # ... 其他executor ...
}
```

### Checkpoint Runner逻辑

在`app/services/checkpoint_runner.py`中，executor的查找逻辑是：

```python
executor_name = rule_config.get("executor") or checkpoint_code.lower()
executor_fn = executor_registry.get(executor_name)
```

这意味着：
1. 优先从`rule_config_json->executor`读取
2. 如果不存在，使用`checkpoint_code.lower()`作为fallback
3. 对于`CP_SUM_MISMATCH`，fallback会变成`cp_sum_mismatch`，这正好匹配注册表中的名称

但是，为了数据一致性和可维护性，建议显式设置`executor`字段。

## 迁移历史

- **迁移009**: 修复checkpoint的`only_checks`配置，避免重复问题
- **迁移010**: 禁用旧的`FORMAT_*`和`CONTENT_*`系列checkpoint
- **迁移011**: 修复`CP_*`系列checkpoint的`executor`字段（本次新增）

## 注意事项

1. **数据一致性**: 虽然代码可以从`rule_config_json`读取executor，但表顶层的`executor`字段也应该正确设置，以保持数据一致性。

2. **向后兼容**: 迁移011会检查字段是否已设置，避免重复更新。

3. **测试建议**: 执行迁移后，建议运行一次完整的审查测试，确保所有checkpoint都能正常执行。
