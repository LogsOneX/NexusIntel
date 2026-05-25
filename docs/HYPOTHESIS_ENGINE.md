# Hypothesis Engine

Hypothesis Engine membantu analyst menguji kemungkinan hubungan tanpa mengubahnya menjadi fakta.

## Contoh

- Dua profile mungkin terkait karena avatar hash dan external link sama.
- Domain mungkin impersonation candidate karena keyword suspicious.
- Infrastruktur mungkin unrelated karena hanya CDN/shared hosting.

## Rules

- Di bawah 70: jangan ditulis sebagai fakta.
- 70-89: `likely/probable`, analyst review wajib.
- 90+: strong hypothesis, tetap harus citation.
- Attribution orang nyata perlu 95+ dan minimal dua bukti publik langsung yang independen.

## Analyst Actions

Hypothesis bisa diterima atau ditolak melalui endpoint accept/reject. Keputusan disimpan di metadata kasus.
