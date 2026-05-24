# Legal and Compliance Guardrails

NexusIntel dirancang untuk lawful, passive, public-source OSINT dan official/BYOK connectors.

## Larangan Teknis

- Tidak ada credential stuffing.
- Tidak ada account takeover logic.
- Tidak ada password reset probing yang memicu email, OTP, 2FA, lockout, atau perubahan state.
- Tidak ada account creation, spam, CAPTCHA bypass, rate-limit evasion, atau private API abuse.
- Tidak ada illegal scraping atau scraping behind authentication.
- Tidak menyimpan raw leaked credentials, raw stolen PII, credit cards, atau illegal breach dumps.
- Tidak memasukkan synthetic/demo intelligence ke real graph.

## Data Minimization

- Simpan artifact yang relevan dengan case dan legal basis.
- Candidate dan noise dipisahkan dari graph utama.
- Raw payload harus punya hash dan provenance; akses raw evidence harus eksplisit.

## Source Attribution

Setiap artifact idealnya memiliki:

- source
- source_url
- fetched_at
- confidence_score
- confidence_reason
- evidence_grade
- raw_evidence_ref
- legal_basis
- public_source_note

## AI Oracle

AI hanya boleh:

- summarize case evidence
- suggest lawful transforms
- identify weak evidence
- identify coverage gaps
- explain confidence
- draft reports with caveats

AI tidak boleh menyatakan guilt, criminal status, atau identity certainty tanpa direct, public, independently corroborated evidence.
