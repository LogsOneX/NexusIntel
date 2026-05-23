import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Bot,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Database,
  FileJson,
  GitBranch,
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
import PresenceBar from "./PresenceBar";

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

type TransformDefinition = {
  id: string;
  label: string;
  description: string;
  input_types: string[];
  output_types: string[];
  adapter_id: string;
  requires_api_key: boolean;
  required_keys?: string[];
  enabled: boolean;
  disabled_reason?: string | null;
  legal_note?: string;
};

type EvidenceRecord = {
  id: string;
  investigation_id: string;
  entity_id?: string | null;
  source: string;
  uri: string;
  sha256: string;
  content_type: string;
  size_bytes: number;
  meta?: Record<string, unknown>;
  created_at: string;
  payload_preview?: string | null;
  payload_truncated?: boolean;
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

type CoverageMatrix = {
  columns: string[];
  rows: string[];
  matrix: Record<string, Record<string, number>>;
};

type AnalystPipeline = {
  generated_at: string;
  selected_entity: {
    entity_id?: string;
    entity_type: string;
    confidence_baseline: number;
    confidence_label?: string;
    source?: string;
    source_url?: string;
    timestamp?: string;
    raw_evidence_ref?: string;
    confidence_reason?: string;
    legal_note?: string;
    source_coverage_status: string[];
    available_transforms: TransformDefinition[];
    recommended_transforms: TransformDefinition[];
    disabled_transforms: TransformDefinition[];
    noise?: { is_noise: boolean; noise_score: number; reasons: string[] };
  };
  coverage_matrix: CoverageMatrix;
  noise_killer: { filtered_count: number; items: Array<Record<string, unknown>> };
  correlations: Array<Record<string, unknown>>;
  lead_queue: {
    strongest_pivots: Array<Record<string, unknown>>;
    unverified_interesting_pivots: Array<Record<string, unknown>>;
    possible_same_actor_links: Array<Record<string, unknown>>;
    contradictions: Array<Record<string, unknown>>;
    high_value_next_actions: Array<Record<string, unknown>>;
  };
  evidence_summary: { count: number; sources: Record<string, number>; hashes: string[] };
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

async function downloadFile(path: string, token: string | null, fallbackName: string) {
  const response = await fetch(`${API_BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename=([^;]+)/i);
  const fileName = match ? match[1].replaceAll('"', '') : fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
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

function classifyEntityValue(value: string): string {
  const target = value.trim();
  if (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(target)) return "email";
  if (/^\+[1-9]\d{7,14}$/.test(target.replace(/[\s-]/g, ""))) return "phone";
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(target) || target.includes(":")) return "ip";
  if (/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i.test(target.replace(/^https?:\/\//, "").split("/")[0])) return "domain";
  return target.includes(" ") ? "name" : "username";
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
  const [analystPipeline, setAnalystPipeline] = useState<AnalystPipeline | null>(null);
  const [transformRegistry, setTransformRegistry] = useState<TransformDefinition[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceRecord[]>([]);
  const [evidenceDrawer, setEvidenceDrawer] = useState<EvidenceRecord | null>(null);
  const [transformLoading, setTransformLoading] = useState<string | null>(null);
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

  const loadTransformRegistry = useCallback(async () => {
    const payload = await apiJson("/api/v1/transforms/registry", undefined, token);
    setTransformRegistry(payload.data.transforms || []);
  }, [token]);

  const loadEvidence = useCallback(async (id: string) => {
    const payload = await apiJson(`/api/v1/investigations/${id}/evidence`, undefined, token);
    setEvidenceItems(payload.data.items || []);
  }, [token]);

  const loadAnalystPipeline = useCallback(async (id: string, entityId?: string | null) => {
    const suffix = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : "";
    const payload = await apiJson(`/api/v1/investigations/${id}/analyst-pipeline${suffix}`, undefined, token);
    setAnalystPipeline(payload.data.analyst_pipeline || null);
  }, [token]);

  const loadGraph = useCallback(async (id: string) => {
    const payload = await apiJson(`/api/v1/investigations/${id}/graph`, undefined, token);
    setActiveInvestigationId(id);
    setGraph(payload.data);
    setSelectedNode(null);
    setOracleNode(null);
    setEvidenceDrawer(null);
    await loadCaseHealth(id);
    await loadEvidence(id);
    await loadAnalystPipeline(id, null);
  }, [loadAnalystPipeline, loadCaseHealth, loadEvidence, token]);

  const clearActiveInvestigation = useCallback(() => {
    setActiveInvestigationId(null);
    setGraph({ nodes: [], edges: [] });
    setSelectedNode(null);
    setOracleNode(null);
    setCaseHealth(null);
    setAnalystPipeline(null);
    setEvidenceItems([]);
    setEvidenceDrawer(null);
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
    loadTransformRegistry().catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load transform registry"));
  }, [loadTransformRegistry]);

  useEffect(() => {
    if (!activeInvestigationId) {
      setCaseHealth(null);
      return undefined;
    }
    const timer = window.setTimeout(() => void loadCaseHealth(activeInvestigationId), 350);
    return () => window.clearTimeout(timer);
  }, [activeInvestigationId, graph.edges.length, graph.nodes.length, loadCaseHealth]);

  useEffect(() => {
    if (!activeInvestigationId) {
      setAnalystPipeline(null);
      return undefined;
    }
    const timer = window.setTimeout(() => void loadAnalystPipeline(activeInvestigationId, selectedNode?.id || null).catch(() => undefined), 420);
    return () => window.clearTimeout(timer);
  }, [activeInvestigationId, graph.edges.length, graph.nodes.length, loadAnalystPipeline, selectedNode?.id]);

  useEffect(() => {
    if (!currentTaskId) return undefined;
    let stopped = false;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const taskPayload = await apiJson(`/api/v1/tasks/${currentTaskId}`, undefined, token);
        const investigationId = taskPayload.data.investigation_id || activeInvestigationId;
        if (investigationId) {
          const graphPayload = await apiJson(`/api/v1/tasks/${currentTaskId}/graph`, undefined, token);
          if (!stopped) setGraph(graphPayload.data || { nodes: [], edges: [] });
        }
        if (["completed", "failed"].includes(taskPayload.data.status)) {
          if (!stopped && investigationId) void loadCaseHealth(investigationId);
          return;
        }
        if (!stopped) timer = window.setTimeout(refresh, 1400);
      } catch (caught) {
        if (!stopped) {
          setError(caught instanceof Error ? caught.message : "Failed to refresh running graph");
          timer = window.setTimeout(refresh, 3000);
        }
      }
    };
    void refresh();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activeInvestigationId, currentTaskId, loadCaseHealth, token]);

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

  const addSeedEntity = async (value: string, entityMode: "passive" | "standard" | "aggressive") => {
    const clean = value.trim();
    if (!clean) return;
    const kind = classifyEntityValue(clean);
    setLoading(true);
    setError(null);
    try {
      if (!activeInvestigationId) {
        const payload = await apiJson(
          "/api/v1/investigations",
          { method: "POST", body: JSON.stringify({ target: clean, mode: entityMode, target_type: kind }) },
          token,
        );
        const id = payload.data.investigation_id || payload.data.investigation;
        setActiveInvestigationId(id);
        setGraph(payload.data.graph || { nodes: [], edges: [] });
        setSelectedNode(payload.data.root_node || null);
        setOracleNode(null);
        setCurrentTaskId(null);
        setTaskLabel(`manual entity / ${clean}`);
        setTerminalLines((previous) => [...previous.slice(-260), { level: "system", message: `Added ${kind} entity without lookup: ${clean}`, time: new Date().toISOString() }]);
        setDataPanelOpen(true);
        navigate(`/graph?case=${id}`);
        await loadInvestigations();
        await loadCaseHealth(id);
        await loadEvidence(id);
        await loadAnalystPipeline(id, payload.data.root_node?.id || null);
        return;
      }

      const payload = await apiJson(
        "/api/v1/entities",
        {
          method: "POST",
          body: JSON.stringify({
            investigation_id: activeInvestigationId,
            type: kind,
            label: clean,
            value: clean,
            source_id: selectedNode?.id || null,
            relationship_type: selectedNode ? "manual_pivot" : "manual_seed",
            data: { created_from: "toolbar_add_entity", mode: entityMode },
          }),
        },
        token,
      );
      setGraph(payload.data.graph || { nodes: [], edges: [] });
      setSelectedNode(payload.data.node || null);
      setTaskLabel(`manual entity / ${clean}`);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "system", message: `Added ${kind} entity without lookup: ${clean}`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadEvidence(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, payload.data.node?.id || selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to add entity");
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
      await loadEvidence(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to start investigation");
    } finally {
      setLoading(false);
    }
  };

  const selectedTransforms = useMemo(() => {
    if (!selectedNode) return [];
    return transformRegistry.filter((item) => item.input_types.includes(selectedNode.type) || item.input_types.includes("*"));
  }, [selectedNode, transformRegistry]);

  const selectedEvidenceRefs = useMemo(() => {
    if (!selectedNode) return [] as EvidenceRecord[];
    const data = selectedNode.data || {};
    const artifact = (data.artifact || {}) as Record<string, unknown>;
    const refIds = new Set([data.raw_evidence_ref, artifact.raw_evidence_ref].filter(Boolean).map(String));
    return evidenceItems.filter((item) => item.entity_id === selectedNode.id || refIds.has(item.id));
  }, [evidenceItems, selectedNode]);

  const openEvidence = useCallback(async (id: string) => {
    try {
      const payload = await apiJson(`/api/v1/evidence/${id}`, undefined, token);
      setEvidenceDrawer(payload.data.evidence || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load raw evidence");
    }
  }, [token]);

  const runRegisteredTransform = useCallback(async (transformId: string) => {
    if (!activeInvestigationId || !selectedNode) return;
    setTransformLoading(transformId);
    setError(null);
    try {
      const payload = await apiJson(
        "/api/v1/transforms/run",
        { method: "POST", body: JSON.stringify({ investigation_id: activeInvestigationId, node_id: selectedNode.id, transform_id: transformId, options: { mode } }) },
        token,
      );
      setGraph(payload.data.graph || { nodes: [], edges: [] });
      setCurrentTaskId(payload.data.run_id || null);
      setTaskLabel(`${transformId} / ${selectedNode.label}`);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Registered transform completed: ${transformId}`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadEvidence(activeInvestigationId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Registered transform failed");
    } finally {
      setTransformLoading(null);
    }
  }, [activeInvestigationId, loadCaseHealth, loadEvidence, mode, selectedNode, token]);

  const pendingEntityType = useMemo(() => classifyEntityValue(target), [target]);

  const pendingTransforms = useMemo(() => {
    if (!target.trim()) return [] as TransformDefinition[];
    return transformRegistry.filter((item) => item.input_types.includes(pendingEntityType) || item.input_types.includes("*"));
  }, [pendingEntityType, target, transformRegistry]);

  const runCorrelationEngine = useCallback(async () => {
    if (!activeInvestigationId) return;
    try {
      const payload = await apiJson(`/api/v1/investigations/${activeInvestigationId}/correlate`, { method: "POST" }, token);
      setGraph(payload.data.graph || { nodes: [], edges: [] });
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Correlation engine created ${(payload.data.created || []).length} possible_same_actor edge(s)`, time: new Date().toISOString() }]);
      await loadAnalystPipeline(activeInvestigationId, selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Correlation engine failed");
    }
  }, [activeInvestigationId, loadAnalystPipeline, selectedNode?.id, token]);

  const exportPacket = useCallback(async (format: "html" | "pdf" | "json" | "csv" | "graph_json") => {
    if (!activeInvestigationId) return;
    try {
      await downloadFile(`/api/v1/investigations/${activeInvestigationId}/exports/analyst-packet?format=${format}`, token, `nexusintel-${activeInvestigationId}.${format}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Export failed");
    }
  }, [activeInvestigationId, token]);

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
        <PresenceBar />
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
          onAddSeed={addSeedEntity}
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
          {selectedNode ? (
            <>
              <h2>{selectedNode.label}</h2>
              <code>{selectedNode.type} / {selectedNode.confidence || "medium"}</code>
              <div className="entity-drawer-section analyst-enrichment-panel">
                <strong>Analyst Enrichment</strong>
                <div className="analyst-kpi-grid">
                  <span><b>{analystPipeline?.selected_entity?.entity_type || selectedNode.type}</b><small>Type</small></span>
                  <span><b>{analystPipeline?.selected_entity?.confidence_baseline ?? "--"}%</b><small>Baseline</small></span>
                  <span><b>{analystPipeline?.evidence_summary?.count ?? evidenceItems.length}</b><small>Evidence</small></span>
                </div>
                <p>{analystPipeline?.selected_entity?.confidence_reason || "Run an evidence-backed transform to calculate confidence and source coverage."}</p>
                <code>{analystPipeline?.selected_entity?.source_url || "source_url pending"}</code>
                <code>{analystPipeline?.selected_entity?.raw_evidence_ref ? `raw:${analystPipeline.selected_entity.raw_evidence_ref}` : "raw evidence pending"}</code>
                <small>{analystPipeline?.selected_entity?.legal_note || "Legal note pending evidence-backed collection."}</small>
                <div className="coverage-status-list">{(analystPipeline?.selected_entity?.source_coverage_status || []).map((item) => <span key={item}>{item}</span>)}</div>
              </div>
              <div className="entity-drawer-section lead-queue-panel">
                <strong>Lead Queue</strong>
                {(analystPipeline?.lead_queue?.strongest_pivots || []).slice(0, 3).map((item) => <span key={`strong-${String(item.node_id)}`}>Strong: {String(item.label)} / {String(item.reason)}</span>)}
                {(analystPipeline?.lead_queue?.unverified_interesting_pivots || []).slice(0, 3).map((item) => <span key={`weak-${String(item.node_id)}`}>Verify: {String(item.label)} / {String(item.reason)}</span>)}
                {(analystPipeline?.lead_queue?.possible_same_actor_links || []).slice(0, 3).map((item, index) => <span key={`same-${index}`}>Possible same actor: {String(item.confidence_level)}% / {String((item.reasons as unknown[])?.[0] || "shared feature")}</span>)}
                {(analystPipeline?.lead_queue?.contradictions || []).slice(0, 3).map((item, index) => <span className="danger-line" key={`contra-${index}`}>Contradiction: {String(item.label)} / {String(item.reason)}</span>)}
                <button type="button" onClick={() => void runCorrelationEngine()} disabled={!activeInvestigationId}><GitBranch size={13} /> Build possible_same_actor links</button>
              </div>
              <div className="entity-drawer-section coverage-matrix-panel">
                <strong>OSINT Coverage Matrix</strong>
                <div className="coverage-matrix-scroll"><table><tbody>{(analystPipeline?.coverage_matrix?.rows || []).map((row) => <tr key={row}><th>{row}</th>{(analystPipeline?.coverage_matrix?.columns || []).map((column) => <td key={`${row}-${column}`}>{analystPipeline?.coverage_matrix?.matrix?.[row]?.[column] || 0}</td>)}</tr>)}</tbody></table></div>
              </div>
              <div className="entity-drawer-section export-packet-panel">
                <strong>Export Analyst Packet</strong>
                <div className="packet-buttons">
                  <button type="button" onClick={() => void exportPacket("pdf")}>PDF</button>
                  <button type="button" onClick={() => void exportPacket("html")}>HTML</button>
                  <button type="button" onClick={() => void exportPacket("json")}>JSON Evidence</button>
                  <button type="button" onClick={() => void exportPacket("csv")}>CSV IOCs</button>
                  <button type="button" onClick={() => void exportPacket("graph_json")}>Graph JSON</button>
                </div>
              </div>
              <div className="entity-drawer-section">
                <strong>Evidence</strong>
                {selectedEvidenceRefs.length ? selectedEvidenceRefs.map((item) => (
                  <button className="evidence-ref-button" key={item.id} type="button" onClick={() => void openEvidence(item.id)}>
                    <span>{item.source}</span>
                    <code>{item.sha256.slice(0, 16)}</code>
                  </button>
                )) : <p>No raw evidence linked yet. Run a registry transform to collect proof-backed artifacts.</p>}
              </div>
              {evidenceDrawer && (
                <div className="entity-drawer-section raw-evidence-preview">
                  <strong>Raw Evidence Preview</strong>
                  <span>{evidenceDrawer.source} / {evidenceDrawer.content_type}</span>
                  <code>sha256:{evidenceDrawer.sha256}</code>
                  <pre>{evidenceDrawer.payload_preview || "No preview available"}</pre>
                </div>
              )}
              <div className="entity-drawer-section transform-library-panel">
                <strong>Transform Library</strong>
                {selectedTransforms.length ? selectedTransforms.map((item) => (
                  <button key={item.id} type="button" disabled={!item.enabled || transformLoading === item.id} onClick={() => void runRegisteredTransform(item.id)}>
                    <span>{item.label}</span>
                    <small>{item.description}</small>
                    <code>{item.enabled ? item.output_types.join(", ") : item.disabled_reason || "disabled"}</code>
                  </button>
                )) : <p>No registered transform accepts this entity type yet.</p>}
              </div>
              <div className="nx-data-table">{rows.map(([key, value]) => <div className="nx-row" key={`${key}:${value}`}><span>{key}</span><code>{value}</code></div>)}</div>
            </>
          ) : (
            <>
              <h2>{activeCase?.target || "No active entity"}</h2>
              <code>{activeCase ? `${activeCase.target_type} / ${activeCase.status}` : "no investigation loaded"}</code>
              {target.trim() ? (
                <div className="entity-drawer-section analyst-enrichment-panel">
                  <strong>Pending Entity Preview</strong>
                  <div className="analyst-kpi-grid">
                    <span><b>{pendingEntityType}</b><small>Type</small></span>
                    <span><b>40%</b><small>Baseline</small></span>
                    <span><b>{pendingTransforms.filter((item) => item.enabled).length}</b><small>Available</small></span>
                  </div>
                  <p>Adding the entity will not run lookup. Choose an evidence-backed transform after it exists on the graph.</p>
                  <strong>Recommended</strong>
                  {pendingTransforms.filter((item) => item.enabled).slice(0, 4).map((item) => <span key={item.id}>{item.label}: {item.output_types.join(", ")}</span>)}
                  <strong>Disabled</strong>
                  {pendingTransforms.filter((item) => !item.enabled).slice(0, 4).map((item) => <span key={item.id}>{item.label}: {item.disabled_reason}</span>)}
                </div>
              ) : <p>Select a case from the investigation dock, create a blank investigation, or launch a new target scan from the toolbar.</p>}
            </>
          )}
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
  return <section className="settings-page"><header className="page-header"><div><span className="micro-label">Settings</span><h1>BYOK and LLM Engine</h1></div><button className="nx-primary" type="button" onClick={save}>Save Settings</button></header><div className="settings-grid"><div className="command-card"><h2>AI Engine Config</h2><label>Provider<select value={settings.llm?.provider || "local"} onChange={(event) => update(["llm", "provider"], event.target.value)}><option value="local">Rule-based local</option><option value="ollama">Ollama</option><option value="openai">OpenAI compatible</option><option value="anthropic">Anthropic</option></select></label><label>Endpoint<input value={settings.llm?.endpoint || ""} onChange={(event) => update(["llm", "endpoint"], event.target.value)} placeholder="http://localhost:11434" /></label><label>Model<input value={settings.llm?.model || ""} onChange={(event) => update(["llm", "model"], event.target.value)} placeholder="llama3.1" /></label><label>Remote API Key<input type="password" value={settings.llm?.api_key || ""} onChange={(event) => update(["llm", "api_key"], event.target.value)} /></label></div><div className="command-card"><h2>Third-Party API Keys</h2>{["github", "hibp", "urlscan", "google_maps", "shodan", "censys", "intelx", "virustotal", "twilio", "numverify"].map((key) => <label key={key}>{key.toUpperCase()}<input type="password" value={settings.api_keys?.[key] || ""} onChange={(event) => update(["api_keys", key], event.target.value)} /></label>)}<p>Keys are optional. Core NexusIntel recon remains free/public-source.</p></div></div>{saved && <div className="save-toast">Settings saved locally.</div>}</section>;
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
