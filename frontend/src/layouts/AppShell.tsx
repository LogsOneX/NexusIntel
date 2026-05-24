import { useEffect, useMemo, useState } from "react";
import SidebarNav from "./SidebarNav";
import CommandPalette from "../components/common/CommandPalette";
import type { CommandItem } from "../lib/types";

export default function AppShell({ route, user, collapsed, setCollapsed, navigate, logout, children, commands = [] }: { route: string; user: string; collapsed: boolean; setCollapsed: (value: boolean) => void; navigate: (path: string) => void; logout: () => void; children: React.ReactNode; commands?: CommandItem[] }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const allCommands = useMemo<CommandItem[]>(() => [
    { id: "new-investigation", label: "New Investigation", description: "Open the graph workspace and focus target input", shortcut: "G", group: "Cases", action: () => navigate("/graph") },
    { id: "dashboard", label: "Open Dashboard", group: "Navigation", action: () => navigate("/dashboard") },
    { id: "workspace", label: "Open Workspace", group: "Navigation", action: () => navigate("/workspace") },
    { id: "graph", label: "Open Network Graph", group: "Navigation", action: () => navigate("/graph") },
    { id: "oracle", label: "Ask Oracle", group: "Navigation", action: () => navigate("/oracle") },
    { id: "settings", label: "Open Connector Center", group: "Navigation", action: () => navigate("/settings") },
    ...commands,
  ], [commands, navigate]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <main className={collapsed ? "command-shell nav-collapsed premium-shell" : "command-shell premium-shell"}>
      <SidebarNav route={route} user={user} collapsed={collapsed} setCollapsed={setCollapsed} navigate={navigate} logout={logout} />
      <section className="command-content premium-content">{children}</section>
      <CommandPalette open={paletteOpen} commands={allCommands} onClose={() => setPaletteOpen(false)} />
    </main>
  );
}

