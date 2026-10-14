@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing. Running install.bat first...
    call install.bat
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" --version >nul 2>nul
if errorlevel 1 (
    echo Virtual environment is broken. Running install.bat to rebuild...
    call install.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

echo Starting Ultimate Hermes Agent server...
start "Ultimate Hermes Agent server" cmd /c "".venv\Scripts\python.exe" main.py"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8765"
echo Ultimate Hermes Agent is running at http://127.0.0.1:8765
echo Keep the server command window open while using the dashboard.
pause
