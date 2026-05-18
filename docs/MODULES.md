# Module Catalog

Modul di bawah ini adalah plugin OSINT pasif yang dimuat otomatis oleh `AnalyticsEngine`.

## identity

### `username_presence`

Enumerasi username lintas platform publik. Modul ini memakai registry `recon/platforms.py`, negative markers, HTTP status, dan confidence score.

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

Account/workspace enrichment yang aman: MX/TXT Google Workspace hints, Gmail domain hints, GitHub/GitLab public API enrichment, dan search pivot links.

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

Website-to-links enricher: title/meta, internal links, external links, email yang tampil di HTML, asset count, text sample, dan tracker hints seperti Google Analytics, GTM, Meta Pixel, Hotjar, Cloudflare Insights, Microsoft Clarity, Segment, dan Sentry.

Target: `domain`, `url`

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
- DNS record/IP,
- risk,
- signal.

Graph disimpan otomatis di report JSON/Markdown/HTML dan bisa diekspor khusus dengan:

```bash
python3 main.py hunt example.com --save --format graph
```
