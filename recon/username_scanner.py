import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

@dataclass
class PlatformResult:
    platform: str
    url: str
    status: str
    status_code: Optional[int]
    response_time: float
    error_message: Optional[str] = None

@dataclass
class ReconReport:
    target: str
    scan_type: str
    total_platforms: int
    found_count: int
    not_found_count: int
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
        self.platforms = self._load_platforms()
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_platforms(self) -> Dict[str, Dict[str, str]]:
        return {
            "GitHub": {"url": "https://github.com/{username}", "type": "tech"},
            "GitLab": {"url": "https://gitlab.com/{username}", "type": "tech"},
            "StackOverflow": {"url": "https://stackoverflow.com/users/{username}", "type": "tech"},
            "Dev.to": {"url": "https://dev.to/{username}", "type": "tech"},
            "Dribbble": {"url": "https://dribbble.com/{username}", "type": "creative"},
            "Behance": {"url": "https://behance.net/{username}", "type": "creative"},
            "SoundCloud": {"url": "https://soundcloud.com/{username}", "type": "creative"},
            "Vimeo": {"url": "https://vimeo.com/{username}", "type": "creative"},
            "Instagram": {"url": "https://instagram.com/{username}", "type": "social"},
            "Twitter": {"url": "https://twitter.com/{username}", "type": "social"},
            "TikTok": {"url": "https://tiktok.com/@{username}", "type": "social"},
            "Reddit": {"url": "https://reddit.com/user/{username}", "type": "social"},
            "Facebook": {"url": "https://facebook.com/{username}", "type": "social"},
            "Pinterest": {"url": "https://pinterest.com/{username}", "type": "social"},
            "YouTube": {"url": "https://youtube.com/@{username}", "type": "social"},
            "Snapchat": {"url": "https://snapchat.com/add/{username}", "type": "social"},
            "Telegram": {"url": "https://t.me/{username}", "type": "social"},
            "Mastodon": {"url": "https://mastodon.social/@{username}", "type": "social"},
            "LinkedIn": {"url": "https://linkedin.com/in/{username}", "type": "professional"},
            "Fiverr": {"url": "https://fiverr.com/{username}", "type": "professional"},
            "Upwork": {"url": "https://upwork.com/freelancers/{username}", "type": "professional"},
            "AngelList": {"url": "https://angel.co/u/{username}", "type": "professional"},
            "ProductHunt": {"url": "https://producthunt.com/@{username}", "type": "professional"},
            "Medium": {"url": "https://medium.com/@{username}", "type": "blog"},
            "WordPress": {"url": "https://{username}.wordpress.com", "type": "blog"},
            "Tumblr": {"url": "https://{username}.tumblr.com", "type": "blog"},
            "Etsy": {"url": "https://etsy.com/shop/{username}", "type": "ecommerce"},
            "eBay": {"url": "https://ebay.com/usr/{username}", "type": "ecommerce"},
            "PayPal": {"url": "https://paypal.me/{username}", "type": "finance"},
            "Venmo": {"url": "https://venmo.com/{username}", "type": "finance"},
            "CashApp": {"url": "https://cash.app/${username}", "type": "finance"},
            "Trello": {"url": "https://trello.com/{username}", "type": "productivity"},
            "Notion": {"url": "https://notion.so/{username}", "type": "productivity"},
        }

    def _sanitize_target(self, target: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.@-]", "", target)

    def _render_summary(self, report: ReconReport) -> None:
        console.print("\n[bold green]Username enumeration result summary[/bold green]\n")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Platform", style="dim", width=24)
        table.add_column("Status", width=12)
        table.add_column("Code", width=8)
        table.add_column("Response (s)", justify="right")

        for result in sorted(report.results, key=lambda item: (item.status != "found", item.platform.lower())):
            status = result.status
            if status == "found":
                status = "[bold green]FOUND[/bold green]"
            elif status == "not_found":
                status = "[yellow]MISSING[/yellow]"
            elif status == "error":
                status = "[red]ERROR[/red]"
            else:
                status = "[cyan]UNKNOWN[/cyan]"

            table.add_row(result.platform, status, str(result.status_code or "-"), f"{result.response_time:.2f}")

        console.print(table)

    async def _check_platform(self, session: aiohttp.ClientSession, platform: str, url_template: str, username: str) -> PlatformResult:
        url = url_template.format(username=username)
        start = time.time()

        try:
            async with session.get(url, timeout=self.timeout, allow_redirects=True) as response:
                elapsed = time.time() - start
                status_code = response.status
                text = await response.text(errors="ignore")

                if status_code in {200, 403}:
                    status = "found"
                elif status_code == 404:
                    status = "not_found"
                else:
                    status = "unknown"

                return PlatformResult(platform=platform, url=url, status=status, status_code=status_code, response_time=round(elapsed, 2))
        except asyncio.TimeoutError:
            return PlatformResult(platform=platform, url=url, status="error", status_code=None, response_time=round(time.time() - start, 2), error_message="Timeout")
        except Exception as exc:
            return PlatformResult(platform=platform, url=url, status="error", status_code=None, response_time=round(time.time() - start, 2), error_message=str(exc))

    async def scan_username(self, username: str, category: Optional[str] = None) -> ReconReport:
        sanitized = self._sanitize_target(username)
        if category:
            category = category.lower()
            platforms = {name: cfg for name, cfg in self.platforms.items() if cfg.get("type") == category}
            if not platforms:
                raise ValueError(f"No platforms found for category '{category}'")
        else:
            platforms = self.platforms

        if not platforms:
            raise ValueError("No platforms available for scan. Update configuration.")

        console.print(f"[bold white]Scanning username:[/bold white] [cyan]{sanitized}[/cyan]")
        console.print(f"[bold white]Platform set:[/bold white] [magenta]{len(platforms)} platform(s)[/magenta]\n")

        start = time.time()
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}) as session:
            semaphore = asyncio.Semaphore(self.workers)
            tasks = []

            for platform, cfg in platforms.items():
                tasks.append(self._bounded_check(session, semaphore, platform, cfg["url"], sanitized))

            results = []
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
                task = progress.add_task("Performing username enumeration...", total=len(tasks))
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    progress.advance(task)

        report = ReconReport(
            target=sanitized,
            scan_type="username",
            total_platforms=len(results),
            found_count=sum(1 for r in results if r.status == "found"),
            not_found_count=sum(1 for r in results if r.status == "not_found"),
            error_count=sum(1 for r in results if r.status == "error"),
            results=results,
            duration=round(time.time() - start, 2),
            generated_at=datetime.utcnow().isoformat() + "Z"
        )

        self._render_summary(report)
        return report

    async def _bounded_check(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, platform: str, url_template: str, username: str) -> PlatformResult:
        async with semaphore:
            return await self._check_platform(session, platform, url_template, username)

    def save_report(self, report: ReconReport, format: str = "json") -> str:
        filename = f"username_scan_{report.target}_{int(time.time())}.{format}"
        filepath = os.path.join(self.output_dir, filename)

        if format == "json":
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump({
                    "target": report.target,
                    "scan_type": report.scan_type,
                    "generated_at": report.generated_at,
                    "duration": report.duration,
                    "total_platforms": report.total_platforms,
                    "found_count": report.found_count,
                    "not_found_count": report.not_found_count,
                    "error_count": report.error_count,
                    "results": [r.__dict__ for r in report.results]
                }, fh, indent=2)
        else:
            lines = [
                f"Username scan report for {report.target}",
                f"Generated: {report.generated_at}",
                f"Duration: {report.duration}s",
                f"Total platforms: {report.total_platforms}",
                f"Found: {report.found_count}",
                f"Not found: {report.not_found_count}",
                f"Errors: {report.error_count}",
                "\nResults:",
            ]
            for r in report.results:
                lines.append(f"- {r.platform}: {r.status} ({r.status_code or '-'}) -> {r.url}")

            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))

        console.print(f"[bold green]Saved username report:[/bold green] [cyan]{filepath}[/cyan]")
        return filepath
