@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
set "HOST=127.0.0.1"
set "PORT=8000"

echo ==================================================
echo Adventurer's Guild AI - Browser Window Launcher
echo ==================================================

if exist "AdventurerGuildAI.exe" (
    echo [launch] Starting AdventurerGuildAI.exe (single startup owner)...
    start "Adventurer Guild AI" "AdventurerGuildAI.exe" --mode web --host %HOST% --port %PORT%
    exit /b 0
)

if exist "dist\AdventurerGuildAI.exe" (
    echo [launch] Starting dist\AdventurerGuildAI.exe (single startup owner)...
    start "Adventurer Guild AI" "dist\AdventurerGuildAI.exe" --mode web --host %HOST% --port %PORT%
    exit /b 0
)

call :detect_python
if "%PYTHON_CMD%"=="" (
    echo [error] Could not find AdventurerGuildAI.exe or Python runtime.
    echo [error] Build the executable first using tools\build_exe.bat.
    goto :error_pause
)

echo [launch] Starting source launcher with %PYTHON_CMD% (single startup owner)...
start "Adventurer Guild AI (source)" cmd /k call %PYTHON_CMD% -u run.py --mode web --host %HOST% --port %PORT%
exit /b 0

:detect_python
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
goto :eof

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
