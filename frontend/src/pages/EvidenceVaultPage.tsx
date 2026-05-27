import { useEffect, useMemo, useState } from "react";
import { Database, Filter, ShieldCheck } from "lucide-react";
import type { EvidenceRecord, PageProps } from "../lib/types";
import { apiJson } from "../lib/api";
import EvidenceCard from "../components/evidence/EvidenceCard";
import EvidenceDrawer from "../components/evidence/EvidenceDrawer";
import EmptyState from "../components/common/EmptyState";
import StatusChip from "../components/common/StatusChip";

export default function EvidenceVaultPage({ token }: PageProps) {
  const [items, setItems] = useState<EvidenceRecord[]>([]);
  const [selected, setSelected] = useState<EvidenceRecord | null>(null);
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [qualitySummary, setQualitySummary] = useState<Record<string, any> | null>(null);
  const [qualityById, setQualityById] = useState<Record<string, any>>({});

  useEffect(() => {
    apiJson<any>("/api/v1/evidence", undefined, token)
      .then((payload) => setItems(payload.data.items || []))
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Evidence endpoint unavailable"));
    apiJson<any>("/api/v1/cases", undefined, token)
      .then((payload) => {
        const first = payload.data.items?.[0]?.id;
        if (!first) return null;
        return apiJson<any>(`/api/v1/investigations/${first}/evidence-quality`, undefined, token);
      })
      .then((payload) => {
        if (!payload) return;
        setQualitySummary(payload.data.summary || null);
        setQualityById(Object.fromEntries((payload.data.items || []).map((item: any) => [String(item.evidence_id), item])));
      })
      .catch(() => undefined);
  }, [token]);

  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();
    return items.filter((item) => {
      const meta = item.meta || {};
      const evidenceGrade = String(meta.evidence_grade || meta.grade || "ungraded");
      const blob = `${item.source} ${item.uri} ${item.sha256} ${item.content_type} ${JSON.stringify(meta)}`.toLowerCase();
      return (!term || blob.includes(term)) && (grade === "all" || evidenceGrade === grade);
    });
  }, [grade, items, query]);

  return (
    <section className="evidence-vault-page premium-page studio-page scroll-page">
      <header className="page-header premium-page-header">
        <div>
          <span className="micro-label">Raw proof store</span>
          <h1>Evidence Vault</h1>
          <p className="muted-copy">Browse public-source proof objects, hashes, source URLs, timestamps, and legal notes before trusting a graph relationship.</p>
        </div>
        <div className="page-actions"><StatusChip label={`${items.length} evidence objects`} tone="info" />{qualitySummary && <StatusChip label={`${qualitySummary.average_quality || 0}% avg quality`} tone={(qualitySummary.average_quality || 0) >= 65 ? "ok" : "warning"} />}</div>
      </header>
      {error && <div className="nx-alert"><span>{error}</span></div>}
      <section className="vault-toolbar premium-card">
        <label><Filter size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter source, URL, hash, entity, legal note" /></label>
        <select value={grade} onChange={(event) => setGrade(event.target.value)}>
          <option value="all">All grades</option>
          <option value="A1">A1 direct public source</option>
          <option value="A2">A2 strong technical evidence</option>
          <option value="B1">B1 corroborated public signals</option>
          <option value="B2">B2 weak single signal</option>
          <option value="C">C candidate only</option>
        </select>
      </section>
      {!rows.length ? <EmptyState title="No evidence available" message="Evidence appears after transforms store raw public-source proof. No fake evidence is displayed." icon={Database} /> : (
        <div className="vault-grid">
          {rows.map((item) => <div key={item.id} className="evidence-card-wrap"><EvidenceCard evidence={item} onOpenRaw={() => setSelected(item)} />{qualityById[item.id] && <div className="evidence-quality-strip"><StatusChip label={`${qualityById[item.id].quality_score}% quality`} tone={qualityById[item.id].report_safe ? "ok" : "warning"} /><button type="button" onClick={() => navigator.clipboard?.writeText(`evidence:${item.id}:${item.sha256}`)}>Copy citation</button></div>}</div>)}
        </div>
      )}
      <section className="command-card premium-card vault-note">
        <header><ShieldCheck size={15} /><strong>Evidence-first rule</strong></header>
        <p>Nodes without source URL, fetched timestamp, confidence reason, or raw hash should be treated as weak leads until corroborated. Report-safe status is calculated from source, freshness, directness, and hash verification.</p>
      </section>
      <EvidenceDrawer open={Boolean(selected)} evidence={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
