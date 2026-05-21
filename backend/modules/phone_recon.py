from __future__ import annotations

import re
from typing import Any

from .common import EmitCallback, ReconFinding, maybe_emit

try:
    import phonenumbers  # type: ignore
    from phonenumbers import carrier, geocoder, timezone  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    phonenumbers = None
    carrier = geocoder = timezone = None

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

COUNTRY_CALLING_CODES = {
    "1": {"region": "North America", "type": "nanp"},
    "44": {"region": "United Kingdom", "type": "national_plan"},
    "49": {"region": "Germany", "type": "national_plan"},
    "55": {"region": "Brazil", "type": "national_plan"},
    "60": {"region": "Malaysia", "type": "national_plan"},
    "61": {"region": "Australia", "type": "national_plan"},
    "62": {"region": "Indonesia", "type": "national_plan"},
    "63": {"region": "Philippines", "type": "national_plan"},
    "65": {"region": "Singapore", "type": "national_plan"},
    "81": {"region": "Japan", "type": "national_plan"},
    "82": {"region": "South Korea", "type": "national_plan"},
    "86": {"region": "China", "type": "national_plan"},
    "91": {"region": "India", "type": "national_plan"},
}

INDONESIA_MOBILE_PREFIXES = {
    "811", "812", "813", "821", "822", "823", "851", "852", "853", "855", "856", "857", "858", "859",
    "877", "878", "879", "881", "882", "883", "884", "885", "886", "887", "888", "889", "895", "896", "897", "898", "899",
}


class PhoneResolver:
    """Public phone validation and numbering-plan posture resolver.

    This module does not perform WhatsApp/Telegram/Instagram/Facebook account-existence or contact-sync checks.
    It emits safe deep-link candidates as investigation pivots only, without fetching or claiming registration.
    """

    def normalize(self, value: str) -> str:
        raw = value.strip().replace(" ", "").replace("-", "")
        if raw.startswith("00"):
            raw = "+" + raw[2:]
        return raw

    def fallback_plan(self, e164: str) -> dict[str, Any]:
        digits = e164.lstrip("+")
        for length in range(1, 4):
            code = digits[:length]
            if code in COUNTRY_CALLING_CODES:
                meta = COUNTRY_CALLING_CODES[code]
                subscriber = digits[length:]
                line_type = "unknown"
                if code == "62" and subscriber.startswith("8") and subscriber[:3] in INDONESIA_MOBILE_PREFIXES:
                    line_type = "mobile_candidate"
                return {"calling_code": code, "region": meta["region"], "plan_type": meta["type"], "subscriber": subscriber, "line_type": line_type}
        return {"calling_code": None, "region": "unknown", "plan_type": "unknown", "subscriber": digits, "line_type": "unknown"}

    async def resolve(self, phone: str, *, emit: EmitCallback | None = None) -> dict[str, Any]:
        e164 = self.normalize(phone)
        valid_regex = bool(E164_RE.match(e164))
        findings: list[ReconFinding] = [
            ReconFinding("validation", "E.164 format", f"phone:{e164}:format", "ghost_phone", "high" if valid_regex else "low", "HAS_VALIDATION", {"valid_e164_regex": valid_regex}),
        ]
        await maybe_emit(emit, f"Phone E.164 validation: {'valid' if valid_regex else 'invalid'}", findings[-1].as_artifact())

        parsed_data: dict[str, Any] = self.fallback_plan(e164)
        if phonenumbers:
            try:
                parsed = phonenumbers.parse(e164, None)
                parsed_data.update(
                    {
                        "valid": phonenumbers.is_valid_number(parsed),
                        "possible": phonenumbers.is_possible_number(parsed),
                        "country_code": parsed.country_code,
                        "national_number": parsed.national_number,
                        "region_code": phonenumbers.region_code_for_number(parsed),
                        "carrier": carrier.name_for_number(parsed, "en") if carrier else "",
                        "geolocation": geocoder.description_for_number(parsed, "en") if geocoder else "",
                        "timezones": list(timezone.time_zones_for_number(parsed)) if timezone else [],
                        "number_type": str(phonenumbers.number_type(parsed)),
                    }
                )
            except Exception as exc:
                parsed_data["parse_error"] = str(exc)

        plan_finding = ReconFinding("phone_posture", "Numbering plan", f"phone:{e164}:numbering_plan", "ghost_phone", "high" if parsed_data.get("valid") or valid_regex else "low", "HAS_NUMBERING_PLAN", parsed_data)
        findings.append(plan_finding)
        await maybe_emit(emit, f"Phone numbering plan resolved: {parsed_data.get('region') or parsed_data.get('region_code') or 'unknown'}", plan_finding.as_artifact())

        for name, url in {
            "WhatsApp public deep-link candidate": f"https://wa.me/{e164.lstrip('+')}",
            "Telegram public username/phone link candidate": f"https://t.me/+{e164.lstrip('+')}",
            "Viber public add-contact link candidate": f"viber://chat?number={e164}",
        }.items():
            finding = ReconFinding("deeplink_candidate", name, url, "ghost_phone", "low", "HAS_PUBLIC_DEEPLINK_CANDIDATE", {"queried": False, "registration_claim": False, "reason": "no account-existence probing"})
            findings.append(finding)
        guardrail = ReconFinding("guardrail", "Messenger account-existence probes skipped", f"phone:{e164}:guardrail", "ghost_phone", "confirmed", "HAS_GUARDRAIL", {"skipped": ["whatsapp_fetch", "telegram_fetch", "instagram_contact_sync", "facebook_contact_sync"], "reason": "public-source-only policy"})
        findings.append(guardrail)
        return {"target": e164, "valid_e164": valid_regex, "plan": parsed_data, "artifacts": [finding.as_artifact() for finding in findings]}
