import { ShieldCheck } from "lucide-react";

type ValidationResult = { target_id?: string; label?: string; validation_label?: string; final_confidence?: number; explanation?: string[] };

export default function ValidationPanel({ validation }: { validation?: { counts?: Record<string, number>; results?: ValidationResult[] } | null }) {
  const counts = validation?.counts || {};
  const results = validation?.results || [];
  return (
    <article className="investigator-card">
      <header><ShieldCheck size={15} /><strong>Validation</strong><span>{results.length} findings</span></header>
      <div className="investigator-counts">
        {Object.keys(counts).length ? Object.entries(counts).map(([key, value]) => <span key={key}>{key}<b>{value}</b></span>) : <span>No graph findings yet<b>0</b></span>}
      </div>
      <div className="investigator-list compact">
        {results.slice(0, 6).map((item) => (
          <div key={item.target_id || item.label}>
            <strong>{item.label || "Unknown"}</strong>
            <span>{item.validation_label || "INSUFFICIENT_EVIDENCE"} / {item.final_confidence ?? 0}%</span>
            <small>{(item.explanation || ["No explanation available."])[0]}</small>
          </div>
        ))}
      </div>
    </article>
  );
}
