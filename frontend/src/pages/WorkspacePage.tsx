import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, FileUp, Plus, Trash2 } from "lucide-react";
import type { GraphPayload, Investigation, PageProps } from "../lib/types";
import { apiJson } from "../lib/api";
import { caseTitle } from "../lib/format";
import OraclePanel from "../components/OraclePanel";
import ImportWizard from "../components/import/ImportWizard";
import ConfirmDialog from "../components/common/ConfirmDialog";

export default function WorkspacePage({ token, navigate }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [caseName, setCaseName] = useState("");
  const [operator, setOperator] = useState("");
  const [notes, setNotes] = useState("");
  const [brief, setBrief] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Investigation | null>(null);
  const [showImport, setShowImport] = useState(false);
  const initialCaseLoadedRef = useRef(false);

  const loadCases = useCallback(async () => {
    const payload = await apiJson<any>("/api/v1/cases", undefined, token);
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
    const payload = await apiJson<any>(`/api/v1/investigations/${item.id}/graph`, undefined, token);
    setGraph(payload.data);
    navigate(`/workspace?case=${item.id}`);
  }, [navigate, token]);

  useEffect(() => {
    loadCases().then((items) => {
      if (initialCaseLoadedRef.current) return;
      initialCaseLoadedRef.current = true;
      const requestedCase = new URLSearchParams(window.location.search).get("case");
      const selected = requestedCase ? items.find((item) => item.id === requestedCase) : null;
      if (selected) void selectCase(selected);
    }).catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load cases"));
  }, [loadCases, selectCase]);

  const saveCase = async () => {
    if (!activeId) return;
    await apiJson(`/api/v1/cases/${activeId}`, { method: "PATCH", body: JSON.stringify({ case_name: caseName, assigned_operator: operator, notes }) }, token);
    await loadCases();
  };

  const confirmDelete = async () => {
    const item = deleteTarget;
    if (!item) return;
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
    setDeleteTarget(null);
  };

  const autoBrief = async () => {
    if (!activeId) return;
    const payload = await apiJson<any>("/api/v1/oracle/briefing", { method: "POST", body: JSON.stringify({ investigation_id: activeId, graph_state: graph }) }, token);
    setBrief(`${payload.data.executive_summary}\n\nThreat Assessment:\n${payload.data.threat_assessment}`);
  };

  return (
    <section className="workspace-page premium-page">
      <header className="page-header premium-page-header"><div><span className="micro-label">Case & Folder Manager</span><h1>Case & Folder Manager</h1><p>Manage active threat folder records, security logs, and analyst dossiers</p></div><div className="page-actions"><button className="nx-secondary" type="button" onClick={() => setShowImport((open) => !open)}><FileUp size={15} />Import</button><button className="nx-secondary" type="button" onClick={() => navigate("/graph")}><Plus size={15} />Create New Custom Case</button><button className="nx-secondary" type="button" onClick={autoBrief} disabled={!activeId}><Bot size={15} />AI Auto-Briefing</button></div></header>
      {error && <div className="nx-alert"><span>{error}</span></div>}
      {showImport && <ImportWizard token={token} investigationId={activeId} />}
      <div className="workspace-grid premium-workspace-grid">
        <aside className="case-strip large premium-card studio-case-folder-list"><strong>Case Folders</strong>{cases.map((item) => <div className={item.id === activeId ? "case-list-item active" : "case-list-item"} key={item.id}><button type="button" onClick={() => void selectCase(item)}>{caseTitle(item)}<span>{item.target_type} / {item.status}</span></button><button className="case-delete-button" type="button" onClick={() => setDeleteTarget(item)} title="Delete investigation"><Trash2 size={13} /></button></div>)}{!cases.length && <span>No cases yet. Create one from Network Graph.</span>}</aside>
        <section className="case-editor premium-card"><label>Case Name<input value={caseName} onChange={(event) => setCaseName(event.target.value)} /></label><label>Assigned Operator<input value={operator} onChange={(event) => setOperator(event.target.value)} /></label><label>Investigation Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Markdown notes" /></label><button className="nx-primary" type="button" onClick={saveCase} disabled={!activeId}>Save Case</button>{brief && <pre className="brief-box">{brief}</pre>}</section>
        <OraclePanel token={token} investigationId={activeId} graph={graph} title="Workspace Oracle" />
      </div>
      <ConfirmDialog open={Boolean(deleteTarget)} title="Delete Investigation" message={deleteTarget ? `Delete investigation ${caseTitle(deleteTarget)} and all graph data?` : "Delete investigation?"} confirmLabel="Delete" onCancel={() => setDeleteTarget(null)} onConfirm={() => void confirmDelete()} />
    </section>
  );
}

