from app.osint.schema import FindingBatch, entity, relationship
from app.targeting import extract_domain, username_seed


class IntelPlanner:
    name = "intel_planner"

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        root = entity(target_type if target_type != "unknown" else "target", target, target, 100, self.name)
        entities = [root]
        relationships = []

        tasks = [
            ("Validate target type and collection boundaries", "task"),
            ("Collect public identifiers and aliases", "task"),
            ("Pivot only through public endpoints and published metadata", "task"),
            ("Correlate findings through confidence-scored graph edges", "task"),
        ]
        if mode in {"active", "aggressive"}:
            tasks.append(("Run read-only HTTP/DNS checks for authorized infrastructure", "task"))

        for label, type_ in tasks:
            task = entity(type_, f"{target}:{label}", label, 85, self.name, {"mode": mode})
            entities.append(task)
            relationships.append(relationship(root, task, "requires", "Requires", 80))

        if target_type in {"email", "domain", "url"}:
            domain = extract_domain(target)
            if domain:
                domain_node = entity("domain", domain, domain, 95, self.name)
                entities.append(domain_node)
                relationships.append(relationship(root, domain_node, "pivots_to", "Pivots To", 90))

        seed = username_seed(target)
        if seed and target_type in {"username", "email", "url", "unknown"}:
            username = entity("username", seed, seed, 90, self.name)
            entities.append(username)
            relationships.append(relationship(root, username, "alias_candidate", "Alias Candidate", 75))

        return FindingBatch(
            module=self.name,
            summary=f"Created collection plan for {target_type} target in {mode} mode.",
            entities=entities,
            relationships=relationships,
            raw={"mode": mode, "target_type": target_type},
        )
