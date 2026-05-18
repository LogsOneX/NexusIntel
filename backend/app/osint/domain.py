import re
from urllib.parse import urlparse

import dns.resolver
import httpx

from app.osint.http import make_client
from app.osint.schema import FindingBatch, entity, relationship
from app.targeting import extract_domain


class DomainRecon:
    name = "domain_recon"

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        domain = extract_domain(target)
        if not domain:
            return FindingBatch(self.name, "No domain available for infrastructure recon.")

        root = entity("domain", domain, domain, 100, self.name)
        entities = [root]
        relationships = []
        raw = {"dns": {}, "rdap": None, "ct": []}

        dns_records = self._dns(domain)
        raw["dns"] = dns_records
        for record_type, values in dns_records.items():
            for value in values:
                node_type = {
                    "A": "ip",
                    "AAAA": "ip",
                    "MX": "mail_server",
                    "NS": "nameserver",
                    "CAA": "dns_record",
                    "TXT": "dns_record",
                }.get(record_type, "dns_record")
                node = entity(node_type, value, value, 82, self.name, {"record_type": record_type})
                entities.append(node)
                relationships.append(relationship(root, node, f"has_{record_type.lower()}", record_type, 82))

        async with make_client() as client:
            rdap = await self._rdap(client, domain)
            raw["rdap"] = rdap
            if rdap:
                registrar = rdap.get("registrar")
                if registrar:
                    registrar_node = entity("organization", registrar, registrar, 78, self.name, {"source": "rdap"})
                    entities.append(registrar_node)
                    relationships.append(relationship(root, registrar_node, "registered_via", "Registered Via", 78))
                for name_server in rdap.get("nameservers", []):
                    ns_node = entity("nameserver", name_server, name_server, 82, self.name, {"source": "rdap"})
                    entities.append(ns_node)
                    relationships.append(relationship(root, ns_node, "delegated_to", "Delegated To", 82))

            if mode in {"active", "aggressive"}:
                ct = await self._certificate_transparency(client, domain)
                raw["ct"] = ct
                for item in ct[:80 if mode == "aggressive" else 35]:
                    subdomain = item.strip("*.").lower()
                    if subdomain and subdomain.endswith(domain):
                        sub_node = entity("subdomain", subdomain, subdomain, 72, self.name, {"source": "crt.sh"})
                        entities.append(sub_node)
                        relationships.append(relationship(root, sub_node, "certificate_name", "Certificate Name", 72))

        risk_notes = self._posture_notes(dns_records)
        for note in risk_notes:
            signal = entity("risk", f"{domain}:{note}", note, 65, self.name, {"domain": domain})
            entities.append(signal)
            relationships.append(relationship(root, signal, "has_risk", "Has Risk", 65))

        return FindingBatch(
            self.name,
            f"Collected DNS/RDAP{'/CT' if mode in {'active', 'aggressive'} else ''} public infrastructure signals for {domain}.",
            entities,
            relationships,
            raw,
        )

    def _dns(self, domain: str) -> dict[str, list[str]]:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5
        resolver.timeout = 3
        output: dict[str, list[str]] = {}
        for record_type in ["A", "AAAA", "MX", "NS", "TXT", "CAA"]:
            try:
                answers = resolver.resolve(domain, record_type)
            except Exception:
                continue
            values = []
            for answer in answers:
                value = str(answer).strip().strip('"')
                if record_type == "MX":
                    value = value.split()[-1].rstrip(".")
                if record_type == "NS":
                    value = value.rstrip(".")
                values.append(value)
            output[record_type] = sorted(set(values))
        return output

    async def _rdap(self, client: httpx.AsyncClient, domain: str) -> dict | None:
        try:
            response = await client.get(f"https://rdap.org/domain/{domain}")
            if response.status_code >= 400:
                return None
            data = response.json()
        except Exception:
            return None
        registrar = None
        for entity_item in data.get("entities", []):
            roles = entity_item.get("roles", [])
            if "registrar" in roles:
                vcard = entity_item.get("vcardArray", [None, []])[1]
                for row in vcard:
                    if row and row[0] == "fn":
                        registrar = row[3]
        return {
            "handle": data.get("handle"),
            "registrar": registrar,
            "nameservers": [item.get("ldhName", "").rstrip(".") for item in data.get("nameservers", []) if item.get("ldhName")],
            "events": data.get("events", []),
        }

    async def _certificate_transparency(self, client: httpx.AsyncClient, domain: str) -> list[str]:
        try:
            response = await client.get(f"https://crt.sh/?q=%25.{domain}&output=json", timeout=12)
            if response.status_code >= 400:
                return []
            rows = response.json()
        except Exception:
            return []
        names: set[str] = set()
        for row in rows[:500]:
            for name in str(row.get("name_value", "")).splitlines():
                cleaned = name.strip().lower()
                if re.match(r"^\*?\.[a-z0-9.-]+$", cleaned) or cleaned.endswith(domain):
                    names.add(cleaned)
        return sorted(names)

    def _posture_notes(self, records: dict[str, list[str]]) -> list[str]:
        notes = []
        txt = " ".join(records.get("TXT", [])).lower()
        if "v=spf1" not in txt:
            notes.append("No SPF TXT record observed")
        if "p=reject" not in txt and "p=quarantine" not in txt:
            notes.append("No strict DMARC policy observed in root TXT set")
        if not records.get("CAA"):
            notes.append("No CAA records observed")
        return notes


def normalize_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    parsed = urlparse(value)
    if parsed.netloc:
        return value
    return f"https://{value}"
