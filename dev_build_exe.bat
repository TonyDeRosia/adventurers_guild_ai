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
    echo Python 3.10+ is required to build AdventurerGuildAI.exe.
    exit /b 1
)

echo Installing/updating build tools...
call %PYTHON_CMD% -m pip install --upgrade pip pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
)

echo Cleaning prior build outputs...
if exist "build" rmdir /s /q "build"
if exist "dist\AdventurerGuildAI.exe" del /q "dist\AdventurerGuildAI.exe"

echo Building standalone executable with PyInstaller...
echo - onefile bundle with embedded Python runtime
echo - windowed mode to avoid terminal/Python noise for end users
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name AdventurerGuildAI run.py --add-data "data;data" --add-data "app/static;app/static" --collect-submodules app --collect-submodules engine --collect-submodules images --collect-submodules memory --collect-submodules models --collect-submodules prompts --collect-submodules rules
if errorlevel 1 (
    echo Executable build failed.
    exit /b 1
)

if not exist "dist\AdventurerGuildAI.exe" (
    echo Executable build did not produce dist\AdventurerGuildAI.exe.
    exit /b 1
)

echo Build complete: dist\AdventurerGuildAI.exe
exit /b 0
