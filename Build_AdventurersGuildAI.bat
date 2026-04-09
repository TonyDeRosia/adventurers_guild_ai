@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ================================================================
echo   Adventurers Guild AI - Windows Build Launcher
echo ================================================================
echo.

title Adventurers Guild AI Build Launcher

call :resolve_python
if errorlevel 1 goto :finish

call :pick_output_dir
if errorlevel 1 goto :finish

call :verify_tools
if errorlevel 1 goto :finish

call :verify_packaging_inputs
if errorlevel 1 goto :finish

call :choose_build_mode
if errorlevel 1 goto :finish

if /i "%BUILD_MODE%"=="EXE" (
    call :build_exe
    goto :post_build
)

if /i "%BUILD_MODE%"=="INSTALLER" (
    call :build_installer
    goto :post_build
)

if /i "%BUILD_MODE%"=="ALL" (
    call :build_exe
    if errorlevel 1 goto :post_build
    call :build_installer
    goto :post_build
)

echo [ERROR] Unknown build mode "%BUILD_MODE%".
set "SCRIPT_EXIT_CODE=1"
goto :finish

:post_build
if "%INSTALLER_BUILD_STATUS%"=="success" (
    call :copy_installer_to_output
) else if /i "%BUILD_MODE%"=="EXE" (
    echo.
    echo [INFO] Installer build was intentionally skipped because EXE-only mode was selected.
) else if "%INSTALLER_BUILD_STATUS%"=="failed" (
    echo.
    echo [WARN] Installer build failed. No installer artifact was copied.
) else (
    echo.
    echo [INFO] Installer was not built.
)

goto :finish

:resolve_python
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python 3.10+ was not found (expected "py -3" or "python" in PATH).
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

echo [OK] Python command: %PYTHON_CMD%
exit /b 0

:pick_output_dir
set "SELECTED_OUTPUT_DIR="
echo.
echo Select where final build artifacts should be copied.
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms > $null; $dialog = New-Object System.Windows.Forms.FolderBrowserDialog; $dialog.Description = 'Choose folder for final Adventurers Guild AI installer artifact'; $dialog.ShowNewFolderButton = $true; if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Write($dialog.SelectedPath) }"`) do set "SELECTED_OUTPUT_DIR=%%I"

if not defined SELECTED_OUTPUT_DIR (
    echo [WARN] Folder picker was canceled or unavailable.
    set /p "SELECTED_OUTPUT_DIR=Enter output folder path manually (or leave blank to cancel): "
)

if not defined SELECTED_OUTPUT_DIR (
    echo [ERROR] No output folder selected.
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

if not exist "%SELECTED_OUTPUT_DIR%" (
    mkdir "%SELECTED_OUTPUT_DIR%" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not create output folder: %SELECTED_OUTPUT_DIR%
        set "SCRIPT_EXIT_CODE=1"
        exit /b 1
    )
)

for %%I in ("%SELECTED_OUTPUT_DIR%") do set "SELECTED_OUTPUT_DIR=%%~fI"
echo [OK] Output folder: %SELECTED_OUTPUT_DIR%
exit /b 0

:verify_tools
echo.
echo ---------------- Tool Verification ----------------
where cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cmd.exe was not found in PATH.
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

where powershell >nul 2>&1
if errorlevel 1 (
    echo [ERROR] powershell.exe was not found in PATH.
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

set "ISCC_PATH="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    where iscc >nul 2>&1
    if not errorlevel 1 set "ISCC_PATH=iscc"
)

if not defined ISCC_PATH (
    echo [ERROR] Inno Setup 6 compiler not found (ISCC.exe). Install from https://jrsoftware.org/isinfo.php
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

echo [OK] Inno Setup compiler: %ISCC_PATH%
echo [OK] Tool verification complete.
exit /b 0

:verify_packaging_inputs
echo.
echo ------------- Packaging Input Verification -------------
call :require_path "tools\build_exe.bat" "file"
if errorlevel 1 exit /b 1
call :require_path "tools\build_installer.bat" "file"
if errorlevel 1 exit /b 1
call :require_path "installer\AdventurerGuildAI.iss" "file"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\AdventurerGuildAI.spec" "file"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\runtime_bundle" "dir"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\runtime_bundle\comfyui\README.txt" "file"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\runtime_bundle\workflows\scene_image.json" "file"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\runtime_bundle\THIRD_PARTY_NOTICES.txt" "file"
if errorlevel 1 exit /b 1
call :require_path "packaging\windows\runtime_bundle\licenses\ComfyUI-LICENSE-MIT.txt" "file"
if errorlevel 1 exit /b 1

echo [OK] Packaging input verification complete.
exit /b 0

:require_path
set "REQ_PATH=%~1"
set "REQ_KIND=%~2"
if /i "%REQ_KIND%"=="file" (
    if not exist "%REQ_PATH%" (
        echo [ERROR] Required file is missing: %REQ_PATH%
        set "SCRIPT_EXIT_CODE=1"
        exit /b 1
    )
) else if /i "%REQ_KIND%"=="dir" (
    if not exist "%REQ_PATH%\" (
        echo [ERROR] Required folder is missing: %REQ_PATH%
        set "SCRIPT_EXIT_CODE=1"
        exit /b 1
    )
) else (
    echo [ERROR] Internal launcher error: unknown path type "%REQ_KIND%" for %REQ_PATH%
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

echo [OK] Found %REQ_PATH%
exit /b 0

:choose_build_mode
echo.
echo ---------------- Build Selection ----------------
echo   [1] Build EXE only
echo   [2] Build installer only
echo   [3] Build everything (EXE then installer)
set "BUILD_SELECTION="
set /p "BUILD_SELECTION=Choose option 1, 2, or 3 (default 3): "
if "%BUILD_SELECTION%"=="" set "BUILD_SELECTION=3"

if "%BUILD_SELECTION%"=="1" (
    set "BUILD_MODE=EXE"
) else if "%BUILD_SELECTION%"=="2" (
    set "BUILD_MODE=INSTALLER"
) else if "%BUILD_SELECTION%"=="3" (
    set "BUILD_MODE=ALL"
) else (
    echo [ERROR] Invalid selection "%BUILD_SELECTION%".
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)

echo [OK] Build mode: %BUILD_MODE%
exit /b 0

:build_exe
echo.
echo ==================== STEP: Build EXE ====================
call "tools\build_exe.bat"
if errorlevel 1 (
    echo [ERROR] EXE build failed.
    set "EXE_BUILD_STATUS=failed"
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)
if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    echo [ERROR] EXE build reported success but output is missing: dist\AdventurerGuildAI\AdventurerGuildAI.exe
    set "EXE_BUILD_STATUS=failed"
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)
set "EXE_BUILD_STATUS=success"
echo [OK] EXE build complete.
exit /b 0

:build_installer
echo.
echo ================= STEP: Build Installer =================
call "tools\build_installer.bat"
if errorlevel 1 (
    echo [ERROR] Installer build failed.
    set "INSTALLER_BUILD_STATUS=failed"
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)
if not exist "installer\Output\AdventurerGuildAI_Setup.exe" (
    echo [ERROR] Installer build reported success but output is missing: installer\Output\AdventurerGuildAI_Setup.exe
    set "INSTALLER_BUILD_STATUS=failed"
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)
set "INSTALLER_BUILD_STATUS=success"
set "FINAL_INSTALLER_PATH=%ROOT_DIR%installer\Output\AdventurerGuildAI_Setup.exe"
echo [OK] Installer build complete.
exit /b 0

:copy_installer_to_output
set "COPIED_INSTALLER_PATH=%SELECTED_OUTPUT_DIR%\AdventurerGuildAI_Setup.exe"
copy /y "installer\Output\AdventurerGuildAI_Setup.exe" "%COPIED_INSTALLER_PATH%" >nul
if errorlevel 1 (
    echo [ERROR] Installer was built, but copy to output folder failed.
    echo [ERROR] Source: installer\Output\AdventurerGuildAI_Setup.exe
    echo [ERROR] Destination: %COPIED_INSTALLER_PATH%
    set "SCRIPT_EXIT_CODE=1"
    exit /b 1
)
echo [OK] Copied installer to: %COPIED_INSTALLER_PATH%
exit /b 0

:finish
echo.
echo ================================================================
if "%INSTALLER_BUILD_STATUS%"=="success" (
    echo Final installer artifact:
    if defined COPIED_INSTALLER_PATH (
        echo   %COPIED_INSTALLER_PATH%
    ) else (
        echo   %ROOT_DIR%installer\Output\AdventurerGuildAI_Setup.exe
    )
) else if /i "%BUILD_MODE%"=="EXE" (
    echo Installer artifact: not generated (EXE-only mode).
) else (
    echo Installer artifact: not available due to skip/failure.
)

if "%SCRIPT_EXIT_CODE%"=="" set "SCRIPT_EXIT_CODE=0"
if "%SCRIPT_EXIT_CODE%"=="0" (
    echo Status: SUCCESS
) else (
    echo Status: FAILED (exit code %SCRIPT_EXIT_CODE%)
)
echo ================================================================
echo.
pause
exit /b %SCRIPT_EXIT_CODE%
