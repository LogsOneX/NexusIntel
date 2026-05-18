#!/usr/bin/env sh
set -eu

HOST="${NEXUS_HOST:-127.0.0.1}"
PORT="${NEXUS_PORT:-8080}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  NEXUS_HOST="$HOST" NEXUS_PORT="$PORT" docker compose up -d --build
  echo "NexusIntel platform: http://${HOST}:${PORT}"
  exit $?
fi

if command -v docker-compose >/dev/null 2>&1; then
  NEXUS_HOST="$HOST" NEXUS_PORT="$PORT" docker-compose up -d --build
  echo "NexusIntel platform: http://${HOST}:${PORT}"
  exit $?
fi

echo "Docker Compose is required for the full standalone stack: frontend, API, worker, Redis, and PostgreSQL." >&2
exit 1
