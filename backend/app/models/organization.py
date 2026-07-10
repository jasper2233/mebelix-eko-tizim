from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Organization(BaseModel):
    """Tenant. Single row (Mebelix) for now; schema is multi-tenant ready per TZ 4.1."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), default=None, kw_only=True)
    address: Mapped[str | None] = mapped_column(String(255), default=None, kw_only=True)
    phones: Mapped[list[str]] = mapped_column(JSONB, default_factory=list, kw_only=True)
    currency: Mapped[str] = mapped_column(String(10), default="UZS", kw_only=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tashkent", kw_only=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
