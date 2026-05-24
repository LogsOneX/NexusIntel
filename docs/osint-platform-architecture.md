# NexusIntel OSINT Platform Architecture

## Frontend

- React/Vite command center.
- `CommandCenter.tsx` mengelola route lokal, session, graph hub, telemetry, drawers, dan command palette.
- Core pages: Dashboard, Identity Search, Network Graph, Workspace, Threat Watchlist, Evidence Vault, Transform Library, Oracle, Settings, Account.
- Graph menggunakan Cytoscape dengan overlay drawer untuk Case Dock, Entity Inspector, Terminal, dan Entity Palette.

## Backend

- FastAPI API gateway di `backend/main.py`.
- PostgreSQL menyimpan investigations, entities, relationships, tasks, events, settings, provenance, audit logs, dan watchlists.
- Redis digunakan untuk Celery broker/backend dan WebSocket log bus.
- Celery worker di `backend/tasks.py` menjalankan transform, legacy NexusRecon bridge, watchlist sweep, crypto task, dan entity resolution queue isolation.

## OSINT Adapter SDK

- `backend/osint/types.py` mendefinisikan adapter, artifact, evidence, confidence, transform, dan run context.
- `backend/osint/registry.py` mengekspos transform registry.
- Adapter menghasilkan artifact evidence-first; artifact router memisahkan ENTITY, EVIDENCE, SIGNAL, CANDIDATE, COMPLIANCE, dan NOISE.

## Evidence Vault

- Raw proof disimpan sebagai `DataProvenance` dengan source, URI, SHA-256, content type, size, metadata, dan timestamp.
- API utama: `GET /api/v1/evidence`, `GET /api/v1/evidence/{id}`, `GET /api/v1/investigations/{id}/evidence`.

## Confidence Scoring

- Confidence mempertimbangkan source reliability, directness, freshness, corroboration, contradiction, dan false-positive risk.
- Label operasional:
  - A1: direct official/public source.
  - A2: strong public technical evidence.
  - B1: multiple independent public signals.
  - B2: single weak public signal.
  - C: candidate lead only.

## Audit Trail

- FastAPI middleware menulis audit logs untuk request API.
- Audit mencatat operator, action/path, target entity jika tersedia, IP, status code, dan timestamp.

## Watchlist

- Watchlist menyimpan authorized target, type, interval, enabled state, last delta, dan last checked timestamp.
- Celery Beat menjalankan passive sweep dan mengirim `SYSTEM_ALERT` ke telemetry saat ada delta.
