@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo 检查 Checkpoint 配置
echo ============================================================
echo.

REM 激活虚拟环境
if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
) else (
    echo 错误: 虚拟环境不存在，请先创建虚拟环境
    pause
    exit /b 1
)

REM 执行检查脚本
python 检查checkpoint配置.py

pause
