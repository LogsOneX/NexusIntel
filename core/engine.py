import asyncio
import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from rich.console import Console

from core.targets import TargetProfile, classify_target


console = Console()
ModuleRun = Callable[[str], Awaitable[Dict[str, Any]]]


@dataclass
class ModuleDescriptor:
    name: str
    display_name: str
    description: str
    category: str = "general"
    target_types: List[str] = field(default_factory=lambda: ["any"])
    tags: List[str] = field(default_factory=list)
    passive: bool = True
    risk: str = "low"

    @classmethod
    def from_metadata(cls, module_name: str, metadata: Optional[dict]) -> "ModuleDescriptor":
        metadata = metadata or {}
        return cls(
            name=module_name,
            display_name=metadata.get("name", module_name.replace("_", " ").title()),
            description=metadata.get("description", "No description provided."),
            category=metadata.get("category", "general"),
            target_types=list(metadata.get("target_types", ["any"])),
            tags=list(metadata.get("tags", [])),
            passive=bool(metadata.get("passive", True)),
            risk=metadata.get("risk", "low"),
        )

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "target_types": self.target_types,
            "tags": self.tags,
            "passive": self.passive,
            "risk": self.risk,
        }


@dataclass
class LoadedModule:
    descriptor: ModuleDescriptor
    run: ModuleRun


class AnalyticsEngine:
    def __init__(
        self,
        modules_dir: str = "modules",
        module_timeout: int = 25,
        max_concurrent: int = 8,
    ):
        self.modules_dir = Path(modules_dir)
        self.module_timeout = module_timeout
        self.max_concurrent = max_concurrent
        self.loaded_modules: Dict[str, LoadedModule] = {}

    def discover_modules(self) -> List[str]:
        if not self.modules_dir.exists():
            return []
        return sorted(
            path.stem
            for path in self.modules_dir.glob("*.py")
            if not path.name.startswith("__")
        )

    def load_modules(
        self,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        category: Optional[str] = None,
    ) -> Dict[str, LoadedModule]:
        include_set = {item.strip() for item in include or [] if item.strip()}
        exclude_set = {item.strip() for item in exclude or [] if item.strip()}
        self.loaded_modules = {}

        for name in self.discover_modules():
            if include_set and name not in include_set:
                continue
            if name in exclude_set:
                continue

            try:
                module = importlib.import_module(f"{self.modules_dir.name}.{name}")
                run_fn = getattr(module, "run", None)
                if not run_fn or not inspect.iscoroutinefunction(run_fn):
                    console.print(f"[yellow][WARN][/yellow] Module '{name}' skipped: missing async run(target).")
                    continue

                descriptor = ModuleDescriptor.from_metadata(name, getattr(module, "metadata", None))
                if category and descriptor.category != category:
                    continue
                self.loaded_modules[name] = LoadedModule(descriptor=descriptor, run=run_fn)
            except Exception as exc:
                console.print(f"[red][ERROR][/red] Failed to load module '{name}': {exc}")

        return self.loaded_modules

    def catalog(self) -> List[dict]:
        if not self.loaded_modules:
            self.load_modules()
        return [loaded.descriptor.as_dict() for loaded in self.loaded_modules.values()]

    async def execute_all(self, target: str, profile: Optional[TargetProfile] = None) -> Dict[str, Any]:
        if not self.loaded_modules:
            self.load_modules()

        profile = profile or classify_target(target)
        if not self.loaded_modules:
            return {}

        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = {
            name: asyncio.create_task(self._execute_one(loaded, target, profile, semaphore))
            for name, loaded in self.loaded_modules.items()
        }

        results: Dict[str, Any] = {}
        for name, task in tasks.items():
            results[name] = await task
        return results

    async def _execute_one(
        self,
        loaded: LoadedModule,
        target: str,
        profile: TargetProfile,
        semaphore: asyncio.Semaphore,
    ) -> dict:
        descriptor = loaded.descriptor
        if not _supports_target(descriptor.target_types, profile.kind):
            return {
                "status": "skipped",
                "message": f"Module expects {', '.join(descriptor.target_types)} target(s), got {profile.kind}.",
                "module": descriptor.as_dict(),
                "signal_count": 0,
            }

        async with semaphore:
            try:
                result = await asyncio.wait_for(loaded.run(target), timeout=self.module_timeout)
                if not isinstance(result, dict):
                    result = {"status": "success", "data": result}
                result.setdefault("status", "success")
                result["module"] = descriptor.as_dict()
                result["signal_count"] = _count_signal(result.get("data"))
                return result
            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "message": f"Module timed out after {self.module_timeout}s.",
                    "module": descriptor.as_dict(),
                    "signal_count": 0,
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "message": str(exc),
                    "module": descriptor.as_dict(),
                    "signal_count": 0,
                }


def _supports_target(target_types: Iterable[str], actual: str) -> bool:
    expected = set(target_types or ["any"])
    return "any" in expected or actual in expected


def _count_signal(data: Any) -> int:
    if isinstance(data, dict):
        for key in ("matches", "found", "present", "signals", "records", "subdomains", "emails_found"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        return len([value for value in data.values() if value not in (None, "", [], {})])
    if isinstance(data, list):
        return len(data)
    return 0
