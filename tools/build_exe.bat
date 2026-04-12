@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%\logs\tools"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
if defined BUILD_LOG_FILE (
    set "LOG_FILE=%BUILD_LOG_FILE%"
) else (
    set "LOG_FILE=%LOG_DIR%\build_exe_%STAMP%.log"
)

set "INTERACTIVE=0"
echo %CMDCMDLINE% | find /I " /c " >nul || set "INTERACTIVE=1"

call :log ============================================================
call :log Adventurer Guild AI - EXE Build Script
call :log Purpose: Build dist\AdventurerGuildAI\AdventurerGuildAI.exe with PyInstaller.
call :log Note: Internal worker script. Use Build_AdventurersGuildAI.bat from repo root.
call :log Note: This script builds binaries only. It does NOT download model weights.
call :log Log file: %LOG_FILE%
call :log ============================================================

set "PYTHON_CMD="
call :step "[1/6] Resolving Python"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" (
    call :fail "[1/6] Resolving Python" "Python 3.10+ is required to build AdventurerGuildAI.exe."
)
call :pass "[1/6] Resolving Python" "Using %PYTHON_CMD%"

call :step "[2/6] Installing build dependencies"
call %PYTHON_CMD% -m pip install --upgrade pip pyinstaller -r requirements.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[2/6] Installing build dependencies" "Failed to install build/runtime dependencies."
call :pass "[2/6] Installing build dependencies" "Dependencies installed."

call :step "[3/6] Cleaning old outputs"
if exist "build" rmdir /s /q "build" >>"%LOG_FILE%" 2>&1
if exist "dist\AdventurerGuildAI" rmdir /s /q "dist\AdventurerGuildAI" >>"%LOG_FILE%" 2>&1
call :pass "[3/6] Cleaning old outputs" "Old output folders removed."

call :step "[4/6] Running prebuild audit"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\comfyui\README.txt ^
  --require-file packaging\windows\runtime_bundle\workflows\scene_image.json ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[4/6] Running prebuild audit" "Pre-build audit failed."
call :pass "[4/6] Running prebuild audit" "Packaging input audit passed."

set "SPEC_FILE=packaging\windows\AdventurerGuildAI.spec"
if not exist "%SPEC_FILE%" call :fail "[5/6] Running PyInstaller" "Spec file not found at %SPEC_FILE%."

call :step "[5/6] Running PyInstaller"
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean "%SPEC_FILE%" >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[5/6] Running PyInstaller" "Executable build failed."
if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" call :fail "[5/6] Running PyInstaller" "Build did not produce AdventurerGuildAI.exe."
call :pass "[5/6] Running PyInstaller" "Executable produced."

call :step "[6/6] Build complete"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\comfyui\README.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\workflows\scene_image.json ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[6/6] Build complete" "Post-build distribution audit failed."
call :pass "[6/6] Build complete" "Distribution audit passed."

call :log SUCCESS: Build complete.
call :log Output folder: dist\AdventurerGuildAI
call :log Output executable: dist\AdventurerGuildAI\AdventurerGuildAI.exe
call :log Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 0

:step
call :log %~1
exit /b 0

:pass
call :log SUCCESS: %~2
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
if "%~1"=="" exit /b 0
echo(%*
>>"%LOG_FILE%" echo(%*
exit /b 0
