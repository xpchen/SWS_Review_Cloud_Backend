@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo 测试文档审查
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

REM 检查参数
if "%~1"=="" (
    echo 用法: 测试文档审查.bat ^<版本ID^> [审查类型] [--direct] [--diagnose]
    echo.
    echo 参数说明:
    echo   版本ID: 必需，要审查的版本ID
    echo   审查类型: RULE ^(规则审查^) ^| AI ^(AI审查^) ^| MIXED ^(混合审查^)，默认: RULE
    echo   --direct: 直接执行（不使用Celery，同步执行）
    echo   --diagnose: 诊断 Celery Worker 状态并退出
    echo.
    echo 示例:
    echo   测试文档审查.bat 10 RULE --direct
    echo   测试文档审查.bat 10 AI --direct --show-results
    echo   测试文档审查.bat --diagnose
    pause
    exit /b 1
)

REM 如果是诊断模式
if "%~1"=="--diagnose" (
    python 测试审查.py --diagnose
    pause
    exit /b 0
)

set VERSION_ID=%~1
set RUN_TYPE=%~2
if "%RUN_TYPE%"=="" set RUN_TYPE=RULE
if "%RUN_TYPE%"=="--direct" set RUN_TYPE=RULE

REM 检查是否有 --direct 参数
set DIRECT_FLAG=
if "%~3"=="--direct" set DIRECT_FLAG=--direct
if "%~2"=="--direct" set DIRECT_FLAG=--direct

REM 检查是否有 --show-results 参数
set SHOW_RESULTS=
if "%~3"=="--show-results" set SHOW_RESULTS=--show-results
if "%~4"=="--show-results" set SHOW_RESULTS=--show-results
if "%~2"=="--show-results" set SHOW_RESULTS=--show-results

echo 版本ID: %VERSION_ID%
echo 审查类型: %RUN_TYPE%
if not "%DIRECT_FLAG%"=="" echo 执行模式: 直接执行（不使用Celery）
echo.

REM 执行测试脚本
python 测试审查.py %VERSION_ID% %RUN_TYPE% %DIRECT_FLAG% %SHOW_RESULTS%

pause
