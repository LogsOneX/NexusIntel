from __future__ import annotations

import unittest

from backend.investigator.brain import InvestigatorBrain
from backend.investigator.hypothesis import HypothesisEngine
from backend.investigator.local_llm import model_status
from backend.investigator.noise_killer import NoiseKiller
from backend.investigator.report import ReportReadinessEngine
from backend.investigator.types import InvestigatorQuestion
from backend.investigator.validator import Validator


class InvestigatorBrainTests(unittest.IsolatedAsyncioTestCase):
    def test_generic_login_page_is_noise(self) -> None:
        decision = NoiseKiller().decide({"id": "n1", "type": "profile", "label": "Login", "value": "https://example.test/login", "data": {"status_code": 200, "title": "Sign in to continue"}})
        self.assertTrue(decision.is_noise)
        self.assertIn("auth wall", " ".join(decision.reasons).lower())

    def test_candidate_profile_without_proof_is_not_verified(self) -> None:
        graph = {"nodes": [{"id": "c1", "type": "profile_candidate", "label": "alpha candidate", "value": "https://example.test/{username}", "confidence": "candidate", "data": {}}], "edges": []}
        validation = Validator().validate_graph(graph, [], "c1")
        self.assertEqual(validation["selected"]["validation_label"], "NOISE")

    def test_manual_entity_without_evidence_is_unverified(self) -> None:
        graph = {"nodes": [{"id": "m1", "type": "username", "label": "alpha", "value": "alpha", "source": "manual", "confidence": "medium", "data": {}}], "edges": []}
        validation = Validator().validate_graph(graph, [], "m1")
        self.assertNotIn(validation["selected"]["validation_label"], {"VERIFIED", "STRONG"})
        self.assertIn("missing source_url", validation["selected"]["explanation"])

    def test_direct_public_evidence_becomes_strong(self) -> None:
        graph = {"nodes": [{"id": "d1", "type": "domain", "label": "nexusintel.dev", "value": "nexusintel.dev", "source": "official_dns", "confidence": "confirmed", "data": {"source_url": "https://dns.public.test/nexusintel.dev", "raw_evidence_ref": "ev1", "fetched_at": "2026-05-25T00:00:00Z"}}], "edges": []}
        evidence = [{"id": "ev1", "source": "official_dns", "uri": "https://dns.public.test/nexusintel.dev", "sha256": "a" * 64, "created_at": "2026-05-25T00:00:00Z"}]
        validation = Validator().validate_graph(graph, evidence, "d1")
        self.assertIn(validation["selected"]["validation_label"], {"STRONG", "VERIFIED"})

    def test_shared_avatar_and_link_creates_hypothesis_not_identity_fact(self) -> None:
        graph = {"nodes": [{"id": "a", "type": "profile", "label": "A", "value": "A", "data": {"avatar_hash": "hash1", "external_link": "https://example.com"}}, {"id": "b", "type": "profile", "label": "B", "value": "B", "data": {"avatar_hash": "hash1", "external_link": "https://example.com"}}], "edges": []}
        hypotheses = HypothesisEngine().generate(graph, {"results": []})
        self.assertTrue(hypotheses)
        self.assertLess(hypotheses[0].confidence_score, 90)
        self.assertIn("hypothesis", hypotheses[0].analyst_warning.lower())

    def test_report_readiness_blocks_missing_evidence(self) -> None:
        graph = {"nodes": [{"id": "m1", "type": "username", "label": "alpha", "value": "alpha", "data": {}}], "edges": []}
        validation = Validator().validate_graph(graph, [], "m1")
        readiness = ReportReadinessEngine().score(graph, validation, {"removed_count": 0, "items": []}, [], [])
        self.assertIn("No evidence vault records", " ".join(readiness["blockers"]))

    async def test_rules_mode_brain_cannot_upgrade_without_evidence(self) -> None:
        state = {"graph": {"nodes": [{"id": "m1", "type": "username", "label": "alpha", "value": "alpha", "data": {}}], "edges": []}, "evidence": [], "settings": {"ai": {"mode": "rules"}}, "transforms": [], "api_keys": []}
        answer = await InvestigatorBrain().answer(InvestigatorQuestion("Validate strongest findings", "case", "m1"), state)
        selected = answer["validation_summary"]["selected"]
        self.assertNotIn(selected["validation_label"], {"VERIFIED", "STRONG"})
        self.assertIn("Insufficient evidence", answer["reply"])

    def test_model_status_defaults_to_rules_fallback(self) -> None:
        status = model_status({"ai": {"mode": "rules"}})
        self.assertTrue(status["fallback"])
        self.assertEqual(status["model"], "rules-only")


if __name__ == "__main__":
    unittest.main()
