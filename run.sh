#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm not found. Please install Node.js and npm first." >&2
  exit 1
fi

if [[ ! -f "frontend/package.json" ]]; then
  echo "Error: frontend/package.json not found." >&2
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "Error: frontend/node_modules missing. Run: cd frontend && npm install" >&2
  exit 1
fi

declare -a BACKEND_CMD
if command -v anonymous-prover >/dev/null 2>&1; then
  BACKEND_CMD=(anonymous-prover serve --host "$BACKEND_HOST" --port "$BACKEND_PORT")
elif [[ -x ".venv/bin/anonymous-prover" ]]; then
  BACKEND_CMD=("$ROOT_DIR/.venv/bin/anonymous-prover" serve --host "$BACKEND_HOST" --port "$BACKEND_PORT")
else
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found." >&2
    exit 1
  fi
  BACKEND_CMD=(python3 -m uvicorn anonymous_prover.api.app:create_app --factory --host "$BACKEND_HOST" --port "$BACKEND_PORT")
fi

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

echo "Starting backend: ${BACKEND_CMD[*]}"
if [[ "${BACKEND_CMD[0]}" == "python3" ]]; then
  (export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"; "${BACKEND_CMD[@]}") &
else
  "${BACKEND_CMD[@]}" &
fi
BACKEND_PID=$!

echo "Starting frontend: npm run dev -- --host $FRONTEND_HOST --port $FRONTEND_PORT"
(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo
echo "Frontend: http://localhost:${FRONTEND_PORT}"
echo "Backend : http://localhost:${BACKEND_PORT}"
echo "Docs    : http://localhost:${BACKEND_PORT}/docs"
echo "Press Ctrl+C to stop both."
echo

wait -n "$BACKEND_PID" "$FRONTEND_PID"
