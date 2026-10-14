@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking Python installation...
set PYTHON_CMD=
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>nul
    if not errorlevel 1 goto install_deps
    echo Existing virtual environment is invalid. Rebuilding...
    rmdir /s /q .venv >nul 2>nul
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" goto install_deps
    py -3 -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" goto install_deps
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m venv .venv
    if exist ".venv\Scripts\python.exe" goto install_deps
)

echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
pause
exit /b 1

:install_deps
echo [2/3] Installing dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Installation failed. Review the error above.
    pause
    exit /b 1
)

echo [3/3] Setting up workspace directories...
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "data" mkdir data
if not exist "workspace" mkdir workspace

echo.
echo ========================================================
echo Ultimate Hermes Agent setup complete!
echo Double-click start.bat to launch the local dashboard.
echo ========================================================
pause
exit /b 0
