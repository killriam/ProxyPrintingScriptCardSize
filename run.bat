@echo off
setlocal enabledelayedexpansion
title MaMo Proxy Print Pipeline
echo ========================================================
echo   MaMo Proxy Print Pipeline
echo ========================================================
echo.

cd /d "%~dp0"

python proxy_print.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Pipeline encountered an error (exit code %ERRORLEVEL%).
) else (
    echo.
    echo [SUCCESS] All outputs generated successfully in ready2Print\
)

echo.
pause
