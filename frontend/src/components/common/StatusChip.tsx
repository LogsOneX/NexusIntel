import { AlertTriangle, CheckCircle2, CircleDashed, KeyRound, XCircle } from "lucide-react";

export type StatusTone = "ok" | "warning" | "danger" | "info" | "muted" | "key";

const icons = {
  ok: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: CircleDashed,
  muted: CircleDashed,
  key: KeyRound,
};

export default function StatusChip({ label, tone = "muted", title }: { label: string; tone?: StatusTone; title?: string }) {
  const Icon = icons[tone];
  return <span className={`status-chip ${tone}`} title={title || label}><Icon size={12} />{label}</span>;
}

