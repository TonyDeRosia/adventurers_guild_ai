@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo Adventurer's Guild AI - Developer Source Launcher
echo ==================================================

echo [dev] Detecting Python...
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
    echo [error] Python 3.10+ is required for developer mode.
    goto :error_pause
)

echo [dev] Using %PYTHON_CMD%

if not exist ".deps_installed" (
    echo [dev] Dependencies missing. Running tools\setup_dev_env.bat...
    call "%~dp0tools\setup_dev_env.bat"
    if errorlevel 1 (
        echo [error] Dependency setup failed.
        goto :error_pause
    )
)

set "ENABLE_TERMINAL="
set "ARGS=%*"
echo %ARGS% | findstr /I /C:"--terminal" >nul && set "ENABLE_TERMINAL=1"
echo %ARGS% | findstr /I /C:"--mode terminal" >nul && set "ENABLE_TERMINAL=1"

if defined ENABLE_TERMINAL (
    echo [dev] Terminal mode enabled (developer-only).
    set "ADVENTURER_GUILD_AI_ENABLE_TERMINAL=1"
) else (
    echo [dev] Browser UI mode enabled (default).
)

echo [dev] Starting backend...
call %PYTHON_CMD% run.py %*
if errorlevel 1 (
    echo.
    echo [error] Launch failed with exit code %errorlevel%.
    goto :error_pause
)

exit /b 0

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
