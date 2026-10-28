"""Platforma bazasi jadvallari (`multi` rejim, `POSTGRES_DB`). Ish bazasidan ALOHIDA metadata:
obunachi bazalarida bu jadvallar yo'q, ish jadvallari esa platforma bazasida yo'q.
Migratsiyalar — `modules/platforma/migrations` (`alembic -c alembic_platforma.ini`)."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PlatformBase(DeclarativeBase):
    pass


class Tenant(PlatformBase):
    """Obunachi (ijarachi). Ichida korxonalar va filiallar — obunachining o'z bazasida (TZ §2.4)."""

    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Subdomen va baza nomi manbai (`t_<kod>`). O'zgarmaydi.
    kod: Mapped[str] = mapped_column(String(31), unique=True)
    nomi: Mapped[str] = mapped_column(String(200))
    #: `faol` | `toxtatilgan` — to'xtatilganga kirish 403, ma'lumot o'chirilmaydi
    holat: Mapped[str] = mapped_column(String(20), default="faol", server_default="faol")
    #: Yoqilgan modullar (tarif): `mes`, `ombor`, `kassa`, `moliya`, `soliq`, `kroy`
    modules: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
