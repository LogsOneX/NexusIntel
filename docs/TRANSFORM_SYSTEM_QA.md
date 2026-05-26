# Transform System QA

This checklist verifies the production transform pipeline without fake intelligence or unsafe account probing.

## Manual Workflow

1. Create or open an investigation with an email seed.
2. Run `email_to_workspace`; confirm the request uses `POST /api/v1/transforms/run`, DNS warnings do not crash, and graph/evidence refresh.
3. Run `email_to_gravatar`; confirm 404/no avatar is represented as weak evidence or warning, not a crash.
4. Run `email_to_username_candidates`; confirm generated usernames enter the candidate lead bin and are not verified graph nodes.
5. Promote a candidate username, then run `username_to_profiles`; confirm public profile nodes remain candidate/probable unless target-specific evidence exists.
6. Run `domain_to_dns` and `domain_to_rdap`; confirm evidence and graph update with real source URLs/refs.
7. Run `ip_to_rdap_asn` against a public IP and a private IP; private IP should return a clear skipped/warning result.
8. Open Transform Library diagnostics and confirm disabled BYOK transforms explain missing keys.
9. Confirm disabled transforms such as direct email public profile pivot, favicon hash, reverse DNS, and phone deeplinks cannot be run.
10. Confirm telemetry reports accepted/completed/error only after backend responses, with real persisted counts.
11. Confirm evidence list, analyst pipeline, and case health refresh after transform completion.
12. Export report and confirm no serializer crash from missing timestamps.

## Local Smoke Script

Run:

```bash
PYTHONPATH=. python3 backend/scripts/smoke_transform_system.py
```

The script patches DNS/HTTP failures locally and checks that adapters return warnings or empty results instead of exceptions. It does not require API keys and does not perform credential, OTP, login, or private API activity.
