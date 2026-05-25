import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { KeyRound, Shield } from "lucide-react";
import GraphCanvas from "./GraphCanvas";
import OraclePanel from "./OraclePanel";
import InvestigatorPanel from "./investigator/InvestigatorPanel";
import AppShell from "../layouts/AppShell";
import DashboardPage from "../pages/DashboardPage";
import WorkspacePage from "../pages/WorkspacePage";
import SettingsPage from "../pages/SettingsPage";
import OraclePage from "../pages/OraclePage";
import AccountPage from "../pages/AccountPage";
import GraphPage from "../pages/GraphPage";
import IdentitySearchPage from "../pages/IdentitySearchPage";
import EvidenceVaultPage from "../pages/EvidenceVaultPage";
import ReportsPage from "../pages/ReportsPage";
import ThreatWatchlistPage from "../pages/ThreatWatchlistPage";
import TransformLibraryPage from "../pages/TransformLibraryPage";
import CaseDock from "./cases/CaseDock";
import EntityInspector from "./entity/EntityInspector";
import EvidenceDrawer from "./evidence/EvidenceDrawer";
import ConfirmDialog from "./common/ConfirmDialog";
import CommandPalette from "./common/CommandPalette";
import GraphWorkspaceLayout from "../layouts/GraphWorkspaceLayout";
import GraphTopBar from "./graph/GraphTopBar";
import GraphCanvasStage from "./graph/GraphCanvasStage";
import CaseDockDrawer from "./cases/CaseDockDrawer";
import InspectorDrawer from "./entity/InspectorDrawer";
import TelemetryDrawer from "./terminal/TelemetryDrawer";
import EntityPaletteDrawer from "./entity/EntityPaletteDrawer";
import AddEntityDialog from "./entity/AddEntityDialog";
import { FALLBACK_TRANSFORMS } from "./transforms/TransformLibrary";
import { apiJson, downloadFile, wsUrl } from "../lib/api";
import { clearSession, readLocalJson, readSession, saveSession, writeLocalJson } from "../lib/storage";
import { caseTitle } from "../lib/format";
import { classifyEntityValue, evidenceRefsForNode } from "../lib/graph";
import type { AnalystPipeline, ApiNode, CaseHealth, CommandItem, EvidenceRecord, GraphPayload, Investigation, PageProps, SessionState, TerminalLine, TransformDefinition } from "../lib/types";

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
      const payload = await apiJson<any>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      onLogin({ token: payload.data.token, user: payload.data.user });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-screen premium-login">
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

function normalizeGraphPayload(payload: any): GraphPayload {
  return {
    nodes: Array.isArray(payload?.nodes) ? payload.nodes : [],
    edges: Array.isArray(payload?.edges) ? payload.edges : [],
    leads: Array.isArray(payload?.leads) ? payload.leads : [],
    noise: Array.isArray(payload?.noise) ? payload.noise : [],
    compliance: Array.isArray(payload?.compliance) ? payload.compliance : [],
    metadata: payload?.metadata || {},
  };
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
  const [transformRegistry, setTransformRegistry] = useState<TransformDefinition[]>(FALLBACK_TRANSFORMS);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceRecord[]>([]);
  const [evidenceDrawer, setEvidenceDrawer] = useState<EvidenceRecord | null>(null);
  const [transformLoading, setTransformLoading] = useState<string | null>(null);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [taskLabel, setTaskLabel] = useState("idle");
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [terminalOpen, setTerminalOpen] = useState(() => readLocalJson("nexus.graph.terminalOpen", false));
  const [dataPanelOpen, setDataPanelOpen] = useState(() => readLocalJson("nexus.graph.inspectorOpen", false));
  const [caseDockOpen, setCaseDockOpen] = useState(() => readLocalJson("nexus.graph.caseDockOpen", false));
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addDialogType, setAddDialogType] = useState("username");
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [investigatorOpen, setInvestigatorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleteCase, setDeleteCase] = useState<Investigation | null>(null);
  const initialCaseLoadedRef = useRef(false);

  const loadInvestigations = useCallback(async () => {
    const payload = await apiJson<any>("/api/v1/investigations", undefined, token);
    const items = payload.data.items || [];
    setInvestigations(items);
    return items as Investigation[];
  }, [token]);

  const loadCaseHealth = useCallback(async (id: string) => {
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${id}/health`, undefined, token);
      setCaseHealth(payload.data.health || null);
    } catch (caught) {
      setCaseHealth(null);
      setError(caught instanceof Error ? caught.message : "Failed to load case health");
    }
  }, [token]);

  const loadTransformRegistry = useCallback(async () => {
    try {
      const payload = await apiJson<any>("/api/v1/transforms/registry", undefined, token);
      const transforms = payload.data.transforms || [];
      setTransformRegistry(transforms.length ? transforms : FALLBACK_TRANSFORMS);
    } catch {
      setTransformRegistry(FALLBACK_TRANSFORMS);
    }
  }, [token]);

  const loadEvidence = useCallback(async (id: string) => {
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${id}/evidence`, undefined, token);
      setEvidenceItems(payload.data.items || []);
    } catch {
      setEvidenceItems([]);
    }
  }, [token]);

  const loadAnalystPipeline = useCallback(async (id: string, entityId?: string | null) => {
    try {
      const suffix = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : "";
      const payload = await apiJson<any>(`/api/v1/investigations/${id}/analyst-pipeline${suffix}`, undefined, token);
      setAnalystPipeline(payload.data.analyst_pipeline || null);
    } catch {
      setAnalystPipeline(null);
    }
  }, [token]);

  const loadGraph = useCallback(async (id: string) => {
    const payload = await apiJson<any>(`/api/v1/investigations/${id}/graph`, undefined, token);
    setActiveInvestigationId(id);
    setGraph(normalizeGraphPayload(payload.data));
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
    loadInvestigations().then((items) => {
      if (initialCaseLoadedRef.current) return;
      initialCaseLoadedRef.current = true;
      const requestedCase = new URLSearchParams(window.location.search).get("case");
      if (requestedCase && items.some((item) => item.id === requestedCase)) selectInvestigation(requestedCase);
    }).catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load investigations"));
  }, [loadInvestigations, selectInvestigation]);

  useEffect(() => { void loadTransformRegistry(); }, [loadTransformRegistry]);

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
    const timer = window.setTimeout(() => void loadAnalystPipeline(activeInvestigationId, selectedNode?.id || null), 420);
    return () => window.clearTimeout(timer);
  }, [activeInvestigationId, graph.edges.length, graph.nodes.length, loadAnalystPipeline, selectedNode?.id]);

  useEffect(() => {
    if (!currentTaskId) return undefined;
    let stopped = false;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const taskPayload = await apiJson<any>(`/api/v1/tasks/${currentTaskId}`, undefined, token);
        const investigationId = taskPayload.data.investigation_id || activeInvestigationId;
        if (investigationId) {
          const graphPayload = await apiJson<any>(`/api/v1/tasks/${currentTaskId}/graph`, undefined, token);
          if (!stopped) setGraph(normalizeGraphPayload(graphPayload.data));
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
    return () => { stopped = true; if (timer) window.clearTimeout(timer); };
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
      const payload = await apiJson<any>("/api/v1/investigations", { method: "POST", body: JSON.stringify({ target: seed, mode, target_type: target.trim() ? undefined : "case" }) }, token);
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

  const confirmDeleteActive = async () => {
    const active = deleteCase;
    if (!active) return;
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
      setDeleteCase(null);
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
        const payload = await apiJson<any>("/api/v1/investigations", { method: "POST", body: JSON.stringify({ target: clean, mode: entityMode, target_type: kind }) }, token);
        const id = payload.data.investigation_id || payload.data.investigation;
        setActiveInvestigationId(id);
        setGraph(normalizeGraphPayload(payload.data.graph));
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
      const payload = await apiJson<any>("/api/v1/entities", { method: "POST", body: JSON.stringify({ investigation_id: activeInvestigationId, type: kind, label: clean, value: clean, source_id: selectedNode?.id || null, relationship_type: selectedNode ? "manual_pivot" : "manual_seed", data: { created_from: "toolbar_add_entity", mode: entityMode } }) }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
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

  const startLookupValue = async (value: string, lookupMode: "passive" | "standard" | "aggressive" = mode) => {
    const clean = value.trim();
    if (!clean) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiJson<any>("/api/v1/scans/nexusrecon", { method: "POST", body: JSON.stringify({ target: clean, mode: lookupMode }) }, token);
      const id = payload.data.investigation_id;
      setActiveInvestigationId(id);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setCurrentTaskId(payload.data.task_id);
      setTaskLabel(`pipeline / ${clean}`);
      setSelectedNode(null);
      setOracleNode(null);
      setTerminalLines([]);
      setTerminalOpen(true);
      setDataPanelOpen(false);
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

  const startInvestigation = async (event: FormEvent) => {
    event.preventDefault();
    await startLookupValue(target, mode);
  };

  const selectedTransforms = useMemo(() => {
    if (!selectedNode) return [];
    return transformRegistry.filter((item) => item.input_types.includes(selectedNode.type) || item.input_types.includes("*"));
  }, [selectedNode, transformRegistry]);

  const selectedEvidenceRefs = useMemo(() => {
    if (!selectedNode) return [] as EvidenceRecord[];
    const refIds = new Set(evidenceRefsForNode(selectedNode));
    return evidenceItems.filter((item) => item.entity_id === selectedNode.id || refIds.has(item.id));
  }, [evidenceItems, selectedNode]);

  const openEvidence = useCallback(async (id: string) => {
    try {
      const payload = await apiJson<any>(`/api/v1/evidence/${id}`, undefined, token);
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
      const payload = await apiJson<any>("/api/v1/transforms/run", { method: "POST", body: JSON.stringify({ investigation_id: activeInvestigationId, node_id: selectedNode.id, transform_id: transformId, options: { mode } }) }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setCurrentTaskId(payload.data.run_id || null);
      setTaskLabel(`${transformId} / ${selectedNode.label}`);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Registered transform completed: ${transformId}`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadEvidence(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, selectedNode.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Registered transform failed");
    } finally {
      setTransformLoading(null);
    }
  }, [activeInvestigationId, loadAnalystPipeline, loadCaseHealth, loadEvidence, mode, selectedNode, token]);

  const pendingEntityType = useMemo(() => classifyEntityValue(target), [target]);
  const pendingTransforms = useMemo(() => {
    if (!target.trim()) return [] as TransformDefinition[];
    return transformRegistry.filter((item) => item.input_types.includes(pendingEntityType) || item.input_types.includes("*"));
  }, [pendingEntityType, target, transformRegistry]);

  const runCorrelationEngine = useCallback(async () => {
    if (!activeInvestigationId) return;
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${activeInvestigationId}/correlate`, { method: "POST" }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Correlation engine created ${(payload.data.created || []).length} possible_same_actor edge(s)`, time: new Date().toISOString() }]);
      await loadAnalystPipeline(activeInvestigationId, selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Correlation engine failed");
    }
  }, [activeInvestigationId, loadAnalystPipeline, selectedNode?.id, token]);

  const promoteLead = useCallback(async (leadId: string) => {
    if (!activeInvestigationId) return;
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${activeInvestigationId}/leads/${leadId}/promote`, { method: "POST" }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setSelectedNode(payload.data.node || null);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Promoted candidate lead ${leadId} to main graph`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, payload.data.node?.id || selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead promotion failed");
    }
  }, [activeInvestigationId, loadAnalystPipeline, loadCaseHealth, selectedNode?.id, token]);

  const restoreNoise = useCallback(async (noiseId: string) => {
    if (!activeInvestigationId) return;
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${activeInvestigationId}/noise/${noiseId}/restore`, { method: "POST" }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setSelectedNode(payload.data.node || null);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "success", message: `Restored noise item ${noiseId} to main graph`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, payload.data.node?.id || selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Noise restore failed");
    }
  }, [activeInvestigationId, loadAnalystPipeline, loadCaseHealth, selectedNode?.id, token]);

  const markSelectedNoise = useCallback(async () => {
    if (!activeInvestigationId || !selectedNode) return;
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${activeInvestigationId}/entities/${selectedNode.id}/mark-noise`, { method: "POST", body: JSON.stringify({ reason: "Analyst removed this entity from the main graph as noise." }) }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setSelectedNode(null);
      setTerminalLines((previous) => [...previous.slice(-260), { level: "system", message: `Marked ${selectedNode.label} as graph noise`, time: new Date().toISOString() }]);
      await loadCaseHealth(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Mark noise failed");
    }
  }, [activeInvestigationId, loadAnalystPipeline, loadCaseHealth, selectedNode, token]);

  const exportPacket = useCallback(async (format: "html" | "pdf" | "json" | "csv" | "graph_json") => {
    if (!activeInvestigationId) return;
    try {
      await downloadFile(`/api/v1/investigations/${activeInvestigationId}/exports/analyst-packet?format=${format}`, token, `nexusintel-${activeInvestigationId}.${format}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Export failed");
    }
  }, [activeInvestigationId, token]);

  const addTypedEntity = useCallback(async (value: string, type: string, lookup: boolean) => {
    const clean = value.trim();
    if (!clean) return;
    if (lookup) {
      setTarget(clean);
      await startLookupValue(clean, mode);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (!activeInvestigationId) {
        const payload = await apiJson<any>("/api/v1/investigations", { method: "POST", body: JSON.stringify({ target: clean, mode, target_type: type }) }, token);
        const id = payload.data.investigation_id || payload.data.investigation;
        setActiveInvestigationId(id);
        setGraph(normalizeGraphPayload(payload.data.graph));
        setSelectedNode(payload.data.root_node || null);
        navigate(`/graph?case=${id}`);
        await loadInvestigations();
        await loadCaseHealth(id);
        await loadEvidence(id);
        return;
      }
      const payload = await apiJson<any>("/api/v1/entities", { method: "POST", body: JSON.stringify({ investigation_id: activeInvestigationId, type, label: clean, value: clean, source_id: selectedNode?.id || null, relationship_type: selectedNode ? "manual_pivot" : "manual_seed", data: { created_from: "add_entity_dialog", mode } }) }, token);
      setGraph(normalizeGraphPayload(payload.data.graph));
      setSelectedNode(payload.data.node || null);
      await loadCaseHealth(activeInvestigationId);
      await loadEvidence(activeInvestigationId);
      await loadAnalystPipeline(activeInvestigationId, payload.data.node?.id || selectedNode?.id || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to add entity");
    } finally {
      setLoading(false);
    }
  }, [activeInvestigationId, loadAnalystPipeline, loadCaseHealth, loadEvidence, loadInvestigations, mode, navigate, selectedNode, startLookupValue, token]);

  const dispatchGraphEvent = useCallback((name: string, detail?: Record<string, unknown>) => {
    window.dispatchEvent(new CustomEvent(`nexus:${name}`, { detail }));
  }, []);

  const runTelemetryCommand = useCallback((command: string) => {
    const normalized = command.trim().toLowerCase();
    const log = (message: string, level = "system") => setTerminalLines((previous) => [...previous.slice(-260), { level, message, time: new Date().toISOString() }]);
    if (!normalized) return;
    if (normalized === "help") {
      log("Safe UI commands: help, clear-ui-logs, open-palette, open-case-dock, close-case-dock, open-inspector, close-inspector, fit-graph, toggle-terminal");
      return;
    }
    if (normalized === "clear-ui-logs" || normalized === "clear") { setTerminalLines([]); return; }
    if (normalized === "open-palette") { setPaletteOpen(true); log("Entity palette opened"); return; }
    if (normalized === "open-case-dock") { setCaseDockOpen(true); log("Case dock opened"); return; }
    if (normalized === "close-case-dock") { setCaseDockOpen(false); log("Case dock closed"); return; }
    if (normalized === "open-inspector") { setDataPanelOpen(true); log("Entity inspector opened"); return; }
    if (normalized === "close-inspector") { setDataPanelOpen(false); log("Entity inspector closed"); return; }
    if (normalized === "fit-graph") { dispatchGraphEvent("graph-fit"); log("Graph fit requested"); return; }
    if (normalized === "toggle-terminal" || normalized === "toggle-console") { setTerminalOpen((open) => !open); return; }
    if (normalized === "close-palette") { setPaletteOpen(false); log("Entity palette closed"); return; }
    log(`Unsupported UI command: ${command}`, "warning");
  }, [dispatchGraphEvent]);

  const graphCommands = useMemo<CommandItem[]>(() => [
    { id: "add-entity", label: "Add Entity", description: "Create a seed entity", shortcut: "A", group: "INVESTIGATION", action: () => setAddDialogOpen(true) },
    { id: "palette", label: "Open Entity Palette", description: "Browse production entity types", group: "INVESTIGATION", action: () => setPaletteOpen(true) },
    { id: "lookup", label: "Run Lookup", description: "Run lookup for the current search value", shortcut: "Enter", group: "INVESTIGATION", disabled: !target.trim(), action: () => void startLookupValue(target, mode) },
    { id: "case-dock", label: caseDockOpen ? "Hide Case Dock" : "Open Case Dock", shortcut: "D", group: "VIEW", action: () => setCaseDockOpen((open) => !open) },
    { id: "inspector", label: dataPanelOpen ? "Hide Inspector" : "Open Inspector", shortcut: "I", group: "VIEW", action: () => setDataPanelOpen((open) => !open) },
    { id: "terminal", label: "Toggle Telemetry", group: "VIEW", action: () => setTerminalOpen((open) => !open) },
    { id: "fit", label: "Fit Graph", shortcut: "F", group: "LAYOUT", action: () => dispatchGraphEvent("graph-fit") },
    { id: "layout", label: "Switch Layout", shortcut: "L", group: "LAYOUT", action: () => dispatchGraphEvent("graph-layout", { mode: "force" }) },
    { id: "export", label: "Export Report", group: "EXPORT", action: () => dispatchGraphEvent("graph-export") },
    { id: "evidence", label: "Open Evidence Vault", group: "EXPORT", action: () => navigate("/evidence") },
    { id: "review-noise", label: "Review Noise", group: "VIEW", action: () => setCaseDockOpen(true) },
    { id: "settings", label: "Open Settings", group: "VIEW", action: () => navigate("/settings") },
    { id: "investigator", label: "Open Investigator Brain", group: "INVESTIGATOR", action: () => setInvestigatorOpen(true) },
    { id: "new-case", label: "New Investigation", group: "INVESTIGATION", action: () => void createBlankInvestigation() },
  ], [caseDockOpen, createBlankInvestigation, dataPanelOpen, dispatchGraphEvent, mode, navigate, startLookupValue, target]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const targetElement = event.target as HTMLElement | null;
      const typing = targetElement?.tagName === "INPUT" || targetElement?.tagName === "TEXTAREA" || targetElement?.tagName === "SELECT" || targetElement?.isContentEditable;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandPaletteOpen(true); return; }
      if (typing) return;
      if (event.key.toLowerCase() === "d") { event.preventDefault(); setCaseDockOpen((open) => !open); }
      if (event.key.toLowerCase() === "i") { event.preventDefault(); setDataPanelOpen((open) => !open); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const activeCase = useMemo(() => investigations.find((item) => item.id === activeInvestigationId) || null, [activeInvestigationId, investigations]);

  return (
    <GraphPage>
      <GraphWorkspaceLayout>
        {error && <div className="nx-alert graph-alert"><span>{error}</span><button type="button" onClick={() => setError(null)}>Dismiss</button></div>}
        <GraphTopBar
          activeCase={activeCase}
          entities={graph.nodes.length}
          relationships={graph.edges.length}
          target={target}
          setTarget={setTarget}
          detectedType={pendingEntityType}
          mode={mode}
          setMode={setMode}
          loading={loading}
          dockOpen={caseDockOpen}
          inspectorOpen={dataPanelOpen}
          terminalOpen={terminalOpen}
          paletteOpen={paletteOpen}
          onLookup={startInvestigation}
          onAddEntity={() => setAddDialogOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
          onToggleDock={() => setCaseDockOpen((open) => !open)}
          onToggleInspector={() => setDataPanelOpen((open) => !open)}
          onToggleTerminal={() => setTerminalOpen((open) => !open)}
          onExport={() => dispatchGraphEvent("graph-export")}
          onFit={() => dispatchGraphEvent("graph-fit")}
          onLayout={(layout) => dispatchGraphEvent("graph-layout", { mode: layout })}
          onOpenEvidence={() => navigate("/evidence")}
          onOpenInvestigator={() => setInvestigatorOpen(true)}
          onReviewNoise={() => setCaseDockOpen(true)}
          onOpenSettings={() => navigate("/settings")}
        />
        <GraphCanvasStage>
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
            onOpenAddEntity={(kind) => { setAddDialogType(kind || "username"); setAddDialogOpen(true); }}
            onOpenImport={() => navigate("/evidence")}
            hideToolbar
          />
        </GraphCanvasStage>
        <CaseDockDrawer open={caseDockOpen} onClose={() => setCaseDockOpen(false)}>
          <CaseDock investigations={investigations} activeCase={activeCase} health={caseHealth} leads={graph.leads || []} noise={graph.noise || []} compliance={graph.compliance || []} onSelect={selectInvestigation} onCreateBlank={createBlankInvestigation} onDeleteActive={() => activeCase && setDeleteCase(activeCase)} onClearActive={clearActiveInvestigation} onPromoteLead={(id) => void promoteLead(id)} onRestoreNoise={(id) => void restoreNoise(id)} loading={loading} />
        </CaseDockDrawer>
        <InspectorDrawer open={dataPanelOpen} onClose={() => setDataPanelOpen(false)}>
          <EntityInspector
            open
            selectedNode={selectedNode}
            activeCase={activeCase}
            target={target}
            pendingEntityType={pendingEntityType}
            pendingTransforms={pendingTransforms}
            selectedTransforms={selectedTransforms}
            analystPipeline={analystPipeline}
            evidenceItems={evidenceItems}
            selectedEvidenceRefs={selectedEvidenceRefs}
            transformLoading={transformLoading}
            onOpenEvidence={(id) => void openEvidence(id)}
            onRunRegisteredTransform={(id) => void runRegisteredTransform(id)}
            onRunCorrelationEngine={() => void runCorrelationEngine()}
            onExportPacket={(format) => void exportPacket(format)}
            onMarkNoise={() => void markSelectedNoise()}
          />
        </InspectorDrawer>
        <TelemetryDrawer open={terminalOpen} lines={terminalLines} taskLabel={taskLabel || "idle"} onClose={() => setTerminalOpen(false)} onClear={() => setTerminalLines([])} onRunCommand={runTelemetryCommand} />
        {oracleNode && <div className="graph-oracle-popover"><button type="button" onClick={() => setOracleNode(null)}>Close Oracle</button><OraclePanel token={token} investigationId={activeInvestigationId} graph={graph} activeNode={oracleNode} title="Node Oracle" /></div>}
        {investigatorOpen && <div className="graph-investigator-popover"><button type="button" onClick={() => setInvestigatorOpen(false)}>Close Investigator</button><InvestigatorPanel token={token} /></div>}
        <EntityPaletteDrawer open={paletteOpen} onClose={() => setPaletteOpen(false)} onPick={(kind) => { setAddDialogType(kind); setPaletteOpen(false); setAddDialogOpen(true); }} />
        <AddEntityDialog open={addDialogOpen} initialType={addDialogType} onClose={() => setAddDialogOpen(false)} onAdd={(value, type, lookup) => void addTypedEntity(value, type, lookup)} />
        <CommandPalette open={commandPaletteOpen} commands={graphCommands} onClose={() => setCommandPaletteOpen(false)} />
        <EvidenceDrawer open={Boolean(evidenceDrawer)} evidence={evidenceDrawer} onClose={() => setEvidenceDrawer(null)} />
        <ConfirmDialog open={Boolean(deleteCase)} title="Delete Investigation" message={deleteCase ? `Delete investigation ${caseTitle(deleteCase)} and all graph data?` : "Delete investigation?"} confirmLabel="Delete" onCancel={() => setDeleteCase(null)} onConfirm={() => void confirmDeleteActive()} />
      </GraphWorkspaceLayout>
    </GraphPage>
  );

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
  const [collapsed, setCollapsed] = useState(() => readLocalJson("nexus.shell.navCollapsed", true));

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

  useEffect(() => { writeLocalJson("nexus.shell.navCollapsed", collapsed); }, [collapsed]);

  if (route === "/login" || !session.token) return <LoginPage onLogin={login} />;

  const props: PageProps = { token: session.token, user: session.user || "operator", navigate };
  let page = <DashboardPage {...props} />;
  if (route === "/identity") page = <IdentitySearchPage {...props} />;
  if (route === "/workspace") page = <WorkspacePage {...props} />;
  if (route === "/graph") page = <GraphHub {...props} />;
  if (route === "/watchlist") page = <ThreatWatchlistPage {...props} />;
  if (route === "/evidence") page = <EvidenceVaultPage {...props} />;
  if (route === "/reports") page = <ReportsPage {...props} />;
  if (route === "/transforms") page = <TransformLibraryPage {...props} />;
  if (route === "/oracle") page = <OraclePage {...props} />;
  if (route === "/settings") page = <SettingsPage {...props} />;
  if (route === "/account") page = <AccountPage {...props} />;

  return <AppShell route={route} user={session.user || "operator"} collapsed={collapsed} setCollapsed={setCollapsed} navigate={navigate} logout={logout}>{page}</AppShell>;
}
