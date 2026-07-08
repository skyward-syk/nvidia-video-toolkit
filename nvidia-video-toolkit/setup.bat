@echo off
chcp 65001 >nul
title NVIDIA AI 视频工具套件 — 沙箱安装

echo ============================================================
echo   NVIDIA AI 视频工具套件 — 一键安装
echo ============================================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已找到
python --version
echo.

:: 创建虚拟环境
set VENV_DIR=%~dp0venv
if exist "%VENV_DIR%" (
    echo [信息] 虚拟环境已存在，跳过创建
) else (
    echo [信息] 正在创建虚拟环境...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建完成
)
echo.

:: 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"

:: 升级 pip
echo [信息] 升级 pip...
python -m pip install --upgrade pip --quiet

:: 安装 PyTorch CUDA 版
echo.
echo ============================================================
echo   安装 PyTorch (CUDA 12.1)
echo ============================================================
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
if %errorlevel% neq 0 (
    echo [警告] PyTorch CUDA 版安装失败，尝试 CPU 版...
    pip install torch torchvision
)

:: 安装其余依赖
echo.
echo ============================================================
echo   安装其余依赖
echo ============================================================
pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，请检查网络连接
)

:: 检查 FFmpeg
echo.
echo ============================================================
echo   检查 FFmpeg
echo ============================================================
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] FFmpeg 未找到或不在 PATH 中
    echo   视频处理功能需要 FFmpeg
    echo   下载地址: https://ffmpeg.org/download.html
    echo   下载后将 ffmpeg.exe 所在目录加入系统 PATH
    echo   或在应用「设置」中手动指定路径
) else (
    echo [OK] FFmpeg 已就绪
)

echo.
echo ============================================================
echo   安装完成！
echo ============================================================
echo.
echo 启动方式:
echo   方法1: 双击 run.bat
echo   方法2: 在终端执行 run.bat
echo.
pause
