#!/usr/bin/env bash
# PeerLens — native development setup (Linux / macOS).
# Safe to run repeatedly. Installs nothing globally.
set -euo pipefail

cd "$(dirname "$0")"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
info()  { echo "${BOLD}==>${OFF} $*"; }
ok()    { echo "  ${GREEN}✓${OFF} $*"; }
warn()  { echo "  ${YELLOW}!${OFF} $*"; }
die()   { echo "  ${RED}✗${OFF} $*" >&2; exit 1; }

# --- Python ---------------------------------------------------------------
info "Checking Python"
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      PYTHON="$candidate"; break
    fi
  fi
done
[ -n "$PYTHON" ] || die "Python 3.11 or newer is required. Install it, then re-run ./setup.sh"
ok "$($PYTHON --version)"

# --- Node -----------------------------------------------------------------
info "Checking Node.js"
command -v node >/dev/null 2>&1 || die "Node.js 20 or newer is required (https://nodejs.org)."
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 20 ] || die "Node.js 20+ required, found $(node --version)."
ok "$(node --version)"
command -v npm >/dev/null 2>&1 || die "npm is required (normally bundled with Node.js)."

# --- Virtual environment --------------------------------------------------
info "Setting up the Python virtual environment"
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
  ok "Created .venv"
else
  ok "Reusing existing .venv"
fi
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -e "backend[dev]"
ok "Backend dependencies installed"

# --- Frontend -------------------------------------------------------------
info "Installing frontend dependencies"
(cd frontend && npm install --silent --no-audit --no-fund)
ok "Frontend dependencies installed"

# --- Data directory and database -----------------------------------------
info "Initializing data directory and database"
mkdir -p data/uploads
./.venv/bin/python -c "
import sys; sys.path.insert(0, 'backend')
from peerlens.db import init_db
from peerlens import config
init_db()
print(f'  database: {config.DB_PATH}')
print(f'  uploads:  {config.UPLOAD_DIR}')
"
ok "SQLite initialized"

echo
echo "${GREEN}${BOLD}Setup complete.${OFF}"
echo
echo "  Start PeerLens:   ${BOLD}./run.sh${OFF}"
echo "  Then open:        ${BOLD}http://localhost:5173${OFF}"
echo
echo "  Configure your AI provider in Settings. A local Ollama model works with"
echo "  no API key and no data leaving your machine."
