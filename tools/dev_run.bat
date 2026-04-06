@echo off
setlocal

set "ROOT_DIR=%~dp0.."
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
    echo Python 3.10+ is required for developer mode.
    exit /b 1
)

if not exist ".deps_installed" (
    call "%~dp0setup_dev_env.bat"
    if errorlevel 1 (
        echo Setup failed.
        exit /b 1
    )
)

set "ENABLE_TERMINAL="
set "ARGS=%*"
echo %ARGS% | findstr /I /C:"--terminal" >nul && set "ENABLE_TERMINAL=1"
echo %ARGS% | findstr /I /C:"--mode terminal" >nul && set "ENABLE_TERMINAL=1"

if defined ENABLE_TERMINAL (
    set "ADVENTURER_GUILD_AI_ENABLE_TERMINAL=1"
)

call %PYTHON_CMD% run.py %*
exit /b %errorlevel%
