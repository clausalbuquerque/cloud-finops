#!/usr/bin/env bash
#
# sync-env.sh — Distribute the root .env (single source of truth) to every
# sub-project that consumes environment variables.
#
# Usage:
#   ./scripts/sync-env.sh            # write copies to all targets
#   ./scripts/sync-env.sh --check    # dry run: show what would be written
#
# Edit ONLY the root .env. The generated per-project .env files carry a
# "DO NOT EDIT" header and are overwritten on every run.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC="${ROOT_DIR}/.env"

# Sub-project directories that receive a copy of the root .env.
TARGETS=(
  "azure-consumption-extractor"
  "azure-metrics-extractor"
  "database"
  "ai-agents/python"
)

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
elif [[ -n "${1:-}" ]]; then
  echo "Unknown argument: ${1}" >&2
  echo "Usage: ./scripts/sync-env.sh [--check]" >&2
  exit 2
fi

if [[ ! -f "${SRC}" ]]; then
  echo "ERROR: root .env not found at ${SRC}" >&2
  echo "Create it first:  cp .env.example .env  (then fill in secrets)" >&2
  exit 1
fi

HEADER="# ============================================================================
# AUTO-GENERATED from the root .env by scripts/sync-env.sh — DO NOT EDIT.
# Edit the root .env and re-run:  ./scripts/sync-env.sh
# ============================================================================"

echo "Source of truth: ${SRC}"
written=0
for t in "${TARGETS[@]}"; do
  dest_dir="${ROOT_DIR}/${t}"
  dest="${dest_dir}/.env"
  if [[ ! -d "${dest_dir}" ]]; then
    echo "  skip   ${t}/.env (directory not found)"
    continue
  fi
  if ${CHECK_ONLY}; then
    echo "  would write  ${t}/.env"
  else
    { printf '%s\n\n' "${HEADER}"; cat "${SRC}"; } > "${dest}"
    echo "  wrote  ${t}/.env"
    written=$((written + 1))
  fi
done

if ${CHECK_ONLY}; then
  echo "Check complete (no files written)."
else
  echo "Done. Wrote ${written} file(s)."
fi
