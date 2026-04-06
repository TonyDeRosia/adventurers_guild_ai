@echo off
setlocal EnableExtensions

set "SOURCE_DIR=%~dp0"
if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"

cd /d "%SOURCE_DIR%"

echo ==================================================
echo Adventurer's Guild AI Bootstrap
echo ==================================================
echo This script copies the project, builds AdventurerGuildAI.exe,
echo then launches the built executable.
echo.

set "DEFAULT_INSTALL=%USERPROFILE%\AdventurerGuildAI"
set /p "INSTALL_DIR=Enter install folder [%DEFAULT_INSTALL%]: "
if "%INSTALL_DIR%"=="" set "INSTALL_DIR=%DEFAULT_INSTALL%"

if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"
if /I "%INSTALL_DIR%"=="%SOURCE_DIR%" (
    echo [error] Install folder must be different from the source folder.
    goto :error_pause
)

echo [bootstrap] Creating install folder: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if errorlevel 1 (
    echo [error] Could not create install folder.
    goto :error_pause
)

echo [bootstrap] Copying project files...
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /MIR /XD ".git" ".venv" "__pycache__" ".pytest_cache" "build" "dist" "installer\Output" /XF ".deps_installed"
set "ROBOCOPY_RC=%ERRORLEVEL%"
if %ROBOCOPY_RC% GEQ 8 (
    echo [error] File copy failed (robocopy exit code %ROBOCOPY_RC%).
    goto :error_pause
)

echo [bootstrap] Building AdventurerGuildAI.exe in install folder...
cd /d "%INSTALL_DIR%"
call "tools\build_exe.bat"
if errorlevel 1 (
    echo [error] Executable build failed.
    goto :error_pause
)

if not exist "dist\AdventurerGuildAI.exe" (
    echo [error] Build did not produce dist\AdventurerGuildAI.exe.
    goto :error_pause
)

echo [bootstrap] Launching dist\AdventurerGuildAI.exe ...
start "AdventurerGuildAI" "%INSTALL_DIR%\dist\AdventurerGuildAI.exe"
if errorlevel 1 (
    echo [error] Failed to launch executable.
    goto :error_pause
)

echo [bootstrap] Done.
exit /b 0

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
