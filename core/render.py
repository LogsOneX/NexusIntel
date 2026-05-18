from typing import Dict, Iterable, Mapping

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.targets import TargetProfile


console = Console()


def print_banner() -> None:
    title = Text("NEXUSRECON", style="bold bright_cyan")
    title.append("  /  DATA AGGREGATOR", style="bold white")
    subtitle = "Graph-minded passive OSINT for identity, domain, account, and exposure mapping"
    console.print(
        Panel.fit(
            Group(title, Text(subtitle, style="dim")),
            border_style="bright_blue",
            padding=(1, 3),
            box=box.DOUBLE,
        )
    )


def render_target_profile(profile: TargetProfile) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold cyan")
    table.add_row("Target", profile.original)
    table.add_row("Type", profile.kind)
    table.add_row("Normalized", profile.normalized or "-")
    if profile.email:
        table.add_row("Email", profile.email)
    if profile.domain:
        table.add_row("Domain", profile.domain)
    if profile.username:
        table.add_row("Username", profile.username)
    if profile.phone:
        table.add_row("Phone", profile.phone)
    if profile.ip:
        table.add_row("IP", profile.ip)
    console.print(Panel(table, title="[bold]Target Profile[/bold]", border_style="cyan", box=box.ROUNDED))


def render_module_catalog(modules: Iterable[Mapping[str, object]]) -> None:
    table = Table(title="Available Modules", header_style="bold bright_cyan", box=box.SIMPLE_HEAVY)
    table.add_column("Module", style="bold white")
    table.add_column("Category", style="cyan")
    table.add_column("Targets", style="magenta")
    table.add_column("Description", style="dim")

    for item in modules:
        table.add_row(
            str(item.get("name", "-")),
            str(item.get("category", "-")),
            ", ".join(item.get("target_types", []) or ["any"]),
            str(item.get("description", "")),
        )
    console.print(table)


def render_engine_results(results: Dict[str, dict], title: str = "Module Results") -> None:
    table = Table(title=title, header_style="bold bright_cyan", box=box.SIMPLE_HEAVY)
    table.add_column("Module", style="bold white")
    table.add_column("Status")
    table.add_column("Signal", justify="right")
    table.add_column("Summary", style="dim")

    for name, payload in sorted(results.items()):
        status = payload.get("status", "unknown")
        data = payload.get("data", {})
        if status == "success":
            status_text = "[bold green]OK[/bold green]"
        elif status == "skipped":
            status_text = "[yellow]SKIP[/yellow]"
        else:
            status_text = "[red]ERROR[/red]"

        signal = payload.get("signal_count")
        if signal is None:
            signal = _count_signal(data)
        summary = payload.get("summary") or payload.get("message") or _summarize_data(data)
        table.add_row(name, status_text, str(signal), summary)

    console.print(table)


def render_run_dashboard(results: Dict[str, dict], graph: Mapping[str, object]) -> None:
    ok = sum(1 for payload in results.values() if payload.get("status") == "success")
    skipped = sum(1 for payload in results.values() if payload.get("status") == "skipped")
    errors = sum(1 for payload in results.values() if payload.get("status") == "error")
    signals = sum(int(payload.get("signal_count", 0) or 0) for payload in results.values())
    summary = graph.get("summary", {}) if isinstance(graph, Mapping) else {}

    table = Table.grid(expand=True)
    for _ in range(6):
        table.add_column(ratio=1)
    table.add_row(
        _metric("OK", str(ok), "green"),
        _metric("Skipped", str(skipped), "yellow"),
        _metric("Errors", str(errors), "red"),
        _metric("Signals", str(signals), "cyan"),
        _metric("Nodes", str(summary.get("node_count", 0)), "magenta"),
        _metric("Edges", str(summary.get("edge_count", 0)), "blue"),
    )
    console.print(Panel(table, title="[bold]Run Dashboard[/bold]", border_style="bright_blue", box=box.ROUNDED))


def render_project_overview(modules: Iterable[Mapping[str, object]]) -> None:
    module_list = list(modules)
    categories: Dict[str, int] = {}
    for module in module_list:
        category = str(module.get("category", "general"))
        categories[category] = categories.get(category, 0) + 1

    structure = Table.grid(padding=(0, 2))
    structure.add_column(style="bold cyan")
    structure.add_column(style="white")
    structure.add_row("main.py", "CLI entrypoint, command routing, report save orchestration")
    structure.add_row("core/", "target profiling, dynamic module engine, graph builder, rendering, reporting")
    structure.add_row("modules/", "passive enrichers loaded by metadata and target type")
    structure.add_row("recon/", "standalone scanners and shared platform registry")
    structure.add_row("docs/", "architecture, module catalog, and reference notes")
    structure.add_row("legacy/", "archived historical versions")

    stats = ", ".join(f"{name}={count}" for name, count in sorted(categories.items()))
    body = Group(
        Text(f"Modules: {len(module_list)} ({stats or 'none'})", style="bold white"),
        Text("Data flow: target -> profile -> modules -> normalized results -> graph -> report", style="dim"),
        structure,
    )
    console.print(Panel(body, title="[bold]Project Anatomy[/bold]", border_style="cyan", box=box.ROUNDED))


def render_key_values(title: str, values: Mapping[str, object], border_style: str = "bright_blue") -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="white")
    for key, value in values.items():
        table.add_row(str(key), _stringify(value))
    console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style=border_style, box=box.ROUNDED))


def _metric(label: str, value: str, style: str) -> Panel:
    body = Text()
    body.append(label + "\n", style="dim")
    body.append(value, style=f"bold {style}")
    return Panel(body, border_style=style, box=box.ROUNDED, padding=(0, 1))


def _count_signal(data: object) -> int:
    if isinstance(data, dict):
        for key in ("found", "matches", "present", "signals", "records", "subdomains"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        return len([value for value in data.values() if value not in (None, "", [], {})])
    if isinstance(data, list):
        return len(data)
    return 0


def _summarize_data(data: object) -> str:
    if isinstance(data, dict):
        preferred = []
        for key in ("query", "identity", "domain", "target", "risk_level", "registrar", "provider"):
            if data.get(key):
                preferred.append(f"{key}={data[key]}")
        return ", ".join(preferred[:3]) or f"{len(data)} field(s)"
    if isinstance(data, list):
        return f"{len(data)} item(s)"
    return _stringify(data)


def _stringify(value: object, limit: int = 110) -> str:
    if value is None:
        return "-"
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(str(item) for item in value)
    elif isinstance(value, dict):
        text = ", ".join(f"{k}={v}" for k, v in value.items())
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."
