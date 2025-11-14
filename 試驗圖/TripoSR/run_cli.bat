@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
set PYTHONUTF8=1

:: Usage:
::   Put input images under input\ or pass a full path.
::   run_cli.bat input\chair.png   (outputs will be in output\)

set VENV_SCRIPTS=.venv\Scripts
set PROJECT_DIR=%~dp0
set TRIPOSR_DIR=%PROJECT_DIR%vendor\TripoSR
set OUTPUT_DIR=%PROJECT_DIR%output

if not exist "%VENV_SCRIPTS%\activate.bat" (
  echo [ERROR] Environment not initialized. Please run setup_env.bat first.
  exit /b 1
)

call "%VENV_SCRIPTS%\activate.bat"
if errorlevel 1 (
  echo [ERROR] Failed to activate venv
  exit /b 1
)

if not exist "%TRIPOSR_DIR%\run.py" (
  echo [ERROR] TripoSR source or run.py not found. Re-run setup_env.bat.
  exit /b 1
)

if "%~1"=="" (
  echo [INFO] No input image provided. Using TripoSR\examples\chair.png
  set INPUT_IMG=%TRIPOSR_DIR%\examples\chair.png
) else (
  set INPUT_IMG=%~1
)

if not exist "%OUTPUT_DIR%" (
  mkdir "%OUTPUT_DIR%"
)

pushd "%TRIPOSR_DIR%"
echo [INFO] Running inference: %INPUT_IMG%
python run.py "%INPUT_IMG%" --output-dir "%OUTPUT_DIR%"
set EXITCODE=%ERRORLEVEL%
popd

if %EXITCODE% EQU 0 (
  echo [SUCCESS] Done. Outputs at %OUTPUT_DIR%
) else (
  echo [ERROR] Inference failed (code %EXITCODE%)
)

exit /b %EXITCODE%

