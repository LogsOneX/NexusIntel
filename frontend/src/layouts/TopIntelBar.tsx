import { Activity, AlertTriangle, Database, KeyRound, Layers3 } from "lucide-react";
import MetricCard from "../components/common/MetricCard";

export default function TopIntelBar({ totalCases = 0, activeTasks = 0, highRiskCases = 0, evidenceCount = 0, connectorSummary = "not checked" }: { totalCases?: number; activeTasks?: number; highRiskCases?: number; evidenceCount?: number; connectorSummary?: string }) {
  return (
    <div className="top-intel-bar" aria-label="Operational metrics">
      <MetricCard label="Cases" value={totalCases} detail="investigations" icon={Layers3} />
      <MetricCard label="Active Tasks" value={activeTasks} detail="running" icon={Activity} tone={activeTasks ? "info" : "default"} />
      <MetricCard label="High Risk" value={highRiskCases} detail="needs review" icon={AlertTriangle} tone={highRiskCases ? "danger" : "default"} />
      <MetricCard label="Evidence" value={evidenceCount} detail="raw refs" icon={Database} />
      <MetricCard label="Connectors" value={connectorSummary} detail="BYOK health" icon={KeyRound} />
    </div>
  );
}

