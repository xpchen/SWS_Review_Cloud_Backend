@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%1"=="" (
    echo 用法: 检查版本文件对象.bat ^<版本ID^>
    echo 示例: 检查版本文件对象.bat 13
    pause
    exit /b 1
)
python 检查版本文件对象.py %1
pause
