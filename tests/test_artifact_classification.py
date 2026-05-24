from __future__ import annotations

import unittest

from backend.artifact_classifier import append_artifact_to_meta, artifact_record, classify_artifact, route_artifact, should_create_entity


class ArtifactClassificationTests(unittest.TestCase):
    def test_classifier_buckets_guardrail_candidate_and_noise(self) -> None:
        self.assertEqual(classify_artifact({"type": "guardrail", "label": "No recovery probing"}), "COMPLIANCE")
        self.assertEqual(classify_artifact({"type": "profile_candidate", "data": {"verification": "candidate_url_only"}}), "CANDIDATE")
        self.assertEqual(classify_artifact({"type": "generic_page", "label": "soft 404 profile shell"}), "NOISE")
        self.assertEqual(classify_artifact({"type": "raw_html", "label": "profile html"}), "EVIDENCE")
        self.assertEqual(classify_artifact({"type": "validation", "label": "email syntax"}), "SIGNAL")
        self.assertEqual(classify_artifact({"type": "domain", "label": "example.com", "value": "example.com"}), "ENTITY")

    def test_guardrail_artifact_does_not_create_entity(self) -> None:
        artifact = {"type": "guardrail", "label": "No recovery probing", "value": "policy:no-recovery", "relationship": "has_guardrail"}
        self.assertFalse(should_create_entity(artifact))
        record = artifact_record(artifact, "COMPLIANCE", default_source="unit", parent_id="root")
        meta = append_artifact_to_meta({}, "compliance", record)
        self.assertEqual(len(meta["compliance"]), 1)
        self.assertEqual(meta["artifact_counts"]["compliance_count"], 1)

    def test_profile_candidate_artifact_does_not_create_entity_by_default(self) -> None:
        artifact = {"type": "profile_candidate", "label": "alpha on Example", "value": "https://example.test/alpha", "relationship": "candidate_profile", "data": {"verification": "candidate_url_only"}}
        self.assertFalse(should_create_entity(artifact))
        record = artifact_record(artifact, "CANDIDATE", default_source="unit", parent_id="root")
        meta = append_artifact_to_meta({}, "leads", record)
        self.assertEqual(len(meta["leads"]), 1)
        self.assertEqual(meta["artifact_counts"]["candidate_count"], 1)

    def test_entity_with_guardrail_metadata_still_creates_entity(self) -> None:
        artifact = {"type": "google_profile", "label": "Public Maps profile", "value": "https://google.com/maps/contrib/123", "data": {"guardrail": "explicit_public_maps_profile_url_only"}}
        self.assertTrue(should_create_entity(artifact))

    def test_real_domain_email_and_profile_create_entities(self) -> None:
        for artifact in [
            {"type": "domain", "label": "example.com", "value": "example.com", "relationship": "HAS_DOMAIN"},
            {"type": "email", "label": "a@example.com", "value": "a@example.com", "relationship": "HAS_EMAIL"},
            {"type": "profile", "label": "GitHub alpha", "value": "https://github.com/alpha", "relationship": "OBSERVED_ON"},
        ]:
            with self.subTest(artifact=artifact):
                self.assertTrue(should_create_entity(artifact))

    def test_signal_and_evidence_do_not_create_graph_entities(self) -> None:
        validation = {"type": "validation", "label": "Email format", "value": "email:a@example.com:format", "relationship": "HAS_VALIDATION"}
        raw_html = {"type": "raw_html", "label": "Profile HTML", "value": "sha256:abc"}
        self.assertFalse(should_create_entity(validation))
        self.assertTrue(route_artifact(validation).attach_to_parent)
        self.assertFalse(should_create_entity(raw_html))
        self.assertEqual(route_artifact(raw_html).meta_bucket, "evidence")


if __name__ == "__main__":
    unittest.main()
