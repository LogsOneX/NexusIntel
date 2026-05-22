import { Users } from "lucide-react";
import { useCollaborationStore } from "../store/collaborationStore";

export default function PresenceBar() {
  const connected = useCollaborationStore((state) => state.connected);
  const presence = useCollaborationStore((state) => state.presence);
  const operators = Object.values(presence);
  return (
    <div className="presence-bar">
      <Users size={13} />
      <span>{connected ? "Yjs online" : "Yjs offline"}</span>
      {operators.slice(0, 4).map((operator) => <code key={operator.operator}>{operator.operator}</code>)}
    </div>
  );
}
