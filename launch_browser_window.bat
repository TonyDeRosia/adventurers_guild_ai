@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
set "HOST=127.0.0.1"
set "PORT=8000"
set "APP_URL=http://%HOST%:%PORT%"

echo ==================================================
echo Adventurer's Guild AI - Browser Window Launcher
echo ==================================================

if exist "AdventurerGuildAI.exe" (
    echo [launch] Starting AdventurerGuildAI.exe...
    start "Adventurer Guild AI" "AdventurerGuildAI.exe"
    goto :open_browser
)

if exist "dist\AdventurerGuildAI.exe" (
    echo [launch] Starting dist\AdventurerGuildAI.exe...
    start "Adventurer Guild AI" "dist\AdventurerGuildAI.exe"
    goto :open_browser
)

call :detect_python
if "%PYTHON_CMD%"=="" (
    echo [error] Could not find AdventurerGuildAI.exe or Python runtime.
    echo [error] Build the executable first using tools\build_exe.bat.
    goto :error_pause
)

echo [launch] Starting source server with %PYTHON_CMD%...
start "Adventurer Guild AI (source)" cmd /k call %PYTHON_CMD% -u run.py --mode web --host %HOST% --port %PORT%

:open_browser
echo [launch] Waiting for backend health check before opening browser...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='%APP_URL%/health'; $ready=$false; for($i=0;$i -lt 60;$i++){ try { $resp=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1; if ($resp.StatusCode -eq 200) { $ready=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; Start-Process '%APP_URL%'; if(-not $ready){ Write-Host '[launch] Backend not confirmed yet; browser opened anyway.' }"
if errorlevel 1 (
    echo [warn] Automatic browser open failed. Open manually: %APP_URL%
    goto :error_pause
)

echo [launch] Browser launched at %APP_URL%
exit /b 0

:detect_python
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
goto :eof

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
