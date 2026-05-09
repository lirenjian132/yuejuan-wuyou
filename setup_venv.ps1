<# YueJuanWuYou - Setup Windows venv and install dependencies #>

$ErrorActionPreference = "Continue"
$host.ui.RawUI.WindowTitle = "YueJuanWuYou Setup"

# Find Python 3.12
$pythonPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Python312\python.exe"
)

$python = $null
foreach ($p in $pythonPaths) {
    if (Test-Path $p) {
        $python = $p
        Write-Host "Found Python: $p" -ForegroundColor Green
        break
    }
}

if (-not $python) {
    Write-Host "ERROR: Python 3.12 not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Set up paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$venvDir = Join-Path $scriptDir "venv_win"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Windows venv + Dependencies" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Project dir: $scriptDir"
Write-Host ""

# Create venv
Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Yellow
& $python -m venv $venvDir

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Failed to create venv!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "venv created." -ForegroundColor Green

# Install Python dependencies
Write-Host ""
Write-Host "[2/3] Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "(This downloads from Tsinghua mirror, may take a few minutes)"
Write-Host ""

& $venvPip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if ($LASTEXITCODE -ne 0) {
    Write-Host "Mirror failed, trying default PyPI..." -ForegroundColor Yellow
    & $venvPip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host "Dependencies installed." -ForegroundColor Green

# Install PyInstaller
Write-Host ""
Write-Host "[3/3] Installing PyInstaller..." -ForegroundColor Yellow
& $venvPip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

if ($LASTEXITCODE -ne 0) {
    & $venvPip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install PyInstaller!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host "PyInstaller installed." -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "  Next: run build_pipeline.ps1" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

Read-Host "Press Enter to exit"
