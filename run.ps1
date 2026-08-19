# PeerLens - start the development servers (Windows PowerShell).
#
#   .\run.ps1          backend on :8000 + Vite dev server on :5173 (hot reload)
#   .\run.ps1 -Prod    build the frontend and serve everything from :8000
#
# If Windows blocks this script, run it as:
#   powershell -ExecutionPolicy Bypass -File .\run.ps1

param([switch]$Prod)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    Write-Host "No .venv found. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = "$PSScriptRoot\backend" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })

# Load .env if present (KEY=VALUE lines, # comments ignored).
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'))
        }
    }
}

# Override with PEERLENS_PORT / PEERLENS_HOST if 8000 is already taken.
$port = if ($env:PEERLENS_PORT) { $env:PEERLENS_PORT } else { "8000" }
$bindHost = if ($env:PEERLENS_HOST) { $env:PEERLENS_HOST } else { "0.0.0.0" }

if ($Prod) {
    Write-Host "==> Building the frontend"
    Push-Location frontend
    try { npm run build } finally { Pop-Location }
    Write-Host "==> Serving PeerLens on http://peerlens.localhost:$port" -ForegroundColor Green
    Write-Host "    (or http://localhost:$port - browsers resolve any *.localhost name themselves)"
    & .\.venv\Scripts\uvicorn.exe peerlens.main:app --host $bindHost --port $port
    exit $LASTEXITCODE
}

if (-not (Test-Path frontend\node_modules)) {
    Write-Host "Frontend dependencies missing. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "==> Starting the API on http://localhost:$port"
$backend = Start-Process -PassThru -NoNewWindow `
    -FilePath ".\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "peerlens.main:app", "--host", "127.0.0.1", "--port", $port, "--reload"

try {
    Write-Host "==> Starting the frontend on http://peerlens.localhost:5173" -ForegroundColor Green
    Write-Host "    (Ctrl-C stops both.)"
    Push-Location frontend
    try { npm run dev } finally { Pop-Location }
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
