import type { SessionState } from "./types";

const AUTH_KEY = "nexusintel.session";

export function readSession(): SessionState {
  try {
    const raw = window.localStorage.getItem(AUTH_KEY);
    if (!raw) return { token: null, user: null };
    return JSON.parse(raw) as SessionState;
  } catch {
    return { token: null, user: null };
  }
}

export function saveSession(session: SessionState) {
  window.localStorage.setItem(AUTH_KEY, JSON.stringify(session));
}

export function clearSession() {
  window.localStorage.removeItem(AUTH_KEY);
}

export function readLocalJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeLocalJson<T>(key: string, value: T) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

