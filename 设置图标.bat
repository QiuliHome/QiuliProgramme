@echo off
REM Double-click to apply the QL icon to Qiuli shortcuts
chcp 65001 >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0…Ë÷√Õº±Í.ps1"
if errorlevel 1 pause
