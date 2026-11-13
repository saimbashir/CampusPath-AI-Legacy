@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 scripts\bootstrap.py %*
) else (
  python scripts\bootstrap.py %*
)
if errorlevel 1 echo Startup did not complete. Read the message above and START_HERE.md.
pause
