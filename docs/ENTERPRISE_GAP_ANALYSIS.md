# NexusIntel Enterprise Gap Analysis

## Scope
This document tracks the gap between NexusIntel and enterprise OSINT/link-analysis platforms such as Maltego, SocialLinks, OSINT Industries, and StealthMole.

## Closed In This Upgrade
- Added a connector marketplace model with configured/enabled/testable state and legal/source notes.
- Expanded transform diagnostics with disabled transforms, missing adapters, missing API keys, counts by entity type, and connector setup recommendations.
- Added playbook metadata for analyst workflows rather than forcing single-transform guessing.
- Improved evidence operating-system scoring with freshness, directness, source reliability, report-safety, and contradiction indicators.
- Added import preview/storage paths for Maltego CSV, SpiderFoot CSV, Generic IOC CSV, and user-provided JSON exports.
- Added graph controls for candidate/signal visibility, confidence filtering, multi-select, neighbor selection, hide/show, and minimap orientation.

## Still Open
- Full lasso selection and undo/redo layout stacks remain roadmap items.
- External connector adapters beyond safe/local/BYOK metadata remain disabled until implemented and tested against official APIs.
- Connector test calls are deliberately conservative and do not probe private/authenticated surfaces.
- Graph collaboration and server-side layout persistence need a database-backed layout model.

## Safety Boundaries
NexusIntel must not perform credential attacks, OTP triggering, login bypass, CAPTCHA bypass, private API abuse, scraping behind authentication, or stalking automation. All enrichment must be public-source, official API, analyst-provided, or local reasoning with evidence citations.
