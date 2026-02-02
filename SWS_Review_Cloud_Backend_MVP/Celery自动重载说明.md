# Celery Worker 自动重载说明

## 概述

Celery Worker **默认不会自动重载代码**。当你修改了任务代码（如 `app/worker/tasks.py`、`app/worker/pipeline.py` 等）后，需要手动重启 Worker 才能生效。

但是，Celery 支持 `--autoreload` 参数，可以自动检测代码变化并重新加载 Worker。

## 启用自动重载

### 方式1：使用批处理脚本（已启用）

运行 `启动CeleryWorker.bat`，脚本已配置自动重载：

```bash
启动CeleryWorker.bat
```

### 方式2：手动启动（添加 --autoreload）

```bash
# 激活虚拟环境
.\env\Scripts\activate

# 启动 Celery Worker（启用自动重载）
python -m celery -A app.worker.app worker --loglevel=info --pool=solo --autoreload
```

### 方式3：VS Code / VS2022 调试

VS Code 和 VS2022 的启动配置已更新，会自动使用 `--autoreload` 参数。

## 自动重载的工作原理

启用 `--autoreload` 后，Celery Worker 会：

1. **监控文件变化**：自动检测 Python 文件（`.py`）的修改
2. **重新加载模块**：检测到变化后，自动重新导入模块
3. **重启 Worker**：重新加载后，Worker 会使用新的代码

## 自动重载的限制

### Windows 上的注意事项

1. **Solo 池的限制**：
   - 使用 `solo` 池时，自动重载会重启整个 Worker 进程
   - 正在执行的任务会被中断
   - 新任务会等待 Worker 重启完成后执行

2. **性能影响**：
   - 频繁的代码修改会导致频繁重启
   - 可能影响任务执行效率

3. **稳定性**：
   - 在某些情况下，自动重载可能不够稳定
   - 如果遇到问题，可以禁用自动重载

## 禁用自动重载

如果需要禁用自动重载（例如生产环境），移除 `--autoreload` 参数：

```bash
python -m celery -A app.worker.app worker --loglevel=info --pool=solo
```

## 监控自动重载

启用自动重载后，当代码发生变化时，你会看到类似输出：

```
[2026-02-01 05:30:00,000: INFO/MainProcess] celery@LAPTOP-XXX ready.
[2026-02-01 05:30:15,000: INFO/MainProcess] Restarting celery@LAPTOP-XXX (autoreload)
[2026-02-01 05:30:16,000: INFO/MainProcess] celery@LAPTOP-XXX ready.
```

## 最佳实践

### 开发环境

✅ **推荐启用自动重载**：
- 方便快速迭代
- 减少手动重启次数
- 提高开发效率

### 生产环境

❌ **不推荐启用自动重载**：
- 可能影响任务执行
- 增加不稳定性
- 应该使用进程管理工具（如 systemd、supervisor）来管理 Worker

### 调试时

⚠️ **谨慎使用自动重载**：
- 调试时频繁重启可能影响断点
- 建议禁用自动重载，手动重启 Worker

## 手动重启 Worker

如果自动重载出现问题，可以手动重启：

1. **停止 Worker**：按 `Ctrl+C`
2. **重新启动**：运行 `启动CeleryWorker.bat` 或手动启动命令

## 检查 Worker 状态

可以通过以下方式检查 Worker 是否正常运行：

```bash
# 检查 Worker 是否在运行
python 检查Celery状态.py
```

## 常见问题

### Q: 修改代码后 Worker 没有自动重启？

A: 检查：
1. 是否添加了 `--autoreload` 参数
2. 修改的文件是否在监控范围内（`.py` 文件）
3. 文件是否成功保存

### Q: 自动重载导致任务中断？

A: 这是正常行为。自动重载会重启 Worker，正在执行的任务会被中断。建议：
- 开发时避免在任务执行过程中修改代码
- 或者等待任务完成后再修改代码

### Q: 自动重载不工作？

A: 尝试：
1. 手动重启 Worker
2. 检查文件权限
3. 查看 Worker 日志中的错误信息

## 总结

- ✅ **开发环境**：启用自动重载，提高开发效率
- ❌ **生产环境**：禁用自动重载，使用进程管理工具
- ⚠️ **调试时**：根据情况选择是否启用

当前的配置已默认启用自动重载，修改代码后 Worker 会自动重启，无需手动重启。
