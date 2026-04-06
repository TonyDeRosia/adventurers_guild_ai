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
    echo Python 3.10+ is required to build the executable.
    pause
    exit /b 1
)

echo Ensuring PyInstaller is installed...
call %PYTHON_CMD% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    call %PYTHON_CMD% -m pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo Building AdventurerGuildAI.exe...
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --name AdventurerGuildAI run.py --add-data "data;data" --add-data "data/workflows;data/workflows" --add-data "app/static;app/static"
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete:
if exist "dist\AdventurerGuildAI.exe" (
    echo dist\AdventurerGuildAI.exe
) else (
    echo Expected output not found in dist\.
)
pause
exit /b 0
