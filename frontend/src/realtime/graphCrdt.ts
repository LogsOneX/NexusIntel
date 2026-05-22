import type { NexusYjsSession } from "./yjsProvider";

export function publishNodePosition(session: NexusYjsSession, nodeId: string, position: { x: number; y: number }) {
  session.graphMap.set(`node:${nodeId}:position`, { ...position, updated_at: new Date().toISOString() });
}

export function publishGraphPatch(session: NexusYjsSession, patch: Record<string, unknown>) {
  session.graphMap.set(`patch:${crypto.randomUUID()}`, { ...patch, updated_at: new Date().toISOString() });
}
