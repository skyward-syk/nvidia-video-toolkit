@echo off
chcp 65001 >nul
title NVIDIA AI 视频工具套件
setlocal enabledelayedexpansion

set VENV_DIR=%~dp0venv
set SCRIPT_DIR=%~dp0

echo ============================================================
echo   NVIDIA AI 视频工具套件
echo ============================================================
echo.

:: 检查虚拟环境是否存在
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [错误] 虚拟环境未找到！
    echo.
    echo 请先双击运行 setup.bat 完成安装，然后再运行本脚本。
    echo.
    pause
    exit /b 1
)

:: 激活虚拟环境
echo [信息] 正在激活虚拟环境...
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [错误] 虚拟环境激活失败！
    pause
    exit /b 1
)

:: 检查关键依赖
echo [信息] 检查依赖...
python -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] PySide6 未安装，请重新运行 setup.bat
    pause
    exit /b 1
)

:: 启动应用
echo [信息] 正在启动 GUI...
cd /d "%SCRIPT_DIR%"
python main.py

:: 如果异常退出，显示错误
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo [错误] 应用异常退出 (错误码: %errorlevel%)
    echo ============================================================
    echo.
    echo 常见问题：
    echo   1. 缺少依赖 - 请重新运行 setup.bat
    echo   2. 显卡驱动问题 - 确保 NVIDIA 驱动已安装
    echo   3. Python 版本不兼容 - 需要 Python 3.10+
    echo.
    pause
)
