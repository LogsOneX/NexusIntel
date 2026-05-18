#!/usr/bin/env sh
set -eu

HOST="${NEXUS_HOST:-127.0.0.1}"
PORT="${NEXUS_PORT:-8080}"

mkdir -p results reports .nexusrecon

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  NEXUS_HOST="$HOST" NEXUS_PORT="$PORT" docker compose up -d --build
  echo "NexusRecon dashboard: http://${HOST}:${PORT}"
  exit $?
fi

if command -v docker-compose >/dev/null 2>&1; then
  NEXUS_HOST="$HOST" NEXUS_PORT="$PORT" docker-compose up -d --build
  echo "NexusRecon dashboard: http://${HOST}:${PORT}"
  exit $?
fi

PYTHON="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
exec python main.py --no-banner dashboard "${HOST}:${PORT}"
