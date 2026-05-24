import type { LucideIcon } from "lucide-react";

export default function MetricCard({ label, value, detail, icon: Icon, tone = "default" }: { label: string; value: string | number; detail?: string; icon?: LucideIcon; tone?: string }) {
  return (
    <article className={`metric-card ${tone}`}>
      <div>{Icon && <Icon size={15} />}<span>{label}</span></div>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

