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

- `run_nexusrecon_task`: bridge ke `nexusrecon.main.NexusRecon`, capture stdout/stderr, lalu normalisasi profil publik menjadi graph.
- `run_email_google_task`: email/workspace recon public-source: local part, domain, MX/TXT, DMARC, BIMI, provider hints, dan Gravatar hash check.
- `run_domain_task`: DNS/domain recon: A/AAAA/MX/NS/TXT/CAA dan candidate subdomain read-only untuk mode standard/aggressive.

Semua worker menulis entity/relationship ke PostgreSQL dan publish log ke Redis channel `logs:{task_id}`.

## Frontend

Frontend canonical:

- `frontend/src/components/Dashboard.tsx`
- `frontend/src/components/GraphCanvas.tsx`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`

Dashboard menyediakan:

- left console untuk target acquisition, recon mode, manual entity, dan investigation list,
- central Cytoscape graph canvas sebagai workspace utama,
- right deep data drawer untuk structured JSON intelligence,
- bottom terminal HUD yang subscribe ke WebSocket task log,
- right-click context menu untuk menjalankan transform dari node.

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
  -> FastAPI creates investigation + root node
  -> Celery task queued
  -> Worker runs local OSINT method
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
