@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

REM Release launcher only: this script does not run source mode.
if exist "AdventurerGuildAI.exe" (
    start "" "AdventurerGuildAI.exe"
    exit /b 0
)

if exist "dist\AdventurerGuildAI.exe" (
    start "" "dist\AdventurerGuildAI.exe"
    exit /b 0
)

echo AdventurerGuildAI.exe was not found in this folder.
echo.
echo End users should launch the installed app from Start Menu/Desktop after running the installer.
echo Developers should run source mode with tools\dev_run.bat
exit /b 1
