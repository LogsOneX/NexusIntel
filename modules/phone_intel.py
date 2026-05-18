import re


metadata = {
    "name": "Phone Pattern Intelligence",
    "description": "Offline phone number normalization, length checks, country-code hints, and risk notes.",
    "category": "identity",
    "target_types": ["phone"],
    "tags": ["phone", "pattern", "offline"],
    "passive": True,
    "risk": "low",
}


COUNTRY_CODES = {
    "1": "North America",
    "44": "United Kingdom",
    "49": "Germany",
    "60": "Malaysia",
    "61": "Australia",
    "62": "Indonesia",
    "63": "Philippines",
    "65": "Singapore",
    "81": "Japan",
    "82": "South Korea",
    "91": "India",
}


async def run(target: str) -> dict:
    digits = re.sub(r"\D", "", target)
    valid = 7 <= len(digits) <= 15
    normalized = f"+{digits}" if digits else None
    country_hint = None
    signals = []

    for code, country in sorted(COUNTRY_CODES.items(), key=lambda item: len(item[0]), reverse=True):
        if digits.startswith(code):
            country_hint = country
            signals.append({"type": "country_code", "code": code, "value": country})
            break

    if valid:
        signals.append({"type": "length", "value": "valid_e164_range"})
    if len(digits) in {10, 11, 12, 13}:
        signals.append({"type": "shape", "value": "common_mobile_length"})

    return {
        "status": "success",
        "summary": f"Phone pattern valid={valid}, country={country_hint or 'unknown'}.",
        "data": {
            "target": target,
            "normalized": normalized,
            "digit_count": len(digits),
            "valid_e164_range": valid,
            "country_hint": country_hint,
            "signals": signals,
            "note": "Pattern-only analysis; no carrier or subscriber lookup is performed.",
        },
    }
