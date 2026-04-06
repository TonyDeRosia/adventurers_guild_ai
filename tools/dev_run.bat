@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

echo [info] tools\dev_run.bat is a compatibility wrapper.
echo [info] Use root dev_run.bat for source launches.
call "%ROOT_DIR%\dev_run.bat" %*
exit /b %errorlevel%
