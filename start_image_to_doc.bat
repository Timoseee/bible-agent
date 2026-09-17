@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
python process_images.py
echo.
pause
