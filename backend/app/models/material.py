from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import MaterialType, db_enum


class Material(BaseModel):
    """Raw material catalog (TZ 4.5). Auto-populated from uploaded .project files."""

    __tablename__ = "material"

    __table_args__ = (
        Index("ix_material_name_type", "name", "type", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    name: Mapped[str] = mapped_column(String(150), kw_only=True)
    code: Mapped[str | None] = mapped_column(String(50), default=None, kw_only=True)
    type: Mapped[MaterialType] = mapped_column(db_enum(MaterialType), kw_only=True)
    thickness: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    width: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    length: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    default_supplier: Mapped[str | None] = mapped_column(String(100), default=None, kw_only=True)
    price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    color: Mapped[str | None] = mapped_column(String(30), default=None, kw_only=True)
    glossiness: Mapped[str | None] = mapped_column(String(30), default=None, kw_only=True)
