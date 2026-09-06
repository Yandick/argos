@echo off
setlocal
cd /d "%~dp0"
title ServerHelper

echo ========================================================
echo   ServerHelper - Agent Multi-Task Remote Orchestrator
echo ========================================================

if not exist ".venv\Scripts\server-helper.exe" (
    echo [Info] Virtual environment not found, installing package...
    where uv >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        uv venv
        uv pip install -e .
    ) else (
        python -m venv .venv
        .\.venv\Scripts\pip install -e .
    )
)

.\.venv\Scripts\server-helper.exe %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [Error] CLI exited with error code %ERRORLEVEL%.
    pause
)
