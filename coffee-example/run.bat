@echo off
REM One-command launcher for the CORECONF coffee-maker fleet web console (Windows).
REM
REM Creates a local virtual environment (first run only), installs the two
REM dependencies, and starts the web console. Needs Python 3.9+ on PATH.
REM
REM   run.bat

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo error: 'python' not found. Install Python 3.9+ and retry.
  exit /b 1
)

if not exist ".venv" (
  echo [run] creating virtual environment (.venv)...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

python -c "import aiocoap, cbor2" >nul 2>nul
if errorlevel 1 (
  echo [run] installing dependencies...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
)

echo [run] starting web console on http://127.0.0.1:8080
python webui\web_console.py

endlocal
