@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ====================================
echo       Adventurer Guild AI
echo ====================================

echo Checking Python installation...
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python is not installed or not available in PATH.
        echo Please install Python 3.10 or newer from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)

if not exist ".deps_installed" (
    echo First-time setup detected.
    call "%ROOT_DIR%setup.bat"
    if errorlevel 1 (
        echo Setup failed. The game cannot start yet.
        pause
        exit /b 1
    )
)

echo Starting Adventurer Guild AI...
call %PYTHON_CMD% run.py
if errorlevel 1 (
    echo The game exited with an error.
    pause
    exit /b 1
)

exit /b 0
