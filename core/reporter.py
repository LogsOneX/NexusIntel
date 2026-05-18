import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.graph import build_investigation_graph
from core.targets import TargetProfile, classify_target


class ReportGenerator:
    def __init__(
        self,
        target: str,
        results: Dict[str, Any],
        output_dir: str = "results",
        profile: Optional[TargetProfile] = None,
        run_label: str = "osint",
    ):
        self.target = target
        self.results = results
        self.output_dir = Path(output_dir)
        self.profile = profile or classify_target(target)
        self.run_label = run_label
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.graph = build_investigation_graph(self.profile, self.results)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, output_format: str = "json") -> str:
        if output_format == "json":
            return self.generate_json()
        if output_format == "md":
            return self.generate_markdown()
        if output_format == "html":
            return self.generate_html()
        if output_format == "graph":
            return self.generate_graph_json()
        raise ValueError(f"Unsupported report format: {output_format}")

    def generate_json(self) -> str:
        filepath = self._path("json")
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(self._payload(), handle, indent=2, ensure_ascii=False, default=str)
        return str(filepath)

    def generate_graph_json(self) -> str:
        filepath = self._path("graph.json")
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(self.graph, handle, indent=2, ensure_ascii=False, default=str)
        return str(filepath)

    def generate_markdown(self) -> str:
        payload = self._payload()
        filepath = self._path("md")

        lines = [
            "# NexusRecon OSINT Report",
            "",
            f"- Target: `{self.target}`",
            f"- Type: `{self.profile.kind}`",
            f"- Normalized: `{self.profile.normalized}`",
            f"- Generated: `{self.timestamp}`",
            f"- Modules: `{payload['meta']['total_modules']}`",
            f"- Graph Nodes: `{self.graph['summary']['node_count']}`",
            f"- Graph Edges: `{self.graph['summary']['edge_count']}`",
            "",
            "## Executive Summary",
            "",
            "| Module | Status | Signals | Summary |",
            "| :--- | :--- | ---: | :--- |",
        ]

        for name, result in sorted(self.results.items()):
            lines.append(
                f"| `{name}` | {result.get('status', 'unknown')} | {result.get('signal_count', 0)} | "
                f"{_md_escape(_summary(result.get('data'), result.get('message')))} |"
            )

        lines.extend(["", "## Module Details", ""])
        for name, result in sorted(self.results.items()):
            lines.extend(
                [
                    f"### {name}",
                    "",
                    f"- Status: `{result.get('status', 'unknown')}`",
                    f"- Signals: `{result.get('signal_count', 0)}`",
                    "",
                    "```json",
                    json.dumps(result.get("data", result.get("message", {})), indent=2, ensure_ascii=False, default=str),
                    "```",
                    "",
                ]
            )

        lines.extend(
            [
                "## Investigation Graph",
                "",
                "| Node Type | Count |",
                "| :--- | ---: |",
            ]
        )
        for node_type, count in sorted(self.graph["summary"]["node_types"].items()):
            lines.append(f"| `{node_type}` | {count} |")
        lines.extend(
            [
                "",
                "```json",
                json.dumps(self.graph, indent=2, ensure_ascii=False, default=str),
                "```",
                "",
            ]
        )

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)

    def generate_html(self) -> str:
        filepath = self._path("html")
        rows = []
        detail_blocks = []
        node_rows = []
        edge_rows = []
        for name, result in sorted(self.results.items()):
            status = html.escape(str(result.get("status", "unknown")))
            signal = html.escape(str(result.get("signal_count", 0)))
            summary = html.escape(_summary(result.get("data"), result.get("message")))
            rows.append(f"<tr><td><strong>{html.escape(name)}</strong></td><td><span class=\"badge badge-{status}\">{status}</span></td><td>{signal}</td><td>{summary}</td></tr>")
            body = html.escape(json.dumps(result.get("data", result.get("message", {})), indent=2, ensure_ascii=False, default=str))
            detail_blocks.append(f"<details><summary>{html.escape(name)}</summary><pre>{body}</pre></details>")

        for node in self.graph["nodes"][:160]:
            node_rows.append(
                "<tr>"
                f"<td><span class=\"node-type\">{html.escape(node['type'])}</span></td>"
                f"<td>{html.escape(node['label'])}</td>"
                f"<td>{html.escape(json.dumps(node.get('properties', {}), ensure_ascii=False, default=str)[:240])}</td>"
                "</tr>"
            )
        for edge in self.graph["edges"][:220]:
            edge_rows.append(
                "<tr>"
                f"<td>{html.escape(edge['relationship'])}</td>"
                f"<td>{html.escape(edge['source'])}</td>"
                f"<td>{html.escape(edge['target'])}</td>"
                f"<td>{html.escape(edge.get('module', ''))}</td>"
                "</tr>"
            )

        total_signals = sum(int(result.get("signal_count", 0) or 0) for result in self.results.values())
        ok = sum(1 for result in self.results.values() if result.get("status") == "success")
        skipped = sum(1 for result in self.results.values() if result.get("status") == "skipped")
        errors = sum(1 for result in self.results.values() if result.get("status") == "error")

        content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NexusRecon Report - {html.escape(self.profile.normalized)}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0a0d12; --panel:#141922; --panel2:#10151d; --line:#2b3545; --text:#eef3fb; --muted:#9aa8ba; --cyan:#58d7ff; --green:#78e6a1; --amber:#f4c76b; --red:#ff7d7d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1180px; margin:0 auto; padding:32px 20px 56px; }}
    header, section {{ border:1px solid var(--line); background:var(--panel); padding:22px; border-radius:8px; margin-bottom:18px; }}
    h1 {{ margin:0 0 8px; font-size:30px; letter-spacing:0; }}
    h2 {{ margin:0 0 14px; font-size:18px; letter-spacing:0; }}
    .muted {{ color:var(--muted); }}
    .meta, .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-top:16px; }}
    .metric {{ border:1px solid var(--line); background:var(--panel2); border-radius:8px; padding:14px; }}
    .metric span {{ color:var(--muted); display:block; font-size:12px; text-transform:uppercase; }}
    .metric strong {{ display:block; font-size:22px; margin-top:6px; }}
    table {{ width:100%; border-collapse:collapse; margin:8px 0 0; background:var(--panel2); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:11px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:var(--cyan); font-size:12px; text-transform:uppercase; }}
    tr:last-child td {{ border-bottom:0; }}
    pre {{ overflow:auto; background:#0b1017; border:1px solid var(--line); padding:14px; border-radius:8px; }}
    details {{ background:var(--panel2); border:1px solid var(--line); border-radius:8px; padding:12px 14px; margin-top:10px; }}
    summary {{ cursor:pointer; font-weight:700; }}
    .badge {{ display:inline-flex; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; text-transform:uppercase; }}
    .badge-success {{ color:var(--green); }}
    .badge-skipped {{ color:var(--amber); }}
    .badge-error {{ color:var(--red); }}
    .node-type {{ color:var(--cyan); font-weight:700; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>NexusRecon OSINT Report</h1>
    <div class="muted">Passive public-source scan summary with module output and investigation graph.</div>
    <div class="meta">
      <div class="metric"><span>Target</span><strong>{html.escape(self.target)}</strong></div>
      <div class="metric"><span>Type</span><strong>{html.escape(self.profile.kind)}</strong></div>
      <div class="metric"><span>Normalized</span><strong>{html.escape(self.profile.normalized)}</strong></div>
      <div class="metric"><span>Generated</span><strong>{html.escape(self.timestamp)}</strong></div>
    </div>
  </header>
  <section>
    <h2>Executive Dashboard</h2>
    <div class="stats">
      <div class="metric"><span>Modules OK</span><strong>{ok}</strong></div>
      <div class="metric"><span>Skipped</span><strong>{skipped}</strong></div>
      <div class="metric"><span>Errors</span><strong>{errors}</strong></div>
      <div class="metric"><span>Signals</span><strong>{total_signals}</strong></div>
      <div class="metric"><span>Graph Nodes</span><strong>{self.graph['summary']['node_count']}</strong></div>
      <div class="metric"><span>Graph Edges</span><strong>{self.graph['summary']['edge_count']}</strong></div>
    </div>
  </section>
  <section>
    <h2>Module Results</h2>
    <table>
      <thead><tr><th>Module</th><th>Status</th><th>Signals</th><th>Summary</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Investigation Graph Nodes</h2>
    <table>
      <thead><tr><th>Type</th><th>Label</th><th>Properties</th></tr></thead>
      <tbody>{''.join(node_rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Investigation Graph Edges</h2>
    <table>
      <thead><tr><th>Relationship</th><th>Source</th><th>Target</th><th>Module</th></tr></thead>
      <tbody>{''.join(edge_rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Raw Module Details</h2>
    {''.join(detail_blocks)}
  </section>
</main>
</body>
</html>
"""
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def _payload(self) -> dict:
        ok = sum(1 for result in self.results.values() if result.get("status") == "success")
        errors = sum(1 for result in self.results.values() if result.get("status") == "error")
        skipped = sum(1 for result in self.results.values() if result.get("status") == "skipped")
        return {
            "meta": {
                "target": self.target,
                "target_profile": self.profile.__dict__,
                "generated_at": self.timestamp,
                "run_label": self.run_label,
                "total_modules": len(self.results),
                "successful_modules": ok,
                "error_modules": errors,
                "skipped_modules": skipped,
            },
            "graph": self.graph,
            "data": self.results,
        }

    def _path(self, extension: str) -> Path:
        safe_target = re.sub(r"[^A-Za-z0-9_.-]", "_", self.profile.normalized or self.target)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"{self.run_label}_{safe_target}_{stamp}.{extension}"


def _summary(data: Any, fallback: Any = None) -> str:
    if fallback:
        return str(fallback)
    if isinstance(data, dict):
        chunks = []
        for key in ("query", "identity", "target", "domain", "provider", "risk_level", "found_count", "present_count"):
            if data.get(key) not in (None, "", [], {}):
                chunks.append(f"{key}: {data[key]}")
        return ", ".join(chunks[:4]) or f"{len(data)} fields"
    if isinstance(data, list):
        return f"{len(data)} items"
    return str(data or "No data")


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
