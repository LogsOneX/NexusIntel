import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

export type NexusYjsSession = {
  doc: Y.Doc;
  provider: WebsocketProvider;
  graphMap: Y.Map<unknown>;
};

export function createNexusYjsSession(workspaceId: string): NexusYjsSession {
  const url = import.meta.env.VITE_YJS_WS_URL || "ws://127.0.0.1:1234";
  const doc = new Y.Doc();
  const provider = new WebsocketProvider(url, `nexusintel:${workspaceId}`, doc);
  const graphMap = doc.getMap("graph");
  return { doc, provider, graphMap };
}
