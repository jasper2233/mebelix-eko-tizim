from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import SessionStatus, db_enum


class WorkSession(BaseModel):
    """Operator shift on a terminal, opened by badge scan (TZ 8.2). created_at = start time."""

    __tablename__ = "work_session"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"), index=True, kw_only=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)  # terminal account
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    status: Mapped[SessionStatus] = mapped_column(
        db_enum(SessionStatus), default=SessionStatus.ACTIVE, index=True, kw_only=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)


class Scan(BaseModel):
    """Successful work-unit registration (one QOLDIQ decrement). created_at = scan time.

    Idempotency: client_event_id is a client-generated UUID; unique index rejects network replays
    (TZ 8.4.4). Cancelled scans stay for audit with is_cancelled=True (counter re-incremented).
    """

    __tablename__ = "scan"

    __table_args__ = (
        Index("ix_scan_client_event_id", "client_event_id", unique=True),
        Index("ix_scan_order_post", "order_id", "post_id"),
        Index("ix_scan_instance_post", "instance_id", "post_id", postgresql_where=text("NOT is_cancelled")),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), kw_only=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), kw_only=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("part_instance.id"), kw_only=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("part_route.id"), kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"), index=True, kw_only=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("work_session.id"), index=True, kw_only=True)
    client_event_id: Mapped[str | None] = mapped_column(String(64), default=None, kw_only=True)
    is_cancelled: Mapped[bool] = mapped_column(default=False, kw_only=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
