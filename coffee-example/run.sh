#!/usr/bin/env bash
#
# One-command launcher for the CORECONF coffee-maker fleet web console.
#
# Creates a local virtual environment (first run only), installs the two
# dependencies, and starts the web console. Works on macOS and Linux with
# any Python >= 3.9.
#
#   ./run.sh                 # start on http://localhost:8080
#   WEBUI_PORT=9000 ./run.sh # choose a different port
#
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: '$PY' not found. Install Python 3.9+ and retry." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[run] creating virtual environment (.venv)…"
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate

if ! python -c "import aiocoap, cbor2" >/dev/null 2>&1; then
  echo "[run] installing dependencies…"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
fi

echo "[run] starting web console on http://${WEBUI_HOST:-127.0.0.1}:${WEBUI_PORT:-8080}"
exec python webui/web_console.py
