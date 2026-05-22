import { Fingerprint } from "lucide-react";

type Props = {
  provenance?: { sha256?: string; source?: string; uri?: string; verified?: boolean } | null;
};

export default function ProvenancePanel({ provenance }: Props) {
  return (
    <section className="flat-intel-panel">
      <header><Fingerprint size={14} /><strong>Provenance</strong></header>
      {provenance ? (
        <div className="flat-kv">
          <span>SHA256</span><code>{provenance.sha256 || "--"}</code>
          <span>Source</span><code>{provenance.source || "--"}</code>
          <span>Status</span><code>{provenance.verified ? "VERIFIED" : "UNVERIFIED"}</code>
        </div>
      ) : <p>No chain-of-custody object selected.</p>}
    </section>
  );
}
