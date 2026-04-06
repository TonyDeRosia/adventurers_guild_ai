@echo off
setlocal

set "ROOT_DIR=%~dp0"
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
    echo Python 3.10+ is required to build Adventurer Guild AI.
    exit /b 1
)

if not exist "dist\AdventurerGuildAI.exe" (
    echo No existing executable found. Building executable first...
    call build_exe.bat
    if errorlevel 1 (
        echo Executable build failed.
        exit /b 1
    )
)

set "ISCC_CMD="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_CMD=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_CMD=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC_CMD%"=="" (
    where iscc >nul 2>&1
    if %errorlevel%==0 (
        set "ISCC_CMD=iscc"
    )
)

if "%ISCC_CMD%"=="" (
    echo Inno Setup 6 is required. Install from https://jrsoftware.org/isinfo.php
    exit /b 1
)

echo Building installer with Inno Setup...
"%ISCC_CMD%" "installer\AdventurerGuildAI.iss"
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo.
echo Installer build complete. Check the installer\Output folder.
exit /b 0
