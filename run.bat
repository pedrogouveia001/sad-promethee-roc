@echo off
title PrometheeInvestor Startup Script
echo ===================================================
echo   Starting PrometheeInvestor (PROMETHEE ROC)
echo ===================================================
cd /d "%~dp0"

:: 1. Check for local virtual environment
if exist .venv\Scripts\python.exe (
    echo [INFO] Found local virtual environment in .venv
    set "PYTHON_PATH=.venv\Scripts\python.exe"
) else if exist ..\sad-smarter-b3\.venv\Scripts\python.exe (
    echo [INFO] Found virtual environment in sibling directory: ..\sad-smarter-b3\.venv
    set "PYTHON_PATH=..\sad-smarter-b3\.venv\Scripts\python.exe"
) else (
    echo [WARNING] No virtual environment found.
    echo [INFO] Creating a new local virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Please ensure Python is installed and added to your PATH.
        pause
        exit /b 1
    )
    set "PYTHON_PATH=.venv\Scripts\python.exe"
    echo [INFO] Installing requirements.txt...
    %PYTHON_PATH% -m pip install --upgrade pip
    %PYTHON_PATH% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: 2. Check if database is seeded (sad_promethee.db)
if not exist instance\sad_promethee.db (
    echo [INFO] Database not found or not initialized. Seeding database with historical test data...
    %PYTHON_PATH% seed_historical.py
)

:: 3. Run the Flask application
echo [INFO] Launching app.py...
echo [INFO] Please open your browser at: http://localhost:5000
%PYTHON_PATH% app.py

if errorlevel 1 (
    echo.
    echo [ERROR] The application crashed or was terminated.
    pause
)
