@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

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

echo Release package prepared:
echo - %RELEASE_DIR%\AdventurerGuildAI_Setup.exe
echo.
echo This package is end-user safe and excludes developer-only scripts.
exit /b 0
