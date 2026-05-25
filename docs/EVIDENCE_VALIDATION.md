# Evidence Validation

Validator memastikan setiap finding punya dukungan bukti sebelum dipakai dalam analisis.

## Dimensi Validasi

- Syntax: email, domain, IP, phone E.164, URL, hash.
- Source: official API, public web, analyst-provided, manual, legacy scanner, unknown.
- Evidence: raw ref, source URL, payload hash, timestamp, target-specific markers.
- Corroboration: source independen, avatar/hash/link/domain/username/cert/favicons yang sama.
- Contradiction: not found, soft 404, conflicting names/locations, stale evidence.

## Labels

- `VERIFIED`: direct evidence, high confidence, no warning.
- `STRONG`: kuat tapi belum memenuhi semua syarat verified.
- `PROBABLE`: sinyal cukup tapi butuh review.
- `WEAK`: bukti tipis.
- `CANDIDATE`: lead belum verified.
- `NOISE`: harus ditekan dari graph.
- `CONTRADICTED`: ada evidence konflik.
- `INSUFFICIENT_EVIDENCE`: tidak cukup bukti untuk klaim.
