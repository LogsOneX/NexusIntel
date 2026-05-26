import { useEffect, useMemo, useState } from "react";
import { Download, FileText, Lock, ShieldCheck } from "lucide-react";
import type { Investigation, PageProps } from "../lib/types";
import { apiJson, downloadFile } from "../lib/api";
import { caseTitle, formatDate } from "../lib/format";
import EmptyState from "../components/common/EmptyState";
import StatusChip from "../components/common/StatusChip";

const REPORT_SECTIONS = [
  "Executive Summary",
  "Key Judgments",
  "Scope & Methodology",
  "Entity Graph Summary",
  "Evidence Table",
  "Confidence Assessment",
  "Noise Removed",
  "Timeline",
  "IOCs",
  "Recommended Next Steps",
  "Raw Evidence Hashes",
];

export default function ReportsPage({ token }: PageProps) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [title, setTitle] = useState("NexusIntel Intelligence Dossier");
  const [analyst, setAnalyst] = useState("Operator");
  const [sections, setSections] = useState(() => new Set(REPORT_SECTIONS));
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiJson<any>("/api/v1/cases", undefined, token)
      .then((payload) => {
        if (cancelled) return;
        const items = payload.data.items || [];
        setCases(items);
        if (items[0]) setSelectedId(items[0].id);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Backend endpoint unavailable"));
    return () => { cancelled = true; };
  }, [token]);

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedId) || null, [cases, selectedId]);

  const toggleSection = (section: string) => {
    setSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section); else next.add(section);
      return next;
    });
  };

  const exportReport = async (format: "pdf" | "html" | "json") => {
    if (!selectedCase) return;
    setExporting(true);
    setError(null);
    try {
      await downloadFile(`/api/v1/investigations/${selectedCase.id}/exports/analyst-packet?format=${format}`, token, `nexusintel-${selectedCase.id}.${format}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Backend report export unavailable");
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="reports-page studio-report-page studio-page scroll-page">
      <header className="studio-page-hero">
        <div>
          <span className="micro-label">Report Builder</span>
          <h1>OSINT Report Constructor</h1>
          <p>Compile evidence-backed intelligence packets from real NexusIntel cases without generating synthetic findings.</p>
        </div>
        <StatusChip label="Evidence-first export" tone="ok" />
      </header>
      {error && <div className="nx-alert"><span>{error}</span></div>}
      <div className="studio-report-grid">
        <aside className="studio-report-panel">
          <header><FileText size={16} /><strong>Dossier Parameters</strong></header>
          <label>Investigation<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{cases.map((item) => <option value={item.id} key={item.id}>{caseTitle(item)}</option>)}</select></label>
          <label>Document Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label>Lead Analyst<input value={analyst} onChange={(event) => setAnalyst(event.target.value)} /></label>
          <div className="studio-section-list"><strong>Section Bundle</strong>{REPORT_SECTIONS.map((section) => <label key={section} className="studio-check-row"><input type="checkbox" checked={sections.has(section)} onChange={() => toggleSection(section)} /><span>{section}</span></label>)}</div>
          <div className="studio-report-actions">
            <button className="nx-primary" type="button" disabled={!selectedCase || exporting} onClick={() => void exportReport("pdf")}><Download size={15} />{exporting ? "Compiling Dossier" : "Compile & Export PDF Dossier"}</button>
            <button className="nx-secondary" type="button" disabled={!selectedCase || exporting} onClick={() => void exportReport("html")}>Export HTML</button>
            <button className="nx-secondary" type="button" disabled={!selectedCase || exporting} onClick={() => void exportReport("json")}>JSON Bundle</button>
          </div>
        </aside>
        <section className="studio-report-preview">
          {!selectedCase ? <EmptyState title="No case available" message="Create or load an investigation before exporting a report." icon={FileText} /> : <>
            <div className="report-sheet-classification"><Lock size={13} />SECURE / CONFIDENTIAL</div>
            <h2>CYBER THREAT ASSESSMENT REPORT</h2>
            <p className="report-sheet-title">{title}</p>
            <dl>
              <div><dt>Case</dt><dd>{caseTitle(selectedCase)}</dd></div>
              <div><dt>Target</dt><dd>{selectedCase.target} / {selectedCase.target_type}</dd></div>
              <div><dt>Status</dt><dd>{selectedCase.status}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(selectedCase.updated_at)}</dd></div>
              <div><dt>Analyst</dt><dd>{analyst || "Operator"}</dd></div>
            </dl>
            <div className="report-sheet-sections"><ShieldCheck size={15} /><span>{sections.size} report sections selected. Export uses backend evidence citations and confidence explanations.</span></div>
          </>}
        </section>
      </div>
    </section>
  );
}
