#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/backend/.venv-py312/Scripts/python.exe}"

export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-8000}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://47.89.252.137:18080/v1}"
export VISUAL_UI_DRAFT_MODEL="${VISUAL_UI_DRAFT_MODEL:-gpt-5.5}"
export MIDSCENE_RUNNER_URL="${MIDSCENE_RUNNER_URL:-http://127.0.0.1:8787}"

exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
