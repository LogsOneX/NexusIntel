# Architecture

NexusRecon sekarang dipisah menjadi empat lapisan utama.

## 1. CLI Layer

`main.py` bertanggung jawab untuk:

- parsing command dan opsi,
- menampilkan banner/tabel Rich,
- memilih workflow (`hunt`, `flow`, `aggregate`, `username`, `email`, `phone`, `domain`, `doctor`, `dashboard`),
- meneruskan mode eksekusi `standard`, `active`, atau `aggressive`,
- memanggil engine atau scanner standalone,
- menyimpan report bila `--save` dipakai.

## 2. Core Layer

`core/targets.py` melakukan klasifikasi target menjadi `username`, `email`, `domain`, `url`, `phone`, atau `unknown`.

`core/engine.py` memuat modul dari `modules/`, membaca metadata, memfilter kategori, menjalankan modul secara asynchronous, dan memberi timeout per modul.

Engine juga meneruskan `mode` ke modul yang mendukung parameter `mode`. Modul lama tetap kompatibel karena engine akan memanggil `run(target)` bila modul belum menerima mode.

`core/graph.py` mengubah hasil modul menjadi investigation graph berisi `nodes`, `edges`, dan ringkasan tipe node.

`core/flows.py` menyimpan flow templates dan menjalankan chained enrichment. Output graph dari satu step dapat menjadi input step berikutnya, dengan filter agar pivot manual tidak dieksekusi otomatis.

`core/reporter.py` membuat report JSON, Markdown, dan HTML.

`core/render.py` menyimpan komponen tampilan Rich supaya CLI tidak penuh kode presentasi.

## 3. Dashboard Layer

`dashboard/server.py` menjalankan local dashboard tanpa Docker dan tanpa framework tambahan. Endpoint lokal memanggil `AnalyticsEngine`, `EntityGraphBuilder`, dan `ReportGenerator`.

```text
browser
  -> /api/hunt
  -> AnalyticsEngine
  -> EntityGraphBuilder
  -> canvas graph + tables + raw JSON
```

Dashboard juga punya endpoint graph-workspace:

- `/api/flows` dan `/api/flow/run` untuk chained enrichment.
- `/api/vault` untuk local API key vault.
- `/api/types` untuk entity type registry.
- `/api/cases` untuk case/sketch persistence.

## 4. Recon Layer

`recon/platforms.py` adalah registry platform username bersama.

`recon/username_scanner.py` adalah scanner username standalone dengan progress bar dan confidence scoring.

`recon/ultimate_scanner.py` adalah scanner standalone untuk email, phone, dan domain.

## 5. Modules Layer

Folder `modules/` berisi plugin OSINT pasif. Setiap modul wajib punya:

- `metadata` dict,
- `async run(target: str) -> dict`.

Engine akan skip modul jika tipe target tidak sesuai dengan `metadata["target_types"]`.

## Data Flow

```text
CLI command
  -> classify_target()
  -> AnalyticsEngine.load_modules()
  -> module.run(target)
  -> normalized result dict
  -> EntityGraphBuilder nodes/edges dengan nodeType/nodeLabel/nodeProperties/nodeShape/nodeIcon
  -> Rich table
  -> optional ReportGenerator
```

## Pola yang Diadaptasi

- Dari Flowsint: konsep graph-based investigation, enricher modular, flows, vault, entity types, dan pemisahan core/enrichers/app.
- Dari GHunt: workflow CLI modular, async execution, dan export JSON.
- Dari Holehe: schema account-presence yang mudah dibaca pipeline (`name`, `domain`, `method`, `rateLimit`, `exists`, `emailrecovery`, `phoneNumber`, `others`).

Tidak ada kode vendor dari project referensi. Semua implementasi dibuat ulang untuk mode pasif dan defensif.

## Prinsip Desain

- Passive first: hanya sumber publik.
- Active mode: read-only crawling/probing untuk target yang diizinkan, tanpa bypass, login abuse, register spam, atau forgotten-password probing.
- Modular: tambah modul tanpa mengubah engine.
- Fail soft: error satu modul tidak mematikan scan lain.
- Explainable: setiap hasil menyimpan status, signal count, dan summary.
- Reportable: output bisa dipakai manusia atau pipeline.
