import { create } from "zustand";

export type CollaborationPatch = {
  type: "node_position" | "graph_patch" | "presence";
  payload: Record<string, unknown>;
  operator?: string;
  time?: string;
};

type GraphStore = {
  workspaceId: string | null;
  patches: CollaborationPatch[];
  setWorkspaceId: (workspaceId: string | null) => void;
  applyPatch: (patch: CollaborationPatch) => void;
  clearPatches: () => void;
};

export const useGraphStore = create<GraphStore>((set) => ({
  workspaceId: null,
  patches: [],
  setWorkspaceId: (workspaceId) => set({ workspaceId }),
  applyPatch: (patch) => set((state) => ({ patches: [...state.patches.slice(-199), patch] })),
  clearPatches: () => set({ patches: [] }),
}));
