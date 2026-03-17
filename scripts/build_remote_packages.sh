#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "Python 3 interpreter not found. Set PYTHON_BIN or install python3." >&2
  exit 1
fi

exec "$PYTHON_BIN" "$ROOT_DIR/scripts/build_remote_packages.py" "$@"