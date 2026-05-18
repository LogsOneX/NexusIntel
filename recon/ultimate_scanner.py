import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp
from rich import box
from rich.console import Console
from rich.table import Table

from core.targets import normalize_domain


console = Console()


PROVIDERS = {
    "gmail.com": "Google",
    "googlemail.com": "Google",
    "outlook.com": "Microsoft",
    "hotmail.com": "Microsoft",
    "live.com": "Microsoft",
    "yahoo.com": "Yahoo",
    "icloud.com": "Apple",
    "me.com": "Apple",
    "protonmail.com": "Proton",
    "proton.me": "Proton",
    "tutanota.com": "Tuta",
    "aol.com": "AOL",
    "yandex.com": "Yandex",
    "mail.ru": "Mail.ru",
    "gmx.com": "GMX",
    "zoho.com": "Zoho",
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


@dataclass
class EmailResult:
    email: str
    valid_format: bool
    provider: Optional[str]
    domain: Optional[str]
    mx_records: List[str]
    gravatar_hash: Optional[str]
    gravatar_profile: Optional[str]
    disposable_hint: bool
    signals: List[str]
    note: str


@dataclass
class PhoneResult:
    phone: str
    valid: bool
    normalized: Optional[str]
    digit_count: int
    country_hint: Optional[str]
    signals: List[str]
    note: str


@dataclass
class DomainResult:
    domain: str
    registered: bool
    registrar: Optional[str]
    creation_date: Optional[str]
    expiration_date: Optional[str]
    nameservers: List[str]
    a_records: List[str]
    aaaa_records: List[str]
    mx_records: List[str]
    txt_records: List[str]
    dmarc_records: List[str]
    caa_records: List[str]
    certificate_names: List[str]
    emails_found: List[str]
    security_headers: Dict[str, str]
    note: str


class NexusReconUltimate:
    def __init__(self, timeout: int = 12, workers: int = 50, verbose: bool = False, output_dir: str = "results"):
        self.timeout = timeout
        self.workers = workers
        self.verbose = verbose
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _safe_filename(self, label: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", label)

    async def _dns_query(self, domain: str, record_type: str) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://dns.google/resolve",
                    params={"name": domain, "type": record_type},
                    timeout=self.timeout,
                ) as response:
                    if response.status != 200:
                        return []
                    data = await response.json()
                    return [answer.get("data", "") for answer in data.get("Answer", []) if answer.get("data")]
        except Exception:
            return []

    async def _rdap_lookup(self, domain: str) -> Dict[str, object]:
        result: Dict[str, object] = {
            "registered": False,
            "registrar": None,
            "creation_date": None,
            "expiration_date": None,
            "nameservers": [],
            "emails": [],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://rdap.org/domain/{domain}", timeout=self.timeout) as response:
                    if response.status != 200:
                        return result
                    data = await response.json()
        except Exception:
            return result

        result["registered"] = True
        registrar = data.get("registrar")
        result["registrar"] = registrar.get("name") if isinstance(registrar, dict) else registrar

        for event in data.get("events", []):
            action = str(event.get("eventAction", "")).lower()
            if action in {"registration", "registered"} and not result["creation_date"]:
                result["creation_date"] = event.get("eventDate")
            if action in {"expiration", "expiry"} and not result["expiration_date"]:
                result["expiration_date"] = event.get("eventDate")

        result["nameservers"] = [
            ns.get("ldhName")
            for ns in data.get("nameservers", [])
            if isinstance(ns, dict) and ns.get("ldhName")
        ]

        emails: List[str] = []
        for entity in data.get("entities", []):
            for vcard in entity.get("vcardArray", [[], []])[1]:
                if isinstance(vcard, list) and vcard and vcard[0] == "email" and len(vcard) > 3:
                    emails.append(vcard[3])
        result["emails"] = sorted(set(emails))
        return result

    async def _crtsh_names(self, domain: str) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://crt.sh/",
                    params={"q": f"%.{domain}", "output": "json"},
                    timeout=self.timeout,
                ) as response:
                    if response.status != 200:
                        return []
                    data = await response.json(content_type=None)
        except Exception:
            return []

        names = set()
        for item in data[:250]:
            raw = item.get("name_value", "")
            for name in raw.splitlines():
                clean = name.strip().lower().lstrip("*.").rstrip(".")
                if clean.endswith(domain) and clean != domain:
                    names.add(clean)
        return sorted(names)[:80]

    async def _security_headers(self, domain: str) -> Dict[str, str]:
        headers_of_interest = [
            "server",
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy",
        ]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(f"https://{domain}", allow_redirects=True, timeout=self.timeout) as response:
                    return {key: response.headers.get(key, "missing") for key in headers_of_interest}
        except Exception:
            return {key: "unreachable" for key in headers_of_interest}

    def _render_email(self, result: EmailResult) -> None:
        values = {
            "Email": result.email,
            "Valid format": result.valid_format,
            "Provider": result.provider or "Unknown",
            "Domain": result.domain or "-",
            "MX": ", ".join(result.mx_records) if result.mx_records else "None",
            "Gravatar": result.gravatar_profile or "No public profile",
            "Disposable hint": result.disposable_hint,
            "Signals": ", ".join(result.signals) if result.signals else "-",
            "Note": result.note,
        }
        self._render_table("Email Intelligence", values)

    def _render_phone(self, result: PhoneResult) -> None:
        values = {
            "Input": result.phone,
            "Valid pattern": result.valid,
            "Normalized": result.normalized or "-",
            "Digits": result.digit_count,
            "Country hint": result.country_hint or "Unknown",
            "Signals": ", ".join(result.signals) if result.signals else "-",
            "Note": result.note,
        }
        self._render_table("Phone Intelligence", values)

    def _render_domain(self, result: DomainResult) -> None:
        values = {
            "Domain": result.domain,
            "Registered": result.registered,
            "Registrar": result.registrar or "Unknown",
            "Created": result.creation_date or "Unknown",
            "Expires": result.expiration_date or "Unknown",
            "NS": ", ".join(result.nameservers[:6]) if result.nameservers else "None",
            "A": ", ".join(result.a_records[:6]) if result.a_records else "None",
            "MX": ", ".join(result.mx_records[:4]) if result.mx_records else "None",
            "DMARC": ", ".join(result.dmarc_records[:2]) if result.dmarc_records else "None",
            "Certificates": f"{len(result.certificate_names)} passive name(s)",
            "Emails": ", ".join(result.emails_found) if result.emails_found else "None",
            "Note": result.note,
        }
        self._render_table("Domain Intelligence", values)

    def _render_table(self, title: str, values: Dict[str, object]) -> None:
        table = Table(title=title, show_header=False, box=box.SIMPLE_HEAVY)
        table.add_column("Field", style="dim")
        table.add_column("Value", style="white")
        for key, value in values.items():
            table.add_row(key, str(value))
        console.print(table)

    async def scan_email(self, email: str, save: bool = False, format: str = "json") -> EmailResult:
        sanitized = email.strip().lower()
        valid_format = bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sanitized))
        signals: List[str] = []
        provider = domain = gravatar_hash = gravatar_profile = None
        mx_records: List[str] = []
        disposable_hint = False

        if valid_format:
            domain = sanitized.split("@", 1)[1]
            provider = PROVIDERS.get(domain, "Custom / unknown")
            mx_records = await self._dns_query(domain, "MX")
            if mx_records:
                signals.append("mx_records")
            disposable_hint = any(token in domain for token in ("mailinator", "tempmail", "10minutemail", "guerrillamail"))
            if disposable_hint:
                signals.append("disposable_domain_hint")

            gravatar_hash = hashlib.md5(sanitized.encode("utf-8")).hexdigest()
            gravatar_url = f"https://en.gravatar.com/{gravatar_hash}.json"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(gravatar_url, timeout=self.timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            entry = data.get("entry", [{}])[0]
                            gravatar_profile = entry.get("profileUrl") or f"https://gravatar.com/{gravatar_hash}"
                            signals.append("gravatar_profile")
            except Exception:
                pass
            note = "Passive email checks completed."
        else:
            note = "Invalid email format."

        result = EmailResult(
            email=sanitized,
            valid_format=valid_format,
            provider=provider,
            domain=domain,
            mx_records=mx_records,
            gravatar_hash=gravatar_hash,
            gravatar_profile=gravatar_profile,
            disposable_hint=disposable_hint,
            signals=signals,
            note=note,
        )
        self._render_email(result)
        if save:
            self.save_report(result, format=format)
        return result

    async def scan_phone(self, phone: str, save: bool = False, format: str = "json") -> PhoneResult:
        digits = re.sub(r"\D", "", phone)
        valid = 7 <= len(digits) <= 15
        normalized = f"+{digits}" if digits else None
        signals = []
        country_hint = None
        for code, country in sorted(COUNTRY_CODES.items(), key=lambda item: len(item[0]), reverse=True):
            if digits.startswith(code):
                country_hint = country
                signals.append(f"country_code_{code}")
                break
        if len(digits) in {10, 11, 12, 13}:
            signals.append("common_mobile_length")
        note = "Pattern-only public phone analysis completed." if valid else "Invalid phone number pattern."

        result = PhoneResult(phone=phone, valid=valid, normalized=normalized, digit_count=len(digits), country_hint=country_hint, signals=signals, note=note)
        self._render_phone(result)
        if save:
            self.save_report(result, format=format)
        return result

    async def scan_domain(self, domain: str, save: bool = False, format: str = "json") -> DomainResult:
        sanitized = normalize_domain(domain)
        rdap_task = asyncio.create_task(self._rdap_lookup(sanitized))
        dns_tasks = {
            "a": asyncio.create_task(self._dns_query(sanitized, "A")),
            "aaaa": asyncio.create_task(self._dns_query(sanitized, "AAAA")),
            "mx": asyncio.create_task(self._dns_query(sanitized, "MX")),
            "txt": asyncio.create_task(self._dns_query(sanitized, "TXT")),
            "dmarc": asyncio.create_task(self._dns_query(f"_dmarc.{sanitized}", "TXT")),
            "caa": asyncio.create_task(self._dns_query(sanitized, "CAA")),
        }
        crt_task = asyncio.create_task(self._crtsh_names(sanitized))
        headers_task = asyncio.create_task(self._security_headers(sanitized))

        rdap_data = await rdap_task
        dns = {key: await task for key, task in dns_tasks.items()}
        certificate_names = await crt_task
        headers = await headers_task

        result = DomainResult(
            domain=sanitized,
            registered=bool(rdap_data["registered"]),
            registrar=rdap_data.get("registrar"),
            creation_date=rdap_data.get("creation_date"),
            expiration_date=rdap_data.get("expiration_date"),
            nameservers=list(rdap_data.get("nameservers", [])),
            a_records=dns["a"],
            aaaa_records=dns["aaaa"],
            mx_records=dns["mx"],
            txt_records=dns["txt"],
            dmarc_records=dns["dmarc"],
            caa_records=dns["caa"],
            certificate_names=certificate_names,
            emails_found=list(rdap_data.get("emails", [])),
            security_headers=headers,
            note="RDAP, DNS, certificate transparency, and header checks completed.",
        )
        self._render_domain(result)
        if save:
            self.save_report(result, format=format)
        return result

    def save_report(self, result: object, format: str = "json") -> str:
        label = getattr(result, "email", None) or getattr(result, "phone", None) or getattr(result, "domain", "scan")
        filename = f"ultimate_{self._safe_filename(label)}_{int(time.time())}.{format}"
        filepath = os.path.join(self.output_dir, filename)

        if format == "json":
            with open(filepath, "w", encoding="utf-8") as handle:
                json.dump(asdict(result), handle, indent=2, ensure_ascii=False)
        else:
            lines = [f"Scan Report - {label}", f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]
            for key, value in asdict(result).items():
                lines.append(f"{key}: {value}")
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))

        console.print(f"[bold green]Saved discovery report:[/bold green] [cyan]{filepath}[/cyan]")
        return filepath
