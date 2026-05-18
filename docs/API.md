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

## Investigations

```text
POST /api/v1/investigations
GET  /api/v1/investigations
GET  /api/v1/investigations/{investigation_id}/graph
```

Create body:

```json
{
  "target": "alice@example.com",
  "target_type": "email",
  "mode": "standard"
}
```

`target_type` is optional. The backend can classify username, email, domain, and phone-like targets.

## Quick Scan

```text
POST /api/v1/scans/nexusrecon
```

Creates an investigation and immediately queues the NexusRecon identity sweep.

```json
{
  "target": "johndoe",
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

- `maigret_username`
- `sherlock_username`
- `legacy_nexusrecon`
- `email_footprint`
- `holehe_email`
- `google_osint`
- `workspace_recon`
- `domain_recon`
- `dns_recon`
- `website_recon`

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
