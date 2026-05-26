import { useEffect, useMemo, useState } from "react";
import { Database, Download, FileUp, FolderOpen, Network, Search } from "lucide-react";
import type { CaseHealth, Investigation, PageProps } from "../lib/types";
import { apiJson } from "../lib/api";
import { caseTitle, formatDate } from "../lib/format";
import TopIntelBar from "../layouts/TopIntelBar";
import EmptyState from "../components/common/EmptyState";
import StatusChip from "../components/common/StatusChip";
import LeadQueuePanel from "../components/cases/LeadQueuePanel";
import CoverageMatrix from "../components/cases/CoverageMatrix";
import ImportWizard from "../components/import/ImportWizard";

type HealthMap = Record<string, CaseHealth | null>;

export default function DashboardPage({ token, navigate }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [health, setHealth] = useState<HealthMap>({});
  const [error, setError] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [selector, setSelector] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiJson<any>("/api/v1/cases", undefined, token)
      .then(async (payload) => {
        const items = payload.data.items || [];
        if (cancelled) return;
        setCases(items);
        const pairs = await Promise.all(items.slice(0, 8).map(async (item: Investigation) => {
          try {
            const healthPayload = await apiJson<any>(`/api/v1/investigations/${item.id}/health`, undefined, token);
            return [item.id, healthPayload.data.health || null] as const;
          } catch {
            return [item.id, null] as const;
          }
        }));
        if (!cancelled) setHealth(Object.fromEntries(pairs));
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load dashboard"));
    return () => { cancelled = true; };
  }, [token]);

  const totals = useMemo(() => {
    const healthRows = Object.values(health).filter(Boolean) as CaseHealth[];
    return {
      highRisk: healthRows.filter((item) => (item.intelligence?.risk_score || 0) >= 70).length,
      evidence: healthRows.reduce((sum, item) => sum + (item.node_count || 0), 0),
      active: cases.filter((item) => ["queued", "running", "active"].includes(item.status)).length,
    };
  }, [cases, health]);

  const firstHealth = (Object.values(health).find(Boolean) as CaseHealth | undefined) || null;
  return (
    <section className="dashboard-page premium-page studio-page scroll-page">
      <header className="page-header premium-page-header"><div><span className="micro-label">Threat Intelligence Portal</span><h1>Threat Intelligence Portal</h1><p>Platform aggregated cyber tracking, scans frequency and active threat levels overview</p></div><div className="page-actions"><button className="nx-secondary" type="button" onClick={() => setShowImport((open) => !open)}><FileUp size={15} />Import</button><button className="nx-primary" type="button" onClick={() => navigate("/graph")}><Network size={15} />Open Graph</button></div></header>
      <form className="dashboard-selector premium-card" onSubmit={(event) => { event.preventDefault(); if (selector.trim()) navigate(`/identity?seed=${encodeURIComponent(selector.trim())}`); }}>
        <Search size={18} />
        <input value={selector} onChange={(event) => setSelector(event.target.value)} placeholder="Search email, phone, username, domain, IP, or wallet" />
        <button className="nx-primary" type="submit" disabled={!selector.trim()}>Investigate</button>
      </form>
      <TopIntelBar totalCases={cases.length} activeTasks={totals.active} highRiskCases={totals.highRisk} evidenceCount={totals.evidence} connectorSummary="BYOK" />
      {error && <div className="nx-alert"><span>{error}</span></div>}
      {showImport && <ImportWizard token={token} />}
      <div className="cockpit-grid">
        <section className="command-card wide premium-card recent-investigations"><header><strong>Recent Investigations</strong><span>{cases.length} cases</span></header>{!cases.length ? <EmptyState title="No cases yet" message="Open Network Graph to create the first investigation. No demo case data is generated." icon={FolderOpen} /> : <div className="intel-table premium-table"><div className="intel-row head"><span>Case</span><span>Target</span><span>Risk</span><span>Health</span><span>Updated</span><span>Actions</span></div>{cases.map((item) => { const itemHealth = health[item.id]; return <div className="intel-row" key={item.id}><span>{caseTitle(item)}</span><span>{item.target} / {item.target_type}</span><span><StatusChip label={itemHealth?.intelligence ? `${itemHealth.intelligence.risk_score}%` : "--"} tone={(itemHealth?.intelligence?.risk_score || 0) > 70 ? "danger" : "muted"} /></span><span>{itemHealth ? `${itemHealth.score}%` : "--"}</span><span>{formatDate(item.updated_at)}</span><span className="row-actions"><button type="button" onClick={() => navigate(`/graph?case=${item.id}`)}><Network size={13} />Graph</button><button type="button" onClick={() => navigate(`/workspace?case=${item.id}`)}><FolderOpen size={13} />Workspace</button><button type="button" title="Export from graph report panel"><Download size={13} />Export</button></span></div>; })}</div>}</section>
        <section className="command-card premium-card"><header><strong>Lead Queue</strong><span>triage</span></header><LeadQueuePanel health={firstHealth} compact /></section>
        <section className="command-card premium-card cockpit-coverage"><CoverageMatrix health={firstHealth} compact /></section>
        <section className="command-card premium-card"><header><strong>Scanners Connectivity</strong><span>BYOK</span></header><div className="connector-mini-grid"><StatusChip label="GitHub optional" tone="key" /><StatusChip label="HIBP requires key" tone="key" /><StatusChip label="URLScan optional" tone="key" /><StatusChip label="Core passive enabled" tone="ok" /></div><p className="muted-copy">Connector health is shown from configured settings when available. Missing keys disable paid/official API transforms instead of producing fake data.</p></section>
        <section className="command-card premium-card"><header><strong>Adversary Signal Feeds</strong><Database size={15} /></header><EmptyState title="No active signal feed rows" message="Public CTI and connector-backed indicators appear here when the backend returns verified evidence." icon={Database} /></section>
      </div>
    </section>
  );
}
