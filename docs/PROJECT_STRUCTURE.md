# Project Structure

This document reflects the cleaned NexusIntel repository layout as of 2026-05-24.

## Active Runtime Tree

```text
.
├── backend/
│   ├── main.py                 # FastAPI API gateway and WebSocket routes
│   ├── tasks.py                # Celery workers and transform orchestration
│   ├── queues.py               # Celery queue routing constants
│   ├── recon_validators.py     # Normalization/validation layer
│   ├── modules/                # Async OSINT runtime modules used by API/workers
│   ├── osint/                  # Adapter SDK, registry, evidence, scoring, importers, reporting
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx             # React mount -> CommandCenter
│   ├── src/components/
│   │   ├── CommandCenter.tsx   # Session/manual routing + graph hub orchestration
│   │   ├── GraphCanvas.tsx     # Active Cytoscape visual link-analysis canvas
│   │   ├── CustomNode.tsx      # Entity palette/icon helpers
│   │   ├── OraclePanel.tsx
│   │   ├── PresenceBar.tsx
│   │   ├── TimelineView.tsx
│   │   ├── cases/
│   │   ├── common/
│   │   ├── entity/
│   │   ├── evidence/
│   │   ├── import/
│   │   └── transforms/
│   ├── src/layouts/            # AppShell, SidebarNav, TopIntelBar
│   ├── src/pages/              # Dashboard, Workspace, Graph, Oracle, Settings, Account
│   ├── src/lib/                # API, types, graph, confidence, format, storage helpers
│   ├── src/realtime/           # Yjs/CRDT collaboration helpers
│   ├── src/store/              # Zustand stores
│   ├── src/styles.css          # Premium graphite intelligence UI system
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── tsconfig.json
│   └── Dockerfile
├── core/                       # Legacy-compatible CLI engine/flows/graph/reporting
├── modules/                    # Legacy CLI OSINT modules loaded by core.engine
├── nexusrecon/                 # NexusRecon class bridge imported by backend/tasks.py
├── recon/                      # Platform registry and standalone scanner compatibility
├── dashboard/                  # Legacy local dashboard used by python3 main.py dashboard
├── docs/                       # Architecture, operation, SDK, evidence, cleanup docs
├── tests/                      # Python SDK/service tests
├── main.py                     # Legacy CLI entry point
├── docker-compose.yml          # Full stack orchestration
├── Makefile                    # Common run/stop/dev commands
├── start.sh                    # Local startup helper
├── requirements.txt            # Legacy CLI requirements
└── pyproject.toml
```

## Runtime Entry Points

- Backend API: `backend/main.py`
- Celery workers: `backend/tasks.py`
- Frontend app: `frontend/src/App.jsx` -> `frontend/src/components/CommandCenter.tsx`
- Graph engine: `frontend/src/components/GraphCanvas.tsx`
- Legacy CLI: `main.py`
- Legacy local dashboard: `dashboard/server.py` via `python3 main.py dashboard 127.0.0.1:8080`
- Compose stack: `docker-compose.yml`

## Legacy Compatibility Notes

The directories `core/`, `modules/`, `nexusrecon/`, `recon/`, and `dashboard/` are intentionally kept. They are referenced by the root CLI, backend Celery bridge, Makefile, and documentation. Do not delete them unless the CLI compatibility contract is retired.

## Generated/Runtime Directories Ignored By Git

- Python caches: `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- Node/build outputs: `node_modules/`, `frontend/node_modules/`, `dist/`, `frontend/dist/`, `.vite/`
- Local runtime: `data/`, `logs/`, `tmp/`, `temp/`, `dump.rdb`
- NexusIntel outputs: `results/`, `reports/generated/`, `exports/`, `screenshots/`, `.nexusrecon/`, `*.sqlite`, `*.db`
- Secret material: `.env*` except `.env.example`, `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.pfx`, `secrets/`, `credentials.json`
