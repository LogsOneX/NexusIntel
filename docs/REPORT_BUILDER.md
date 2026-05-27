# Report Builder

## Export Endpoint
The analyst packet endpoint remains:

`GET /api/v1/investigations/{investigation_id}/exports/analyst-packet?format=pdf|html|json|csv|graph_json`

## Current Sections
The report builder supports analyst-selectable report intent and export formats. Backend exports preserve evidence-first behavior and must not add unsupported claims.

Report sections should include:
- Cover page and handling banner
- Executive summary
- Key judgments
- Scope and methodology
- Graph/entity/relationship summaries
- Evidence table and hashes
- IOC table
- Correlations
- Candidate leads and noise appendix when selected
- Compliance notes
- Timeline and recommended next steps

## Evidence Rules
Every report claim should be backed by evidence IDs, source URLs, hashes, or explicitly marked as insufficient evidence. Candidates and low-confidence signals must not be presented as verified attribution.

## UI Behavior
The Reports page now provides export controls for PDF, HTML, JSON, CSV IOC, and Graph JSON, plus options to include candidates, noise appendix, and graph snapshot context in the preview.
