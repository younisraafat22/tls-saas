# TLS Appointment Checker - Build Script
# Step 1: PyInstaller  →  dist/TLSAppointmentChecker/
# Step 2: Inno Setup   →  installer_output/TLS_Appointment_Checker_v1.0.0_Setup.exe

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "=== TLS Appointment Checker Build ===" -ForegroundColor Cyan
Write-Host "Working directory: $root"
Write-Host ""

# ── 1. PyInstaller ──────────────────────────────────────────────────────────
Write-Host "[1/2] Running PyInstaller..." -ForegroundColor Yellow

$distPath  = Join-Path $root "dist"
$buildPath = Join-Path $root "build"

# Remove stale artifacts so frozen builds never reuse old files.
if (Test-Path $distPath) {
    Remove-Item -Recurse -Force $distPath
}
if (Test-Path $buildPath) {
    Remove-Item -Recurse -Force $buildPath
}

$oldErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"

$specPath = Join-Path $root "TLSAppointmentChecker.spec"
cmd.exe /c "python -m PyInstaller ""$specPath"" --clean --distpath ""$distPath"" --workpath ""$buildPath"" --noconfirm"

$ErrorActionPreference = $oldErrorAction

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller failed!" -ForegroundColor Red
    exit 1
}

$exePath = Join-Path $distPath "TLSAppointmentChecker\TLSAppointmentChecker.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: Expected EXE not found at: $exePath" -ForegroundColor Red
    exit 1
}

$exeSize = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "  EXE built: $exePath ($exeSize MB)" -ForegroundColor Green

# ── 2. Inno Setup ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/2] Running Inno Setup compiler..." -ForegroundColor Yellow

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    Write-Host "Inno Setup not found at: $iscc" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "installer_output") | Out-Null

& $iscc (Join-Path $root "installer_setup.iss")

if ($LASTEXITCODE -ne 0) {
    Write-Host "Inno Setup failed!" -ForegroundColor Red
    exit 1
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== BUILD COMPLETE ===" -ForegroundColor Green
$installer = Get-ChildItem (Join-Path $root "installer_output") -Filter "*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($installer) {
    $sizeMB = [math]::Round($installer.Length / 1MB, 1)
    Write-Host "Installer: $($installer.FullName) ($sizeMB MB)" -ForegroundColor Green
}
