@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%\logs\tools"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\create_release_package_%STAMP%.log"

set "INTERACTIVE=0"
echo %CMDCMDLINE% | find /I " /c " >nul || set "INTERACTIVE=1"

call :log ============================================================
call :log Adventurer Guild AI - Release Package Script
call :log Purpose: Copy installer into release\user after packaging audit.
call :log Note: This script prepares release handoff files only.
call :log Log file: %LOG_FILE%
call :log ============================================================

call :step "[1/4] Resolving Python"
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" call :fail "[1/4] Resolving Python" "Python 3.10+ is required to run packaging audits."
call :pass "[1/4] Resolving Python" "Using %PYTHON_CMD%"

call :step "[2/4] Validating installer availability"
set "INSTALLER=installer\Output\AdventurerGuildAI_Setup.exe"
if not exist "%INSTALLER%" call :fail "[2/4] Validating installer availability" "Installer not found. Build it with tools\build_installer.bat first."
call :pass "[2/4] Validating installer availability" "Installer found."

call :step "[3/4] Preparing release folder"
set "RELEASE_DIR=release\user"
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%" >>"%LOG_FILE%" 2>&1
mkdir "%RELEASE_DIR%" >>"%LOG_FILE%" 2>&1
copy /y "%INSTALLER%" "%RELEASE_DIR%\AdventurerGuildAI_Setup.exe" >nul
if errorlevel 1 call :fail "[3/4] Preparing release folder" "Failed to copy installer into release folder."
call :pass "[3/4] Preparing release folder" "Installer copied to release folder."

call :step "[4/4] Auditing source packaging layout"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\comfyui\README.txt ^
  --require-file packaging\windows\runtime_bundle\workflows\scene_image.json ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[4/4] Auditing source packaging layout" "Packaging audit failed."
call :pass "[4/4] Auditing source packaging layout" "Packaging audit passed."

call :log SUCCESS: Release package prepared.
call :log Output: %RELEASE_DIR%\AdventurerGuildAI_Setup.exe
call :log Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 0

:step
call :log %~1
exit /b 0

:pass
call :log %~1 - SUCCESS. %~2
exit /b 0

:fail
call :log %~1 - FAILURE. %~2
call :log See log: %LOG_FILE%
echo.
echo ERROR: %~2
echo Phase failed: %~1
echo Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 1

:log
echo %~1
>>"%LOG_FILE%" echo %~1
exit /b 0
