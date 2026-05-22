# Deployment

NexusIntel berjalan sebagai stack Docker Compose dari root repo. Stack utama menjalankan frontend, API, worker, Redis, dan PostgreSQL.

Repository resmi:

```text
https://github.com/LogsOneX/NexusIntel
```

## Kebutuhan Sistem

Minimum untuk testing ringan:

- CPU: 2 core / 2 vCPU
- RAM: 4 GB
- Storage kosong: 12 GB
- OS: Linux x86_64 direkomendasikan
- Runtime: Docker Engine 24+ dan Docker Compose v2

Rekomendasi harian:

- CPU: 4 core / 4 vCPU
- RAM: 8 GB
- Storage kosong: 25 GB

Operasi besar atau banyak case:

- CPU: 4-8 core
- RAM: 16 GB
- Storage kosong: 50 GB+

Storage bisa bertambah karena Docker image/build cache dan data investigation di `data/postgres`.

## Hidupin Stack

```bash
docker compose up -d --build
```

Atau:

```bash
make up
```

Buka command center:

```text
http://127.0.0.1:8080
```

Default development login:

```text
admin / nexusintel
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


## Auth dan LLM Environment

Ganti login lokal sebelum operasi nyata:

```bash
NEXUS_ADMIN_USER=operator \
NEXUS_ADMIN_PASSWORD="passphrase-kuat" \
NEXUS_AUTH_SECRET="secret-panjang" \
docker compose up -d --build
```

Konfigurasi Oracle LLM opsional:

```bash
NEXUS_LLM_PROVIDER=ollama \
NEXUS_LLM_ENDPOINT=http://localhost:11434 \
NEXUS_LLM_MODEL=llama3.1 \
docker compose up -d --build
```

BYOK opsional:

```bash
SHODAN_API_KEY=... INTELX_API_KEY=... VIRUSTOTAL_API_KEY=... docker compose up -d --build
```


## Ghost Engine Runtime Options

Optional internal egress proxy for public-source HTTP requests:

```bash
NEXUS_EGRESS_PROXY=http://proxy.internal:8080 docker compose up -d --build
```

The engine uses exponential backoff for 429/5xx responses and does not rotate proxies or bypass rate limits. `NEXUS_PLATFORM_CATALOG=/path/catalog.json` can be mounted for an internal 500+ public profile registry. Package `phonenumbers` is installed in the backend image for phone parsing; DNS uses dnspython through asyncio thread workers for Python 3.13 stability.

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
python3 -m py_compile backend/main.py backend/tasks.py backend/recon_validators.py
cd frontend && npm ci && npm run build
docker compose config
docker compose build
```

## Updated Runtime Files

Core runtime yang harus ikut ter-deploy:

```text
backend/main.py
backend/tasks.py
backend/recon_validators.py
frontend/src/components/Dashboard.tsx
frontend/src/components/FlowCanvas.tsx
frontend/src/components/CustomNode.tsx
frontend/src/components/GraphCanvas.tsx
frontend/src/styles.css
```

`GraphCanvas.tsx` dipertahankan sebagai compatibility wrapper. Canvas aktif adalah `FlowCanvas.tsx`.

## Local Legacy Mode

CLI/dashboard legacy manual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py dashboard 127.0.0.1:8080
```

Untuk platform enterprise terbaru, gunakan Compose.


## Advanced Services

Compose menjalankan service tambahan:

- `worker-network`: Celery queue `network_io,default`.
- `worker-ml`: Celery queue `ml_gpu`.
- `celery-beat`: scheduler watchlist.
- `y-websocket`: multiplayer canvas CRDT server.

Environment penting:

```bash
NEXUS_ENV=development
NEXUS_PROXY_POOL=http://proxy1:8080,http://proxy2:8080
WATCHLIST_SWEEP_SECONDS=1800
YJS_HOST=127.0.0.1
YJS_PORT=1234
```

`NEXUS_ENV=development` mengaktifkan dry-run untuk modul berpotensi memakai API eksternal seperti crypto tracker dan serverless invoker.
