# Noise Killer

Noise Killer memisahkan item bernilai rendah dari main graph agar investigator tidak salah membaca artefak sebagai finding.

## Suppressed by Default

- Generic login/sign-up pages.
- Auth wall only, HTTP 401/403 tanpa target-specific proof.
- Soft 404 / profile not found.
- Parked domains.
- CDN/shared edge IP tanpa bukti ownership.
- Registrar privacy-only records.
- Generic provider MX/NS yang tidak memberi nilai investigasi.
- Messenger deeplink landing page.
- Template-generated candidate URL.
- Empty metadata pages.

## Output

Setiap keputusan memiliki:

- `is_noise`
- `noise_score`
- `reasons`
- `recommended_action`
- `affected_node_ids`
- `evidence_refs`

UI menampilkan noise di Noise Bin, bukan sebagai node graph utama.
