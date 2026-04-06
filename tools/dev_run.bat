@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

echo [compat] tools\dev_run.bat is a compatibility wrapper.
echo [compat] Use root run.bat for source launches.
call "%ROOT_DIR%\run.bat" %*
exit /b %errorlevel%
