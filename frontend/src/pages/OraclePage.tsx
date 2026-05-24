import type { PageProps } from "../lib/types";
import OraclePanel from "../components/OraclePanel";

export default function OraclePage({ token }: PageProps) {
  return <section className="oracle-page premium-page"><header className="page-header premium-page-header"><div><span className="micro-label">AI Oracle</span><h1>Intelligence Analyst Interface</h1></div></header><OraclePanel token={token} title="Standalone Oracle" /></section>;
}

