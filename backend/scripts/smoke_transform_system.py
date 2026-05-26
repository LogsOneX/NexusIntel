#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.osint.adapters import domain as domain_adapters
from backend.osint.adapters import email as email_adapters
from backend.osint.adapters.domain import DomainCTAdapter, DomainDNSAdapter, DomainRDAPAdapter, IPRDAPAdapter
from backend.osint.adapters.email import EmailDomainWorkspaceAdapter, GravatarAdapter, UsernameCandidateAdapter
from backend.osint.registry import registry
from backend.osint.types import EntityInput, RunContext


class _FakeResponse:
    def __init__(self, status_code: int = 404, text: str = "not found", url: str = "https://example.invalid/") -> None:
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": "text/plain"}
        self.url = url

    def json(self) -> Any:
        return []

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("fake http error", request=None, response=None)


class _FakeAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(status_code=404, text="not found", url=url)


@contextmanager
def failing_dns():
    original_email = email_adapters.dns.resolver.resolve
    original_domain = domain_adapters.dns.resolver.resolve

    def _fail(*args: Any, **kwargs: Any) -> None:
        raise email_adapters.dns.resolver.NXDOMAIN()

    email_adapters.dns.resolver.resolve = _fail
    domain_adapters.dns.resolver.resolve = _fail
    try:
        yield
    finally:
        email_adapters.dns.resolver.resolve = original_email
        domain_adapters.dns.resolver.resolve = original_domain


@contextmanager
def fake_http():
    original_email = email_adapters.httpx.AsyncClient
    original_domain = domain_adapters.httpx.AsyncClient
    email_adapters.httpx.AsyncClient = _FakeAsyncClient
    domain_adapters.httpx.AsyncClient = _FakeAsyncClient
    try:
        yield
    finally:
        email_adapters.httpx.AsyncClient = original_email
        domain_adapters.httpx.AsyncClient = original_domain


async def main() -> int:
    diagnostics = registry.validate_registry()
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    if diagnostics["errors"]:
        failures.append(f"registry errors: {diagnostics['errors']}")
    checks.append({"check": "registry_diagnostics", "errors": len(diagnostics["errors"]), "warnings": len(diagnostics["warnings"])})

    ctx = RunContext(investigation_id="smoke", run_id="smoke-run", api_keys={}, options={})
    email = EntityInput(type="email", value="test@example.com", label="test@example.com")

    candidates = await UsernameCandidateAdapter().run(email, ctx)
    if not candidates.artifacts or any(item.type != "username_candidate" for item in candidates.artifacts):
        failures.append("email.username_candidates did not return username_candidate artifacts")
    if candidates.raw_evidence:
        failures.append("email.username_candidates should not create raw evidence")
    checks.append({"check": "email_to_username_candidates", "artifacts": len(candidates.artifacts), "evidence": len(candidates.raw_evidence), "status": candidates.status})

    with failing_dns():
        workspace = await EmailDomainWorkspaceAdapter().run(email, ctx)
        dns_result = await DomainDNSAdapter().run(EntityInput(type="domain", value="example.com"), ctx)
    if workspace.status == "failed":
        failures.append("email.domain_workspace returned failed status under DNS failure")
    if not workspace.raw_evidence:
        failures.append("email.domain_workspace should capture raw evidence even when DNS is empty")
    checks.append({"check": "email_to_workspace_dns_failure", "artifacts": len(workspace.artifacts), "evidence": len(workspace.raw_evidence), "warnings": workspace.warnings, "status": workspace.status})
    checks.append({"check": "domain_to_dns_dns_failure", "artifacts": len(dns_result.artifacts), "evidence": len(dns_result.raw_evidence), "status": dns_result.status})

    with fake_http():
        gravatar = await GravatarAdapter().run(email, ctx)
        rdap = await DomainRDAPAdapter().run(EntityInput(type="domain", value="example.com"), ctx)
        ct = await DomainCTAdapter().run(EntityInput(type="domain", value="example.com"), ctx)
        private_ip = await IPRDAPAdapter().run(EntityInput(type="ip", value="10.0.0.1"), ctx)
    if not gravatar.artifacts or gravatar.artifacts[0].type != "avatar_hash":
        failures.append("email.gravatar should keep weak avatar_hash artifact on HTTP 404")
    checks.append({"check": "email_to_gravatar_http_404", "artifacts": len(gravatar.artifacts), "evidence": len(gravatar.raw_evidence), "status": gravatar.status})
    checks.append({"check": "domain_to_rdap_http_404", "artifacts": len(rdap.artifacts), "evidence": len(rdap.raw_evidence), "warnings": rdap.warnings, "status": rdap.status})
    checks.append({"check": "domain_to_ct_http_404", "artifacts": len(ct.artifacts), "evidence": len(ct.raw_evidence), "warnings": ct.warnings, "status": ct.status})
    checks.append({"check": "ip_to_rdap_private_ip", "artifacts": len(private_ip.artifacts), "evidence": len(private_ip.raw_evidence), "warnings": private_ip.warnings, "status": private_ip.status})

    missing_key_transforms = [item for item in diagnostics["transforms"] if any(str(reason).startswith("missing_api_key") for reason in item["reasons"])]
    if not missing_key_transforms:
        failures.append("expected at least one BYOK transform to report missing_api_key")
    checks.append({"check": "byok_missing_key_diagnostics", "disabled_missing_key_transforms": [item["transform_id"] for item in missing_key_transforms]})

    payload = {"ok": not failures, "failures": failures, "checks": checks}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
