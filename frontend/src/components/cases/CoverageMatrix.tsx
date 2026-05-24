import { HelpCircle } from "lucide-react";
import type { CoverageMatrixData, GraphPayload, CaseHealth } from "../../lib/types";
import { COVERAGE_COLUMNS, COVERAGE_ROWS, inferCoverageMatrix } from "../../lib/graph";

function valueTone(value: number, row: string) {
  if (!value) return "empty";
  if (row === "verified" || row === "found") return "good";
  if (row === "noisy" || row === "failed") return "bad";
  if (row === "requires API key" || row === "disabled") return "warn";
  return "active";
}

export default function CoverageMatrix({ matrix, graph, health, compact = false }: { matrix?: CoverageMatrixData | null; graph?: GraphPayload | null; health?: CaseHealth | null; compact?: boolean }) {
  const resolved = matrix || inferCoverageMatrix(graph, health);
  const rows = resolved.rows?.length ? resolved.rows : COVERAGE_ROWS;
  const columns = resolved.columns?.length ? resolved.columns : COVERAGE_COLUMNS;
  return (
    <section className={compact ? "coverage-matrix compact" : "coverage-matrix"}>
      <header><strong>OSINT Coverage Matrix</strong><span title="Inferred from graph data when backend coverage is unavailable"><HelpCircle size={13} /> inferred-safe</span></header>
      <div className="coverage-scroll" role="region" aria-label="OSINT coverage matrix">
        <table>
          <thead><tr><th>State</th>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>{rows.map((row) => <tr key={row}><th>{row}</th>{columns.map((column) => { const value = Number(resolved.matrix?.[row]?.[column] || 0); return <td className={valueTone(value, row)} key={`${row}-${column}`} title={`${column}: ${row} ${value}`}>{value || ""}</td>; })}</tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

