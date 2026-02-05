@echo off
REM Windows 上启动 FastAPI 服务器的批处理脚本

echo ========================================
echo 启动 FastAPI API 服务器 (Windows)
echo ========================================
echo.

REM 切换到项目目录
cd /d "%~dp0"

REM 检查虚拟环境是否存在（优先检查 env，然后是 .venv）
set "VENV_ACTIVATE="
if exist "env\Scripts\activate.bat" (
    set "VENV_ACTIVATE=env\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=.venv\Scripts\activate.bat"
) else (
    echo 错误: 虚拟环境不存在！
    echo 请先创建虚拟环境: python -m venv env
    echo 或者: python -m venv .venv
    pause
    exit /b 1
)

REM 激活虚拟环境
call "%VENV_ACTIVATE%"

REM 检查是否安装了 uvicorn
python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo 错误: uvicorn 未安装！
    echo 请运行: pip install -r requirements.txt
    pause
    exit /b 1
)

echo 正在启动 FastAPI API 服务器...
echo 服务器地址: http://0.0.0.0:8000
echo API 文档: http://localhost:8000/docs
echo 健康检查: http://localhost:8000/health
echo.
echo 提示: 按 Ctrl+C 停止服务器
echo ========================================
echo.

REM 启动 uvicorn 服务器，启用自动重载
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level info

pause
