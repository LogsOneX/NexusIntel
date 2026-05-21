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
- Mode agresif tetap read-only dan harus dipakai hanya untuk target authorized.
- Memanfaatkan analisis pasif terhadap tanda tanda publik (Public Sign-up Response Signatures) dan penjelajahan dokumen web terbuka (Public Web Document/DOM Metadata Parsing) yang berada dalam koridor investigasi pasif dan read-only tanpa memodifikasi data akun target atau memicu notifikasi sistem.
- Tidak ada register/forgot-password/password-reset probing yang mengirim email, mengunci akun, memicu OTP/2FA, membuat sesi target, atau mengubah state layanan pihak ketiga.
- Tidak ada bypass, spam, scraping tertutup, private API abuse, credential stuffing, atau rate-limit evasion.

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

Buka command center:

```text
http://127.0.0.1:8080
```

Login lokal default untuk development:

```text
username: admin
password: nexusintel
```

Ganti credential sebelum operasi nyata:

```bash
NEXUS_ADMIN_USER=operator NEXUS_ADMIN_PASSWORD="passphrase-kuat" NEXUS_AUTH_SECRET="secret-panjang" docker compose up -d --build
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

## Command Center Flow

UI terbaru berjalan sebagai multi-page Intelligence Command Center dengan protected local login, persistent sidebar, dashboard hub, workspace/case management, network graph, AI Oracle, settings, dan account page. Core graph memakai `GraphCanvas` berbasis Cytoscape dengan edge-to-edge tactical canvas, unified master toolbar, integrated launch form, drag-and-drop entity palette, right-click Logic Flow, Playbooks, Smart Selector, collapsible data drawer, collapsible terminal HUD, Timeline Mode, dan Export Intelligence report.

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

- Email: regex validation, local-part/domain split, MX/TXT/DMARC/BIMI, disposable-domain hint, public workspace posture, GET-only public sign-up document signatures, dan guardrail state-changing probes.
- Domain/IP: DNS, RDAP, crt.sh, reverse DNS, GeoIP/ASN hint via free source.
- Username/nama: shape validation, name-part split, public profile candidate URLs, title/body/metadata false-positive filtering, dan guardrail sensitive inference.
- Phone: strict E.164, country calling code, public numbering-plan line hint, dan public deep-link web document metadata tanpa klaim registrasi.

NexusIntel tidak melakukan password-reset probing, OTP trigger, account creation, private API usage, contact-sync, SMTP VRFY/RCPT, atau rate-limit evasion.

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


## AI Oracle dan BYOK

NexusIntel sekarang punya `/oracle` dan Oracle panel di `/graph` serta `/workspace`. Tanpa LLM eksternal, Oracle memakai local rule-based engine untuk highlight entity dan briefing dasar. Untuk LLM lokal/remote, buka Settings atau set env:

```bash
NEXUS_LLM_PROVIDER=ollama
NEXUS_LLM_ENDPOINT=http://localhost:11434
NEXUS_LLM_MODEL=llama3.1
```

Optional BYOK keys tersedia untuk Shodan, IntelX, dan VirusTotal di Settings. Core OSINT tetap berjalan tanpa paid API.


## Ghost Engine: Async Public Presence Resolution

Backend terbaru memiliki `backend/modules/` sebagai asynchronous public-source recon engine:

- `identity_recon.py`: concurrent public profile checks dengan false-positive filtering berbasis status code, title/body/DOM metadata markers, username evidence, dan optional local JSON catalog via `NEXUS_PLATFORM_CATALOG` untuk registry 500+ surface internal.
- `workspace_recon.py`: non-blocking async DNS MX/TXT/DMARC/BIMI/MTA-STS, provider posture Google/Microsoft/Proton/Zoho/Fastmail, Microsoft tenant hint, public workspace documents, dan Gravatar hash.
- `email_recon.py`: email posture resolver yang memecah local-part/domain, menjalankan workspace + username pivot, dan menganalisis GET-only public sign-up document signatures tanpa submit target email.
- `phone_recon.py`: E.164, carrier/geolocation/timezone via `phonenumbers`, public numbering-plan hints, dan public deep-link DOM/OpenGraph metadata sebagai pivot tanpa klaim registrasi akun.

Celery worker menjalankan engine ini via `asyncio.run()` dan men-stream temuan ke Redis/WebSocket saat ditemukan. Rate-limit handling memakai exponential backoff; tidak ada bypass atau rate-limit evasion. Optional egress proxy tunggal bisa dipakai dengan `NEXUS_EGRESS_PROXY` untuk environment internal.
