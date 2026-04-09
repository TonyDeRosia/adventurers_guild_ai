@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%" || goto :fatal_startup

title Adventurers Guild AI Build Launcher

set "SCRIPT_EXIT_CODE=1"
set "FAILURE_REASON=Build launcher did not complete."
set "BUILD_MODE="
set "EXE_BUILD_STATUS=not_run"
set "INSTALLER_BUILD_STATUS=not_run"
set "FINAL_INSTALLER_PATH="
set "COPIED_INSTALLER_PATH="
set "SELECTED_OUTPUT_DIR="
set "PYTHON_CMD="
set "POWERSHELL_CMD="
set "ISCC_PATH="
set "LOG_FILE=%ROOT_DIR%build_launcher.log"

break > "%LOG_FILE%"
call :log "================================================================"
call :log "Adventurers Guild AI - Windows Build Launcher"
call :log "Started: %DATE% %TIME%"
call :log "Repo root: %ROOT_DIR%"
call :log "Log file: %LOG_FILE%"
call :log "================================================================"

call :stage "Resolving Python"
call :resolve_python
if errorlevel 1 goto :finish

call :stage "Selecting output folder"
call :pick_output_dir
if errorlevel 1 goto :finish

call :stage "Verifying packaging inputs"
call :verify_packaging_inputs
if errorlevel 1 goto :finish

call :stage "Choosing build mode"
call :choose_build_mode
if errorlevel 1 goto :finish

call :stage "Verifying tools"
call :verify_tools
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

call :fail "Unknown build mode \"%BUILD_MODE%\"."
goto :finish

:post_build
if "%INSTALLER_BUILD_STATUS%"=="success" (
    call :copy_installer_to_output
    if errorlevel 1 goto :finish
) else if /i "%BUILD_MODE%"=="EXE" (
    call :log "[INFO] Installer build was intentionally skipped (EXE-only mode)."
) else if "%INSTALLER_BUILD_STATUS%"=="failed" (
    call :log "[WARN] Installer build failed. No installer artifact was copied."
) else (
    call :log "[INFO] Installer was not built."
)

if "%SCRIPT_EXIT_CODE%"=="1" if "%EXE_BUILD_STATUS%"=="success" if /i "%BUILD_MODE%"=="EXE" (
    set "SCRIPT_EXIT_CODE=0"
    set "FAILURE_REASON="
)
if "%SCRIPT_EXIT_CODE%"=="1" if "%INSTALLER_BUILD_STATUS%"=="success" (
    set "SCRIPT_EXIT_CODE=0"
    set "FAILURE_REASON="
)

goto :finish

:resolve_python
set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    call :log "[INFO] Found launcher command: py"
    py -3 -c "import sys;raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        call :log "[OK] Python resolved via: py -3"
        exit /b 0
    ) else (
        call :log "[WARN] py found, but \"py -3\" did not execute successfully."
    )
) else (
    call :log "[INFO] Command not found in PATH: py"
)

where python >nul 2>&1
if not errorlevel 1 (
    call :log "[INFO] Found launcher command: python"
    python -c "import sys;raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        call :log "[OK] Python resolved via: python"
        exit /b 0
    ) else (
        call :log "[WARN] python found, but it does not appear to be usable Python 3."
    )
) else (
    call :log "[INFO] Command not found in PATH: python"
)

call :fail "Python 3 was not found. Expected a working \"py -3\" or \"python\" in PATH."
exit /b 1

:pick_output_dir
set "SELECTED_OUTPUT_DIR="
set "PICKER_SCRIPT=%TEMP%\agai_pick_folder_%RANDOM%_%RANDOM%.ps1"
set "PICKER_OUTPUT=%TEMP%\agai_pick_folder_%RANDOM%_%RANDOM%.out"
set "PICKER_ERR=%TEMP%\agai_pick_folder_%RANDOM%_%RANDOM%.err"
set "PICKER_TIMEOUT_SEC=45"
set "PICKER_RC="
set "PICKER_FALLBACK_REASON="
set "PICKER_ERR_LINE="

where powershell >nul 2>&1
if not errorlevel 1 (
    set "POWERSHELL_CMD=powershell"
    call :log "[INFO] powershell found in PATH: %POWERSHELL_CMD%"
    call :log "[INFO] Attempting folder picker using powershell."
    call :log "[INFO] Picker script: %PICKER_SCRIPT%"
    call :log "[INFO] Picker output file: %PICKER_OUTPUT%"
    call :log "[INFO] Picker error file: %PICKER_ERR%"

    > "%PICKER_SCRIPT%" echo Add-Type -AssemblyName System.Windows.Forms ^> $null
    >> "%PICKER_SCRIPT%" echo $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    >> "%PICKER_SCRIPT%" echo $dialog.Description = 'Choose folder for final Adventurers Guild AI installer artifact'
    >> "%PICKER_SCRIPT%" echo $dialog.ShowNewFolderButton = $true
    >> "%PICKER_SCRIPT%" echo if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Write($dialog.SelectedPath) }

    "%POWERSHELL_CMD%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$scriptPath='%PICKER_SCRIPT%'; $outPath='%PICKER_OUTPUT%'; $errPath='%PICKER_ERR%'; $timeoutMs=%PICKER_TIMEOUT_SEC%*1000; " ^
    "$p = Start-Process -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-STA','-File',$scriptPath) -PassThru -WindowStyle Normal -RedirectStandardOutput $outPath -RedirectStandardError $errPath; " ^
    "if ($p.WaitForExit($timeoutMs)) { exit $p.ExitCode } else { try { $p.Kill() } catch {}; exit 124 }"
    set "PICKER_RC=%ERRORLEVEL%"
    call :log "[INFO] Picker command exit code: %PICKER_RC%"

    if exist "%PICKER_OUTPUT%" (
        call :log "[INFO] Picker output file created: yes"
        set /p "SELECTED_OUTPUT_DIR=" < "%PICKER_OUTPUT%"
        if defined SELECTED_OUTPUT_DIR (
            call :log "[INFO] Selected path read: yes"
        ) else (
            call :log "[INFO] Selected path read: no (file empty or unreadable)"
        )
    ) else (
        call :log "[INFO] Picker output file created: no"
        call :log "[INFO] Selected path read: no"
    )

    if "%PICKER_RC%"=="0" (
        if defined SELECTED_OUTPUT_DIR (
            call :log "[OK] Folder picker returned a path."
        ) else (
            set "PICKER_FALLBACK_REASON=Folder picker returned no folder (cancelled/closed/empty)."
        )
    ) else if "%PICKER_RC%"=="124" (
        set "PICKER_FALLBACK_REASON=Folder picker timed out after %PICKER_TIMEOUT_SEC%s."
    ) else (
        set "PICKER_FALLBACK_REASON=Folder picker failed (powershell exit code %PICKER_RC%)."
    )

    if defined PICKER_FALLBACK_REASON (
        if exist "%PICKER_ERR%" (
            set /p "PICKER_ERR_LINE=" < "%PICKER_ERR%"
            if defined PICKER_ERR_LINE call :log "[WARN] Picker error (first line): %PICKER_ERR_LINE%"
        )
        call :log "[WARN] %PICKER_FALLBACK_REASON%"
        call :log "[WARN] Falling back to manual output folder entry."
    )
) else (
    call :log "[WARN] powershell not found in PATH."
    call :log "[WARN] Falling back to manual output folder entry."
)

if exist "%PICKER_SCRIPT%" del /q "%PICKER_SCRIPT%" >nul 2>&1
if exist "%PICKER_OUTPUT%" del /q "%PICKER_OUTPUT%" >nul 2>&1
if exist "%PICKER_ERR%" del /q "%PICKER_ERR%" >nul 2>&1

if not defined SELECTED_OUTPUT_DIR (
    set /p "SELECTED_OUTPUT_DIR=Enter output folder path (leave blank to cancel): "
)

if not defined SELECTED_OUTPUT_DIR (
    call :fail "No output folder was selected."
    exit /b 1
)

if not exist "%SELECTED_OUTPUT_DIR%" (
    mkdir "%SELECTED_OUTPUT_DIR%" >nul 2>&1
    if errorlevel 1 (
        call :fail "Could not create output folder: %SELECTED_OUTPUT_DIR%"
        exit /b 1
    )
)

for %%I in ("%SELECTED_OUTPUT_DIR%") do set "SELECTED_OUTPUT_DIR=%%~fI"
call :log "[OK] Output folder: %SELECTED_OUTPUT_DIR%"
exit /b 0

:verify_tools
where cmd >nul 2>&1
if errorlevel 1 (
    call :fail "cmd.exe was not found in PATH."
    exit /b 1
)
call :log "[OK] cmd.exe available."

where powershell >nul 2>&1
if errorlevel 1 (
    call :log "[WARN] powershell.exe was not found in PATH (folder picker fallback will be manual only)."
) else (
    set "POWERSHELL_CMD=powershell"
    call :log "[OK] powershell.exe available."
)

if /i "%BUILD_MODE%"=="EXE" (
    call :log "[INFO] Skipping Inno Setup verification because EXE-only mode was selected."
    call :log "[OK] Tool verification complete."
    exit /b 0
)

if /i not "%BUILD_MODE%"=="INSTALLER" if /i not "%BUILD_MODE%"=="ALL" (
    call :fail "Internal launcher error: build mode must be chosen before installer tool verification."
    exit /b 1
)

set "ISCC_CANDIDATE_1=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
set "ISCC_CANDIDATE_2=%ProgramFiles%\Inno Setup 6\ISCC.exe"
call :log "[INFO] Checking Inno Setup path: %ISCC_CANDIDATE_1%"
if exist "%ISCC_CANDIDATE_1%" set "ISCC_PATH=%ISCC_CANDIDATE_1%"

if not defined ISCC_PATH (
    call :log "[INFO] Checking Inno Setup path: %ISCC_CANDIDATE_2%"
    if exist "%ISCC_CANDIDATE_2%" set "ISCC_PATH=%ISCC_CANDIDATE_2%"
)

if not defined ISCC_PATH (
    call :log "[INFO] Checking Inno Setup via PATH command: iscc"
    where iscc >nul 2>&1
    if not errorlevel 1 set "ISCC_PATH=iscc"
)

if not defined ISCC_PATH (
    call :fail "Inno Setup compiler (ISCC.exe) not found. Checked: %ISCC_CANDIDATE_1% | %ISCC_CANDIDATE_2% | PATH:iscc"
    exit /b 1
)

call :log "[OK] Inno Setup compiler: %ISCC_PATH%"
call :log "[OK] Tool verification complete."
exit /b 0

:verify_packaging_inputs
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

call :log "[OK] Packaging input verification complete."
exit /b 0

:require_path
set "REQ_PATH=%~1"
set "REQ_KIND=%~2"
if /i "%REQ_KIND%"=="file" (
    if not exist "%REQ_PATH%" (
        call :fail "Required file is missing: %REQ_PATH%"
        exit /b 1
    )
) else if /i "%REQ_KIND%"=="dir" (
    if not exist "%REQ_PATH%\" (
        call :fail "Required folder is missing: %REQ_PATH%"
        exit /b 1
    )
) else (
    call :fail "Internal launcher error: unknown path type %REQ_KIND% for %REQ_PATH%"
    exit /b 1
)

call :log "[OK] Found %REQ_PATH%"
exit /b 0

:choose_build_mode
call :log "  [1] Build EXE only"
call :log "  [2] Build installer only"
call :log "  [3] Build everything (EXE then installer)"
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
    call :fail "Invalid selection: %BUILD_SELECTION%"
    exit /b 1
)

call :log "[OK] Build mode: %BUILD_MODE%"
exit /b 0

:build_exe
call :stage "Build EXE"
call "tools\build_exe.bat"
if errorlevel 1 (
    set "EXE_BUILD_STATUS=failed"
    call :fail "EXE build failed."
    exit /b 1
)
if not exist "dist\AdventurerGuildAI\AdventurerGuildAI.exe" (
    set "EXE_BUILD_STATUS=failed"
    call :fail "EXE build reported success but output is missing: dist\AdventurerGuildAI\AdventurerGuildAI.exe"
    exit /b 1
)
set "EXE_BUILD_STATUS=success"
call :log "[OK] EXE build complete."
exit /b 0

:build_installer
call :stage "Build Installer"
call "tools\build_installer.bat"
if errorlevel 1 (
    set "INSTALLER_BUILD_STATUS=failed"
    call :fail "Installer build failed."
    exit /b 1
)
if not exist "installer\Output\AdventurerGuildAI_Setup.exe" (
    set "INSTALLER_BUILD_STATUS=failed"
    call :fail "Installer build reported success but output is missing: installer\Output\AdventurerGuildAI_Setup.exe"
    exit /b 1
)
set "INSTALLER_BUILD_STATUS=success"
set "FINAL_INSTALLER_PATH=%ROOT_DIR%installer\Output\AdventurerGuildAI_Setup.exe"
call :log "[OK] Installer build complete."
exit /b 0

:copy_installer_to_output
set "COPIED_INSTALLER_PATH=%SELECTED_OUTPUT_DIR%\AdventurerGuildAI_Setup.exe"
copy /y "installer\Output\AdventurerGuildAI_Setup.exe" "%COPIED_INSTALLER_PATH%" >nul
if errorlevel 1 (
    call :fail "Installer was built, but copy to output folder failed. Source=installer\Output\AdventurerGuildAI_Setup.exe Destination=%COPIED_INSTALLER_PATH%"
    exit /b 1
)
call :log "[OK] Copied installer to: %COPIED_INSTALLER_PATH%"
exit /b 0

:finish
call :log_blank
call :log "================================================================"
if "%INSTALLER_BUILD_STATUS%"=="success" (
    call :log "Final installer artifact:"
    if defined COPIED_INSTALLER_PATH (
        call :log "  %COPIED_INSTALLER_PATH%"
    ) else (
        call :log "  %ROOT_DIR%installer\Output\AdventurerGuildAI_Setup.exe"
    )
) else if /i "%BUILD_MODE%"=="EXE" (
    call :log "Installer artifact: not generated (EXE-only mode)."
) else (
    call :log "Installer artifact: not available due to skip/failure."
)

if "%SCRIPT_EXIT_CODE%"=="" set "SCRIPT_EXIT_CODE=1"
if "%SCRIPT_EXIT_CODE%"=="0" (
    call :log "Status: SUCCESS"
) else (
    call :log "Status: FAILED (exit code %SCRIPT_EXIT_CODE%)"
    if defined FAILURE_REASON call :log "Reason: %FAILURE_REASON%"
)
call :log "Finished: %DATE% %TIME%"
call :log "================================================================"
call :log_blank
pause
exit /b %SCRIPT_EXIT_CODE%

rem Guard rail: do not fall through into helper labels.
goto :eof

:stage
call :log_blank
call :log "---------------- %~1 ----------------"
exit /b 0

:fail
set "SCRIPT_EXIT_CODE=1"
set "FAILURE_REASON=%~1"
call :log "[ERROR] %~1"
exit /b 1

:log
set "LOG_LINE=%~1"
if defined LOG_LINE (
    echo %LOG_LINE%
    >> "%LOG_FILE%" echo %LOG_LINE%
) else (
    echo(
    >> "%LOG_FILE%" echo(
)
exit /b 0

:log_blank
echo(
>> "%LOG_FILE%" echo(
exit /b 0

:fatal_startup
echo [ERROR] Failed to change directory to script root.
echo [ERROR] Script path: %~dp0
echo.
pause
exit /b 1
