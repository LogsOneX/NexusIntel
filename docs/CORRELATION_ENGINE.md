# Advanced Correlation Engine

The advanced correlation engine creates weighted hypotheses, not attribution facts.

## Weighted Features

- Shared username
- Shared avatar hash
- Shared favicon hash
- Shared external link
- Shared email domain
- Shared display name
- Shared bio phrase
- Shared location text
- Shared analytics ID
- Shared certificate/fingerprint
- Shared infrastructure
- Temporal proximity
- Contradiction penalty

## Output Types

- `possible_same_actor`
- `same_asset_reuse`
- `same_infrastructure`
- `same_operator_hypothesis`

Every correlation includes score, reasons, supporting evidence, contradicting evidence, and `requires_analyst_confirmation=true`.
