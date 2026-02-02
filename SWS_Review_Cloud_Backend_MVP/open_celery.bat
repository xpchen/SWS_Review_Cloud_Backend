@echo off
setlocal

REM 项目根目录
set "PROJ=D:\Workspace\SWS_Review_Cloud_Backend\SWS_Review_Cloud_Backend_MVP"
REM venv 激活脚本（cmd专用）
set "ACT=%PROJ%\env\Scripts\activate.bat"

if not exist "%ACT%" (
  echo [ERROR] Not found: "%ACT%"
  echo Please check venv path: %PROJ%\env
  pause
  exit /b 1
)

REM 生成临时脚本，避免 start/cmd 的引号转义问题
set "TMP=%TEMP%\__sws_start_celery__.bat"

> "%TMP%" echo @echo off
>>"%TMP%" echo cd /d "%PROJ%"
>>"%TMP%" echo call "%ACT%"
>>"%TMP%" echo cd /d "%PROJ%"
>>"%TMP%" echo echo.
>>"%TMP%" echo echo [INFO] Starting Celery worker...
>>"%TMP%" echo echo [INFO] Working dir: %%CD%%
>>"%TMP%" echo echo.
>>"%TMP%" echo python -m celery -A app.worker.app worker --loglevel=info --pool=solo
>>"%TMP%" echo echo.
>>"%TMP%" echo echo [INFO] Celery exited. Press any key to close.
>>"%TMP%" echo pause ^>nul

REM 打开新cmd运行临时脚本
start "SWS Celery Worker (env)" cmd /k "%TMP%"

endlocal
