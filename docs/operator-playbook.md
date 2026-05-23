# Operator Playbook

1. Create a case or add a manual seed entity. Adding an entity does not run lookup.
2. Select a node and open Transform Library in Entity Data.
3. Run only transforms that are valid for that node type. Disabled transforms require BYOK or are not implemented.
4. Review Evidence before treating a node as intelligence.
5. Use confidence reason to separate confirmed facts, candidates, and noise.
6. Mark false positives/noise from the graph instead of forcing attribution.
7. For Google Maps, use only analyst-supplied public profile/place URLs.
8. For phone data, use numbering-plan and official BYOK lookup only; do not claim messenger registration from deeplinks alone.
9. For breach data, configure official HIBP BYOK; no unofficial breach scraping.
10. Export reports only after evidence refs and confidence explanations are present.
