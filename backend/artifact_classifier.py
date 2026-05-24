from __future__ import annotations

# Compatibility facade: the production artifact taxonomy now lives under backend.osint.
from backend.osint.artifact_router import (
    append_artifact_to_meta,
    artifact_record,
    artifact_record_key,
    bucket_for_classification,
    classify_artifact,
    dedupe_records,
    route_artifact,
    should_create_entity,
)
from backend.osint.taxonomy import ArtifactClass, ArtifactRoute, GraphVisibility

__all__ = [
    "ArtifactClass",
    "ArtifactRoute",
    "GraphVisibility",
    "append_artifact_to_meta",
    "artifact_record",
    "artifact_record_key",
    "bucket_for_classification",
    "classify_artifact",
    "dedupe_records",
    "route_artifact",
    "should_create_entity",
]
