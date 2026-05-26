import { useEffect, useMemo, useState } from "react";
import { BrainCircuit, KeyRound, PlugZap, Save } from "lucide-react";
import type { ConnectorDefinition, PageProps } from "../lib/types";
import { apiJson } from "../lib/api";
import StatusChip from "../components/common/StatusChip";

const CONNECTORS: ConnectorDefinition[] = [
  { id: "github", name: "GitHub", category: "Code", reliability: "high public", legal_note: "Official API/BYOK public code and profile search.", requires_key: true },
  { id: "hibp", name: "HaveIBeenPwned", category: "Breach", reliability: "authoritative", legal_note: "Official API only. Disabled without key.", requires_key: true },
  { id: "urlscan", name: "URLScan", category: "Infrastructure", reliability: "high public", legal_note: "Official API/BYOK or public lookups where allowed.", requires_key: true },
  { id: "virustotal", name: "VirusTotal", category: "Infrastructure", reliability: "high aggregator", legal_note: "Official BYOK connector.", requires_key: true },
  { id: "shodan", name: "Shodan", category: "Infrastructure", reliability: "high scanner", legal_note: "Official BYOK connector.", requires_key: true },
  { id: "censys", name: "Censys", category: "Infrastructure", reliability: "high scanner", legal_note: "Official BYOK connector.", requires_key: true },
  { id: "securitytrails", name: "SecurityTrails", category: "DNS", reliability: "high aggregator", legal_note: "Official BYOK connector.", requires_key: true },
  { id: "google_maps", name: "Google Maps/Places", category: "Maps", reliability: "official", legal_note: "Place enrichment only from analyst-supplied public place/profile evidence.", requires_key: true },
  { id: "intelx", name: "IntelX", category: "Breach/Data", reliability: "third-party", legal_note: "Official BYOK connector only.", requires_key: true },
  { id: "opencorporates", name: "OpenCorporates", category: "Corporate", reliability: "public registry", legal_note: "Public corporate registry enrichment.", requires_key: false },
];

const DEFAULT_SETTINGS = {
  llm: { provider: "local", endpoint: "http://localhost:11434", model: "llama3.1" },
  ai: { mode: "rules", endpoint: "http://localhost:11434", model: "", ram_profile: "tiny", context_tokens: 4096, max_tokens: 700, temperature: 0.1, enable_summarization: true, enable_json_mode: true, custom_system_prompt: "" },
  api_keys: {},
  connectors: {},
};

export default function SettingsPage({ token }: PageProps) {
  const [settings, setSettings] = useState<Record<string, any>>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);
  const [filter, setFilter] = useState("all");
  const [modelStatus, setModelStatus] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    apiJson<any>("/api/v1/settings", undefined, token).then((payload) => setSettings({ ...DEFAULT_SETTINGS, ...(payload.data.settings || {}) })).catch(() => undefined);
    apiJson<any>("/api/v1/investigator/model-status", undefined, token).then((payload) => setModelStatus(payload.data.status || null)).catch(() => undefined);
  }, [token]);

  const update = (path: string[], value: string | boolean | number) => setSettings((current) => {
    const next = { ...current, llm: { ...(current.llm || {}) }, ai: { ...(current.ai || {}) }, api_keys: { ...(current.api_keys || {}) }, connectors: { ...(current.connectors || {}) } };
    let target = next as any;
    path.slice(0, -1).forEach((part) => { target[part] = { ...(target[part] || {}) }; target = target[part]; });
    target[path[path.length - 1]] = value;
    return next;
  });

  const save = async () => {
    await apiJson("/api/v1/settings", { method: "PUT", body: JSON.stringify({ settings }) }, token);
    const status = await apiJson<any>("/api/v1/investigator/model-status", undefined, token).catch(() => null);
    if (status?.data?.status) setModelStatus(status.data.status);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  };

  const rows = useMemo(() => CONNECTORS.filter((item) => filter === "all" || item.category === filter), [filter]);
  const categories = ["all", ...Array.from(new Set(CONNECTORS.map((item) => item.category)))];

  return (
    <section className="settings-page premium-page studio-page scroll-page">
      <header className="page-header premium-page-header">
        <div><span className="micro-label">Connector Center</span><h1>BYOK, Local AI, and Rate Limits</h1></div>
        <button className="nx-primary" type="button" onClick={save}><Save size={15} />Save Settings</button>
      </header>

      <div className="settings-grid premium-settings">
        <section className="command-card premium-card ai-settings-card">
          <header><BrainCircuit size={16} /><strong>Local Investigator Brain</strong><StatusChip label={modelStatus?.fallback ? "rules active" : String(modelStatus?.mode || "rules")} tone={modelStatus?.fallback ? "muted" : "ok"} /></header>
          <div className="settings-two-col">
            <label>AI Mode<select value={settings.ai?.mode || "rules"} onChange={(event) => update(["ai", "mode"], event.target.value)}><option value="rules">Rules only</option><option value="ollama">Ollama compatible</option><option value="llamacpp">llama.cpp server</option><option value="openai_compatible">OpenAI compatible</option></select></label>
            <label>RAM Profile<select value={settings.ai?.ram_profile || "tiny"} onChange={(event) => update(["ai", "ram_profile"], event.target.value)}><option value="tiny">Tiny / 2-4GB</option><option value="small">Small / 4-8GB</option><option value="balanced">Balanced / 8-16GB</option></select></label>
            <label>Endpoint<input value={settings.ai?.endpoint || ""} onChange={(event) => update(["ai", "endpoint"], event.target.value)} placeholder="http://localhost:11434" /></label>
            <label>Model Name<input value={settings.ai?.model || ""} onChange={(event) => update(["ai", "model"], event.target.value)} placeholder="operator-selected local model" /></label>
            <label>Context Tokens<input type="number" min={1024} max={32768} value={settings.ai?.context_tokens || 4096} onChange={(event) => update(["ai", "context_tokens"], Number(event.target.value))} /></label>
            <label>Max Tokens<input type="number" min={128} max={4096} value={settings.ai?.max_tokens || 700} onChange={(event) => update(["ai", "max_tokens"], Number(event.target.value))} /></label>
            <label>Temperature<input type="number" step="0.05" min={0} max={1} value={settings.ai?.temperature ?? 0.1} onChange={(event) => update(["ai", "temperature"], Number(event.target.value))} /></label>
            <label>API Key<input type="password" value={settings.ai?.api_key || ""} onChange={(event) => update(["ai", "api_key"], event.target.value)} placeholder="only for compatible remote gateway" /></label>
          </div>
          <div className="settings-checks">
            <label><input type="checkbox" checked={settings.ai?.enable_summarization !== false} onChange={(event) => update(["ai", "enable_summarization"], event.target.checked)} />Enable evidence summaries</label>
            <label><input type="checkbox" checked={settings.ai?.enable_json_mode !== false} onChange={(event) => update(["ai", "enable_json_mode"], event.target.checked)} />Request strict JSON mode</label>
          </div>
          <label>Custom Investigator System Prompt<textarea value={settings.ai?.custom_system_prompt || ""} onChange={(event) => update(["ai", "custom_system_prompt"], event.target.value)} placeholder="Optional. Leave empty to use the evidence-first default prompt." /></label>
          <p className="muted-copy">Install and run your preferred local model runtime separately. NexusIntel never downloads a model automatically; rules-only investigator mode remains available without an LLM.</p>
        </section>

        <section className="command-card premium-card">
          <header><KeyRound size={16} /><strong>Legacy LLM Compatibility</strong></header>
          <label>Provider<select value={settings.llm?.provider || "local"} onChange={(event) => update(["llm", "provider"], event.target.value)}><option value="local">Rule-based local</option><option value="ollama">Ollama</option><option value="openai">OpenAI compatible</option><option value="anthropic">Anthropic</option></select></label>
          <label>Endpoint<input value={settings.llm?.endpoint || ""} onChange={(event) => update(["llm", "endpoint"], event.target.value)} placeholder="http://localhost:11434" /></label>
          <label>Model<input value={settings.llm?.model || ""} onChange={(event) => update(["llm", "model"], event.target.value)} placeholder="llama3.1" /></label>
          <label>Remote API Key<input type="password" value={settings.llm?.api_key || ""} onChange={(event) => update(["llm", "api_key"], event.target.value)} /></label>
          <p className="muted-copy">Kept for existing Oracle integrations. New reasoning uses the Local Investigator Brain settings above.</p>
        </section>

        <section className="command-card premium-card connector-center">
          <header><PlugZap size={16} /><strong>OSINT Connectors</strong><select value={filter} onChange={(event) => setFilter(event.target.value)}>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></header>
          <div className="connector-list">
            {rows.map((connector) => {
              const configured = Boolean(settings.api_keys?.[connector.id]) || !connector.requires_key;
              const enabled = settings.connectors?.[connector.id] !== false;
              return <article className="connector-card" key={connector.id}><header><strong>{connector.name}</strong><div><StatusChip label={enabled ? "enabled" : "disabled"} tone={enabled ? "ok" : "muted"} /><StatusChip label={configured ? "configured" : "requires key"} tone={configured ? "ok" : "key"} /></div></header><p>{connector.legal_note}</p><div className="connector-fields"><label><span>Enabled</span><input aria-label={`${connector.name} enabled`} type="checkbox" checked={enabled} onChange={(event) => update(["connectors", connector.id], event.target.checked)} /></label>{connector.requires_key && <label><span>API Key</span><input type="password" value={settings.api_keys?.[connector.id] || ""} onChange={(event) => update(["api_keys", connector.id], event.target.value)} placeholder="stored by backend" /></label>}<button type="button" onClick={() => update(["connectors", `${connector.id}_last_tested`], new Date().toISOString())}>Test</button></div><small>{connector.category} / {connector.reliability}</small></article>;
            })}
          </div>
        </section>
      </div>
      {saved && <div className="save-toast">Settings saved.</div>}
    </section>
  );
}
