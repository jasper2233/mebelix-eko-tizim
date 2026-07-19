from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class BridgeAgent(BaseModel):
    """Printerli kompyuterdagi chop etish agenti (TZ 2.2.2).

    Admin panel bir martalik ulanish kodi beradi; agent birinchi ishga tushganda
    kodni doimiy tokenga almashtiradi (pairing). Kod 15 daqiqa yashaydi va bir
    marta ishlaydi; token muddatsiz — faqat revoke yoki yangi kod uni o'ldiradi.
    Bazada tokenning sha256 xeshi saqlanadi, o'zi pair javobida bir marta beriladi.
    """

    __tablename__ = "bridge_agent"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    name: Mapped[str] = mapped_column(String(100), kw_only=True)
    # null = hali ulanmagan (kod kutilmoqda)
    token_hash: Mapped[str | None] = mapped_column(String(64), default=None, unique=True, index=True, kw_only=True)
    pair_code: Mapped[str | None] = mapped_column(String(16), default=None, index=True, kw_only=True)
    pair_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
