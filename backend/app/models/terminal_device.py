from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class TerminalDevice(BaseModel):
    """Ish markazida chek CHIQARA OLADIGAN qurilma (postning monobloki).

    Terminal hisobi qurilmaga emas, odamga bog'langan: arrachi o'z hisobiga
    telefondan kirsa ham ARRA ish markazi aniqlanadi va chek postdagi printerdan
    chiqadi. Postda turmagan odam bosgan chek kimningdir detaliga yopishib
    qoladi — 2026-09-24 da ikki bir xil chek shu yo'l bilan chiqqan.

    Ulanish `BridgeAgent` naqshida: admin bir martalik kod beradi, monoblokda
    terminal ekranida kiritiladi va brauzerga httpOnly cookie (token) yoziladi.
    Bazada tokenning sha256 xeshi. Ish markazida kamida bitta ULANGAN qurilma
    bo'lsa, chek faqat shunday cookie'li brauzerdan chiqadi; ulanmagan ish
    markazida cheklov yo'q (`services/terminal_device.py`).
    """

    __tablename__ = "terminal_device"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    # null = hali ulanmagan (kod kutilmoqda) yoki kod qayta berilgan
    token_hash: Mapped[str | None] = mapped_column(String(64), default=None, unique=True, index=True, kw_only=True)
    pair_code: Mapped[str | None] = mapped_column(String(16), default=None, index=True, kw_only=True)
    pair_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    # Kod QAYSI brauzerda kiritilgani — admin panelda "Telefon"/"Kompyuter" bo'lib
    # ko'rinadi: kodni ko'rgan ishchi uni telefonida kiritib qo'ysa darhol seziladi
    paired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    paired_user_agent: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
