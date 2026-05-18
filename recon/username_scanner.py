import asyncio
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
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from recon.platforms import filter_platforms


console = Console()


@dataclass
class PlatformResult:
    platform: str
    category: str
    url: str
    status: str
    status_code: Optional[int]
    response_time: float
    confidence: float
    evidence: str
    error_message: Optional[str] = None


@dataclass
class ReconReport:
    target: str
    scan_type: str
    total_platforms: int
    found_count: int
    not_found_count: int
    unknown_count: int
    error_count: int
    results: List[PlatformResult]
    duration: float
    generated_at: str


class UsernameScanner:
    def __init__(self, timeout: int = 12, workers: int = 50, verbose: bool = False, output_dir: str = "results"):
        self.timeout = timeout
        self.workers = workers
        self.verbose = verbose
        self.output_dir = output_dir
        self.platforms = filter_platforms()
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize_target(self, target: str) -> str:
        value = target.strip()
        if "@" in value and not value.startswith("@"):
            value = value.split("@", 1)[0]
        return re.sub(r"[^A-Za-z0-9_.-]", "", value.split("/")[-1])

    def _render_summary(self, report: ReconReport) -> None:
        table = Table(title="Username Enumeration", header_style="bold bright_cyan", box=box.SIMPLE_HEAVY)
        table.add_column("Platform", style="bold white", width=20)
        table.add_column("Category", style="cyan", width=13)
        table.add_column("Status", width=12)
        table.add_column("Code", width=7)
        table.add_column("Conf.", justify="right", width=7)
        table.add_column("URL", style="dim")

        for result in sorted(report.results, key=lambda item: (item.status != "found", item.platform.lower())):
            status = result.status
            if status == "found":
                status = "[bold green]FOUND[/bold green]"
            elif status == "not_found":
                status = "[yellow]MISS[/yellow]"
            elif status == "error":
                status = "[red]ERROR[/red]"
            else:
                status = "[cyan]UNKNOWN[/cyan]"

            table.add_row(
                result.platform,
                result.category,
                status,
                str(result.status_code or "-"),
                f"{result.confidence:.2f}",
                result.url,
            )

        console.print(table)
        console.print(
            f"[bold green]{report.found_count} found[/bold green] / "
            f"[yellow]{report.not_found_count} missing[/yellow] / "
            f"[cyan]{report.unknown_count} unknown[/cyan] / "
            f"[red]{report.error_count} error[/red] in [bold]{report.duration:.2f}s[/bold]"
        )

    async def _check_platform(
        self,
        session: aiohttp.ClientSession,
        platform: str,
        config: Dict[str, object],
        username: str,
    ) -> PlatformResult:
        url = str(config["url"]).format(username=username)
        category = str(config.get("type", "general"))
        negative_markers = [str(item).lower() for item in config.get("negative", [])]
        start = time.time()

        try:
            async with session.get(url, timeout=self.timeout, allow_redirects=True) as response:
                elapsed = round(time.time() - start, 2)
                status_code = response.status
                text = (await response.text(errors="ignore"))[:160000].lower()

                if status_code in {404, 410}:
                    status, confidence, evidence = "not_found", 0.95, f"HTTP {status_code}"
                elif status_code == 429:
                    status, confidence, evidence = "unknown", 0.25, "rate limited"
                elif status_code in {200, 301, 302, 303, 403}:
                    negative_hit = next((marker for marker in negative_markers if marker and marker in text), None)
                    if negative_hit:
                        status, confidence, evidence = "not_found", 0.72, f"negative marker: {negative_hit}"
                    else:
                        base_confidence = 0.82 if status_code == 200 else 0.62
                        status, confidence, evidence = "found", base_confidence, f"HTTP {status_code}"
                else:
                    status, confidence, evidence = "unknown", 0.35, f"HTTP {status_code}"

                return PlatformResult(platform, category, url, status, status_code, elapsed, confidence, evidence)
        except asyncio.TimeoutError:
            return PlatformResult(platform, category, url, "error", None, round(time.time() - start, 2), 0.0, "timeout", "Timeout")
        except Exception as exc:
            return PlatformResult(platform, category, url, "error", None, round(time.time() - start, 2), 0.0, "request failed", str(exc))

    async def scan_username(self, username: str, category: Optional[str] = None) -> ReconReport:
        sanitized = self._sanitize_target(username)
        platforms = filter_platforms(category)
        if not platforms:
            raise ValueError(f"No platforms found for category '{category}'")
        if not sanitized:
            raise ValueError("Username target is empty after sanitization.")

        console.print(f"[bold white]Target username:[/bold white] [cyan]{sanitized}[/cyan]")
        console.print(f"[bold white]Platform set:[/bold white] [magenta]{len(platforms)}[/magenta]\n")

        start = time.time()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 NexusRecon/2.0",
            "Accept-Language": "en-US,en;q=0.8",
        }

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(self.workers)

            async def bounded(platform: str, config: Dict[str, object]) -> PlatformResult:
                async with semaphore:
                    return await self._check_platform(session, platform, config, sanitized)

            tasks = [bounded(platform, config) for platform, config in platforms.items()]
            results: List[PlatformResult] = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Probing public profiles", total=len(tasks))
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    if self.verbose and result.status == "found":
                        console.print(f"[green]+[/green] {result.platform}: {result.url}")
                    progress.advance(task)

        report = ReconReport(
            target=sanitized,
            scan_type="username",
            total_platforms=len(results),
            found_count=sum(1 for item in results if item.status == "found"),
            not_found_count=sum(1 for item in results if item.status == "not_found"),
            unknown_count=sum(1 for item in results if item.status == "unknown"),
            error_count=sum(1 for item in results if item.status == "error"),
            results=results,
            duration=round(time.time() - start, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._render_summary(report)
        return report

    def save_report(self, report: ReconReport, format: str = "json") -> str:
        safe_target = re.sub(r"[^A-Za-z0-9_.-]", "_", report.target)
        filename = f"username_scan_{safe_target}_{int(time.time())}.{format}"
        filepath = os.path.join(self.output_dir, filename)

        if format == "json":
            with open(filepath, "w", encoding="utf-8") as handle:
                json.dump(asdict(report), handle, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"Username scan report for {report.target}",
                f"Generated: {report.generated_at}",
                f"Duration: {report.duration}s",
                f"Platforms: {report.total_platforms}",
                f"Found: {report.found_count}",
                f"Missing: {report.not_found_count}",
                f"Unknown: {report.unknown_count}",
                f"Errors: {report.error_count}",
                "",
                "Results:",
            ]
            for item in sorted(report.results, key=lambda result: (result.status != "found", result.platform.lower())):
                lines.append(
                    f"- {item.platform} [{item.category}] {item.status} "
                    f"({item.status_code or '-'}, conf={item.confidence:.2f}) -> {item.url}"
                )
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))

        console.print(f"[bold green]Saved username report:[/bold green] [cyan]{filepath}[/cyan]")
        return filepath
