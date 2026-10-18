@echo off
rem ===========================================================================
rem  Stop the local Mentor Workbench server (port 8765).
rem  ASCII-only on purpose: cmd.exe parses .cmd with the OEM codepage, so UTF-8
rem  Chinese here breaks line parsing.
rem ===========================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "PORT=8765"
set "FOUND="

echo.
echo   Looking for a process listening on port %PORT% ...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    if not "%%P"=="0" (
        echo   Stopping PID %%P
        taskkill /PID %%P /F >nul 2>&1
        set "FOUND=1"
    )
)

if defined FOUND (
    echo.
    echo   Stopped.
) else (
    echo.
    echo   Nothing was listening on port %PORT% ^(server was not running^).
)
echo.
pause
endlocal