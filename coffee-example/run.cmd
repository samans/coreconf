@echo off
REM Wrapper so run.ps1 can be launched from cmd.exe (or a double-click)
REM without changing the machine's PowerShell execution policy.
REM
REM Runs the native-Windows launcher: creates .venv, installs deps, and
REM starts the web console. Needs Python 3.10+ on PATH.
REM
REM   run.cmd
REM   run.cmd -Port 9000

setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
exit /b %ERRORLEVEL%
