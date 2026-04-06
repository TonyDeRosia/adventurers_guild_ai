@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo [release] Looking for packaged executable...

if exist "AdventurerGuildAI.exe" (
    echo [release] Launching AdventurerGuildAI.exe
    start "" "AdventurerGuildAI.exe"
    exit /b 0
)

if exist "dist\AdventurerGuildAI.exe" (
    echo [release] Launching dist\AdventurerGuildAI.exe
    start "" "dist\AdventurerGuildAI.exe"
    exit /b 0
)

echo [release] AdventurerGuildAI.exe was not found.
echo.
echo End users should launch the installed app from Start Menu/Desktop

echo after running AdventurerGuildAI-Setup.exe.
echo Developers should run source mode with dev_run.bat.
exit /b 1
