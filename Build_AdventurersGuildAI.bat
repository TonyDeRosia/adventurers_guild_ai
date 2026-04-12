@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%logs\build"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\Build_AdventurersGuildAI_%STAMP%.log"

set "INTERNAL_BUILD_SCRIPT=%ROOT_DIR%tools\build_exe.bat"
if not exist "%INTERNAL_BUILD_SCRIPT%" (
    echo.
    echo ============================================================
    echo Adventurer Guild AI - Packaged EXE Builder
    echo ============================================================
    echo ERROR: Internal build worker script not found.
    echo Expected: "%INTERNAL_BUILD_SCRIPT%"
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Adventurer Guild AI - Packaged EXE Builder
echo ============================================================
echo Purpose: Build the packaged AdventurerGuildAI Windows EXE output.
echo What this script does: Runs the official PyInstaller/spec build pipeline.
echo Note: This is the packaged EXE build script. For source runs, use run.bat.
echo Log file: "%LOG_FILE%"
echo ============================================================
echo.

set "BUILD_LOG_FILE=%LOG_FILE%"
call "%INTERNAL_BUILD_SCRIPT%"
set "BUILD_EXIT_CODE=%errorlevel%"

echo.
if "%BUILD_EXIT_CODE%"=="0" (
    echo Build finished successfully.
    echo Packaged EXE folder: "%ROOT_DIR%dist\AdventurerGuildAI"
    echo Log file: "%LOG_FILE%"
) else (
    echo Build failed.
    echo See failure phase details above.
    echo Log file: "%LOG_FILE%"
)
echo.
pause
exit /b %BUILD_EXIT_CODE%
