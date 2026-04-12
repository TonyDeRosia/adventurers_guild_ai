@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%\logs\tools"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\build_installer_%STAMP%.log"

set "INTERACTIVE=0"
echo %CMDCMDLINE% | find /I " /c " >nul || set "INTERACTIVE=1"

call :log ============================================================
call :log Adventurer Guild AI - Installer Build Script
call :log Purpose: Build installer\Output\AdventurerGuildAI_Setup.exe.
call :log Note: This script packages app files only. It does NOT bundle model weights.
call :log Log file: %LOG_FILE%
call :log ============================================================

call :step "[1/5] Resolving Python"
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" call :fail "[1/5] Resolving Python" "Python 3.10+ is required to run packaging audits."
call :pass "[1/5] Resolving Python" "Using %PYTHON_CMD%"

call :step "[2/5] Ensuring EXE build exists"
if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
  call :log EXE missing; invoking tools\build_exe.bat
  call "%~dp0build_exe.bat" >>"%LOG_FILE%" 2>&1
  if errorlevel 1 call :fail "[2/5] Ensuring EXE build exists" "Could not build executable prerequisite."
)
call :pass "[2/5] Ensuring EXE build exists" "Executable is present."

call :step "[3/5] Resolving Inno Setup"
set "ISCC_CMD="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  set "ISCC_CMD=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
  set "ISCC_CMD=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
  where iscc >nul 2>&1
  if %errorlevel%==0 set "ISCC_CMD=iscc"
)
if "%ISCC_CMD%"=="" call :fail "[3/5] Resolving Inno Setup" "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php"
call :pass "[3/5] Resolving Inno Setup" "Using %ISCC_CMD%"

call :step "[4/5] Auditing dist payload"
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\comfyui\README.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\workflows\scene_image.json ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[4/5] Auditing dist payload" "Distribution audit failed."
call :pass "[4/5] Auditing dist payload" "Distribution audit passed."

call :step "[5/5] Building Windows installer"
"%ISCC_CMD%" "installer\AdventurerGuildAI.iss" >>"%LOG_FILE%" 2>&1
if errorlevel 1 call :fail "[5/5] Building Windows installer" "Installer build failed."
if not exist "installer\Output\AdventurerGuildAI_Setup.exe" call :fail "[5/5] Building Windows installer" "Installer output not found."
call :pass "[5/5] Building Windows installer" "Installer built successfully."

call :log SUCCESS: Installer build complete.
call :log Output: installer\Output\AdventurerGuildAI_Setup.exe
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
