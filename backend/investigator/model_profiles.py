from __future__ import annotations

from backend.investigator.types import ModelProfile


PROFILES = {
    "tiny": ModelProfile("tiny", "2-4GB", 4096, "classification, short summaries, next actions", 500),
    "small": ModelProfile("small", "4-8GB", 8192, "stronger evidence reasoning and concise briefings", 700),
    "balanced": ModelProfile("balanced", "8-16GB", 12000, "full analyst summaries with strict evidence cards", 900),
}


def get_profile(name: str | None) -> ModelProfile:
    return PROFILES.get(str(name or "tiny").lower(), PROFILES["tiny"])


def list_profiles() -> list[dict]:
    return [profile.to_dict() for profile in PROFILES.values()]
