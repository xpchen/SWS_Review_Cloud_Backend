# Uvicorn 控制台日志输出说明

## 默认行为

`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` 命令**默认就会输出控制台信息**，包括：

### 1. 启动信息
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. 请求日志（默认）
每次API请求都会输出：
```
INFO:     127.0.0.1:52341 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:52342 - "POST /api/auth/login HTTP/1.1" 200 OK
```

### 3. 错误日志
如果发生错误：
```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  ...
```

### 4. 热重载日志
代码修改后自动重载：
```
INFO:     Detected file change in 'app/main.py'. Reloading...
INFO:     Stopping reloader process [12345]
INFO:     Starting reloader process [12346]
```

## 在 VS2022 中查看日志

### 方法1：输出窗口（推荐）

1. **调试** → **窗口** → **输出**
2. 在**显示输出来源**下拉菜单中选择：
   - **调试** - 显示调试器输出
   - **Python** - 显示 Python 解释器输出（包括 uvicorn 日志）

### 方法2：集成终端

如果使用 `.vscode/launch.json` 配置（`"console": "integratedTerminal"`），日志会显示在 VS2022 的集成终端中。

### 方法3：外部终端

如果直接在外部终端运行，日志会直接显示在终端中。

## 配置更详细的日志

### 1. 增加日志详细程度

```bash
# 使用 --log-level 参数
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# 日志级别选项：
# critical - 只显示严重错误
# error    - 显示错误
# warning  - 显示警告和错误
# info     - 显示信息、警告和错误（默认）
# debug    - 显示所有日志（最详细）
# trace    - 显示最详细的跟踪信息
```

### 2. 使用访问日志格式

```bash
# 使用 --access-log 启用访问日志（默认已启用）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --access-log

# 禁用访问日志
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --no-access-log
```

### 3. 自定义日志格式

创建 `uvicorn_log_config.py`：

```python
import logging
import sys

# 配置日志格式
log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "format": "%(asctime)s [%(levelname)s] %(client_addr)s - \"%(request_line)s\" %(status_code)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO"},
    },
}
```

使用：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-config uvicorn_log_config.py
```

## 在 VS2022 中配置日志输出

### 更新启动配置

在项目属性的**调试**标签页中，参数可以添加日志级别：

**参数**：
```
app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

或者在 `.vscode/launch.json` 中：

```json
{
    "name": "Python: FastAPI (API Server)",
    "type": "debugpy",
    "request": "launch",
    "module": "uvicorn",
    "args": [
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--log-level",
        "debug"  // 添加这一行
    ],
    "console": "integratedTerminal",  // 确保使用集成终端
    ...
}
```

## 应用内日志配置

### 配置 Python logging

在 `app/main.py` 中添加日志配置：

```python
import logging
import sys

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)  # 输出到控制台
    ]
)

# 设置各个模块的日志级别
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.DEBUG)  # 应用日志更详细
```

### 在代码中使用日志

```python
import logging

logger = logging.getLogger(__name__)

def some_function():
    logger.debug("调试信息")
    logger.info("一般信息")
    logger.warning("警告信息")
    logger.error("错误信息")
```

## 查看日志的完整命令示例

### 开发环境（详细日志）
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

### 生产环境（简洁日志）
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info --no-access-log
```

### 完整配置示例
```bash
uvicorn app.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level debug \
  --access-log \
  --use-colors
```

## VS2022 调试时的日志输出

### 确保日志可见

1. **输出窗口设置**：
   - **调试** → **窗口** → **输出**
   - 选择 **Python** 作为输出源
   - 勾选 **自动滚动**

2. **集成终端设置**：
   - 如果使用 `"console": "integratedTerminal"`
   - 日志会直接显示在终端中
   - 可以右键终端标签页 → **清除缓冲区** 清空日志

3. **环境变量**：
   添加 `PYTHONUNBUFFERED=1` 确保日志实时输出：
   ```
   PYTHONUNBUFFERED=1
   ```

## 日志输出示例

### 正常启动
```
INFO:     Will watch for changes in these directories: ['D:\\Workspace\\SWS_Review_Cloud_Backend\\SWS_Review_Cloud_Backend_MVP']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### API 请求
```
INFO:     127.0.0.1:52341 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:52342 - "POST /api/auth/login HTTP/1.1" 200 OK
INFO:     127.0.0.1:52343 - "GET /api/versions/1/outline HTTP/1.1" 200 OK
```

### 错误情况
```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "app/routers/auth.py", line 15, in login
    user = auth_service.login(body.username, body.password)
  ...
```

### 代码修改重载
```
INFO:     Detected file change in 'app/routers/auth.py'. Reloading...
INFO:     Stopping reloader process [12345]
INFO:     Starting reloader process [12347]
INFO:     Started server process [12348]
INFO:     Application startup complete.
```

## 快速测试

运行以下命令，你应该能看到所有日志输出：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

然后访问 `http://localhost:8000/health`，你应该能看到：
- 启动日志
- 请求日志
- 响应日志

## 总结

✅ **uvicorn 默认就会输出控制台信息**
✅ **在 VS2022 的输出窗口中可以查看**
✅ **可以通过 `--log-level` 参数调整详细程度**
✅ **添加 `PYTHONUNBUFFERED=1` 确保实时输出**

如果看不到日志，检查：
1. 输出窗口是否选择了正确的输出源（Python）
2. 是否使用了集成终端配置
3. 环境变量 `PYTHONUNBUFFERED` 是否设置
