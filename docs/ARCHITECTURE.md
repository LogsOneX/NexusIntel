# Architecture

NexusIntel memakai arsitektur root-first. Runtime platform masuk lewat `backend/main.py` untuk API dan `backend/tasks.py` untuk worker.

## Runtime Stack

```text
browser
  -> frontend nginx
  -> FastAPI backend/main.py
  -> Celery backend/tasks.py
  -> Redis broker + log pub/sub
  -> PostgreSQL graph store
  -> nexusrecon/core/modules/recon local OSINT code
```

## Backend Gateway

`backend/main.py` bertanggung jawab untuk:

- membuat table PostgreSQL saat startup,
- membuat dan membaca investigation,
- menulis manual entity,
- menghapus entity dan relationship terkait,
- dispatch transform ke Celery,
- mengirim graph payload ke frontend,
- membuka WebSocket `/api/v1/ws/logs/{task_id}` untuk live terminal HUD.

Model data utama:

- `investigations`
- `entities`
- `relationships`
- `task_records`
- `events`

## Worker Engine

`backend/tasks.py` adalah entrypoint Celery canonical. Worker menjalankan transform berikut:

- `run_nexusrecon_task`: bridge ke `nexusrecon.main.NexusRecon`, capture stdout/stderr, jalankan identity parser, lalu normalisasi profil publik menjadi graph.
- `run_email_google_task`: email/workspace recon public-source: regex validation, local part, domain, MX/TXT, DMARC, BIMI, disposable hint, provider hints, dan Gravatar hash check.
- `run_domain_task`: DNS/domain/IP recon: A/AAAA/CNAME/MX/NS/TXT/CAA, RDAP, reverse DNS, GeoIP/ASN hints, dan crt.sh subdomain read-only.
- `run_phone_task`: phone recon public-source: E.164 validation, country calling code, numbering-plan hint, dan policy guardrail.

Semua worker menulis entity/relationship ke PostgreSQL dan publish log ke Redis channel `logs:{task_id}`.

## Recon Validator Layer

`backend/recon_validators.py` adalah layer normalisasi sebelum data masuk graph. File ini menjaga semua artifact menjadi schema seragam:

- `type`
- `label`
- `value`
- `source`
- `confidence`
- `relationship`
- `data`

Validator aktif:

- `analyze_email_target`
- `analyze_network_target`
- `analyze_identity_target`
- `analyze_phone_target`

Validator ini bersifat public-source/read-only. Ia tidak menjalankan register/forgot-password probing, private API, credential checks, messaging-app account existence probing, atau rate-limit evasion.

## Frontend

Frontend canonical:

- `frontend/src/App.jsx` mounts `CommandCenter`.
- `frontend/src/components/CommandCenter.tsx` owns local routing/session and graph hub orchestration.
- `frontend/src/components/GraphCanvas.tsx` is the active Cytoscape visual link-analysis engine.
- `frontend/src/components/CustomNode.tsx`, `OraclePanel.tsx`, `PresenceBar.tsx`, and `TimelineView.tsx` are active graph/support components.
- `frontend/src/layouts/` contains shell/navigation/top intel bar components.
- `frontend/src/pages/` contains Dashboard, Workspace, Graph, Oracle, Settings, and Account pages.
- `frontend/src/components/{cases,common,entity,evidence,import,transforms}/` contains reusable analyst UI.
- `frontend/src/lib/` contains shared API, types, graph, confidence, format, and session helpers.
- `frontend/src/styles.css` contains the current premium graphite intelligence UI system.

Dashboard menyediakan:

- persistent left navigation and command palette,
- investigation cockpit with recent cases, lead queue, and coverage matrix,
- Cytoscape graph canvas as the main visual workspace,
- drag-and-drop entity pipeline for username, email, domain, IP, phone, and wallet,
- evidence-first entity inspector with overview, evidence, transforms, timeline, raw JSON, and notes,
- bottom live telemetry HUD subscribed to WebSocket task logs,
- right-click context menu for node transforms/playbooks.

## Legacy Compatibility

Folder berikut tetap dipakai sebagai engine lokal:

- `nexusrecon/`
- `core/`
- `modules/`
- `recon/`

`dashboard/server.py` tetap ada untuk dashboard legacy manual dari CLI. Untuk stack enterprise terbaru, gunakan Compose dan entrypoint root backend.

## Data Flow

```text
Target submit
  -> POST /api/v1/scans/nexusrecon
  -> FastAPI classifies target + creates investigation + root node
  -> Celery task queued by target type
  -> Worker runs validator + local OSINT method
  -> Worker writes normalized entities/edges
  -> Worker publishes Redis log events
  -> UI streams logs through WebSocket
  -> UI polls task graph and redraws Cytoscape
```

## Safety Model

Arsitektur ini public-source first:

- no paid API,
- no external repo runtime dependency,
- no credential or private session use,
- no register/forgot-password probing,
- active/aggressive mode tetap read-only dan hanya untuk target authorized.


## Queue Isolation

Celery worker dipisahkan secara eksplisit:

- `network_io`: HTTP, DNS, proxy-governed requests, crypto explorer, serverless invocation, watchlist sweep.
- `ml_gpu`: entity resolution, NLP/embedding/scoring workloads.

Pemisahan ini mencegah task ML yang berat menghabiskan memori worker scraping/I/O.

## Multiplayer Runtime

Graph collaboration menggunakan Yjs + `y-websocket` di frontend, Zustand untuk state lokal, dan Redis Pub/Sub backend untuk patch/presence bridging. Service `y-websocket` tersedia di Docker Compose dan expose default `127.0.0.1:1234`.
