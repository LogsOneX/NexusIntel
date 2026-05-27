# Connector Marketplace

## Purpose
The connector marketplace explains which data sources are available, which transforms they unlock, whether an API key is required, and why a source may be disabled.

## Backend
Endpoints:
- `GET /api/v1/connectors`
- `POST /api/v1/connectors/{connector_id}/test`

Connector metadata includes:
- id, name, category
- source reliability
- requires API key
- configured/enabled/key present
- testable and last tested
- unlocked transforms
- legal note
- quota placeholder
- documentation URL

## Included Connectors
Implemented or local/import connectors:
- GitHub public search (BYOK)
- HIBP (BYOK)
- Google Maps/Places metadata (BYOK for Places)
- SpiderFoot import
- Maltego CSV import
- Generic IOC CSV

Disabled placeholders until official adapters are implemented:
- URLScan, VirusTotal, Shodan, Censys, SecurityTrails, OpenCorporates, Twilio Lookup, Numverify, IntelX

## Frontend
Settings now displays connector status cards, key/configuration state, test action, source reliability, legal notes, disabled reasons, and unlocked transforms.

## No Fake Availability
Disabled connectors must remain disabled with clear reasons. Missing keys must show `missing_api_key`; missing adapters must show `adapter_not_implemented`.
