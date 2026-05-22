import type { NexusYjsSession } from "./yjsProvider";

export function updateLocalPresence(session: NexusYjsSession, operator: string, state: Record<string, unknown>) {
  session.provider.awareness.setLocalStateField("operator", operator);
  session.provider.awareness.setLocalStateField("state", { ...state, time: new Date().toISOString() });
}
