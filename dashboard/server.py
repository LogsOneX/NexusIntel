import asyncio
import json
import socket
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from core.engine import AnalyticsEngine
from core.flows import list_flows, run_flow_sync
from core.graph import build_investigation_graph
from core.reporter import ReportGenerator
from core.schemas import get_entity_types
from core.targets import classify_target
from core.vault import delete_vault_key, set_vault_key, vault_status


DEFAULT_ADDR = "127.0.0.1:8080"
CASE_PATH = Path(".nexusrecon") / "cases.json"


def parse_bind(value: str | None) -> Tuple[str, int]:
    raw = (value or DEFAULT_ADDR).strip()
    if ":" not in raw:
        return raw, 8080
    host, port = raw.rsplit(":", 1)
    return host or "127.0.0.1", int(port)


def serve_dashboard(bind: str | None = None) -> None:
    host, port = parse_bind(bind)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    actual_host, actual_port = server.server_address[:2]
    print(f"NexusRecon dashboard running at http://{actual_host}:{actual_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def find_available_bind(preferred: str = DEFAULT_ADDR) -> str:
    host, port = parse_bind(preferred)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return f"{host}:{port}"
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return f"{host}:{sock.getsockname()[1]}"


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "NexusReconDashboard/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/dashboard"}:
            self._send_html(DASHBOARD_HTML)
        elif parsed.path == "/api/modules":
            self._send_json(module_catalog())
        elif parsed.path == "/api/types":
            self._send_json({"types": get_entity_types()})
        elif parsed.path == "/api/flows":
            self._send_json({"flows": list_flows()})
        elif parsed.path == "/api/vault":
            self._send_json(vault_status())
        elif parsed.path == "/api/cases":
            self._send_json(case_store())
        elif parsed.path == "/api/health":
            self._send_json({"status": "ok", "service": "nexusrecon-dashboard"})
        else:
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/hunt":
            self._handle_hunt()
        elif parsed.path == "/api/flow/run":
            self._handle_flow_run()
        elif parsed.path == "/api/vault":
            self._handle_vault_update()
        elif parsed.path == "/api/vault/delete":
            self._handle_vault_delete()
        elif parsed.path == "/api/cases":
            self._handle_case_create()
        elif parsed.path == "/api/cases/save":
            self._handle_case_save()
        elif parsed.path == "/api/save":
            self._handle_save()
        else:
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[dashboard] {self.address_string()} - {fmt % args}")

    def _handle_hunt(self) -> None:
        payload = self._read_json()
        target = str(payload.get("target", "")).strip()
        if not target:
            self._send_json({"error": "Target is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        include = _split_csv(payload.get("include"))
        exclude = _split_csv(payload.get("exclude"))
        category = str(payload.get("category") or "").strip() or None
        timeout = _bounded_int(payload.get("timeout"), default=18, minimum=1, maximum=90)
        concurrency = _bounded_int(payload.get("concurrency"), default=6, minimum=1, maximum=20)
        mode = _mode(payload.get("mode"))

        try:
            result = asyncio.run(run_hunt(target, include, exclude, category, timeout, concurrency, mode))
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_flow_run(self) -> None:
        payload = self._read_json()
        flow_id = str(payload.get("flow_id") or "").strip()
        target = str(payload.get("target") or "").strip()
        timeout = _bounded_int(payload.get("timeout"), default=18, minimum=1, maximum=90)
        concurrency = _bounded_int(payload.get("concurrency"), default=6, minimum=1, maximum=20)
        mode = _mode(payload.get("mode"))
        if not flow_id or not target:
            self._send_json({"error": "flow_id and target are required."}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            self._send_json(run_flow_sync(flow_id, target, timeout=timeout, concurrency=concurrency, mode=mode))
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_vault_update(self) -> None:
        payload = self._read_json()
        try:
            item = set_vault_key(str(payload.get("name", "")), str(payload.get("value", "")))
            self._send_json({"status": "saved", "key": item, "vault": vault_status()})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_vault_delete(self) -> None:
        payload = self._read_json()
        name = str(payload.get("name", ""))
        deleted = delete_vault_key(name)
        self._send_json({"status": "deleted" if deleted else "missing", "vault": vault_status()})

    def _handle_case_create(self) -> None:
        payload = self._read_json()
        name = str(payload.get("name") or "Untitled Investigation").strip()
        store = case_store()
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        case = {
            "id": case_id,
            "name": name,
            "created_at": now,
            "updated_at": now,
            "graphs": [],
            "notes": str(payload.get("notes") or ""),
        }
        store.setdefault("cases", []).append(case)
        _save_cases(store)
        self._send_json({"status": "created", "case": case, "store": store})

    def _handle_case_save(self) -> None:
        payload = self._read_json()
        case_id = str(payload.get("case_id") or "").strip()
        target = str(payload.get("target") or "").strip()
        graph = payload.get("graph")
        results = payload.get("results")
        if not case_id or not isinstance(graph, dict):
            self._send_json({"error": "case_id and graph are required."}, status=HTTPStatus.BAD_REQUEST)
            return
        store = case_store()
        case = next((item for item in store.get("cases", []) if item.get("id") == case_id), None)
        if not case:
            self._send_json({"error": "Case not found."}, status=HTTPStatus.NOT_FOUND)
            return
        now = datetime.now(timezone.utc).isoformat()
        case.setdefault("graphs", []).append(
            {
                "id": str(uuid.uuid4()),
                "target": target,
                "created_at": now,
                "summary": graph.get("summary", {}),
                "graph": graph,
                "results": results,
            }
        )
        case["updated_at"] = now
        _save_cases(store)
        self._send_json({"status": "saved", "case": case, "store": store})

    def _handle_save(self) -> None:
        payload = self._read_json()
        target = str(payload.get("target", "")).strip()
        results = payload.get("results")
        output_format = str(payload.get("format") or "json")
        if output_format not in {"json", "md", "html", "graph"}:
            self._send_json({"error": "Unsupported format."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not target or not isinstance(results, dict):
            self._send_json({"error": "Target and results are required."}, status=HTTPStatus.BAD_REQUEST)
            return
        profile = classify_target(target)
        path = ReportGenerator(target=target, results=results, profile=profile, run_label="dashboard").generate(output_format)
        self._send_json({"status": "saved", "path": path})

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("content-length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, markup: str) -> None:
        body = markup.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


async def run_hunt(
    target: str,
    include: list[str] | None,
    exclude: list[str] | None,
    category: str | None,
    timeout: int,
    concurrency: int,
    mode: str,
) -> dict:
    profile = classify_target(target)
    engine = AnalyticsEngine(module_timeout=timeout, max_concurrent=concurrency, mode=mode)
    engine.load_modules(include=include, exclude=exclude, category=category)
    catalog = engine.catalog()
    results = await engine.execute_all(target, profile=profile)
    graph = build_investigation_graph(profile, results)
    return {
        "target_profile": profile.__dict__,
        "catalog": catalog,
        "results": results,
        "graph": graph,
        "dashboard": _dashboard_summary(results, graph),
        "mode": mode,
    }


def module_catalog() -> dict:
    engine = AnalyticsEngine()
    engine.load_modules()
    modules = engine.catalog()
    categories: Dict[str, int] = {}
    target_types: Dict[str, int] = {}
    for module in modules:
        category = str(module.get("category", "general"))
        categories[category] = categories.get(category, 0) + 1
        for target_type in module.get("target_types", []) or ["any"]:
            target_types[target_type] = target_types.get(target_type, 0) + 1
    return {"modules": modules, "categories": categories, "target_types": target_types}


def case_store() -> dict:
    if not CASE_PATH.exists():
        return {"cases": []}
    try:
        with CASE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {"cases": []}
    except (OSError, json.JSONDecodeError):
        return {"cases": []}


def _save_cases(payload: dict) -> None:
    CASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CASE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _dashboard_summary(results: dict, graph: dict) -> dict:
    ok = sum(1 for payload in results.values() if payload.get("status") == "success")
    skipped = sum(1 for payload in results.values() if payload.get("status") == "skipped")
    errors = sum(1 for payload in results.values() if payload.get("status") == "error")
    signals = sum(int(payload.get("signal_count", 0) or 0) for payload in results.values())
    return {
        "ok": ok,
        "skipped": skipped,
        "errors": errors,
        "signals": signals,
        "nodes": graph.get("summary", {}).get("node_count", 0),
        "edges": graph.get("summary", {}).get("edge_count", 0),
    }


def _split_csv(value: Any) -> list[str] | None:
    if not value:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [item.strip() for item in str(value).split(",")]
    return [item for item in items if item]


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _mode(value: Any) -> str:
    mode = str(value or "standard").strip().lower()
    return mode if mode in {"standard", "active", "aggressive"} else "standard"


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NexusRecon Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0d10;
      --surface: #14181f;
      --surface-2: #10141b;
      --line: #2d3746;
      --text: #edf2f8;
      --muted: #9aa7b8;
      --cyan: #56d6ff;
      --green: #7be39d;
      --amber: #f1c36c;
      --red: #ff7a7a;
      --violet: #b78cff;
      --steel: #7ca6d8;
      --shadow: rgba(0, 0, 0, 0.28);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    button, input, select {
      font: inherit;
      letter-spacing: 0;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #11151b;
      padding: 18px;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
    }
    main {
      min-width: 0;
      padding: 18px;
      display: grid;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 18px;
    }
    .mark {
      width: 34px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: var(--cyan);
      background: var(--surface-2);
      font-weight: 800;
    }
    .brand h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.1;
    }
    .brand p {
      margin: 2px 0 0;
      color: var(--muted);
      font-size: 12px;
    }
    .form {
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }
    label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    input, select {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      color: var(--text);
      padding: 9px 10px;
      outline: none;
    }
    input:focus, select:focus { border-color: var(--cyan); }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      margin-top: 6px;
    }
    button {
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      color: var(--text);
      cursor: pointer;
      padding: 8px 12px;
    }
    button.primary {
      border-color: #286f83;
      background: #12323c;
      color: var(--cyan);
      font-weight: 700;
    }
    button:hover { border-color: var(--cyan); }
    button:disabled { opacity: 0.55; cursor: wait; }
    .side-section {
      border-top: 1px solid var(--line);
      padding-top: 14px;
      margin-top: 14px;
    }
    .module-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .module-pill, .compact-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px;
      background: var(--surface-2);
    }
    .module-pill strong {
      display: block;
      font-size: 13px;
    }
    .module-pill span {
      color: var(--muted);
      font-size: 12px;
    }
    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 16px 32px var(--shadow);
    }
    .topbar h2 {
      margin: 0;
      font-size: 20px;
    }
    .topbar p {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: var(--surface-2);
      border-radius: 999px;
      padding: 8px 12px;
      color: var(--muted);
      white-space: nowrap;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 99px;
      background: var(--green);
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }
    .viewbar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      padding: 8px;
      box-shadow: 0 16px 32px var(--shadow);
    }
    .viewbar button {
      min-height: 34px;
      border-radius: 7px;
      color: var(--muted);
    }
    .viewbar button.active {
      border-color: #286f83;
      background: #12323c;
      color: var(--cyan);
    }
    .view-panel {
      display: none;
      gap: 16px;
    }
    .view-panel.active {
      display: grid;
    }
    .metric, .panel {
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      box-shadow: 0 16px 32px var(--shadow);
    }
    .metric {
      padding: 14px;
      min-height: 82px;
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    .metric strong {
      display: block;
      margin-top: 8px;
      font-size: 26px;
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: minmax(320px, 0.42fr) minmax(0, 0.58fr);
      gap: 16px;
      align-items: start;
    }
    .graph-panel {
      min-height: 760px;
    }
    .panel {
      min-width: 0;
      overflow: hidden;
    }
    .panel header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      padding: 13px 14px;
    }
    .panel h3 {
      margin: 0;
      font-size: 15px;
    }
    .panel-body {
      padding: 14px;
    }
    .graph-wrap {
      min-height: 680px;
      position: relative;
      background: #0e1218;
    }
    .graph-tools {
      display: grid;
      grid-template-columns: minmax(180px, 1.2fr) minmax(140px, 180px) minmax(140px, 180px) minmax(160px, 1fr) minmax(140px, 180px) auto auto auto;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
      align-items: center;
    }
    .graph-tools input, .graph-tools select {
      min-height: 34px;
      padding: 7px 9px;
    }
    .graph-count {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    canvas {
      width: 100%;
      height: 680px;
      display: block;
    }
    .legend {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
    }
    .legend span {
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .swatch {
      width: 10px;
      height: 10px;
      border-radius: 99px;
      background: var(--cyan);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px;
      vertical-align: top;
      text-align: left;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }
    tr:last-child td { border-bottom: 0; }
    .badge {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .ok { color: var(--green); }
    .skip { color: var(--amber); }
    .error { color: var(--red); }
    .tabs {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .tabs button {
      min-height: 32px;
      font-size: 12px;
      padding: 6px 9px;
    }
    .tabs button.active {
      border-color: var(--cyan);
      color: var(--cyan);
    }
    pre {
      margin: 0;
      max-height: 420px;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      color: #d7e0ec;
    }
    .empty {
      min-height: 200px;
      display: grid;
      place-items: center;
      color: var(--muted);
      text-align: center;
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 20px;
    }
    .save-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
    }
    .mini-grid {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .flow-cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 12px 0;
    }
    .flow-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      padding: 11px;
      cursor: pointer;
    }
    .flow-card.active {
      border-color: var(--cyan);
      color: var(--cyan);
    }
    .flow-card strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .timeline {
      display: grid;
      gap: 10px;
    }
    .timeline-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      padding: 10px;
    }
    .timeline-item strong {
      display: block;
      font-size: 13px;
      margin-bottom: 4px;
    }
    .tool-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      align-items: start;
    }
    .single-column {
      width: 100%;
      max-width: 1180px;
      margin: 0 auto;
    }
    .small-muted {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .inspector-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }
    .inspector-title strong {
      font-size: 15px;
    }
    .node-dot {
      width: 12px;
      height: 12px;
      border-radius: 99px;
      background: var(--cyan);
      display: inline-block;
      flex: 0 0 auto;
    }
    .scrollbox {
      max-height: 300px;
      overflow: auto;
    }
    @media (max-width: 1080px) {
      .shell { grid-template-columns: 1fr; }
      aside { position: relative; height: auto; }
      .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .workspace { grid-template-columns: 1fr; }
      .detail-grid { grid-template-columns: 1fr; }
      .tool-grid { grid-template-columns: 1fr; }
      .flow-cards { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      main { padding: 12px; }
      aside { padding: 12px; }
      .topbar, .actions, .save-row { grid-template-columns: 1fr; }
      .graph-tools { grid-template-columns: 1fr; }
      .row { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      canvas { height: 520px; }
      .graph-wrap { min-height: 520px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">
        <div class="mark">NX</div>
        <div>
          <h1>NexusRecon</h1>
          <p>Local OSINT Dashboard</p>
        </div>
      </div>
      <form class="form" id="huntForm">
        <div>
          <label for="target">Target</label>
          <input id="target" name="target" placeholder="username, email, domain, URL, phone" autocomplete="off" required>
        </div>
        <div>
          <label for="mode">Operation Mode</label>
          <select id="mode" name="mode">
            <option value="standard">Standard</option>
            <option value="active">Active</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>
        <div class="row">
          <div>
            <label for="timeout">Timeout</label>
            <input id="timeout" name="timeout" type="number" min="1" max="90" value="18">
          </div>
          <div>
            <label for="concurrency">Concurrency</label>
            <input id="concurrency" name="concurrency" type="number" min="1" max="20" value="6">
          </div>
        </div>
        <div>
          <label for="saveFormat">Save</label>
          <select id="saveFormat">
            <option value="json">JSON</option>
            <option value="md">Markdown</option>
            <option value="html">HTML</option>
            <option value="graph">Graph JSON</option>
          </select>
        </div>
        <div class="actions">
          <button class="primary" id="runBtn" type="submit">Run Hunt</button>
          <button id="saveBtn" type="button" disabled title="Save the latest dashboard result">Save</button>
        </div>
      </form>
      <div class="side-section">
        <label>Case / Sketch</label>
        <div class="mini-grid">
          <input id="caseName" placeholder="New case name">
          <button id="createCaseBtn" type="button">Create Case</button>
          <select id="caseSelect"><option value="">No case selected</option></select>
          <button id="saveCaseBtn" type="button" disabled>Save Graph to Case</button>
        </div>
      </div>
    </aside>
    <main>
      <section class="topbar">
        <div>
          <h2 id="headline">Investigation Workspace</h2>
          <p id="subline">Ready for local passive reconnaissance.</p>
        </div>
        <div class="status"><span class="dot" id="statusDot"></span><span id="statusText">Idle</span></div>
      </section>
      <section class="metrics">
        <div class="metric"><span>OK</span><strong id="mOk">0</strong></div>
        <div class="metric"><span>Skipped</span><strong id="mSkipped">0</strong></div>
        <div class="metric"><span>Errors</span><strong id="mErrors">0</strong></div>
        <div class="metric"><span>Signals</span><strong id="mSignals">0</strong></div>
        <div class="metric"><span>Nodes</span><strong id="mNodes">0</strong></div>
        <div class="metric"><span>Edges</span><strong id="mEdges">0</strong></div>
      </section>
      <nav class="viewbar" id="viewbar" aria-label="Workspace views">
        <button type="button" class="active" data-view-btn="overview">Overview</button>
        <button type="button" data-view-btn="flow">Flow</button>
        <button type="button" data-view-btn="timeline">Timeline</button>
        <button type="button" data-view-btn="vault">Vault</button>
        <button type="button" data-view-btn="types">Types</button>
        <button type="button" data-view-btn="raw">Raw</button>
      </nav>
      <div class="view-panel active" data-view="overview">
        <div class="workspace">
          <section class="panel graph-panel">
            <header>
              <h3>Investigation Graph</h3>
              <div class="legend" id="legend"></div>
            </header>
            <div class="graph-tools">
              <input id="graphSearch" placeholder="Search graph nodes">
              <select id="graphFilter"><option value="">All entity types</option></select>
              <select id="addEntityType"><option value="signal">Signal</option></select>
              <input id="addEntityLabel" placeholder="Add entity label">
              <select id="addEntityRelation">
                <option value="manual_link">manual_link</option>
                <option value="suspected_link">suspected_link</option>
                <option value="owns">owns</option>
                <option value="uses">uses</option>
                <option value="mentions">mentions</option>
              </select>
              <button id="addEntityBtn" type="button">Add</button>
              <button id="removeEntityBtn" type="button">Remove</button>
              <button id="resetGraphBtn" type="button">Reset</button>
              <span class="graph-count" id="graphCount">0 nodes</span>
            </div>
            <div class="graph-wrap">
              <canvas id="graphCanvas" width="960" height="520"></canvas>
            </div>
          </section>
          <div class="detail-grid">
          <section class="panel">
            <header>
              <h3>Entity Inspector</h3>
            </header>
            <div class="panel-body" id="profileView">
              <div class="empty">No target loaded.</div>
            </div>
          </section>
          <section class="panel">
            <header>
              <h3>Intelligence Output</h3>
              <div class="tabs" id="tabs"></div>
            </header>
            <div class="panel-body" id="resultsView">
              <div class="empty">Run an operation to populate results.</div>
            </div>
          </section>
          </div>
        </div>
      </div>
      <div class="view-panel single-column" data-view="flow">
        <section class="panel">
          <header><h3>Flow Studio</h3></header>
          <div class="panel-body">
            <div class="mini-grid">
              <select id="flowSelect"></select>
              <button id="runFlowBtn" type="button">Run Flow</button>
            </div>
            <div class="small-muted" id="flowDescription">Load a flow to see the chain.</div>
            <div class="flow-cards" id="flowCards"></div>
            <div class="scrollbox" id="flowLog"><div class="empty">No flow execution yet.</div></div>
          </div>
        </section>
      </div>
      <div class="view-panel single-column" data-view="timeline">
        <section class="panel">
          <header><h3>Timeline</h3></header>
          <div class="panel-body">
            <div class="timeline" id="timelineView"><div class="empty">No timeline yet.</div></div>
          </div>
        </section>
      </div>
      <div class="view-panel single-column" data-view="vault">
        <section class="panel">
          <header><h3>Vault</h3></header>
          <div class="panel-body">
            <div class="mini-grid">
              <input id="vaultName" placeholder="WHOXY_API_KEY">
              <input id="vaultValue" placeholder="secret value" type="password">
              <button id="saveVaultBtn" type="button">Save Key</button>
            </div>
            <div class="scrollbox" id="vaultList"><div class="empty">No vault keys loaded.</div></div>
          </div>
        </section>
      </div>
      <div class="view-panel single-column" data-view="types">
        <section class="panel">
          <header><h3>Entity Types</h3></header>
          <div class="panel-body scrollbox" id="typeList">
            <div class="empty">No type registry loaded.</div>
          </div>
        </section>
      </div>
      <div class="view-panel" data-view="raw">
        <section class="panel">
          <header>
            <h3>Raw Output</h3>
            <div class="save-row">
              <span id="saveStatus"></span>
            </div>
          </header>
          <div class="panel-body"><pre id="rawOutput">{}</pre></div>
        </section>
      </div>
    </main>
  </div>
  <script>
    const state = {
      latest: null, activeModule: 'all', activeView: 'overview', modules: [], flows: [], cases: [],
      types: [], selectedCase: '', selectedNodeId: '', graphPositions: new Map()
    };
    const colors = {
      target: '#56d6ff', username: '#56d6ff', email: '#56d6ff', domain: '#7be39d',
      url: '#7ca6d8', hostname: '#7be39d', ip: '#f1c36c', module: '#b78cff',
      service: '#ffb86c', profile: '#ffb86c', signal: '#f1c36c', risk: '#ff7a7a',
      dns_record: '#7ca6d8', phone: '#56d6ff', application: '#f6a960', flow: '#b78cff',
      organization: '#9dd6a5', asn: '#c2a3ff', cidr: '#c2a3ff', tracker: '#e78ac3',
      task: '#8fd3ff', hypothesis: '#f0d98c'
    };
    const brandMarks = {
      github: 'GH', gitlab: 'GL', npm: 'np', pypi: 'Py', reddit: 'rd', youtube: 'YT',
      twitter: 'X', instagram: 'IG', linkedin: 'in', medium: 'Md', docker: 'Dk',
      google: 'G', microsoft: 'MS', cloudflare: 'CF', apple: 'AP', android: 'AN'
    };

    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'content-type': 'application/json' },
        ...options
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      return data;
    }

    function setStatus(text, tone = 'idle') {
      $('statusText').textContent = text;
      $('statusDot').style.background = tone === 'error' ? 'var(--red)' : tone === 'busy' ? 'var(--amber)' : 'var(--green)';
    }

    function metric(id, value) { $(id).textContent = Number(value || 0).toLocaleString(); }

    function setView(view) {
      state.activeView = view;
      document.querySelectorAll('[data-view]').forEach((panel) => {
        panel.classList.toggle('active', panel.dataset.view === view);
      });
      document.querySelectorAll('[data-view-btn]').forEach((button) => {
        button.classList.toggle('active', button.dataset.viewBtn === view);
      });
      if (view === 'overview' && state.latest) requestAnimationFrame(() => renderGraph(state.latest.graph));
    }

    function renderModules(data) {
      state.modules = data.modules || [];
    }

    function renderFlows(data) {
      state.flows = data.flows || [];
      $('flowSelect').innerHTML = state.flows.map((flow) => `
        <option value="${escapeHtml(flow.id)}">${escapeHtml(flow.name)}</option>
      `).join('');
      renderFlowCards();
      renderFlowDescription();
    }

    function renderFlowDescription() {
      const flow = state.flows.find((item) => item.id === $('flowSelect').value);
      if (!flow) {
        $('flowDescription').textContent = 'No flow selected.';
        return;
      }
      const steps = (flow.steps || []).map((step, index) => `${index + 1}. ${step.name}`).join(' -> ');
      $('flowDescription').textContent = `${flow.description} | ${steps}`;
      renderFlowCards();
    }

    function renderFlowCards() {
      if (!$('flowCards')) return;
      $('flowCards').innerHTML = state.flows.map((flow) => {
        const active = flow.id === $('flowSelect').value ? 'active' : '';
        const steps = (flow.steps || []).length;
        return `<div class="flow-card ${active}" data-flow-card="${escapeHtml(flow.id)}">
          <strong>${escapeHtml(flow.name)}</strong>
          <span class="small-muted">${escapeHtml(flow.id)} / ${steps} steps</span>
        </div>`;
      }).join('');
      $('flowCards').querySelectorAll('[data-flow-card]').forEach((card) => {
        card.addEventListener('click', () => {
          $('flowSelect').value = card.dataset.flowCard;
          renderFlowDescription();
        });
      });
    }

    function renderVault(data) {
      const keys = data.keys || [];
      if (!keys.length) {
        $('vaultList').innerHTML = '<div class="empty">No vault keys yet.</div>';
        return;
      }
      $('vaultList').innerHTML = `<table><tbody>${keys.map((key) => `
        <tr>
          <td>${escapeHtml(key.name)}<br><span class="small-muted">${escapeHtml(key.source || '')}</span></td>
          <td>${escapeHtml(key.masked || '')}</td>
        </tr>
      `).join('')}</tbody></table>`;
    }

    function renderTypes(data) {
      const types = data.types || [];
      state.types = types;
      $('addEntityType').innerHTML = types.map((type) => `
        <option value="${escapeHtml(type.name)}">${escapeHtml(type.label)}</option>
      `).join('');
      $('typeList').innerHTML = `<table><tbody>${types.map((type) => `
        <tr>
          <td><span class="swatch" style="display:inline-block;background:${escapeHtml(type.color)}"></span> ${escapeHtml(type.label)}</td>
          <td>${escapeHtml(type.shape)}<br><span class="small-muted">${escapeHtml((type.fields || []).join(', '))}</span></td>
        </tr>
      `).join('')}</tbody></table>`;
    }

    function renderCases(data) {
      state.cases = data.cases || [];
      $('caseSelect').innerHTML = '<option value="">No case selected</option>' + state.cases.map((item) => `
        <option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} (${(item.graphs || []).length})</option>
      `).join('');
      if (state.selectedCase) $('caseSelect').value = state.selectedCase;
      $('saveCaseBtn').disabled = !state.latest || !$('caseSelect').value;
    }

    function renderProfile(profile) {
      const rows = Object.entries(profile || {}).filter(([, v]) => v !== null && v !== '' && v !== undefined);
      $('profileView').innerHTML = `
        <div class="inspector-title"><span class="node-dot"></span><strong>Target Profile</strong></div>
        <table><tbody>${rows.map(([k, v]) => `
        <tr><th>${escapeHtml(k)}</th><td>${escapeHtml(String(v))}</td></tr>
      `).join('')}</tbody></table>`;
    }

    function renderInspector(node) {
      if (!node) {
        renderProfile(state.latest ? state.latest.target_profile : {});
        return;
      }
      const props = { id: node.id, type: node.type, label: node.label, ...(node.properties || {}) };
      const rows = Object.entries(props).filter(([, v]) => v !== null && v !== '' && v !== undefined);
      $('profileView').innerHTML = `
        <div class="inspector-title">
          <span class="node-dot" style="background:${colors[node.type] || '#9aa7b8'}"></span>
          <strong>${escapeHtml(node.nodeType || node.type)}</strong>
        </div>
        <table><tbody>${rows.map(([k, v]) => `
          <tr><th>${escapeHtml(k)}</th><td>${escapeHtml(formatValue(v))}</td></tr>
        `).join('')}</tbody></table>`;
    }

    function formatValue(value) {
      if (Array.isArray(value)) return value.join(', ');
      if (value && typeof value === 'object') return JSON.stringify(value);
      return String(value);
    }

    function renderResults(results) {
      const names = Object.keys(results || {}).sort();
      $('tabs').innerHTML = ['all', ...names].map((name) => `
        <button type="button" class="${state.activeModule === name ? 'active' : ''}" data-tab="${escapeHtml(name)}">${escapeHtml(name)}</button>
      `).join('');
      $('tabs').querySelectorAll('button').forEach((button) => {
        button.addEventListener('click', () => {
          state.activeModule = button.dataset.tab;
          renderResults(state.latest.results);
        });
      });

      if (!names.length) {
        $('resultsView').innerHTML = '<div class="empty">No module output.</div>';
        return;
      }
      if (state.activeModule !== 'all' && results[state.activeModule]) {
        $('resultsView').innerHTML = `<pre>${escapeHtml(JSON.stringify(results[state.activeModule], null, 2))}</pre>`;
        return;
      }
      $('resultsView').innerHTML = `<table>
        <thead><tr><th>Module</th><th>Status</th><th>Signals</th><th>Summary</th></tr></thead>
        <tbody>${names.map((name) => {
          const r = results[name] || {};
          const statusClass = r.status === 'success' ? 'ok' : r.status === 'skipped' ? 'skip' : 'error';
          return `<tr>
            <td>${escapeHtml(name)}</td>
            <td><span class="badge ${statusClass}">${escapeHtml(r.status || 'unknown')}</span></td>
            <td>${escapeHtml(String(r.signal_count || 0))}</td>
            <td>${escapeHtml(r.summary || r.message || '')}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>`;
    }

    function renderLegend(graph) {
      const types = [...new Set((graph.nodes || []).map((n) => n.type))].sort();
      const selected = $('graphFilter').value;
      const options = '<option value="">All entity types</option>' + types.map((type) => `
        <option value="${escapeHtml(type)}">${escapeHtml(type)}</option>
      `).join('');
      if ($('graphFilter').innerHTML !== options) {
        $('graphFilter').innerHTML = options;
        $('graphFilter').value = selected;
      }
      $('legend').innerHTML = types.slice(0, 12).map((type) => `
        <span><i class="swatch" style="background:${colors[type] || '#9aa7b8'}"></i>${escapeHtml(type)}</span>
      `).join('');
    }

    function renderGraph(graph) {
      renderLegend(graph || { nodes: [] });
      const canvas = $('graphCanvas');
      const ctx = canvas.getContext('2d');
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(640, Math.floor(rect.width * ratio));
      canvas.height = Math.max(420, Math.floor(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const width = canvas.width / ratio;
      const height = canvas.height / ratio;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#0e1218';
      ctx.fillRect(0, 0, width, height);

      const filter = $('graphFilter').value;
      const query = $('graphSearch').value.trim().toLowerCase();
      const allNodes = graph.nodes || [];
      const matched = allNodes.filter((node) => {
        const byType = !filter || node.type === filter;
        const haystack = `${node.label || ''} ${node.type || ''} ${JSON.stringify(node.properties || {})}`.toLowerCase();
        const byQuery = !query || haystack.includes(query);
        return byType && byQuery;
      });
      const nodes = matched.slice(0, 180);
      const allowed = new Set(nodes.map((node) => node.id));
      const edges = (graph.edges || []).filter((edge) => allowed.has(edge.source) && allowed.has(edge.target)).slice(0, 320);
      $('graphCount').textContent = `${nodes.length}/${allNodes.length} nodes`;
      state.graphPositions = new Map();
      if (!nodes.length) {
        ctx.fillStyle = '#9aa7b8';
        ctx.font = '14px system-ui';
        ctx.fillText((graph.nodes || []).length ? 'No nodes match the current filter.' : 'No graph data yet.', 24, 32);
        return;
      }

      const byId = new Map(nodes.map((node, index) => [node.id, { ...node, index }]));
      const center = nodes.find((n) => n.id === state.selectedNodeId) || nodes.find((n) => !['module'].includes(n.type)) || nodes[0];
      const centerId = center.id;
      const cx = width / 2;
      const cy = height / 2;
      const ring = Math.max(170, Math.min(width, height) * 0.32);
      const nonCenter = nodes.filter((n) => n.id !== centerId);
      nonCenter.forEach((node, i) => {
        const typeOffset = node.type === 'module' ? 0.6 : node.type === 'risk' ? 1.1 : 0;
        const angle = ((i / Math.max(1, nonCenter.length)) * Math.PI * 2) + typeOffset;
        const radius = ring + ((i % 5) * 46);
        node.x = Math.min(width - 50, Math.max(50, cx + Math.cos(angle) * radius));
        node.y = Math.min(height - 50, Math.max(50, cy + Math.sin(angle) * radius));
        byId.set(node.id, node);
      });
      center.x = cx;
      center.y = cy;
      byId.set(center.id, center);

      for (let step = 0; step < 80; step++) {
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j];
            let dx = a.x - b.x, dy = a.y - b.y;
            let distance = Math.max(24, Math.hypot(dx, dy));
            const force = 820 / (distance * distance);
            dx /= distance; dy /= distance;
            if (a.id !== centerId) { a.x += dx * force; a.y += dy * force; }
            if (b.id !== centerId) { b.x -= dx * force; b.y -= dy * force; }
          }
        }
        edges.forEach((edge) => {
          const source = byId.get(edge.source);
          const target = byId.get(edge.target);
          if (!source || !target) return;
          const desired = source.type === 'module' || target.type === 'module' ? 190 : 125;
          let dx = target.x - source.x, dy = target.y - source.y;
          let distance = Math.max(1, Math.hypot(dx, dy));
          const pull = (distance - desired) * 0.012;
          dx /= distance; dy /= distance;
          if (source.id !== centerId) { source.x += dx * pull; source.y += dy * pull; }
          if (target.id !== centerId) { target.x -= dx * pull; target.y -= dy * pull; }
        });
        nodes.forEach((node) => {
          node.x = Math.min(width - 44, Math.max(44, node.x));
          node.y = Math.min(height - 44, Math.max(44, node.y));
        });
      }

      ctx.lineWidth = 1;
      edges.forEach((edge) => {
        const source = byId.get(edge.source);
        const target = byId.get(edge.target);
        if (!source || !target) return;
        ctx.strokeStyle = 'rgba(154, 167, 184, 0.22)';
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      });

      nodes.forEach((node) => {
        const selected = node.id === state.selectedNodeId;
        const radius = selected ? 21 : node.id === centerId ? 18 : node.type === 'module' ? 13 : 11;
        ctx.beginPath();
        ctx.fillStyle = colors[node.type] || '#9aa7b8';
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#081018';
        ctx.font = '700 9px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(brandForNode(node), node.x, node.y);
        ctx.strokeStyle = selected ? '#edf2f8' : '#0b0d10';
        ctx.lineWidth = selected ? 4 : 3;
        ctx.stroke();
        ctx.fillStyle = '#edf2f8';
        ctx.font = node.id === centerId ? '700 12px system-ui' : '11px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        const label = String(node.label || '').slice(0, 24);
        ctx.fillText(label, node.x, node.y + radius + 14);
        state.graphPositions.set(node.id, { ...node, radius });
      });
    }

    function brandForNode(node) {
      const label = `${node.label || ''} ${JSON.stringify(node.properties || {})}`.toLowerCase();
      for (const [key, value] of Object.entries(brandMarks)) {
        if (label.includes(key)) return value;
      }
      if (node.type === 'domain') return 'DM';
      if (node.type === 'email') return '@';
      if (node.type === 'url') return 'UR';
      if (node.type === 'ip') return 'IP';
      if (node.type === 'flow') return 'FL';
      if (node.type === 'task') return 'TK';
      return String(node.type || '?').slice(0, 2).toUpperCase();
    }

    function selectGraphNode(event) {
      if (!state.latest) return;
      const canvas = $('graphCanvas');
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      let selected = null;
      let best = 9999;
      state.graphPositions.forEach((node) => {
        const distance = Math.hypot(node.x - x, node.y - y);
        if (distance < Math.max(24, node.radius + 8) && distance < best) {
          selected = node;
          best = distance;
        }
      });
      if (!selected) return;
      state.selectedNodeId = selected.id;
      renderInspector(selected);
      renderGraph(state.latest.graph);
    }

    function addManualEntity() {
      if (!state.latest) return;
      const label = $('addEntityLabel').value.trim();
      const type = $('addEntityType').value || 'signal';
      if (!label) return;
      const style = state.types.find((item) => item.name === type) || {};
      const id = `manual:${type}:${Date.now().toString(36)}:${Math.random().toString(36).slice(2, 8)}`;
      const node = {
        id, type, label,
        properties: { manual: true, source_module: 'operator', label },
        nodeType: style.label || type,
        nodeLabel: label,
        nodeProperties: { manual: true, source_module: 'operator', label },
        nodeSize: 14,
        nodeColor: style.color || colors[type] || '#9aa7b8',
        nodeIcon: style.icon || 'Circle',
        nodeShape: style.shape || 'circle',
        nodeMetadata: { created_at: new Date().toISOString(), schema: style.name || type, source_module: 'operator' },
        val: 2
      };
      state.latest.graph.nodes.push(node);
      const source = state.selectedNodeId || ((state.latest.graph.nodes || [])[0] || {}).id;
      if (source && source !== id) {
        state.latest.graph.edges.push({
          id: `manual-edge:${Date.now().toString(36)}:${Math.random().toString(36).slice(2, 8)}`,
          source,
          target: id,
          relationship: $('addEntityRelation').value || 'manual_link',
          label: ($('addEntityRelation').value || 'manual_link').toUpperCase(),
          type: $('addEntityRelation').value || 'manual_link',
          weight: 1,
          confidence_level: 'operator',
          date: new Date().toISOString(),
          module: 'operator'
        });
      }
      state.selectedNodeId = id;
      $('addEntityLabel').value = '';
      renderInspector(node);
      refreshGraphState();
    }

    function removeSelectedEntity() {
      if (!state.latest || !state.selectedNodeId) return;
      const id = state.selectedNodeId;
      state.latest.graph.nodes = (state.latest.graph.nodes || []).filter((node) => node.id !== id);
      state.latest.graph.edges = (state.latest.graph.edges || []).filter((edge) => edge.source !== id && edge.target !== id);
      state.selectedNodeId = '';
      renderProfile(state.latest.target_profile);
      refreshGraphState();
    }

    function refreshGraphState() {
      if (!state.latest) return;
      recalcGraphSummary(state.latest.graph);
      metric('mNodes', state.latest.graph.summary.node_count);
      metric('mEdges', state.latest.graph.summary.edge_count);
      metric('mSignals', Math.max(Number($('mSignals').textContent.replaceAll(',', '')) || 0, state.latest.graph.summary.node_count));
      renderGraph(state.latest.graph);
      renderTimeline(state.latest);
      $('rawOutput').textContent = JSON.stringify(state.latest, null, 2);
    }

    function recalcGraphSummary(graph) {
      const nodeTypes = {};
      (graph.nodes || []).forEach((node) => {
        nodeTypes[node.type] = (nodeTypes[node.type] || 0) + 1;
      });
      graph.summary = {
        node_count: (graph.nodes || []).length,
        edge_count: (graph.edges || []).length,
        node_types: nodeTypes
      };
    }

    function renderAll(data) {
      state.latest = data;
      state.activeModule = 'all';
      state.selectedNodeId = '';
      $('headline').textContent = data.target_profile.normalized || data.target_profile.original || 'Investigation Workspace';
      $('subline').textContent = `${data.target_profile.kind} / ${Object.keys(data.results || {}).length} modules / ${data.mode || 'standard'} mode`;
      metric('mOk', data.dashboard.ok);
      metric('mSkipped', data.dashboard.skipped);
      metric('mErrors', data.dashboard.errors);
      metric('mSignals', data.dashboard.signals);
      metric('mNodes', data.dashboard.nodes);
      metric('mEdges', data.dashboard.edges);
      renderProfile(data.target_profile);
      renderResults(data.results);
      renderGraph(data.graph);
      renderTimeline(data);
      $('rawOutput').textContent = JSON.stringify(data, null, 2);
      $('saveBtn').disabled = false;
      $('saveCaseBtn').disabled = !$('caseSelect').value;
      $('saveStatus').textContent = '';
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    document.querySelectorAll('[data-view-btn]').forEach((button) => {
      button.addEventListener('click', () => setView(button.dataset.viewBtn));
    });
    $('graphCanvas').addEventListener('click', selectGraphNode);
    $('graphSearch').addEventListener('input', () => {
      if (state.latest) renderGraph(state.latest.graph);
    });
    $('graphFilter').addEventListener('change', () => {
      if (state.latest) renderGraph(state.latest.graph);
    });
    $('resetGraphBtn').addEventListener('click', () => {
      $('graphSearch').value = '';
      $('graphFilter').value = '';
      state.selectedNodeId = '';
      if (state.latest) {
        renderProfile(state.latest.target_profile);
        renderGraph(state.latest.graph);
      }
    });
    $('addEntityBtn').addEventListener('click', addManualEntity);
    $('removeEntityBtn').addEventListener('click', removeSelectedEntity);

    $('huntForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = Object.fromEntries(form.entries());
      $('runBtn').disabled = true;
      $('saveBtn').disabled = true;
      setStatus('Running', 'busy');
      try {
        const data = await api('/api/hunt', { method: 'POST', body: JSON.stringify(payload) });
        setView('overview');
        renderAll(data);
        setStatus('Ready');
      } catch (error) {
        setStatus('Error', 'error');
        $('rawOutput').textContent = JSON.stringify({ error: error.message }, null, 2);
      } finally {
        $('runBtn').disabled = false;
      }
    });

    $('saveBtn').addEventListener('click', async () => {
      if (!state.latest) return;
      $('saveBtn').disabled = true;
      $('saveStatus').textContent = 'Saving...';
      try {
        const payload = {
          target: state.latest.target_profile.original,
          results: state.latest.results,
          format: $('saveFormat').value
        };
        const saved = await api('/api/save', { method: 'POST', body: JSON.stringify(payload) });
        $('saveStatus').textContent = saved.path;
      } catch (error) {
        $('saveStatus').textContent = error.message;
      } finally {
        $('saveBtn').disabled = false;
      }
    });

    $('flowSelect').addEventListener('change', renderFlowDescription);

    $('runFlowBtn').addEventListener('click', async () => {
      const target = $('target').value.trim();
      const flowId = $('flowSelect').value;
      if (!target || !flowId) return;
      $('runFlowBtn').disabled = true;
      setStatus('Running flow', 'busy');
      try {
        const payload = {
          target,
          flow_id: flowId,
          timeout: $('timeout').value,
          concurrency: $('concurrency').value,
          mode: $('mode').value
        };
        const data = await api('/api/flow/run', { method: 'POST', body: JSON.stringify(payload) });
        setView('overview');
        renderAll({
          target_profile: data.target_profile,
          catalog: state.modules,
          results: data.results,
          graph: data.graph,
          dashboard: {
            ok: data.summary.completed_steps,
            skipped: 0,
            errors: data.summary.failed_steps,
            signals: data.graph.summary.node_count,
            nodes: data.graph.summary.node_count,
            edges: data.graph.summary.edge_count
          },
          flow: data,
          mode: data.summary.mode || $('mode').value
        });
        renderFlowLog(data);
        setStatus('Ready');
      } catch (error) {
        setStatus('Error', 'error');
        $('flowLog').innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
      } finally {
        $('runFlowBtn').disabled = false;
      }
    });

    function renderFlowLog(data) {
      const logs = data.execution_log || [];
      if (!logs.length) {
        $('flowLog').innerHTML = '<div class="empty">No flow steps.</div>';
        return;
      }
      $('flowLog').innerHTML = `<table><thead><tr><th>Step</th><th>Status</th><th>ms</th></tr></thead><tbody>${logs.map((item) => `
        <tr>
          <td>${escapeHtml(item.enricher_name)}<br><span class="small-muted">${escapeHtml((item.inputs || []).join(', '))}</span></td>
          <td>${escapeHtml(item.status)}</td>
          <td>${escapeHtml(String(item.execution_time_ms || 0))}</td>
        </tr>
      `).join('')}</tbody></table>`;
    }

    function renderTimeline(data) {
      const flowLog = (data.flow && data.flow.execution_log) || [];
      const edgeEvents = ((data.graph || {}).edges || []).slice(0, 80).map((edge) => ({
        title: edge.relationship || edge.type || 'edge',
        detail: `${edge.source} -> ${edge.target}`,
        time: edge.date || ''
      }));
      const flowEvents = flowLog.map((item) => ({
        title: item.node_id || item.step_id,
        detail: `${item.status} / ${(item.inputs || []).join(', ')} / ${item.execution_time_ms || 0}ms`,
        time: item.timestamp || ''
      }));
      const events = [...flowEvents, ...edgeEvents].slice(0, 120);
      if (!events.length) {
        $('timelineView').innerHTML = '<div class="empty">No timeline yet.</div>';
        return;
      }
      $('timelineView').innerHTML = events.map((item) => `
        <div class="timeline-item">
          <strong>${escapeHtml(item.title || 'event')}</strong>
          <span class="small-muted">${escapeHtml(item.time || '')}</span>
          <div>${escapeHtml(item.detail || '')}</div>
        </div>
      `).join('');
    }

    $('saveVaultBtn').addEventListener('click', async () => {
      const name = $('vaultName').value.trim();
      const value = $('vaultValue').value.trim();
      if (!name || !value) return;
      $('saveVaultBtn').disabled = true;
      try {
        const data = await api('/api/vault', { method: 'POST', body: JSON.stringify({ name, value }) });
        renderVault(data.vault);
        $('vaultValue').value = '';
      } catch (error) {
        $('vaultList').innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
      } finally {
        $('saveVaultBtn').disabled = false;
      }
    });

    $('createCaseBtn').addEventListener('click', async () => {
      const name = $('caseName').value.trim() || 'Untitled Investigation';
      const data = await api('/api/cases', { method: 'POST', body: JSON.stringify({ name }) });
      state.selectedCase = data.case.id;
      renderCases(data.store);
      $('caseName').value = '';
    });

    $('caseSelect').addEventListener('change', () => {
      state.selectedCase = $('caseSelect').value;
      $('saveCaseBtn').disabled = !state.latest || !state.selectedCase;
    });

    $('saveCaseBtn').addEventListener('click', async () => {
      if (!state.latest || !$('caseSelect').value) return;
      const payload = {
        case_id: $('caseSelect').value,
        target: state.latest.target_profile.original,
        graph: state.latest.graph,
        results: state.latest.results
      };
      const data = await api('/api/cases/save', { method: 'POST', body: JSON.stringify(payload) });
      state.selectedCase = data.case.id;
      renderCases(data.store);
      $('saveStatus').textContent = `Saved graph to ${data.case.name}`;
    });

    window.addEventListener('resize', () => {
      if (state.latest) renderGraph(state.latest.graph);
    });

    api('/api/modules').then(renderModules).catch(() => {});
    api('/api/flows').then(renderFlows);
    api('/api/vault').then(renderVault);
    api('/api/types').then(renderTypes);
    api('/api/cases').then(renderCases);
  </script>
</body>
</html>"""
