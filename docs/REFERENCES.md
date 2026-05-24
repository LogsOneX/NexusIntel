# Reference Notes

Dokumen ini mencatat apa yang dipelajari dari project referensi dan bagaimana pola tersebut diterapkan ulang di NexusIntel/NexusRecon. Thanks untuk developer dan komunitas project di bawah ini; implementasi runtime di repo ini tetap standalone dan tidak melakukan vendoring/copy-paste kode vendor.

## Flowsint

Repository: https://github.com/reconurge/flowsint

Pola yang diadaptasi:

- Graph-based investigation.
- Enricher/module architecture.
- Local-first, ethical OSINT positioning.
- Pemisahan fungsi core, enrichers, API/app pada level konsep.

Implementasi NexusIntel:

- `frontend/src/components/GraphCanvas.tsx` menjadi canvas link-analysis besar.
- `frontend/src/components/CommandCenter.tsx`, `frontend/src/pages/`, dan `frontend/src/components/GraphCanvas.tsx` menyediakan command center dan transform-driven graph workspace.
- `backend/main.py` dan `backend/tasks.py` membuat API/worker transform.
- `core/graph.py` tetap dipakai untuk workflow CLI legacy.

## Maigret

Repository: https://github.com/soxoj/maigret

Pola yang diadaptasi:

- Username dossier.
- Username permutation.
- Category/tag thinking.
- Graph/report oriented output.

Implementasi NexusIntel:

- `backend/tasks.py::run_nexusrecon_task` menormalisasi public profile signal ke graph.
- `modules/identity_expansion.py` dan `modules/username_presence.py` tetap tersedia untuk CLI legacy.

## Sherlock

Repository: https://github.com/sherlock-project/sherlock

Pola yang diadaptasi:

- Public username discovery lintas platform.
- HTTP status + negative marker untuk mengurangi false positive.

Implementasi NexusIntel:

- `recon/platforms.py` menjadi registry platform standalone.
- `nexusrecon.main.NexusRecon` di-bridge oleh Celery worker untuk transform username.
- `modules/username_presence.py` tetap menjalankan passive concurrent checks dengan confidence scoring pada CLI legacy.

## GHunt

Repository: https://github.com/mxrch/GHunt

Pola yang diadaptasi:

- CLI dengan module commands.
- Fully async workflow.
- JSON export sebagai output pipeline.
- Pemisahan penggunaan CLI dan library-style logic.

Implementasi NexusIntel:

- `backend/tasks.py` memakai async routines untuk recon public-source.
- API/worker memisahkan gateway dan long-running task.
- CLI legacy tetap mendukung JSON/Markdown/HTML/graph export.
- Email/workspace transform memakai DNS/provider hints tanpa cookies/login.

## Holehe

Repository: https://github.com/megadose/holehe

Pola yang diadaptasi:

- Account presence output yang konsisten.
- Field seperti `name`, `rateLimit`, `exists`, `emailrecovery`, `phoneNumber`, dan `others`.
- Banyak modul kecil yang mengisi satu list hasil.

Implementasi NexusIntel:

- `modules/account_presence.py` mengeluarkan schema account-presence NexusRecon.
- `backend/tasks.py::run_email_google_task` memakai public DNS, provider hints, dan Gravatar hash.
- Implementasi tidak memakai flow forgotten-password atau register endpoint agresif.

## License and Code Copying

NexusRecon tidak melakukan vendoring atau copy-paste kode dari project referensi. Semua pola di atas diimplementasikan ulang sebagai desain lokal yang pasif dan defensif. Hormati lisensi project sumber saat mengambil inspirasi lebih lanjut.
