import HypothesisPanel from "./HypothesisPanel";

export default function HypothesisBoard({ hypotheses }: { hypotheses?: Array<Record<string, any>> | null }) {
  return <HypothesisPanel hypotheses={hypotheses as any} />;
}
