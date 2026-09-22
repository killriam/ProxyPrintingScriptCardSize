@echo off
setlocal
title MaMo Proxy Print Studio
cd /d "%~dp0"

REM Launch GUI (tries pythonw first for no console, falls back to python)
start "" pythonw proxy_gui.py %* 2>nul
if %ERRORLEVEL% NEQ 0 (
    python proxy_gui.py %*
)
