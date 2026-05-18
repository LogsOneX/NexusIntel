import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from rich.console import Console
from rich.table import Table

console = Console()

@dataclass
class EmailResult:
    email: str
    valid_format: bool
    provider: Optional[str]
    mx_records: List[str]
    note: str

@dataclass
class PhoneResult:
    phone: str
    valid: bool
    normalized: Optional[str]
    note: str

@dataclass
class DomainResult:
    domain: str
    registered: bool
    registrar: Optional[str]
    creation_date: Optional[str]
    expiration_date: Optional[str]
    nameservers: List[str]
    emails_found: List[str]
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

    def _render_email(self, result: EmailResult) -> None:
        console.print("\n[bold green]Email discovery result[/bold green]\n")
        table = Table(show_header=False)
        table.add_row("Email", f"[cyan]{result.email}[/cyan]")
        table.add_row("Valid format", str(result.valid_format))
        table.add_row("Provider", result.provider or "Unknown")
        table.add_row("MX records", ", ".join(result.mx_records) if result.mx_records else "None")
        table.add_row("Note", result.note)
        console.print(table)

    def _render_phone(self, result: PhoneResult) -> None:
        console.print("\n[bold green]Phone discovery result[/bold green]\n")
        table = Table(show_header=False)
        table.add_row("Phone", f"[cyan]{result.phone}[/cyan]")
        table.add_row("Valid", str(result.valid))
        table.add_row("Normalized", result.normalized or "N/A")
        table.add_row("Note", result.note)
        console.print(table)

    def _render_domain(self, result: DomainResult) -> None:
        console.print("\n[bold green]Domain discovery result[/bold green]\n")
        table = Table(show_header=False)
        table.add_row("Domain", f"[cyan]{result.domain}[/cyan]")
        table.add_row("Registered", str(result.registered))
        table.add_row("Registrar", result.registrar or "Unknown")
        table.add_row("Created", result.creation_date or "Unknown")
        table.add_row("Expires", result.expiration_date or "Unknown")
        table.add_row("Nameservers", ", ".join(result.nameservers) if result.nameservers else "None")
        table.add_row("Emails found", ", ".join(result.emails_found) if result.emails_found else "None")
        table.add_row("Note", result.note)
        console.print(table)

    async def _lookup_mx_records(self, domain: str) -> List[str]:
        mx_records: List[str] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        for answer in data.get("Answer", []):
                            mx_records.append(answer.get("data", ""))
        except Exception:
            pass
        return mx_records

    async def _rdap_lookup(self, domain: str) -> Dict[str, Optional[str]]:
        result: Dict[str, Optional[str]] = {
            "registered": False,
            "registrar": None,
            "creation_date": None,
            "expiration_date": None,
            "nameservers": [],
            "emails": []
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://rdap.org/domain/{domain}", timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result["registered"] = True
                        result["registrar"] = data.get("registrar", {}).get("name") if isinstance(data.get("registrar"), dict) else data.get("registrar")
                        result["creation_date"] = data.get("events", [{}])[0].get("eventDate") if data.get("events") else None
                        result["expiration_date"] = data.get("events", [{}])[-1].get("eventDate") if data.get("events") else None
                        result["nameservers"] = [ns.get("ldhName") for ns in data.get("nameservers", []) if isinstance(ns, dict)]
                        for entity in data.get("entities", []):
                            for vcard in entity.get("vcardArray", [[], []])[1]:
                                if isinstance(vcard, list) and vcard[0] == "email":
                                    result["emails"].append(vcard[3])
        except Exception:
            pass

        return result

    async def scan_email(self, email: str, save: bool = False, format: str = "json") -> EmailResult:
        provider = None
        note = "No strong metadata available without external API keys."
        sanitized = email.strip()
        valid_format = bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sanitized))

        if valid_format:
            provider = sanitized.split("@", 1)[1].lower()
            mx_records = await self._lookup_mx_records(provider)
            note = "MX lookup completed." if mx_records else "No MX records discovered." 
        else:
            mx_records = []
            note = "Invalid email format."

        result = EmailResult(email=sanitized, valid_format=valid_format, provider=provider, mx_records=mx_records, note=note)
        self._render_email(result)

        if save:
            self.save_report(result, format=format)

        return result

    async def scan_phone(self, phone: str, save: bool = False, format: str = "json") -> PhoneResult:
        digits = re.sub(r"\D", "", phone)
        valid = len(digits) >= 7 and len(digits) <= 15
        normalized = f"+{digits}" if digits else None
        note = "Potentially valid international phone number." if valid else "Invalid phone number pattern." 

        result = PhoneResult(phone=phone, valid=valid, normalized=normalized, note=note)
        self._render_phone(result)

        if save:
            self.save_report(result, format=format)

        return result

    async def scan_domain(self, domain: str, save: bool = False, format: str = "json") -> DomainResult:
        sanitized = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        rdap_data = await self._rdap_lookup(sanitized)
        note = "RDAP and DNS lookup completed." if rdap_data.get("registered") else "Domain appears unregistered or lookup failed."
        result = DomainResult(
            domain=sanitized,
            registered=rdap_data["registered"],
            registrar=rdap_data["registrar"],
            creation_date=rdap_data["creation_date"],
            expiration_date=rdap_data["expiration_date"],
            nameservers=rdap_data["nameservers"] or [],
            emails_found=rdap_data["emails"] or [],
            note=note
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
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(asdict(result), fh, indent=2)
        else:
            lines = [f"Scan Report - {label}", f"Generated: {datetime.utcnow().isoformat()}Z", ""]
            for key, value in asdict(result).items():
                lines.append(f"{key}: {value}")
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))

        console.print(f"[bold green]Saved discovery report:[/bold green] [cyan]{filepath}[/cyan]")
        return filepath
