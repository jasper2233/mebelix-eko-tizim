from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import DefectStatus, db_enum


class PartDefect(BaseModel):
    """Brak qilingan nusxa — operator terminalda skan tasmasidagi BRAK tugmasi bilan belgilaydi.

    OEE Quality shundan: `(skanlar − brak) ÷ skanlar`, brak yo'q bo'lsa 100%
    (`api/routes/reports.py`). Brak SKANNI bekor qilmaydi va marshrutni qayta ochmaydi —
    qayta ishlab chiqarish oqimi (`-B1` nusxa, yangi chek, aybdor post) keyingi bosqich,
    qarori `docs/12-oee.md` §7 da.

    Nomi `defect` EMAS: o'sha nomdagi jadval 2026-08-21 da tushirilgan (`a1c9d4f2b60e`),
    eski nom bilan yangi jadval tarixda chalkashlik berardi — `downtime_reason` bilan
    bir xil sabab.

    Sabab MATN bo'lib saqlanadi, FK emas: ro'yxat `system_setting` dagi `defect_reasons`
    kalitida va admin uni istalgan payt o'zgartiradi — snapshot eski yozuvning ma'nosini
    saqlaydi.
    """

    __tablename__ = "part_defect"

    __table_args__ = (
        #: Hisobot: shu stanokdagi, shu davrdagi braklar
        Index("ix_part_defect_machine_at", "machine_id", "created_at"),
        Index("ix_part_defect_instance", "instance_id"),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), kw_only=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), kw_only=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("part_instance.id"), kw_only=True)
    #: Qaysi skandan keyin belgilangan — bitta skan ikki marta brak qilinmasin
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan.id"), default=None, kw_only=True)
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    #: Belgilagan hodim — brigadaning langar smenasi (skan ham unga yoziladi)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    reason: Mapped[str] = mapped_column(String(60), kw_only=True)
    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    #: Menejer qarori. Operator faqat qayd qiladi — kim aybdor va qayerdan qayta
    #: boshlanishini u bilmaydi (docs/12 §7).
    status: Mapped[DefectStatus] = mapped_column(
        db_enum(DefectStatus), default=DefectStatus.PENDING, index=True, kw_only=True
    )
    #: Aybdor QADAM (`part_route`), post emas: bitta post marshrutda ikki marta uchrashi
    #: mumkin (Kromka → Prisadka → Kromka). `None` — material nuqsoni yoki aniqlanmagan.
    blame_route_id: Mapped[int | None] = mapped_column(ForeignKey("part_route.id"), default=None, kw_only=True)
    #: O'sha qadamda skanerlagan hodim — tasdiqlash paytida SURATGA olinadi: keyingi
    #: bekor qilish yoki qayta skan aybni boshqa odamga ko'chirib yubormasin.
    blame_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    #: Qayta ishlab chiqarish QAYSI qadamdan boshlanadi (tasdiqlashda majburiy).
    #: Hozircha faqat QAROR yozuvi — remake oqimi hali yo'q (docs/12 §7).
    restart_route_id: Mapped[int | None] = mapped_column(ForeignKey("part_route.id"), default=None, kw_only=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
