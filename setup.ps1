# ==============================================================================
# Firefly Mini — Automated Windows Setup Sentinel v2.1.0
# PowerShell installation script for Windows 10 / 11
# ==============================================================================

[CmdletBinding()]
param (
    [switch]$Check,
    [switch]$Force,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\setup.ps1 [-Check] [-Force] [-Help]" -ForegroundColor Cyan
    Write-Host "  -Check : Verify dependencies without installing"
    Write-Host "  -Force : Reinstall virtualenv and dependencies"
    Write-Host "  -Help  : Show this help message"
    exit 0
}

Write-Host "✦ ============================================================ ✦" -ForegroundColor Magenta
Write-Host "   FIREFLY MINI — Cyber-Cat Windows Setup Sentinel v2.1.0       " -ForegroundColor Cyan
Write-Host "✦ ============================================================ ✦" -ForegroundColor Magenta

# Check Python
$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = "py -3"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyCmd = "python"
}

if (-not $pyCmd) {
    Write-Host "`n[X] Python 3.10+ is missing!" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org or run:"
    Write-Host "  winget install Python.Python.3.11" -ForegroundColor Yellow
    exit 1
}

$pyVer = & ($pyCmd.Split(' ')) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
Write-Host "`n[✔] Detected Python: $pyVer ($pyCmd)" -ForegroundColor Green

if ($Check) {
    Write-Host "`n[✔] Pre-flight check complete." -ForegroundColor Green
    exit 0
}

# Create / reuse virtual environment
$venvDir = ".venv"
$venvPython = "$venvDir\Scripts\python.exe"
$venvFirefly = "$venvDir\Scripts\firefly.exe"

if ($Force -and (Test-Path $venvDir)) {
    Write-Host "`n[*] Removing existing virtual environment (-Force)..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Write-Host "`n[*] Creating Python virtual environment in $venvDir..." -ForegroundColor Cyan
    & ($pyCmd.Split(' ')) -m venv $venvDir
}

Write-Host "`n[*] Upgrading pip and setuptools..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip setuptools wheel -q

Write-Host "`n[*] Installing Firefly Mini in editable mode with dev dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install -e ".[dev]" -q

Write-Host "`n[*] Running Firefly Doctor diagnostic..." -ForegroundColor Magenta
& $venvPython -m firefly doctor

Write-Host "`n✦ ============================================================ ✦" -ForegroundColor Magenta
Write-Host "✔ Setup Completed Successfully!" -ForegroundColor Green
Write-Host "Run Firefly Mini with:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\firefly chat" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\firefly hud" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\firefly doctor" -ForegroundColor Yellow
Write-Host "✦ ============================================================ ✦" -ForegroundColor Magenta
