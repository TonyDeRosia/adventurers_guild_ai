@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

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
        exit /b 1
    )
)

echo Installing dependencies...
call %PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    exit /b 1
)

call %PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

echo Setup complete.
echo ok>".deps_installed"
exit /b 0
