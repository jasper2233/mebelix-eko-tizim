from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import EmployeeStatus, db_enum


class Employee(BaseModel):
    """Shop-floor worker identified by badge QR (TZ 4.2). Distinct from system users."""

    __tablename__ = "employee"

    __table_args__ = (Index("ix_employee_badge_id", "badge_id", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    full_name: Mapped[str] = mapped_column(String(100), kw_only=True)
    # Badge QR payload, UUID format. Lost badge → row kept, badge blocked, new employee row NOT created:
    # the badge_id is replaced but history (scans FK employee.id) stays intact.
    badge_id: Mapped[str] = mapped_column(String(36), kw_only=True)
    phone: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    passport_id: Mapped[str | None] = mapped_column(String(20), default=None, kw_only=True)
    position: Mapped[str | None] = mapped_column(String(50), default=None, kw_only=True)
    status: Mapped[EmployeeStatus] = mapped_column(db_enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, kw_only=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), default=None, kw_only=True)
    # ponytail: JSONB int list instead of a join table — read-heavy, tiny cardinality (max 6 posts)
    assigned_post_ids: Mapped[list[int]] = mapped_column(JSONB, default_factory=list, kw_only=True)
    hired_date: Mapped[date | None] = mapped_column(Date, default=None, kw_only=True)
