# ---------------------------------------------------------------------------
# RAG Quality Monitor — Windows PowerShell launcher.
#
#   .\scripts\start.ps1
#   .\scripts\start.ps1 -BackendOnly
#   .\scripts\start.ps1 -FrontendOnly
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$Port = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "error: .venv not found. Run .\scripts\setup.ps1 first."
}

$jobs = @()

if (-not $FrontendOnly) {
    Write-Host "==> API      : http://127.0.0.1:$Port  (docs at /docs)"
    $jobs += Start-Job -Name "rqm-backend" -ScriptBlock {
        param($root, $port)
        Set-Location (Join-Path $root "backend")
        & (Join-Path $root ".venv\Scripts\python.exe") -m uvicorn app.main:app --host 127.0.0.1 --port $port
    } -ArgumentList $Root, $Port
}

if (-not $BackendOnly) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "==> Dashboard: http://127.0.0.1:$FrontendPort"
        $jobs += Start-Job -Name "rqm-frontend" -ScriptBlock {
            param($root, $port)
            Set-Location (Join-Path $root "frontend")
            npm run dev -- --port $port
        } -ArgumentList $Root, $FrontendPort
    }
    else {
        Write-Warning "npm not found - the dashboard cannot be started."
    }
}

Write-Host "Press Ctrl+C to stop."
try {
    while ($true) {
        Start-Sleep -Seconds 2
        $jobs | Receive-Job
    }
}
finally {
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
}
