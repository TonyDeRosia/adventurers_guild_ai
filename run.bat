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
    if exist "dist\AdventurerGuildAI.exe" (
        echo Python not detected. Launching prebuilt executable...
        start "" "dist\AdventurerGuildAI.exe"
        exit /b 0
    )

    echo.
    echo Python 3.10+ is required OR use the prebuilt executable.
    echo.
    echo Download Python:
    echo https://www.python.org/downloads/windows/
    echo.
    echo IMPORTANT:
    echo - Check 'Add Python to PATH' during install
    echo.
    echo OR use the .exe version if available.
    echo.
    pause
    exit /b 1
)

echo ====================================
echo       Adventurer Guild AI
echo ====================================
echo Starting via Python launcher...

if not exist ".deps_installed" (
    echo First-time setup detected.
    call "%ROOT_DIR%setup.bat"
    if errorlevel 1 (
        echo Setup failed. The game cannot start yet.
        pause
        exit /b 1
    )
)

call %PYTHON_CMD% run.py
if errorlevel 1 (
    echo The game exited with an error.
    pause
    exit /b 1
)

exit /b 0
