from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import CapacityUnit, MachineStatus, db_enum


class Machine(BaseModel):
    """Concrete equipment bound to a post (TZ 4.3). IP is used for terminal/TABLO context."""

    __tablename__ = "machine"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None, kw_only=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), default=None, kw_only=True)
    capacity: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    capacity_unit: Mapped[CapacityUnit | None] = mapped_column(db_enum(CapacityUnit), default=None, kw_only=True)
    status: Mapped[MachineStatus] = mapped_column(db_enum(MachineStatus), default=MachineStatus.ACTIVE, kw_only=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), default=None, kw_only=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), default=None, kw_only=True)
    installed_date: Mapped[date | None] = mapped_column(Date, default=None, kw_only=True)
