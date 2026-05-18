# Deployment

NexusIntel berjalan sebagai stack Docker Compose dari root repo.

## One-command

```bash
docker compose up -d --build
```

Atau:

```bash
make up
```

Dashboard:

```text
http://127.0.0.1:8080
```

Stop:

```bash
docker compose down
```

## Services

- `frontend`: Nginx static React dashboard, reverse proxy `/api/`.
- `api`: FastAPI dari `backend/main.py`.
- `worker`: Celery dari `backend/tasks.py`.
- `redis`: broker Celery dan live log pub/sub.
- `postgres`: graph database.

## Ports

Default:

```text
127.0.0.1:8080 -> frontend:80
```

Custom:

```bash
NEXUS_HOST=0.0.0.0 NEXUS_PORT=9090 docker compose up -d --build
```

Atau:

```bash
make up HOST=0.0.0.0 PORT=9090
```

## Persistent Data

Compose memakai bind mount lokal:

```text
data/postgres
data/redis
```

Folder `data/` di-ignore dari git.

## Health Checks

API:

```text
GET /api/health
GET /api/v1/health
```

Graph:

```text
GET /api/v1/investigations/{id}/graph
```

Task:

```text
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/graph
WS  /api/v1/ws/logs/{task_id}
```

## Build Verification

```bash
python3 -m py_compile backend/main.py backend/tasks.py
cd frontend && npm ci && npm run build
docker compose config
docker compose build
```

## Local Legacy Mode

CLI/dashboard legacy manual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py dashboard 127.0.0.1:8080
```

Untuk platform enterprise terbaru, gunakan Compose.
