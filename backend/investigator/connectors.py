from __future__ import annotations

from typing import Any


CONNECTOR_DEFINITIONS = [
    ("github", "GitHub", "Code", "Official API/BYOK public code and profile search.", "high public", True),
    ("hibp", "HaveIBeenPwned", "Breach", "Official breach API only. Disabled without key.", "authoritative", True),
    ("virustotal", "VirusTotal", "Infrastructure", "Official BYOK connector.", "high aggregator", True),
    ("shodan", "Shodan", "Infrastructure", "Official BYOK connector.", "high scanner", True),
    ("censys", "Censys", "Infrastructure", "Official BYOK connector.", "high scanner", True),
    ("securitytrails", "SecurityTrails", "DNS", "Official BYOK DNS enrichment.", "high aggregator", True),
    ("urlscan", "URLScan", "Infrastructure", "Official API/BYOK or public lookups where allowed.", "high public", True),
    ("google_maps", "Google Maps/Places", "Maps", "Place enrichment only from analyst-supplied public evidence.", "official", True),
    ("twilio", "Twilio Lookup", "Phone", "Official lookup API if configured.", "official", True),
    ("opencorporates", "OpenCorporates", "Corporate", "Public corporate registry enrichment.", "public registry", False),
    ("custom_http", "Custom HTTP Adapter", "Custom", "Operator-defined adapter placeholder; must remain public-source and read-only.", "operator defined", False),
]


def connector_status(settings: dict[str, Any]) -> list[dict[str, Any]]:
    configured = settings.get("api_keys") or {}
    enabled = settings.get("connectors") or {}
    items: list[dict[str, Any]] = []
    for connector_id, name, category, legal_note, reliability, requires_key in CONNECTOR_DEFINITIONS:
        key_present = bool(configured.get(connector_id)) or not requires_key
        last_tested = enabled.get(f"{connector_id}_last_tested") if isinstance(enabled, dict) else None
        items.append({
            "id": connector_id,
            "name": name,
            "category": category,
            "configured": key_present,
            "enabled": enabled.get(connector_id, True) is not False if isinstance(enabled, dict) else True,
            "key_present": key_present,
            "test_status": "not_configured" if requires_key and not key_present else "not_tested" if not last_tested else "operator_recorded",
            "last_tested": last_tested,
            "quota": "not tracked locally",
            "legal_note": legal_note,
            "source_reliability": reliability,
        })
    return items
