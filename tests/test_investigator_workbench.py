from __future__ import annotations

import unittest

from backend.investigator.connectors import connector_status
from backend.investigator.correlation import AdvancedCorrelationEngine
from backend.investigator.evidence_os import build_evidence_map
from backend.investigator.report import ReportReadinessEngine
from backend.investigator.validator import Validator
from backend.playbooks import PlaybookEngine


class InvestigatorWorkbenchTests(unittest.TestCase):
    def test_evidence_map_flags_unsupported_findings(self) -> None:
        graph = {"nodes": [{"id": "n1", "type": "domain", "label": "nexusintel.dev", "value": "nexusintel.dev", "data": {}}], "edges": []}
        evidence_map = build_evidence_map(graph, [])
        self.assertEqual(evidence_map["coverage"]["unsupported"], 1)
        self.assertIn("unsupported", evidence_map["unsupported_findings"][0]["warning"])

    def test_evidence_map_links_node_to_evidence(self) -> None:
        graph = {"nodes": [{"id": "n1", "type": "domain", "label": "nexusintel.dev", "value": "nexusintel.dev", "data": {"raw_evidence_ref": "ev1"}}], "edges": []}
        evidence = [{"id": "ev1", "source": "official_dns", "uri": "https://dns.public.test/nexusintel.dev", "sha256": "a" * 64, "content_type": "application/json", "created_at": "2026-05-25T00:00:00Z", "meta": {"source_url": "https://dns.public.test/nexusintel.dev", "fetched_at": "2026-05-25T00:00:00Z", "status_code": 200}}]
        evidence_map = build_evidence_map(graph, evidence)
        self.assertEqual(evidence_map["coverage"]["supported_nodes"], 1)
        self.assertEqual(evidence_map["node_evidence"]["n1"][0]["status_code"], 200)

    def test_advanced_correlation_scores_shared_avatar_and_link(self) -> None:
        graph = {"nodes": [{"id": "a", "type": "profile", "label": "A", "value": "A", "data": {"avatar_hash": "hash1", "external_link": "https://example.org"}}, {"id": "b", "type": "profile", "label": "B", "value": "B", "data": {"avatar_hash": "hash1", "external_link": "https://example.org"}}], "edges": []}
        correlations = AdvancedCorrelationEngine().correlate(graph, {"node_evidence": {}})
        self.assertTrue(correlations)
        self.assertEqual(correlations[0]["type"], "same_asset_reuse")
        self.assertTrue(correlations[0]["requires_analyst_confirmation"])

    def test_playbook_planning_blocks_incompatible_input(self) -> None:
        plan = PlaybookEngine().plan("case", "email_investigation", {"nodes": [{"id": "d", "type": "domain"}], "edges": []}, [], set())
        self.assertTrue(plan["blocked_steps"])

    def test_playbook_planning_has_runnable_report_preparation(self) -> None:
        plan = PlaybookEngine().plan("case", "report_preparation", {"nodes": [], "edges": []}, [], set())
        self.assertTrue(plan["runnable_steps"])

    def test_connector_status_reports_missing_key(self) -> None:
        items = connector_status({"api_keys": {}, "connectors": {}})
        github = next(item for item in items if item["id"] == "github")
        self.assertFalse(github["configured"])
        opencorporates = next(item for item in items if item["id"] == "opencorporates")
        self.assertTrue(opencorporates["configured"])

    def test_report_readiness_separates_safe_and_unsafe(self) -> None:
        graph = {"nodes": [{"id": "n1", "type": "domain", "label": "nexusintel.dev", "value": "nexusintel.dev", "source": "official_dns", "confidence": "confirmed", "data": {"source_url": "https://dns.public.test/nexusintel.dev", "raw_evidence_ref": "ev1", "fetched_at": "2026-05-25T00:00:00Z"}}], "edges": []}
        evidence = [{"id": "ev1", "source": "official_dns", "uri": "https://dns.public.test/nexusintel.dev", "sha256": "a" * 64, "created_at": "2026-05-25T00:00:00Z"}]
        validation = Validator().validate_graph(graph, evidence)
        readiness = ReportReadinessEngine().score(graph, validation, {"removed_count": 0, "items": []}, [], evidence)
        self.assertGreaterEqual(readiness["score"], 50)
        self.assertTrue(readiness["report_safe_findings"])


if __name__ == "__main__":
    unittest.main()
