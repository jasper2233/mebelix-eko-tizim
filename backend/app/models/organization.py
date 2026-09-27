from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Organization(BaseModel):
    """Tenant. Bitta qator ("Mebelix"), `1393a241b793` migratsiyasi yaratadi.

    Oltita jadvaldagi `organization_id` FK hech qayerda filtrlanmaydi va hech
    qachon berilmaydi (`default=1`): ikkinchi tashkilot tayyor mexanizmni yoqish
    emas, noldan yozish bo'ladi.
    """

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(100), kw_only=True)
