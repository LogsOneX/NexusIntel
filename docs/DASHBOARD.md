# Dashboard

NexusRecon punya local web dashboard tanpa Docker dan tanpa framework web tambahan. Server memakai Python standard library, lalu memanggil engine OSINT yang sama dengan CLI.

## Run

```bash
python3 main.py dashboard 127.0.0.1:8080
```

Shortcut kompatibel:

```bash
python3 main.py 127.0.0.1:8080
```

Buka:

```text
http://127.0.0.1:8080
```

## Endpoint Lokal

- `GET /` - dashboard UI.
- `GET /api/modules` - katalog modul, kategori, dan target types.
- `GET /api/types` - dynamic entity type registry.
- `GET /api/flows` - flow templates.
- `GET /api/vault` - masked vault key list.
- `GET /api/cases` - local case/sketch store.
- `GET /api/health` - health check.
- `POST /api/hunt` - menjalankan workflow OSINT.
- `POST /api/flow/run` - menjalankan chained flow.
- `POST /api/vault` - menyimpan local API key.
- `POST /api/vault/delete` - menghapus local vault key.
- `POST /api/cases` - membuat case/sketch.
- `POST /api/cases/save` - menyimpan graph ke case/sketch.
- `POST /api/save` - menyimpan hasil terakhir ke `results/`.

## UI Sections

- Sidebar untuk target, kategori, include/exclude module, timeout, concurrency, dan save format.
- Case/Sketch selector untuk menyimpan graph investigasi lokal.
- Executive metrics untuk OK, skipped, errors, signals, nodes, dan edges.
- Canvas investigation graph untuk target, modules, profiles, URLs, domains, DNS records, IPs, trackers, app-link nodes, flow hints, dan risk nodes.
- Graph tools untuk search, filter entity type, reset view, dan click-to-inspect node.
- Entity inspector untuk target profile atau node graph yang dipilih.
- Module result table dengan tab per modul.
- Flow Studio untuk menjalankan flow chained seperti `Identity Surface`, `Domain Surface`, `Identity Deep Pivot`, dan `Phone Triage`.
- Vault untuk menyimpan API key lokal dengan file permission `0600`; UI hanya menampilkan masked value.
- Entity Types registry untuk melihat schema, icon, warna, shape, dan field utama.
- Raw JSON output untuk pipeline/debug.

## Design Notes

Dashboard ini mengikuti konsep graph-minded investigation pada level workflow: enrichers, flows, vault, entity types, local-first operation, search/filter graph, dan node inspector. Implementasinya tetap dibuat ulang dan dipadatkan untuk mode single-file local server agar mudah dijalankan tanpa Docker.
