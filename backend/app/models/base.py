from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BaseModel(Base):
    """Hamma jadvalning umumiy ustunlari: id + vaqt tamg'alari + yumshoq o'chirish."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), server_default=text("current_timestamp(0)")
    )
    # server_default YO'Q: INSERT'da ustun tushirib qoldiriladi va NULL bo'lib qoladi —
    # «hech tahrirlanmagan» belgisi shunda ma'noga ega (ilgari DB defaulti har yangi
    # qatorga vaqt qo'yib, updated_at hech qachon NULL bo'lmasdi).
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    # Indekssiz: boolean ustun o'zi tanlovsiz, har so'rov uni aniqroq ustun bilan
    # birga filtrlaydi — issiq yo'llardagi PARTIAL indekslar (`WHERE NOT is_deleted`)
    # shu ishni qiladi. 18 ta `ix_*_is_deleted` migratsiyada o'chirilgan.
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
