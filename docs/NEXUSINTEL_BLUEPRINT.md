# NexusIntel Platform Blueprint

NexusIntel adalah stack OSINT standalone yang dibangun ulang secara independen. Flowsint, Maltego, OSINT Industries, Maigret, Sherlock, GHunt, dan Holehe dipakai sebagai referensi konsep produk dan pola kerja, bukan sebagai dependency atau vendor code. Stack utama berada di root: `backend/` dan `frontend/`.

## Stack

```text
React + Cytoscape UI
  -> Nginx reverse proxy
  -> FastAPI backend
  -> Celery task queue
  -> Redis broker + live event bus
  -> PostgreSQL graph store
  -> internal Python OSINT workers
  -> legacy bridges for nexusrecon/core/modules
```

## Data Flow

```text
UI submits target
  -> POST /api/investigations
  -> FastAPI creates investigation + root entity
  -> Celery worker starts autonomous modules
  -> modules normalize findings into entity/relationship JSON
  -> PostgreSQL stores graph nodes and edges
  -> Redis publishes live events
  -> UI receives SSE logs and refreshes Cytoscape graph
```

## Internal Modules

- `intel_planner`: builds collection plan, tasks, and guardrail context.
- `identity_profiler`: standalone username enumeration across public profile surfaces.
- `email_workspace_recon`: email format, local-part, domain, MX/TXT, DMARC/BIMI, public Gravatar hash/avatar check in active modes, and workspace provider hints.
- `domain_recon`: DNS, RDAP, certificate transparency in active modes, and mail/security posture notes.
- `website_surface_recon`: page fetch, title, internal links, exposed emails, tracker hints, and shallow active crawl.
- `phone_recon`: offline normalization and country-code hints.
- `legacy_nexusrecon_bridge`: wraps `nexusrecon.main.NexusRecon` and streams captured terminal output into live events.
- `legacy_analytics_bridge`: wraps `core.AnalyticsEngine`, executes `modules/*`, and normalizes the legacy graph into the PostgreSQL schema.

## Graph Schema

The platform stores OSINT output as:

- `investigations`: target, mode, status, summary.
- `entities`: typed nodes with confidence, source, properties.
- `relationships`: typed directed edges with confidence and properties.
- `events`: live execution history mirrored to Redis SSE channels.

Entity examples:

- `username`
- `email`
- `domain`
- `website`
- `url`
- `ip`
- `subdomain`
- `service`
- `developer_profile`
- `social_profile`
- `risk`
- `task`
- `signal`

## UI/UX Model

The first screen is the actual command graph:

- left rail: launch target, mode, cases, manual entity entry.
- center: large Cytoscape link-analysis canvas with search/filter.
- right rail: entity inspector and live terminal-style recon HUD.
- graph nodes can be selected, dragged, expanded, or removed.

## Guardrails

NexusIntel is public-source and defensive by design:

- no paid API dependency,
- no cloned external OSINT repo dependency,
- no credential stuffing,
- no private API abuse,
- no password-reset or registration probing,
- active/aggressive mode is read-only and intended for owned or authorized targets.

## Deployment

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8080
```
