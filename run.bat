@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo Adventurer's Guild AI - Install + Build Bootstrap
echo ==================================================
echo.
echo This script will:
echo  1) Ask where to install a local copy
echo  2) Copy the app files there
echo  3) Build AdventurerGuildAI.exe in that location
echo  4) Launch the browser-ready launcher
echo.

call :pick_install_folder INSTALL_BASE
if not defined INSTALL_BASE (
    echo [error] No install location was selected.
    goto :error_pause
)

set "TARGET_DIR=%INSTALL_BASE%\AdventurerGuildAI"
echo [setup] Target install directory: "%TARGET_DIR%"

if exist "%TARGET_DIR%" (
    echo.
    set /p OVERWRITE_CHOICE=[setup] "%TARGET_DIR%" already exists. Replace it? [y/N]: 
    if /I not "!OVERWRITE_CHOICE!"=="y" (
        echo [setup] Installation canceled.
        exit /b 0
    )
    echo [setup] Removing previous install folder...
    rmdir /s /q "%TARGET_DIR%"
)

mkdir "%TARGET_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [error] Failed to create "%TARGET_DIR%".
    goto :error_pause
)

echo [setup] Copying project files...
robocopy "%ROOT_DIR%" "%TARGET_DIR%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP ^
    /XD ".git" ".pytest_cache" "__pycache__" "build" "dist" "release\user" "installer\Output"
set "COPY_RC=%errorlevel%"
if %COPY_RC% GEQ 8 (
    echo [error] File copy failed with robocopy exit code %COPY_RC%.
    goto :error_pause
)

echo [setup] Building AdventurerGuildAI.exe in install folder...
pushd "%TARGET_DIR%"
call "tools\build_exe.bat"
set "BUILD_RC=%errorlevel%"
if %BUILD_RC% NEQ 0 (
    popd
    echo [error] Executable build failed with exit code %BUILD_RC%.
    goto :error_pause
)

if exist "dist\AdventurerGuildAI.exe" (
    copy /y "dist\AdventurerGuildAI.exe" "AdventurerGuildAI.exe" >nul
)

echo [setup] Build complete.
echo [setup] Launching browser-ready launcher...
call "launch_browser_window.bat"
set "LAUNCH_RC=%errorlevel%"
popd

if %LAUNCH_RC% NEQ 0 (
    echo [warn] Launcher exited with code %LAUNCH_RC%.
    goto :error_pause
)

exit /b 0

:pick_install_folder
set "%~1="
set "SELECTED_FOLDER="

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms | Out-Null; $dlg = New-Object System.Windows.Forms.FolderBrowserDialog; $dlg.Description = 'Select install location for Adventurer Guild AI'; $dlg.ShowNewFolderButton = $true; if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Write($dlg.SelectedPath) }"`) do (
    set "SELECTED_FOLDER=%%I"
)

if defined SELECTED_FOLDER (
    set "%~1=%SELECTED_FOLDER%"
    goto :eof
)

echo [setup] Folder picker was canceled or unavailable.
set /p MANUAL_FOLDER=Enter install folder path manually (or leave blank to cancel): 
if defined MANUAL_FOLDER set "%~1=%MANUAL_FOLDER%"
goto :eof

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
