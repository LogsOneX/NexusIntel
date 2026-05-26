import { UserCircle } from "lucide-react";
import type { PageProps } from "../lib/types";

export default function AccountPage({ user }: PageProps) {
  return <section className="account-page premium-page studio-page scroll-page"><header className="page-header premium-page-header"><div><span className="micro-label">Account</span><h1>Operator Profile</h1></div></header><div className="command-card premium-card"><UserCircle size={28} /><h2>{user}</h2><p>Local operator session. Logout clears the browser token and returns to the terminal login screen.</p></div></section>;
}
