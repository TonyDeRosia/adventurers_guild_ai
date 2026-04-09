@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

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
    echo Python 3 is required to launch Build_AdventurersGuildAI.py.
    pause
    exit /b 1
)

%PYTHON_CMD% "%ROOT_DIR%Build_AdventurersGuildAI.py"
exit /b %errorlevel%
