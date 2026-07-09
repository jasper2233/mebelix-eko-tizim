from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class User(BaseModel):
    __tablename__ = "user"

    # Partial unique indexes: uniqueness only among live rows, so a soft-deleted user's
    # username/phone can be re-registered without an IntegrityError.
    __table_args__ = (
        Index("ix_user_username", "username", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_user_phone", "phone", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    name: Mapped[str | None] = mapped_column(String(30), kw_only=True)
    username: Mapped[str] = mapped_column(String(20), kw_only=True)
    # E.164 Uzbek mobile: '+998' + 9 digits = 13 chars total. Stored canonical, no spaces.
    phone: Mapped[str] = mapped_column(String(13), kw_only=True)
    hashed_password: Mapped[str] = mapped_column(String, kw_only=True)

    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)
    is_superuser: Mapped[bool] = mapped_column(default=False, kw_only=True)
    token_version: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)
