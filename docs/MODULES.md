# Module Catalog

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
