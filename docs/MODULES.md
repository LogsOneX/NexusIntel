# Module Catalog

Dokumen ini menjelaskan modul CLI legacy yang dimuat oleh `core.engine.AnalyticsEngine`. Dashboard enterprise terbaru tidak menampilkan module picker; dashboard menjalankan transform dari node, lalu `backend/tasks.py` yang memutuskan wrapper OSINT mana yang dipakai. Folder `modules/` tetap penting untuk CLI dan legacy-compatible engine.

Untuk runtime dashboard terbaru, layer normalisasi utama ada di:

```text
backend/recon_validators.py
```

Layer ini dipanggil oleh Celery sebelum hasil recon ditulis sebagai graph node/edge.


## Ghost Engine Backend Modules

Folder `backend/modules/` adalah runtime OSINT async untuk dashboard/Celery. Modul ini berbeda dari folder legacy `modules/` di root. Semua modul memakai public-source/read-only signals: HTTP status, public DOM/OpenGraph metadata, DNS, RDAP, dan public web documents. Modul tidak mengirim password reset/OTP, tidak membuat akun, tidak contact-sync, tidak SMTP VRFY/RCPT, dan tidak mengubah state layanan pihak ketiga.

### `backend/modules/identity_recon.py`

Async username resolver dengan `aiohttp`, concurrency tinggi, curated public profile URLs, optional `NEXUS_PLATFORM_CATALOG` untuk registry internal 500+ surface, false-positive filtering, negative marker parsing, title/DOM metadata extraction, confidence scoring, dan 4-tier clustered execution: Major Socials, Tech & Dev, Gaming & Forums, Deep Sweep. Hasil langsung di-stream ke WebSocket melalui callback Celery.

### `backend/modules/workspace_recon.py`

Workspace/cloud posture resolver: MX/TXT/DMARC/BIMI/MTA-STS, Google/Microsoft/Proton/Zoho/Fastmail/Yandex/Amazon SES/Mailgun/SendGrid provider hints, Microsoft tenant discovery, public workspace documents, dan Gravatar hash. DNS berjalan non-blocking via `asyncio.to_thread(dnspython)` agar stabil di Python 3.13.

### `backend/modules/email_recon.py`

Email posture resolver yang memvalidasi format, mendeteksi disposable domain, memecah local-part/domain, menjalankan workspace resolver, melakukan public username pivot dari local-part, dan mengambil GET-only public sign-up document signatures. Target email tidak dikirim ke form registrasi; tidak ada password reset, OTP, SMTP VRFY, SMTP RCPT, atau contact-sync.

### `backend/modules/phone_recon.py`

Phone posture resolver: normalisasi E.164, parsing `phonenumbers`, carrier/geolocation/timezone jika library tersedia, fallback numbering-plan lokal, public deep-link DOM/OpenGraph metadata, dan deep-link candidate artifacts tanpa klaim registrasi messenger.

### `backend/modules/case_hygiene.py`

Investigation quality module untuk menghitung health score, coverage entity, weak-confidence nodes, isolated nodes, edge distribution, dan rekomendasi next action. Modul ini dipakai oleh endpoint `/api/v1/investigations/{investigation_id}/health` dan lifecycle dock di Network Graph supaya operator tahu apakah case sudah matang, masih tipis, atau perlu transform lanjutan.

## Runtime Transform Validators

### `analyze_identity_target`

Validasi username/nama, split name parts, public profile candidate URLs, dan guardrail untuk sensitive cultural-origin inference.

Target: `username`, `name`

### `analyze_email_target`

Validasi format email, split local-part/domain, DNS MX/TXT/DMARC/BIMI, disposable-domain hint, mail exchanger posture, public sign-up document signatures, dan guardrail untuk state-changing probes.

Target: `email`, `domain-like email pivot`

### `analyze_network_target`

Domain/IP recon public-source: DNS A/AAAA/CNAME/MX/NS/TXT/CAA, RDAP domain/IP, crt.sh passive subdomain, reverse DNS, dan GeoIP/ASN hint via source gratis.

Target: `domain`, `url`, `ip`

### `analyze_phone_target`

Strict E.164 validation, country calling code parsing, Indonesian mobile prefix hint, public numbering-plan line-type signal, public deep-link metadata, dan guardrail untuk contact-sync/OTP/login probes.

Target: `phone`

Modul di bawah ini adalah plugin OSINT yang dimuat otomatis oleh `AnalyticsEngine`. Mode `standard` menjaga eksekusi ringan, sedangkan `active` dan `aggressive` mengaktifkan modul/crawling read-only yang lebih dalam.

## identity

### `intel_assistant`

Local analyst brain untuk membuat operation profile, priority tasks, hypotheses, collection plan, flow hints, dan guardrails. Modul ini tidak memakai API eksternal; output-nya menjadi node `task`, `hypothesis`, dan `flow` di graph.

Target: `any`

### `identity_expansion`

Permutasi username, alias handle, pivot pencarian manual, dan rekomendasi flow. Modul ini offline-first: tidak memukul layanan pihak ketiga, tapi menghasilkan entity baru untuk graph dan flow chaining.

Target: `username`, `email`, `url`, `domain`, `unknown`

### `username_presence`

Enumerasi username lintas platform publik. Modul ini memakai registry `recon/platforms.py`, negative markers, HTTP status, confidence score, profile title extraction, external profile links, category hits, dan footprint score.

Target: `username`, `email`, `url`

### `account_presence`

Account-presence hints berbasis data publik seperti Gravatar hash profile, identity hubs, package registries, dan profile endpoint. Modul ini tidak memakai flow registrasi, forgotten-password, atau endpoint private.

Output `results` mengikuti schema NexusRecon account-presence:

```json
{
  "name": "GitHub",
  "domain": "github.com",
  "method": "profile",
  "rateLimit": false,
  "exists": true,
  "emailrecovery": null,
  "phoneNumber": null,
  "others": null
}
```

Target: `email`, `username`

### `account_pivots`

Account/workspace enrichment yang aman: MX/TXT provider hints, SPF/DMARC posture, Gmail domain hints, GitHub/GitLab/npm public API enrichment, search pivot links, Digital Asset Links, dan Apple app-site association.

Target: `email`, `username`, `domain`

### `user_analytics`

Enrichment profil publik dari GitHub, Dev.to, dan Hacker News, termasuk repository language signals.

Target: `username`, `email`, `url`

### `phone_intel`

Analisis offline untuk normalisasi nomor telepon, rentang E.164, country-code hint, dan shape signal.

Target: `phone`

## infrastructure

### `domain_intelligence`

Domain intelligence pasif: RDAP, DNS A/AAAA/MX/NS/TXT/CAA, certificate transparency, security headers, mail posture, dan risk summary.

Target: `domain`, `url`, `email`

### `network_mapping`

Mapping ringan untuk DNS address records, nameserver, CNAME, dan RDAP ownership hints.

Target: `domain`, `url`, `email`

### `ip_asn_lookup`

Resolve domain ke IP dan enrich IP ownership, range, CIDR, country, parent handle, dan entity hint melalui RDAP publik.

Target: `ip`, `domain`, `url`, `email`

### `website_surface`

Website-to-links enricher: title/meta, internal links, external links, email yang tampil di HTML, asset count, text sample, tracker hints, dan optional internal crawl saat mode `active`/`aggressive`.

Target: `domain`, `url`

### `active_surface`

Active read-only surface sweep untuk target yang diizinkan: common-host DNS sweep, robots/sitemap/security.txt, common-path probing, HTTP status, technology hints, dan risk notes. Mode `standard` akan skip modul ini.

Target: `domain`, `url`, `email`

### `header_diagnostics`

Inspeksi HTTP response header publik dan missing browser security controls seperti HSTS, CSP, X-Frame-Options, dan Referrer-Policy.

Target: `domain`, `url`

## Membuat Modul Baru

Template minimal:

```python
metadata = {
    "name": "New Passive Module",
    "description": "What this module collects.",
    "category": "identity",
    "target_types": ["username"],
    "tags": ["tag"],
    "passive": True,
    "risk": "low",
}

async def run(target: str) -> dict:
    return {
        "status": "success",
        "summary": "Human-readable summary.",
        "data": {"target": target},
    }
```

Status yang disarankan:

- `success`: modul selesai dan data valid.
- `skipped`: tipe target tidak relevan atau tidak ada kandidat.
- `error`: modul gagal karena timeout, network, parsing, atau exception lain.

## Graph Output

Setiap modul tidak perlu membuat graph sendiri. Engine mengumpulkan output, lalu `core.graph.EntityGraphBuilder` mengekstrak entity penting seperti:

- target,
- module,
- service/profile,
- URL,
- domain/hostname,
- username variants,
- application/app-link nodes,
- flow hints,
- DNS record/IP,
- risk,
- signal.

Graph disimpan otomatis di report JSON/Markdown/HTML dan bisa diekspor khusus dengan:

```bash
python3 main.py hunt example.com --save --format graph
```
