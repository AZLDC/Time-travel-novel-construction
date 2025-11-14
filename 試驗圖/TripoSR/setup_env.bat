@echo off
cls
setlocal
chcp 65001 >nul
set PYTHONUTF8=1

:: ------------------------------------------------------------
:: TripoSR environment bootstrap (Windows, global Python)
:: - Use system/global Python (no local .venv)
:: - Clone upstream repo into vendor\TripoSR
:: - Install PyTorch and dependencies into the global environment
:: ------------------------------------------------------------
set PROJECT_DIR=%~dp0
set VENDOR_DIR=%PROJECT_DIR%vendor
set TRIPOSR_DIR=%VENDOR_DIR%\TripoSR

:: Choose Python 3 interpreter: try py -3, then python3, then python (must be >= 3.8)
set "PYTHON_CMD="

call :ProbePy py -3
if defined PYTHON_CMD goto :HavePython
call :ProbePy python3
if defined PYTHON_CMD goto :HavePython
call :ProbePy python
if defined PYTHON_CMD goto :HavePython
if not defined PYTHON_CMD (
  echo [ERROR] Python 3 (>=3.8) not found. Please install and retry.
  exit /b 1
)

:HavePython

:: Upgrade pip / setuptools / wheel (via selected Python)
%PYTHON_CMD% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip / setuptools / wheel
  exit /b 1
)

:: Ensure vendor dir exists
if not exist "%VENDOR_DIR%" (
  mkdir "%VENDOR_DIR%"
)

:: Clone TripoSR source (Git required; will fallback to ZIP if Git is missing)
if not exist "%TRIPOSR_DIR%" (
  where git >nul 2>nul
  if errorlevel 1 (
    echo [WARN] Git not found. Trying ZIP fallback download...
    set "ZIP_URL=https://github.com/VAST-AI-Research/TripoSR/archive/refs/heads/main.zip"
    set "ZIP_PATH=%VENDOR_DIR%\TripoSR-main.zip"
    set "UNZIP_DIR=%VENDOR_DIR%\TripoSR-main"
    
    echo [INFO] Downloading ZIP: %ZIP_URL%
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_PATH%' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
      echo [ERROR] Failed to download ZIP. Please install Git or download manually.
      exit /b 1
    )
    
    echo [INFO] Extracting ZIP to %VENDOR_DIR%
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%VENDOR_DIR%' -Force } catch { exit 1 }"
    if errorlevel 1 (
      echo [ERROR] Failed to extract ZIP.
      exit /b 1
    )
    
    del /f /q "%ZIP_PATH%" >nul 2>nul
    if exist "%TRIPOSR_DIR%" rmdir /s /q "%TRIPOSR_DIR%"
    ren "%UNZIP_DIR%" TripoSR
    if not exist "%TRIPOSR_DIR%" (
      echo [ERROR] ZIP fallback failed to create %TRIPOSR_DIR%
      exit /b 1
    )
  ) else (
    echo [INFO] Cloning TripoSR into %TRIPOSR_DIR%
    git clone https://github.com/VAST-AI-Research/TripoSR "%TRIPOSR_DIR%"
    if errorlevel 1 (
      echo [ERROR] Failed to clone TripoSR
      exit /b 1
    )
  )
) else (
  echo [INFO] TripoSR repo exists, pulling latest
  pushd "%TRIPOSR_DIR%"
  git pull
  popd
)

:: Install TripoSR dependencies via helper Python script (handles torch, transformers, requirements, gradio)
pushd "%TRIPOSR_DIR%"
echo [INFO] Installing TripoSR requirements via tr_setup_deps.py
%PYTHON_CMD% "%PROJECT_DIR%tr_setup_deps.py"
set "TR_DEPS_RC=%ERRORLEVEL%"
popd

if not "%TR_DEPS_RC%"=="0" (
  echo [ERROR] tr_setup_deps.py failed with exit code %TR_DEPS_RC%.
  exit /b %TR_DEPS_RC%
)

echo ================================================
echo [SUCCESS] Setup completed!
echo [NEXT] Run run_gradio.bat (GUI) or run_cli.bat (CLI)
exit /b 0

:ProbePy
set "CAND=%*"
%CAND% --version 2>nul | findstr /c:"Python 3.8" /c:"Python 3.9" /c:"Python 3.10" /c:"Python 3.11" /c:"Python 3.12" >nul && set "PYTHON_CMD=%CAND%"
exit /b
