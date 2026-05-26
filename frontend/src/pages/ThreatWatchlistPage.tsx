import { FormEvent, useEffect, useMemo, useState } from "react";
import { Bell, Plus, Radar, ShieldAlert, Trash2 } from "lucide-react";
import type { Investigation, PageProps } from "../lib/types";
import { apiJson } from "../lib/api";
import { classifyEntityValue } from "../lib/graph";
import { caseTitle, formatDate } from "../lib/format";
import EmptyState from "../components/common/EmptyState";
import StatusChip from "../components/common/StatusChip";

type WatchlistItem = {
  id: string;
  investigation_id: string;
  target: string;
  target_type: string;
  enabled: boolean;
  interval_hours: number;
  last_delta?: Record<string, unknown>;
  updated_at?: string;
};

export default function ThreatWatchlistPage({ token, navigate }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [investigationId, setInvestigationId] = useState("");
  const [target, setTarget] = useState("");
  const [intervalHours, setIntervalHours] = useState(12);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const [casePayload, watchPayload] = await Promise.all([
      apiJson<any>("/api/v1/cases", undefined, token),
      apiJson<any>("/api/v1/watchlist", undefined, token).catch(() => apiJson<any>("/api/v1/watchlists", undefined, token)),
    ]);
    const nextCases = casePayload.data.items || [];
    setCases(nextCases);
    setItems(watchPayload.data.items || []);
    if (!investigationId && nextCases[0]) setInvestigationId(nextCases[0].id);
  };

  useEffect(() => { load().catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load watchlist")); }, [token]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    const clean = target.trim();
    if (!clean || !investigationId) return;
    await apiJson("/api/v1/watchlist", { method: "POST", body: JSON.stringify({ investigation_id: investigationId, target: clean, target_type: classifyEntityValue(clean), interval_hours: intervalHours, enabled: true }) }, token)
      .catch(() => apiJson("/api/v1/watchlists", { method: "POST", body: JSON.stringify({ investigation_id: investigationId, target: clean, target_type: classifyEntityValue(clean), interval_hours: intervalHours, enabled: true }) }, token));
    setTarget("");
    await load();
  };

  const byCase = useMemo(() => new Map(cases.map((item) => [item.id, caseTitle(item)])), [cases]);

  return (
    <section className="watchlist-page premium-page studio-page scroll-page">
      <header className="page-header premium-page-header">
        <div>
          <span className="micro-label">Passive monitoring posture</span>
          <h1>Threat Watchlist</h1>
          <p className="muted-copy">Monitor authorized domains, IPs, emails, organizations, keywords, or wallets with legal passive checks. No illegal dark web crawling is implemented.</p>
        </div>
        <button className="nx-secondary" type="button" onClick={() => navigate("/settings")}><ShieldAlert size={15} />Configure CTI connectors</button>
      </header>
      {error && <div className="nx-alert"><span>{error}</span></div>}
      <form className="watchlist-form premium-card" onSubmit={create}>
        <select value={investigationId} onChange={(event) => setInvestigationId(event.target.value)}>
          <option value="">Select case</option>
          {cases.map((item) => <option value={item.id} key={item.id}>{caseTitle(item)}</option>)}
        </select>
        <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="domain, IP, email, org keyword, crypto wallet" />
        <select value={intervalHours} onChange={(event) => setIntervalHours(Number(event.target.value))}>
          <option value={6}>Every 6 hours</option>
          <option value={12}>Every 12 hours</option>
          <option value={24}>Daily</option>
          <option value={168}>Weekly</option>
        </select>
        <button className="nx-primary" type="submit" disabled={!target.trim() || !investigationId}><Plus size={15} />Add Watch</button>
      </form>
      {!items.length ? <EmptyState title="No watchlist items" message="Add authorized targets to monitor passive deltas and connector-backed CTI indicators. No placeholder alerts are shown." icon={Radar} /> : (
        <div className="watchlist-table premium-table">
          <div className="intel-row head"><span>Target</span><span>Type</span><span>Case</span><span>Status</span><span>Last Checked</span><span>Delta</span><span>Actions</span></div>
          {items.map((item) => <div className="intel-row" key={item.id}><span>{item.target}</span><span>{item.target_type}</span><span>{byCase.get(item.investigation_id) || item.investigation_id}</span><span><StatusChip label={item.enabled ? "enabled" : "paused"} tone={item.enabled ? "ok" : "muted"} /></span><span>{formatDate(item.updated_at)}</span><span>{Object.keys(item.last_delta || {}).length ? <StatusChip label="delta" tone="warning" /> : <StatusChip label="clear" tone="muted" />}</span><span className="row-actions"><button type="button" onClick={() => apiJson(`/api/v1/watchlists/${item.id}/toggle`, { method: "PATCH" }, token).then(load)}><Bell size={13} />Toggle</button><button className="danger" type="button" onClick={() => apiJson(`/api/v1/watchlist/${item.id}`, { method: "DELETE" }, token).then(load)}><Trash2 size={13} />Remove</button></span></div>)}
        </div>
      )}
    </section>
  );
}
