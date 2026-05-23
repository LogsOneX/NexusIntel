# Analyst Enrichment Pipeline

The Analyst Enrichment Pipeline turns a selected entity into an evidence-first operator view. It is available through:

```text
GET  /api/v1/investigations/{id}/analyst-pipeline?entity_id={node_id}
POST /api/v1/investigations/{id}/correlate
GET  /api/v1/investigations/{id}/exports/analyst-packet?format=html|pdf|json|csv|graph_json
```

## Entity Enrichment

For the active entity NexusIntel shows:

- entity type
- available transforms
- recommended transforms
- disabled transforms with reason
- source coverage status
- confidence baseline
- source URL, timestamp, raw evidence hash, confidence reason, and legal note

Manual or legacy nodes are explicitly treated as unverified until an evidence-backed transform attaches proof.

## Live Transform Telemetry

Registered SDK transforms stream:

- source queried
- result count
- raw evidence captured
- confidence baseline changes
- low-confidence/noise count

## Lead Queue

The lead queue prioritizes:

- strongest pivots
- unverified but interesting pivots
- possible same actor links
- contradictions/noise
- high-value next actions from collection gaps

## Correlation Engine

Correlation uses weighted public-source features and creates `possible_same_actor` edges only for analyst review. Features include same avatar hash, username, external links, domain/email, display name, location text, analytics IDs, favicon hash, and certificate metadata. Scores below automatic identity confidence remain hypothetical.

## Noise Killer

Noise Killer flags shared CDN IPs, Cloudflare/edge infrastructure, registrar privacy, generic login pages, false-positive profile pages, parked domains, soft 404s, auth walls, and low-value phone deeplink pages. It does not delete data automatically; the investigator decides.

## Coverage Matrix

Coverage columns: Email, Username, Phone, Domain, IP, Image, Google Maps, Breach, Web Search, Infrastructure, Social, Code, Crypto.

Rows: attempted, found, verified, noisy, disabled, requires API key.

## Analyst Packet Exports

Export formats:

- PDF
- HTML
- JSON evidence bundle
- CSV IOCs
- graph JSON
