@echo off
chcp 65001 >nul
cd /d "%~dp0"
python 执行迁移011.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 迁移执行失败，请检查错误信息
    pause
)
