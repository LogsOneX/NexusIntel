# NexusRecon / Data Aggregator

NexusRecon adalah command center OSINT public-source untuk menggabungkan enumerasi username, inspeksi email, domain intelligence, active surface sweep, HTTP header diagnostics, dan enrichment profil publik dalam satu CLI/dashboard yang lebih rapi.

Fokus project ini adalah **public-source reconnaissance**: memakai endpoint publik, DNS/RDAP, certificate transparency, profile page publik, API publik, dan active crawling read-only untuk target yang kamu punya izin. Tidak ada bypass, credential stuffing, private API abuse, spam register/forgot-password, atau rate-limit evasion.

## Bedah Cara Kerja

```text
input target
  -> core.targets.classify_target()
  -> core.engine.AnalyticsEngine.load_modules()
  -> mode dipilih: standard, active, atau aggressive
  -> modules/*.py dipilih berdasarkan metadata target_types/category
  -> async run(target) per modul
  -> hasil dinormalisasi: status, summary, signal_count, data, module
  -> core.graph.EntityGraphBuilder membuat nodes/edges investigasi
  -> core.render menampilkan dashboard CLI
  -> core.reporter menulis JSON/Markdown/HTML/Graph JSON
```

Desain ini mengambil pola investigasi modern:

- Graph-first investigation: setiap temuan diubah menjadi entity graph nodes/edges.
- Async module workflow dan export JSON/Markdown/HTML/graph.
- Account-presence schema konsisten: `name`, `domain`, `method`, `rateLimit`, `exists`, `emailrecovery`, `phoneNumber`, `others`.

## Fitur Utama

- CLI Rich dan dashboard web lokal yang lebih estetik dengan target profile, graph canvas, module results, raw JSON, dan report save.
- Workflow `hunt` untuk menjalankan modul OSINT sesuai tipe target: username, email, domain, URL, atau phone, dengan mode `standard`, `active`, dan `aggressive`.
- Modul standalone NexusRecon untuk local intel assistant, identity expansion, username presence, account presence, account pivots, active surface, dan domain intelligence.
- Local Intel Assistant: operation plan, priority tasks, hypotheses, collection plan, recommended flows, dan guardrails langsung masuk graph.
- Username enumeration lintas kategori: social, tech, creative, professional, identity, finance, marketplace, travel, fitness, gaming, blog, plus profile link extraction dan footprint score.
- Email intelligence: validasi format, provider hint, MX lookup, Gravatar hash profile, disposable-domain hint.
- Account/workspace pivots: DNS provider signals, SPF/DMARC hints, public developer profiles, search pivots, Digital Asset Links, dan Apple app-site association.
- Domain intelligence: RDAP, DNS A/AAAA/MX/NS/TXT/CAA, certificate transparency, security headers, mail posture, website surface, IP/RDAP network hints, dan risk summary.
- Active surface sweep: common-host DNS sweep, robots/sitemap/security.txt, common-path probing, technology hints, dan risk notes untuk authorized targets.
- Investigation graph otomatis untuk menghubungkan target, modul, service, URL, DNS record, domain, hostname, aplikasi, flow hint, dan risk.
- Flow Studio lokal dan CLI `flow` untuk chaining enrichers: output entity bisa menjadi input step berikutnya.
- Vault lokal untuk API key, case/sketch persistence, dan entity type registry.
- Ops readiness checks untuk memastikan modul, flow, entity schema, storage lokal, vault, dan runtime siap dipakai.
- Export laporan ke JSON, Markdown, HTML, atau graph JSON untuk workflow `hunt` dan `aggregate`.

## Struktur Project

```text
.
├── main.py                  # CLI utama: hunt, flow, aggregate, username, email, phone, domain
├── core/
│   ├── engine.py            # Dynamic module loader + concurrency + timeout + metadata
│   ├── graph.py             # Entity graph builder ala investigation graph
│   ├── reporter.py          # Export JSON/Markdown/HTML
│   ├── render.py            # Tampilan Rich untuk CLI
│   └── targets.py           # Target classifier: username/email/domain/url/phone
├── dashboard/
│   └── server.py            # Local web dashboard tanpa Docker
├── modules/
│   ├── username_presence.py # Username enumeration pasif
│   ├── intel_assistant.py   # Local analyst brain + operation plan
│   ├── identity_expansion.py # Permutasi username, alias, dan pivot manual
│   ├── account_presence.py  # Account presence hints + Nexus schema
│   ├── account_pivots.py    # Public account enrichment + workspace pivots
│   ├── domain_intelligence.py # Domain/RDAP/DNS/CRT/header intelligence
│   ├── active_surface.py   # Active DNS/HTTP surface sweep
│   ├── ip_asn_lookup.py     # IP/RDAP network ownership hints
│   ├── website_surface.py   # Website metadata, links, emails, tracker hints
│   ├── network_mapping.py   # Passive DNS + RDAP network hints
│   ├── header_diagnostics.py
│   ├── phone_intel.py
│   └── user_analytics.py
├── recon/
│   ├── platforms.py         # Registry platform username
│   ├── username_scanner.py  # Scanner username standalone
│   └── ultimate_scanner.py  # Email/phone/domain standalone
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DASHBOARD.md
│   ├── DEPLOYMENT.md
│   ├── MODULES.md
│   └── REFERENCES.md
├── legacy/                  # Arsip versi lama
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── start.sh
├── requirements.txt
└── pyproject.toml
```

## One-Command Deployment

Fresh clone bisa dinaikkan dengan satu perintah:

```bash
make up
```

Dashboard akan tersedia di:

```text
http://127.0.0.1:8080
```

Stop service:

```bash
make down
```

Fallback tanpa Docker Compose:

```bash
./start.sh
```

Script ini otomatis membuat `.venv`, menginstal dependency, dan menjalankan dashboard di `127.0.0.1:8080`. Detail deployment ada di `docs/DEPLOYMENT.md`.

## Instalasi Manual

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Opsional sebagai CLI package:

```bash
python3 -m pip install -e .
nexusrecon --help
```

## Penggunaan Cepat

Jalankan dashboard lokal tanpa Docker:

```bash
python3 main.py dashboard 127.0.0.1:8080
python3 main.py 127.0.0.1:8080
```

Matikan dashboard:

```bash
# dari terminal dashboard: Ctrl+C
pkill -f "main.py.*dashboard"
```

Jalankan unified workflow:

```bash
python3 main.py hunt johndoe --save --format html
python3 main.py hunt alice@example.com --category identity --save --format md
python3 main.py hunt example.com --category infrastructure --save --format json
python3 main.py hunt example.com --category infrastructure --save --format graph
python3 main.py hunt example.com --mode active --category infrastructure
python3 main.py hunt example.com --aggressive --include active_surface,website_surface,domain_intelligence
```

Username scanner standalone:

```bash
python3 main.py username johndoe --workers 60 --timeout 12 --save
python3 main.py username johndoe --category tech
```

Email, phone, dan domain standalone:

```bash
python3 main.py email alice@example.com --save
python3 main.py phone "+62 812-3456-7890"
python3 main.py domain example.com --save
```

Lihat modul dan kategori:

```bash
python3 main.py list-modules
python3 main.py list-modules --category identity
python3 main.py categories
python3 main.py doctor
python3 main.py flow list
```

## Workflow Advanced

Filter modul tertentu:

```bash
python3 main.py hunt johndoe --include username_presence,user_analytics,account_pivots
python3 main.py hunt "John Doe" --include identity_expansion
python3 main.py flow run identity_surface johndoe --timeout 12 --concurrency 4
python3 main.py flow run domain_surface example.com --save --format graph
python3 main.py flow run active_domain_recon example.com --mode aggressive --timeout 30
```

Kecualikan modul tertentu:

```bash
python3 main.py aggregate -t example.com --exclude header_diagnostics
```

Atur timeout dan concurrency:

```bash
python3 main.py hunt example.com --timeout 30 --concurrency 10 --save --format html
```

## Format Laporan

Workflow `hunt` dan `aggregate` mendukung:

- `json` untuk pipeline dan parsing otomatis.
- `md` untuk catatan investigasi.
- `html` untuk report visual yang bisa dibuka di browser.
- `graph` untuk export nodes/edges investigasi sebagai JSON.

Output default disimpan di `results/`.

## Menambah Modul

Buat file baru di `modules/` dengan metadata dan fungsi `async run(target: str) -> dict`.

```python
metadata = {
    "name": "Example Module",
    "description": "Describe what the module collects.",
    "category": "identity",
    "target_types": ["username", "email"],
    "tags": ["example"],
    "passive": True,
    "risk": "low",
}

async def run(target: str) -> dict:
    return {
        "status": "success",
        "summary": "Example signal collected.",
        "data": {"target": target},
    }
```

Kategori umum: `identity`, `infrastructure`, `general`.

## Catatan Etika

Gunakan hanya untuk target yang kamu miliki izin untuk analisis, investigasi internal, threat intelligence defensif, atau riset data publik yang sah. Batasi concurrency jika layanan memberi rate limit, dan jangan gunakan hasil OSINT untuk harassment, doxxing, impersonation, atau akses tidak sah.

## Thanks and Credits

Terima kasih untuk developer dan project berikut sebagai inspirasi desain:

- reconurge untuk [Flowsint](https://github.com/reconurge/flowsint), terutama konsep graph-based investigation dan enricher architecture.
- soxoj untuk [Maigret](https://github.com/soxoj/maigret), terutama konsep username dossier, permutation, tags, recursive pivots, dan report graph.
- Sherlock Project untuk [Sherlock](https://github.com/sherlock-project/sherlock), terutama konsep username discovery lintas platform publik.
- mxrch untuk [GHunt](https://github.com/mxrch/GHunt), terutama pola framework async, CLI modules, dan JSON export.
- megadose untuk [Holehe](https://github.com/megadose/holehe), terutama standar account-presence output dan ide email-to-accounts OSINT.
- Maltego dan OSINT Industries sebagai referensi UX untuk graph investigation, entity inspector, dan workflow investigasi modern.

NexusRecon tidak menyalin kode dari project referensi tersebut. Implementasi di repo ini dibuat ulang sebagai toolkit pasif, dengan credit dan respect terhadap lisensi masing-masing project.
