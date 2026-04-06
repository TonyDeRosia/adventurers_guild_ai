@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo Adventurer's Guild AI - Developer Source Launcher
echo ==================================================

echo [source] Detecting Python...
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
    echo [error] Python 3.10+ is required to run from source.
    goto :error_pause
)

echo [source] Using %PYTHON_CMD%

if not exist ".deps_installed" (
    echo [source] Dependencies not initialized. Running tools\setup_dev_env.bat...
    call "%ROOT_DIR%tools\setup_dev_env.bat"
    if errorlevel 1 (
        echo [error] Dependency setup failed.
        goto :error_pause
    )
)

set "ENABLE_TERMINAL="
set "PREV_ARG="
for %%A in (%*) do (
    if /I "%%~A"=="--terminal" set "ENABLE_TERMINAL=1"
    if /I "!PREV_ARG!"=="--mode" if /I "%%~A"=="terminal" set "ENABLE_TERMINAL=1"
    set "PREV_ARG=%%~A"
)

if defined ENABLE_TERMINAL (
    echo [source] Terminal mode enabled (developer-only).
    set "ADVENTURER_GUILD_AI_ENABLE_TERMINAL=1"
) else (
    echo [source] Browser UI mode enabled (default for developer source runs).
echo [source] End users should run the installed app from Start Menu/Desktop.
)

echo [source] Starting application...
call %PYTHON_CMD% -u run.py %*
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
