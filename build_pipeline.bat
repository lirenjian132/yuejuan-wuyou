@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   YueJuanWuYou - PyInstaller Build
echo ============================================
echo.

set "VENV_PYTHON=venv\Scripts\python.exe"
set "VENV_PIP=venv\Scripts\pip.exe"

echo [1/3] Checking PyInstaller...
"%VENV_PIP%" show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    "%VENV_PIP%" install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo PyInstaller install failed! Check network or install manually.
        pause
        exit /b 1
    )
) else (
    echo PyInstaller already installed.
)

echo.
echo [2/3] Building pipeline_cli.py -^> pipeline.exe...
echo This may take 5-15 minutes, please wait...
echo.

"%VENV_PYTHON%" -m PyInstaller ^
    --onefile ^
    --name pipeline ^
    --distpath "electron-app\resources" ^
    --workpath "build\pyinstaller" ^
    --specpath "build" ^
    --add-data "confusion_dict.py;." ^
    --hidden-import scan_and_grade ^
    --hidden-import database ^
    --hidden-import report_generator ^
    --hidden-import export_tool ^
    --hidden-import generate_sheet ^
    --hidden-import fill_simulator ^
    --hidden-import template_matcher ^
    --hidden-import run_pipeline ^
    --hidden-import jieba ^
    --hidden-import cv2 ^
    --hidden-import numpy ^
    --hidden-import fitz ^
    --hidden-import rapidocr_onnxruntime ^
    --hidden-import weasyprint ^
    --hidden-import reportlab ^
    --hidden-import qrcode ^
    --hidden-import fonttools ^
    --hidden-import difflib ^
    --clean ^
    pipeline_cli.py

if %errorlevel% neq 0 (
    echo.
    echo Build FAILED! Check error messages above.
    pause
    exit /b 1
)

echo.
echo [3/3] Verifying build...
if exist "electron-app\resources\pipeline.exe" (
    echo.
    echo ============================================
    echo   BUILD SUCCESS!
    echo   Output: electron-app\resources\pipeline.exe
    echo ============================================
) else (
    echo Output file not found, build may have failed.
)

pause
