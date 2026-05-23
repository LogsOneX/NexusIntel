# Impersonation Investigation Mode

Purpose: compare a suspicious domain against an official organization/domain and produce evidence-backed takedown material.

Inputs:

- Suspected fake domain.
- Official legitimate domain.
- Organization name.
- Optional SpiderFoot CSV, favicon/logo metadata, screenshots.

Workflow:

1. Run `domain_to_dns`, `domain_to_rdap`, `domain_to_ct_subdomains`, and `domain_to_web_fingerprint` on both domains.
2. Compare titles, headers, favicon hashes, outbound links, CT subdomains, shared IPs, nameservers, analytics IDs, and copied assets.
3. Penalize generic CDN/shared hosting/registrar privacy before linking infrastructure.
4. Mark weak links as `possible_same_actor`; do not merge actors automatically below high confidence.
5. Export report with source URLs, timestamps, hashes, and recommended next pivots.

Outputs:

- Risk score.
- IOC table.
- Hosting/registrar escalation notes.
- Preservation request checklist.
- Evidence appendix with SHA-256 references.
