import { create } from "zustand";

export type PresenceState = {
  operator: string;
  cursor?: { x: number; y: number };
  selectedNode?: string;
  time?: string;
};

type CollaborationStore = {
  connected: boolean;
  presence: Record<string, PresenceState>;
  setConnected: (connected: boolean) => void;
  setPresence: (presence: Record<string, PresenceState>) => void;
};

export const useCollaborationStore = create<CollaborationStore>((set) => ({
  connected: false,
  presence: {},
  setConnected: (connected) => set({ connected }),
  setPresence: (presence) => set({ presence }),
}));
