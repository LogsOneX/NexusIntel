from __future__ import annotations

import asyncio
from typing import Any

import dns.resolver

from .common import AsyncHttpClient, EmitCallback, ReconFinding, md5_lower, maybe_emit, normalize_domain, public_metadata

try:
    import aiodns  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    aiodns = None


class AsyncDNSResolver:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.resolver = aiodns.DNSResolver(timeout=timeout) if aiodns else None

    async def resolve(self, domain: str, record_type: str) -> list[str]:
        if self.resolver:
            try:
                answers = await self.resolver.query(domain, record_type)
                values: list[str] = []
                for item in answers:
                    if record_type == "MX":
                        values.append(str(getattr(item, "host", "")).rstrip("."))
                    elif record_type == "TXT":
                        text = getattr(item, "text", None)
                        values.append(str(text if text is not None else item).strip('"'))
                    else:
                        values.append(str(getattr(item, "host", None) or getattr(item, "text", None) or item).rstrip("."))
                return sorted({value for value in values if value})
            except Exception:
                return []
        return await asyncio.to_thread(self._sync_resolve, domain, record_type)

    def _sync_resolve(self, domain: str, record_type: str) -> list[str]:
        try:
            answers = dns.resolver.resolve(domain, record_type, lifetime=self.timeout)
        except Exception:
            return []
        values: list[str] = []
        for answer in answers:
            if record_type == "MX":
                values.append(str(answer.exchange).rstrip("."))
            elif record_type == "TXT":
                chunks = getattr(answer, "strings", None)
                if chunks:
                    values.append("".join(part.decode("utf-8", "ignore") for part in chunks))
                else:
                    values.append(str(answer).strip('"'))
            else:
                values.append(str(answer).rstrip("."))
        return sorted(set(values))


class WorkspaceResolver:
    def __init__(self, *, timeout: float = 8.0):
        self.timeout = timeout
        self.dns = AsyncDNSResolver(timeout=min(timeout, 6.0))

    @staticmethod
    def infer_services(domain: str, mx: list[str], txt: list[str]) -> list[ReconFinding]:
        joined_mx = " ".join(mx).lower()
        joined_txt = " ".join(txt).lower()
        findings: list[ReconFinding] = []
        providers = [
            ("Google Workspace", "google", "google.com" in joined_mx or "googlemail.com" in joined_mx or domain in {"gmail.com", "googlemail.com"}),
            ("Microsoft 365", "microsoft", "protection.outlook.com" in joined_mx or "outlook.com" in joined_mx or "hotmail.com" in domain),
            ("Proton Mail", "proton", "protonmail" in joined_mx or domain in {"proton.me", "protonmail.com"}),
            ("Zoho Mail", "zoho", "zoho" in joined_mx),
            ("Fastmail", "fastmail", "messagingengine.com" in joined_mx or "fastmail" in joined_mx),
            ("Yandex 360", "yandex", "yandex" in joined_mx),
            ("Amazon SES", "aws", "amazonses" in joined_mx or "amazonses" in joined_txt),
            ("Mailgun", "mailgun", "mailgun" in joined_txt or "mailgun" in joined_mx),
            ("SendGrid", "sendgrid", "sendgrid" in joined_txt or "sendgrid" in joined_mx),
        ]
        for label, key, matched in providers:
            if matched:
                findings.append(
                    ReconFinding(
                        "service",
                        label,
                        f"{domain}:{key}",
                        "ghost_workspace",
                        "high" if key in {"google", "microsoft", "proton"} else "medium",
                        "USES_SERVICE",
                        {"provider_key": key, "evidence": "public_mx_txt"},
                    )
                )
        if "spf1" in joined_txt:
            findings.append(ReconFinding("email_security", "SPF Policy", f"{domain}:spf", "ghost_workspace", "medium", "HAS_EMAIL_SECURITY", {"policy": "SPF"}))
        if any("dmarc" in record.lower() or "v=dmarc1" in record.lower() for record in txt):
            findings.append(ReconFinding("email_security", "DMARC Policy", f"{domain}:dmarc", "ghost_workspace", "medium", "HAS_EMAIL_SECURITY", {"policy": "DMARC"}))
        if any("v=bimi1" in record.lower() for record in txt):
            findings.append(ReconFinding("email_security", "BIMI Policy", f"{domain}:bimi", "ghost_workspace", "medium", "HAS_EMAIL_SECURITY", {"policy": "BIMI"}))
        return findings

    async def microsoft_tenant_hint(self, client: AsyncHttpClient, domain: str) -> ReconFinding | None:
        url = f"https://login.microsoftonline.com/{domain}/v2.0/.well-known/openid-configuration"
        result = await client.request_text("GET", url, retries=1)
        if int(result.get("status") or 0) == 200 and "authorization_endpoint" in str(result.get("text") or ""):
            return ReconFinding("tenant", "Microsoft tenant discovery", f"microsoft:{domain}", "ghost_workspace", "medium", "HAS_TENANT_HINT", {"endpoint": url, "status_code": 200})
        return None

    async def public_document_hint(self, client: AsyncHttpClient, label: str, url: str, marker: str | None = None) -> ReconFinding | None:
        result = await client.request_text("GET", url, retries=1, max_bytes=180_000)
        status = int(result.get("status") or 0)
        text = str(result.get("text") or "")
        if status >= 400 or not text:
            return None
        if marker and marker.lower() not in text[:80_000].lower():
            return None
        return ReconFinding(
            "public_workspace_document",
            label,
            url,
            "ghost_workspace",
            "medium",
            "EXPOSES_PUBLIC_WORKSPACE_DOCUMENT",
            {"status_code": status, "final_url": result.get("url"), "metadata": public_metadata(text), "sample": text[:600]},
        )

    async def gravatar(self, client: AsyncHttpClient, email: str) -> ReconFinding:
        digest = md5_lower(email)
        url = f"https://www.gravatar.com/avatar/{digest}?d=404"
        result = await client.request_text("GET", url, max_bytes=512, retries=1)
        exists = int(result.get("status") or 0) == 200
        return ReconFinding(
            "avatar_hash",
            "Gravatar MD5",
            digest,
            "ghost_workspace",
            "high" if exists else "low",
            "HAS_PUBLIC_AVATAR_HASH",
            {"hash": digest, "exists": exists, "status_code": result.get("status"), "url": url},
        )

    async def resolve(self, target: str, *, emit: EmitCallback | None = None) -> dict[str, Any]:
        email = target.strip().lower()
        domain = normalize_domain(email.rsplit("@", 1)[-1] if "@" in email else email)
        tasks = {
            "MX": self.dns.resolve(domain, "MX"),
            "TXT": self.dns.resolve(domain, "TXT"),
            "DMARC": self.dns.resolve(f"_dmarc.{domain}", "TXT"),
            "BIMI": self.dns.resolve(f"default._bimi.{domain}", "TXT"),
            "MTA_STS_TXT": self.dns.resolve(f"_mta-sts.{domain}", "TXT"),
        }
        mx, txt, dmarc, bimi, mta_sts_txt = await asyncio.gather(*tasks.values())
        record_map = {"MX": mx, "TXT": txt, "DMARC": dmarc, "BIMI": bimi, "MTA_STS_TXT": mta_sts_txt}
        findings: list[ReconFinding] = []
        for record_type, values in record_map.items():
            for value in values[:40]:
                finding = ReconFinding("dns_record", f"{record_type} {value[:100]}", f"{record_type}:{domain}:{value}", "ghost_workspace", "high", "HAS_DNS_RECORD", {"record_type": record_type, "record": value})
                findings.append(finding)
                await maybe_emit(emit, f"Workspace DNS {record_type}: {value[:120]}", finding.as_artifact())
        for finding in self.infer_services(domain, mx, txt + dmarc + bimi):
            findings.append(finding)
            await maybe_emit(emit, f"Workspace provider signal: {finding.label}", finding.as_artifact())
        async with AsyncHttpClient(concurrency=10, timeout=self.timeout) as client:
            document_tasks = [
                self.microsoft_tenant_hint(client, domain),
                self.gravatar(client, email) if "@" in email else asyncio.sleep(0, result=None),
                self.public_document_hint(client, "MTA-STS policy", f"https://mta-sts.{domain}/.well-known/mta-sts.txt", "version: STSv1"),
                self.public_document_hint(client, "Autoconfig mail profile", f"https://autoconfig.{domain}/mail/config-v1.1.xml"),
                self.public_document_hint(client, "Autodiscover endpoint", f"https://autodiscover.{domain}/autodiscover/autodiscover.xml"),
            ]
            for finding in await asyncio.gather(*document_tasks):
                if finding:
                    findings.append(finding)
                    await maybe_emit(emit, f"Workspace public signal: {finding.label}", finding.as_artifact())
        return {"target": target, "domain": domain, "mx": mx, "txt": txt, "artifacts": [finding.as_artifact() for finding in findings]}
