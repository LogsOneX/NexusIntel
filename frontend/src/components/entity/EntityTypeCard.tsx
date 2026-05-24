import type { LucideIcon } from "lucide-react";

export default function EntityTypeCard({ icon: Icon, label, description, onClick }: { icon: LucideIcon; label: string; description: string; onClick: () => void }) {
  return <button className="entity-type-card" type="button" onClick={onClick}><Icon size={18} /><span><strong>{label}</strong><small>{description}</small></span></button>;
}
