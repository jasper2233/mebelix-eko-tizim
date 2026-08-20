from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import DefectStatus, StopKind, db_enum


class StopReason(BaseModel):
    """Stanok to'xtash sababi — ro'yxatni admin yuritadi.

    `kind` — egasining taksonomiyasi (rejali/rejasiz), OEE hisobiga TA'SIR QILMAYDI.
    Hisobni `excludes_planned` hal qiladi:

      True   vaqt PLANNED TIME dan chiqariladi — ishlab chiqarish uchun
             rejalashtirilmagan (tushlik, tanaffus, smena yo'q). OEE tushmaydi.
      False  vaqt RUN dan chiqadi, PLANNED joyida qoladi — ya'ni Availability
             YO'QOTISHI (sozlash, arra almashtirish, nosozlik, material yo'q).

    Ikki ustunni ajratish ataylab: "sozlash" egasining ro'yxatida rejali, lekin
    standart bo'yicha u qisqartirilishi mumkin bo'lgan yo'qotish (Six Big Losses
    — Setup & Adjustments). PLANNED dan chiqarilsa, eng katta zaxira hisobotda
    umuman ko'rinmay qolardi. Bayroq sozlanadigan — qaror kodda qotib qolmasin.
    """

    __tablename__ = "stop_reason"

    __table_args__ = (Index("ix_stop_reason_name", "name", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    name: Mapped[str] = mapped_column(String(60), kw_only=True)
    kind: Mapped[StopKind] = mapped_column(db_enum(StopKind), kw_only=True)
    excludes_planned: Mapped[bool] = mapped_column(default=False, kw_only=True)
    order_index: Mapped[int] = mapped_column(default=0, kw_only=True)
    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)


class MachineStop(BaseModel):
    """Bitta to'xtash oralig'i. `ended_at IS NULL` = hozir to'xtab turibdi.

    Ish markaziga yoziladi, smenaga emas: stanok operatorsiz ham to'xtab turadi
    ("operator yo'q", "zakaz yo'q") va o'sha vaqt ham Availability yo'qotishi.
    `employee_id` — tugmani bosgan odam, bo'lmasligi mumkin.
    """

    __tablename__ = "machine_stop"

    __table_args__ = (
        # Hisobot davr kesimida o'qiydi; ochiq to'xtashni topish ham shu indeksda
        Index("ix_machine_stop_machine_started", "machine_id", "started_at"),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    reason_id: Mapped[int] = mapped_column(ForeignKey("stop_reason.id"), kw_only=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)


class Defect(BaseModel):
    """Brak — yaroqsiz detal nusxasi. OEE ning Quality qismi shundan chiqadi.

    Ikki xil post bor va ularni ajratish MUHIM:
      `found_post_id`   brakni KIM TOPDI (avtomat — o'sha terminalning posti)
      `blamed_post_id`  brakni KIM CHIQARDI (menejer tasdiqlaganda belgilaydi)

    Quality AYBDOR postga yoziladi: kromkachi arradan kelgan yaroqsiz detalni
    topsa, bu kromkaning ko'rsatkichini tushirmasligi kerak. Aybdorni skan
    tarixidan taklif qilamiz, lekin qarorni ODAM qabul qiladi — fayl ham,
    hisoblagich ham detalning qaysi bosqichda buzilganini bilmaydi.

    Tasdiqlangach detal qayta ishlab chiqarishga ketadi (`restart_post_id`):
    ARRA yoki ROVER dan boshlansa YANGI nusxa yaratiladi (chek o'sha ikki
    postda chiqadi — `_ROUTE_START_POSTS`), boshqa postdan boshlansa bori
    to'g'rilanadi va o'sha qadamdan keyingi skanlari bekor qilinadi.
    """

    __tablename__ = "defect"

    __table_args__ = (
        # Menejer ekrani KUTILAYOTGANLARNI so'raydi; hisobot esa davr kesimida
        Index("ix_defect_status_created", "status", "created_at"),
    )

    instance_id: Mapped[int] = mapped_column(ForeignKey("part_instance.id"), index=True, kw_only=True)
    found_post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    found_by_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    reason: Mapped[str] = mapped_column(String(200), kw_only=True)
    status: Mapped[DefectStatus] = mapped_column(db_enum(DefectStatus), default=DefectStatus.PENDING, kw_only=True)
    blamed_post_id: Mapped[int | None] = mapped_column(ForeignKey("post.id"), default=None, kw_only=True)
    blamed_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    restart_post_id: Mapped[int | None] = mapped_column(ForeignKey("post.id"), default=None, kw_only=True)
    #: ARRA/ROVER dan qayta boshlanganda yaratilgan YANGI nusxa
    new_instance_id: Mapped[int | None] = mapped_column(ForeignKey("part_instance.id"), default=None, kw_only=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
