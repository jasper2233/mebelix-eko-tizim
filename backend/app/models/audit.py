from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class AuditLog(BaseModel):
    """System audit trail (TZ 10.11): who did what, when. created_at = event time."""

    __tablename__ = "audit_log"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, index=True, kw_only=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    module: Mapped[str] = mapped_column(String(50), kw_only=True)  # orders, users, scans, ...
    action: Mapped[str] = mapped_column(String(50), kw_only=True)  # created, updated, cancelled, ...
    entity_type: Mapped[str | None] = mapped_column(String(50), default=None, kw_only=True)
    entity_id: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    message: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    ip: Mapped[str | None] = mapped_column(String(45), default=None, kw_only=True)
