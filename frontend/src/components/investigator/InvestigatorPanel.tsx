import { type FormEvent, useEffect, useMemo, useState } from "react";
import { BrainCircuit, Loader2, RefreshCw, Send } from "lucide-react";
import { apiJson } from "../../lib/api";
import type { Investigation } from "../../lib/types";
import ModelStatusCard from "./ModelStatusCard";
import ValidationPanel from "./ValidationPanel";
import NoiseExplanationPanel from "./NoiseExplanationPanel";
import HypothesisPanel from "./HypothesisPanel";
import NextActionPanel from "./NextActionPanel";
import ReportReadinessCard from "./ReportReadinessCard";
import EvidenceMapPanel from "./EvidenceMapPanel";
import CorrelationExplainer from "./CorrelationExplainer";
import PlaybookRunner from "./PlaybookRunner";
import NoiseReviewPanel from "./NoiseReviewPanel";

type BrainResponse = {
  reply?: string;
  provider?: string;
  mode?: string;
  evidence_refs?: Array<Record<string, unknown>>;
  validation_summary?: Record<string, any>;
  noise_summary?: Record<string, any>;
  hypotheses?: Array<Record<string, any>>;
  next_actions?: Array<Record<string, any>>;
  confidence_warnings?: string[];
  model_status?: Record<string, any>;
  report_readiness?: Record<string, any>;
};

const QUICK_PROMPTS = [
  "Summarize case with evidence citations",
  "Validate strongest findings",
  "What is noise and why?",
  "Find contradictions",
  "What should I run next?",
  "Prepare report readiness brief",
];

export default function InvestigatorPanel({ token }: { token: string }) {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [caseId, setCaseId] = useState("");
  const [prompt, setPrompt] = useState("Summarize case with evidence citations");
  const [answer, setAnswer] = useState<BrainResponse | null>(null);
  const [modelStatus, setModelStatus] = useState<Record<string, any> | null>(null);
  const [evidenceMap, setEvidenceMap] = useState<Record<string, any> | null>(null);
  const [correlations, setCorrelations] = useState<Array<Record<string, any>>>([]);
  const [playbooks, setPlaybooks] = useState<Array<Record<string, any>>>([]);
  const [playbookId, setPlaybookId] = useState("");
  const [playbookPlan, setPlaybookPlan] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiJson<any>("/api/v1/cases", undefined, token).then((payload) => {
      const items = (payload.data.items || []) as Investigation[];
      setCases(items);
      setCaseId((current) => current || items[0]?.id || "");
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load cases."));
    apiJson<any>("/api/v1/investigator/model-status", undefined, token).then((payload) => setModelStatus(payload.data.status || null)).catch(() => undefined);
    apiJson<any>("/api/v1/playbooks", undefined, token).then((payload) => {
      const items = payload.data.items || [];
      setPlaybooks(items);
      setPlaybookId((current) => current || items[0]?.id || "");
    }).catch(() => undefined);
  }, [token]);

  useEffect(() => {
    if (!caseId) return;
    apiJson<any>(`/api/v1/investigations/${caseId}/evidence-map`, undefined, token).then((payload) => setEvidenceMap(payload.data || null)).catch(() => setEvidenceMap(null));
    apiJson<any>(`/api/v1/investigations/${caseId}/correlations`, undefined, token).then((payload) => setCorrelations(payload.data.items || [])).catch(() => setCorrelations([]));
    setPlaybookPlan(null);
  }, [caseId, token]);

  const activeCase = useMemo(() => cases.find((item) => item.id === caseId), [cases, caseId]);

  const ask = async (text = prompt) => {
    if (!caseId || !text.trim()) return;
    setLoading(true);
    setError("");
    try {
      const payload = await apiJson<any>("/api/v1/oracle/chat", { method: "POST", body: JSON.stringify({ investigation_id: caseId, prompt: text.trim(), mode: "balanced" }) }, token);
      setAnswer(payload.data || {});
      if (payload.data?.model_status) setModelStatus(payload.data.model_status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigator request failed.");
    } finally {
      setLoading(false);
    }
  };

  const refreshMemory = async () => {
    if (!caseId) return;
    setLoading(true);
    try {
      await apiJson(`/api/v1/investigations/${caseId}/memory/refresh`, { method: "POST" }, token);
      await ask("Summarize refreshed investigator memory and report readiness");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Memory refresh failed.");
    } finally {
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask();
  };

  const planPlaybook = async () => {
    if (!caseId || !playbookId) return;
    setLoading(true);
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${caseId}/playbooks/${playbookId}/plan`, { method: "POST" }, token);
      setPlaybookPlan(payload.data || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Playbook plan failed.");
    } finally {
      setLoading(false);
    }
  };

  const runPlaybook = async (confirmed: boolean) => {
    if (!caseId || !playbookId) return;
    setLoading(true);
    try {
      const payload = await apiJson<any>(`/api/v1/investigations/${caseId}/playbooks/${playbookId}/run`, { method: "POST", body: JSON.stringify({ confirmed }) }, token);
      setPlaybookPlan(payload.data || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Playbook run failed.");
    } finally {
      setLoading(false);
    }
  };

  if (!cases.length) {
    return <section className="investigator-panel"><div className="investigator-empty"><BrainCircuit size={28} /><h2>No case available</h2><p>Create or open an investigation first. The brain will not fabricate intelligence without case evidence.</p></div></section>;
  }

  return (
    <section className="investigator-panel">
      <header className="investigator-hero">
        <div><span className="micro-label">Investigator Brain</span><h2>Evidence-first local analyst</h2><p>Rules validate facts first. Local LLM assistance is optional and cannot upgrade unsupported findings.</p></div>
        <div className="investigator-case-select"><label>Case<select value={caseId} onChange={(event) => setCaseId(event.target.value)}>{cases.map((item) => <option key={item.id} value={item.id}>{String(item.meta?.case_name || item.target)}</option>)}</select></label><button type="button" onClick={refreshMemory} disabled={loading}><RefreshCw size={14} />Refresh Memory</button></div>
      </header>

      <div className="investigator-layout">
        <aside className="investigator-left">
          <ModelStatusCard status={modelStatus} />
          <ReportReadinessCard readiness={answer?.report_readiness as any} />
          <PlaybookRunner playbooks={playbooks as any} activePlaybook={playbookId} plan={playbookPlan as any} onSelect={setPlaybookId} onPlan={planPlaybook} onRun={(confirmed) => void runPlaybook(confirmed)} />
          <article className="investigator-card">
            <header><BrainCircuit size={15} /><strong>Quick Prompts</strong><span>{activeCase?.target_type || "case"}</span></header>
            <div className="investigator-prompts">{QUICK_PROMPTS.map((item) => <button key={item} type="button" onClick={() => { setPrompt(item); void ask(item); }} disabled={loading}>{item}</button>)}</div>
          </article>
        </aside>

        <main className="investigator-main">
          <form className="investigator-query" onSubmit={submit}>
            <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask the investigator brain..." />
            <button type="submit" disabled={loading}>{loading ? <Loader2 className="spin" size={15} /> : <Send size={15} />} Ask</button>
          </form>
          {error && <div className="investigator-error">{error}</div>}
          <article className="investigator-answer">
            <header><strong>Analyst Brief</strong><span>{answer?.provider || "rules"} / {answer?.mode || "standby"}</span></header>
            <p>{answer?.reply || "Ask for a case summary, validation review, contradictions, or next actions. If evidence is missing, the brain will say insufficient evidence."}</p>
            {!!answer?.evidence_refs?.length && <div className="evidence-ref-row">{answer.evidence_refs.slice(0, 8).map((ref, index) => <code key={String(ref.evidence_id || ref.source_url || index)}>{String(ref.evidence_id || ref.source_url || "evidence")}</code>)}</div>}
            {!!answer?.confidence_warnings?.length && <ul className="confidence-warning-list">{answer.confidence_warnings.map((item) => <li key={item}>{item}</li>)}</ul>}
          </article>

          <div className="investigator-grid">
            <EvidenceMapPanel evidenceMap={evidenceMap as any} />
            <ValidationPanel validation={answer?.validation_summary as any} />
            <NoiseExplanationPanel noise={answer?.noise_summary as any} />
            <NoiseReviewPanel noise={answer?.noise_summary as any} />
            <HypothesisPanel hypotheses={answer?.hypotheses as any} />
            <CorrelationExplainer correlations={correlations as any} />
            <NextActionPanel actions={answer?.next_actions as any} />
          </div>
        </main>
      </div>
    </section>
  );
}
