import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Braces,
  ChevronLeft,
  ChevronRight,
  FileJson,
  Layers3,
  Maximize2,
  Minimize2,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Plus,
  Radio,
  Search,
  Shield,
  Sparkles,
  Terminal,
  UserSearch,
} from "lucide-react";
import FlowCanvas from "./FlowCanvas";

type GraphNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  source?: string;
  confidence?: string;
  data?: Record<string, unknown>;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  data?: Record<string, unknown>;
};

type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type Investigation = {
  id: string;
  target: string;
  target_type: string;
  status: string;
  mode: string;
  created_at: string;
  updated_at: string;
  meta?: Record<string, unknown>;
};

type TerminalLine = {
  task_id?: string;
  level: string;
  message: string;
  time?: string;
  payload?: Record<string, unknown>;
};

type ManualEntityDraft = {
  type: string;
  label: string;
  value: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";

function wsUrl(taskId: string): string {
  const configured = import.meta.env.VITE_WS_BASE;
  if (configured) return `${configured}/api/v1/ws/logs/${taskId}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/ws/logs/${taskId}`;
}

async function apiJson(path: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.detail || payload.message || `Request failed: ${response.status}`);
  }
  return payload;
}

function flattenData(input: unknown, prefix = ""): Array<[string, string]> {
  if (input === null || input === undefined) return [];
  if (typeof input !== "object") return [[prefix || "value", String(input)]];
  if (Array.isArray(input)) {
    return input.flatMap((item, index) => flattenData(item, `${prefix}[${index}]`));
  }
  return Object.entries(input as Record<string, unknown>).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object") return flattenData(value, nextKey);
    return [[nextKey, String(value ?? "")]];
  });
}

function graphStats(graph: GraphPayload) {
  const byType = graph.nodes.reduce<Record<string, number>>((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {});
  return {
    entities: graph.nodes.length,
    relationships: graph.edges.length,
    profiles: byType.profile || 0,
    infra: (byType.domain || 0) + (byType.ip || 0) + (byType.dns_record || 0),
  };
}

function terminalPrefix(level: string): string {
  if (["tool", "info", "success", "warning"].includes(level)) return "[OSINT]";
  if (level === "error") return "[ALERT]";
  return "[SYS]";
}

export default function Dashboard() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [activeInvestigationId, setActiveInvestigationId] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<"passive" | "standard" | "aggressive">("standard");
  const [manualEntity, setManualEntity] = useState<ManualEntityDraft>({ type: "email", label: "", value: "" });
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [taskLabel, setTaskLabel] = useState("idle");
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isCommandOpen, setIsCommandOpen] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isTerminalOpen, setIsTerminalOpen] = useState(true);
  const [isFocusMode, setIsFocusMode] = useState(false);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);

  const stats = useMemo(() => graphStats(graph), [graph]);
  const activeInvestigation = investigations.find((item) => item.id === activeInvestigationId) || null;
  const selectedDataRows = useMemo(() => {
    const rows = flattenData(selectedNode?.data || {});
    if (!filter.trim()) return rows;
    const needle = filter.toLowerCase();
    return rows.filter(([key, value]) => key.toLowerCase().includes(needle) || value.toLowerCase().includes(needle));
  }, [filter, selectedNode]);

  const shellClass = useMemo(
    () =>
      [
        "nx-shell",
        !isCommandOpen ? "left-collapsed" : "",
        !isSidebarOpen ? "right-collapsed" : "",
        !isTerminalOpen ? "terminal-collapsed" : "",
        isFocusMode ? "focus-mode" : "",
      ]
        .filter(Boolean)
        .join(" "),
    [isCommandOpen, isFocusMode, isSidebarOpen, isTerminalOpen],
  );

  const exitFocusMode = useCallback(() => {
    if (isFocusMode) setIsFocusMode(false);
  }, [isFocusMode]);

  const toggleCommand = useCallback(() => {
    exitFocusMode();
    setIsCommandOpen((open) => !open);
  }, [exitFocusMode]);

  const toggleSidebar = useCallback(() => {
    exitFocusMode();
    setIsSidebarOpen((open) => !open);
  }, [exitFocusMode]);

  const toggleTerminal = useCallback(() => {
    exitFocusMode();
    setIsTerminalOpen((open) => !open);
  }, [exitFocusMode]);

  const toggleFocusMode = useCallback(() => {
    setIsFocusMode((open) => {
      const next = !open;
      if (next) {
        setIsCommandOpen(false);
        setIsSidebarOpen(false);
        setIsTerminalOpen(false);
      } else {
        setIsCommandOpen(true);
        setIsSidebarOpen(true);
        setIsTerminalOpen(true);
      }
      return next;
    });
  }, []);

  const loadInvestigations = useCallback(async () => {
    try {
      const payload = await apiJson("/api/v1/investigations");
      setInvestigations(payload.data.items || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load investigations");
    }
  }, []);

  const loadGraph = useCallback(async (investigationId: string) => {
    try {
      const payload = await apiJson(`/api/v1/investigations/${investigationId}/graph`);
      setGraph(payload.data);
      setActiveInvestigationId(investigationId);
      setSelectedNode(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load graph");
    }
  }, []);

  useEffect(() => {
    loadInvestigations();
  }, [loadInvestigations]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (!["b", "j", "f"].includes(key)) return;
      event.preventDefault();
      if (key === "b") toggleSidebar();
      if (key === "j") toggleTerminal();
      if (key === "f") toggleFocusMode();
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [toggleFocusMode, toggleSidebar, toggleTerminal]);

  useEffect(() => {
    if (!currentTaskId) return undefined;
    const socket = new WebSocket(wsUrl(currentTaskId));
    socket.onmessage = (event) => {
      try {
        const line = JSON.parse(event.data) as TerminalLine;
        setTerminalLines((previous) => [...previous.slice(-260), line]);
      } catch {
        setTerminalLines((previous) => [...previous.slice(-260), { level: "tool", message: event.data }]);
      }
    };
    socket.onerror = () => {
      setTerminalLines((previous) => [
        ...previous.slice(-260),
        { level: "error", message: "WebSocket telemetry connection failed", time: new Date().toISOString() },
      ]);
    };
    return () => socket.close();
  }, [currentTaskId]);

  const startInvestigation = async (event: FormEvent) => {
    event.preventDefault();
    if (!target.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiJson("/api/v1/scans/nexusrecon", {
        method: "POST",
        body: JSON.stringify({ target: target.trim(), mode }),
      });
      setActiveInvestigationId(payload.data.investigation_id);
      setGraph(payload.data.graph);
      setSelectedNode(null);
      setCurrentTaskId(payload.data.task_id);
      setTaskLabel(`nexusrecon / ${target.trim()}`);
      setTerminalLines([]);
      setIsFocusMode(false);
      setIsTerminalOpen(true);
      await loadInvestigations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to start investigation");
    } finally {
      setLoading(false);
    }
  };

  const addManualEntity = async (event: FormEvent) => {
    event.preventDefault();
    if (!activeInvestigationId || !manualEntity.value.trim()) return;
    const label = manualEntity.label.trim() || manualEntity.value.trim();
    try {
      const payload = await apiJson("/api/v1/entities", {
        method: "POST",
        body: JSON.stringify({
          investigation_id: activeInvestigationId,
          type: manualEntity.type,
          label,
          value: manualEntity.value.trim(),
          source_id: selectedNode?.id || null,
          relationship_type: selectedNode ? "manual_pivot" : "manual_seed",
          data: { created_from: "dashboard", parent: selectedNode?.id || null },
        }),
      });
      setGraph(payload.data.graph);
      setManualEntity({ type: manualEntity.type, label: "", value: "" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to add entity");
    }
  };

  const handleTaskStart = (taskId: string, transform: string, node: GraphNode) => {
    setCurrentTaskId(taskId);
    setTaskLabel(`${transform.replaceAll("_", " ")} / ${node.label}`);
    setTerminalLines([]);
  };

  return (
    <main className={shellClass}>
      <div className="nx-floating-controls" aria-label="Workspace controls">
        <button className={isCommandOpen ? "nx-control-button active" : "nx-control-button"} type="button" onClick={toggleCommand} title="Toggle command rail">
          <PanelLeft size={16} />
        </button>
        <button className={isSidebarOpen ? "nx-control-button active" : "nx-control-button"} type="button" onClick={toggleSidebar} title="Toggle deep data panel (Ctrl+B)">
          <PanelRight size={16} />
        </button>
        <button className={isTerminalOpen ? "nx-control-button active" : "nx-control-button"} type="button" onClick={toggleTerminal} title="Toggle terminal HUD (Ctrl+J)">
          <PanelBottom size={16} />
        </button>
        <button className={isFocusMode ? "nx-control-button active" : "nx-control-button"} type="button" onClick={toggleFocusMode} title="Fullscreen graph focus (Ctrl+F)">
          {isFocusMode ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
      </div>

      <aside className={isCommandOpen ? "nx-left" : "nx-left closed"}>
        <div className="nx-brand">
          <div className="nx-brand-mark"><Shield size={20} /></div>
          <div>
            <strong>NexusIntel</strong>
            <span>Standalone OSINT Command Center</span>
          </div>
        </div>

        <form className="nx-panel" onSubmit={startInvestigation}>
          <div className="nx-panel-title">
            <UserSearch size={15} />
            <span>Target acquisition</span>
          </div>
          <label>
            <span>Primary target</span>
            <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="username, email, domain, phone" />
          </label>
          <label>
            <span>Recon mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value as "passive" | "standard" | "aggressive")}>
              <option value="passive">Passive</option>
              <option value="standard">Standard</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </label>
          <button className="nx-primary" type="submit" disabled={loading}>
            <Radio size={15} />
            {loading ? "Queuing..." : "Launch sweep"}
          </button>
        </form>

        <form className="nx-panel" onSubmit={addManualEntity}>
          <div className="nx-panel-title">
            <Plus size={15} />
            <span>Entity builder</span>
          </div>
          <select value={manualEntity.type} onChange={(event) => setManualEntity((draft) => ({ ...draft, type: event.target.value }))}>
            <option value="username">Username</option>
            <option value="email">Email</option>
            <option value="domain">Domain</option>
            <option value="phone">Phone</option>
            <option value="ip">IP address</option>
            <option value="profile">Profile URL</option>
            <option value="service">Service</option>
          </select>
          <input value={manualEntity.label} onChange={(event) => setManualEntity((draft) => ({ ...draft, label: event.target.value }))} placeholder="Label (optional)" />
          <input value={manualEntity.value} onChange={(event) => setManualEntity((draft) => ({ ...draft, value: event.target.value }))} placeholder="Entity value" />
          <button className="nx-secondary" type="submit" disabled={!activeInvestigationId}>
            <Plus size={15} />
            Add entity
          </button>
        </form>

        <section className="nx-panel nx-cases">
          <div className="nx-panel-title">
            <Layers3 size={15} />
            <span>Investigations</span>
          </div>
          <div className="nx-case-list">
            {investigations.map((item) => (
              <button
                className={item.id === activeInvestigationId ? "nx-case active" : "nx-case"}
                key={item.id}
                type="button"
                onClick={() => loadGraph(item.id)}
              >
                <strong>{item.target}</strong>
                <span>{item.target_type} / {item.status} / {new Date(item.created_at).toLocaleString()}</span>
              </button>
            ))}
            {!investigations.length && <div className="nx-empty">No cases yet.</div>}
          </div>
        </section>
      </aside>

      <section className="nx-center">
        <header className="nx-topbar">
          <div>
            <div className="nx-eyebrow">
              <Activity size={14} />
              <span>{activeInvestigation ? activeInvestigation.status : "ready"}</span>
            </div>
            <h1>{activeInvestigation ? activeInvestigation.target : "Create a target to begin visual intelligence mapping"}</h1>
          </div>
          <div className="nx-stat-grid">
            <div><span>Entities</span><strong>{stats.entities}</strong></div>
            <div><span>Edges</span><strong>{stats.relationships}</strong></div>
            <div><span>Profiles</span><strong>{stats.profiles}</strong></div>
            <div><span>Infra</span><strong>{stats.infra}</strong></div>
          </div>
        </header>

        {error && (
          <div className="nx-alert">
            <AlertTriangle size={16} />
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        <div className="nx-workbench">
          <FlowCanvas
            investigationId={activeInvestigationId}
            nodes={graph.nodes}
            edges={graph.edges}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
            onGraphUpdate={setGraph}
            onTaskStart={handleTaskStart}
            onError={setError}
          />

          <aside className={isSidebarOpen ? "nx-drawer" : "nx-drawer closed"} aria-hidden={!isSidebarOpen}>
            <button className="nx-drawer-toggle" type="button" onClick={toggleSidebar} title="Toggle deep data panel">
              {isSidebarOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
            <div className="nx-drawer-inner">
              <div className="nx-panel-title">
                <FileJson size={15} />
                <span>Deep entity data</span>
              </div>
              {selectedNode ? (
                <>
                  <div className="nx-entity-head">
                    <span className={`nx-entity-chip ${selectedNode.type}`}>{selectedNode.type}</span>
                    <h2>{selectedNode.label}</h2>
                    <p>{selectedNode.value}</p>
                  </div>
                  <div className="nx-search">
                    <Search size={14} />
                    <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter structured fields" />
                  </div>
                  <div className="nx-data-table">
                    <div className="nx-row">
                      <strong>Field</strong>
                      <strong>Value</strong>
                    </div>
                    <div className="nx-row"><span>source</span><code>{selectedNode.source || "unknown"}</code></div>
                    <div className="nx-row"><span>confidence</span><code>{selectedNode.confidence || "medium"}</code></div>
                    {selectedDataRows.map(([key, value]) => (
                      <div className="nx-row" key={`${key}:${value}`}>
                        <span>{key}</span>
                        <code>{value}</code>
                      </div>
                    ))}
                    {!selectedDataRows.length && <div className="nx-empty">No nested intelligence fields matched.</div>}
                  </div>
                  <details className="nx-json-raw">
                    <summary><Braces size={14} /> Raw JSON</summary>
                    <pre>{JSON.stringify(selectedNode, null, 2)}</pre>
                  </details>
                </>
              ) : (
                <div className="nx-empty large">
                  <Sparkles size={18} />
                  <strong>Select a node</strong>
                  <span>Click any graph entity to inspect normalized intelligence, raw payloads, confidence and source metadata.</span>
                </div>
              )}
            </div>
          </aside>
        </div>

        <section className={isTerminalOpen ? "nx-terminal" : "nx-terminal closed"} aria-hidden={!isTerminalOpen}>
          <header>
            <div>
              <Terminal size={15} />
              <strong>Live terminal HUD</strong>
              <span>{taskLabel}</span>
            </div>
            <div className="nx-terminal-actions">
              <code>{currentTaskId || "no-active-task"}</code>
              <button className="icon-button" type="button" onClick={toggleTerminal} title="Hide terminal HUD">
                <PanelBottom size={15} />
              </button>
            </div>
          </header>
          <div className="nx-terminal-lines">
            {terminalLines.map((line, index) => (
              <div className={`nx-term-line ${line.level}`} key={`${line.time || index}:${index}`}>
                <span>{line.time ? new Date(line.time).toLocaleTimeString() : "--:--:--"}</span>
                <strong>{terminalPrefix(line.level)}</strong>
                <code>{line.message}</code>
              </div>
            ))}
            {!terminalLines.length && (
              <div className="nx-term-line system">
                <span>00:00:00</span>
                <strong>[SYS]</strong>
                <code>Waiting for a recon task...</code>
              </div>
            )}
            <div className="nx-terminal-cursor" aria-hidden="true" />
          </div>
        </section>
      </section>
    </main>
  );
}
