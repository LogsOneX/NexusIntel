import { familyForEntity } from "./entityOntology";

export type EntityVisual = {
  kind: string;
  family: string;
  label: string;
  glyph: string;
  color: string;
  accent: string;
  shape: "card";
  size: "sm" | "md" | "lg";
  priority: number;
  borderStyle: "solid" | "dashed";
  defaultConfidence: number;
  description: string;
};

const GLYPHS: Record<string, string> = {
  username: "user", email: "mail", domain: "globe", ip: "server", phone: "phone", profile: "id", location: "pin", google_maps_review: "star", crypto_wallet: "wallet", crypto_transaction: "ledger", image_asset: "image", document: "file", target: "crosshair",
};

export function visualForEntity(kind: string): EntityVisual {
  const family = familyForEntity(kind);
  const candidate = kind.includes("candidate") || kind.includes("possible");
  return {
    kind,
    family,
    label: kind.replaceAll("_", " ").toUpperCase(),
    glyph: GLYPHS[kind] || GLYPHS[family] || "node",
    color: "#111419",
    accent: kind.includes("risk") || kind.includes("suspicious") ? "#d84a4a" : candidate ? "#c58a36" : "#7aa7c7",
    shape: "card",
    size: kind === "target" || kind === "investigation_root" ? "lg" : "md",
    priority: kind === "target" ? 100 : 50,
    borderStyle: candidate ? "dashed" : "solid",
    defaultConfidence: candidate ? 45 : 70,
    description: `${family} entity`,
  };
}
