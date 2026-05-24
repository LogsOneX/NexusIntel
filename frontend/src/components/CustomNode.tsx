import type { ReactElement } from "react";
import { ArrowRightLeft, AtSign, Crosshair, Fingerprint, Globe2, Hash, KeyRound, MapPin, Network, Phone, Star, UserRound, WalletCards } from "lucide-react";

export type EntityKind = "username" | "email" | "domain" | "ip" | "phone" | "crypto_wallet" | "crypto_transaction" | "censored_email" | "censored_phone" | "google_profile" | "google_review" | "location" | "profile" | "platform" | "service" | "signal" | "target";

type CustomNodeProps = {
  kind: string;
  label: string;
  value?: string;
  selected?: boolean;
  confidence?: string;
};

export const ENTITY_KIND_META: Record<string, { label: string; icon: ReactElement; description: string }> = {
  username: { label: "Username", icon: <UserRound size={15} />, description: "public identity pivot" },
  email: { label: "Email", icon: <AtSign size={15} />, description: "mail and workspace pivot" },
  domain: { label: "Domain", icon: <Globe2 size={15} />, description: "DNS and RDAP pivot" },
  ip: { label: "IP", icon: <Network size={15} />, description: "network and reverse DNS pivot" },
  phone: { label: "Phone", icon: <Phone size={15} />, description: "numbering plan pivot" },
  crypto_wallet: { label: "Wallet", icon: <WalletCards size={15} />, description: "blockchain wallet pivot" },
  crypto_transaction: { label: "Tx", icon: <ArrowRightLeft size={15} />, description: "blockchain transaction pivot" },
  censored_email: { label: "Masked Email", icon: <KeyRound size={15} />, description: "partial email recovery hint" },
  censored_phone: { label: "Masked Phone", icon: <KeyRound size={15} />, description: "partial phone recovery hint" },
  google_profile: { label: "Google", icon: <Fingerprint size={15} />, description: "public Google profile pivot" },
  google_review: { label: "Review", icon: <Star size={15} />, description: "public Google Maps review" },
  location: { label: "Location", icon: <MapPin size={15} />, description: "reviewed venue/location" },
  profile: { label: "Profile", icon: <Fingerprint size={15} />, description: "public profile URL" },
  platform: { label: "Platform", icon: <Hash size={15} />, description: "service host" },
  service: { label: "Service", icon: <Crosshair size={15} />, description: "observed capability" },
  signal: { label: "Signal", icon: <Crosshair size={15} />, description: "derived intelligence" },
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
  if (kind === "crypto_wallet") return "₿";
  if (kind === "crypto_transaction" || kind === "transaction") return "TX";
  if (kind === "censored_email" || kind === "censored_phone") return "***";
  if (kind === "google_review") return "★";
  if (kind === "location") return "LOC";
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
