import contextlib
from typing import Any

from app.events import emit_event
from app.osint.schema import FindingBatch, entity, relationship
from app.targeting import username_seed
from nexusrecon.main import NexusRecon


class _EventWriter:
    def __init__(self, investigation_id: str, module: str) -> None:
        self.investigation_id = investigation_id
        self.module = module
        self.buffer = ""

    def write(self, data: str) -> int:
        self.buffer += data
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            cleaned = _strip_ansi(line).strip()
            if cleaned:
                emit_event(self.investigation_id, "terminal", cleaned[:500], self.module)
        return len(data)

    def flush(self) -> None:
        cleaned = _strip_ansi(self.buffer).strip()
        if cleaned:
            emit_event(self.investigation_id, "terminal", cleaned[:500], self.module)
        self.buffer = ""


class LegacyNexusReconBridge:
    name = "legacy_nexusrecon_bridge"

    async def run(
        self,
        target: str,
        target_type: str,
        mode: str,
        investigation_id: str | None = None,
    ) -> FindingBatch:
        username = username_seed(target)
        if not username:
            return FindingBatch(self.name, "Legacy NexusRecon skipped: no username seed.")

        timeout = 9 if mode == "standard" else 13 if mode == "active" else 18
        workers = 35 if mode == "standard" else 65 if mode == "active" else 95
        scanner = NexusRecon(timeout=timeout, max_concurrent=workers)

        writer = _EventWriter(investigation_id, self.name) if investigation_id else None
        if writer:
            emit_event(investigation_id, "info", f"Legacy NexusRecon scanning {len(scanner.platforms)} surfaces for {username}.", self.name)
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                report = await scanner.scan_username(username)
            writer.flush()
        else:
            report = await scanner.scan_username(username)

        root = entity("username", username, username, 96, self.name)
        entities = [root]
        relationships = []
        found = []
        errors = []

        for result in report.results:
            item = _dataclass_dict(result)
            if result.status == "found":
                found.append(item)
                service = entity("service", result.platform, result.platform, 82, self.name, {"legacy": True})
                profile = entity(
                    "legacy_profile",
                    result.url,
                    result.platform,
                    78,
                    self.name,
                    {
                        "platform": result.platform,
                        "status_code": result.status_code,
                        "response_time": result.response_time,
                    },
                )
                url = entity("url", result.url, result.url, 78, self.name)
                entities.extend([service, profile, url])
                relationships.append(relationship(root, profile, "legacy_profile_found", "Legacy Profile Found", 78))
                relationships.append(relationship(profile, service, "on_platform", "On Platform", 76))
                relationships.append(relationship(profile, url, "located_at", "Located At", 76))
            elif result.status == "error":
                errors.append(item)

        score = min(100, report.found_count * 4 + max(0, report.total_platforms - report.error_count) // 8)
        signal = entity(
            "signal",
            f"{username}:legacy-nexusrecon-score",
            f"Legacy NexusRecon score {score}/100",
            score,
            self.name,
            {
                "found": report.found_count,
                "errors": report.error_count,
                "total_platforms": report.total_platforms,
                "duration": report.scan_duration,
            },
        )
        entities.append(signal)
        relationships.append(relationship(root, signal, "has_signal", "Has Signal", score))

        return FindingBatch(
            self.name,
            f"Legacy NexusRecon found {report.found_count} profile signal(s) across {report.total_platforms} platforms.",
            entities,
            relationships,
            {
                "username": username,
                "total_platforms": report.total_platforms,
                "found": found,
                "errors": errors[:60],
                "duration": report.scan_duration,
            },
        )


def _dataclass_dict(value: Any) -> dict[str, Any]:
    return {
        key: getattr(value, key)
        for key in ("platform", "url", "status", "status_code", "response_time", "error_message")
        if hasattr(value, key)
    }


def _strip_ansi(value: str) -> str:
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", value)
