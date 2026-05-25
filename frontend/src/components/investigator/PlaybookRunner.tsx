import { PlayCircle } from "lucide-react";

type Playbook = { id: string; name: string; description?: string; input_types?: string[] };
type PlaybookPlan = { runnable_steps?: Array<Record<string, any>>; blocked_steps?: Array<Record<string, any>>; required_confirmation?: Array<Record<string, any>>; safety_note?: string };

export default function PlaybookRunner({ playbooks, activePlaybook, plan, onSelect, onPlan }: { playbooks?: Playbook[]; activePlaybook?: string; plan?: PlaybookPlan | null; onSelect: (id: string) => void; onPlan: () => void }) {
  return (
    <article className="investigator-card playbook-runner">
      <header><PlayCircle size={15} /><strong>Playbook Runner</strong><span>{playbooks?.length || 0}</span></header>
      <div className="playbook-controls">
        <select value={activePlaybook || ""} onChange={(event) => onSelect(event.target.value)}>
          {(playbooks || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button type="button" onClick={onPlan} disabled={!activePlaybook}>Plan</button>
      </div>
      <div className="investigator-list compact">
        {(plan?.runnable_steps || []).slice(0, 4).map((item) => <div key={String(item.id)}><strong>{String(item.label || item.id)}</strong><small>{String(item.description || "Runnable passive step")}</small></div>)}
        {!!plan?.required_confirmation?.length && <div><strong>Confirmation Required</strong><small>{plan.required_confirmation.length} broad/deep step(s) require analyst confirmation.</small></div>}
        {!!plan?.blocked_steps?.length && <div><strong>Blocked</strong><small>{plan.blocked_steps.length} step(s) blocked by input type or missing API key.</small></div>}
        {!plan && <p className="empty-copy">Select a playbook and generate a safe execution plan. Steps are not auto-run.</p>}
      </div>
    </article>
  );
}
