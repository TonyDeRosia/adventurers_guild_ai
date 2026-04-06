@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo Adventurer's Guild AI - Source Launcher
echo ==================================================

call :detect_python
if "%PYTHON_CMD%"=="" (
    echo [error] Python 3 was not found. Install Python 3 and try again.
    goto :error_pause
)

echo [startup] Using Python command: %PYTHON_CMD%
echo [startup] Installing dependencies (if needed)...
call %PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [error] Dependency installation failed.
    goto :error_pause
)

echo [startup] Launching run.py...
call %PYTHON_CMD% -u run.py --mode web --host 127.0.0.1 --port 8000
set "APP_RC=%errorlevel%"

if not "%APP_RC%"=="0" (
    echo [error] Launcher exited with code %APP_RC%.
    goto :error_pause
)

exit /b 0

:detect_python
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto :eof
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
)

goto :eof

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
