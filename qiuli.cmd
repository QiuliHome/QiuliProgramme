@echo off
REM Qiuli command wrapper -- lets you run "qiuli" from any directory
REM (works after this folder is added to PATH)
chcp 65001 >nul 2>nul
python "%~dp0qiuli.py" %*
