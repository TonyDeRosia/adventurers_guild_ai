@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

echo ================================================
echo Adventurer's Guild AI (Source Run)
echo ================================================

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
    echo [error] Python 3 was not found in PATH.
    echo [error] Install Python 3.10+ and try again.
    goto :error_pause
)

echo [setup] Installing/updating dependencies from requirements.txt ...
call %PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [error] Dependency installation failed.
    goto :error_pause
)

echo [run] Launching application via run.py ...
call %PYTHON_CMD% run.py
set "RUN_RC=%ERRORLEVEL%"
if not "%RUN_RC%"=="0" (
    echo [error] Application exited with code %RUN_RC%.
    goto :error_pause
)

exit /b 0

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
