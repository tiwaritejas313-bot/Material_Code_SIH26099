"""
Phase 7: audit trail. Deliberately scoped to actual governance-relevant
actions -- reviewer decisions and the group changes they cause, plus
user-initiated uploads via the API -- not the one-off bulk seed-data loader
scripts (load_samanvay.py etc.), since loading the initial dataset isn't a
"change" to anything, it's the starting state. Every real state-changing
action a user takes through the API IS logged.
"""
from datetime import datetime, timezone
from typing import Any, Optional


async def log_action(
    db,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    previous_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    reason: Optional[str] = None,
) -> None:
    await db.audit_log.insert_one({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "actor": actor,
        "previous_value": previous_value,
        "new_value": new_value,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
