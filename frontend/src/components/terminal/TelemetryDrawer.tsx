import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Play, Terminal, Trash2, X } from "lucide-react";
import type { TerminalLine } from "../../lib/types";

type TelemetryCategory = "ALL" | "CORE" | "API" | "TRANSFORM" | "GRAPH" | "SECURITY";

function categoryFor(line: TerminalLine): Exclude<TelemetryCategory, "ALL"> {
  const text = `${line.level || ""} ${line.message || ""}`.toLowerCase();
  if (text.includes("transform") || text.includes("adapter")) return "TRANSFORM";
  if (text.includes("websocket") || text.includes("api") || text.includes("http") || text.includes("queued") || text.includes("endpoint")) return "API";
  if (text.includes("graph") || text.includes("node") || text.includes("edge") || text.includes("entity")) return "GRAPH";
  if (text.includes("error") || text.includes("guardrail") || text.includes("blocked") || text.includes("compliance")) return "SECURITY";
  return "CORE";
}

function timeFor(line: TerminalLine): string {
  if (!line.time) return "--:--:--";
  const parsed = new Date(line.time);
  if (Number.isNaN(parsed.getTime())) return "--:--:--";
  return parsed.toLocaleTimeString();
}

function levelFor(line: TerminalLine): string {
  const clean = (line.level || "info").toLowerCase();
  if (["error", "warning", "success", "system", "tool", "info"].includes(clean)) return clean;
  return "info";
}

export default function TelemetryDrawer({
  open,
  children,
  lines,
  taskLabel = "idle",
  onClose,
  onClear,
  onRunCommand,
}: {
  open: boolean;
  children?: ReactNode;
  lines?: TerminalLine[];
  taskLabel?: string;
  onClose?: () => void;
  onClear?: () => void;
  onRunCommand?: (command: string) => void;
}) {
  const [command, setCommand] = useState("");
  const [filter, setFilter] = useState<TelemetryCategory>("ALL");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const categories: TelemetryCategory[] = ["ALL", "CORE", "API", "TRANSFORM", "GRAPH", "SECURITY"];
  const liveLines = lines || [];
  const filteredLines = useMemo(() => liveLines.filter((line) => filter === "ALL" || categoryFor(line) === filter), [filter, liveLines]);

  useEffect(() => {
    if (open) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [filteredLines.length, open]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const clean = command.trim();
    if (!clean) return;
    onRunCommand?.(clean);
    setCommand("");
  };

  if (children && !lines) return <section className={open ? "nexus-telemetry telemetry-drawer open" : "nexus-telemetry telemetry-drawer"} aria-label="Live telemetry" aria-hidden={!open}>{children}</section>;

  return (
    <section className={open ? "nexus-telemetry telemetry-drawer open reference-telemetry" : "nexus-telemetry telemetry-drawer reference-telemetry"} aria-label="Live telemetry console" aria-hidden={!open}>
      <header className="ref-telemetry-header">
        <div><Terminal size={14} /><strong>Live Telemetry Console</strong><span>{taskLabel || "idle"}</span></div>
        <nav aria-label="Telemetry filters">
          {categories.map((category) => <button className={filter === category ? "active" : ""} key={category} type="button" onClick={() => setFilter(category)}>{category}</button>)}
        </nav>
        <div>
          <button type="button" onClick={onClear} aria-label="Clear telemetry"><Trash2 size={13} /></button>
          <button type="button" onClick={onClose} aria-label="Close telemetry"><X size={13} /></button>
        </div>
      </header>
      <div className="ref-telemetry-lines" ref={scrollRef}>
        {filteredLines.map((line, index) => {
          const category = categoryFor(line);
          return (
            <p className={levelFor(line)} key={`${line.time || index}:${index}`}>
              <time>{timeFor(line)}</time>
              <strong className={`category-${category.toLowerCase()}`}>{category}</strong>
              <code>{line.message}</code>
            </p>
          );
        })}
        {!filteredLines.length && <div className="ref-telemetry-empty">No telemetry captured for filter {filter}. Run a lookup or transform to stream live events.</div>}
      </div>
      <form className="ref-telemetry-input" onSubmit={submit}>
        <span>nexusintel_operator#</span>
        <input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Safe UI commands: help, clear-ui-logs, open-palette, fit-graph..." />
        <button type="submit" aria-label="Run UI command"><Play size={12} /></button>
      </form>
    </section>
  );
}
