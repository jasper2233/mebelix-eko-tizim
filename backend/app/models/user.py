from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import UserRole, db_enum


class User(BaseModel):
    __tablename__ = "user"

    # Partial unique indexes: uniqueness only among live rows, so a soft-deleted user's
    # username/phone can be re-registered without an IntegrityError.
    __table_args__ = (
        Index("ix_user_username", "username", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_user_phone", "phone", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    name: Mapped[str | None] = mapped_column(String(30), default=None, kw_only=True)
    username: Mapped[str] = mapped_column(String(20), kw_only=True)
    # E.164 Uzbek mobile: '+998' + 9 digits = 13 chars total. Stored canonical, no spaces.
    phone: Mapped[str] = mapped_column(String(13), kw_only=True)
    hashed_password: Mapped[str] = mapped_column(String, kw_only=True)

    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)
    is_superuser: Mapped[bool] = mapped_column(default=False, kw_only=True)
    token_version: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)

    # TZ 3: admin/director/manager/texnolog are people; terminal/tablo are device accounts
    # bound to a machine (TZ 8.1 variant B). Operators (arrachi..boyoqchi) are users too —
    # POST_ROLES maps each to its post and `scanning.operator_employee` mirrors an Employee row,
    # so scans keep their payroll attribution without a badge.
    role: Mapped[UserRole] = mapped_column(
        db_enum(UserRole), default=UserRole.ADMIN, server_default="admin", kw_only=True
    )
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
