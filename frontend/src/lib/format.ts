import type { Investigation } from "./types";

export function terminalPrefix(level: string): string {
  if (["tool", "info", "success", "warning"].includes(level)) return "[OSINT]";
  if (level === "error") return "[ALERT]";
  return "[SYS]";
}

export function formatDate(value?: string | null): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

export function caseTitle(item: Investigation | null | undefined): string {
  if (!item) return "No active case";
  return String(item.meta?.case_name || item.target || "Untitled Investigation");
}

export function safeString(value: unknown, fallback = "--"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return fallback;
  }
}

export function upperSnake(value: string): string {
  const normalized = value.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return (normalized || "UNKNOWN").toUpperCase();
}

