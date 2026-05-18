# Dashboard

Dashboard terbaru adalah command-center UI berbasis React + Cytoscape. Entry point-nya `frontend/src/components/Dashboard.tsx`; canvas link analysis ada di `frontend/src/components/GraphCanvas.tsx`.

## Run

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8080
```

Stop:

```bash
docker compose down
```

## Layout

- Left console: target acquisition, mode selector, manual entity builder, investigation list.
- Center canvas: graph besar sebagai area kerja utama.
- Right drawer: deep entity data dengan field filter dan raw JSON.
- Bottom HUD: terminal log real-time dari worker melalui WebSocket.

## Graph Workflow

1. Buat investigation dari target awal.
2. Worker membuat node root dan entity hasil recon.
3. Klik node untuk inspect data.
4. Right-click node untuk menjalankan transform.
5. Terminal HUD menampilkan output task live.
6. Graph refresh otomatis saat task berjalan.

## Context Transforms

Transform yang tersedia berubah mengikuti tipe node:

- `username`: username sweep dan Sherlock-style pivot.
- `email`: email footprint, Google/workspace public indicators, local-part username pivot.
- `domain`: DNS/domain recon, workspace recon, website surface.
- `profile/platform`: host/domain pivot dan identity sweep ulang.

Dashboard tidak menampilkan include/exclude atau module picker. UI dibuat agar investigator memilih entity dan transform, bukan memilih modul internal.

## Data Panel

Panel kanan menampilkan:

- tipe entity,
- label dan value,
- source,
- confidence,
- nested JSON fields dalam table searchable,
- raw JSON untuk debugging dan export mental model.

## Terminal HUD

Terminal HUD subscribe ke:

```text
WS /api/v1/ws/logs/{task_id}
```

Worker menyiarkan:

- queue/start event,
- captured stdout/stderr dari NexusRecon,
- DNS/email/domain recon progress,
- success/error summary.

## Legacy Local Dashboard

Dashboard legacy dari `dashboard/server.py` masih bisa dijalankan via:

```bash
python3 main.py dashboard 127.0.0.1:8080
```

Mode ini hanya untuk fallback manual. UI enterprise terbaru berjalan lewat Compose.
