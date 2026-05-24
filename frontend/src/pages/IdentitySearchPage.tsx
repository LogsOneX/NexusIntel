import { FormEvent, useMemo, useState } from "react";
import { AtSign, Bitcoin, Fingerprint, Globe2, Loader2, Network, Phone, Radar, ShieldCheck, UserRound } from "lucide-react";
import type { PageProps, TerminalLine } from "../lib/types";
import { apiJson, wsUrl } from "../lib/api";
import { classifyEntityValue } from "../lib/graph";
import { terminalPrefix } from "../lib/format";
import StatusChip from "../components/common/StatusChip";
import EmptyState from "../components/common/EmptyState";

const MODULES = [
  { id: "account_presence", title: "Account Presence", types: ["email", "phone", "username"], note: "Verified public signals and candidates are separated." },
  { id: "workspace", title: "Workspace / Domain Posture", types: ["email", "domain"], note: "MX, TXT, provider, DNS and mail security posture." },
  { id: "dns_ip", title: "DNS / IP Signals", types: ["domain", "ip"], note: "DNS, RDAP, reverse DNS, ASN, web posture." },
  { id: "profiles", title: "Public Profile Candidates", types: ["username", "email"], note: "Candidates stay out of main graph until promoted." },
  { id: "cti", title: "Breach / CTI Indicators", types: ["email", "domain", "ip", "crypto_wallet"], note: "Official/BYOK connectors only. No leaked credential storage." },
  { id: "confidence", title: "Confidence & Evidence", types: ["*"], note: "Each accepted result needs source, timestamp, hash, and legal note." },
];

function typeIcon(type: string) {
  if (type === "email") return AtSign;
  if (type === "phone") return Phone;
  if (type === "domain") return Globe2;
  if (type === "ip") return Network;
  if (type === "crypto_wallet") return Bitcoin;
  if (type === "username") return UserRound;
  return Fingerprint;
}

export default function IdentitySearchPage({ token, navigate }: PageProps) {
  const [target, setTarget] = useState(new URLSearchParams(window.location.search).get("seed") || "");
  const [mode, setMode] = useState<"passive" | "standard" | "aggressive">("standard");
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const entityType = useMemo(() => classifyEntityValue(target), [target]);
  const TypeIcon = typeIcon(entityType);
  const compatibleModules = MODULES.map((module) => ({ ...module, enabled: module.types.includes("*") || module.types.includes(entityType) }));

  const runLookup = async (event: FormEvent) => {
    event.preventDefault();
    const clean = target.trim();
    if (!clean) return;
    setLoading(true);
    setError(null);
    setLines([]);
    try {
      const payload = await apiJson<any>("/api/v1/scans/nexusrecon", { method: "POST", body: JSON.stringify({ target: clean, mode }) }, token);
      const nextTask = payload.data.task_id;
      setTaskId(nextTask);
      const socket = new WebSocket(wsUrl(nextTask));
      socket.onmessage = (message) => {
        try {
          setLines((previous) => [...previous.slice(-180), JSON.parse(message.data)]);
        } catch {
          setLines((previous) => [...previous.slice(-180), { level: "info", message: message.data }]);
        }
      };
      socket.onclose = () => setLoading(false);
      navigate(`/graph?case=${payload.data.investigation_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lookup failed");
      setLoading(false);
    }
  };

  return (
    <section className="identity-page premium-page">
      <header className="page-header premium-page-header">
        <div>
          <span className="micro-label">Selector-first investigation</span>
          <h1>Identity Search</h1>
          <p className="muted-copy">Reverse email, phone, username, domain, IP, and wallet workflows with evidence-first output. No demo intelligence is generated.</p>
        </div>
      </header>

      <form className="identity-search-hero" onSubmit={runLookup}>
        <div className="selector-input">
          <TypeIcon size={22} />
          <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="email, phone, username, domain, IP, crypto wallet" />
          <StatusChip label={entityType.replaceAll("_", " ")} tone="info" />
        </div>
        <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
          <option value="passive">Passive</option>
          <option value="standard">Standard</option>
          <option value="aggressive">Authorized deep sweep</option>
        </select>
        <button className="nx-primary" type="submit" disabled={loading || !target.trim()}>
          {loading ? <Loader2 className="spin" size={15} /> : <Radar size={15} />}
          Run Lookup
        </button>
      </form>

      {error && <div className="nx-alert"><span>{error}</span></div>}

      <div className="identity-grid">
        <section className="command-card premium-card">
          <header><ShieldCheck size={16} /><strong>Enrichment Modules</strong><span>valid for selector</span></header>
          <div className="module-card-grid">
            {compatibleModules.map((module) => (
              <article className={module.enabled ? "module-card enabled" : "module-card disabled"} key={module.id}>
                <div><strong>{module.title}</strong>{module.enabled ? <StatusChip label="available" tone="ok" /> : <StatusChip label="not applicable" tone="muted" />}</div>
                <p>{module.note}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="command-card premium-card lookup-progress">
          <header><Radar size={16} /><strong>Live Progress</strong><span>{taskId || "idle"}</span></header>
          {!lines.length ? <EmptyState title="No lookup running" message="Enter a selector to stream source queries, result counts, evidence capture, confidence movement, and noise filtering." icon={Radar} /> : (
            <div className="progress-log">
              {lines.map((line, index) => <p key={`${line.time || index}:${index}`}><span>{line.time ? new Date(line.time).toLocaleTimeString() : "--:--:--"}</span><strong>{terminalPrefix(line.level)}</strong><code>{line.message}</code></p>)}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
