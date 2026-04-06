@echo off
setlocal
call "%~dp0dev_build_installer.bat" %*
exit /b %errorlevel%
