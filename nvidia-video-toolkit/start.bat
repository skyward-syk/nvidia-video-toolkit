@echo off
title NVIDIA AI Video Toolkit

cd /d "%~dp0"

echo Starting NVIDIA AI Video Toolkit...
echo If nothing appears, check output/app.log
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Exit code: %errorlevel%
    pause
)
