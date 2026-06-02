Param(
    [string]$VenvPath = ".venv",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Write-Host "[rival] Starting native Windows dev workflow (no Docker)..." -ForegroundColor Cyan

if (-not (Test-Path $VenvPath)) {
    Write-Host "[rival] Creating virtual environment at $VenvPath" -ForegroundColor Yellow
    python -m venv $VenvPath
}

$activate = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    throw "Virtual environment activation script not found: $activate"
}

. $activate

if (-not $SkipInstall) {
    Write-Host "[rival] Installing package and dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    python -m pip install -e .
}

Write-Host "[rival] Initializing database schema + seed..." -ForegroundColor Yellow
haynesworld-rival init-db

Write-Host "[rival] Launching API server in a new terminal..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$PWD'; . '$activate'; haynesworld-rival run-api"

Write-Host "[rival] Launching worker loop in a new terminal..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$PWD'; . '$activate'; haynesworld-rival poll-loop"

Write-Host "[rival] Dev stack started." -ForegroundColor Green
Write-Host "- Admin UI: http://127.0.0.1:8080/admin/dashboard"
