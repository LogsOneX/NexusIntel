# Analyst Workflows

## Email Investigation

1. Buka `Identity Search`.
2. Masukkan email dan pilih Passive/Standard sesuai legal basis.
3. Pantau telemetry untuk source queried, result count, evidence captured, dan noise filtered.
4. Buka graph case untuk melihat email, domain, MX/DNS, workspace posture, avatar/hash, dan candidate profiles.
5. Review Evidence Vault sebelum mempromosikan candidate lead.

## Phone Investigation

1. Masukkan phone dalam format E.164.
2. Jalankan numbering-plan transform dan legal connector jika configured.
3. Deeplink metadata hanya diperlakukan sebagai candidate, bukan bukti registrasi.
4. Promosikan lead hanya jika ada public evidence yang mendukung.

## Username Investigation

1. Masukkan username.
2. Jalankan public profile transform.
3. Validasi false-positive via source URL, profile markers, title/body match, avatar/link evidence.
4. Gunakan correlation engine untuk possible_same_actor; jangan merge otomatis tanpa confidence tinggi.

## Domain/IP Investigation

1. Masukkan domain atau IP.
2. Jalankan DNS, RDAP, CT subdomain, web fingerprint, reverse DNS, dan ASN transforms.
3. Gunakan confidence lens untuk memisahkan infrastructure, CTI, dan candidate findings.

## Graph Expansion

1. Pilih node.
2. Buka Entity Inspector > Transforms atau right-click node.
3. Jalankan transform yang valid dan evidence-backed.
4. Candidate/noise/compliance tetap keluar dari main graph sampai analis mempromosikan.

## Evidence Review

1. Buka `Evidence Vault`.
2. Filter berdasarkan source, entity, grade, confidence, URL, atau hash.
3. Buka raw payload hanya saat diperlukan.
4. Salin hash/source untuk laporan.

## Watchlist Monitoring

1. Buka `Threat Watchlist`.
2. Tambahkan authorized target ke case.
3. Pilih interval pasif.
4. Review delta dan alert tanpa illegal crawling.

## Report Export

1. Buka graph atau inspector.
2. Export Analyst Packet dalam HTML/PDF/JSON/CSV/Graph JSON.
3. Pastikan report menyertakan citations, timestamps, confidence, noise removed, candidate leads, dan compliance notes.
