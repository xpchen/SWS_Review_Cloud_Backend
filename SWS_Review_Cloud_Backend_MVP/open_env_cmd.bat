@echo off
setlocal

REM 项目根目录
set "PROJ=D:\Workspace\SWS_Review_Cloud_Backend\SWS_Review_Cloud_Backend_MVP"
REM venv 激活脚本（Windows）
set "ACT=%PROJ%\env\Scripts\activate.bat"

if not exist "%ACT%" (
  echo [ERROR] Not found: "%ACT%"
  echo Please check venv path: %PROJ%\env
  pause
  exit /b 1
)

REM 打开新cmd并保持窗口（/k），同时定位到项目目录并激活env
start "SWS Review Cloud (env)" cmd /k ^
  "cd /d "%PROJ%" && call "%ACT%" && cd /d "%PROJ%""

endlocal
