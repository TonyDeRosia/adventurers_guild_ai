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
    echo Python 3.10+ is required to run packaging audits.
    exit /b 1
)

set "INSTALLER=installer\Output\AdventurerGuildAI_Setup.exe"
if not exist "%INSTALLER%" (
    echo Installer not found at %INSTALLER%.
    echo Build it first with tools\build_installer.bat
    exit /b 1
)

set "RELEASE_DIR=release\user"
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

copy /y "%INSTALLER%" "%RELEASE_DIR%\AdventurerGuildAI_Setup.exe" >nul

echo Running source-tree packaging audit...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\comfyui\README.txt ^
  --require-file packaging\windows\runtime_bundle\workflows\scene_image.json ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Packaging audit failed.
    exit /b 1
)

echo Release package prepared:
echo - %RELEASE_DIR%\AdventurerGuildAI_Setup.exe
echo.
echo This package is end-user safe and excludes developer-only scripts.
exit /b 0
