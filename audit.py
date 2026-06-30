"""Audit logging for admin actions and sensitive student operations."""

import json
from typing import Any

from flask import request, session


def log_audit(db, action: str, entity_type: str, entity_id: int | None = None, details: dict | None = None) -> None:
    """
    Record an auditable action performed by the current user.

    Args:
        db: Database instance.
        action: Short action label (e.g. grade_update, enrollment_drop).
        entity_type: Table or resource name.
        entity_id: Optional primary key of affected record.
        details: Optional JSON-serializable metadata.
    """
    user_id = session.get("user_id")
    if not user_id:
        return

    ip_address = request.remote_addr if request else None
    payload = json.dumps(details or {})

    db.execute(
        """
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        user_id,
        action,
        entity_type,
        entity_id,
        payload,
        ip_address,
    )


def get_audit_logs(db, limit: int = 100) -> list[dict[str, Any]]:
    """Return recent audit log entries with actor username."""
    return db.execute(
        """
        SELECT a.*, u.username AS actor_name, u.role AS actor_role
        FROM audit_log a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        LIMIT ?
        """,
        limit,
    )
