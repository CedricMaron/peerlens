# PeerLens - start the development servers (Windows PowerShell).
#
#   .\run.ps1          backend on :8000 + Vite dev server on :5173 (hot reload)
#   .\run.ps1 -Prod    build the frontend and serve everything from :8000

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

if ($Prod) {
    Write-Host "==> Building the frontend"
    Push-Location frontend
    try { npm run build } finally { Pop-Location }
    Write-Host "==> Serving PeerLens on http://localhost:8000" -ForegroundColor Green
    & .\.venv\Scripts\uvicorn.exe peerlens.main:app --host 0.0.0.0 --port 8000
    exit $LASTEXITCODE
}

if (-not (Test-Path frontend\node_modules)) {
    Write-Host "Frontend dependencies missing. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "==> Starting the API on http://localhost:8000"
$backend = Start-Process -PassThru -NoNewWindow `
    -FilePath ".\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "peerlens.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"

try {
    Write-Host "==> Starting the frontend on http://localhost:5173" -ForegroundColor Green
    Write-Host "    (Ctrl-C stops both.)"
    Push-Location frontend
    try { npm run dev } finally { Pop-Location }
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
