# OSINT Adapter SDK

NexusIntel uses `backend/osint/` as the lawful public-source adapter layer. Adapters must implement `OSINTAdapter.run(entity, context)` and return `AdapterResult` with zero synthetic graph intelligence.

Required artifact fields:

- `artifact_id`
- `type`, `label`, `value`
- `source`, `source_url`, `fetched_at`
- `confidence_score`, `confidence_reason`, `evidence_grade`
- `raw_evidence_ref`
- `relationship`, `tags`, `data`
- `legal_basis`, `public_source_note`

Adapters live under `backend/osint/adapters/` and are registered in `backend/osint/registry.py`. If an adapter needs a connector key, mark `requires_api_key=True` and define the transform `required_keys`. The UI will show the transform as disabled until the key exists.

Strict rules:

- Passive public-source or official BYOK API only.
- No password reset, OTP, contact-sync, login bypass, private API, CAPTCHA bypass, or authenticated scraping.
- Candidate artifacts must be labelled low confidence until corroborated.
