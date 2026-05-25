# Evidence Operating System

Evidence OS 2.0 makes graph findings evidence-first.

## Evidence Fields

Every evidence object exposes:

- `evidence_id`
- `source_url`
- `fetched_at`
- `sha256`
- `content_type`
- `status_code` when available
- payload excerpt on explicit request

## API

- `GET /api/v1/investigations/{id}/evidence-map`
- `GET /api/v1/evidence/{evidence_id}/excerpt`
- `POST /api/v1/evidence/{evidence_id}/verify`
- `POST /api/v1/evidence/diff`

Findings without `raw_evidence_ref`/`evidence_id` are reported as unsupported warnings and should not be used as report-safe findings.
