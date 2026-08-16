#!/usr/bin/env bash
# PeerLens — start the development servers (Linux / macOS).
#
#   ./run.sh          backend on :8000 + Vite dev server on :5173 (hot reload)
#   ./run.sh --prod   build the frontend and serve everything from :8000
set -euo pipefail

cd "$(dirname "$0")"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'

[ -d .venv ] || { echo "${RED}No .venv found. Run ./setup.sh first.${OFF}" >&2; exit 1; }

export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
[ -f .env ] && set -a && . ./.env && set +a

if [ "${1:-}" = "--prod" ]; then
  echo "${BOLD}==>${OFF} Building the frontend"
  (cd frontend && npm run build)
  echo "${BOLD}==>${OFF} Serving PeerLens on ${GREEN}http://localhost:8000${OFF}"
  exec ./.venv/bin/uvicorn peerlens.main:app --host 0.0.0.0 --port 8000
fi

[ -d frontend/node_modules ] || { echo "${RED}Frontend dependencies missing. Run ./setup.sh first.${OFF}" >&2; exit 1; }

cleanup() { [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "${BOLD}==>${OFF} Starting the API on http://localhost:8000"
./.venv/bin/uvicorn peerlens.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

echo "${BOLD}==>${OFF} Starting the frontend on ${GREEN}http://localhost:5173${OFF}"
echo "    (Ctrl-C stops both.)"
cd frontend && npm run dev
