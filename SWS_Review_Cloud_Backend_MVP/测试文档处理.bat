@echo off
REM 测试文档处理批处理脚本
REM 激活虚拟环境并执行测试脚本

echo ========================================
echo 测试文档处理
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
echo 激活虚拟环境...
call env\Scripts\activate.bat

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python 不可用！
    pause
    exit /b 1
)

REM 检查是否有参数
if "%1"=="list" (
    echo.
    echo ========================================
    echo 列出所有项目和文档
    echo ========================================
    echo.
    python 测试文档处理.py --list-documents
    pause
    exit /b 0
)

echo.
echo ========================================
echo 开始处理文档
echo ========================================
echo 文档ID: 2 (如果不存在会自动创建)
echo 文件路径: D:\Workspace\SWS_Review_Cloud_Backend\docs\校核文件\方案\广东科学技术职业学院珠海校区教师家园四期(报批稿).docx
echo.

REM 执行测试脚本（如果文档不存在会自动创建）
python 测试文档处理.py 2 "D:\Workspace\SWS_Review_Cloud_Backend\docs\校核文件\方案\广东科学技术职业学院珠海校区教师家园四期(报批稿).docx"

REM 检查执行结果
if errorlevel 1 (
    echo.
    echo ========================================
    echo 处理失败！
    echo ========================================
    echo.
    echo 提示: 运行 "测试文档处理.bat list" 可以查看所有可用的文档ID
) else (
    echo.
    echo ========================================
    echo 处理完成！
    echo ========================================
)

echo.
pause
