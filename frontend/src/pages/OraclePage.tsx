import type { PageProps } from "../lib/types";
import InvestigatorPanel from "../components/investigator/InvestigatorPanel";

export default function OraclePage({ token }: PageProps) {
  return <section className="oracle-page premium-page"><header className="page-header premium-page-header"><div><span className="micro-label">Investigator Brain</span><h1>Evidence-First Local Analyst</h1></div></header><InvestigatorPanel token={token} /></section>;
}
