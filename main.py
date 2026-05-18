import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.engine import AnalyticsEngine
from core.reporter import ReportGenerator
from recon.ultimate_scanner import NexusReconUltimate
from recon.username_scanner import UsernameScanner

console = Console()

BANNER = """
[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]
[bold white]          DATA AGGREGATOR / NEXUSRECON UNIFIED OSINT CLI          [/bold white]
[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]
"""


def print_banner() -> None:
    console.print(Panel.fit(BANNER, title="[bold green]OSINT FRAMEWORK[/bold green]", border_style="bright_blue"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-aggregator",
        description="Unified OSINT scanner for target analytics, username enumeration, email discovery, phone reconnaissance, and domain intelligence.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    aggregate = subparsers.add_parser("aggregate", help="Run public analytics modules against a host or URL.")
    aggregate.add_argument("-t", "--target", required=True, help="Target domain or URL to analyze.")
    aggregate.add_argument("--save", action="store_true", help="Save module report files.")
    aggregate.add_argument("--format", choices=["json", "md"], default="json", help="Save output format for aggregated report.")

    username = subparsers.add_parser("username", help="Enumerate a username across many platforms.")
    username.add_argument("username", help="Username to scan.")
    username.add_argument("--timeout", type=int, default=12, help="HTTP request timeout in seconds.")
    username.add_argument("--workers", type=int, default=45, help="Number of concurrent requests.")
    username.add_argument("--category", help="Filter scan to a platform category like social, tech, gaming.")
    username.add_argument("--save", action="store_true", help="Save the scan report.")
    username.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")
    username.add_argument("--verbose", action="store_true", help="Show verbose progress output.")

    email = subparsers.add_parser("email", help="Validate and inspect a public email address.")
    email.add_argument("email", help="Email address to inspect.")
    email.add_argument("--save", action="store_true", help="Save the email report.")
    email.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    phone = subparsers.add_parser("phone", help="Analyze a phone number string.")
    phone.add_argument("phone", help="Phone number to inspect.")
    phone.add_argument("--save", action="store_true", help="Save the phone report.")
    phone.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    domain = subparsers.add_parser("domain", help="Inspect domain registration and DNS metadata.")
    domain.add_argument("domain", help="Domain to inspect.")
    domain.add_argument("--save", action="store_true", help="Save the domain report.")
    domain.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    list_modules = subparsers.add_parser("list-modules", help="List available aggregator modules.")
    list_modules.add_argument("--source", choices=["modules"], default="modules", help="Source of available modules.")

    return parser


async def run_aggregate(target: str, save: bool, output_format: str) -> None:
    print_banner()
    engine = AnalyticsEngine()
    engine.load_modules()
    loaded = list(engine.loaded_modules.keys())

    console.print(f"[bold green]Modules loaded:[/bold green] [cyan]{len(loaded)}[/cyan] {loaded}")
    if not loaded:
        console.print("[bold red]No analytics modules available. Aborting.[/bold red]")
        return

    console.print(f"\n[bold white]Running aggregate scan for:[/bold white] [cyan]{target}[/cyan]\n")
    results = await engine.execute_all(target)

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Module", style="dim")
    table.add_column("Status")
    table.add_column("Details")

    for module_name, output in results.items():
        if output.get("status") == "error":
            table.add_row(module_name, "[red]ERROR[/red]", output.get("message", "Unknown error"))
        else:
            count = len(output.get("data", {})) if isinstance(output.get("data", dict)) else len(output.get("data", []))
            table.add_row(module_name, "[green]OK[/green]", f"{count} data points collected")

    console.print(table)

    if save:
        reporter = ReportGenerator(target=target, results=results)
        json_path = reporter.generate_json()
        md_path = reporter.generate_markdown()
        console.print(f"\n[bold green]Saved reports:[/bold green] [cyan]{json_path}[/cyan], [cyan]{md_path}[/cyan]")


async def run_username_scan(args: argparse.Namespace) -> None:
    print_banner()
    scanner = UsernameScanner(timeout=args.timeout, workers=args.workers, verbose=args.verbose)
    report = await scanner.scan_username(args.username, category=args.category)
    if args.save:
        scanner.save_report(report, format=args.format)


async def run_email_scan(args: argparse.Namespace) -> None:
    print_banner()
    scanner = NexusReconUltimate()
    await scanner.scan_email(args.email, save=args.save, format=args.format)


async def run_phone_scan(args: argparse.Namespace) -> None:
    print_banner()
    scanner = NexusReconUltimate()
    await scanner.scan_phone(args.phone, save=args.save, format=args.format)


async def run_domain_scan(args: argparse.Namespace) -> None:
    print_banner()
    scanner = NexusReconUltimate()
    await scanner.scan_domain(args.domain, save=args.save, format=args.format)


def list_available_modules() -> None:
    engine = AnalyticsEngine()
    engine.load_modules()
    loaded = sorted(engine.loaded_modules.keys())

    console.print("\n[bold green]Available analytics modules[/bold green]\n")
    for entry in loaded:
        console.print(f"• [cyan]{entry}[/cyan]")


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "aggregate":
        await run_aggregate(args.target, args.save, args.format)
    elif args.command == "username":
        await run_username_scan(args)
    elif args.command == "email":
        await run_email_scan(args)
    elif args.command == "phone":
        await run_phone_scan(args)
    elif args.command == "domain":
        await run_domain_scan(args)
    elif args.command == "list-modules":
        list_available_modules()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
