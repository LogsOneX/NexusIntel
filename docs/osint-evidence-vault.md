# Evidence Vault

Every raw payload collected by the adapter SDK is stored through `ProvenanceStore` and indexed in the `data_provenance` table. The vault stores raw HTML, JSON, text, headers, source URL, timestamp metadata, and SHA-256 hashes.

Endpoints:

```text
GET /api/v1/evidence/{id}
GET /api/v1/investigations/{id}/evidence
GET /api/v1/provenance/{id}/verify
```

Graph nodes created by registry transforms include `raw_evidence_ref`, `source_url`, `fetched_at`, `confidence_reason`, and `legal_basis` in node data. The right-side Entity Data drawer exposes linked evidence and a raw preview.

Deduplication is SHA-256 based per investigation/source, so identical payloads reuse the stored object.

## Analyst Packet Exports

The export endpoint can bundle graph state, evidence metadata, confidence explanations, and IOC rows into PDF, HTML, JSON, CSV, or graph JSON. Evidence references remain hash-addressed so exported findings can be verified against the local vault.
