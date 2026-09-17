@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo 正在安装图片转 Word 所需组件，请稍候...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo 安装失败，请检查网络和 Python 环境。
) else (
  echo.
  echo 安装完成。以后只需双击 start_image_to_doc.bat。
)
pause
