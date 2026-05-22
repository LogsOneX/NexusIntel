from __future__ import annotations

import json
from typing import Any

import redis


class CollaborationBus:
    def __init__(self, redis_url: str) -> None:
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def publish_patch(self, workspace_id: str, patch: dict[str, Any]) -> int:
        payload = json.dumps({"workspace_id": workspace_id, "patch": patch}, default=str)
        self.client.lpush(f"workspace:{workspace_id}:history", payload)
        self.client.ltrim(f"workspace:{workspace_id}:history", 0, 199)
        return int(self.client.publish(f"workspace:{workspace_id}", payload))

    def presence(self, workspace_id: str, operator: str, state: dict[str, Any]) -> None:
        self.client.hset(f"workspace:{workspace_id}:presence", operator, json.dumps(state, default=str))
        self.client.expire(f"workspace:{workspace_id}:presence", 90)

    def list_presence(self, workspace_id: str) -> dict[str, Any]:
        raw = self.client.hgetall(f"workspace:{workspace_id}:presence")
        return {key: json.loads(value) for key, value in raw.items()}
