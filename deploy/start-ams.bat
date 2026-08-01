@echo off
REM ============================================================
REM  Start AMS as the school server (no window, runs quietly).
REM  Prefer Install-AMS.bat -- it does all of this properly and
REM  starts AMS at boot. This file is the manual alternative:
REM  put it next to AMS.exe and run it.
REM ============================================================

REM The session key is generated automatically on first run and kept in
REM instance\secret_key, so there is nothing to set here any more.

REM Serve to the whole network on port 8080. Caddy will put the
REM nice https://itam.madaacademy.edu.jo name in front of it.
set AMS_NO_BROWSER=1
set PORT=8080

AMS.exe
