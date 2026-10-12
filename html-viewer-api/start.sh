#!/usr/bin/env bash
# Local development: Azurite (storage emulator) + API on http://localhost:7071.
# No Docker needed: Azurite runs through npx. If something already listens on
# port 10000 (e.g. `docker compose up -d azurite`), that one is used instead.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-7071}"

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements-dev.txt
[ -f .env ] || cp .env.example .env

listening() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if ! listening 10000; then
  echo "==> Starting Azurite"
  npx --yes azurite@3 --silent --skipApiVersionCheck --loose --location .azurite &
  AZURITE_PID=$!
  trap 'kill $AZURITE_PID 2>/dev/null' EXIT
  for _ in $(seq 1 60); do listening 10000 && break; sleep 1; done
fi

python scripts/dev_setup.py

echo "==> API on http://localhost:$PORT (docs: http://localhost:$PORT/api/docs)"
uvicorn app.main:app --env-file .env --host 127.0.0.1 --port "$PORT" --reload
