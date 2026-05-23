from __future__ import annotations

import socket
from urllib.parse import quote, urlparse

import dns.resolver
import httpx
from bs4 import BeautifulSoup

from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RawEvidenceObject, RunContext, SourceReliability, utc_now

LEGAL = "Passive public DNS/RDAP/HTTP collection; no authenticated scraping or exploitation."


def confidence():
    return assess(direct=True, reliability=SourceReliability.PRIMARY, fp_risk="low", reason="Direct public infrastructure source observation.")


def art(t: str, label: str, value: str, source: str, url: str | None, relationship: str, data: dict) -> OSINTArtifact:
    c = confidence()
    return OSINTArtifact(type=t, label=label, value=value, source=source, source_url=url, fetched_at=utc_now(), confidence_score=c.score, confidence_reason=c.reason, evidence_grade=evidence_grade(c.score, c.source_reliability), raw_evidence_ref=None, relationship=relationship, tags=[], data=data, legal_basis=LEGAL)


def normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.split("/")[0].split(":")[0].strip(".")


class DomainDNSAdapter(BaseAdapter):
    id = "domain.dns"
    name = "Domain DNS"
    description = "Collect A/AAAA/MX/NS/TXT/CAA records."
    input_types = ["domain"]
    output_types = ["dns_record", "ip", "mx_record", "txt_record"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        domain = normalize_domain(entity.value)
        payload: dict[str, list[str]] = {}
        artifacts = [art("domain", domain, domain, self.id, f"dns:{domain}", "DNS_OF", {"domain": domain})]
        for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CAA"]:
            values: list[str] = []
            try:
                answers = dns.resolver.resolve(domain, rtype, lifetime=6)
                for answer in answers:
                    if rtype == "MX":
                        values.append(str(answer.exchange).rstrip("."))
                    elif rtype == "TXT":
                        strings = getattr(answer, "strings", None)
                        values.append("".join(part.decode("utf-8", "ignore") for part in strings) if strings else str(answer).strip('"'))
                    else:
                        values.append(str(answer).rstrip("."))
            except Exception:
                values = []
            payload[rtype] = sorted(set(values))
            for value in payload[rtype][:50]:
                node_type = "ip" if rtype in {"A", "AAAA"} else "mx_record" if rtype == "MX" else "txt_record" if rtype == "TXT" else "dns_record"
                artifacts.append(art(node_type, f"{rtype} {value}"[:96], value, self.id, f"dns:{domain}", f"HAS_{rtype}", {"domain": domain, "record_type": rtype}))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[RawEvidenceObject(source=self.id, source_url=f"dns:{domain}", payload=payload, content_type="application/json")])


class DomainRDAPAdapter(BaseAdapter):
    id = "domain.rdap"
    name = "Domain RDAP"
    input_types = ["domain"]
    output_types = ["rdap_record", "nameserver"]
    description = "Collect public RDAP domain registration metadata."

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        domain = normalize_domain(entity.value)
        url = f"https://rdap.org/domain/{quote(domain)}"
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
            response = await client.get(url)
            raw = RawEvidenceObject(source=self.id, source_url=url, payload={"status_code": response.status_code, "body": response.text[:300000]}, content_type="application/json")
            response.raise_for_status()
            data = response.json()
        artifacts = [art("rdap_record", f"RDAP {domain}", domain, self.id, url, "HAS_RDAP", data)]
        for ns in data.get("nameservers", [])[:20] if isinstance(data, dict) else []:
            name = ns.get("ldhName") if isinstance(ns, dict) else None
            if name:
                artifacts.append(art("nameserver", name, name, self.id, url, "HAS_NAMESERVER", {"domain": domain}))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])


class DomainCTAdapter(BaseAdapter):
    id = "domain.ct_subdomains"
    name = "Certificate Transparency Subdomains"
    input_types = ["domain"]
    output_types = ["subdomain"]
    description = "Collect subdomains from crt.sh public CT index."

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        domain = normalize_domain(entity.value)
        url = f"https://crt.sh/?q=%25.{quote(domain)}&output=json"
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
            response = await client.get(url)
            raw = RawEvidenceObject(source=self.id, source_url=url, payload={"status_code": response.status_code, "body": response.text[:500000]}, content_type="application/json")
            response.raise_for_status()
            data = response.json()
        names = set()
        for row in data[:500] if isinstance(data, list) else []:
            for item in str(row.get("name_value", "")).splitlines():
                clean = item.lower().strip("*. ")
                if clean.endswith(domain):
                    names.add(clean)
        artifacts = [art("subdomain", name, name, self.id, url, "HAS_CT_SUBDOMAIN", {"domain": domain}) for name in sorted(names)[:100]]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])


class WebFingerprintAdapter(BaseAdapter):
    id = "domain.web_fingerprint"
    name = "Web Fingerprint"
    input_types = ["domain", "url"]
    output_types = ["web_fingerprint", "external_link", "title"]
    description = "Fetch public homepage headers/title/meta and external links."

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        target = entity.value.strip()
        url = target if target.startswith(("http://", "https://")) else f"https://{normalize_domain(target)}"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
            response = await client.get(url)
            html = response.text[:300000]
            raw = RawEvidenceObject(source=self.id, source_url=str(response.url), payload={"status_code": response.status_code, "headers": dict(response.headers), "body": html}, content_type="text/html", headers=dict(response.headers))
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else str(response.url)
        artifacts = [art("web_fingerprint", title[:96], str(response.url), self.id, str(response.url), "HAS_WEB_FINGERPRINT", {"status_code": response.status_code, "headers": dict(response.headers), "title": title})]
        host = urlparse(str(response.url)).netloc
        seen = set()
        for link in soup.find_all("a", href=True)[:100]:
            href = str(link.get("href"))
            if href.startswith("http") and urlparse(href).netloc != host and href not in seen:
                seen.add(href)
                artifacts.append(art("external_link", href[:96], href, self.id, str(response.url), "LINKS_TO", {"from": str(response.url)}))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])


class IPRDAPAdapter(BaseAdapter):
    id = "ip.rdap_asn"
    name = "IP RDAP/ASN"
    input_types = ["ip"]
    output_types = ["rdap_record", "asn"]
    description = "Collect public RDAP allocation metadata for an IP."

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        ip = entity.value.strip()
        url = f"https://rdap.org/ip/{quote(ip)}"
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
            response = await client.get(url)
            raw = RawEvidenceObject(source=self.id, source_url=url, payload={"status_code": response.status_code, "body": response.text[:300000]}, content_type="application/json")
            response.raise_for_status()
            data = response.json()
        artifacts = [art("rdap_record", f"RDAP {ip}", ip, self.id, url, "HAS_RDAP", data)]
        if data.get("handle"):
            artifacts.append(art("asn", data.get("handle"), data.get("handle"), self.id, url, "HAS_ALLOCATION", data))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])
