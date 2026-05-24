# Repository Cleanup Audit

Date: 2026-05-24
Scope: NexusIntel repository structure cleanup and professionalization.

## Summary

This cleanup was performed with static usage checks before deletion. Files were searched by filename/component name/import path across frontend, backend, docs, Docker, Makefile, tests, and CLI entry points. Generated/cache artifacts were removed where permissions allowed. Uncertain legacy code was kept and documented.

## Cleanup Map

| file/path | category | reason | action taken | risk level | verification command |
|---|---|---|---|---|---|
| `backend/main.py` | PRODUCTION_ACTIVE | FastAPI API gateway, settings, auth, cases, graph, transforms, evidence, exports. | Kept | High | `python3 -m py_compile backend/main.py` |
| `backend/tasks.py` | PRODUCTION_ACTIVE | Celery worker entrypoint imported by API and Docker workers. | Kept | High | `python3 -m py_compile backend/tasks.py` |
| `backend/recon_validators.py` | PRODUCTION_ACTIVE | Runtime normalization layer imported by `backend/tasks.py`. | Kept | High | `python3 -m py_compile backend/recon_validators.py` |
| `backend/queues.py` | PRODUCTION_ACTIVE | Celery queue routing and NSA-grade queue isolation references. | Kept | Medium | `python3 -m compileall backend` |
| `backend/modules/` | PRODUCTION_ACTIVE | Runtime OSINT modules imported by API/workers/adapters. | Kept | High | `rg "backend.modules" backend tests` |
| `backend/modules/opsec_http.py` | UNKNOWN_KEEP | Not directly imported by API/tasks in current scan, but part of OPSEC/proxy architecture and uses `ProxyRotator`. | Kept and documented | Medium | `rg "opsec_http|OpsecHttp" backend` |
| `backend/osint/` | PRODUCTION_ACTIVE | Adapter SDK, registry, importers, scoring, analyst pipeline, tests and API imports. | Kept | High | `rg "backend.osint" backend tests` |
| `frontend/src/App.jsx` | PRODUCTION_ACTIVE | React mount imports `CommandCenter`. | Kept | High | `npm run typecheck && npm run build` |
| `frontend/src/components/CommandCenter.tsx` | PRODUCTION_ACTIVE | Current session/routing/graph hub orchestration. | Kept | High | `rg "CommandCenter" frontend/src` |
| `frontend/src/components/GraphCanvas.tsx` | PRODUCTION_ACTIVE | Active Cytoscape graph canvas. | Kept | High | `rg "GraphCanvas" frontend/src` |
| `frontend/src/components/CustomNode.tsx` | PRODUCTION_ACTIVE | Imported by `GraphCanvas.tsx` for entity palette/icons. | Kept | High | `rg "CustomNode|EntityPaletteItem|platformMark" frontend/src` |
| `frontend/src/components/OraclePanel.tsx` | PRODUCTION_ACTIVE | Used by graph/workspace/oracle pages. | Kept | Medium | `rg "OraclePanel" frontend/src` |
| `frontend/src/components/PresenceBar.tsx` | PRODUCTION_ACTIVE | Used by graph hub. | Kept | Medium | `rg "PresenceBar" frontend/src` |
| `frontend/src/components/TimelineView.tsx` | PRODUCTION_ACTIVE | Imported by `GraphCanvas.tsx`. | Kept | Medium | `rg "TimelineView" frontend/src` |
| `frontend/src/components/{cases,common,entity,evidence,import,transforms}/` | PRODUCTION_ACTIVE | Current modular UI created by frontend refactor and imported by pages/CommandCenter. | Kept | Medium | `rg "components/(cases|common|entity|evidence|import|transforms)" frontend/src` |
| `frontend/src/layouts/` | PRODUCTION_ACTIVE | AppShell/sidebar/top intel bar imported by CommandCenter/pages. | Kept | Medium | `rg "../layouts|layouts/" frontend/src` |
| `frontend/src/pages/` | PRODUCTION_ACTIVE | Current dashboard/workspace/settings/oracle/account page modules. | Kept | Medium | `rg "../pages|pages/" frontend/src` |
| `frontend/src/lib/` | PRODUCTION_ACTIVE | Shared API/types/graph/confidence/session helpers imported across UI. | Kept | Medium | `rg "../lib|../../lib" frontend/src` |
| `frontend/src/components/Dashboard.tsx` | DUPLICATE_OR_STALE | Old single-file dashboard prototype. No production imports; superseded by `CommandCenter.tsx` + `pages/`. | Deleted | Low | `rg "Dashboard.tsx|from .*Dashboard|<Dashboard" frontend README.md docs` |
| `frontend/src/components/FlowCanvas.tsx` | DUPLICATE_OR_STALE | Wrapper around `GraphCanvas`; no production imports; docs were stale. | Deleted | Low | `rg "FlowCanvas.tsx|from .*FlowCanvas|<FlowCanvas" frontend README.md docs` |
| `frontend/src/components/CryptoWalletNode.tsx` | DEAD_CODE | Standalone component not imported anywhere. Crypto node rendering is handled by Cytoscape styles in `GraphCanvas.tsx`. | Deleted | Low | `rg "CryptoWalletNode" .` |
| `frontend/src/components/HypotheticalEdgeLegend.tsx` | DEAD_CODE | Standalone legend not imported anywhere. | Deleted | Low | `rg "HypotheticalEdgeLegend" .` |
| `frontend/src/components/ProvenancePanel.tsx` | DEAD_CODE | Superseded by evidence drawer/inspector and not imported anywhere. | Deleted | Low | `rg "ProvenancePanel" .` |
| `frontend/src/components/WatchlistPanel.tsx` | DEAD_CODE | Not imported by current dashboard or watchlist endpoints. | Deleted | Low | `rg "WatchlistPanel" .` |
| `frontend/src/styles.css` | PRODUCTION_ACTIVE | Current global visual system. Duplicate obsolete sections remain a future refactor risk, but file is actively imported by `main.jsx`. | Kept, polished earlier | Medium | `rg "styles.css" frontend/src` |
| `frontend/dist/` | GENERATED_ARTIFACT | Vite build output. | Deleted | None | `git status --ignored --short` |
| `frontend/node_modules/` | GENERATED_ARTIFACT | Local dependency install. Ignored and untracked; kept locally to allow validation without network install. | Kept ignored | None | `git status --ignored --short` |
| `backend/**/__pycache__/`, `tests/__pycache__/` | GENERATED_ARTIFACT | Python bytecode caches. | Deleted | None | `find backend tests -name __pycache__` |
| `data/` | GENERATED_ARTIFACT | Docker PostgreSQL/Redis runtime data. | Attempted delete; permission denied by local ownership. Kept ignored and documented. | None | `rm -rf data` |
| `.gitignore` | DOCUMENTATION_ACTIVE | Repo hygiene rules. | Updated | Low | `git diff -- .gitignore` |
| `README.md` | DOCUMENTATION_ACTIVE | Primary project documentation. | Updated active structure references | Low | `rg "Dashboard.tsx|FlowCanvas.tsx" README.md` |
| `docs/ARCHITECTURE.md` | DOCUMENTATION_ACTIVE | Architecture documentation. | Updated frontend canonical section | Low | `rg "Dashboard.tsx|FlowCanvas.tsx" docs/ARCHITECTURE.md` |
| `docs/DASHBOARD.md` | DOCUMENTATION_ACTIVE | Dashboard usage docs. | Updated active canvas note | Low | `rg "FlowCanvas" docs/DASHBOARD.md` |
| `docs/DEPLOYMENT.md` | DOCUMENTATION_ACTIVE | Deployment docs. | Updated runtime file list | Low | `rg "Dashboard.tsx|FlowCanvas.tsx" docs/DEPLOYMENT.md` |
| `docs/REFERENCES.md` | DOCUMENTATION_ACTIVE | Reference attribution docs. | Updated frontend implementation reference | Low | `rg "Dashboard.tsx" docs/REFERENCES.md` |
| `docs/NEXUSINTEL_BLUEPRINT.md` | DOCUMENTATION_ACTIVE | Product blueprint. | Updated canonical runtime list | Low | `rg "Dashboard.tsx|FlowCanvas.tsx" docs/NEXUSINTEL_BLUEPRINT.md` |
| `docs/PROJECT_STRUCTURE.md` | DOCUMENTATION_ACTIVE | Current repo structure. | Created | Low | `sed -n '1,220p' docs/PROJECT_STRUCTURE.md` |
| `core/` | COMPATIBILITY_ACTIVE | Imported by root CLI and Makefile readiness target. | Kept | High | `rg "from core|import core" main.py modules core Makefile` |
| `modules/` | COMPATIBILITY_ACTIVE | Legacy CLI modules loaded by `core.engine`; still documented and used for CLI. | Kept | High | `rg "modules/|from modules|AnalyticsEngine" docs main.py core` |
| `nexusrecon/` | COMPATIBILITY_ACTIVE | `backend/tasks.py` imports `nexusrecon.main.NexusRecon`. | Kept | High | `rg "nexusrecon" backend main.py docs` |
| `recon/` | COMPATIBILITY_ACTIVE | Imported by root CLI and legacy modules. | Kept | High | `rg "from recon|import recon" main.py modules recon` |
| `dashboard/` | COMPATIBILITY_ACTIVE | Imported by root CLI for `python3 main.py dashboard`. | Kept | Medium | `rg "dashboard.server|serve_dashboard" main.py docs Makefile` |
| `.agents/`, `.codex/` | UNKNOWN_KEEP | Local hidden directories found but empty/untracked in this scan. | Kept | Low | `find .agents .codex -maxdepth 2 -type f` |
| `docker-compose.yml`, `Makefile`, `start.sh`, `.env.example` | PRODUCTION_ACTIVE | Deployment and local operations. | Kept | High | `docker compose config` |
| `tests/test_osint_sdk.py` | PRODUCTION_ACTIVE | Current Python SDK/service test coverage. | Kept | Medium | `python3 -m unittest tests/test_osint_sdk.py` |

## Deleted Files

- `frontend/src/components/Dashboard.tsx`
- `frontend/src/components/FlowCanvas.tsx`
- `frontend/src/components/CryptoWalletNode.tsx`
- `frontend/src/components/HypotheticalEdgeLegend.tsx`
- `frontend/src/components/ProvenancePanel.tsx`
- `frontend/src/components/WatchlistPanel.tsx`
- `frontend/dist/`
- Python `__pycache__/` directories under `backend/`, `backend/modules/`, `backend/osint/`, and `tests/`

## Generated Artifacts Still Present Locally

- `frontend/node_modules/` is ignored and untracked. It was kept to allow local `npm run typecheck` and `npm run build` without a network reinstall.
- `data/` is ignored and untracked. Removal was attempted but local permissions denied access to Docker-created PostgreSQL/Redis files.

## Second-Pass Hygiene Review

| check | finding | action taken | risk level | verification command |
|---|---|---|---|---|
| Unused frontend imports | `KeyRound` in `TransformCard.tsx` was unused under `tsc --noUnusedLocals`. | Removed unused import | Low | `cd frontend && npm exec tsc -- --noEmit --noUnusedLocals --noUnusedParameters` |
| Deleted-file docs references | Operational docs still mentioned removed prototype files as historical notes. | Removed stale names from `docs/DASHBOARD.md` and `docs/DEPLOYMENT.md`; kept only cleanup-audit references. | Low | `rg 'Dashboard\.tsx|FlowCanvas\.tsx|CryptoWalletNode|HypotheticalEdgeLegend|ProvenancePanel|WatchlistPanel' README.md docs frontend --glob '!frontend/node_modules/**'` |
| Stale CSS selectors | CSS still contained selectors for deleted standalone components and old `graph-command-bar`. | Removed `crypto-wallet-node`, `hypothetical-edge-legend`, `flat-intel-panel`, `watchlist-row(s)`, and `graph-command-bar` CSS blocks. | Low | `rg 'crypto-wallet-node|hypothetical-edge-legend|graph-command-bar|flat-intel-panel|watchlist-row|watchlist-rows' frontend/src` |
| Empty local folders | Empty untracked `.agents/` and `.codex/` directories were present. | Removed with `rmdir` after confirming they contained no files. | Low | `find . -type d -empty -not -path './.git/*' -not -path './frontend/node_modules/*' -not -path './data/*'` |
| Package/dependency bloat | React, ReactDOM, Vite, Cytoscape, Lucide, Yjs, y-websocket, and Zustand are all referenced by runtime source or build tooling. | Kept dependencies unchanged. | Low | `rg "from ['\"](cytoscape|lucide-react|react|react-dom|yjs|y-websocket|zustand)" frontend/src` |
| Generated tracked files | No tracked build/cache/runtime artifacts found. | No tracked artifact deletion needed beyond first pass. | Low | `git ls-files | rg '(^|/)(dist|build|node_modules|__pycache__|data)(/|$)|\.(pyc|pyo|log|sqlite|db)$'` |

## Validation Results

| command | result | notes |
|---|---|---|
| `cd frontend && npm run typecheck` | Pass | TypeScript compiled with `tsc --noEmit`. |
| `cd frontend && npm exec tsc -- --noEmit --noUnusedLocals --noUnusedParameters` | Pass | Second-pass unused import/type hygiene check passed. |
| `cd frontend && npm run build` | Pass | Vite production build completed. Vite reported the existing large chunk warning for the main bundle; no build failure. Build output was removed afterward because `frontend/dist/` is generated. |
| `python3 -m py_compile backend/main.py backend/tasks.py backend/recon_validators.py` | Pass | Core backend entrypoints compile. |
| `python3 -m compileall backend` | Pass | Backend package compile completed. Generated `__pycache__/` directories were removed afterward. |
| `docker compose config` | Pass | Compose file renders successfully. |
| `python3 -m unittest tests/test_osint_sdk.py` | Pass | OSINT SDK unit tests ran 8 tests successfully. |
| `rg 'Dashboard\.tsx|FlowCanvas\.tsx|CryptoWalletNode|HypotheticalEdgeLegend|ProvenancePanel|WatchlistPanel' README.md docs frontend --glob '!frontend/node_modules/**'` | Pass | Remaining references are intentional cleanup notes/audit entries only, not runtime imports. |

## Remaining Recommendations

1. Split `frontend/src/styles.css` into layered files (`tokens`, `layout`, `graph`, `components`) after the current UI stabilizes. It is active but very large due historical overrides.
2. Review `backend/modules/opsec_http.py` once OPSEC HTTP client usage is finalized. It is kept as `UNKNOWN_KEEP` because it belongs to the proxy/OPSEC architecture but is not directly imported by API/tasks in this scan.
3. Consider adding a dedicated frontend lint command later. Current validation relies on TypeScript and Vite build.
