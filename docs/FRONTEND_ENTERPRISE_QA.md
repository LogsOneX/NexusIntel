# NexusIntel Frontend Enterprise QA

Use this checklist after graph UI, transform, and report changes. The backend remains the source of truth; no test should rely on fake graph nodes, fake cases, or synthetic intelligence.

## Graph Interaction

1. Open `/graph` with a real or detached investigation.
2. Drag a node by its glyph/card and confirm it moves smoothly.
3. Confirm dragging a node does not accidentally close/open the transform popover.
4. Pan the empty canvas with left-drag.
5. Pan with middle mouse.
6. Hold Space and drag to pan.
7. Scroll up over the canvas and confirm cursor-centered zoom in.
8. Scroll down over the canvas and confirm cursor-centered zoom out.
9. Confirm zoom stays clamped and the percentage control remains accurate.
10. Click Fit Graph and confirm all visible nodes fit with padding.
11. Switch Force, Tree, Orbit/Circular, and Manual layouts.
12. Drag a node, refresh graph data via lookup/transform, and confirm existing node positions remain stable.

## Transform Workflow

1. Click a node and confirm the inspector opens.
2. Confirm `NodeActionPopover` appears beside the selected node.
3. Right-click the node and confirm the full transform list opens.
4. Confirm transforms come from `/api/v1/transforms/registry` compatibility by node type.
5. Run a valid transform and confirm the request uses `POST /api/v1/transforms/run`.
6. Confirm telemetry opens on transform start.
7. Confirm transform errors show in the popover and telemetry without fake success.
8. Confirm graph data updates from the backend response.
9. Confirm evidence, health, and analyst pipeline refresh after successful transform.
10. Confirm selected node remains selected when still present in the updated graph.

## Drawers And Pages

1. Open Case Dock and close it from its internal X button.
2. Open Entity Palette and close it from its internal X button.
3. Open Entity Inspector and close it from its internal X button.
4. Open Telemetry and close it from its internal X button.
5. Press Escape and confirm the topmost overlay closes.
6. Confirm Case Dock, Palette, Inspector, Evidence Drawer, and Telemetry scroll internally.
7. Confirm `/dashboard` scrolls vertically when content exceeds the viewport.
8. Confirm `/workspace` or `/cases` scrolls vertically.
9. Confirm `/reports` scrolls vertically.
10. Confirm `/settings`, `/evidence`, `/transforms`, `/oracle`, `/account`, and `/watchlist` scroll vertically.
11. Confirm `/graph` does not page-scroll and only the graph stage pans/zooms.

## Report Export

1. Open `/reports`.
2. Select a real case.
3. Click Compile & Export PDF Dossier.
4. Confirm the endpoint is `/api/v1/investigations/{id}/exports/analyst-packet?format=pdf`.
5. Confirm the PDF contains a cover page, summary, scope, entity table, relationship table, evidence table, confidence section, noise, leads, correlations, next steps, hashes, page numbers, and report hash.
6. Confirm unsupported findings are labeled as insufficient evidence.
7. Confirm HTML, JSON, CSV, and graph JSON exports still work from their existing endpoints.

## Regression Guardrails

1. Login/session still works.
2. Case loading, creation, deletion, and selection still work.
3. Add entity still calls production logic.
4. Lookup opens telemetry and uses production endpoint behavior.
5. Candidate promote, mark noise, noise restore, compliance log, evidence viewer, settings/connectors, and local investigator panels still work.
6. No fake cases, fake telemetry, fake API keys, fake graph nodes, or fake report content appear in runtime UI.
7. Narrow viewport has no horizontal page or toolbar scroll.
8. `npm run typecheck`, `npm run build`, `python3 -m compileall backend`, and `docker compose config` pass.
