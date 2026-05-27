import { useMemo, useState } from "react";
import { FileUp, Upload } from "lucide-react";
import { apiJson } from "../../lib/api";
import EmptyState from "../common/EmptyState";
import ImportPreviewTable from "./ImportPreviewTable";
import FieldMappingPanel from "./FieldMappingPanel";

type ImportType = "spiderfoot_csv" | "maltego_csv" | "generic_ioc_csv" | "urlscan_json" | "shodan_json" | "ghunt_json" | "holehe_json" | "maigret_json" | "sherlock_json";

function parseCsv(text: string): Array<Record<string, unknown>> {
  const lines = text.split(/\r?\n/).filter(Boolean);
  const headers = (lines.shift() || "").split(",").map((item) => item.trim());
  return lines.slice(0, 60).map((line) => Object.fromEntries(line.split(",").map((value, index) => [headers[index] || `column_${index + 1}`, value.trim()])));
}

export default function ImportWizard({ token, investigationId }: { token: string; investigationId?: string | null }) {
  const [kind, setKind] = useState<ImportType>("spiderfoot_csv");
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [mapping, setMapping] = useState<Record<string, unknown>>({});
  const columns = useMemo(() => Array.from(new Set(rows.flatMap((row) => Object.keys(row)))), [rows]);
  const loadFile = async (file: File) => {
    const text = await file.text();
    try {
      const payload = await apiJson<any>("/api/v1/importers/preview", { method: "POST", body: JSON.stringify({ format: kind, content: text }) }, token);
      setRows(payload.data.preview?.rows || []);
      setMapping(payload.data.mapping || {});
      setMessage(null);
    } catch (error) {
      try {
        if (file.name.toLowerCase().endsWith(".json") || kind.endsWith("json")) {
          const parsed = JSON.parse(text);
          const list = Array.isArray(parsed) ? parsed : Array.isArray(parsed.items) ? parsed.items : [parsed];
          setRows(list.slice(0, 60));
        } else {
          setRows(parseCsv(text));
        }
        setMapping({});
        setMessage("Backend preview unavailable; using local preview only.");
      } catch (inner) {
        setRows([]);
        setMessage(inner instanceof Error ? inner.message : "Unable to parse file");
      }
    }
  };
  const submit = async () => {
    try {
      await apiJson("/api/v1/imports", { method: "POST", body: JSON.stringify({ type: kind, investigation_id: investigationId || null, preview_only: false, rows, mapping }) }, token);
      setMessage("Import submitted to backend.");
    } catch (error) {
      setMessage(error instanceof Error ? `${error.message}. Backend importer may not be available yet.` : "Backend importer not available yet.");
    }
  };
  return (
    <section className="import-wizard">
      <header><FileUp size={16} /><strong>Import Wizard</strong><span>Preview before import</span></header>
      <div className="import-controls"><select value={kind} onChange={(event) => setKind(event.target.value as ImportType)}><option value="spiderfoot_csv">SpiderFoot CSV</option><option value="maltego_csv">Maltego CSV</option><option value="ghunt_json">GHunt JSON</option><option value="holehe_json">Holehe JSON</option><option value="maigret_json">Maigret JSON</option><option value="sherlock_json">Sherlock JSON</option><option value="urlscan_json">URLScan JSON</option><option value="shodan_json">Shodan JSON</option><option value="generic_ioc_csv">Generic IOC CSV</option></select><label className="file-drop"><Upload size={15} />Select file<input type="file" accept=".csv,.json,.txt" onChange={(event) => { const file = event.target.files?.[0]; if (file) void loadFile(file); }} /></label></div>
      {message && <div className="nx-alert"><span>{message}</span></div>}
      {!rows.length ? <EmptyState title="No file loaded" message="Client-side preview only. Nothing is inserted into a case graph until backend import succeeds." icon={FileUp} /> : <><FieldMappingPanel columns={columns} /><ImportPreviewTable rows={rows} /><button className="nx-primary" type="button" onClick={submit}>Confirm Import</button></>}
    </section>
  );
}

