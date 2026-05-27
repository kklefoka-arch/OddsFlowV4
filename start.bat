@echo off
cd /d "%~dp0"
echo Starting OddsFlow V4...
start "ngrok" powershell -NoExit -Command "ngrok http 8083"
uvicorn app.main:app --host 0.0.0.0 --port 8083
pause
