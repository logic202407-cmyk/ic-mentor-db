@echo off
rem ===========================================================================
rem  Mentor Workbench - one-click launcher
rem  Starts the local server on 127.0.0.1:8765 and opens the browser.
rem  All data stays on this machine; nothing is uploaded anywhere.
rem
rem  NOTE: this file is intentionally ASCII-only. cmd.exe parses .cmd files with
rem  the OEM codepage, so saving UTF-8 Chinese here breaks line parsing (observed:
rem  lines got split and cmd tried to run fragments like "on.exe").
rem ===========================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8765"
set "PY=.venv\Scripts\python.exe"
set "URL=http://%HOST%:%PORT%/"

echo.
echo   ============================================
echo    Mentor Workbench  /  Mentor Investigation Desk
echo   ============================================
echo.

rem ---- 1. Python environment ---------------------------------------------
if not exist "%PY%" (
    echo   [1/3] No .venv found. Creating it now ^(first run, needs internet^)...
    where py >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   [X] Python launcher "py" not found.
        echo       Install Python 3.11+ with "Add python.exe to PATH", then run again.
        echo.
        pause
        exit /b 1
    )
    py -3 -m venv .venv
    if errorlevel 1 (
        echo   [X] Failed to create the virtual environment.
        pause
        exit /b 1
    )
    "%PY%" -m pip install --upgrade pip
    "%PY%" -m pip install -r workbench\requirements.txt
    if errorlevel 1 (
        echo   [X] Dependency install failed. Check the network and retry.
        pause
        exit /b 1
    )
    echo   [1/3] Dependencies installed.
)

rem ---- 2. Already running? -----------------------------------------------
set "RUNNING="
for /f "tokens=*" %%L in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do set "RUNNING=1"

if defined RUNNING (
    echo   [2/3] Server already running on port %PORT%.
    start "" "%URL%"
    echo.
    echo   URL: %URL%
    echo   To stop it, run stop.cmd
    echo.
    pause
    exit /b 0
)

rem ---- 3. Start the server ------------------------------------------------
echo   [2/3] Starting the local server...
start "Mentor Workbench Server" /min "%PY%" -m uvicorn workbench.app:app --host %HOST% --port %PORT%

set "PROBE=import sys,urllib.request;sys.exit(0 if urllib.request.urlopen('http://%HOST%:%PORT%/api/health',timeout=2).status==200 else 1)"
set /a TRIES=0

:waitloop
set /a TRIES+=1
"%PY%" -c "%PROBE%" >nul 2>&1
if errorlevel 1 (
    if %TRIES% GEQ 40 goto :timeout
    ping -n 2 127.0.0.1 >nul 2>&1
    goto :waitloop
)
goto :ready

:timeout
echo.
echo   [X] Server did not become ready within 20 seconds.
echo       Check the "Mentor Workbench Server" window for the error.
echo       Common causes: port %PORT% already in use, or missing dependencies.
echo.
echo       Manual diagnosis:
echo         .venv\Scripts\python.exe -m uvicorn workbench.app:app --host %HOST% --port %PORT%
echo.
pause
exit /b 1

:ready
echo   [3/3] Ready.
echo.
echo   ============================================
echo    URL      %URL%
echo    Home     find a mentor / browse by discipline
echo    Classic  %URL%classic
echo   ============================================
echo.
echo   Local data only. AI output needs human review.
echo   Stop: close the "Mentor Workbench Server" window, or run stop.cmd
echo.
start "" "%URL%"
echo   Browser opened. The server runs in its own "Mentor Workbench Server"
echo   window; closing THAT window (or running stop.cmd) stops the service.
echo   This launcher window can be closed at any time.
echo.
pause
endlocal
