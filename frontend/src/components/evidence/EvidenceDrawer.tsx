import Drawer from "../common/Drawer";
import type { EvidenceRecord } from "../../lib/types";
import RawEvidenceViewer from "./RawEvidenceViewer";

export default function EvidenceDrawer({ open, evidence, onClose }: { open: boolean; evidence: EvidenceRecord | null; onClose: () => void }) {
  return <Drawer open={open} title="Raw Evidence" onClose={onClose}><RawEvidenceViewer evidence={evidence} /></Drawer>;
}

