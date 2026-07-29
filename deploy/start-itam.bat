@echo off
REM ============================================================
REM  Start ITAM as the school server (no window, runs quietly).
REM  Put this file next to ITAM.exe and double-click it, or set
REM  it to run at startup so ITAM is always available.
REM ============================================================

REM Keep the same secret across restarts so logins stay valid.
REM Change this ONCE to any long random text, then leave it.
set SECRET_KEY=change-this-to-a-long-random-string-once

REM Serve to the whole network on port 8080. Caddy will put the
REM nice https://itam.madaacademy.edu.jo name in front of it.
set ITAM_NO_BROWSER=1
set PORT=8080

ITAM.exe
