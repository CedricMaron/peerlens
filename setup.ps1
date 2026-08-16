# PeerLens - native development setup (Windows PowerShell).
# Safe to run repeatedly. Installs nothing globally.
#
#   .\setup.ps1

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Write-Info { param($m) Write-Host "==> $m" -ForegroundColor White }
function Write-Ok   { param($m) Write-Host "  [ok] $m" -ForegroundColor Green }
function Write-Fail { param($m) Write-Host "  [x] $m" -ForegroundColor Red; exit 1 }

# --- Python ---------------------------------------------------------------
Write-Info "Checking Python"
$python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $check = & $candidate -c "import sys; print(1 if sys.version_info >= (3,11) else 0)" 2>$null
    if ($check -eq '1') { $python = $candidate; break }
}
if (-not $python) { Write-Fail "Python 3.11 or newer is required (https://python.org)." }
Write-Ok (& $python --version)

# --- Node -----------------------------------------------------------------
Write-Info "Checking Node.js"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Fail "Node.js 20 or newer is required (https://nodejs.org)."
}
$nodeMajor = [int](node -p "process.versions.node.split('.')[0]")
if ($nodeMajor -lt 20) { Write-Fail "Node.js 20+ required, found $(node --version)." }
Write-Ok (node --version)
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Fail "npm is required." }

# --- Virtual environment --------------------------------------------------
Write-Info "Setting up the Python virtual environment"
if (-not (Test-Path .venv)) {
    & $python -m venv .venv
    Write-Ok "Created .venv"
} else {
    Write-Ok "Reusing existing .venv"
}
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -e "backend[dev]"
Write-Ok "Backend dependencies installed"

# --- Frontend -------------------------------------------------------------
Write-Info "Installing frontend dependencies"
Push-Location frontend
try { npm install --silent --no-audit --no-fund } finally { Pop-Location }
Write-Ok "Frontend dependencies installed"

# --- Data directory and database -----------------------------------------
Write-Info "Initializing data directory and database"
New-Item -ItemType Directory -Force -Path data\uploads | Out-Null
& .\.venv\Scripts\python.exe -c @"
import sys; sys.path.insert(0, 'backend')
from peerlens.db import init_db
from peerlens import config
init_db()
print(f'  database: {config.DB_PATH}')
print(f'  uploads:  {config.UPLOAD_DIR}')
"@
Write-Ok "SQLite initialized"

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "  Start PeerLens:   .\run.ps1"
Write-Host "  Then open:        http://localhost:5173"
Write-Host ""
Write-Host "  Configure your AI provider in Settings. A local Ollama model works with"
Write-Host "  no API key and no data leaving your machine."
