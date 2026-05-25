import { Cpu } from "lucide-react";

type ModelStatus = {
  mode?: string;
  model?: string;
  endpoint?: string;
  context_budget?: number;
  max_tokens?: number;
  temperature?: number;
  fallback?: boolean;
  ram_profile?: { name?: string; intended_ram?: string; role?: string };
};

export default function ModelStatusCard({ status }: { status?: ModelStatus | null }) {
  const mode = status?.mode || "rules";
  return (
    <article className="investigator-card model-status-card">
      <header><Cpu size={15} /><strong>Model Status</strong><span>{status?.fallback ? "rules fallback" : mode}</span></header>
      <dl className="investigator-kv">
        <div><dt>Mode</dt><dd>{mode}</dd></div>
        <div><dt>Model</dt><dd>{status?.model || "rules-only"}</dd></div>
        <div><dt>RAM Profile</dt><dd>{status?.ram_profile?.name || "tiny"} / {status?.ram_profile?.intended_ram || "2-4GB"}</dd></div>
        <div><dt>Context</dt><dd>{status?.context_budget || 4096} tokens</dd></div>
      </dl>
      <p className="investigator-note">No model is downloaded automatically. Rules-first validation stays active even when no local LLM is configured.</p>
    </article>
  );
}
