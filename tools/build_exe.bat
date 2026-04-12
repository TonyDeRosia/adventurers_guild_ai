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

echo Installing/updating build and runtime dependencies...
call %PYTHON_CMD% -m pip install --upgrade pip pyinstaller -r requirements.txt
if errorlevel 1 (
    echo Failed to install build/runtime dependencies.
    exit /b 1
)

echo Cleaning prior build outputs...
if exist "build" rmdir /s /q "build"
if exist "dist\AdventurerGuildAI" rmdir /s /q "dist\AdventurerGuildAI"

echo Running pre-build packaging audit...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\comfyui\README.txt ^
  --require-file packaging\windows\runtime_bundle\workflows\scene_image.json ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Pre-build audit failed.
    exit /b 1
)

set "SPEC_FILE=packaging\windows\AdventurerGuildAI.spec"
if not exist "%SPEC_FILE%" (
    echo PyInstaller spec file not found at %SPEC_FILE%.
    exit /b 1
)

echo Building standalone executable with PyInstaller spec...
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 (
    echo Executable build failed.
    exit /b 1
)

if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    echo Executable build did not produce dist\AdventurerGuildAI\AdventurerGuildAI.exe.
    exit /b 1
)

echo Running post-build distribution audit...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\comfyui\README.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\workflows\scene_image.json ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Post-build audit failed.
    exit /b 1
)

echo Build complete: dist\AdventurerGuildAI\AdventurerGuildAI.exe
exit /b 0
