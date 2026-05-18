# Deployment

NexusIntel berjalan sebagai stack Docker Compose penuh dari root repo: React frontend di `frontend/`, FastAPI backend di `backend/`, Celery worker, Redis broker/event bus, dan PostgreSQL graph store. Default binding sengaja `127.0.0.1:8080` supaya dashboard tidak terbuka ke network publik tanpa keputusan eksplisit.

## One-command path

```bash
make up
```

Dashboard tersedia di:

```text
http://127.0.0.1:8080
```

Stop service:

```bash
make down
```

Alternatif langsung:

```bash
docker compose up -d --build
```

`./start.sh` juga tersedia sebagai wrapper singkat untuk Compose.

## Custom host atau port

```bash
make up HOST=0.0.0.0 PORT=8080
```

Atau:

```bash
NEXUS_HOST=127.0.0.1 NEXUS_PORT=9090 ./start.sh
```

## Runtime data

Docker Compose memakai named volume berikut agar graph dan broker state tetap tersimpan:

- `nexus_pgdata`
- `nexus_redis`

## Health dan readiness

Health endpoint:

```text
GET /api/health
```

Graph endpoint:

```text
GET /api/investigations/{id}/graph
```

Live event stream:

```text
GET /api/investigations/{id}/events
WS  /api/investigations/{id}/ws
```

Operational readiness lokal:

```bash
make readiness
```

CLI anatomy check:

```bash
make doctor
```

## Manual local mode

Manual local mode di bawah ini hanya untuk CLI/dashboard legacy, bukan stack penuh:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py --no-banner dashboard 127.0.0.1:8080
```

NexusRecon tetap local-first. Gunakan mode `active` atau `aggressive` hanya untuk target yang kamu miliki izin untuk dianalisis.
