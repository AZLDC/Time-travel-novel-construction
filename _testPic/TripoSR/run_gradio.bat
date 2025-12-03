@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
set PYTHONUTF8=1

set PROJECT_DIR=%~dp0
set TRIPOSR_DIR=%PROJECT_DIR%vendor\TripoSR

if not exist "%TRIPOSR_DIR%\gradio_app.py" (
  echo [ERROR] TripoSR source or gradio_app.py not found. Re-run setup_env.bat.
  exit /b 1
)

pushd "%TRIPOSR_DIR%"
python3 gradio_app.py
set EXITCODE=%ERRORLEVEL%
popd

exit /b %EXITCODE%
