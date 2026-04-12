@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%\logs\tools"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\setup_dev_env_%STAMP%.log"

set "INTERACTIVE=0"
echo %CMDCMDLINE% | find /I " /c " >nul || set "INTERACTIVE=1"

call :log ============================================================
call :log Adventurer Guild AI - Dev Environment Setup
call :log Purpose: Install Python dependencies for local development/build.
call :log Note: This script does NOT install ComfyUI models/checkpoints.
call :log Log file: %LOG_FILE%
call :log ============================================================

call :step "[1/3] Resolving Python"
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" call :fail "[1/3] Resolving Python" "Python 3.10+ is required."
call :pass "[1/3] Resolving Python" "Using %PYTHON_CMD%"

call :step "[2/3] Upgrading pip"
call %PYTHON_CMD% -m pip install --upgrade pip >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[2/3] Upgrading pip" "Failed to upgrade pip."
call :pass "[2/3] Upgrading pip" "pip upgraded."

call :step "[3/3] Installing requirements"
call %PYTHON_CMD% -m pip install -r requirements.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[3/3] Installing requirements" "Dependency installation failed."
echo ok>".deps_installed"
call :pass "[3/3] Installing requirements" "Dependencies installed."

call :log SUCCESS: Development environment setup complete.
call :log Marker file: .deps_installed
call :log Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 0

:step
call :log %~1
exit /b 0

:pass
call :log %~1 - SUCCESS. %~2
exit /b 0

:fail
call :log %~1 - FAILURE. %~2
call :log See log: %LOG_FILE%
echo.
echo ERROR: %~2
echo Phase failed: %~1
echo Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 1

:log
echo %~1
>>"%LOG_FILE%" echo %~1
exit /b 0
