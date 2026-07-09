@echo off
title NVIDIA AI Video Toolkit - Setup

echo ============================================================
echo   NVIDIA AI Video Toolkit - Setup
echo ============================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ not found
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

set VENV_DIR=%~dp0venv
if exist "%VENV_DIR%" (
    echo [INFO] venv already exists, skipping creation
) else (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet

echo.
echo [INFO] Installing PyTorch CUDA...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
if %errorlevel% neq 0 (
    echo [WARN] PyTorch CUDA failed, trying CPU version...
    pip install torch torchvision
)

echo.
echo [INFO] Installing dependencies...
pip install -r "%~dp0requirements.txt"

ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] FFmpeg not found in PATH
    echo Download: https://ffmpeg.org/download.html
) else (
    echo [OK] FFmpeg ready
)

echo.
echo ============================================================
echo   Setup complete! Double-click run.bat to start.
echo ============================================================
pause
