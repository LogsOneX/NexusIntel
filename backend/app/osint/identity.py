import hashlib
import re
from typing import Any

import httpx

from app.config import get_settings
from app.osint.http import bounded_gather, make_client
from app.osint.schema import FindingBatch, entity, relationship
from app.osint.sources import NEGATIVE_MARKERS, PLATFORM_SOURCES
from app.targeting import username_seed


class IdentityProfiler:
    name = "identity_profiler"

    def _platform_limit(self, mode: str) -> int:
        if mode == "aggressive":
            return len(PLATFORM_SOURCES)
        if mode == "active":
            return 42
        return 28

    def _confidence(self, status_code: int, body: str, url: str) -> int:
        text = body[:8000].lower()
        if status_code in {401, 403}:
            return 62
        if status_code == 200:
            if any(marker in text for marker in NEGATIVE_MARKERS):
                return 0
            if "profile" in text or "followers" in text or "repositories" in text or url.lower() in text:
                return 82
            return 70
        if status_code in {301, 302, 307, 308}:
            return 55
        return 0

    async def _check(self, client: httpx.AsyncClient, username: str, source: dict[str, str]) -> dict[str, Any] | None:
        url = source["url"].format(username=username)
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            return {
                "platform": source["name"],
                "url": url,
                "status": "error",
                "error": str(exc)[:160],
                "confidence": 0,
                "category": source["category"],
            }

        confidence = self._confidence(response.status_code, response.text, str(response.url))
        if confidence <= 0:
            return {
                "platform": source["name"],
                "url": url,
                "status": "not_found",
                "status_code": response.status_code,
                "confidence": 0,
                "category": source["category"],
            }
        title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()[:180] if title_match else source["name"]
        return {
            "platform": source["name"],
            "url": str(response.url),
            "status": "found",
            "status_code": response.status_code,
            "confidence": confidence,
            "category": source["category"],
            "profile_type": source["type"],
            "title": title,
        }

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        username = username_seed(target)
        if not username:
            return FindingBatch(self.name, "No usable username seed found.")

        settings = get_settings()
        limit = settings.aggressive_concurrency if mode == "aggressive" else settings.standard_concurrency
        sources = PLATFORM_SOURCES[: self._platform_limit(mode)]
        root = entity("username", username, username, 95, self.name)

        async with make_client() as client:
            async def worker(source: dict[str, str]) -> dict[str, Any] | None:
                return await self._check(client, username, source)

            results = await bounded_gather(sources, limit, worker)

        found = [item for item in results if item.get("status") == "found"]
        entities = [root]
        relationships = []
        categories: dict[str, int] = {}

        for item in found:
            profile = entity(
                item["profile_type"],
                item["url"],
                item["platform"],
                item["confidence"],
                self.name,
                {
                    "platform": item["platform"],
                    "category": item["category"],
                    "title": item.get("title"),
                    "status_code": item.get("status_code"),
                },
            )
            url_node = entity("url", item["url"], item["url"], item["confidence"], self.name)
            service = entity("service", item["platform"], item["platform"], 85, self.name, {"category": item["category"]})
            entities.extend([profile, url_node, service])
            relationships.append(relationship(root, profile, "profile_found", "Profile Found", item["confidence"]))
            relationships.append(relationship(profile, url_node, "located_at", "Located At", item["confidence"]))
            relationships.append(relationship(profile, service, "on_platform", "On Platform", 80))
            categories[item["category"]] = categories.get(item["category"], 0) + 1

        for alias in self._aliases(username):
            if alias != username:
                alias_node = entity("username", alias, alias, 55, self.name, {"derived_from": username})
                entities.append(alias_node)
                relationships.append(relationship(root, alias_node, "alias_candidate", "Alias Candidate", 55))

        footprint = min(100, len(found) * 9 + len(categories) * 4)
        fingerprint = hashlib.sha256("|".join(sorted(item["url"] for item in found)).encode()).hexdigest()[:16]
        score = entity(
            "signal",
            f"{username}:identity-footprint",
            f"Identity footprint {footprint}/100",
            footprint,
            self.name,
            {"found": len(found), "checked": len(sources), "categories": categories, "fingerprint": fingerprint},
        )
        entities.append(score)
        relationships.append(relationship(root, score, "has_signal", "Has Signal", footprint))

        return FindingBatch(
            self.name,
            f"Checked {len(sources)} public username surfaces and found {len(found)} likely profiles.",
            entities,
            relationships,
            {"checked": len(sources), "found": found, "mode": mode},
        )

    def _aliases(self, username: str) -> set[str]:
        clean = re.sub(r"[^A-Za-z0-9]", "", username)
        aliases = {username, username.lower(), username.replace("_", "."), username.replace(".", "_")}
        if clean and clean != username:
            aliases.add(clean)
        return {item for item in aliases if 2 <= len(item) <= 64}
