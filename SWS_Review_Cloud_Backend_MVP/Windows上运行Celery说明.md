# Windows 上运行 Celery Worker 说明

## 问题说明

在 Windows 上，Celery 默认使用的 `prefork` 进程池会有权限问题，导致错误：
```
PermissionError: [WinError 5] 拒绝访问。
```

## 解决方案

在 Windows 上运行 Celery Worker 时，必须使用 `solo` 或 `threads` 池。

### 方式1：使用批处理脚本（推荐）

直接运行：
```bash
启动CeleryWorker.bat
```

### 方式2：手动启动

```bash
# 激活虚拟环境
.\env\Scripts\activate

# 启动 Celery Worker（使用 solo 池）
python -m celery -A app.worker.app worker --loglevel=info --pool=solo
```

### 方式3：使用 threads 池（如果需要并发）

```bash
python -m celery -A app.worker.app worker --loglevel=info --pool=threads --concurrency=4
```

## 配置说明

### 自动配置（已实现）

代码已经自动检测 Windows 平台并使用 `solo` 池（`app/worker/app.py`）：
```python
if sys.platform == "win32":
    app.conf.worker_pool = "solo"
```

### 手动指定池类型

即使代码已自动配置，你也可以在启动时手动指定：

**Solo 池（单线程，Windows 推荐）**：
```bash
celery -A app.worker.app worker --loglevel=info --pool=solo
```

**Threads 池（多线程并发）**：
```bash
celery -A app.worker.app worker --loglevel=info --pool=threads --concurrency=4
```

## 池类型对比

| 池类型 | Windows 支持 | 并发能力 | 适用场景 |
|--------|-------------|---------|---------|
| `prefork` | ❌ 不支持 | 多进程 | Linux/Mac 生产环境 |
| `solo` | ✅ 支持 | 单线程 | Windows 开发/测试 |
| `threads` | ✅ 支持 | 多线程 | Windows 需要并发时 |

## 注意事项

1. **Solo 池限制**：
   - 单线程执行，任务按顺序处理
   - 适合开发和测试环境
   - 不适合高并发生产环境

2. **Threads 池**：
   - 支持多线程并发
   - 适合 Windows 上需要并发的场景
   - 注意线程安全（大部分 Python 库是线程安全的）

3. **生产环境**：
   - Windows 上可以使用 `threads` 池
   - 但建议使用 Linux 服务器 + `prefork` 池以获得更好的性能

## VS2022 调试配置

VS2022 的启动配置已更新，会自动添加 `--pool=solo` 参数。

## 验证

启动 Worker 后，你应该看到类似输出：
```
[2026-02-01 05:20:00,000: INFO/MainProcess] Connected to redis://localhost:6379/1
[2026-02-01 05:20:00,000: INFO/MainProcess] mingle: searching for neighbors
[2026-02-01 05:20:01,000: INFO/MainProcess] mingle: all alone
[2026-02-01 05:20:01,000: INFO/MainProcess] celery@DESKTOP-XXX ready.
```

如果看到 `PermissionError`，说明没有使用 `--pool=solo` 参数。

## 常见问题

### Q: 为什么 Windows 上不能使用 prefork 池？

A: `prefork` 池使用 `fork()` 系统调用创建子进程，但 Windows 不支持 `fork()`，只支持 `spawn()`。Windows 上的多进程实现有权限限制，会导致权限错误。

### Q: Solo 池性能如何？

A: Solo 池是单线程的，任务按顺序执行。对于开发和小规模使用足够，但不适合高并发生产环境。如果需要并发，使用 `threads` 池。

### Q: 可以在 Windows 上使用 threads 池吗？

A: 可以！`threads` 池在 Windows 上工作良好，支持多线程并发。使用 `--pool=threads --concurrency=4` 启动。
