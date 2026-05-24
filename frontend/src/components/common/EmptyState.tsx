import { Inbox } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export default function EmptyState({ title, message, action, icon: Icon = Inbox }: { title: string; message?: string; action?: React.ReactNode; icon?: LucideIcon }) {
  return (
    <div className="empty-state premium-empty">
      <Icon size={22} />
      <strong>{title}</strong>
      {message && <p>{message}</p>}
      {action && <div>{action}</div>}
    </div>
  );
}

