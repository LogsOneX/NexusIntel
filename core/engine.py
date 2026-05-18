import os
import sys
import importlib
import inspect
import asyncio
from typing import Dict, Any, List
from rich.console import Console

console = Console()

class AnalyticsEngine:
    def __init__(self, modules_dir: str = "modules"):
        self.modules_dir = modules_dir
        self.loaded_modules = {}

    def discover_modules(self) -> List[str]:
        """Discovers valid python files inside the modules directory."""
        if not os.path.exists(self.modules_dir):
            return []
        
        module_files = []
        for file in os.listdir(self.modules_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_files.append(file[:-3])
        return module_files

    def load_modules(self):
        """Dynamically imports discovered modules and extracts their entry points."""
        module_names = self.discover_modules()
        
        # Ensure modules directory is in sys.path
        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
        
        for name in module_names:
            try:
                module_path = f"{self.modules_dir}.{name}"
                mod = importlib.import_module(module_path)
                
                # Check for the mandatory async 'run' function
                if hasattr(mod, "run") and inspect.iscoroutinefunction(mod.run):
                    self.loaded_modules[name] = mod.run
                else:
                    console.print(f"[yellow][WARN][/yellow] Module '{name}' skipped: Missing async 'run' function.")
            except Exception as e:
                console.print(f"[red][ERROR][/red] Failed to load module '{name}': {e}")

    async def execute_all(self, target: str) -> Dict[str, Any]:
        """Runs all loaded modules concurrently against the specified target."""
        if not self.loaded_modules:
            console.print("[yellow][WARN][/yellow] No modules loaded. Execution aborted.")
            return {}

        tasks = {}
        for name, run_fn in self.loaded_modules.items():
            tasks[name] = asyncio.create_task(run_fn(target))

        results = {}
        for name, task in tasks.items():
            try:
                # Await individual task execution safely
                results[name] = await task
            except Exception as e:
                results[name] = {"status": "error", "message": str(e)}
        
        return results
