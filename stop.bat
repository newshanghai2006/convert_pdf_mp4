@echo off
title PDF to Mp4 Stop Server

echo ========================================
echo   Stop PDF to AI Film service (port 5005)
echo ========================================
echo.

REM Match ":5005 " (with trailing space) so ports like 50053/50054 are not killed
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /C:":5005 " ^| findstr "LISTENING"') do (
    echo Killing PID %%a ...
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)

if "%FOUND%"=="0" (
    echo No service found on port 5005 ^(maybe already stopped^).
) else (
    echo Service stopped.
)

echo.
pause
