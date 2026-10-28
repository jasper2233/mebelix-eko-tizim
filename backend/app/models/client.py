from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Client(BaseModel):
    """Customer. orders_count is computed in queries, not stored."""

    __tablename__ = "client"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    full_name: Mapped[str] = mapped_column(String(150), kw_only=True)
    phone: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    phone_alt: Mapped[str | None] = mapped_column(String(13), default=None, kw_only=True)
    address: Mapped[str | None] = mapped_column(String(255), default=None, kw_only=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    #: Doimiy mijoz — to'lovsiz ishlab chiqarishga kira oladi, lekin faqat kredit limiti doirasida
    #: (EKO TIZIM TZ Q14). Limitdan oshsa — direktor tasdig'i (Q22)
    doimiy: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", kw_only=True)
    #: So'm. Bo'sh = limit yo'q (doimiy bo'lsa ham to'lovsiz ishga tushmaydi)
    kredit_limit: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
