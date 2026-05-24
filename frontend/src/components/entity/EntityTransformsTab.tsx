import type { ApiNode, AnalystPipeline, TransformDefinition } from "../../lib/types";
import TransformLibrary from "../transforms/TransformLibrary";
import TransformRecommendationBar from "../transforms/TransformRecommendationBar";

export default function EntityTransformsTab({ node, transforms, analystPipeline, loadingId, onRun }: { node: ApiNode | null; transforms: TransformDefinition[]; analystPipeline?: AnalystPipeline | null; loadingId?: string | null; onRun: (id: string) => void }) {
  const recommended = analystPipeline?.selected_entity?.recommended_transforms || transforms.filter((item) => item.enabled).slice(0, 3);
  return <div className="entity-transform-tab"><TransformRecommendationBar transforms={recommended} onRun={onRun} /><TransformLibrary transforms={transforms} selectedNode={node} onRun={onRun} loadingId={loadingId} title="Valid Transforms" /></div>;
}

