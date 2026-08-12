from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import CapacityUnit, MachineStatus, db_enum


class Machine(BaseModel):
    """Concrete equipment bound to a post (TZ 4.3).

    Terminal/TABLO context comes from user.machine_id; ip_address is informational only.

    `pair_code`/`token_hash` — monoblokni shu stanokka bog'lash (bridge-agent bilan bir xil
    oqim). Bog'langan qurilmada operator beyjik bilan kiradi: beyjik QR qog'ozda, ya'ni
    o'zi parol bo'la olmaydi — u FAQAT sexdagi bog'langan qurilmada kirish kaliti.
    """

    __tablename__ = "machine"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None, kw_only=True)
    capacity: Mapped[float | None] = mapped_column(default=None, kw_only=True)
    capacity_unit: Mapped[CapacityUnit | None] = mapped_column(db_enum(CapacityUnit), default=None, kw_only=True)
    status: Mapped[MachineStatus] = mapped_column(db_enum(MachineStatus), default=MachineStatus.ACTIVE, kw_only=True)

    # null = qurilma bog'lanmagan (kod kutilmoqda). Token muddatsiz, sha256 xeshi saqlanadi.
    pair_code: Mapped[str | None] = mapped_column(String(8), default=None, index=True, kw_only=True)
    pair_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), default=None, unique=True, index=True, kw_only=True)

    @property
    def paired(self) -> bool:
        """Qurilma bog'langanmi — token o'zi hech qachon tashqariga chiqmaydi."""
        return self.token_hash is not None
