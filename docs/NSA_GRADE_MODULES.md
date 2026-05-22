# NexusIntel Advanced Architecture Modules

Dokumen ini merangkum upgrade arsitektur 6 modul. Semua kapabilitas tetap dalam batas authorized, read-only, dan public-source. Bagian egress tidak dibuat untuk bypass WAF; implementasinya adalah governance jaringan, retry sopan, jitter, dan allowlisted proxy.

## 1. Egress Governance, Proxy Rotator, dan Jitter

File utama:

- `backend/modules/proxy_rotator.py`
- `backend/modules/opsec_http.py`
- `backend/modules/serverless_invoker.py`

Fitur:

- Redis-backed round-robin proxy pool dari `NEXUS_PROXY_POOL` atau `NEXUS_EGRESS_PROXY`.
- Randomized network jitter 1.2 sampai 4.7 detik.
- Exponential backoff untuk status transient/rate-limit.
- Serverless invoker aman dengan dry-run saat `NEXUS_ENV=development`.

Queue Celery: `network_io`.

## 2. Chain of Custody dan Audit Trail

File utama:

- `backend/modules/provenance_store.py`
- tabel `data_provenance`
- tabel `audit_logs`
- middleware audit di `backend/main.py`

Fitur:

- RAW payload disimpan ke `data/provenance/<investigation_id>/<sha256>.raw`.
- SHA-256 disimpan ke Postgres.
- Endpoint verifikasi hash memastikan bukti tidak berubah.
- Audit middleware mencatat user, method, path, status code, target entity, dan IP address.

## 3. Persistent Surveillance Watchlist

File utama:

- `backend/modules/watchlist_engine.py`
- tabel `watchlists`
- Celery Beat task `nexusintel.watchlist_sweep_all`

Fitur:

- Watchlist on/off per investigation.
- Interval default 12 jam pada model, sweep scheduler default 1800 detik via `WATCHLIST_SWEEP_SECONDS`.
- Delta graph signature memicu event `SYSTEM_ALERT` melalui Redis log bus.

Queue Celery: `network_io`.

## 4. Deep Entity Resolution

File utama:

- `backend/modules/entity_resolution.py`
- task `nexusintel.entity_resolution`

Fitur:

- TF-IDF style token/cosine scoring ringan tanpa dependency model besar.
- Skor `>=85` menghasilkan `SAME_IDENTITY`.
- Skor `<85` menghasilkan `HYPOTHETICAL_MATCH` untuk edge putus-putus amber di UI.

Queue Celery: `ml_gpu`. Task ML tidak digabung dengan scraping/network worker.

## 5. Multiplayer Command Canvas

File utama:

- `frontend/src/store/graphStore.ts`
- `frontend/src/store/collaborationStore.ts`
- `frontend/src/realtime/yjsProvider.ts`
- `frontend/src/realtime/graphCrdt.ts`
- `frontend/src/realtime/presence.ts`
- `backend/modules/collaboration_bus.py`

Fitur:

- Yjs + `y-websocket` untuk CRDT graph workspace.
- Zustand untuk local collaboration/presence state.
- Redis Pub/Sub endpoint backend untuk broadcast JSON patch dan analyst presence.

## 6. Crypto Wallet Tracker

File utama:

- `backend/modules/crypto_recon.py`
- task `nexusintel.crypto_wallet`

Fitur:

- Bitcoin wallet lookup via free public Blockstream API.
- Ethereum/address lain tidak dipaksakan jika explorer gratis tidak dikonfigurasi.
- `NEXUS_ENV=development` mengembalikan dummy JSON agar testing tidak memakai kuota/API eksternal.

Queue Celery: `network_io`.

## Runtime Baru

`docker-compose.yml` sekarang memisahkan worker:

- `worker-network`: queue `network_io,default` untuk HTTP/DNS/crypto/watchlist.
- `worker-ml`: queue `ml_gpu` untuk entity resolution/ML.
- `celery-beat`: scheduler watchlist.
- `y-websocket`: multiplayer CRDT service.

## Endpoint Baru

- `POST /api/v1/provenance`
- `GET /api/v1/provenance/{id}/verify`
- `GET /api/v1/audit`
- `POST /api/v1/watchlists`
- `GET /api/v1/watchlists`
- `PATCH /api/v1/watchlists/{id}/toggle`
- `POST /api/v1/entity-resolution/score`
- `POST /api/v1/collaboration/patch`
- `POST /api/v1/collaboration/presence`
- `POST /api/v1/crypto/wallet`
- `POST /api/v1/serverless/invoke`
- `GET /api/v1/proxies/status`
- `POST /api/v1/proxies/seed`


## Graph UI Handling

Crypto wallets are rendered as flat `crypto_wallet` node cards with wallet SVG icons. Transaction artifacts are rendered as `crypto_transaction` nodes with directional ledger icons. Right-click transforms for wallet nodes are `check_wallet_balance` and `trace_transactions`; both route to the `network_io` crypto worker.
