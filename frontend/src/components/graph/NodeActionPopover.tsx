import type { CSSProperties } from "react";
import type { ApiNode, TransformDefinition } from "../../lib/types";
import { getStudioNodeConfidence, getStudioNodeIcon, getStudioNodeVisual } from "../../lib/studioMappers";

const NODE_ICON_PATHS: Record<string, string> = {
  identity: `<circle cx="32" cy="21" r="9"/><path d="M15 53c3-12 10-18 17-18s14 6 17 18"/>`,
  fingerprint: `<path d="M20 28a12 12 0 0124 0v4"/><path d="M14 34v-6a18 18 0 0136 0v5"/><path d="M25 56c-3-8-3-16-1-24a8 8 0 0116 0c1 8-1 15-5 21"/><path d="M32 30v10"/>`,
  mail: `<rect x="10" y="18" width="44" height="30" rx="2"/><path d="M12 21l20 16 20-16"/>`,
  phone: `<path d="M21 10h22v44H21z"/><path d="M29 47h6"/>`,
  globe: `<circle cx="32" cy="32" r="22"/><path d="M10 32h44M32 10c8 8 8 36 0 44M32 10c-8 8-8 36 0 44"/>`,
  link: `<path d="M25 23l-5 5a10 10 0 0014 14l5-5"/><path d="M39 41l5-5a10 10 0 00-14-14l-5 5"/><path d="M25 39l14-14"/>`,
  server: `<rect x="12" y="14" width="40" height="12" rx="2"/><rect x="12" y="30" width="40" height="12" rx="2"/><rect x="12" y="46" width="40" height="8" rx="2"/><path d="M20 20h4M20 36h4M20 50h4"/>`,
  pin: `<path d="M32 56s18-18 18-32A18 18 0 1014 24c0 14 18 32 18 32z"/><circle cx="32" cy="24" r="6"/>`,
  image: `<rect x="12" y="16" width="40" height="32" rx="3"/><path d="M18 42l10-10 8 8 5-5 7 7"/><circle cx="42" cy="25" r="4"/>`,
  wallet: `<path d="M10 20h44v30H10z"/><path d="M44 30h12v12H44z"/><path d="M22 42V18h24"/>`,
  transaction: `<path d="M12 22h34l-8-8M46 22l-8 8"/><path d="M52 42H18l8-8M18 42l8 8"/>`,
  file: `<path d="M18 10h21l9 9v35H18z"/><path d="M39 10v12h9M25 32h15M25 41h12"/>`,
  alert: `<path d="M32 9l25 44H7z"/><path d="M32 24v13M32 45h.1"/>`,
  target: `<circle cx="32" cy="32" r="20"/><circle cx="32" cy="32" r="8"/><path d="M32 6v10M32 48v10M6 32h10M48 32h10"/>`,
};

type Props = {
  node: ApiNode;
  mode: "compact" | "full";
  style: CSSProperties;
  transforms: TransformDefinition[];
  loadingId?: string | null;
  error?: string | null;
  onClose: () => void;
  onRun: (transformId: string, node: ApiNode) => void;
  onOpenInspector: () => void;
  onOpenEvidence: (node: ApiNode) => void;
  onMarkNoise: (node: ApiNode) => void;
  onCorrelate?: () => void;
  onOpenTransformLibrary: () => void;
  onExpand: () => void;
};

export default function NodeActionPopover({ node, mode, style, transforms, loadingId, error, onClose, onRun, onOpenInspector, onOpenEvidence, onMarkNoise, onCorrelate, onOpenTransformLibrary, onExpand }: Props) {
  const visual = getStudioNodeVisual(node.type);
  const icon = NODE_ICON_PATHS[getStudioNodeIcon(node.type)] || NODE_ICON_PATHS.target;
  const confidence = getStudioNodeConfidence(node);
  const recommended = transforms.find((item) => item.enabled && item.source_category !== "fallback") || null;
  const visibleTransforms = mode === "full" ? transforms : transforms.slice(0, 4);
  return (
    <section className={mode === "full" ? "studio-node-action-menu full" : "studio-node-action-menu"} style={style}>
      <header>
        <span className="studio-action-glyph" style={{ "--node-accent": visual.accent } as CSSProperties}>
          <svg viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: icon }} /></svg>
        </span>
        <div><strong>{node.label || node.value || node.id}</strong><span>{node.type} / {confidence}% confidence / {String(node.source || node.data?.source || "graph")}</span></div>
        <button type="button" onClick={onClose} aria-label="Close node actions" title="Close">×</button>
      </header>
      <div className="studio-node-primary-actions">
        <button type="button" disabled={!recommended || Boolean(loadingId)} onClick={() => recommended && onRun(recommended.id, node)}>Run Recommended</button>
        <button type="button" onClick={onOpenInspector}>Open Inspector</button>
        <button type="button" onClick={() => onOpenEvidence(node)}>Evidence</button>
        <button type="button" onClick={onCorrelate}>Correlate</button>
        <button type="button" className="danger" onClick={() => onMarkNoise(node)}>Mark Noise</button>
      </div>
      {error && <div className="studio-node-transform-error">{error}</div>}
      <div className="studio-node-transform-list">
        {!transforms.length && <div className="studio-node-transform-empty"><strong>No valid transforms for this entity type</strong><button type="button" onClick={onOpenTransformLibrary}>Open Transform Library</button></div>}
        {visibleTransforms.map((transform) => {
          const fallback = transform.source_category === "fallback";
          const disabledReason = fallback ? "Registry unavailable — fallback transform catalog shown" : !transform.enabled ? transform.disabled_reason || "Disabled by registry" : "";
          return (
            <article key={transform.id} className={disabledReason ? "studio-node-transform-card disabled" : "studio-node-transform-card"}>
              <div><strong>{transform.label}</strong><p>{transform.description}</p><code>{transform.input_types.join(", ")} → {transform.output_types.join(", ")}</code></div>
              <span>{transform.requires_api_key ? "API KEY" : transform.passive === false ? "DEEP" : "PASSIVE"}</span>
              {fallback && <em>FALLBACK</em>}
              {disabledReason && <small>{disabledReason}</small>}
              <button type="button" disabled={Boolean(disabledReason) || loadingId === transform.id} onClick={() => onRun(transform.id, node)}>{loadingId === transform.id ? "Running" : "Run"}</button>
            </article>
          );
        })}
      </div>
      {mode !== "full" && transforms.length > 4 && <button className="studio-node-expand-menu" type="button" onClick={onExpand}>Show all {transforms.length} transforms</button>}
    </section>
  );
}
