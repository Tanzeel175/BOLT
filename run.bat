@echo off
title BOLT - Personal Autonomous AI Assistant
cd /d "%~dp0"

:: Check if standalone compiled executable exists
if exist "dist\BOLT\BOLT.exe" (
    start "" "dist\BOLT\BOLT.exe" %*
    exit /b 0
)

:: Otherwise run via virtualenv pythonw (no console window) or python
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" run.py %*
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py %*
    exit /b 0
)

:: Fallback to system python
python run.py %*

