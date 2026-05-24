export const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function apiJson<T = any>(path: string, options?: RequestInit, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {};
  const optionHeaders = (options?.headers || {}) as Record<string, string>;
  const isForm = typeof FormData !== "undefined" && options?.body instanceof FormData;
  if (!isForm) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...optionHeaders },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.detail || payload.message || `Request failed: ${response.status}`);
  }
  return payload as T;
}

export async function downloadFile(path: string, token: string | null, fallbackName: string) {
  const response = await fetch(`${API_BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename=([^;]+)/i);
  const fileName = match ? match[1].replaceAll('"', "") : fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function wsUrl(taskId: string): string {
  const configured = import.meta.env.VITE_WS_BASE;
  if (configured) return `${configured}/api/v1/ws/logs/${taskId}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/ws/logs/${taskId}`;
}

