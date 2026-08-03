@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m pip install -r requirements_build.txt
if errorlevel 1 exit /b 1

set "PACKAGE_TEMP=%TEMP%\BibleAI-package-build"
if exist "%PACKAGE_TEMP%" rmdir /s /q "%PACKAGE_TEMP%"
mkdir "%PACKAGE_TEMP%"
python -m PyInstaller --clean --noconfirm --distpath "%PACKAGE_TEMP%\dist" --workpath "%PACKAGE_TEMP%\build" build_exe.spec
if errorlevel 1 exit /b 1
if not exist dist\BibleAI mkdir dist\BibleAI
robocopy "%PACKAGE_TEMP%\dist\BibleAI" "dist\BibleAI" /E /COPY:DAT /R:2 /W:1 >nul
if errorlevel 8 exit /b 1
if not exist dist\BibleAI\logs mkdir dist\BibleAI\logs
if not exist dist\BibleAI\output mkdir dist\BibleAI\output

echo.
echo BibleAI executable created at dist\BibleAI\BibleAI.exe
endlocal
