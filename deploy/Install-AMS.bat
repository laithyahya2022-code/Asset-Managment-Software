@echo off
REM Double-click this (right-click -> Run as administrator) to install AMS
REM as a proper Windows service on this machine.
REM
REM Keep it in the same folder as AMS.exe and Install-AMS.ps1.

net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo   This installer needs administrator rights.
  echo   Right-click Install-AMS.bat and choose "Run as administrator".
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-AMS.ps1" %*
echo.
pause
