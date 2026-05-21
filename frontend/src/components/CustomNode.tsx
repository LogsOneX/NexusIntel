import { AtSign, Crosshair, Fingerprint, Globe2, Hash, Network, Phone, ShieldAlert, UserRound } from "lucide-react";

export type EntityKind = "username" | "email" | "domain" | "ip" | "phone" | "profile" | "platform" | "service" | "signal" | "guardrail" | "target";

type CustomNodeProps = {
  kind: string;
  label: string;
  value?: string;
  selected?: boolean;
  confidence?: string;
};

export const ENTITY_KIND_META: Record<string, { label: string; icon: JSX.Element; description: string }> = {
  username: { label: "Username", icon: <UserRound size={15} />, description: "public identity pivot" },
  email: { label: "Email", icon: <AtSign size={15} />, description: "mail and workspace pivot" },
  domain: { label: "Domain", icon: <Globe2 size={15} />, description: "DNS and RDAP pivot" },
  ip: { label: "IP", icon: <Network size={15} />, description: "network and reverse DNS pivot" },
  phone: { label: "Phone", icon: <Phone size={15} />, description: "numbering plan pivot" },
  profile: { label: "Profile", icon: <Fingerprint size={15} />, description: "public profile URL" },
  platform: { label: "Platform", icon: <Hash size={15} />, description: "service host" },
  service: { label: "Service", icon: <Crosshair size={15} />, description: "observed capability" },
  signal: { label: "Signal", icon: <Crosshair size={15} />, description: "derived intelligence" },
  guardrail: { label: "Guardrail", icon: <ShieldAlert size={15} />, description: "policy boundary" },
  target: { label: "Target", icon: <Crosshair size={15} />, description: "root entity" },
};

export function platformMark(kind: string, label?: string, value?: string): string {
  const raw = `${label || ""} ${value || ""}`.toLowerCase();
  if (raw.includes("github")) return "GH";
  if (raw.includes("gitlab")) return "GL";
  if (raw.includes("google") || raw.includes("gmail")) return "G";
  if (raw.includes("microsoft") || raw.includes("outlook")) return "MS";
  if (raw.includes("instagram")) return "IG";
  if (raw.includes("linkedin")) return "IN";
  if (raw.includes("reddit")) return "RD";
  if (raw.includes("tiktok")) return "TT";
  if (kind === "email") return "@";
  if (kind === "domain") return "DNS";
  if (kind === "ip") return "IP";
  if (kind === "phone") return "TEL";
  if (kind === "username") return "ID";
  return kind.slice(0, 3).toUpperCase();
}

export function CustomNode({ kind, label, value, selected = false, confidence = "medium" }: CustomNodeProps) {
  const meta = ENTITY_KIND_META[kind] || ENTITY_KIND_META.signal;
  return (
    <div className={selected ? "custom-node selected" : `custom-node ${confidence === "low" ? "low-confidence" : ""}`}>
      <div className="custom-node-mark">{platformMark(kind, label, value)}</div>
      <div className="custom-node-body">
        <span>{meta.label}</span>
        <strong>{label}</strong>
        {value && <code>{value}</code>}
      </div>
    </div>
  );
}

export function EntityPaletteItem({ kind }: { kind: EntityKind }) {
  const meta = ENTITY_KIND_META[kind];
  return (
    <button
      className="entity-palette-item"
      draggable
      type="button"
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("application/x-nexus-entity", kind);
      }}
      title={meta.description}
    >
      {meta.icon}
      <span>{meta.label}</span>
    </button>
  );
}
