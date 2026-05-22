from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9_@.+-]+", re.I)


def _tokens(entity: dict[str, Any]) -> Counter[str]:
    blob = " ".join(str(entity.get(key, "")) for key in ["type", "label", "value", "source", "confidence"])
    data = entity.get("data") if isinstance(entity.get("data"), dict) else {}
    blob += " " + " ".join(str(value) for value in data.values() if not isinstance(value, (dict, list)))
    return Counter(token.lower() for token in TOKEN_RE.findall(blob))


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(left[token] * right.get(token, 0) for token in left)
    l_norm = math.sqrt(sum(value * value for value in left.values()))
    r_norm = math.sqrt(sum(value * value for value in right.values()))
    return 0.0 if not l_norm or not r_norm else dot / (l_norm * r_norm)


class EntityResolutionEngine:
    def score_pair(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        token_score = cosine_similarity(_tokens(left), _tokens(right)) * 100
        exact_bonus = 0
        if str(left.get("value", "")).lower() == str(right.get("value", "")).lower():
            exact_bonus = 20
        if str(left.get("type", "")).lower() == str(right.get("type", "")).lower():
            exact_bonus += 8
        score = min(100, round(token_score + exact_bonus, 2))
        return {
            "score": score,
            "edge_type": "SAME_IDENTITY" if score >= 85 else "HYPOTHETICAL_MATCH",
            "confidence": "high" if score >= 85 else "medium" if score >= 60 else "low",
            "permanent": score >= 85,
        }
