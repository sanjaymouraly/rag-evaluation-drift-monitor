# ---------------------------------------------------------------------------
# RAG Quality Monitor — Windows PowerShell setup.
# Creates a virtual environment, installs the backend and frontend
# dependencies and (optionally) seeds the demo data.
#
#   .\scripts\setup.ps1
#   .\scripts\setup.ps1 -NoSeed
#   .\scripts\setup.ps1 -NoFrontend
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [switch]$NoSeed,
    [switch]$NoFrontend,
    [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command $PythonBin -ErrorAction SilentlyContinue)) {
    Write-Error "error: '$PythonBin' not found. Install Python 3.11 or newer and re-run."
}

$version = & $PythonBin -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "==> Using Python $version ($PythonBin)"

& $PythonBin -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "error: Python 3.11 or newer is required (found $version)."
}

Write-Host "==> Creating the virtual environment (.venv)"
if (-not (Test-Path ".venv")) {
    & $PythonBin -m venv .venv
}
$python = Join-Path $Root ".venv\Scripts\python.exe"
$pip = Join-Path $Root ".venv\Scripts\pip.exe"

Write-Host "==> Installing the backend dependencies"
& $python -m pip install --upgrade pip
& $pip install -r backend\requirements-dev.txt

if (-not $NoFrontend) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "==> Installing the frontend dependencies"
        Push-Location frontend
        try { npm install } finally { Pop-Location }
    }
    else {
        Write-Warning "npm not found - skipping the frontend install."
    }
}

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
    Write-Host "    (edit .env to set RQM_API_KEY before exposing the server)"
}

if (-not $NoSeed) {
    Write-Host "==> Seeding the demo project (documents, benchmark, runs, gate verdicts)"
    Push-Location backend
    try { & $python -m app.seed --reset } finally { Pop-Location }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "  Start the backend : .\scripts\start.ps1"
Write-Host "  Start the frontend: .\scripts\start.ps1 -FrontendOnly"
Write-Host "  API documentation  : http://127.0.0.1:8000/docs"
