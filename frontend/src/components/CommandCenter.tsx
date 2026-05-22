import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Bot,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Database,
  FileJson,
  FolderOpen,
  Home,
  KeyRound,
  LogOut,
  Network,
  Plus,
  Settings,
  Shield,
  Terminal,
  Trash2,
  UserCircle,
} from "lucide-react";
import GraphCanvas from "./GraphCanvas";
import OraclePanel from "./OraclePanel";

type ApiNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  source?: string;
  confidence?: string;
  data?: Record<string, unknown>;
  created_at?: string;
};

type ApiEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  confidence_level?: number;
  data?: Record<string, unknown>;
  created_at?: string;
};

type GraphPayload = { nodes: ApiNode[]; edges: ApiEdge[] };

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

type GraphIntelligence = {
  posture: string;
  risk_score: number;
  source_reliability: number;
  lead_queue: Array<{ priority: string; node_id: string; label: string; action: string; reason: string }>;
  entity_risks: Array<Record<string, unknown>>;
  communities: Array<{ id: string; size: number; hub_id: string; hub_label: string; types: Record<string, number> }>;
  dossier: Record<string, unknown>;
};

type CaseHealth = {
  score: number;
  status: string;
  node_count: number;
  edge_count: number;
  coverage: Record<string, number>;
  weak_nodes: Array<Record<string, unknown>>;
  isolated_nodes: Array<Record<string, unknown>>;
  recommendations: Array<{ priority: string; action: string; reason: string }>;
  intelligence?: GraphIntelligence;
};

type TerminalLine = {
  task_id?: string;
  level: string;
  message: string;
  time?: string;
  payload?: Record<string, unknown>;
};

type SessionState = { token: string | null; user: string | null };

type PageProps = {
  token: string;
  user: string;
  navigate: (path: string) => void;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";
const AUTH_KEY = "nexusintel.session";

const ROUTES = [
  { path: "/dashboard", label: "Dashboard", icon: Home },
  { path: "/workspace", label: "Workspace", icon: Briefcase },
  { path: "/graph", label: "Network Graph", icon: Network },
  { path: "/oracle", label: "AI Oracle", icon: Bot },
  { path: "/settings", label: "Settings", icon: Settings },
  { path: "/account", label: "Account", icon: UserCircle },
];

function readSession(): SessionState {
  try {
    const raw = window.localStorage.getItem(AUTH_KEY);
    if (!raw) return { token: null, user: null };
    return JSON.parse(raw) as SessionState;
  } catch {
    return { token: null, user: null };
  }
}

function saveSession(session: SessionState) {
  window.localStorage.setItem(AUTH_KEY, JSON.stringify(session));
}

function clearSession() {
  window.localStorage.removeItem(AUTH_KEY);
}

function wsUrl(taskId: string): string {
  const configured = import.meta.env.VITE_WS_BASE;
  if (configured) return `${configured}/api/v1/ws/logs/${taskId}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/ws/logs/${taskId}`;
}

async function apiJson(path: string, options?: RequestInit, token?: string | null) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `Request failed: ${response.status}`);
  return payload;
}

function terminalPrefix(level: string): string {
  if (["tool", "info", "success", "warning"].includes(level)) return "[OSINT]";
  if (level === "error") return "[ALERT]";
  return "[SYS]";
}

function flattenData(input: unknown, prefix = ""): Array<[string, string]> {
  if (input === null || input === undefined) return [];
  if (typeof input !== "object") return [[prefix || "value", String(input)]];
  if (Array.isArray(input)) return input.flatMap((item, index) => flattenData(item, `${prefix}[${index}]`));
  return Object.entries(input as Record<string, unknown>).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object") return flattenData(value, nextKey);
    return [[nextKey, String(value ?? "")]];
  });
}

function LoginPage({ onLogin }: { onLogin: (session: SessionState) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload = await apiJson("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      onLogin({ token: payload.data.token, user: payload.data.user });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-screen">
      <form className="login-terminal" onSubmit={submit}>
        <div className="login-brand"><Shield size={22} /><span>NexusIntel Access Control</span></div>
        <h1>Operator Login</h1>
        <p>Local authentication only. Credentials are configured through environment variables or backend settings.</p>
        <label><span>Operator</span><input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
        <label><span>Passphrase</span><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" /></label>
        {error && <div className="auth-error">{error}</div>}
        <button className="nx-primary" type="submit" disabled={loading}><KeyRound size={15} />{loading ? "Authenticating" : "Enter Command Center"}</button>
      </form>
    </main>
  );
}

function Shell({ route, user, collapsed, setCollapsed, navigate, logout, children }: { route: string; user: string; collapsed: boolean; setCollapsed: (value: boolean) => void; navigate: (path: string) => void; logout: () => void; children: React.ReactNode }) {
  return (
    <main className={collapsed ? "command-shell nav-collapsed" : "command-shell"}>
      <aside className="command-sidebar">
        <div className="command-brand"><Shield size={18} /><div><strong>NexusIntel</strong><span>Command Center</span></div></div>
        <nav>
          {ROUTES.map((item) => {
            const Icon = item.icon;
            return <button className={route === item.path ? "active" : ""} key={item.path} type="button" onClick={() => navigate(item.path)} title={item.label}><Icon size={17} /><span>{item.label}</span></button>;
          })}
        </nav>
        <div className="sidebar-footer">
          <button type="button" onClick={() => setCollapsed(!collapsed)} title="Collapse sidebar">{collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}<span>Collapse</span></button>
          <button type="button" onClick={logout} title="Logout"><LogOut size={16} /><span>Logout</span></button>
          <code>{user}</code>
        </div>
      </aside>
      <section className="command-content">{children}</section>
    </main>
  );
}

function DashboardHome({ token, navigate }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiJson("/api/v1/cases", undefined, token).then((payload) => setCases(payload.data.items || [])).catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load cases"));
  }, [token]);

  return (
    <section className="page-grid">
      <header className="page-header"><div><span className="micro-label">Master Dashboard</span><h1>Case Management Hub</h1></div><button className="nx-secondary" type="button" onClick={() => navigate("/graph")}><Network size={15} />Open Graph</button></header>
      {error && <div className="nx-alert">{error}</div>}
      <div className="command-card wide"><h2>Recent Investigations</h2><div className="intel-table"><div className="intel-row head"><span>Target</span><span>Type</span><span>Status</span><span>Updated</span></div>{cases.map((item) => <button className="intel-row" key={item.id} type="button" onClick={() => navigate(`/graph?case=${item.id}`)}><span>{item.meta?.case_name as string || item.target}</span><span>{item.target_type}</span><span>{item.status}</span><span>{new Date(item.updated_at).toLocaleString()}</span></button>)}</div></div>
      <div className="folder-grid">{cases.slice(0, 6).map((item) => <button className="case-folder" key={item.id} type="button" onClick={() => navigate(`/workspace?case=${item.id}`)}><FolderOpen size={20} /><strong>{item.meta?.case_name as string || item.target}</strong><span>{item.target_type} / {item.status}</span></button>)}{!cases.length && <div className="command-card"><strong>No folders yet</strong><span>Launch a graph investigation to create the first case folder.</span></div>}</div>
      <div className="command-card"><h2>Global Timeline</h2><p>Open Network Graph and press Ctrl+T for temporal graph analysis.</p></div>
      <div className="command-card"><h2>Reports</h2><p>Use Export Intelligence in the graph toolbar to generate printable monochrome reports.</p></div>
    </section>
  );
}

function caseTitle(item: Investigation): string {
  return String(item.meta?.case_name || item.target || "Untitled Investigation");
}

function CaseDock({
  investigations,
  activeCase,
  health,
  onSelect,
  onCreateBlank,
  onDeleteActive,
  onClearActive,
  loading,
}: {
  investigations: Investigation[];
  activeCase: Investigation | null;
  health: CaseHealth | null;
  onSelect: (id: string) => void;
  onCreateBlank: () => void;
  onDeleteActive: () => void;
  onClearActive: () => void;
  loading: boolean;
}) {
  const topRecommendation = health?.recommendations?.[0];
  const intel = health?.intelligence;
  const topLead = intel?.lead_queue?.[0];
  return (
    <aside className="graph-case-dock" aria-label="Investigation lifecycle controls">
      <header>
        <div><FolderOpen size={14} /><strong>Investigation</strong></div>
        <span>{activeCase ? activeCase.status : "detached"}</span>
      </header>
      <select value={activeCase?.id || ""} onChange={(event) => onSelect(event.target.value)} disabled={loading}>
        <option value="">No case selected</option>
        {investigations.map((item) => <option value={item.id} key={item.id}>{caseTitle(item)} / {item.target_type}</option>)}
      </select>
      <div className="case-dock-actions">
        <button type="button" onClick={onCreateBlank} disabled={loading} title="Create a blank investigation from the toolbar target"><Plus size={13} />New</button>
        <button type="button" onClick={onClearActive} disabled={!activeCase || loading} title="Detach graph without deleting"><Database size={13} />Clear</button>
        <button className="danger" type="button" onClick={onDeleteActive} disabled={!activeCase || loading} title="Delete this investigation and its graph"><Trash2 size={13} />Delete</button>
      </div>
      <div className="case-health-strip">
        <span><Activity size={13} />Health {health ? `${health.score}%` : "--"}</span>
        <code>{health?.status || "no graph"}</code>
      </div>
      <div className="intel-kpi-grid">
        <span><strong>{intel ? `${intel.risk_score}%` : "--"}</strong><small>Risk</small></span>
        <span><strong>{intel ? `${intel.source_reliability}%` : "--"}</strong><small>Source</small></span>
        <span><strong>{intel?.communities?.length ?? "--"}</strong><small>Clusters</small></span>
      </div>
      {topLead && <div className="lead-queue-card"><strong>{topLead.action}</strong><span>{topLead.reason}</span></div>}
      {!topLead && topRecommendation && <p>{topRecommendation.action}: {topRecommendation.reason}</p>}
    </aside>
  );
}

function GraphHub({ token, navigate }: PageProps) {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [activeInvestigationId, setActiveInvestigationId] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState<ApiNode | null>(null);
  const [oracleNode, setOracleNode] = useState<ApiNode | null>(null);
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<"passive" | "standard" | "aggressive">("standard");
  const [caseHealth, setCaseHealth] = useState<CaseHealth | null>(null);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [taskLabel, setTaskLabel] = useState("idle");
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [dataPanelOpen, setDataPanelOpen] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const initialCaseLoadedRef = useRef(false);

  const loadInvestigations = useCallback(async () => {
    const payload = await apiJson("/api/v1/investigations", undefined, token);
    const items = payload.data.items || [];
    setInvestigations(items);
    return items as Investigation[];
  }, [token]);

  const loadCaseHealth = useCallback(async (id: string) => {
    try {
      const payload = await apiJson(`/api/v1/investigations/${id}/health`, undefined, token);
      setCaseHealth(payload.data.health || null);
    } catch (caught) {
      setCaseHealth(null);
      setError(caught instanceof Error ? caught.message : "Failed to load case health");
    }
  }, [token]);

  const loadGraph = useCallback(async (id: string) => {
    const payload = await apiJson(`/api/v1/investigations/${id}/graph`, undefined, token);
    setActiveInvestigationId(id);
    setGraph(payload.data);
    setSelectedNode(null);
    setOracleNode(null);
    await loadCaseHealth(id);
  }, [loadCaseHealth, token]);

  const clearActiveInvestigation = useCallback(() => {
    setActiveInvestigationId(null);
    setGraph({ nodes: [], edges: [] });
    setSelectedNode(null);
    setOracleNode(null);
    setCaseHealth(null);
    setCurrentTaskId(null);
    setTaskLabel("idle");
    navigate("/graph");
  }, [navigate]);

  const selectInvestigation = useCallback((id: string) => {
    if (!id) {
      clearActiveInvestigation();
      return;
    }
    setError(null);
    void loadGraph(id)
      .then(() => {
        navigate(`/graph?case=${id}`);
        setTerminalLines((previous) => [...previous.slice(-260), { level: "system", message: `Loaded investigation ${id}`, time: new Date().toISOString() }]);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load investigation"));
  }, [clearActiveInvestigation, loadGraph, navigate]);

  useEffect(() => {
    loadInvestigations()
      .then((items) => {
        if (initialCaseLoadedRef.current) return;
        initialCaseLoadedRef.current = true;
        const requestedCase = new URLSearchParams(window.location.search).get("case");
        if (requestedCase && items.some((item) => item.id === requestedCase)) selectInvestigation(requestedCase);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load investigations"));
  }, [loadInvestigations, selectInvestigation]);

  useEffect(() => {
    if (!activeInvestigationId) {
      setCaseHealth(null);
      return undefined;
    }
    const timer = window.setTimeout(() => void loadCaseHealth(activeInvestigationId), 350);
    return () => window.clearTimeout(timer);
  }, [activeInvestigationId, graph.edges.length, graph.nodes.length, loadCaseHealth]);

  useEffect(() => {
    if (!currentTaskId) return undefined;
    const socket = new WebSocket(wsUrl(currentTaskId));
    socket.onmessage = (event) => {
      try { setTerminalLines((previous) => [...previous.slice(-260), JSON.parse(event.data) as TerminalLine]); }
      catch { setTerminalLines((previous) => [...previous.slice(-260), { level: "tool", message: event.data }]); }
    };
    socket.onerror = () => setTerminalLines((previous) => [...previous.slice(-260), { level: "error", message: "WebSocket telemetry connection failed", time: new Date().toISOString() }]);
    return () => socket.close();
  }, [currentTaskId]);

  const createBlankInvestigation = async () => {
    const seed = target.trim() || `Untitled Investigation ${new Date().toLocaleString()}`;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiJson("/api/v1/investigations", { method: "POST", body: JSON.stringify({ target: seed, mode, target_type: target.trim() ? undefined : "case" }) }, token);
      const id = payload.data.investigation_id || payload.data.investigation;
      await loadInvestigations();
      await loadGraph(id);
      navigate(`/graph?case=${id}`);
      setTaskLabel(`blank case / ${seed}`);
      setTerminalLines([{ level: "system", message: `New blank investigation created: ${seed}`, time: new Date().toISOString() }]);
      setDataPanelOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create investigation");
    } finally {
      setLoading(false);
    }
  };

  const deleteActiveInvestigation = async () => {
    const active = investigations.find((item) => item.id === activeInvestigationId) || null;
    if (!active) return;
    const confirmed = window.confirm(`Delete investigation "${caseTitle(active)}" and all graph data?`);
    if (!confirmed) return;
    setLoading(true);
    setError(null);
    try {
      await apiJson(`/api/v1/investigations/${active.id}`, { method: "DELETE" }, token);
      await loadInvestigations();
      clearActiveInvestigation();
      setTerminalLines([{ level: "system", message: `Deleted investigation ${caseTitle(active)}`, time: new Date().toISOString() }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to delete investigation");
    } finally {
      setLoading(false);
    }
  };

  const startInvestigation = async (event: FormEvent) => {
    event.preventDefault();
    if (!target.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiJson("/api/v1/scans/nexusrecon", { method: "POST", body: JSON.stringify({ target: target.trim(), mode }) }, token);
      const id = payload.data.investigation_id;
      setActiveInvestigationId(id);
      setGraph(payload.data.graph || { nodes: [], edges: [] });
      setCurrentTaskId(payload.data.task_id);
      setTaskLabel(`pipeline / ${target.trim()}`);
      setSelectedNode(null);
      setOracleNode(null);
      setTerminalLines([]);
      setTerminalOpen(true);
      setDataPanelOpen(true);
      navigate(`/graph?case=${id}`);
      await loadInvestigations();
      await loadCaseHealth(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to start investigation");
    } finally {
      setLoading(false);
    }
  };

  const rows = useMemo(() => {
    if (!selectedNode) return [];
    return flattenData({
      id: selectedNode.id,
      type: selectedNode.type,
      label: selectedNode.label,
      value: selectedNode.value,
      source: selectedNode.source || "unknown",
      confidence: selectedNode.confidence || "medium",
      created_at: selectedNode.created_at || "",
      data: selectedNode.data || {},
    });
  }, [selectedNode]);

  const activeCase = useMemo(() => investigations.find((item) => item.id === activeInvestigationId) || null, [activeInvestigationId, investigations]);

  return (
    <section className="graph-page">
      {error && <div className="nx-alert graph-alert">{error}</div>}
      <div className="graph-operational-grid">
        <GraphCanvas
          investigationId={activeInvestigationId}
          nodes={graph.nodes}
          edges={graph.edges}
          selectedNode={selectedNode}
          onSelectNode={setSelectedNode}
          onGraphUpdate={setGraph}
          onTaskStart={(taskId, transform, node) => { setCurrentTaskId(taskId); setTaskLabel(`${transform} / ${node.label}`); setTerminalLines([]); setTerminalOpen(true); }}
          onError={setError}
          onSystemLog={(message) => setTerminalLines((previous) => [...previous.slice(-260), { level: "system", message, time: new Date().toISOString() }])}
          onOracleNode={setOracleNode}
          searchTarget={target}
          setSearchTarget={setTarget}
          reconMode={mode}
          setReconMode={setMode}
          onLaunch={startInvestigation}
          isLaunching={loading}
          terminalOpen={terminalOpen}
          setTerminalOpen={setTerminalOpen}
          dataPanelOpen={dataPanelOpen}
          setDataPanelOpen={setDataPanelOpen}
        />
        <CaseDock
          investigations={investigations}
          activeCase={activeCase}
          health={caseHealth}
          onSelect={selectInvestigation}
          onCreateBlank={createBlankInvestigation}
          onDeleteActive={deleteActiveInvestigation}
          onClearActive={clearActiveInvestigation}
          loading={loading}
        />
        <aside className={dataPanelOpen ? "entity-spec" : "entity-spec closed"}>
          <div className="nx-panel-title"><FileJson size={15} />Entity Data</div>
          {selectedNode ? <><h2>{selectedNode.label}</h2><code>{selectedNode.type} / {selectedNode.confidence || "medium"}</code><div className="nx-data-table">{rows.map(([key, value]) => <div className="nx-row" key={`${key}:${value}`}><span>{key}</span><code>{value}</code></div>)}</div></> : <><h2>{activeCase?.target || "No active entity"}</h2><code>{activeCase ? `${activeCase.target_type} / ${activeCase.status}` : "no investigation loaded"}</code><p>Select a case from the investigation dock, create a blank investigation, or launch a new target scan from the toolbar.</p></>}
        </aside>
        <section className={terminalOpen ? "graph-terminal" : "graph-terminal closed"}><header><Terminal size={15} /><strong>Live Terminal</strong><span>{taskLabel}</span></header><div>{terminalLines.map((line, index) => <p className={line.level} key={`${line.time || index}:${index}`}><span>{line.time ? new Date(line.time).toLocaleTimeString() : "--:--:--"}</span><strong>{terminalPrefix(line.level)}</strong><code>{line.message}</code></p>)}{!terminalLines.length && <p><span>00:00:00</span><strong>[SYS]</strong><code>Waiting for telemetry...</code></p>}</div></section>
        {oracleNode && <div className="graph-oracle-popover"><button type="button" onClick={() => setOracleNode(null)}>Close Oracle</button><OraclePanel token={token} investigationId={activeInvestigationId} graph={graph} activeNode={oracleNode} title="Node Oracle" /></div>}
      </div>
    </section>
  );
}

function WorkspacePage({ token, navigate }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [caseName, setCaseName] = useState("");
  const [operator, setOperator] = useState("");
  const [notes, setNotes] = useState("");
  const [brief, setBrief] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [error, setError] = useState<string | null>(null);
  const initialCaseLoadedRef = useRef(false);

  const loadCases = useCallback(async () => {
    const payload = await apiJson("/api/v1/cases", undefined, token);
    const items = payload.data.items || [];
    setCases(items);
    return items as Investigation[];
  }, [token]);

  const selectCase = useCallback(async (item: Investigation) => {
    setActiveId(item.id);
    setCaseName(String(item.meta?.case_name || item.target));
    setOperator(String(item.meta?.assigned_operator || ""));
    setNotes(String(item.meta?.notes || ""));
    setBrief(null);
    const payload = await apiJson(`/api/v1/investigations/${item.id}/graph`, undefined, token);
    setGraph(payload.data);
    navigate(`/workspace?case=${item.id}`);
  }, [navigate, token]);

  useEffect(() => {
    loadCases()
      .then((items) => {
        if (initialCaseLoadedRef.current) return;
        initialCaseLoadedRef.current = true;
        const requestedCase = new URLSearchParams(window.location.search).get("case");
        const selected = requestedCase ? items.find((item) => item.id === requestedCase) : null;
        if (selected) void selectCase(selected);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load cases"));
  }, [loadCases, selectCase]);

  const saveCase = async () => {
    if (!activeId) return;
    await apiJson(`/api/v1/cases/${activeId}`, { method: "PATCH", body: JSON.stringify({ case_name: caseName, assigned_operator: operator, notes }) }, token);
    await loadCases();
  };

  const deleteCase = async (item: Investigation) => {
    const confirmed = window.confirm(`Delete investigation "${caseTitle(item)}" and all graph data?`);
    if (!confirmed) return;
    await apiJson(`/api/v1/investigations/${item.id}`, { method: "DELETE" }, token);
    const items = await loadCases();
    if (activeId === item.id) {
      setActiveId(null);
      setCaseName("");
      setOperator("");
      setNotes("");
      setBrief(null);
      setGraph({ nodes: [], edges: [] });
      navigate("/workspace");
    }
    if (!items.length) setError(null);
  };

  const autoBrief = async () => {
    if (!activeId) return;
    const payload = await apiJson("/api/v1/oracle/briefing", { method: "POST", body: JSON.stringify({ investigation_id: activeId, graph_state: graph }) }, token);
    setBrief(`${payload.data.executive_summary}\n\nThreat Assessment:\n${payload.data.threat_assessment}`);
  };

  return (
    <section className="workspace-page">
      <header className="page-header"><div><span className="micro-label">Workspace</span><h1>Case Management</h1></div><div className="page-actions"><button className="nx-secondary" type="button" onClick={() => navigate("/graph")}><Plus size={15} />New Investigation</button><button className="nx-secondary" type="button" onClick={autoBrief} disabled={!activeId}><Bot size={15} />AI Auto-Briefing</button></div></header>
      {error && <div className="nx-alert">{error}</div>}
      <div className="workspace-grid">
        <aside className="case-strip large"><strong>Case Folders</strong>{cases.map((item) => <div className={item.id === activeId ? "case-list-item active" : "case-list-item"} key={item.id}><button type="button" onClick={() => void selectCase(item)}>{caseTitle(item)}<span>{item.target_type} / {item.status}</span></button><button className="case-delete-button" type="button" onClick={() => void deleteCase(item)} title="Delete investigation"><Trash2 size={13} /></button></div>)}{!cases.length && <span>No cases yet. Create one from Network Graph.</span>}</aside>
        <section className="case-editor"><label>Case Name<input value={caseName} onChange={(event) => setCaseName(event.target.value)} /></label><label>Assigned Operator<input value={operator} onChange={(event) => setOperator(event.target.value)} /></label><label>Investigation Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Markdown notes" /></label><button className="nx-primary" type="button" onClick={saveCase} disabled={!activeId}>Save Case</button>{brief && <pre className="brief-box">{brief}</pre>}</section>
        <OraclePanel token={token} investigationId={activeId} graph={graph} title="Workspace Oracle" />
      </div>
    </section>
  );
}

function SettingsPage({ token }: PageProps) {
  const [settings, setSettings] = useState<Record<string, any>>({ llm: { provider: "local", endpoint: "http://localhost:11434", model: "llama3.1" }, api_keys: {} });
  const [saved, setSaved] = useState(false);
  useEffect(() => { apiJson("/api/v1/settings", undefined, token).then((payload) => setSettings(payload.data.settings || settings)).catch(() => undefined); }, [token]);
  const update = (path: string[], value: string) => setSettings((current) => { const next = { ...current, llm: { ...(current.llm || {}) }, api_keys: { ...(current.api_keys || {}) } }; let target = next as any; path.slice(0, -1).forEach((part) => { target[part] = { ...(target[part] || {}) }; target = target[part]; }); target[path[path.length - 1]] = value; return next; });
  const save = async () => { await apiJson("/api/v1/settings", { method: "PUT", body: JSON.stringify({ settings }) }, token); setSaved(true); window.setTimeout(() => setSaved(false), 1800); };
  return <section className="settings-page"><header className="page-header"><div><span className="micro-label">Settings</span><h1>BYOK and LLM Engine</h1></div><button className="nx-primary" type="button" onClick={save}>Save Settings</button></header><div className="settings-grid"><div className="command-card"><h2>AI Engine Config</h2><label>Provider<select value={settings.llm?.provider || "local"} onChange={(event) => update(["llm", "provider"], event.target.value)}><option value="local">Rule-based local</option><option value="ollama">Ollama</option><option value="openai">OpenAI compatible</option><option value="anthropic">Anthropic</option></select></label><label>Endpoint<input value={settings.llm?.endpoint || ""} onChange={(event) => update(["llm", "endpoint"], event.target.value)} placeholder="http://localhost:11434" /></label><label>Model<input value={settings.llm?.model || ""} onChange={(event) => update(["llm", "model"], event.target.value)} placeholder="llama3.1" /></label><label>Remote API Key<input type="password" value={settings.llm?.api_key || ""} onChange={(event) => update(["llm", "api_key"], event.target.value)} /></label></div><div className="command-card"><h2>Third-Party API Keys</h2>{["shodan", "intelx", "virustotal"].map((key) => <label key={key}>{key.toUpperCase()}<input type="password" value={settings.api_keys?.[key] || ""} onChange={(event) => update(["api_keys", key], event.target.value)} /></label>)}<p>Keys are optional. Core NexusIntel recon remains free/public-source.</p></div></div>{saved && <div className="save-toast">Settings saved locally.</div>}</section>;
}

function OraclePage({ token }: PageProps) {
  return <section className="oracle-page"><header className="page-header"><div><span className="micro-label">AI Oracle</span><h1>Agentic Intelligence Interface</h1></div></header><OraclePanel token={token} title="Standalone Oracle" /></section>;
}

function AccountPage({ user }: PageProps) {
  return <section className="account-page"><header className="page-header"><div><span className="micro-label">Account</span><h1>Operator Profile</h1></div></header><div className="command-card"><UserCircle size={24} /><h2>{user}</h2><p>Local operator session. Logout clears the browser token and returns to the terminal login screen.</p></div></section>;
}

function routeFromLocation(): string {
  return window.location.pathname === "/" ? "/dashboard" : window.location.pathname;
}

function routeFromPath(path: string): string {
  const clean = path.split("?")[0] || "/dashboard";
  return clean === "/" ? "/dashboard" : clean;
}

export default function CommandCenter() {
  const [session, setSession] = useState<SessionState>(() => readSession());
  const [route, setRoute] = useState(() => routeFromLocation());
  const [collapsed, setCollapsed] = useState(false);

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setRoute(routeFromPath(path));
  }, []);

  useEffect(() => {
    const onPop = () => setRoute(routeFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const login = (next: SessionState) => { saveSession(next); setSession(next); navigate("/dashboard"); };
  const logout = () => { clearSession(); setSession({ token: null, user: null }); navigate("/login"); };

  if (route === "/login" || !session.token) return <LoginPage onLogin={login} />;

  const props: PageProps = { token: session.token, user: session.user || "operator", navigate };
  let page = <DashboardHome {...props} />;
  if (route === "/workspace") page = <WorkspacePage {...props} />;
  if (route === "/graph") page = <GraphHub {...props} />;
  if (route === "/oracle") page = <OraclePage {...props} />;
  if (route === "/settings") page = <SettingsPage {...props} />;
  if (route === "/account") page = <AccountPage {...props} />;

  return <Shell route={route} user={session.user || "operator"} collapsed={collapsed} setCollapsed={setCollapsed} navigate={navigate} logout={logout}>{page}</Shell>;
}
