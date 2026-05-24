import { Activity, AlertTriangle, GitBranch, ShieldCheck } from "lucide-react";
import type { CaseHealth } from "../../lib/types";
import MetricCard from "../common/MetricCard";

export default function CaseHealthCard({ health }: { health: CaseHealth | null }) {
  const intel = health?.intelligence;
  return (
    <section className="case-health-card">
      <header><Activity size={15} /><strong>Case Health</strong><span>{health?.status || "not loaded"}</span></header>
      <div className="case-health-grid">
        <MetricCard label="Health" value={health ? `${health.score}%` : "--"} detail="collection posture" icon={ShieldCheck} />
        <MetricCard label="Risk" value={intel ? `${intel.risk_score}%` : "--"} detail="case pressure" icon={AlertTriangle} tone={(intel?.risk_score || 0) > 70 ? "danger" : "default"} />
        <MetricCard label="Sources" value={intel ? `${intel.source_reliability}%` : "--"} detail="reliability" icon={Activity} />
        <MetricCard label="Clusters" value={intel?.communities?.length ?? "--"} detail="communities" icon={GitBranch} />
      </div>
      {(health?.recommendations || []).slice(0, 2).map((item, index) => <p key={index}><strong>{item.action}</strong><span>{item.reason}</span></p>)}
    </section>
  );
}

