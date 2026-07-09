@echo off
title NVIDIA AI Video Toolkit

set VENV_DIR=%~dp0venv
set SCRIPT_DIR=%~dp0

:: Check venv
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first to install.
    pause
    exit /b 1
)

:: Activate venv
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

:: Check PySide6
python -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PySide6 not installed. Please run setup.bat again.
    pause
    exit /b 1
)

:: Start app
cd /d "%SCRIPT_DIR%"
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] App exited with code %errorlevel%
    pause
)
