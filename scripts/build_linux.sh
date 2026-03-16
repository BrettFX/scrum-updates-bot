#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
	echo "Missing virtual environment. Run $ROOT_DIR/scripts/bootstrap_linux.sh first." >&2
	exit 1
fi

cd "$ROOT_DIR"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onedir --paths src --name scrum-updates-bot src/scrum_updates_bot/main.py