# NexusIntel Blueprint

NexusIntel adalah OSINT investigation platform standalone yang menggabungkan graph workflow, transform-style investigation, dan data panel industri. Semua runtime core berada di repo ini.

## Canonical Runtime

```text
frontend/src/App.jsx
frontend/src/components/CommandCenter.tsx
frontend/src/components/GraphCanvas.tsx
frontend/src/components/CustomNode.tsx
frontend/src/layouts/
frontend/src/pages/
frontend/src/components/{cases,common,entity,evidence,import,transforms}/
frontend/src/lib/
backend/main.py
backend/tasks.py
backend/recon_validators.py
backend/modules/
backend/osint/
docker-compose.yml
```

## Product Goals

- Graph-first investigation seperti Flowsint/Maltego.
- Context transform dari node, bukan module picker mentah.
- Drag-and-drop entity pipeline untuk menambah pivot langsung ke canvas.
- Deep entity data table seperti OSINT.Industries.
- Live terminal HUD untuk melihat worker bergerak.
- Minimalist monochrome intelligence UI: black, anthracite, white/gray, 1px borders, sharp tactical layout.
- Public-source, free, dan deployable dengan satu command.

## Investigation Loop

```text
seed target
  -> root entity
  -> transform
  -> task record
  -> recon validator
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
- Public profile candidate URL generation.

### Email and Workspace

- Regex email validation.
- Email local-part/domain split.
- MX/TXT lookup.
- DMARC and BIMI lookup.
- Disposable-domain hint.
- Google/Microsoft/Zoho/Proton workspace hints.
- Gravatar hash/avatar check in standard/aggressive modes.
- Guardrail for registration probing and breach corpus dependency.

### Domain and Infrastructure

- A/AAAA/CNAME/MX/NS/TXT/CAA lookup.
- RDAP domain/IP lookup.
- crt.sh passive subdomain collection.
- Reverse DNS for IP pivots.
- GeoIP/ASN hint through free public source.
- IP node extraction.
- DNS record graphing.
- Candidate subdomain resolution in standard/aggressive modes.

### Phone

- E.164 validation.
- Country calling code parsing.
- Public numbering-plan line-type hint.
- Guardrail for messaging-app account-existence probing.

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
