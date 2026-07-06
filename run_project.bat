@echo off
title CityPulse AI Platform Launcher
color 0B
echo ============================================================
echo   🏙️  Welcome to CityPulse AI Civic Intelligence Platform
echo ============================================================
echo.

:: Step 1: Check Python
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

:: Step 2: Virtual Environment Setup
echo [2/3] Setting up Python virtual environment...
if not exist "venv" (
    echo Virtual environment 'venv' not found. Creating it now...
    python -m venv venv
)
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Step 3: Install/Update Dependencies
echo [3/3] Verifying dependencies...
echo This may take a moment if dependencies are being installed/updated...
pip install -r requirements.txt

:: Launch
echo.
echo ============================================================
echo   🎉 Launching Streamlit Dashboard...
echo ============================================================
echo.
streamlit run app.py

pause
