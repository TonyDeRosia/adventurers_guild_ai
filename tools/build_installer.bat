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

if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    echo No executable detected in dist\AdventurerGuildAI\. Building executable first...
    call "%~dp0build_exe.bat"
    if errorlevel 1 (
        echo Could not build executable.
        exit /b 1
    )
)

set "ISCC_CMD="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_CMD=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_CMD=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    where iscc >nul 2>&1
    if %errorlevel%==0 set "ISCC_CMD=iscc"
)

if "%ISCC_CMD%"=="" (
    echo Inno Setup 6 was not found. Install from https://jrsoftware.org/isinfo.php
    exit /b 1
)

echo Auditing dist payload before installer build...
call %PYTHON_CMD% tools\audit_distribution.py ^
  --path dist\AdventurerGuildAI ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\THIRD_PARTY_NOTICES.txt ^
  --require-file dist\AdventurerGuildAI\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt
if errorlevel 1 (
    echo Distribution audit failed.
    exit /b 1
)

echo Building Windows installer...
"%ISCC_CMD%" "installer\AdventurerGuildAI.iss"
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo Installer build complete: installer\Output\AdventurerGuildAI_Setup.exe
exit /b 0
