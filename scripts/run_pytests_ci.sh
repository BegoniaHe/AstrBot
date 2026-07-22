#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p ./data/plugins ./data/config ./data/temp

export TESTING="${TESTING:-true}"

# Keep backward compatibility with existing test code that reads ZHIPU_API_KEY.
if [[ -n "${OPENAI_API_KEY:-}" && -z "${ZHIPU_API_KEY:-}" ]]; then
  export ZHIPU_API_KEY="$OPENAI_API_KEY"
fi

PYTEST_TARGETS=("${@:-./tests}")

echo "[ci] syncing dependencies with uv"
uv sync --group dev --locked

echo "[ci] running tests: ${PYTEST_TARGETS[*]}"
uv run pytest "${PYTEST_TARGETS[@]}"
