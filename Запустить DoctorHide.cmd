@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYW=pythonw"
where pythonw >nul 2>&1 || set "PYW=python"

rem если сервер уже поднят — второй экземпляр не запускаем
powershell -NoProfile -Command "try{(Invoke-WebRequest 'http://127.0.0.1:8765/api/status' -UseBasicParsing -TimeoutSec 2)|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
  start "DoctorHide server" /min %PYW% gui\server.py --port 8765
  timeout /t 2 /nobreak >nul
)

start "" http://127.0.0.1:8765/
exit /b 0
