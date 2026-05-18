import argparse
import asyncio
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.engine import AnalyticsEngine
from core.reporter import ReportGenerator

console = Console()

async def main():
    parser = argparse.ArgumentParser(description="Public Data Aggregator & Analytics Framework Engine")
    parser.add_argument("-t", "--target", required=True, help="Username, domain, or full URL indicator to evaluate")
    args = parser.parse_args()

    console.print("[bold blue]==================================================[/bold blue]")
    console.print("[bold white]   PUBLIC DATA AGGREGATOR ENGINE v1.0.0[/bold white]")
    console.print("[bold blue]==================================================[/bold blue]\n")

    # Module Initialization Phase
    engine = AnalyticsEngine()
    engine.load_modules()
    
    loaded_names = list(engine.loaded_modules.keys())
    console.print(f"[bold green][INFO][/bold green] Successfully parsed and initialized {len(loaded_names)} modules: {loaded_names}\n")

    if not loaded_names:
        console.print("[bold red][FATAL][/bold red] Closing application pipeline. Check target directories.")
        return

    # Concurrent Core Execution Phase
    results = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(description=f"Running modules against objective: [cyan]{args.target}[/cyan]...", total=1)
        results = await engine.execute_all(args.target)
        progress.update(task, completed=1)

    # Dynamic CLI Summary Block output rendering 
    console.print("\n[bold white]=== Aggregated Task Results ===[/bold white]")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Plugin ID", style="dim", width=25)
    table.add_column("Status Assessment", width=15)
    table.add_column("Metrics Tracked")

    for mod_name, output in results.items():
        if output.get("status") == "error":
            table.add_row(mod_name, "[bold red]FAILED[/bold red]", output.get("message"))
        else:
            item_count = len(output.get("data", {}))
            table.add_row(mod_name, "[bold green]SUCCESS[/bold green]", f"{item_count} attributes verified")

    console.print(table)

    # Report Output Pipeline File Operations
    console.print("\n[bold green][INFO][/bold green] Writing analytical files out to file storage layers...")
    reporter = ReportGenerator(target=args.target, results=results)
    
    json_path = reporter.generate_json()
    md_path = reporter.generate_markdown()

    console.print(f" -> [bold cyan]JSON Raw Export Stack Written:[/bold cyan] {json_path}")
    console.print(f" -> [bold cyan]Markdown Summary Document Written:[/bold cyan] {md_path}\n")
    console.print("[bold blue]Processing execution complete.[/bold blue]")

if __name__ == "__main__":
    # Standard Event loop handle interface initialization
    asyncio.run(main())
