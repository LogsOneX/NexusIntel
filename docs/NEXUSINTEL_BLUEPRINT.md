# NexusIntel Blueprint

NexusIntel adalah OSINT investigation platform standalone yang menggabungkan graph workflow, transform-style investigation, dan data panel industri. Semua runtime core berada di repo ini.

## Canonical Runtime

```text
frontend/src/components/Dashboard.tsx
frontend/src/components/GraphCanvas.tsx
backend/main.py
backend/tasks.py
docker-compose.yml
```

## Product Goals

- Graph-first investigation seperti Flowsint/Maltego.
- Context transform dari node, bukan module picker mentah.
- Deep entity data table seperti OSINT.Industries.
- Live terminal HUD untuk melihat worker bergerak.
- Public-source, free, dan deployable dengan satu command.

## Investigation Loop

```text
seed target
  -> root entity
  -> transform
  -> task record
  -> live logs
  -> normalized entities
  -> directed relationships
  -> inspect node
  -> next transform
```

## Transform Families

### Identity

- Username presence sweep.
- Public profile normalization.
- Platform/service node generation.
- Local-part pivot dari email.

### Email and Workspace

- Email local-part/domain split.
- MX/TXT lookup.
- DMARC and BIMI lookup.
- Google/Microsoft/Zoho/Proton workspace hints.
- Gravatar hash/avatar check in standard/aggressive modes.

### Domain and Infrastructure

- A/AAAA/MX/NS/TXT/CAA lookup.
- IP node extraction.
- DNS record graphing.
- Candidate subdomain resolution in standard/aggressive modes.

## Graph Schema

Entity fields:

- `id`
- `type`
- `label`
- `value`
- `source`
- `confidence`
- `data`

Relationship fields:

- `id`
- `source`
- `target`
- `type`
- `confidence`
- `data`

## Runtime Boundaries

`nexusrecon/`, `core/`, `modules/`, dan `recon/` tetap menjadi local intelligence engine. Backend baru memanggilnya melalui wrapper root-level agar platform bisa berjalan sebagai service modern.

## References

Project referensi dipakai untuk belajar pola:

- Flowsint: graph investigation, flows, enricher UX.
- Maltego: node expansion mental model.
- OSINT.Industries: deep structured data presentation.
- Maigret/Sherlock: username discovery concept.
- GHunt: async CLI/export style and Google OSINT thinking.
- Holehe: account-presence schema idea.

Tidak ada vendor code yang di-copy ke runtime core.
