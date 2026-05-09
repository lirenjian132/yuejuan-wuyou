# 阅卷无忧 - PyInstaller Build Script
# Right-click -> Run with PowerShell

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$host.ui.RawUI.WindowTitle = "YueJuanWuYou Build"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  YueJuanWuYou - PyInstaller Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Working dir: $PSScriptRoot" -ForegroundColor Gray
Write-Host ""

# Diagnostic: check venv
$venvPython = "venv_win\Scripts\python.exe"
$venvPip = "venv_win\Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv not found at $venvPython" -ForegroundColor Red
    Write-Host "Please make sure the Python virtual environment exists." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "venv Python: OK" -ForegroundColor Green

# Check Python version
Write-Host "Python version:" -ForegroundColor Gray
& $venvPython --version
Write-Host ""

# Step 1: Check/Install PyInstaller
Write-Host "[1/3] Checking PyInstaller..." -ForegroundColor Yellow
$check = & $venvPip show pyinstaller 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller from Tsinghua mirror..." -ForegroundColor Yellow
    & $venvPip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Mirror failed, trying default..." -ForegroundColor Yellow
        & $venvPip install pyinstaller 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to install PyInstaller." -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
    }
}
Write-Host "PyInstaller: OK" -ForegroundColor Green
Write-Host ""

# Step 2: Build
Write-Host "[2/3] Building pipeline.exe..." -ForegroundColor Yellow
Write-Host "This takes 5-15 minutes. Please wait..." -ForegroundColor Yellow
Write-Host ""

$buildArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--name", "pipeline",
    "--distpath", "electron-app\resources",
    "--workpath", "build\pyinstaller",
    "--specpath", "build",
    "--add-data", "confusion_dict.py;.",
    "--hidden-import", "scan_and_grade",
    "--hidden-import", "database",
    "--hidden-import", "report_generator",
    "--hidden-import", "export_tool",
    "--hidden-import", "generate_sheet",
    "--hidden-import", "fill_simulator",
    "--hidden-import", "template_matcher",
    "--hidden-import", "run_pipeline",
    "--hidden-import", "jieba",
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "fitz",
    "--hidden-import", "rapidocr_onnxruntime",
    "--hidden-import", "weasyprint",
    "--hidden-import", "reportlab",
    "--hidden-import", "qrcode",
    "--hidden-import", "fonttools",
    "--hidden-import", "difflib",
    "--clean",
    "pipeline_cli.py"
)

& $venvPython $buildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "Check error messages above for details." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 3: Verify
Write-Host ""
Write-Host "[3/3] Verifying..." -ForegroundColor Yellow
$exePath = "electron-app\resources\pipeline.exe"
if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
    Write-Host "  Output: $exePath" -ForegroundColor Green
    Write-Host "  Size:   $size MB" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
} else {
    Write-Host "WARNING: Build seemed OK but output file not found at $exePath" -ForegroundColor Yellow
}

Read-Host "Press Enter to exit"
