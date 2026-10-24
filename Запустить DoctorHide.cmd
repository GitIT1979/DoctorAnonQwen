@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Интерпретатор: сначала тот, что стоит на этой машине, иначе из PATH
set "PY=C:\Users\User\AppData\Local\Programs\AutoClaw2\resources\vendor\python\python.exe"
if not exist "%PY%" set "PY=python"

rem Если сервер уже поднят — второй экземпляр не запускаем
powershell -NoProfile -Command "try{(Invoke-WebRequest 'http://127.0.0.1:8765/api/status' -UseBasicParsing -TimeoutSec 2)|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
  start "DoctorHide server" cmd /k "%PY%" gui\server.py --port 8765
  timeout /t 3 /nobreak >nul
)

start "" http://127.0.0.1:8765/
exit /b 0
