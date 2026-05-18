import hashlib
import re
from typing import Any

import dns.resolver
import httpx

from app.osint.http import make_client
from app.osint.schema import FindingBatch, entity, relationship
from app.targeting import extract_domain, username_seed


class EmailWorkspaceRecon:
    name = "email_workspace_recon"

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        if target_type != "email":
            domain = extract_domain(target)
            if not domain:
                return FindingBatch(self.name, "No email or domain pivot available.")
            return await self._domain_workspace(domain, target, mode)

        email = target.strip().lower()
        domain = extract_domain(email)
        if not domain or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return FindingBatch(self.name, "Invalid email format for workspace recon.")

        email_node = entity("email", email, email, 100, self.name)
        username_node = entity("username", username_seed(email), username_seed(email), 80, self.name)
        domain_node = entity("domain", domain, domain, 95, self.name)
        entities = [email_node, username_node, domain_node]
        relationships = [
            relationship(email_node, username_node, "local_part", "Local Part", 75),
            relationship(email_node, domain_node, "uses_domain", "Uses Domain", 90),
        ]

        workspace = self._dns_workspace(domain)
        for item in workspace["records"]:
            record = entity("dns_record", f"{domain}:{item['type']}:{item['value']}", item["value"], item["confidence"], self.name, item)
            entities.append(record)
            relationships.append(relationship(domain_node, record, "publishes", item["type"], item["confidence"]))

        for service in workspace["services"]:
            service_node = entity("service", service["name"], service["name"], service["confidence"], self.name, service)
            entities.append(service_node)
            relationships.append(relationship(domain_node, service_node, "uses_service", "Uses Service", service["confidence"]))

        gravatar_hash = hashlib.md5(email.encode()).hexdigest()
        hash_node = entity("hash", gravatar_hash, "Gravatar MD5", 65, self.name, {"algorithm": "md5", "source_value": "email"})
        entities.append(hash_node)
        relationships.append(relationship(email_node, hash_node, "has_public_hash", "Has Public Hash", 65))

        if mode in {"active", "aggressive"}:
            avatar = await self._gravatar_probe(gravatar_hash)
            if avatar:
                avatar_node = entity("avatar", avatar["url"], "Public Gravatar avatar", avatar["confidence"], self.name, avatar)
                entities.append(avatar_node)
                relationships.append(relationship(hash_node, avatar_node, "resolves_to", "Resolves To", avatar["confidence"]))

        return FindingBatch(
            self.name,
            f"Mapped public email workspace posture for {domain}; auth-flow account probing intentionally excluded.",
            entities,
            relationships,
            {"domain": domain, "workspace": workspace, "mode": mode},
        )

    async def _domain_workspace(self, domain: str, target: str, mode: str) -> FindingBatch:
        domain_node = entity("domain", domain, domain, 95, self.name)
        workspace = self._dns_workspace(domain)
        entities = [domain_node]
        relationships = []
        for item in workspace["records"]:
            record = entity("dns_record", f"{domain}:{item['type']}:{item['value']}", item["value"], item["confidence"], self.name, item)
            entities.append(record)
            relationships.append(relationship(domain_node, record, "publishes", item["type"], item["confidence"]))
        for service in workspace["services"]:
            service_node = entity("service", service["name"], service["name"], service["confidence"], self.name, service)
            entities.append(service_node)
            relationships.append(relationship(domain_node, service_node, "uses_service", "Uses Service", service["confidence"]))
        return FindingBatch(self.name, f"Mapped workspace DNS posture for {domain}.", entities, relationships, workspace)

    def _dns_workspace(self, domain: str) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        services: list[dict[str, Any]] = []
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 4
        resolver.timeout = 3

        for record_type in ["MX", "TXT"]:
            try:
                answers = resolver.resolve(domain, record_type)
            except Exception:
                continue
            for answer in answers:
                value = str(answer).strip('"')
                confidence = 80
                records.append({"type": record_type, "value": value, "confidence": confidence})
                lowered = value.lower()
                if "google.com" in lowered or "_spf.google.com" in lowered:
                    services.append({"name": "Google Workspace", "provider": "google", "confidence": 82, "evidence": value})
                if "outlook.com" in lowered or "protection.outlook.com" in lowered:
                    services.append({"name": "Microsoft 365", "provider": "microsoft", "confidence": 82, "evidence": value})
                if "zoho" in lowered:
                    services.append({"name": "Zoho Mail", "provider": "zoho", "confidence": 75, "evidence": value})
                if "protonmail" in lowered or "proton.me" in lowered:
                    services.append({"name": "Proton Mail", "provider": "proton", "confidence": 75, "evidence": value})

        for prefix in ["_dmarc", "default._bimi"]:
            fqdn = f"{prefix}.{domain}"
            try:
                answers = resolver.resolve(fqdn, "TXT")
            except Exception:
                continue
            for answer in answers:
                records.append({"type": prefix.upper(), "value": str(answer).strip('"'), "confidence": 78})

        deduped_services = {item["name"]: item for item in services}
        return {"records": records, "services": list(deduped_services.values())}

    async def _gravatar_probe(self, gravatar_hash: str) -> dict[str, Any] | None:
        url = f"https://www.gravatar.com/avatar/{gravatar_hash}?d=404"
        try:
            async with make_client(timeout=6) as client:
                response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
            return {"url": url, "status_code": response.status_code, "confidence": 68}
        return None
