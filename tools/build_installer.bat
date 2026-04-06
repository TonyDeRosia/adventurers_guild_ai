@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

if not exist "dist\AdventurerGuildAI.exe" (
    echo No executable detected in dist\. Building executable first...
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

echo Building Windows installer...
"%ISCC_CMD%" "installer\AdventurerGuildAI.iss"
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo Installer build complete: installer\Output\AdventurerGuildAI_Setup.exe
exit /b 0
