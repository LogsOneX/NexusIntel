# Report Readiness

Report Readiness menilai apakah kasus cukup kuat untuk diekspor sebagai analyst packet.

## Faktor

- Evidence completeness.
- Confidence quality.
- Unresolved contradictions.
- Noise level.
- Source diversity.
- Attribution risk.
- Coverage gaps.

## Output

- `score`
- `blockers`
- `warnings`
- `recommended_actions`
- `report_safe_findings`
- `findings_not_safe_to_report`

Finding tanpa evidence vault/source URL/raw hash akan ditandai tidak siap untuk laporan final.

## Endpoint

- `GET /api/v1/investigations/{id}/report-readiness`

## Scoring Inputs

- Evidence completeness.
- Confidence quality.
- Source diversity.
- Unresolved contradictions.
- Remaining noise.
- Attribution risk.
- Coverage gaps.
- Timeline completeness when timestamps exist.
