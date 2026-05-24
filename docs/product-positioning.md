# NexusIntel Product Positioning

NexusIntel diposisikan sebagai OSINT Command Center yang menggabungkan selector-first lookup, visual link analysis, evidence vault, passive watchlist, dan explainable entity resolution.

## OSINT Industries Pattern

- Single selector input untuk email, phone, username, domain, IP, dan wallet.
- Result modules dipisahkan antara verified evidence, weak signal, candidate lead, noise, dan compliance note.
- Real-time telemetry menunjukkan source queried, result count, evidence captured, confidence movement, dan noise filtered.
- Tidak ada fake result. Empty state menyatakan tidak ada public evidence yang terverifikasi.

## Maltego Pattern

- Graph canvas tetap menjadi ruang investigasi utama.
- Transforms dikontekstualkan berdasarkan entity type.
- Expand/pivot node menghasilkan relationship edge yang explainable.
- Candidate/noise/compliance tidak masuk main graph secara default.

## Social Links Pattern

- Case/workspace menjadi dataspace investigasi.
- Evidence, graph, notes, lead queue, noise bin, dan export berada dalam konteks case.
- Transform Library dan Entity Palette membuat workflow lebih discoverable daripada hanya right-click menu.

## StealthMole / SOCRadar Pattern

- Threat Watchlist memonitor target authorized secara pasif.
- CTI connector harus legal, public, licensed, atau BYOK.
- Tidak ada illegal dark web crawling, private forum infiltration, CAPTCHA bypass, atau raw credential storage.

## Palantir-Style Entity Resolution

- Entity punya source attribution, confidence, lineage, evidence references, dan audit trail.
- Similarity/correlation hanya membuat `possible_same_actor` sampai analis mengkonfirmasi.
- AI Oracle membantu triage dan briefing, bukan menyatakan guilt atau identitas definitif.
