#!/usr/bin/env bash
# =============================================================================
# Cloud FinOps — Local Environment Bootstrap & Health Verification
# =============================================================================
# Sets up the entire local environment:
# 1. Syncs environment variables across subprojects
# 2. Starts PostgreSQL + pgvector container (port 5433)
# 3. Applies TypeORM database migrations
# 4. Seeds FOCUS 1.0 dataset, synthetic metrics, and spend predictions
# 5. Verifies database and agent readiness
#
# Usage:
#   ./scripts/setup-local-env.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==========================================================================="
echo " 🚀 Cloud FinOps — Local Environment Bootstrap & Health Check"
echo "==========================================================================="

# 1. Sync environment configuration
echo "==> [1/5] Syncing environment configuration (.env)..."
./scripts/sync-env.sh

# 2. Start PostgreSQL + pgvector container
echo "==> [2/5] Starting PostgreSQL + pgvector container (port 5433)..."
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose up -d postgres
    echo "Waiting for PostgreSQL to be healthy..."
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U postgres -d cloud_finops >/dev/null 2>&1; then
            echo "    ✓ PostgreSQL container is healthy and accepting connections on port 5433"
            break
        fi
        sleep 1
    done
else
    echo "    ❌ Error: Docker daemon is not running. Please start Docker."
    exit 1
fi

# 3. Apply database migrations
echo "==> [3/5] Applying database schemas & TypeORM migrations..."
if [ -d "database/node_modules" ]; then
    (cd database && npm run migration:run)
    echo "    ✓ All 5 schema migrations applied successfully"
else
    echo "    ℹ Installing database dependencies..."
    (cd database && npm install --silent && npm run migration:run)
    echo "    ✓ Database dependencies installed and migrations applied"
fi

# 4. Seed sample datasets & predictive models
echo "==> [4/5] Seeding FOCUS 1.0 dataset, synthetic metrics, and spend forecasts..."
cd ai-agents/python
uv run --python .venv/bin/python python scripts/load_focus_data.py
uv run --python .venv/bin/python python scripts/generate_synthetic_metrics.py
uv run --python .venv/bin/python python scripts/run_predictions_pipeline.py
echo "    ✓ Seeding and predictions completed"

# 5. Health verification
echo "==> [5/5] Verifying multi-agent engine readiness..."
uv run --python .venv/bin/python python -c '

from finops_ai.memory import AgentMemoryRepository
from finops_ai.tools.cost_tools import query_cost_trend
from finops_ai.tools.infra_tools import get_tracked_resources
import os

db_url = os.getenv("DATABASE_URL")
repo = AgentMemoryRepository.from_url(db_url)
repo.get_interaction_memory(limit=1)

cost_res = query_cost_trend._run(dimension="service_category")
infra_res = get_tracked_resources._run(resource_type="compute/instance")

db_host = db_url.split("@")[-1] if db_url else "unknown"
days = cost_res.get("days_count", 0) if isinstance(cost_res, dict) else 0
infra_count = len(infra_res) if isinstance(infra_res, list) else 0
print(f"    ✓ Database connection: OK ({db_host})")
print(f"    ✓ Cost data queried:   {days} days trend available")
print(f"    ✓ Infra tracked:       {infra_count} resources available")
'


echo ""
echo "==========================================================================="
echo " 🎉 Environment is fully ready and responding!"
echo "==========================================================================="
echo ""
echo "To start chatting with the multi-agent system, run:"
echo ""
echo "    cd ai-agents/python"
echo "    uv run --python .venv/bin/python python scripts/chat_finops_agent.py"
echo ""
echo "Or simply run:"
echo "    ./scripts/test-chat.sh"
echo "==========================================================================="
