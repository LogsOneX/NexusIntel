
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    id: str
    name: str
    category: str
    source_reliability: str
    requires_api_key: bool
    testable: bool
    implemented: bool
    key_names: tuple[str, ...] = ()
    unlocked_transforms: tuple[str, ...] = ()
    legal_note: str = "Passive public-source or official API/BYOK collection only."
    quota: str = "not tracked locally"
    documentation_url: str | None = None
    disabled_reason: str | None = None


CONNECTOR_DEFINITIONS: tuple[ConnectorDefinition, ...] = (
    ConnectorDefinition("github", "GitHub", "Code", "official_api_high", True, True, True, ("GITHUB_TOKEN",), ("email_to_github_public_search",), "Official GitHub API/BYOK public code search only.", "GitHub API quota", "https://docs.github.com/en/rest"),
    ConnectorDefinition("hibp", "Have I Been Pwned", "Breach", "official_api_authoritative", True, True, True, ("HIBP_API_KEY",), ("email_to_breach_connectors",), "Official HIBP API only. No leaked credential storage.", "HIBP API quota", "https://haveibeenpwned.com/API/v3"),
    ConnectorDefinition("urlscan", "URLScan", "Infrastructure", "official_api_high", True, True, False, ("URLSCAN_API_KEY",), ("domain_to_urlscan",), "Official URLScan API/BYOK only; no authenticated scraping.", "URLScan quota", "https://urlscan.io/docs/api/", "adapter_not_implemented"),
    ConnectorDefinition("virustotal", "VirusTotal", "Infrastructure", "official_api_high", True, True, False, ("VIRUSTOTAL_API_KEY",), (), "Official VirusTotal BYOK placeholder.", "VT quota", "https://docs.virustotal.com/", "adapter_not_implemented"),
    ConnectorDefinition("shodan", "Shodan", "Infrastructure", "official_api_high", True, True, False, ("SHODAN_API_KEY",), (), "Official Shodan BYOK placeholder.", "Shodan quota", "https://developer.shodan.io/api", "adapter_not_implemented"),
    ConnectorDefinition("censys", "Censys", "Infrastructure", "official_api_high", True, True, False, ("CENSYS_API_KEY",), (), "Official Censys BYOK placeholder.", "Censys quota", "https://search.censys.io/api", "adapter_not_implemented"),
    ConnectorDefinition("securitytrails", "SecurityTrails", "DNS", "official_api_high", True, True, False, ("SECURITYTRAILS_API_KEY",), (), "Official SecurityTrails BYOK placeholder.", "SecurityTrails quota", "https://securitytrails.com/corp/api", "adapter_not_implemented"),
    ConnectorDefinition("google_maps", "Google Maps/Places", "Maps", "official_api_high", True, True, True, ("GOOGLE_MAPS_API_KEY",), ("maps_place_to_place_details",), "Place enrichment only from analyst-supplied public profile/place evidence.", "Google API quota", "https://developers.google.com/maps/documentation/places/web-service"),
    ConnectorDefinition("opencorporates", "OpenCorporates", "Corporate", "public_registry_medium", False, False, False, (), (), "Public corporate registry enrichment placeholder.", "not tracked locally", "https://api.opencorporates.com/documentation/API-Reference", "adapter_not_implemented"),
    ConnectorDefinition("twilio", "Twilio Lookup", "Phone", "official_api_high", True, True, False, ("TWILIO_LOOKUP_API_KEY",), (), "Official Twilio Lookup BYOK placeholder; no contact-sync or OTP activity.", "Twilio quota", "https://www.twilio.com/docs/lookup", "adapter_not_implemented"),
    ConnectorDefinition("numverify", "Numverify", "Phone", "third_party_medium", True, True, False, ("NUMVERIFY_API_KEY",), (), "Numverify BYOK placeholder for numbering metadata only.", "Numverify quota", "https://numverify.com/documentation", "adapter_not_implemented"),
    ConnectorDefinition("intelx", "IntelX", "Breach/Data", "third_party_medium", True, True, False, ("INTELX_API_KEY",), (), "IntelX BYOK placeholder; no private API abuse.", "IntelX quota", "https://intelx.io/tools?tab=api", "adapter_not_implemented"),
    ConnectorDefinition("spiderfoot_import", "SpiderFoot Import", "Import", "analyst_provided", False, False, True, (), ("spiderfoot_csv_import",), "Analyst-provided SpiderFoot CSV import preview; no collection performed.", "local import", None),
    ConnectorDefinition("maltego_csv_import", "Maltego CSV Import", "Import", "analyst_provided", False, False, True, (), ("maltego_csv_import",), "Analyst-provided Maltego CSV-compatible import preview.", "local import", None),
    ConnectorDefinition("generic_ioc_csv", "Generic IOC CSV", "Import", "analyst_provided", False, False, True, (), (), "Analyst-provided IOC CSV import preview with evidence attachment.", "local import", None),
)


def _configured_keys(settings: dict[str, Any], runtime_keys: set[str] | None = None) -> set[str]:
    configured = settings.get("api_keys") if isinstance(settings.get("api_keys"), dict) else {}
    aliases = {str(key).upper() for key, value in configured.items() if value}
    aliases.update(runtime_keys or set())
    return aliases


def connector_status(settings: dict[str, Any], runtime_keys: set[str] | None = None, transforms: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    enabled_settings = settings.get("connectors") if isinstance(settings.get("connectors"), dict) else {}
    keys = _configured_keys(settings, runtime_keys)
    transform_by_id = {str(item.get("id")): item for item in (transforms or [])}
    rows: list[dict[str, Any]] = []
    for connector in CONNECTOR_DEFINITIONS:
        key_present = (not connector.requires_api_key) or any(key in keys for key in connector.key_names)
        enabled = enabled_settings.get(connector.id, True) is not False
        unlocked = [transform_by_id.get(item, {"id": item}) for item in connector.unlocked_transforms]
        disabled_reasons: list[str] = []
        if not enabled:
            disabled_reasons.append("disabled_by_operator")
        if connector.disabled_reason:
            disabled_reasons.append(connector.disabled_reason)
        if connector.requires_api_key and not key_present:
            disabled_reasons.append("missing_api_key:" + ",".join(connector.key_names))
        status = "available" if enabled and connector.implemented and key_present else "disabled"
        if connector.requires_api_key and not key_present:
            status = "missing_api_key"
        elif not connector.implemented:
            status = "not_implemented"
        rows.append({
            "id": connector.id,
            "name": connector.name,
            "category": connector.category,
            "source_reliability": connector.source_reliability,
            "reliability": connector.source_reliability,
            "requires_api_key": connector.requires_api_key,
            "requires_key": connector.requires_api_key,
            "configured": key_present,
            "enabled": enabled and connector.implemented and key_present,
            "key_present": key_present,
            "testable": connector.testable,
            "implemented": connector.implemented,
            "test_status": status,
            "last_tested": enabled_settings.get(f"{connector.id}_last_tested"),
            "last_error": enabled_settings.get(f"{connector.id}_last_error"),
            "unlocked_transforms": unlocked,
            "legal_note": connector.legal_note,
            "quota": connector.quota,
            "quota_placeholder": connector.quota,
            "documentation_url": connector.documentation_url,
            "disabled_reason": ";".join(disabled_reasons) if disabled_reasons else None,
        })
    return rows


def test_connector(connector_id: str, settings: dict[str, Any], runtime_keys: set[str] | None = None, transforms: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = {item["id"]: item for item in connector_status(settings, runtime_keys, transforms)}
    row = rows.get(connector_id)
    if not row:
        return {"connector_id": connector_id, "ok": False, "status": "unknown_connector", "tested_at": now_iso(), "message": "Connector is not registered."}
    if not row.get("implemented"):
        return {"connector_id": connector_id, "ok": False, "status": "not_implemented", "tested_at": now_iso(), "message": row.get("disabled_reason") or "Adapter not implemented."}
    if row.get("requires_api_key") and not row.get("key_present"):
        return {"connector_id": connector_id, "ok": False, "status": "missing_api_key", "tested_at": now_iso(), "message": row.get("disabled_reason") or "Required API key is missing."}
    if not row.get("enabled") and row.get("disabled_reason") == "disabled_by_operator":
        return {"connector_id": connector_id, "ok": False, "status": "disabled_by_operator", "tested_at": now_iso(), "message": "Connector is disabled by operator settings."}
    return {"connector_id": connector_id, "ok": True, "status": "metadata_ready", "tested_at": now_iso(), "message": "Connector metadata is available. Live network test is intentionally not run from diagnostics.", "unlocked_transforms": row.get("unlocked_transforms", [])}
