#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PORT="${PORT:-8787}"
export HOST="${HOST:-127.0.0.1}"
export MIDSCENE_ENV_FILE="${MIDSCENE_ENV_FILE:-$ROOT/backend/.env}"
export MIDSCENE_DRY_RUN="${MIDSCENE_DRY_RUN:-1}"

exec "${NODE_BIN:-node}" "$ROOT/midscene-runner/src/server.js"
