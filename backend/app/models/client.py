from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Client(BaseModel):
    """Customer (TZ 4.6). orders_count is computed in queries, not stored."""

    __tablename__ = "client"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    full_name: Mapped[str] = mapped_column(String(150), kw_only=True)
    phone: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    phone_alt: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    address: Mapped[str | None] = mapped_column(String(255), default=None, kw_only=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
