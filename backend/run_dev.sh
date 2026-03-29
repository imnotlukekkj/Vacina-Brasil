#!/usr/bin/env bash
# Small helper to load backend/.env and run uvicorn for development.
# Usage: ./backend/run_dev.sh
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
ENV_FILE="$DIR/.env"
if [ -f "$ENV_FILE" ]; then
  # Export env file into this shell
  # shellcheck disable=SC1090
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  echo "Loaded environment from $ENV_FILE"
else
  echo "No $ENV_FILE found. Create one from .env.example and set your SUPABASE_* vars."
fi
# Run uvicorn from project root
cd "$DIR/.."
# If a project virtualenv exists at ../.venv, try to activate it so uvicorn is available
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -f "$(pwd)/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$(pwd)/.venv/bin/activate"
    echo "Activated virtualenv at $(pwd)/.venv"
  fi
fi

# Prefer system uvicorn if available, otherwise run via python -m uvicorn
if command -v uvicorn >/dev/null 2>&1; then
  uvicorn backend.app:app --reload --port 8000
else
  echo "uvicorn not found in PATH, running via python -m uvicorn"
  python -m uvicorn backend.app:app --reload --port 8000
fi
