#!/usr/bin/env bash
set -euo pipefail

# run_dev.sh — inicia backend (uvicorn) e frontend (vite) para desenvolvimento local
# Uso: ./run_dev.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[run_dev] garantindo venv..."
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate

echo "[run_dev] instalando dependências Python..."
pip install -r backend/requirements.txt

echo "[run_dev] iniciando backend (uvicorn) em background..."
python -m uvicorn backend.app:app --reload --port 8000 &
BACKEND_PID=$!
echo "[run_dev] backend PID=$BACKEND_PID"

echo "[run_dev] escrevendo .env.local para o frontend..."
cat > .env.local <<EOF
VITE_BASE_API_URL=http://localhost:8000
EOF

echo "[run_dev] iniciando frontend (npm run dev)..."
npm install
npm run dev

echo "[run_dev] frontend exit detected — encerrando backend (PID=$BACKEND_PID)"
kill $BACKEND_PID || true
