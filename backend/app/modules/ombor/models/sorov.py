"""Sexdan material so'rovi (EKO TZ §4.4, 2.3b): arrachi/kromkachi terminalda «Material so'rash» bosadi,
omborchi «Material berish» sahifasida ko'radi va beradi. Ikkinchi yo'l — omborchi so'rovsiz oldindan
yetkazadi: so'rov majburiy emas. Post materiali to'liq berilgach ochiq so'rov o'zi yopiladi.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

YANGI = "yangi"
YETKAZILDI = "yetkazildi"
BEKOR = "bekor"


class MaterialSorov(BaseModel):
    __tablename__ = "material_sorov"
    __table_args__ = (
        # Buyurtma + post bo'yicha bittadan ortiq ochiq so'rov bo'lmaydi (qayta bosish — o'sha so'rov)
        Index(
            "ix_material_sorov_ochiq",
            "order_id",
            "post",
            unique=True,
            postgresql_where=text("NOT is_deleted AND holat = 'yangi'"),
        ),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    #: `ARRA` | `KROMKA` | `OVAL` — qaysi post so'radi (qaysi materiallar: list yoki kromka)
    post: Mapped[str] = mapped_column(String(12), kw_only=True)
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
    izoh: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    holat: Mapped[str] = mapped_column(String(12), default=YANGI, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    yopilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    yopgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
