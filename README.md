# NexusIntel OSINT Platform

NexusIntel adalah platform investigasi OSINT standalone: visual graph dashboard, FastAPI gateway, Celery worker, Redis live telemetry, dan PostgreSQL graph store. Core code berjalan langsung dari root repo lewat `frontend/`, `backend/main.py`, dan `backend/tasks.py`.

Repository resmi:

```text
https://github.com/LogsOneX/NexusIntel
```

Project ini tidak menumpang repo OSINT eksternal untuk runtime core. Konsep dari Flowsint, Maigret, Sherlock, GHunt, Holehe, Maltego, dan OSINT.Industries dipakai sebagai inspirasi produk dan workflow; implementasi di sini dibuat ulang dengan metode public-source/free.

## Guardrail

NexusIntel dirancang untuk public-source reconnaissance dan target yang kamu miliki izin untuk dianalisis.

- Tidak ada paid API subscription.
- Tidak ada credential stuffing.
- Tidak ada private API abuse.
- Tidak ada register/forgot-password probing.
- Tidak ada bypass, spam, atau rate-limit evasion.
- Mode agresif tetap read-only dan harus dipakai hanya untuk target authorized.

## Stack

```text
React + Cytoscape dashboard
  -> Nginx reverse proxy
  -> FastAPI API gateway
  -> Celery worker
  -> Redis broker + WebSocket log bus
  -> PostgreSQL graph database
  -> recon_validators + NexusRecon/core/modules/recon local OSINT engine
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
- Network stabil untuk DNS/HTTP public-source recon

Operasi besar atau banyak case:

- CPU: 4-8 core
- RAM: 16 GB
- Storage kosong: 50 GB+

Estimasi penggunaan storage:

- Docker images + build cache awal: 4-10 GB
- `data/postgres`: mulai kecil, bisa tumbuh 1-20 GB tergantung jumlah investigation
- `data/redis`: biasanya kecil, ratusan MB, tergantung task/log history
- `results/`, `reports/`, `.nexusrecon/`: output lokal bila CLI legacy dipakai

Detail lengkap ada di [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

## Cara Hidupin dan Matiin Tools

### Hidupin stack utama

```bash
docker compose up -d --build
```

Alternatif via Makefile:

```bash
make up
```

Buka dashboard:

```text
http://127.0.0.1:8080
```

Stack ini menjalankan frontend, API, worker, Redis, dan PostgreSQL.

### Cek status service

```bash
docker compose ps
```

Status normal:

- `postgres` healthy
- `redis` healthy
- `api` healthy
- `worker` running
- `frontend` healthy

### Lihat logs

Semua service:

```bash
docker compose logs -f
```

API saja:

```bash
docker compose logs -f api
```

Worker saja:

```bash
docker compose logs -f worker
```

### Restart service

Restart semua:

```bash
docker compose restart
```

Restart satu service:

```bash
docker compose restart api
docker compose restart worker
docker compose restart frontend
```

### Matiin stack

Stop dan hapus container/network, data tetap aman:

```bash
docker compose down
```

Atau:

```bash
make down
```

### Reset data lokal

Matikan stack dulu:

```bash
docker compose down
```

Lalu hapus runtime database/cache lokal:

```bash
sudo rm -rf data
```

Gunakan reset hanya kalau memang ingin menghapus semua investigation lama.

### Ganti host atau port

```bash
NEXUS_HOST=127.0.0.1 NEXUS_PORT=9090 docker compose up -d --build
```

Atau:

```bash
make up HOST=127.0.0.1 PORT=9090
```

Dashboard berubah menjadi:

```text
http://127.0.0.1:9090
```

### Health check cepat

```bash
curl http://127.0.0.1:8080/api/v1/health
```

Data runtime disimpan lokal di:

```text
data/postgres
data/redis
```

Folder `data/` di-ignore dari git.

## Dashboard Flow

Dashboard terbaru tidak memakai include/exclude/module picker. Investigator cukup memasukkan target, memilih mode, lalu graph utama menjadi pusat operasi. UI sekarang memakai `FlowCanvas` berbasis Cytoscape dengan drag-and-drop entity pipeline, right-click Logic Flow, data drawer, dan terminal HUD.

1. Submit target username/email/domain/IP/phone.
2. API mengklasifikasi target dan membuat investigation + root entity.
3. Worker Celery menjalankan pipeline OSINT public-source sesuai tipe target.
4. `backend/recon_validators.py` memvalidasi, memecah, dan menormalisasi artifact menjadi schema graph.
5. Worker menulis node/edge ke PostgreSQL dan menyiarkan log real-time ke Redis.
6. UI menerima WebSocket telemetry di terminal HUD.
7. Graph refresh otomatis dan investigator bisa klik/right-click/drag-drop entity untuk transform lanjutan.

Transform utama:

- Username sweep: konsep Maigret/Sherlock untuk enumerasi profil publik.
- Email/workspace recon: konsep Holehe/GHunt yang dibatasi ke DNS, provider hints, Gravatar hash, dan public workspace indicators.
- Domain/DNS recon: A/AAAA/CNAME/MX/NS/TXT/CAA, RDAP, mail posture, service hints, dan crt.sh subdomain read-only.
- IP recon: reverse DNS, RDAP allocation, dan GeoIP/ASN hint dari sumber gratis.
- Phone recon: E.164 validation, country calling code, dan offline public numbering-plan hint.
- Manual entity builder + drag-and-drop entity pipeline: tambah entity dan link langsung ke selected node.

## Deep Recon Validator

`backend/recon_validators.py` adalah parser public-source baru yang berjalan sebelum data dikirim ke UI:

- Email: regex validation, local-part/domain split, MX/TXT/DMARC/BIMI, disposable-domain hint, mail posture, dan guardrail breach/register probing.
- Domain/IP: DNS, RDAP, crt.sh, reverse DNS, GeoIP/ASN hint via free source.
- Username/nama: shape validation, name-part split, public profile candidate URLs, dan guardrail sensitive inference.
- Phone: strict E.164, country calling code, public numbering-plan line hint, dan guardrail messaging-app registration probing.

NexusIntel tidak melakukan register/forgot-password probing, private API usage, phone/email account existence probing, atau rate-limit evasion.

## API Utama

```text
GET  /api/health
GET  /api/v1/health
POST /api/v1/scans/nexusrecon
POST /api/v1/investigations
GET  /api/v1/investigations
GET  /api/v1/investigations/{id}/graph
POST /api/v1/entities
DELETE /api/v1/investigations/{id}/entities/{node_id}
POST /api/v1/transforms
GET  /api/v1/tasks/{task_id}
GET  /api/v1/tasks/{task_id}/graph
WS   /api/v1/ws/logs/{task_id}
```

## Struktur Aktif

```text
.
├── backend/
│   ├── main.py          # canonical FastAPI gateway
│   ├── tasks.py         # canonical Celery OSINT workers
│   ├── recon_validators.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/components/Dashboard.tsx
│   ├── src/components/FlowCanvas.tsx
│   ├── src/components/CustomNode.tsx
│   ├── src/components/GraphCanvas.tsx  # compatibility wrapper
│   ├── src/App.jsx
│   └── src/styles.css
├── core/                # legacy-compatible local engine, graph, flows, reports
├── modules/             # public-source OSINT modules
├── nexusrecon/          # NexusRecon class bridge used by backend/tasks.py
├── recon/               # platform registry and standalone scanners
├── docs/
├── docker-compose.yml
├── Makefile
└── start.sh
```

## CLI Legacy

CLI lama tetap tersedia untuk workflow terminal:

```bash
python3 main.py hunt johndoe --save --format html
python3 main.py username johndoe --workers 60 --timeout 12 --save
python3 main.py email alice@example.com --save
python3 main.py domain example.com --save
python3 main.py doctor
```

Dashboard legacy local tanpa stack penuh masih bisa:

```bash
python3 main.py dashboard 127.0.0.1:8080
```

Untuk platform enterprise terbaru, gunakan Compose.

## Development Checks

```bash
python3 -m py_compile backend/main.py backend/tasks.py
cd frontend && npm ci && npm run build
docker compose config
docker compose build
```

## Thanks

Terima kasih untuk developer dan komunitas:

- reconurge/flowsint
- soxoj/maigret
- sherlock-project/sherlock
- mxrch/GHunt
- megadose/holehe

NexusIntel menghormati lisensi dan boundary project referensi. Tidak ada vendor code yang disalin ke runtime core.

## License

NexusIntel dirilis sebagai open source di bawah **Apache License 2.0**.

Copyright 2026 LogsOneX and NexusIntel contributors.

Lihat [LICENSE](LICENSE) untuk teks lisensi lengkap.
