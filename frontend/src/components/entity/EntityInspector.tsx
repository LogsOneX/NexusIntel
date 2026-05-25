import { useEffect, useMemo, useState } from "react";
import { Database, Download, FileJson, GitBranch, NotebookPen, ShieldAlert, Sparkles } from "lucide-react";
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
  const entityType = selectedNode?.type || pendingEntityType || "entity";
  const entityLabel = selectedNode?.label || activeCase?.target || target || "No active entity";
  const entityValue = selectedNode?.value || target || "Select a node, add an entity, or run lookup.";
  const confidenceLabel = selectedNode?.confidence || (target.trim() ? "pending" : "idle");
  return (
    <aside className={open ? "entity-spec premium-entity-inspector reference-inspector" : "entity-spec premium-entity-inspector reference-inspector closed"}>
      <header className="ref-inspector-toolbar">
        <div><FileJson size={14} /><span>{selectedNode ? "Entity Inspector" : "System Inspector"}</span></div>
        <code>{selectedEvidenceRefs.length} proof</code>
      </header>
      <section className="ref-inspector-hero">
        <div className="ref-entity-glyph">{entityType.slice(0, 3).toUpperCase()}</div>
        <div>
          <p><span>{entityType}</span><b>{confidenceLabel}</b></p>
          <strong title={entityValue}>{entityLabel}</strong>
          <code>{entityValue}</code>
        </div>
      </section>
      <Tabs items={tabItems} active={tab} onChange={setTab} ariaLabel="Entity inspector tabs" />
      <div className="inspector-body">
        {tab === "overview" && <EntityOverviewTab node={selectedNode} activeCase={activeCase} analystPipeline={analystPipeline} pendingEntityType={pendingEntityType} pendingTransforms={pendingTransforms} />}
        {tab === "evidence" && <EntityEvidenceTab evidence={selectedEvidenceRefs.length ? selectedEvidenceRefs : []} onOpenEvidence={onOpenEvidence} />}
        {tab === "transforms" && <EntityTransformsTab node={selectedNode} transforms={transforms} analystPipeline={analystPipeline} loadingId={transformLoading} onRun={onRunRegisteredTransform} />}
        {tab === "timeline" && <EntityTimelineTab node={selectedNode} evidence={selectedEvidenceRefs} />}
        {tab === "raw" && <EntityRawTab node={selectedNode} />}
        {tab === "notes" && <section className="analyst-notes"><header><NotebookPen size={14} /><strong>Analyst Notes</strong></header><textarea value={notes} onChange={(event) => { setNotes(event.target.value); writeLocalJson(noteKey, event.target.value); }} placeholder="Local analyst notes. Stored in this browser until backend notes exist." /></section>}
        {!selectedNode && !target.trim() && tab === "overview" && <div className="ref-inspector-empty"><Database size={22} /><EmptyState title="No active entity" message="Select a node, add an entity, or run a lookup from the command bar." /></div>}
        {selectedNode && tab === "overview" && !selectedEvidenceRefs.length && <div className="ref-signal-warning"><Sparkles size={13} /><span>Finding unsupported until evidence, hash, source URL, or public-source citation is attached.</span></div>}
      </div>
      <footer className="inspector-actions"><button type="button" onClick={onRunCorrelationEngine}><GitBranch size={13} />Correlate</button>{selectedNode && onMarkNoise && <button className="danger" type="button" onClick={onMarkNoise}><ShieldAlert size={13} />Mark Noise</button>}<button type="button" onClick={() => onExportPacket("html")}><Download size={13} />Report</button><button type="button" onClick={() => onExportPacket("json")}>Evidence JSON</button><button type="button" onClick={() => onExportPacket("csv")}>CSV IOCs</button></footer>
      <LeadQueuePanel analystPipeline={analystPipeline} compact />
      <CoverageMatrix matrix={analystPipeline?.coverage_matrix || null} compact />
      {evidenceItems.length > selectedEvidenceRefs.length && <small className="muted-copy">Case evidence available: {evidenceItems.length}. Use Evidence Browser for full filtering.</small>}
    </aside>
  );
}
