import type { EvidenceRecord } from "../../lib/types";
import EmptyState from "../common/EmptyState";
import EvidenceCard from "../evidence/EvidenceCard";

export default function EntityEvidenceTab({ evidence, onOpenEvidence }: { evidence: EvidenceRecord[]; onOpenEvidence: (id: string) => void }) {
  if (!evidence.length) return <EmptyState title="No linked raw evidence" message="Run a registered transform to store source URL, timestamp, hash, confidence reason, and legal note." />;
  return <div className="entity-evidence-list">{evidence.map((item) => <EvidenceCard evidence={item} key={item.id} onOpenRaw={onOpenEvidence} />)}</div>;
}

