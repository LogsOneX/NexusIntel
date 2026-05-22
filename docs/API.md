# API Reference

Base path:

```text
/api/v1
```

Compatibility health path:

```text
/api/health
```

## Health

```text
GET /api/v1/health
```

Returns API status and timestamp.

## Auth

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

Login body:

```json
{
  "username": "admin",
  "password": "nexusintel"
}
```

Protected management/oracle endpoints expect:

```text
Authorization: Bearer <token>
```

## Cases, Settings, and Oracle

```text
GET   /api/v1/cases
PATCH /api/v1/cases/{investigation_id}
GET   /api/v1/settings
PUT   /api/v1/settings
POST  /api/v1/oracle/chat
POST  /api/v1/oracle/briefing
```

Oracle chat body:

```json
{
  "prompt": "Show high-confidence IPs",
  "investigation_id": "uuid",
  "graph_state": { "nodes": [], "edges": [] },
  "node": null
}
```

Oracle responses include `reply`, `commands`, `metrics`, and provider metadata. UI commands include:

- `highlight_type`: fade graph to a specific entity type, optionally with `minConfidence`.
- `clear_highlight`: restore normal graph opacity.
- `suggest_transform`: return a recommended next transform such as `maigret_username`, `email_footprint`, `domain_recon`, `phone_recon`, or `full_identity_pipeline`.

When no LLM is configured, `/api/v1/oracle/chat` falls back to the local NexusIntel investigation brain. It does not invent findings; it only reasons from the submitted graph state, active node, and stored investigation graph.

## Investigations

```text
POST   /api/v1/investigations
GET    /api/v1/investigations
GET    /api/v1/investigations/{investigation_id}/graph
GET    /api/v1/investigations/{investigation_id}/health
GET    /api/v1/investigations/{investigation_id}/intelligence
DELETE /api/v1/investigations/{investigation_id}
DELETE /api/v1/cases/{investigation_id}
```

Create body:

```json
{
  "target": "alice@example.com",
  "target_type": "email",
  "mode": "standard"
}
```

`target_type` is optional. The backend can classify username, email, domain, IP, and phone-like targets. `POST /api/v1/investigations` creates a blank/ready case with a root node. `POST /api/v1/scans/nexusrecon` creates a case and immediately queues the recon worker. The health endpoint returns Case Hygiene score, coverage, weak nodes, isolated nodes, recommendations, and embedded graph intelligence. The intelligence endpoint returns risk posture, source reliability, lead queue, entity risk tags, communities, and a compact case dossier.

## Quick Scan

```text
POST /api/v1/scans/nexusrecon
```

Creates an investigation and immediately queues the correct OSINT pipeline by target type.

```json
{
  "target": "alice@example.com",
  "mode": "standard"
}
```

Response includes:

- `investigation_id`
- `task_id`
- initial `graph`

## Entities

```text
POST   /api/v1/entities
DELETE /api/v1/investigations/{investigation_id}/entities/{node_id}
```

Create body:

```json
{
  "investigation_id": "uuid",
  "type": "email",
  "label": "alice@example.com",
  "value": "alice@example.com",
  "source_id": "optional-parent-node-id",
  "relationship_type": "manual_pivot",
  "data": {
    "note": "manual pivot"
  }
}
```

## Transforms

```text
POST /api/v1/transforms
```

Body:

```json
{
  "investigation_id": "uuid",
  "node_id": "uuid",
  "transform": "email_footprint",
  "mode": "standard"
}
```

Supported transform families:

- `tier_1_major_socials`
- `tier_2_tech_dev`
- `tier_3_gaming_forums`
- `tier_4_deep_sweep`
- `maigret_username`
- `sherlock_username`
- `legacy_nexusrecon`
- `username_presence`
- `email_footprint`
- `holehe_email`
- `google_osint`
- `workspace_recon`
- `domain_recon`
- `dns_recon`
- `website_recon`
- `network_recon`
- `ip_recon`
- `reverse_dns`
- `phone_recon`
- `e164_phone`
- `carrier_lookup`
- `numbering_plan`
- `full_identity_pipeline`
- `identity_macro`
- `email_macro`
- `autonomous_identity_pipeline`

Transform routing:

- identity transforms route to `run_nexusrecon_task`; tier transforms constrain the async identity resolver to the exact cluster and only `tier_4_deep_sweep` runs the legacy full sweep.
- email/workspace transforms route to `run_email_google_task`.
- domain/IP/network transforms route to `run_domain_task`.
- phone transforms route to `run_phone_task`.

All transform workers call `backend/recon_validators.py` before returning graph updates. Username/email context menus expose four clustered tiers: Major Socials, Tech & Dev, Gaming & Forums, and Deep Sweep. Relationships now include numeric `confidence_level` (0-100) for UI edge thickness and filtering.

Celery workers also invoke `backend/modules/` Ghost Engine resolvers. These stream progress through `WS /api/v1/ws/logs/{task_id}` immediately as public signals are found, while final artifacts are persisted to the graph database.

## Tasks

```text
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/graph
```

Use task graph polling while a transform runs.

## Live Logs

```text
WS /api/v1/ws/logs/{task_id}
```

The WebSocket streams JSON lines:

```json
{
  "task_id": "uuid",
  "level": "info",
  "message": "Starting domain recon",
  "payload": {},
  "time": "2026-05-18T00:00:00Z"
}
```
