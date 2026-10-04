@echo off
REM ==========================================================
REM  Double-click to open the Qiuli admin channel
REM ==========================================================
chcp 65001 >nul 2>nul
cd /d "%~dp0"
python "%~dp0qiuli.py" admin
pause
