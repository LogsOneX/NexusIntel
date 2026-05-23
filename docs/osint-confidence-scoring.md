# Confidence Scoring

NexusIntel confidence is evidence-first and conservative.

Labels:

- 95-100: confirmed primary/public authoritative.
- 80-94: strong corroborated public evidence.
- 60-79: probable.
- 40-59: weak/candidate.
- 0-39: noise/low confidence.

Score inputs:

- Source reliability.
- Evidence directness.
- Freshness and timestamp availability.
- Corroboration count.
- Contradiction count.
- False-positive risk.
- Generic infrastructure/login page penalty.

Every persisted SDK artifact carries `confidence_score`, `confidence_reason`, `evidence_grade`, and `raw_evidence_ref` where available. Candidate usernames derived from email local-parts stay weak until corroborated by public profiles or analyst evidence.
