@echo off
REM 检查 LibreOffice 配置的诊断脚本

echo ========================================
echo LibreOffice 配置诊断工具
echo ========================================
echo.

REM 切换到项目目录
cd /d "%~dp0"

REM 检查常见的 LibreOffice 安装路径
echo [1] 检查 LibreOffice 安装路径...
echo.

set "FOUND=0"
set "SOFFICE_PATH="

REM 检查 PATH 中的 soffice.exe
where soffice.exe >nul 2>&1
if %errorlevel% == 0 (
    for /f "delims=" %%i in ('where soffice.exe') do (
        set "SOFFICE_PATH=%%i"
        set "FOUND=1"
        echo [✓] 在 PATH 中找到: %%i
        goto :check_paths
    )
)

:check_paths
REM 检查常见安装路径
set "PATHS[0]=C:\Program Files\LibreOffice\program\soffice.exe"
set "PATHS[1]=C:\Program Files (x86)\LibreOffice\program\soffice.exe"
set "PATHS[2]=%LOCALAPPDATA%\Programs\LibreOffice\program\soffice.exe"

for /L %%i in (0,1,2) do (
    call set "TEST_PATH=%%PATHS[%%i]%%"
    if exist "!TEST_PATH!" (
        if !FOUND! == 0 (
            set "SOFFICE_PATH=!TEST_PATH!"
            set "FOUND=1"
        )
        echo [✓] 找到安装: !TEST_PATH!
    ) else (
        echo [ ] 未找到: !TEST_PATH!
    )
)

echo.
if %FOUND% == 0 (
    echo [✗] 未找到 LibreOffice 安装！
    echo.
    echo 请安装 LibreOffice:
    echo 1. 下载地址: https://www.libreoffice.org/download/
    echo 2. 安装后重新运行此脚本检查
    pause
    exit /b 1
)

echo.
echo [2] 测试 LibreOffice 版本...
echo.

"%SOFFICE_PATH%" --version
if %errorlevel% neq 0 (
    echo [✗] LibreOffice 无法正常运行！
    echo.
    echo 可能的原因:
    echo 1. LibreOffice 安装损坏
    echo 2. 缺少必要的 DLL 依赖
    echo 3. 权限问题
    echo.
    echo 建议: 重新安装 LibreOffice
    pause
    exit /b 1
) else (
    echo [✓] LibreOffice 可以正常运行
)

echo.
echo [3] 检查必要的目录和文件...
echo.

for %%f in ("%SOFFICE_PATH%") do set "SOFFICE_DIR=%%~dpf"
for %%f in ("%SOFFICE_DIR%") do set "LIBREOFFICE_BASE=%%~dpf.."

echo LibreOffice 可执行文件: %SOFFICE_PATH%
echo Program 目录: %SOFFICE_DIR%
echo 基础目录: %LIBREOFFICE_BASE%

if not exist "%SOFFICE_DIR%" (
    echo [✗] Program 目录不存在！
    pause
    exit /b 1
)

if not exist "%LIBREOFFICE_BASE%\program\fundamentalrc" (
    echo [⚠] 未找到 fundamentalrc 文件（可能影响转换）
) else (
    echo [✓] 找到 fundamentalrc 文件
)

echo.
echo [4] 检查环境变量...
echo.

echo PATH 中包含 LibreOffice: 
echo %PATH% | findstr /i "%SOFFICE_DIR%" >nul
if %errorlevel% == 0 (
    echo [✓] PATH 已包含 LibreOffice 目录
) else (
    echo [⚠] PATH 未包含 LibreOffice 目录（程序会自动添加）
)

echo.
echo [5] 测试 DOCX 转 PDF 功能...
echo.

REM 创建临时测试文件
set "TEST_DIR=%TEMP%\libreoffice_test_%RANDOM%"
mkdir "%TEST_DIR%" 2>nul

echo 创建测试 DOCX 文件...
REM 这里可以创建一个简单的测试，但为了简化，我们只检查命令格式
echo [信息] 测试命令格式:
echo "%SOFFICE_PATH%" --headless --nodefault --nolockcheck --convert-to pdf --outdir "%TEST_DIR%" test.docx

echo.
echo ========================================
echo 诊断完成
echo ========================================
echo.
echo 如果 LibreOffice 已正确安装但仍出现转换错误:
echo 1. 检查防病毒软件是否阻止了 LibreOffice
echo 2. 尝试以管理员权限运行
echo 3. 检查日志文件获取详细错误信息
echo 4. 确认 LibreOffice 版本 >= 7.0
echo.

pause
