@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
set PYTHONUTF8=1

:: Usage:
::   Double-click this file or run it without arguments.
::   It will open a simple GUI for selecting input and output paths.

set PROJECT_DIR=%~dp0
set SIMPLE_GUI=%PROJECT_DIR%simple_gui.py

if not exist "%SIMPLE_GUI%" (
  echo [ERROR] simple_gui.py not found. Please ensure it exists in the project root.
  exit /b 1
)

echo [INFO] Launching TripoSR Simple GUI...
python3 "%SIMPLE_GUI%"

exit /b %ERRORLEVEL%

