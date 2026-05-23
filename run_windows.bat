@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "VENV_STREAMLIT=%PROJECT_DIR%.venv\Scripts\streamlit.exe"

if not exist "%VENV_STREAMLIT%" (
    echo Virtual environment not found.
    echo Run setup_windows.ps1 first:
    echo powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
    exit /b 1
)

cd /d "%PROJECT_DIR%"
call "%VENV_STREAMLIT%" run app.py
