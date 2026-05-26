import { useEffect, useMemo, useState } from "react";
import { GitBranch, ShieldCheck } from "lucide-react";
import type { PageProps, TransformDefinition } from "../lib/types";
import { apiJson } from "../lib/api";
import TransformLibrary, { FALLBACK_TRANSFORMS } from "../components/transforms/TransformLibrary";
import StatusChip from "../components/common/StatusChip";

const CATEGORIES = ["all", "Identity", "Infrastructure", "Social/Profile", "Domain/DNS", "IP/ASN", "CTI", "Crypto", "Evidence", "Case hygiene"];

function categoryFor(transform: TransformDefinition) {
  const raw = `${transform.id} ${transform.adapter_id || ""} ${transform.input_types.join(" ")} ${transform.output_types.join(" ")}`.toLowerCase();
  if (raw.includes("email") || raw.includes("username") || raw.includes("phone")) return "Identity";
  if (raw.includes("domain") || raw.includes("dns") || raw.includes("ct_")) return "Domain/DNS";
  if (raw.includes("ip") || raw.includes("asn") || raw.includes("rdap")) return "IP/ASN";
  if (raw.includes("profile") || raw.includes("social")) return "Social/Profile";
  if (raw.includes("breach") || raw.includes("urlscan") || raw.includes("virustotal")) return "CTI";
  if (raw.includes("crypto") || raw.includes("wallet")) return "Crypto";
  if (raw.includes("evidence") || raw.includes("import")) return "Evidence";
  return "Infrastructure";
}

export default function TransformLibraryPage({ token }: PageProps) {
  const [transforms, setTransforms] = useState<TransformDefinition[]>(FALLBACK_TRANSFORMS);
  const [category, setCategory] = useState("all");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiJson<any>("/api/v1/transforms/registry", undefined, token)
      .then((payload) => setTransforms(payload.data.transforms?.length ? payload.data.transforms : FALLBACK_TRANSFORMS))
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Transform registry unavailable"));
  }, [token]);
  const filtered = useMemo(() => transforms.filter((item) => category === "all" || categoryFor(item) === category), [category, transforms]);
  const disabled = transforms.filter((item) => !item.enabled).length;
  return (
    <section className="transform-page transform-library-page premium-page studio-page scroll-page">
      <header className="page-header premium-page-header">
        <div>
          <span className="micro-label">Maltego-style transform registry</span>
          <h1>Transform Library</h1>
          <p className="muted-copy">Browse passive and BYOK transforms by entity type, output class, legal note, and connector readiness.</p>
        </div>
        <div className="page-actions"><StatusChip label={`${transforms.length} transforms`} tone="info" /><StatusChip label={`${disabled} disabled`} tone={disabled ? "warning" : "ok"} /></div>
      </header>
      {error && <div className="nx-alert"><span>{error}</span></div>}
      <section className="transform-category-bar premium-card">
        {CATEGORIES.map((item) => <button className={category === item ? "active" : ""} type="button" onClick={() => setCategory(item)} key={item}>{item}</button>)}
      </section>
      <TransformLibrary transforms={filtered} title={category === "all" ? "All Transforms" : `${category} Transforms`} />
      <section className="command-card premium-card transform-safety-note">
        <header><ShieldCheck size={15} /><strong>Safety model</strong></header>
        <p>Disabled transforms stay visible with a reason. NexusIntel does not register accounts, trigger OTP, probe password resets, bypass CAPTCHA, or call private APIs.</p>
      </section>
    </section>
  );
}
