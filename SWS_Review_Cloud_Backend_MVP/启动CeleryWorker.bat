@echo off
REM Windows 上启动 Celery Worker 的批处理脚本
REM 使用 solo 池以避免 Windows 上的权限问题

echo ========================================
echo 启动 Celery Worker (Windows)
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "env\Scripts\activate.bat" (
    echo 错误: 虚拟环境不存在！
    echo 请先创建虚拟环境: python -m venv env
    pause
    exit /b 1
)

REM 激活虚拟环境
call env\Scripts\activate.bat

REM 检查是否安装了 celery
python -c "import celery" 2>nul
if errorlevel 1 (
    echo 错误: Celery 未安装！
    echo 请运行: pip install celery[redis]
    pause
    exit /b 1
)

echo 正在启动 Celery Worker...
echo 使用 solo 池（Windows 兼容模式）
echo 启用自动重载（代码修改后自动重启）
echo.
echo 提示: 按 Ctrl+C 停止 Worker
echo ========================================
echo.

REM 启动 Celery Worker，使用 solo 池，启用自动重载
python -m celery -A app.worker.app worker --loglevel=info --pool=solo --autoreload

pause
