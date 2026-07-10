@echo off
REM ────────────────────────────────────────────────────────────────────
REM  One-click starter for the ITAM Platform (Windows)
REM  Double-click this file. It installs dependencies on first run,
REM  starts the server with the zero-setup in-memory database, and
REM  opens the API documentation in your browser.
REM ────────────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Please install it from https://nodejs.org
  pause
  exit /b 1
)

if not exist node_modules (
  echo Installing dependencies - this runs only the first time, please wait...
  call npm.cmd install --no-audit --no-fund
  if errorlevel 1 (
    echo.
    echo npm install failed - see the messages above.
    pause
    exit /b 1
  )
)

set DB_TYPE=sqljs
set DB_SYNCHRONIZE=true

echo.
echo ============================================================
echo  Starting the ITAM Platform...
echo  Your browser will open automatically in ~20 seconds.
echo  Keep THIS window open - it is the server.
echo  Web app: http://localhost:3000
echo ============================================================
echo.

REM Open the web app once the server has had time to boot.
start "" /b cmd /c "timeout /t 20 /nobreak >nul & start http://localhost:3000/"

call npm.cmd run start:dev
pause
