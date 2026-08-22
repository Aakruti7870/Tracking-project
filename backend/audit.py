"""Audit logging service. Every sensitive action creates an entry."""
from datetime import datetime, timezone
from typing import Optional

from database import audit_logs


async def write_audit(
    actor_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    await audit_logs.insert_one(
        {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc),
        }
    )
