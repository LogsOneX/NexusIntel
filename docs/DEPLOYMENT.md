# Deployment

NexusIntel berjalan sebagai stack Docker Compose dari root repo. Stack utama menjalankan frontend, API, worker, Redis, dan PostgreSQL.

## Hidupin Stack

```bash
docker compose up -d --build
```

Atau:

```bash
make up
```

Buka dashboard:

```text
http://127.0.0.1:8080
```

## Cek Status

```bash
docker compose ps
```

Kondisi normal:

- `postgres`: healthy
- `redis`: healthy
- `api`: healthy
- `worker`: running
- `frontend`: healthy

## Logs

Semua service:

```bash
docker compose logs -f
```

Service tertentu:

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
```

## Restart

Semua service:

```bash
docker compose restart
```

Service tertentu:

```bash
docker compose restart api
docker compose restart worker
docker compose restart frontend
```

## Matiin Stack

Stop container dan network, tapi data investigation tetap tersimpan:

```bash
docker compose down
```

Atau:

```bash
make down
```

## Reset Total

Gunakan hanya saat ingin menghapus semua investigation/cache lokal.

```bash
docker compose down
sudo rm -rf data
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

Custom local port:

```bash
NEXUS_HOST=127.0.0.1 NEXUS_PORT=9090 docker compose up -d --build
```

Expose ke LAN:

```bash
NEXUS_HOST=0.0.0.0 NEXUS_PORT=8080 docker compose up -d --build
```

Gunakan `0.0.0.0` hanya kalau firewall dan environment sudah aman.

## Persistent Data

Compose memakai bind mount lokal:

```text
data/postgres
data/redis
```

Folder `data/` di-ignore dari git dan Docker build context.

## Health Checks

API:

```bash
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/v1/health
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
