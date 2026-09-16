from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class SystemSetting(BaseModel):
    """Ish vaqtida admin tahrirlaydigan sozlama — kalit/qiymat.

    Nega `.env` emas: belgini o'zgartirish uchun serverga kirib konteynerni qayta
    ishga tushirish kerak bo'lardi. Nega kalit/qiymat: sahifaga keyin stanoklar
    sozlamalari qo'shiladi, har biri uchun alohida migratsiya yozilmasin.
    Qiymat DOIM matn — o'qiydigan joy o'zi turga keltiradi (`settings_service`).
    """

    __tablename__ = "system_setting"

    key: Mapped[str] = mapped_column(String(60), unique=True, index=True, kw_only=True)
    #: Text: ish jadvali (`work_schedule`) JSON bo'lib turadi — bayramlar qo'shilgan
    #: sari 255 belgidan oshadi.
    value: Mapped[str] = mapped_column(Text, kw_only=True)
    #: Kim oxirgi o'zgartirgani — audit jurnalida ham bor, lekin bu yerda
    #: sahifaning o'zida ko'rsatish uchun qo'l ostida turadi.
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True, default=None)
