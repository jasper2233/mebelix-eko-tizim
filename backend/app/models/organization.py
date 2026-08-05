from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Organization(BaseModel):
    """Tenant. Single row (Mebelix) for now; schema is multi-tenant ready per TZ 4.1."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(100), kw_only=True)
