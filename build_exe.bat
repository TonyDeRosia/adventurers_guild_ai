@echo off
setlocal
call "%~dp0dev_build_exe.bat" %*
exit /b %errorlevel%
