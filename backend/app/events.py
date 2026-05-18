import json
from datetime import timezone
from typing import Any

import redis

from app.config import get_settings
from app.database import SessionLocal
from app.models import Event


settings = get_settings()
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def channel_for(investigation_id: str) -> str:
    return f"investigation:{investigation_id}:events"


def emit_event(
    investigation_id: str,
    level: str,
    message: str,
    module: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    with SessionLocal() as session:
        event = Event(
            investigation_id=investigation_id,
            level=level,
            message=message,
            module=module,
            payload=payload,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        data = {
            "id": event.id,
            "investigation_id": investigation_id,
            "level": event.level,
            "message": event.message,
            "module": event.module,
            "payload": event.payload,
            "created_at": event.created_at.astimezone(timezone.utc).isoformat(),
        }
    redis_client.publish(channel_for(investigation_id), json.dumps(data))
    return data
