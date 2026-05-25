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

## Professional OSINT Platform Upgrade

NexusIntel sekarang diarahkan sebagai OSINT Command Center evidence-first, bukan sekadar scanner. Riset produk internal `Riset Mendalam Platform OSINT & Intelijen.pdf` dipakai sebagai referensi utama untuk menggabungkan pola kerja profesional berikut:

- **OSINT Industries style selector workflow:** satu input email/phone/username/domain/IP/wallet, feedback cepat, kandidat dipisahkan dari temuan terverifikasi, dan zero false-positive mindset.
- **Maltego style graph transforms:** setiap entity bisa dipivot, relasi punya confidence dan alasan, graph tetap menjadi ruang link-analysis utama.
- **Social Links style workspace:** case folder, evidence coverage, lead queue, noise bin, compliance log, dan export analyst packet.
- **StealthMole/SOCRadar style posture:** watchlist monitoring pasif, CTI connector BYOK/legal, alert berbasis delta, tanpa illegal dark-web crawling atau raw credential storage.
- **Palantir style lineage:** entity resolution, provenance, audit trail, confidence explainability, dan AI Oracle yang hanya merangkum/triage evidence.

Core pages:

- `Dashboard`: investigation cockpit, universal selector, coverage gaps, recent cases, next actions.
- `Identity Search`: OSINT Industries-style lookup untuk email, phone, username, domain, IP, dan crypto wallet.
- `Network Graph`: Maltego-style visual graph canvas dengan transforms, drawers, evidence-first inspector, dan telemetry.
- `Workspace`: case management, notes, operator assignment, AI briefing.
- `Threat Watchlist`: passive monitoring untuk authorized targets dan connector-backed CTI indicators.
- `Evidence Vault`: raw proof browser dengan hash, source URL, timestamp, dan legal note.
- `Transform Library`: registry transform yang menampilkan input/output, passive status, API-key requirement, dan disabled reason.

Safety model tetap ketat: tidak ada password reset probing, OTP triggering, credential stuffing, private API abuse, CAPTCHA bypass, illegal scraping, raw stolen credential storage, atau synthetic intelligence di graph.

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


## Advanced Architecture Modules

NexusIntel sekarang memiliki foundation 6 modul lanjutan yang tetap read-only dan public-source:

- Egress governance: Redis proxy rotator, jitter 1.2-4.7 detik, exponential backoff, dan serverless invoker tanpa simulasi; jika endpoint tidak dikonfigurasi, tidak ada artefak graph dibuat.
- Chain of Custody: RAW payload store, SHA-256 provenance, verify endpoint, dan audit middleware.
- Watchlist Engine: persistent surveillance on/off, Celery Beat, dan `SYSTEM_ALERT` saat graph signature berubah.
- Deep Entity Resolution: queue `ml_gpu`, scoring identity, permanent/hypothetical edge decision.
- Multiplayer Canvas: Yjs + y-websocket + Zustand + Redis Pub/Sub patch/presence.
- Crypto Wallet Tracker: wallet node + transaction edges hanya dari explorer/RPC publik yang terverifikasi; tidak ada transaksi dummy.

Detail lengkap ada di `docs/NSA_GRADE_MODULES.md`.

## Command Center Flow

UI terbaru berjalan sebagai multi-page Intelligence Command Center dengan protected local login, persistent sidebar, dashboard hub, workspace/case management, network graph, AI Oracle, settings, dan account page. Core graph memakai `GraphCanvas` berbasis Cytoscape dengan edge-to-edge tactical canvas, unified master toolbar, integrated launch form, drag-and-drop entity palette, right-click Logic Flow, Playbooks, Smart Selector, collapsible data drawer, collapsible terminal HUD, Timeline Mode, Export Intelligence report, explicit investigation lifecycle dock untuk select/new/clear/delete case tanpa auto-load case lama, Time-Machine temporal playback, flat correlation heat indicators, dan passive threat auto-tagging.

1. Buka Network Graph; canvas mulai detached kecuali URL berisi `?case=<id>`.
2. Pilih investigation dari lifecycle dock, buat blank investigation, atau ketik target username/email/domain/IP/phone di master toolbar.
3. Klik `Add Entity` untuk menambahkan target ke canvas/case tanpa lookup dan tanpa menjalankan worker.
4. Klik `Lookup` hanya jika operator memang ingin menjalankan pipeline OSINT public-source untuk target tersebut.
5. API mengklasifikasi target dan membuat investigation + root entity jika belum ada case aktif.
6. Worker Celery menjalankan pipeline OSINT public-source sesuai tipe target.
7. `backend/recon_validators.py` memvalidasi, memecah, dan menormalisasi artifact menjadi schema graph.
8. Worker menulis node/edge ke PostgreSQL dan menyiarkan log real-time ke Redis.
9. UI menerima WebSocket telemetry di terminal HUD dan polling task graph sampai selesai, jadi node muncul langsung tanpa pindah halaman.
10. Case Hygiene module menghitung health score, weak nodes, isolated nodes, coverage gaps, dan rekomendasi transform.
11. Investigator bisa klik/right-click/drag-drop entity untuk transform lanjutan secara eksplisit.

Transform utama:

- Username/account pivots: `username_to_email`, `username_to_accounts`, plus 4 tier eksekusi `tier_1_major_socials`, `tier_2_tech_dev`, `tier_3_gaming_forums`, dan `tier_4_deep_sweep` agar worker tidak langsung menembak 100+ platform.
- Email/account/workspace recon: `email_to_account`, `email_to_domain`, konsep Holehe/GHunt yang dibatasi ke DNS, provider hints, Gravatar hash, dan public workspace indicators.
- Domain/DNS recon: A/AAAA/CNAME/MX/NS/TXT/CAA, RDAP, mail posture, service hints, dan crt.sh subdomain read-only.
- IP recon: reverse DNS, RDAP allocation, dan GeoIP/ASN hint dari sumber gratis.
- Phone recon: `phone_to_email`, `phone_to_account`, E.164 validation, country calling code, public deep-link metadata, dan offline public numbering-plan hint.
- Manual entity builder + drag-and-drop entity pipeline: tambah entity dan link langsung ke selected node tanpa auto-lookup; lookup hanya terjadi lewat tombol `Lookup` atau context transform.
- Case Hygiene + Graph Intelligence: health score, risk posture, source reliability, communities, lead queue, weak/isolated entity detection, dan next-action recommendation untuk menjaga kualitas investigation.
- Time-Machine slider: replay graph berdasarkan `created_at` node/edge tanpa remount canvas.
- Passive auto-tagging: IP private/bogon diberi `[INTERNAL]`, domain dengan phishing keywords diberi `[SUSPICIOUS]`, dan node ber-degree tinggi diberi border amber/red flat.


## Evidence Quality Gate

NexusIntel memakai prinsip **no synthetic intelligence by default**:

- Tidak ada node/edge dari dry-run, dummy, synthetic, simulated, atau placeholder payload.
- Worker yang tidak menemukan sumber publik terverifikasi akan selesai sebagai `verified=false` dan graph tidak berubah.
- Artefak yang masuk graph membawa metadata `evidence_grade`, `source`, `source_url`, dan/atau `payload_sha256` jika tersedia.
- Grade `A1` hanya dipakai untuk respons publik terverifikasi dengan sumber yang bisa diaudit; hasil lain harus dianggap `UNVERIFIED`.

## Safe Pivot Policy

NexusIntel tidak menjalankan password-reset probing, recovery-flow scraping, contact-sync simulation, 2FA triggering, atau endpoint internal Google untuk mengungkap data akun. Pivot email/phone/Google dibatasi ke public-source yang bisa diverifikasi atau explicit public profile URL yang diberikan operator. Tidak ada dry-run/dummy intelligence yang boleh menambah node ke graph. Censored entity types (`censored_email`, `censored_phone`) hanya dipakai untuk menandai hint parsial yang sudah tersedia secara authorized, bukan untuk memicu recovery flow.

## High-Density Terminal Graph Polish

Network Graph sekarang memakai node card flat dengan SVG data-uri iconography untuk username, email, domain, IP, phone, crypto wallet, transaction, censored identifiers, Google reviews, dan locations. Context menu memakai viewport-aware bounds dengan z-index tinggi agar tidak overlap/clip, serta crypto transforms `check_wallet_balance` dan `trace_transactions`. Toolbar memakai divider vertikal 1px seperti hardware dashboard dan slider temporal tetap flat monokrom.

## Deep Recon Validator

`backend/recon_validators.py` adalah parser public-source baru yang berjalan sebelum data dikirim ke UI:

- Email: regex validation, local-part/domain split, MX/TXT/DMARC/BIMI, disposable-domain hint, public workspace posture, GET-only public sign-up document signatures, dan guardrail state-changing probes.
- Domain/IP: DNS, RDAP, crt.sh, reverse DNS, GeoIP/ASN hint via free source.
- Username/nama: shape validation, name-part split, public profile candidate URLs, title/body/metadata false-positive filtering, dan guardrail sensitive inference.
- Phone: strict E.164, country calling code, public numbering-plan line hint, dan public deep-link web document metadata tanpa klaim registrasi.

NexusIntel tidak melakukan password-reset probing, OTP trigger, account creation, private API usage, contact-sync, SMTP VRFY/RCPT, atau rate-limit evasion.

## Analyst Enrichment Pipeline

Network Graph sekarang punya pipeline enrichment untuk selected entity dan pending entity input. Panel ini menampilkan tipe entity, transform yang tersedia, transform rekomendasi, transform disabled beserta alasan, source coverage, confidence baseline, lead queue, coverage matrix, noise killer, correlation engine, dan export analyst packet. Node drawer wajib menampilkan source URL, timestamp, raw hash/evidence ref, confidence reason, dan legal note ketika tersedia.

Endpoint utama:

```text
GET  /api/v1/investigations/{id}/analyst-pipeline
POST /api/v1/investigations/{id}/correlate
GET  /api/v1/investigations/{id}/exports/analyst-packet?format=html|pdf|json|csv|graph_json
```

Detail: [Analyst Enrichment Pipeline](docs/analyst-enrichment-pipeline.md).

## OSINT Adapter SDK dan Evidence Vault

NexusIntel sekarang punya adapter SDK di `backend/osint/` untuk transform public-source yang evidence-first. Registry tersedia di `GET /api/v1/transforms/registry`, execution path baru di `POST /api/v1/transforms/run`, dan setiap artifact yang dipersist membawa `source`, `source_url`, `fetched_at`, `confidence_score`, `confidence_reason`, `evidence_grade`, `raw_evidence_ref`, `legal_basis`, dan `public_source_note`.

Evidence vault menyimpan raw HTML/JSON/text/header metadata dengan SHA-256 deduplication dan dapat dibuka dari Entity Data drawer. Tidak ada synthetic/dummy intelligence yang boleh dimasukkan ke case graph.

Dokumentasi operator dan developer:

- [OSINT Adapter SDK](docs/osint-adapter-sdk.md)
- [OSINT Connectors](docs/osint-connectors.md)
- [Evidence Vault](docs/osint-evidence-vault.md)
- [Confidence Scoring](docs/osint-confidence-scoring.md)
- [Google Maps Public Evidence](docs/google-maps-public-evidence.md)
- [Impersonation Investigation Mode](docs/impersonation-investigation-mode.md)
- [Analyst Enrichment Pipeline](docs/analyst-enrichment-pipeline.md)
- [Operator Playbook](docs/operator-playbook.md)

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
GET  /api/v1/transforms/registry
POST /api/v1/transforms/run
GET  /api/v1/transforms/runs/{run_id}
GET  /api/v1/evidence/{id}
GET  /api/v1/investigations/{id}/evidence
GET  /api/v1/investigations/{id}/analyst-pipeline
POST /api/v1/investigations/{id}/correlate
GET  /api/v1/investigations/{id}/exports/analyst-packet
POST /api/v1/importers/preview
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
│   ├── queues.py
│   ├── modules/         # async OSINT runtime modules used by API/workers
│   ├── osint/           # adapter SDK, registry, evidence/scoring/importers/reporting
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx
│   ├── src/components/CommandCenter.tsx
│   ├── src/components/GraphCanvas.tsx
│   ├── src/components/CustomNode.tsx
│   ├── src/components/OraclePanel.tsx
│   ├── src/components/PresenceBar.tsx
│   ├── src/components/TimelineView.tsx
│   ├── src/components/{cases,common,entity,evidence,import,transforms}/
│   ├── src/layouts/
│   ├── src/pages/
│   ├── src/lib/
│   └── src/styles.css
├── core/                # legacy-compatible local CLI engine, graph, flows, reports
├── modules/             # legacy CLI public-source OSINT modules
├── nexusrecon/          # NexusRecon class bridge used by backend/tasks.py
├── recon/               # platform registry and standalone scanners
├── dashboard/           # legacy local dashboard served by python3 main.py dashboard
├── docs/
├── tests/
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

NexusIntel sekarang punya `/oracle` dan Oracle panel kontekstual di `/graph` serta `/workspace`. Tanpa LLM eksternal, Oracle memakai local investigation brain berbasis aturan untuk membaca JSON graph state, menghitung posture kasus, mengurutkan pivot kuat, memberi rekomendasi transform berikutnya, highlight entity type, clear highlight, dan flag collection gap. Panel Oracle juga punya quick prompts untuk summary, next transform, high-confidence infrastructure, dan gap analysis.

### Evidence-First Local Investigator Brain

NexusIntel menambahkan `backend/investigator/` sebagai otak investigasi lokal yang RAM/storage friendly. Engine ini deterministic-first: validator, evidence reasoner, noise killer, hypothesis engine, planner, memory, dan report readiness berjalan sebelum bantuan LLM. LLM lokal hanya dipakai untuk briefing dan planning, tidak boleh mengubah status finding tanpa evidence.

Endpoint utama:

- `POST /api/v1/oracle/chat`
- `GET /api/v1/investigations/{id}/validation`
- `POST /api/v1/investigations/{id}/planner/next-actions`
- `POST /api/v1/investigations/{id}/hypotheses/generate`
- `GET /api/v1/investigations/{id}/report-readiness`
- `GET /api/v1/investigator/model-status`

Mode AI lokal:

```bash
NEXUS_AI_MODE=rules
NEXUS_AI_ENDPOINT=http://localhost:11434
NEXUS_AI_MODEL=
NEXUS_AI_RAM_PROFILE=tiny
```

`rules` adalah default dan tidak membutuhkan model. `ollama`, `llamacpp`, dan `openai_compatible` tersedia jika operator sudah menjalankan runtime/model sendiri. NexusIntel tidak mengunduh model otomatis dan tidak mengirim raw evidence payload besar ke model; context dibatasi ke compact evidence cards, IDs, source URLs, hash, status validasi, dan ringkasan kasus.

### Analyst Workbench: Evidence OS, Playbooks, Correlation

NexusIntel sekarang menambahkan analyst workbench di atas Investigator Brain:

- Evidence OS 2.0: evidence map, excerpt, SHA-256 verification, diff repeated captures, dan unsupported finding warnings.
- Advanced Correlation: weighted correlation untuk shared username/avatar/favicon/link/email domain/display name/bio/location/analytics/cert/infrastructure dengan contradiction penalty.
- Playbook Engine: `email_investigation`, `username_investigation`, `domain_impersonation`, `phone_investigation`, `crypto_wallet_investigation`, `website_clone_detection`, `threat_actor_infrastructure_mapping`, dan `report_preparation`.
- Connector Marketplace: status konfigurasi GitHub, HIBP, VirusTotal, Shodan, Censys, SecurityTrails, URLScan, Google Maps/Places, Twilio Lookup, OpenCorporates, dan custom HTTP adapter placeholder.

Endpoint utama workbench:

- `GET /api/v1/investigations/{id}/evidence-map`
- `GET /api/v1/evidence/{evidence_id}/excerpt`
- `POST /api/v1/evidence/{evidence_id}/verify`
- `POST /api/v1/evidence/diff`
- `GET /api/v1/investigations/{id}/correlations`
- `POST /api/v1/investigations/{id}/correlate`
- `GET /api/v1/playbooks`
- `POST /api/v1/investigations/{id}/playbooks/{playbook_id}/plan`
- `POST /api/v1/investigations/{id}/playbooks/{playbook_id}/run`
- `GET /api/v1/connectors`

Untuk LLM lokal/remote, buka Settings atau set env:

```bash
NEXUS_LLM_PROVIDER=ollama
NEXUS_LLM_ENDPOINT=http://localhost:11434
NEXUS_LLM_MODEL=llama3.1
```

Optional BYOK keys tersedia untuk GitHub, HIBP, URLScan, Google Maps Places, Shodan, Censys, IntelX, VirusTotal, Twilio, dan NumVerify di Settings. Core OSINT tetap berjalan tanpa paid API.


## Ghost Engine: Async Public Presence Resolution

Backend terbaru memiliki `backend/modules/` sebagai asynchronous public-source recon engine:

- `identity_recon.py`: concurrent public profile checks dengan false-positive filtering berbasis status code, title/body/DOM metadata markers, username evidence, dan optional local JSON catalog via `NEXUS_PLATFORM_CATALOG` untuk registry 500+ surface internal.
- `workspace_recon.py`: non-blocking async DNS MX/TXT/DMARC/BIMI/MTA-STS, provider posture Google/Microsoft/Proton/Zoho/Fastmail, Microsoft tenant hint, public workspace documents, dan Gravatar hash.
- `email_recon.py`: email posture resolver yang memecah local-part/domain, menjalankan workspace + username pivot, dan menganalisis GET-only public sign-up document signatures tanpa submit target email.
- `phone_recon.py`: E.164, carrier/geolocation/timezone via `phonenumbers`, public numbering-plan hints, dan public deep-link DOM/OpenGraph metadata sebagai pivot tanpa klaim registrasi akun.

Celery worker menjalankan engine ini via `asyncio.run()` dan men-stream temuan ke Redis/WebSocket saat ditemukan. Rate-limit handling memakai exponential backoff; tidak ada bypass atau rate-limit evasion. Optional egress proxy tunggal bisa dipakai dengan `NEXUS_EGRESS_PROXY` untuk environment internal.
