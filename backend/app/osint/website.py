import re
from urllib.parse import urljoin, urlparse

import bs4
import httpx

from app.osint.domain import normalize_url
from app.osint.http import make_client
from app.osint.schema import FindingBatch, entity, relationship
from app.osint.sources import TRACKER_HINTS
from app.targeting import extract_domain


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class WebsiteSurfaceRecon:
    name = "website_surface_recon"

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        domain = extract_domain(target)
        if not domain:
            return FindingBatch(self.name, "No website/domain target available.")
        start_url = normalize_url(target if target_type == "url" else domain)
        root = entity("website", start_url, start_url, 94, self.name, {"domain": domain})
        domain_node = entity("domain", domain, domain, 90, self.name)
        entities = [root, domain_node]
        relationships = [relationship(root, domain_node, "serves_domain", "Serves Domain", 86)]
        raw = {"pages": []}

        async with make_client() as client:
            pages = await self._crawl(client, start_url, domain, mode)

        for page in pages:
            page_node = entity("url", page["url"], page.get("title") or page["url"], page["confidence"], self.name, page)
            entities.append(page_node)
            relationships.append(relationship(root, page_node, "links_page", "Links Page", page["confidence"]))
            if page.get("title"):
                title = entity("signal", f"{page['url']}:title", page["title"], 62, self.name, {"kind": "title"})
                entities.append(title)
                relationships.append(relationship(page_node, title, "has_title", "Has Title", 62))
            for email_value in page.get("emails", []):
                email_node = entity("email", email_value, email_value, 72, self.name, {"observed_on": page["url"]})
                entities.append(email_node)
                relationships.append(relationship(page_node, email_node, "exposes_email", "Exposes Email", 72))
            for tracker in page.get("trackers", []):
                tracker_node = entity("tracker", tracker, tracker, 68, self.name, {"observed_on": page["url"]})
                entities.append(tracker_node)
                relationships.append(relationship(page_node, tracker_node, "loads_tracker", "Loads Tracker", 68))

        raw["pages"] = pages
        return FindingBatch(
            self.name,
            f"Fetched {len(pages)} public website page(s), extracted links, emails, titles, and tracker hints.",
            entities,
            relationships,
            raw,
        )

    async def _crawl(self, client: httpx.AsyncClient, start_url: str, domain: str, mode: str) -> list[dict]:
        max_pages = 1 if mode == "standard" else 5 if mode == "active" else 12
        queue = [start_url]
        seen: set[str] = set()
        pages: list[dict] = []
        while queue and len(pages) < max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                response = await client.get(url)
            except httpx.HTTPError:
                continue
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue
            page = self._parse_page(str(response.url), response.text, response.status_code, response.headers)
            pages.append(page)
            if mode in {"active", "aggressive"}:
                for link in page.get("internal_links", []):
                    parsed = urlparse(link)
                    if parsed.netloc.endswith(domain) and link not in seen and len(queue) < max_pages * 3:
                        queue.append(link)
        return pages

    def _parse_page(self, url: str, html: str, status_code: int, headers: httpx.Headers) -> dict:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        links = []
        for tag in soup.find_all("a", href=True):
            href = urljoin(url, tag["href"])
            if href.startswith(("http://", "https://")):
                links.append(href.split("#")[0])
        trackers = []
        lowered = html.lower()
        for tracker, needles in TRACKER_HINTS.items():
            if any(needle.lower() in lowered for needle in needles):
                trackers.append(tracker)
        emails = sorted(set(match.lower() for match in EMAIL_RE.findall(html)))[:30]
        return {
            "url": url,
            "status_code": status_code,
            "title": title,
            "server": headers.get("server"),
            "confidence": 78 if status_code < 400 else 35,
            "emails": emails,
            "trackers": sorted(set(trackers)),
            "internal_links": sorted(set(links))[:60],
        }
