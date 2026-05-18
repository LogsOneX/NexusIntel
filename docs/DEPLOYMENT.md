# Deployment

NexusRecon bisa dijalankan sebagai local dashboard manual, Docker Compose service, atau single-command bootstrap. Default binding sengaja `127.0.0.1:8080` supaya dashboard tidak terbuka ke network publik tanpa keputusan eksplisit.

## One-command path

```bash
make up
```

Dashboard tersedia di:

```text
http://127.0.0.1:8080
```

Stop service:

```bash
make down
```

Jika Docker Compose belum tersedia, gunakan bootstrap lokal:

```bash
./start.sh
```

Script ini memakai Docker Compose jika tersedia. Jika Docker Compose tidak ada, script akan membuat `.venv`, menginstal dependency, dan menjalankan dashboard di `127.0.0.1:8080`.

## Custom host atau port

```bash
make up HOST=0.0.0.0 PORT=8080
```

Atau:

```bash
NEXUS_HOST=127.0.0.1 NEXUS_PORT=9090 ./start.sh
```

## Runtime data

Docker Compose memasang volume lokal berikut agar hasil investigasi tetap tersimpan:

- `./results:/app/results`
- `./reports:/app/reports`
- `./.nexusrecon:/app/.nexusrecon`

## Health dan readiness

Health endpoint:

```text
GET /api/health
```

Operational readiness lokal:

```bash
make readiness
```

CLI anatomy check:

```bash
make doctor
```

## Manual local mode

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py --no-banner dashboard 127.0.0.1:8080
```

NexusRecon tetap local-first. Gunakan mode `active` atau `aggressive` hanya untuk target yang kamu miliki izin untuk dianalisis.
