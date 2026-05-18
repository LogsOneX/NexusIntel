# Reference Notes

Dokumen ini mencatat apa yang dipelajari dari project referensi dan bagaimana pola tersebut diterapkan ulang di NexusRecon.

## Flowsint

Repository: https://github.com/reconurge/flowsint

Pola yang diadaptasi:

- Graph-based investigation.
- Enricher/module architecture.
- Local-first, ethical OSINT positioning.
- Pemisahan fungsi core, enrichers, API/app pada level konsep.

Implementasi NexusRecon:

- `core/graph.py` membangun nodes/edges dari output modul.
- `modules/` diperlakukan sebagai passive enrichers.
- `doctor` command membedah struktur lokal dan data flow.
- Report HTML menyertakan node/edge table.

## GHunt

Repository: https://github.com/mxrch/GHunt

Pola yang diadaptasi:

- CLI dengan module commands.
- Fully async workflow.
- JSON export sebagai output pipeline.
- Pemisahan penggunaan CLI dan library-style logic.

Implementasi NexusRecon:

- `AnalyticsEngine` menjalankan modul async dengan timeout dan concurrency.
- `hunt` dan `aggregate` mendukung JSON/Markdown/HTML/graph export.
- Scanner standalone tetap dapat dipakai via command khusus.

## Holehe

Repository: https://github.com/megadose/holehe

Pola yang diadaptasi:

- Account presence output yang konsisten.
- Field seperti `name`, `rateLimit`, `exists`, `emailrecovery`, `phoneNumber`, dan `others`.
- Banyak modul kecil yang mengisi satu list hasil.

Implementasi NexusRecon:

- `modules/holehe_style.py` mengeluarkan subset schema account-presence.
- Implementasi tetap pasif dan tidak memakai flow forgotten-password atau register endpoint agresif.

## License and Code Copying

NexusRecon tidak melakukan vendoring atau copy-paste kode dari project referensi. Semua pola di atas diimplementasikan ulang sebagai desain lokal yang pasif dan defensif. Hormati lisensi project sumber saat mengambil inspirasi lebih lanjut.
