@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo [compat] dev_run.bat is kept for compatibility.
echo [compat] Use run.bat as the primary source launcher.
call "%ROOT_DIR%run.bat" %*
exit /b %errorlevel%
