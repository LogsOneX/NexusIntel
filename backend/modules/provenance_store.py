from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProvenanceStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or os.getenv("NEXUS_PROVENANCE_DIR", "data/provenance"))
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, *, investigation_id: str, source: str, content: bytes | str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(content, dict):
            raw = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
            content_type = "application/json"
        elif isinstance(content, str):
            raw = content.encode("utf-8")
            content_type = "text/plain"
        else:
            raw = content
            content_type = "application/octet-stream"
        digest = sha256_bytes(raw)
        case_dir = self.root / investigation_id
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / f"{digest}.raw"
        if not path.exists():
            path.write_bytes(raw)
        return {
            "sha256": digest,
            "uri": str(path),
            "size": len(raw),
            "source": source,
            "content_type": content_type,
            "storage": "filesystem_minio_compatible",
        }

    def verify(self, uri: str, expected_sha256: str) -> dict[str, Any]:
        path = Path(uri)
        if not path.exists():
            return {"ok": False, "reason": "missing_object", "sha256": None}
        digest = sha256_bytes(path.read_bytes())
        return {"ok": digest == expected_sha256, "sha256": digest, "expected": expected_sha256}
