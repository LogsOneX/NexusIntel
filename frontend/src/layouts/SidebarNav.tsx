import { Briefcase, Command, Database, FileText, Home, LogOut, Network, Settings, UserCircle } from "lucide-react";

const ROUTES = [
  { path: "/dashboard", label: "Dashboard", icon: Home },
  { path: "/graph", label: "Graph", icon: Network },
  { path: "/workspace", label: "Cases", icon: Briefcase },
  { path: "/evidence", label: "Evidence", icon: Database },
  { path: "/reports", label: "Reports", icon: FileText },
  { path: "/settings", label: "Settings", icon: Settings },
];

export default function SidebarNav({ route, user, collapsed, setCollapsed, navigate, logout, onOpenCommandPalette }: { route: string; user: string; collapsed: boolean; setCollapsed: (value: boolean) => void; navigate: (path: string) => void; logout: () => void; onOpenCommandPalette: () => void }) {
  return (
    <aside className="nexus-sidebar command-sidebar premium-sidebar">
      <button className="command-brand premium-brand" type="button" onClick={onOpenCommandPalette} title="Open command palette">
        <span className="brand-monogram">NX</span>
      </button>
      <nav aria-label="Primary navigation">
        {ROUTES.map((item) => {
          const Icon = item.icon;
          return <button aria-current={route === item.path ? "page" : undefined} aria-label={item.label} className={route === item.path ? "active" : ""} key={item.path} type="button" onClick={() => navigate(item.path)} title={item.label}><Icon size={17} /><span>{item.label}</span></button>;
        })}
      </nav>
      <div className="sidebar-footer">
        <button type="button" onClick={onOpenCommandPalette} title="Command palette"><Command size={16} /><span>Command</span></button>
        <button type="button" onClick={logout} title="Logout"><LogOut size={16} /><span>Logout</span></button>
        <button type="button" title={user || "Operator"}><UserCircle size={16} /><span>{user || "Operator"}</span></button>
      </div>
    </aside>
  );
}
