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

# Override with PEERLENS_PORT / PEERLENS_HOST if 8000 is already taken.
PORT="${PEERLENS_PORT:-8000}"
HOST="${PEERLENS_HOST:-0.0.0.0}"

if [ "${1:-}" = "--prod" ]; then
  echo "${BOLD}==>${OFF} Building the frontend"
  (cd frontend && npm run build)
  echo "${BOLD}==>${OFF} Serving PeerLens on ${GREEN}http://localhost:${PORT}${OFF}"
  exec ./.venv/bin/uvicorn peerlens.main:app --host "$HOST" --port "$PORT"
fi

[ -d frontend/node_modules ] || { echo "${RED}Frontend dependencies missing. Run ./setup.sh first.${OFF}" >&2; exit 1; }

cleanup() { [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "${BOLD}==>${OFF} Starting the API on http://localhost:${PORT}"
./.venv/bin/uvicorn peerlens.main:app --host 127.0.0.1 --port "$PORT" --reload &
BACKEND_PID=$!

echo "${BOLD}==>${OFF} Starting the frontend on ${GREEN}http://localhost:5173${OFF}"
echo "    (Ctrl-C stops both.)"
cd frontend && npm run dev
