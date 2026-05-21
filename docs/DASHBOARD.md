# Dashboard

Dashboard terbaru adalah multi-page Intelligence Command Center berbasis React + Cytoscape. Entry point-nya `frontend/src/components/CommandCenter.tsx`; canvas link analysis utama ada di `frontend/src/components/GraphCanvas.tsx`, sementara `FlowCanvas.tsx` hanya compatibility wrapper.

## Run

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8080
```

Development login default:

```text
admin / nexusintel
```

Stop:

```bash
docker compose down
```

## Layout

- Persistent sidebar: Dashboard, Workspace, Network Graph, AI Oracle, Settings, Account.
- Dashboard: recent investigations, case folders, timeline/report quick links.
- Workspace: case name, assigned operator, markdown notes, AI auto-briefing.
- Network Graph: edge-to-edge tactical canvas, explicit investigation lifecycle dock (select/new/clear/delete), unified master toolbar, integrated launch form, entity palette, Smart Selector, Playbooks, Ask Oracle from node context menu, collapsible data panel, and collapsible terminal HUD.
- Settings: BYOK API keys and LLM provider configuration.

## Tactical Canvas

Network Graph sekarang memakai layout Maltego-purity: canvas memenuhi seluruh area kerja, tanpa case strip besar dan tanpa command bar terpisah. Graph tidak auto-load investigation lama; user memilih case eksplisit dari lifecycle dock atau membuka URL `/graph?case=<id>`. Data panel kanan dan terminal bawah berada sebagai overlay absolute yang bisa disembunyikan, sehingga investigator bisa fokus 100% pada visual link analysis. Semua kontrol utama berada di `tactical-graph-toolbar`: stats, launch form, entity palette, smart selector, layout switcher, timeline, fit, export, dan toggle panel. Oracle tidak lagi permanen di bawah graph; panel Oracle hanya muncul sebagai overlay saat dipanggil dari context menu node.

## Graph Workflow

1. Pilih case dari lifecycle dock, klik New untuk blank investigation, atau submit target dari integrated launcher di master toolbar.
2. Worker membuat node root dan entity hasil recon jika launch scan dipakai.
3. Klik node untuk inspect data di collapsible data panel.
4. Right-click node untuk menjalankan transform atau Ask Oracle.
5. Drag username/email/domain/IP/phone dari entity palette untuk menambah pivot manual.
6. Terminal HUD tetap menerima telemetry meskipun panel disembunyikan.
7. Graph refresh otomatis saat task berjalan tanpa mereset pan/zoom.
8. Delete investigation tersedia di Graph lifecycle dock dan Workspace case folders; delete menghapus case beserta graph data lewat API.
9. Health strip menampilkan Case Hygiene score dan rekomendasi next action.

## Context Transforms

Transform yang tersedia berubah mengikuti tipe node:

- `username`: username sweep dan Sherlock-style pivot.
- `email`: email footprint, Google/workspace public indicators, local-part username pivot.
- `domain`: DNS/domain recon, RDAP/crt.sh, workspace recon, website surface.
- `ip`: IP recon, reverse DNS, RDAP allocation, GeoIP/ASN hint.
- `phone`: E.164 validation dan public numbering-plan hint.
- `profile/platform`: host/domain pivot dan identity sweep ulang.

Dashboard tidak menampilkan include/exclude atau module picker. UI dibuat agar investigator memilih entity dan transform, bukan memilih modul internal.

## Visual System

Dashboard memakai gaya Minimalist Monochrome Intelligence:

- background pure black `#000000`,
- panel anthracite `#111111`,
- border `1px solid #333333`,
- white/gray text,
- sharp `0px` corner,
- Inter untuk UI,
- JetBrains Mono untuk node, JSON, dan terminal,
- transform/opacity-only transitions dengan cubic-bezier cinematic.

Edge aktif memakai dashed marching-flow style di canvas untuk menandai task yang sedang berjalan.

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
- validator artifact summary,
- success/error summary.

## Legacy Local Dashboard

Dashboard legacy dari `dashboard/server.py` masih bisa dijalankan via:

```bash
python3 main.py dashboard 127.0.0.1:8080
```

Mode ini hanya untuk fallback manual. UI enterprise terbaru berjalan lewat Compose.


## AI Oracle

Oracle panel tersedia di `/graph`, `/workspace`, dan `/oracle`. Prompt natural language dikirim ke `/api/v1/oracle/chat` bersama JSON graph state dan active node. Jika LLM belum dikonfigurasi, backend memakai local NexusIntel investigation brain untuk summary, confidence posture, high-confidence IP/domain pivots, highlight entity type, clear highlight, transform suggestion, dan collection-gap analysis. Quick prompts di panel Oracle mempercepat triage tanpa harus mengetik prompt panjang.
