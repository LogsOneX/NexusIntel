import type { EvidenceRecord } from "../../lib/types";

export default function RawEvidenceViewer({ evidence }: { evidence: EvidenceRecord | null }) {
  if (!evidence) return <p className="muted-copy">No raw evidence selected.</p>;
  return (
    <section className="raw-evidence-viewer">
      <header><strong>{evidence.source}</strong><code>sha256:{evidence.sha256}</code></header>
      <pre>{evidence.payload_preview || JSON.stringify(evidence.meta || {}, null, 2) || "No preview available"}</pre>
      {evidence.payload_truncated && <small>Payload preview is truncated. Use the evidence API to retrieve full content.</small>}
    </section>
  );
}

