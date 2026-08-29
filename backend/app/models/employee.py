from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import EmployeeStatus, db_enum


class Employee(BaseModel):
    """Shop-floor worker identified by badge QR (TZ 4.2). Distinct from system users."""

    __tablename__ = "employee"

    __table_args__ = (
        Index("ix_employee_badge_id", "badge_id", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_employee_user_id", "user_id", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    full_name: Mapped[str] = mapped_column(String(100), kw_only=True)
    # Kirish hisobiga bog'lam: skaneri yo'q postda (ARRA) odam SHAXSIY hisobi
    # bilan kiradi — `login._open_shift_for` smenani aynan shu bog'lamdan topadi.
    # Qurilma va texnik hisoblar rad etiladi (`_validate_user_link`). ATAYLAB
    # `badge_id` da EMAS: ilgari `user-{id}` beyjik orqali edi va hodimga haqiqiy
    # beyjik chiqarilganda bog'lam uzilib, ish haqi ikkiga bo'linardi
    # (`d1c4e7a90b52`).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    # Badge QR payload, UUID format. Lost badge → row kept, badge blocked, new employee row NOT created:
    # the badge_id is replaced but history (scans FK employee.id) stays intact.
    badge_id: Mapped[str] = mapped_column(String(36), kw_only=True)
    phone: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    position: Mapped[str | None] = mapped_column(String(50), default=None, kw_only=True)
    status: Mapped[EmployeeStatus] = mapped_column(db_enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, kw_only=True)
    # ponytail: JSONB int list instead of a join table — read-heavy, tiny cardinality (9 posts)
    assigned_post_ids: Mapped[list[int]] = mapped_column(JSONB, default_factory=list, kw_only=True)
