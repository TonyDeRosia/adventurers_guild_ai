@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "LOG_DIR=%ROOT_DIR%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LAUNCH_LOG=%LOG_DIR%\build_launcher_bootstrap.log"

call :log ============================================================
call :log [%date% %time%] Build_AdventurersGuildAI.bat invoked

set "GUI_SCRIPT=%ROOT_DIR%Build_AdventurersGuildAI.py"
if not exist "%GUI_SCRIPT%" (
    call :log ERROR: GUI launcher script not found.
    call :log Expected path: "%GUI_SCRIPT%"
    echo.
    echo ERROR: GUI launcher script not found:
    echo   "%GUI_SCRIPT%"
    echo.
    pause
    exit /b 1
)

set "PYTHON_EXE="
set "PYTHON_ARGS="
where pyw >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_EXE=pyw"
    set "PYTHON_ARGS=-3"
)
if not defined PYTHON_EXE (
    where pythonw >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=pythonw"
        set "PYTHON_ARGS="
    )
)
if not defined PYTHON_EXE (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=python"
        set "PYTHON_ARGS="
    )
)

if not defined PYTHON_EXE (
    call :log ERROR: Python not found (tried pyw/pythonw/py/python).
    echo.
    echo ERROR: Python 3 is required to open the GUI build launcher.
    echo Install Python from: https://www.python.org/downloads/windows/
    echo.
    pause
    exit /b 1
)

set "LAUNCH_CMD=%PYTHON_EXE% %PYTHON_ARGS% \"%GUI_SCRIPT%\""
call :log Detected python command: %PYTHON_EXE% %PYTHON_ARGS%
call :log GUI script path: "%GUI_SCRIPT%"
call :log Launch command: %LAUNCH_CMD%

start "Adventurers Guild AI Build Launcher" /D "%ROOT_DIR%" cmd /c ""%PYTHON_EXE%" %PYTHON_ARGS% "%GUI_SCRIPT%" >> "%LAUNCH_LOG%" 2>&1"
if errorlevel 1 (
    call :log ERROR: GUI launch command failed to start. errorlevel=%errorlevel%
    echo.
    echo ERROR: Failed to launch GUI build launcher.
    echo Command attempted:
    echo   %LAUNCH_CMD%
    echo.
    echo See log for details: "%LAUNCH_LOG%"
    echo.
    pause
    exit /b %errorlevel%
)

call :log SUCCESS: GUI launched successfully.
echo GUI launched successfully.
exit /b 0

:log
echo %~1
>>"%LAUNCH_LOG%" echo %~1
exit /b 0
