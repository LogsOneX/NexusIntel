import { Bot, Briefcase, ChevronLeft, ChevronRight, Database, GitBranch, Home, LogOut, Network, Radar, Search, Settings, UserCircle } from "lucide-react";

const ROUTES = [
  { path: "/dashboard", label: "Dashboard", icon: Home },
  { path: "/identity", label: "Identity Search", icon: Search },
  { path: "/workspace", label: "Workspace", icon: Briefcase },
  { path: "/graph", label: "Network Graph", icon: Network },
  { path: "/watchlist", label: "Threat Watchlist", icon: Radar },
  { path: "/evidence", label: "Evidence Vault", icon: Database },
  { path: "/transforms", label: "Transforms", icon: GitBranch },
  { path: "/oracle", label: "AI Oracle", icon: Bot },
  { path: "/settings", label: "Settings", icon: Settings },
  { path: "/account", label: "Account", icon: UserCircle },
];

export default function SidebarNav({ route, user, collapsed, setCollapsed, navigate, logout, onOpenCommandPalette }: { route: string; user: string; collapsed: boolean; setCollapsed: (value: boolean) => void; navigate: (path: string) => void; logout: () => void; onOpenCommandPalette: () => void }) {
  return (
    <aside className="command-sidebar premium-sidebar">
      <button className="command-brand premium-brand" type="button" onClick={onOpenCommandPalette} title="Open command palette">
        <span className="brand-monogram">NX</span>
        <div><strong>NexusIntel</strong><span>Analyst Command</span></div>
      </button>
      <nav aria-label="Primary navigation">
        {ROUTES.map((item) => {
          const Icon = item.icon;
          return <button aria-current={route === item.path ? "page" : undefined} aria-label={item.label} className={route === item.path ? "active" : ""} key={item.path} type="button" onClick={() => navigate(item.path)} title={item.label}><Icon size={17} /><span>{item.label}</span></button>;
        })}
      </nav>
      <div className="sidebar-footer">
        <button type="button" onClick={() => setCollapsed(!collapsed)} title="Collapse sidebar">{collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}<span>Collapse</span></button>
        <button type="button" onClick={logout} title="Logout"><LogOut size={16} /><span>Logout</span></button>
        <code>{user}</code>
      </div>
    </aside>
  );
}
