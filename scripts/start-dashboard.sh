#!/usr/bin/env bash
# =============================================================================
# Cloud FinOps — Dashboard Local Runner
# =============================================================================
# 1. Bootstraps the local database environment (using setup-local-env.sh)
# 2. Starts the Backend-For-Frontend (BFF) API on port 3001
# 3. Starts the Vite React Frontend on port 5173
#
# Usage:
#   ./scripts/start-dashboard.sh
# =============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==========================================================================="
echo " 🚀 Cloud FinOps — Starting Dashboard Environment"
echo "==========================================================================="

# Ensure DB and data are ready
./scripts/setup-local-env.sh

echo ""
echo "==> Starting Python Agent Engine (FastAPI on Port 8000)..."
cd "$REPO_ROOT/ai-agents/python"
if command -v uv >/dev/null 2>&1; then
  uv run --python .venv/bin/python python scripts/run_fastapi.py &
elif [ -f ".venv/bin/python" ]; then
  .venv/bin/python scripts/run_fastapi.py &
else
  python3 scripts/run_fastapi.py &
fi
API_PID=$!

echo "Waiting for Python Agent Engine to be ready on port 8000..."
for i in {1..30}; do
  if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "    ✓ Python Agent Engine is healthy and listening on port 8000"
    break
  fi
  sleep 0.5
done

echo "==> Starting BFF Express Server (Port 3001)..."
cd "$REPO_ROOT/dashboard/server"
npm run dev &
BFF_PID=$!

echo "==> Starting Vite React Frontend (Port 5173)..."
cd "$REPO_ROOT/dashboard"
npm run dev &
UI_PID=$!

echo ""
echo "✅ Everything is running!"
echo "➡️  Open your browser to: http://localhost:5173"
echo "Press Ctrl+C to stop all services."

# Trap Ctrl+C to kill background processes
trap "echo 'Stopping services...'; kill $API_PID $BFF_PID $UI_PID 2>/dev/null || true; exit" INT TERM
wait

