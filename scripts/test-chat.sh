#!/usr/bin/env bash
# =============================================================================
# Cloud FinOps — Local Agent Environment Setup & Interactive Chat Runner
# =============================================================================
# 1. Runs ./scripts/setup-local-env.sh to ensure Postgres, migrations, and seed data are ready
# 2. Launches the interactive multi-agent chat console
#
# Usage:
#   ./scripts/test-chat.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Ensure environment is initialized, seeded, and verified
./scripts/setup-local-env.sh

# Launch the interactive chat console
echo "Dropping you into the Multi-Agent Chat Console..."
cd "$REPO_ROOT/ai-agents/python"
exec uv run --python .venv/bin/python python scripts/chat_finops_agent.py "$@"
