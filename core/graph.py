import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from core.schemas import entity_style
from core.targets import TargetProfile


URL_RE = re.compile(r"^https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")


class EntityGraphBuilder:
    """Build a small investigation graph from normalized module output."""

    def __init__(self, profile: TargetProfile, results: Dict[str, dict]):
        self.profile = profile
        self.results = results
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[str, dict] = {}

    def build(self) -> dict:
        target_id = self._target_node()
        for module_name, result in sorted(self.results.items()):
            module = result.get("module", {})
            module_id = self._add_node(
                "module",
                module_name,
                {
                    "display_name": module.get("display_name", module_name),
                    "category": module.get("category", "general"),
                    "status": result.get("status", "unknown"),
                    "signals": result.get("signal_count", 0),
                },
            )
            self._add_edge(target_id, module_id, "processed_by", module_name)

            data = result.get("data")
            if result.get("status") == "success" and data:
                self._extract_data(module_name, module_id, target_id, data)

        return {
            "nodes": sorted(self.nodes.values(), key=lambda item: (item["type"], item["label"])),
            "edges": sorted(self.edges.values(), key=lambda item: (item["relationship"], item["source"], item["target"])),
            "summary": self.summary(),
        }

    def summary(self) -> dict:
        type_counts: Dict[str, int] = {}
        for node in self.nodes.values():
            type_counts[node["type"]] = type_counts.get(node["type"], 0) + 1
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_types": type_counts,
        }

    def _target_node(self) -> str:
        properties = {
            "original": self.profile.original,
            "kind": self.profile.kind,
            "normalized": self.profile.normalized,
        }
        if self.profile.email:
            properties["email"] = self.profile.email
        if self.profile.domain:
            properties["domain"] = self.profile.domain
        if self.profile.username:
            properties["username"] = self.profile.username
        if self.profile.phone:
            properties["phone"] = self.profile.phone
        if self.profile.ip:
            properties["ip"] = self.profile.ip
        return self._add_node(self.profile.kind or "target", self.profile.normalized or self.profile.original, properties)

    def _extract_data(self, module_name: str, module_id: str, target_id: str, data: Any) -> None:
        if not isinstance(data, dict):
            self._extract_value(module_name, module_id, target_id, data, "emitted")
            return

        domain = data.get("domain")
        domain_id = None
        if isinstance(domain, str) and domain:
            domain_id = self._add_node("domain", domain, {"source_module": module_name})
            self._add_edge(target_id, domain_id, "has_domain", module_name)
            self._add_edge(module_id, domain_id, "emitted", module_name)

        self._extract_collection(module_name, module_id, target_id, data.get("matches"), "profile_match")
        self._extract_collection(module_name, module_id, target_id, data.get("present"), "account_presence")
        self._extract_collection(module_name, module_id, target_id, data.get("uncertain"), "uncertain_signal")
        self._extract_collection(module_name, module_id, target_id, data.get("results"), "service_result")
        self._extract_collection(module_name, module_id, target_id, data.get("gitlab_matches"), "profile_match")
        self._extract_collection(module_name, module_id, target_id, data.get("links"), "observed_link")
        self._extract_collection(module_name, module_id, target_id, data.get("external_links"), "external_link")
        self._extract_collection(module_name, module_id, target_id, data.get("internal_links"), "internal_link")
        self._extract_collection(module_name, module_id, target_id, data.get("username_variants"), "username_variant")
        self._extract_collection(module_name, module_id, target_id, data.get("identity_links"), "identity_link")
        self._extract_collection(module_name, module_id, target_id, data.get("digital_asset_links"), "mobile_app_link")
        self._extract_collection(module_name, module_id, target_id, data.get("flow_hints"), "recommended_flow")

        if isinstance(data.get("github"), dict):
            github = data["github"]
            profile = github.get("profile")
            if isinstance(profile, dict) and profile.get("login"):
                profile_id = self._add_node("profile", f"GitHub:{profile['login']}", profile)
                self._add_edge(target_id, profile_id, "profile_match", module_name)
                self._add_edge(module_id, profile_id, "emitted", module_name)
                if profile.get("html_url"):
                    self._connect_url(profile_id, profile["html_url"], "observed_at", module_name)

        if isinstance(data.get("devto"), dict) and data["devto"].get("username"):
            devto = data["devto"]
            profile_id = self._add_node("profile", f"Dev.to:{devto['username']}", devto)
            self._add_edge(target_id, profile_id, "profile_match", module_name)
            self._add_edge(module_id, profile_id, "emitted", module_name)

        if isinstance(data.get("hackernews"), dict) and data["hackernews"].get("id"):
            hn = data["hackernews"]
            profile_id = self._add_node("profile", f"HackerNews:{hn['id']}", hn)
            self._add_edge(target_id, profile_id, "profile_match", module_name)
            self._add_edge(module_id, profile_id, "emitted", module_name)

        dns = data.get("dns")
        if isinstance(dns, dict):
            anchor = domain_id or target_id
            for record_type, values in dns.items():
                self._extract_dns_values(module_name, module_id, anchor, record_type, values)

        for record_key in ("a_records", "aaaa_records", "mx_records", "txt_records", "caa_records", "ns_records", "cname_records"):
            values = data.get(record_key)
            if isinstance(values, list):
                self._extract_dns_values(module_name, module_id, domain_id or target_id, record_key.upper(), values)

        ip_addresses = data.get("ip_addresses")
        if isinstance(ip_addresses, list):
            self._extract_dns_values(module_name, module_id, domain_id or target_id, "IP", ip_addresses)

        emails = data.get("emails")
        if isinstance(emails, list):
            for email in emails[:80]:
                self._extract_value(module_name, module_id, target_id, str(email), "observed_email")

        cert_names = data.get("certificate_names")
        if isinstance(cert_names, list):
            for host in cert_names[:100]:
                if isinstance(host, str):
                    host_id = self._add_node("hostname", host, {"source_module": module_name})
                    self._add_edge(domain_id or target_id, host_id, "certificate_name", module_name)
                    self._add_edge(module_id, host_id, "emitted", module_name)

        risk = data.get("risk")
        if isinstance(risk, dict):
            label = f"{risk.get('risk_level', 'unknown')}:{risk.get('risk_score', 0)}"
            risk_id = self._add_node("risk", label, risk)
            self._add_edge(target_id, risk_id, "has_risk", module_name)
            self._add_edge(module_id, risk_id, "emitted", module_name)

        signals = data.get("signals")
        if isinstance(signals, list):
            for signal in signals:
                label = _signal_label(signal)
                signal_id = self._add_node("signal", label, {"value": signal, "source_module": module_name})
                self._add_edge(target_id, signal_id, "has_signal", module_name)
                self._add_edge(module_id, signal_id, "emitted", module_name)

        trackers = data.get("trackers")
        if isinstance(trackers, list):
            for tracker in trackers[:80]:
                label = _signal_label(tracker)
                signal_id = self._add_node("tracker", label, {"value": tracker, "source_module": module_name})
                self._add_edge(target_id, signal_id, "uses_tracker", module_name)
                self._add_edge(module_id, signal_id, "emitted", module_name)

        pivots = data.get("public_search_pivots")
        if isinstance(pivots, list):
            for item in pivots:
                url = item.get("url") if isinstance(item, dict) else item
                if isinstance(url, str):
                    properties = {"source_module": module_name}
                    if isinstance(item, dict):
                        properties.update(item)
                    url_id = self._add_node("url", url, properties)
                    self._add_edge(target_id, url_id, "search_pivot", module_name)
                    self._add_edge(module_id, url_id, "emitted", module_name)

        apple_links = data.get("apple_app_links")
        if isinstance(apple_links, dict):
            for app_id in apple_links.get("apps", [])[:40]:
                app_node = self._add_node("application", str(app_id), {"source_module": module_name, "ecosystem": "apple", "app_id": app_id})
                self._add_edge(target_id, app_node, "mobile_app_link", module_name)
                self._add_edge(module_id, app_node, "emitted", module_name)

    def _extract_collection(
        self,
        module_name: str,
        module_id: str,
        target_id: str,
        collection: Any,
        relationship: str,
    ) -> None:
        if not isinstance(collection, list):
            return
        for item in collection:
            if not isinstance(item, dict):
                self._extract_value(module_name, module_id, target_id, item, relationship)
                continue
            label = (
                item.get("platform")
                or item.get("service")
                or item.get("username")
                or item.get("package_name")
                or item.get("flow_id")
                or item.get("label")
                or item.get("name")
                or item.get("url")
            )
            node_type = _node_type_for_item(item, relationship)
            if label:
                node_id = self._add_node(node_type, str(label), item)
                self._add_edge(target_id, node_id, relationship, module_name)
                self._add_edge(module_id, node_id, "emitted", module_name)
                if item.get("url"):
                    self._connect_url(node_id, item["url"], "observed_at", module_name)
                if item.get("domain"):
                    domain_id = self._add_node("domain", str(item["domain"]), {"source_module": module_name})
                    self._add_edge(node_id, domain_id, "uses_domain", module_name)
                for link in item.get("links", [])[:12] if isinstance(item.get("links"), list) else []:
                    if isinstance(link, dict) and link.get("url"):
                        link_id = self._add_node("url", str(link["url"]), {"source_module": module_name, **link})
                        self._add_edge(node_id, link_id, "links_to", module_name)

    def _extract_dns_values(self, module_name: str, module_id: str, anchor_id: str, record_type: str, values: Iterable[Any]) -> None:
        for value in list(values)[:100]:
            if not value:
                continue
            text = str(value)
            node_type = "ip" if _looks_like_ip(text) else "dns_record"
            node_id = self._add_node(node_type, text, {"record_type": record_type, "source_module": module_name})
            self._add_edge(anchor_id, node_id, f"dns_{record_type.lower()}", module_name)
            self._add_edge(module_id, node_id, "emitted", module_name)

    def _extract_value(self, module_name: str, module_id: str, target_id: str, value: Any, relationship: str) -> None:
        if not isinstance(value, str) or not value:
            return
        if URL_RE.match(value):
            node_id = self._add_node("url", value, {"source_module": module_name})
        elif EMAIL_RE.match(value):
            node_id = self._add_node("email", value.lower(), {"source_module": module_name})
        elif DOMAIN_RE.match(value):
            node_id = self._add_node("domain", value.lower(), {"source_module": module_name})
        else:
            node_id = self._add_node("signal", value[:120], {"source_module": module_name})
        self._add_edge(target_id, node_id, relationship, module_name)
        self._add_edge(module_id, node_id, "emitted", module_name)

    def _connect_url(self, source_id: str, url: str, relationship: str, module_name: str) -> None:
        url_id = self._add_node("url", str(url), {"source_module": module_name})
        self._add_edge(source_id, url_id, relationship, module_name)

    def _add_node(self, node_type: str, label: str, properties: Optional[dict] = None) -> str:
        node_id = _stable_id(node_type, label)
        style = entity_style(node_type)
        clean_properties = _clean_properties(properties or {})
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema": style.name,
            "source_module": clean_properties.get("source_module"),
        }
        existing = self.nodes.get(node_id)
        if existing:
            existing["properties"].update(clean_properties)
            existing["nodeProperties"].update(clean_properties)
            return node_id
        self.nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "properties": clean_properties,
            "nodeType": style.label,
            "nodeLabel": label,
            "nodeProperties": clean_properties,
            "nodeSize": 18 if node_type in {"target", "domain", "ip", "email", "username", "phone"} else 12,
            "nodeColor": style.color,
            "nodeIcon": style.icon,
            "nodeImage": clean_properties.get("avatar_url") or clean_properties.get("profile_image"),
            "nodeFlag": _node_flag(node_type, clean_properties),
            "nodeShape": style.shape,
            "nodeMetadata": metadata,
            "val": 2 if node_type == "module" else 3 if node_type in {"target", "domain", "ip"} else 1,
        }
        return node_id

    def _add_edge(self, source: str, target: str, relationship: str, module_name: str) -> None:
        if source == target:
            return
        edge_id = _stable_id("edge", f"{source}:{relationship}:{target}:{module_name}")
        self.edges[edge_id] = {
            "id": edge_id,
            "source": source,
            "target": target,
            "relationship": relationship,
            "label": relationship.upper(),
            "type": relationship,
            "weight": 1,
            "confidence_level": "observed",
            "date": datetime.now(timezone.utc).isoformat(),
            "module": module_name,
        }



def build_investigation_graph(profile: TargetProfile, results: Dict[str, dict]) -> dict:
    return EntityGraphBuilder(profile, results).build()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    safe = re.sub(r"[^a-z0-9_]+", "_", prefix.lower()).strip("_") or "node"
    return f"{safe}:{digest}"


def _clean_properties(properties: dict) -> dict:
    clean = {}
    for key, value in properties.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[str(key)] = value
        elif isinstance(value, (list, tuple, set)):
            clean[str(key)] = [item for item in value if isinstance(item, (str, int, float, bool))][:20]
        elif isinstance(value, dict):
            clean[str(key)] = _clean_properties(value)
        else:
            clean[str(key)] = str(value)
    return clean


def _signal_label(signal: Any) -> str:
    if isinstance(signal, dict):
        parts = [str(signal.get("type", "signal"))]
        if signal.get("value") is not None:
            parts.append(str(signal["value"]))
        if signal.get("code") is not None:
            parts.append(str(signal["code"]))
        return ":".join(parts)
    return str(signal)


def _node_type_for_item(item: dict, relationship: str) -> str:
    declared = str(item.get("type") or "").lower()
    if declared in {"username", "email", "domain", "url", "phone", "ip", "hostname", "flow"}:
        return declared
    if relationship in {"observed_link", "external_link", "internal_link"} or item.get("url") and not item.get("platform"):
        return "url"
    if item.get("package_name") or item.get("namespace") in {"android_app", "web"}:
        return "application"
    if item.get("flow_id"):
        return "flow"
    if item.get("username"):
        return "username"
    if item.get("service") or item.get("name"):
        return "service"
    return "profile"


def _looks_like_ip(value: str) -> bool:
    return bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value)) or ":" in value and all(part for part in value.split(":") if part)


def _node_flag(node_type: str, properties: dict) -> str | None:
    if node_type == "risk":
        level = str(properties.get("risk_level", "")).lower()
        if level == "high":
            return "red"
        if level == "medium":
            return "orange"
        if level == "low":
            return "green"
    if properties.get("status") == "error":
        return "red"
    if properties.get("status") == "skipped":
        return "yellow"
    return None
