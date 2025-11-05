@echo off
setlocal EnableExtensions

rem ASCII-only script to bootstrap portable Python 3.10 inside repo and install deps.
rem Usage:
rem   prepare_slim.bat         (online: bootstrap embedded py310 + download + install)
rem   prepare_slim.bat offline (offline: use embedded py310 to install from local wheels)

set "BASE=%~dp0"
set "PROJ=%BASE%TripoSR"
set "WHEELS=%PROJ%\vendor\wheels"
set "MODELS=%PROJ%\models\TripoSR"
set "PYDIR=%PROJ%\.py310"
set "PYEXE=%PYDIR%\python.exe"
set "PYZIP=%PROJ%\.py310.zip"
set "PYEMB_URL=https://www.python.org/ftp/python/3.10.13/python-3.10.13-embed-amd64.zip"

if not exist "%WHEELS%" mkdir "%WHEELS%"
if not exist "%MODELS%" mkdir "%MODELS%"

if /I "%~1"=="offline" (
  if not exist "%PYEXE%" goto ERR_NO_EMBED
  goto INSTALL_ONLY
)

rem Online: bootstrap embedded Python 3.10 into repo using existing system tools
if not exist "%PYEXE%" (
  curl --version >NUL 2>&1 || goto ERR_CURL
  powershell -NoProfile -Command "$PSVersionTable.PSVersion" >NUL 2>&1 || goto ERR_PWSH
  curl -L -o "%PYZIP" "%PYEMB_URL%" || goto ERR_DL
  powershell -NoProfile -Command "Expand-Archive -Force '%PYZIP%' '%PYDIR%'" || goto ERR_UNZIP
  del /q "%PYZIP%" 2>NUL
  if exist "%PYDIR%\python310._pth" (
    findstr /C:"import site" "%PYDIR%\python310._pth" >NUL || echo import site>>"%PYDIR%\python310._pth"
  )
  curl -L -o "%PYDIR%\get-pip.py" https://bootstrap.pypa.io/get-pip.py || goto ERR_DL
  "%PYEXE%" "%PYDIR%\get-pip.py" || goto ERR_PIP
)

"%PYEXE%" -m pip install --upgrade pip setuptools wheel || goto ERR_PIP
"%PYEXE%" -m pip install --upgrade huggingface-hub || goto ERR_PIP

"%PYEXE%" -m pip download --dest "%WHEELS%" --index-url https://download.pytorch.org/whl/cu121 ^
  torch torchvision torchaudio || goto ERR_PIP

"%PYEXE%" -m pip download --dest "%WHEELS%" ^
  omegaconf==2.3.0 antlr4-python3-runtime==4.9.3 ^
  Pillow==10.1.0 einops==0.7.0 transformers==4.35.0 ^
  trimesh==4.0.5 rembg huggingface-hub imageio imageio-ffmpeg gradio || goto ERR_PIP

"%PYEXE%" -m pip download --dest "%WHEELS%" xatlas==0.0.9 || echo [WARN] xatlas download failed.
"%PYEXE%" -m pip wheel --wheel-dir "%WHEELS%" git+https://github.com/tatsy/torchmcubes.git || echo [WARN] torchmcubes wheel build failed.

"%PYEXE%" -m huggingface_hub.cli download stabilityai/TripoSR config.yaml --local-dir "%MODELS%" || goto ERR_HF
"%PYEXE%" -m huggingface_hub.cli download stabilityai/TripoSR model.ckpt --local-dir "%MODELS%" || goto ERR_HF

goto INSTALL_ONLY

:INSTALL_ONLY
dir /b "%WHEELS%" >NUL 2>&1 || goto ERR_NOWHEELS

"%PYEXE%" -m pip install --no-index --find-links "%WHEELS%" torch torchvision torchaudio || goto ERR_PIP
"%PYEXE%" -m pip install --no-index --find-links "%WHEELS%" ^
  omegaconf==2.3.0 antlr4-python3-runtime==4.9.3 ^
  Pillow==10.1.0 einops==0.7.0 transformers==4.35.0 ^
  trimesh==4.0.5 rembg huggingface-hub imageio imageio-ffmpeg gradio xatlas torchmcubes || goto ERR_PIP

echo.
echo === Wheels in repo ===
dir /b "%WHEELS%"
echo.
echo === Model files in repo ===
dir /b "%MODELS%"
echo.
echo Embedded Python ready: %PYEXE%
echo To run:
echo   cd TripoSR
echo   "%PYEXE%" run.py .\examples\chair.png --device cuda:0 --pretrained-model-name-or-path .\models\TripoSR --no-remove-bg --output-dir .\output
exit /b 0

:ERR_CURL
echo [ERROR] curl is not available. Install curl or run from newer Windows.
exit /b 1

:ERR_PWSH
echo [ERROR] PowerShell is required.
exit /b 1

:ERR_DL
echo [ERROR] Download failed.
exit /b 1

:ERR_UNZIP
echo [ERROR] Failed to extract embedded Python zip.
exit /b 1

:ERR_PIP
echo [ERROR] pip operation failed. Check network or environment.
exit /b 1

:ERR_HF
echo [ERROR] Hugging Face model download failed. Check network or auth.
exit /b 1

:ERR_NOWHEELS
echo [ERROR] No wheels found under %WHEELS%. Run online mode first or copy wheels here.
exit /b 1

:ERR_NO_EMBED
echo [ERROR] Embedded Python not found at %PYEXE%. Run online mode first.
exit /b 1

endlocal
