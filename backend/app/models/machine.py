from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import MachineStatus, db_enum


class Machine(BaseModel):
    """Work center bound to a post — UI da "Ish markazi".

    Not necessarily a machine tool: ARRA/KROMKA/OVAL/PRISADKA/ROVER have real
    equipment, STOLYARKA/BOYOQ/UPAKOVKA/TMO are crew + monoblok only. The class
    and table keep the legacy `machine` name because scan/work_session/part_route/
    user/bridge_agent all carry `machine_id` FKs.

    Terminal/TABLO context comes from user.machine_id.
    """

    __tablename__ = "machine"

    __table_args__ = (
        # Nom operatorga MONOBLOKDA yolg'iz ko'rinadi (post yonida emas) — ikkita
        # "01 ARRA" bo'lsa u qaysi stanokda turganini ajrata olmaydi (`d8f31a05c7e2`)
        Index("ix_machine_name", "name", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    status: Mapped[MachineStatus] = mapped_column(db_enum(MachineStatus), default=MachineStatus.ACTIVE, kw_only=True)
