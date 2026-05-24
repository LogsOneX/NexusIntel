import { useEffect, useMemo, useState } from "react";
import { FileJson, GitBranch, NotebookPen, Download, ShieldAlert } from "lucide-react";
import type { AnalystPipeline, ApiNode, EvidenceRecord, Investigation, TransformDefinition } from "../../lib/types";
import { readLocalJson, writeLocalJson } from "../../lib/storage";
import Tabs from "../common/Tabs";
import EmptyState from "../common/EmptyState";
import LeadQueuePanel from "../cases/LeadQueuePanel";
import CoverageMatrix from "../cases/CoverageMatrix";
import EntityOverviewTab from "./EntityOverviewTab";
import EntityEvidenceTab from "./EntityEvidenceTab";
import EntityTransformsTab from "./EntityTransformsTab";
import EntityTimelineTab from "./EntityTimelineTab";
import EntityRawTab from "./EntityRawTab";

export default function EntityInspector({
  open,
  selectedNode,
  activeCase,
  target,
  pendingEntityType,
  pendingTransforms,
  selectedTransforms,
  analystPipeline,
  evidenceItems,
  selectedEvidenceRefs,
  transformLoading,
  onOpenEvidence,
  onRunRegisteredTransform,
  onRunCorrelationEngine,
  onExportPacket,
  onMarkNoise,
}: {
  open: boolean;
  selectedNode: ApiNode | null;
  activeCase: Investigation | null;
  target: string;
  pendingEntityType: string;
  pendingTransforms: TransformDefinition[];
  selectedTransforms: TransformDefinition[];
  analystPipeline: AnalystPipeline | null;
  evidenceItems: EvidenceRecord[];
  selectedEvidenceRefs: EvidenceRecord[];
  transformLoading: string | null;
  onOpenEvidence: (id: string) => void;
  onRunRegisteredTransform: (id: string) => void;
  onRunCorrelationEngine: () => void;
  onExportPacket: (format: "html" | "pdf" | "json" | "csv" | "graph_json") => void;
  onMarkNoise?: () => void;
}) {
  const [tab, setTab] = useState("overview");
  const noteKey = selectedNode ? `nexusintel.note.${selectedNode.id}` : "nexusintel.note.pending";
  const [notes, setNotes] = useState("");

  useEffect(() => {
    setTab("overview");
  }, [selectedNode?.id]);

  useEffect(() => {
    setNotes(readLocalJson<string>(noteKey, ""));
  }, [noteKey]);

  const tabItems = useMemo(() => [
    { id: "overview", label: "Summary" },
    { id: "evidence", label: "Evidence", count: selectedEvidenceRefs.length },
    { id: "transforms", label: "Transforms", count: (selectedNode ? selectedTransforms : pendingTransforms).length },
    { id: "timeline", label: "Timeline" },
    { id: "raw", label: "Raw" },
    { id: "notes", label: "Notes" },
  ], [pendingTransforms, selectedEvidenceRefs.length, selectedNode, selectedTransforms]);

  const transforms = selectedNode ? selectedTransforms : pendingTransforms;
  return (
    <aside className={open ? "entity-spec premium-entity-inspector" : "entity-spec premium-entity-inspector closed"}>
      <div className="inspector-header"><div><FileJson size={15} /><span>Entity Inspector</span></div><strong>{selectedNode?.label || activeCase?.target || "No active entity"}</strong><code>{selectedNode ? `${selectedNode.type} / ${selectedNode.confidence || "medium"}` : target.trim() ? `${pendingEntityType} / pending` : "select a node"}</code></div>
      <Tabs items={tabItems} active={tab} onChange={setTab} ariaLabel="Entity inspector tabs" />
      <div className="inspector-body">
        {tab === "overview" && <EntityOverviewTab node={selectedNode} activeCase={activeCase} analystPipeline={analystPipeline} pendingEntityType={pendingEntityType} pendingTransforms={pendingTransforms} />}
        {tab === "evidence" && <EntityEvidenceTab evidence={selectedEvidenceRefs.length ? selectedEvidenceRefs : []} onOpenEvidence={onOpenEvidence} />}
        {tab === "transforms" && <EntityTransformsTab node={selectedNode} transforms={transforms} analystPipeline={analystPipeline} loadingId={transformLoading} onRun={onRunRegisteredTransform} />}
        {tab === "timeline" && <EntityTimelineTab node={selectedNode} evidence={selectedEvidenceRefs} />}
        {tab === "raw" && <EntityRawTab node={selectedNode} />}
        {tab === "notes" && <section className="analyst-notes"><header><NotebookPen size={14} /><strong>Analyst Notes</strong></header><textarea value={notes} onChange={(event) => { setNotes(event.target.value); writeLocalJson(noteKey, event.target.value); }} placeholder="Local analyst notes. Stored in this browser until backend notes exist." /></section>}
        {!selectedNode && !target.trim() && tab === "overview" && <EmptyState title="Select or add an entity" message="The inspector is evidence-first. Node source, evidence hash, legal note, and confidence reason appear when available." />}
      </div>
      <footer className="inspector-actions"><button type="button" onClick={onRunCorrelationEngine}><GitBranch size={13} />Correlate</button>{selectedNode && onMarkNoise && <button className="danger" type="button" onClick={onMarkNoise}><ShieldAlert size={13} />Mark Noise</button>}<button type="button" onClick={() => onExportPacket("html")}><Download size={13} />Report</button><button type="button" onClick={() => onExportPacket("json")}>Evidence JSON</button><button type="button" onClick={() => onExportPacket("csv")}>CSV IOCs</button></footer>
      <LeadQueuePanel analystPipeline={analystPipeline} compact />
      <CoverageMatrix matrix={analystPipeline?.coverage_matrix || null} compact />
      {evidenceItems.length > selectedEvidenceRefs.length && <small className="muted-copy">Case evidence available: {evidenceItems.length}. Use Evidence Browser for full filtering.</small>}
    </aside>
  );
}

