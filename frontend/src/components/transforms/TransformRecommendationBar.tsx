import { Sparkles } from "lucide-react";
import type { TransformDefinition } from "../../lib/types";

export default function TransformRecommendationBar({ transforms, onRun }: { transforms: TransformDefinition[]; onRun: (id: string) => void }) {
  if (!transforms.length) return null;
  return <div className="recommendation-bar"><Sparkles size={14} /><strong>Recommended</strong>{transforms.slice(0, 3).map((item) => <button type="button" key={item.id} disabled={!item.enabled} onClick={() => onRun(item.id)}>{item.label}</button>)}</div>;
}

