@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo 导出 Checkpoint 数据
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

REM 执行导出脚本
python 导出checkpoint数据.py

pause
