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
if exist "dist\AdventurerGuildAI" rmdir /s /q "dist\AdventurerGuildAI"

echo Running pre-build packaging audit...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Pre-build audit failed.
    exit /b 1
)

set "PYINSTALLER_CMD=%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onedir --windowed --name AdventurerGuildAI run.py --add-data data;data --add-data app/static;app/static --collect-submodules app --collect-submodules engine --collect-submodules images --collect-submodules memory --collect-submodules models --collect-submodules prompts --collect-submodules rules --collect-all fastapi --collect-all uvicorn --collect-all starlette"

echo Building standalone executable with PyInstaller...
echo %PYINSTALLER_CMD%
call %PYINSTALLER_CMD%
if errorlevel 1 (
    echo Executable build failed.
    exit /b 1
)

if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    echo Executable build did not produce dist\AdventurerGuildAI\AdventurerGuildAI.exe.
    exit /b 1
)

if exist "packaging\windows\runtime_bundle" (
    echo Copying runtime bundle scaffold...
    xcopy /E /I /Y "packaging\windows\runtime_bundle" "dist\AdventurerGuildAI\runtime_bundle" >nul
)

echo Running post-build distribution audit...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Post-build audit failed.
    exit /b 1
)

echo Build complete: dist\AdventurerGuildAI\AdventurerGuildAI.exe
exit /b 0
