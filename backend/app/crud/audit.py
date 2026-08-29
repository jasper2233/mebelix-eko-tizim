from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def log_action(
    db: AsyncSession,
    *,
    module: str,
    action: str,
    user_id: int | None = None,
    employee_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    message: str | None = None,
    meta: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Stage an audit row in the caller's transaction — committed together with the change."""
    entry = AuditLog(
        module=module,
        action=action,
        user_id=user_id,
        employee_id=employee_id,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        meta=meta or {},
        ip=ip,
    )
    db.add(entry)
