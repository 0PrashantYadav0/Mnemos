#!/usr/bin/env bash
# One-shot: install, test, verify, serve, and open Mnemos in the browser.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  uv venv --python 3.11
fi
uv pip install -e ".[dev]"

# If a Cognee Cloud key is present, install the cognee extra so the town's
# memory is mirrored into Cognee Cloud (the badge turns "live").
if [ -n "${COGNEE_API_KEY:-}" ]; then
  echo "== COGNEE_API_KEY detected -> installing Cognee Cloud support =="
  uv pip install -e ".[cognee]"
else
  echo "== No COGNEE_API_KEY set -> running local-only (Cognee Cloud badge: off) =="
fi

echo "== Running tests =="
uv run pytest -q

echo "== Verifying full playthroughs =="
uv run python -m mnemos.verify

PORT="${1:-8123}"
echo "== Serving on http://127.0.0.1:${PORT}/ =="
uv run uvicorn mnemos.api:app --port "${PORT}" &
SERVER_PID=$!
sleep 2

# Open in the default browser (mac / linux / windows-git-bash)
URL="http://127.0.0.1:${PORT}/"
if command -v open >/dev/null 2>&1; then open "$URL";
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL";
elif command -v start >/dev/null 2>&1; then start "$URL"; fi

echo "Server PID ${SERVER_PID}. Press Ctrl+C to stop."
wait $SERVER_PID
