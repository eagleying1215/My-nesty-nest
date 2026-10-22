@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 "启动工作台.py"
) else (
    python "启动工作台.py"
)
if errorlevel 1 (
    echo.
    echo 启动失败。请先安装 Python 3.10 或更新版本，并勾选 Add python.exe to PATH。
    pause
)
