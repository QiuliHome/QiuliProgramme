@echo off
REM ==========================================================
REM  Qiuli launcher (Windows)
REM   Double-click      -> start the interactive REPL
REM   Drag a .ql onto it -> run that script
REM ==========================================================
chcp 65001 >nul 2>nul
setlocal
set "HERE=%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python "%HERE%qiuli.py" %*
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%HERE%qiuli.py" %*
    goto :end
)

echo.
echo   Python not found.
echo   Please install Python 3.8+ from https://www.python.org/downloads/
echo   and remember to check "Add Python to PATH".
echo.

:end
endlocal

