@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%\logs\build"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\Build_AdventurersGuildAI_%STAMP%.log"

set "INTERACTIVE=0"
echo %CMDCMDLINE% | find /I " /c " >nul || set "INTERACTIVE=1"

call :log ============================================================
call :log Adventurer Guild AI - Packaged EXE Build
call :log Purpose: Build dist\AdventurerGuildAI\AdventurerGuildAI.exe from source.
call :log Log file: %LOG_FILE%
call :log ============================================================

set "PYTHON_CMD="
call :step "[1/6] Resolve Python"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" (
    call :fail "[1/6] Resolve Python" "Python 3.10+ was not found in PATH."
    goto :build_failed
)
call :pass "[1/6] Resolve Python" "Using %PYTHON_CMD%"

call :step "[2/6] Install build dependencies"
call %PYTHON_CMD% -m pip install --upgrade pip pyinstaller -r requirements.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[2/6] Install build dependencies" "Dependency installation failed."
if errorlevel 1 goto :build_failed
call :pass "[2/6] Install build dependencies" "Build dependencies are ready."

call :step "[3/6] Clean old build output"
if exist "build" rmdir /s /q "build" >>"%LOG_FILE%" 2>&1
if exist "dist\AdventurerGuildAI" rmdir /s /q "dist\AdventurerGuildAI" >>"%LOG_FILE%" 2>&1
call :pass "[3/6] Clean old build output" "Old build output removed."

call :step "[4/6] Run prebuild audit"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path packaging\windows\runtime_bundle ^
  --require-file packaging\windows\runtime_bundle\comfyui\README.txt ^
  --require-file packaging\windows\runtime_bundle\workflows\scene_image.json ^
  --require-file packaging\windows\runtime_bundle\workflows\character_portrait.json ^
  --require-file packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[4/6] Run prebuild audit" "Prebuild packaging audit failed."
if errorlevel 1 goto :build_failed
call :pass "[4/6] Run prebuild audit" "Packaging input audit passed."

set "SPEC_FILE=packaging\windows\AdventurerGuildAI.spec"
if not exist "%SPEC_FILE%" (
    call :fail "[5/6] Run PyInstaller spec build" "Spec file is missing: %SPEC_FILE%."
    goto :build_failed
)

call :step "[5/6] Run PyInstaller spec build"
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean "%SPEC_FILE%" >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[5/6] Run PyInstaller spec build" "PyInstaller build failed."
if errorlevel 1 goto :build_failed
if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    call :fail "[5/6] Run PyInstaller spec build" "Expected output EXE was not produced."
    goto :build_failed
)
call :pass "[5/6] Run PyInstaller spec build" "PyInstaller build produced AdventurerGuildAI.exe."

call :step "[6/6] Run post-build audit"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\data\sample_campaign.json ^
  --require-file dist\AdventurerGuildAI\app\static\index.html ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\comfyui\README.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\workflows\scene_image.json ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\workflows\character_portrait.json ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[6/6] Run post-build audit" "Post-build distribution audit failed."
if errorlevel 1 goto :build_failed
call :pass "[6/6] Run post-build audit" "Distribution audit passed."

call :log SUCCESS: Packaged EXE build complete.
call :log Final EXE path: %ROOT_DIR%\dist\AdventurerGuildAI\AdventurerGuildAI.exe
call :log Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 0

:build_failed
exit /b 1

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
echo Step failed: %~1
echo Log file: %LOG_FILE%
if "%INTERACTIVE%"=="1" pause
exit /b 1

:log
if "%~1"=="" exit /b 0
echo(%*
>>"%LOG_FILE%" echo(%*
exit /b 0
