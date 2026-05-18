import argparse
import asyncio
import sys
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.engine import AnalyticsEngine
from core.graph import build_investigation_graph
from core.render import (
    print_banner,
    render_engine_results,
    render_module_catalog,
    render_project_overview,
    render_run_dashboard,
    render_target_profile,
)
from core.reporter import ReportGenerator
from core.targets import classify_target
from dashboard.server import DEFAULT_ADDR, serve_dashboard
from recon.platforms import platform_categories
from recon.ultimate_scanner import NexusReconUltimate
from recon.username_scanner import UsernameScanner


console = Console()


def _csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexusrecon",
        description="NexusRecon / Data Aggregator - passive advanced OSINT command center.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--no-banner", action="store_true", help="Do not render the Rich banner.")

    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    hunt = subparsers.add_parser("hunt", help="Run the unified passive OSINT workflow for any target.")
    hunt.add_argument("target", help="Username, email, domain, URL, or phone number.")
    hunt.add_argument("--include", help="Comma-separated module names to include.")
    hunt.add_argument("--exclude", help="Comma-separated module names to exclude.")
    hunt.add_argument("--category", help="Run only modules in a category, for example identity or infrastructure.")
    hunt.add_argument("--timeout", type=int, default=25, help="Per-module timeout in seconds.")
    hunt.add_argument("--concurrency", type=int, default=8, help="Concurrent modules.")
    hunt.add_argument("--save", action="store_true", help="Save a final report.")
    hunt.add_argument("--format", choices=["json", "md", "html", "graph"], default="json", help="Report format.")

    aggregate = subparsers.add_parser("aggregate", help="Run analytics modules against a target.")
    aggregate.add_argument("-t", "--target", required=True, help="Target to analyze.")
    aggregate.add_argument("--include", help="Comma-separated module names to include.")
    aggregate.add_argument("--exclude", help="Comma-separated module names to exclude.")
    aggregate.add_argument("--category", help="Run only modules in a category.")
    aggregate.add_argument("--timeout", type=int, default=25, help="Per-module timeout in seconds.")
    aggregate.add_argument("--concurrency", type=int, default=8, help="Concurrent modules.")
    aggregate.add_argument("--save", action="store_true", help="Save module report file.")
    aggregate.add_argument("--format", choices=["json", "md", "html", "graph"], default="json", help="Report format.")

    username = subparsers.add_parser("username", help="Enumerate a username across public platforms.")
    username.add_argument("username", help="Username or email local-part to scan.")
    username.add_argument("--timeout", type=int, default=12, help="HTTP request timeout in seconds.")
    username.add_argument("--workers", type=int, default=45, help="Number of concurrent requests.")
    username.add_argument("--category", choices=platform_categories(), help="Filter to a platform category.")
    username.add_argument("--save", action="store_true", help="Save the scan report.")
    username.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")
    username.add_argument("--verbose", action="store_true", help="Show found profiles as they appear.")

    email = subparsers.add_parser("email", help="Inspect an email address with passive checks.")
    email.add_argument("email", help="Email address to inspect.")
    email.add_argument("--save", action="store_true", help="Save the email report.")
    email.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    phone = subparsers.add_parser("phone", help="Analyze a phone number pattern.")
    phone.add_argument("phone", help="Phone number to inspect.")
    phone.add_argument("--save", action="store_true", help="Save the phone report.")
    phone.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    domain = subparsers.add_parser("domain", help="Inspect domain RDAP, DNS, CT, and headers.")
    domain.add_argument("domain", help="Domain or URL to inspect.")
    domain.add_argument("--save", action="store_true", help="Save the domain report.")
    domain.add_argument("--format", choices=["json", "txt"], default="json", help="Report file format.")

    list_modules = subparsers.add_parser("list-modules", help="List available OSINT modules.")
    list_modules.add_argument("--category", help="Filter by module category.")

    categories = subparsers.add_parser("categories", help="List username platform categories.")
    categories.set_defaults(command="categories")

    doctor = subparsers.add_parser("doctor", help="Show project anatomy, module counts, and data flow.")
    doctor.add_argument("--category", help="Filter module overview by category.")

    dashboard = subparsers.add_parser("dashboard", help="Run the local web dashboard without Docker.")
    dashboard.add_argument("bind", nargs="?", default=DEFAULT_ADDR, help="Bind address, for example 127.0.0.1:8080.")

    return parser


async def run_module_workflow(args: argparse.Namespace, target: str, label: str) -> None:
    profile = classify_target(target)
    render_target_profile(profile)

    engine = AnalyticsEngine(module_timeout=args.timeout, max_concurrent=args.concurrency)
    engine.load_modules(include=_csv(args.include), exclude=_csv(args.exclude), category=args.category)

    loaded = engine.catalog()
    if not loaded:
        console.print("[bold red]No modules loaded for this selection.[/bold red]")
        return

    console.print(
        Panel(
            f"[bold green]{len(loaded)} module(s)[/bold green] ready "
            f"with timeout=[cyan]{args.timeout}s[/cyan], concurrency=[cyan]{args.concurrency}[/cyan]",
            title="[bold]Execution[/bold]",
            border_style="green",
            box=box.ROUNDED,
        )
    )

    results = await engine.execute_all(target, profile=profile)
    graph = build_investigation_graph(profile, results)
    render_run_dashboard(results, graph)
    render_engine_results(results, title="OSINT Module Results")

    if args.save:
        path = ReportGenerator(target=target, results=results, profile=profile, run_label=label).generate(args.format)
        console.print(f"\n[bold green]Saved final report:[/bold green] [cyan]{path}[/cyan]")


async def run_username_scan(args: argparse.Namespace) -> None:
    scanner = UsernameScanner(timeout=args.timeout, workers=args.workers, verbose=args.verbose)
    report = await scanner.scan_username(args.username, category=args.category)
    if args.save:
        scanner.save_report(report, format=args.format)


async def run_email_scan(args: argparse.Namespace) -> None:
    scanner = NexusReconUltimate()
    await scanner.scan_email(args.email, save=args.save, format=args.format)


async def run_phone_scan(args: argparse.Namespace) -> None:
    scanner = NexusReconUltimate()
    await scanner.scan_phone(args.phone, save=args.save, format=args.format)


async def run_domain_scan(args: argparse.Namespace) -> None:
    scanner = NexusReconUltimate()
    await scanner.scan_domain(args.domain, save=args.save, format=args.format)


def list_available_modules(category: Optional[str] = None) -> None:
    engine = AnalyticsEngine()
    engine.load_modules(category=category)
    render_module_catalog(engine.catalog())


def show_project_doctor(category: Optional[str] = None) -> None:
    engine = AnalyticsEngine()
    engine.load_modules(category=category)
    render_project_overview(engine.catalog())
    render_module_catalog(engine.catalog())


def list_categories() -> None:
    table = Table(title="Username Platform Categories", header_style="bold bright_cyan", box=box.SIMPLE_HEAVY)
    table.add_column("Category", style="cyan")
    for category in platform_categories():
        table.add_row(category)
    console.print(table)


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(sys.argv[1:]))

    if not args.no_banner:
        print_banner()

    if args.command == "hunt":
        await run_module_workflow(args, args.target, "hunt")
    elif args.command == "aggregate":
        await run_module_workflow(args, args.target, "aggregate")
    elif args.command == "username":
        await run_username_scan(args)
    elif args.command == "email":
        await run_email_scan(args)
    elif args.command == "phone":
        await run_phone_scan(args)
    elif args.command == "domain":
        await run_domain_scan(args)
    elif args.command == "list-modules":
        list_available_modules(args.category)
    elif args.command == "categories":
        list_categories()
    elif args.command == "doctor":
        show_project_doctor(args.category)
    elif args.command == "dashboard":
        serve_dashboard(args.bind)
    else:
        parser.print_help()


def main() -> None:
    asyncio.run(async_main())


def _normalize_argv(argv: List[str]) -> List[str]:
    commands = {
        "hunt",
        "aggregate",
        "username",
        "email",
        "phone",
        "domain",
        "list-modules",
        "categories",
        "doctor",
        "dashboard",
    }
    if argv and argv[0] not in commands and _looks_like_bind(argv[0]):
        return ["dashboard", *argv]
    return argv


def _looks_like_bind(value: str) -> bool:
    if ":" in value:
        host, port = value.rsplit(":", 1)
        return bool(host) and port.isdigit()
    return value.count(".") == 3


if __name__ == "__main__":
    main()
