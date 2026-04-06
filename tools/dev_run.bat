@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

echo [dev] Launching source mode via run.py

set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [error] Python 3 was not found. Install Python 3 and try again.
    exit /b 1
)

call %PYTHON_CMD% -u run.py --mode web --host 127.0.0.1 --port 8000
exit /b %errorlevel%
