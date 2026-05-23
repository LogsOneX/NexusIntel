from __future__ import annotations

import hashlib
import unittest

from backend.osint.importers.csv_importers import preview_csv, spiderfoot_mapping
from backend.osint.registry import registry
from backend.osint.reporting import build_html_report
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import OSINTArtifact, SourceReliability, utc_now


class OSINTSDKTests(unittest.TestCase):
    def test_registry_has_minimum_adapter_coverage(self) -> None:
        adapters = registry.list_adapters()
        transforms = registry.list_transforms(set())
        self.assertGreaterEqual(len(adapters), 10)
        self.assertTrue(any(item["id"] == "email_to_gravatar" for item in transforms))
        self.assertTrue(any(item["id"] == "domain_to_dns" for item in transforms))

    def test_artifact_contract_contains_evidence_fields(self) -> None:
        artifact = OSINTArtifact(
            type="domain",
            label="example.com",
            value="example.com",
            source="unit",
            source_url="https://example.com",
            fetched_at=utc_now(),
            confidence_score=90,
            confidence_reason="unit direct public evidence",
            evidence_grade="A2",
            raw_evidence_ref="evidence-id",
            relationship="HAS_DOMAIN",
            tags=[],
            data={},
            legal_basis="unit test",
        ).to_dict()
        for key in ["source", "source_url", "fetched_at", "confidence_score", "confidence_reason", "raw_evidence_ref", "legal_basis", "public_source_note"]:
            self.assertIn(key, artifact)

    def test_confidence_grade(self) -> None:
        assessment = assess(direct=True, reliability=SourceReliability.PRIMARY, fp_risk="low", reason="public primary")
        self.assertGreaterEqual(assessment.score, 80)
        self.assertIn(evidence_grade(assessment.score, assessment.source_reliability), {"A1", "A2"})

    def test_spiderfoot_preview_mapping(self) -> None:
        preview = preview_csv("type,data,source\nEMAILADDR,alpha@example.com,unit\n")
        mapping = spiderfoot_mapping(preview["headers"])
        self.assertEqual(preview["row_count_previewed"], 1)
        self.assertEqual(mapping["type"], "type")

    def test_gravatar_hash_recipe(self) -> None:
        self.assertEqual(hashlib.md5("user@example.com".encode()).hexdigest(), "b58996c504c5638798eb6b511e6f49af")

    def test_report_generation_includes_evidence_hashes(self) -> None:
        html = build_html_report(title="Unit Report", graph={"nodes": [{"type": "domain", "label": "example.com", "data": {}}], "edges": []}, evidence=[{"source": "unit", "sha256": "abc", "created_at": "now"}])
        self.assertIn("Unit Report", html)
        self.assertIn("abc", html)


if __name__ == "__main__":
    unittest.main()
