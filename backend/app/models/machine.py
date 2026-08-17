from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import CapacityUnit, MachineStatus, db_enum


class Machine(BaseModel):
    """Work center bound to a post (TZ 4.3) — UI da "Ish markazi".

    Not necessarily a machine tool: ARRA/KROMKA/OVAL/PRISADKA/ROVER have real
    equipment, STOLYARKA/BOYOQ/UPAKOVKA/TMO are crew + monoblok only. The class
    and table keep the legacy `machine` name because scan/work_session/part_route/
    user/bridge_agent all carry `machine_id` FKs.

    Terminal/TABLO context comes from user.machine_id.
    """

    __tablename__ = "machine"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    capacity: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    capacity_unit: Mapped[CapacityUnit | None] = mapped_column(db_enum(CapacityUnit), default=None, kw_only=True)
    status: Mapped[MachineStatus] = mapped_column(db_enum(MachineStatus), default=MachineStatus.ACTIVE, kw_only=True)
