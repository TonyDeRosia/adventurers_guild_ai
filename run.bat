@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if exist "AdventurerGuildAI.exe" (
    start "" "AdventurerGuildAI.exe"
    exit /b 0
)

if exist "dist\AdventurerGuildAI.exe" (
    start "" "dist\AdventurerGuildAI.exe"
    exit /b 0
)

echo Adventurer Guild AI executable was not found.
echo.
echo End users should launch the installed app from:
echo - Start Menu shortcut, or
echo - Desktop shortcut, or
echo - AdventurerGuildAI.exe

echo.
echo Developers: use dev_run.bat for source-mode runs.
exit /b 1
