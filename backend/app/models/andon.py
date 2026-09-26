from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class AndonEvent(BaseModel):
    """Stanok signal ustunidan (andon) kelgan bitta hodisa — Pico o'qigan chiroq holati.

    Ikki tur (`kind`): `state` — holat o'zgarishi (PROCESSING, AWAIT_PART, IDLE,
    STOPPED, FAULT, OFF), `cycle` — detal sikli (kutish + ishlov vaqti). Xom
    hodisa o'zgarmasdan `payload` da turadi: to'xtashlar va OEE keyingi bosqichda
    aynan shu jadvaldan quriladi, ya'ni ma'lumot hozirdan yig'ilib boradi.

    Kalit Pico'dan: `session` (har yuklanishda yangi tasodifiy id) + `seq`
    (sessiya ichida uzluksiz). Agent uzilishdan keyin navbatni qayta yuboradi —
    takror yozuv shu kalit bo'yicha jimgina tashlanadi.

    Ish markazi Pico'dagi `MACHINE_ID` matnidan EMAS, agentning bog'lanishidan
    (`bridge_agent.machine_id`) olinadi: Pico konfiguratsiyasi xato bo'lsa ham
    ma'lumot to'g'ri stanokka tushadi.
    """

    __tablename__ = "andon_event"

    __table_args__ = (
        Index("ix_andon_event_key", "machine_id", "session", "seq", unique=True),
        Index("ix_andon_event_machine_at", "machine_id", "happened_at"),
        # Hisobot va tablo so'rovlari (tur + stanok + vaqt, `NOT is_deleted`). 2026-09-24 da
        # Pico dublikatlari (`scripts/kromka_dedup.sql`) YUMSHOQ o'chirilgan — ~258 ming qator
        # jadvalda qolgan va umumiy indeks bo'yicha o'qilib keyin tashlanardi. Qisman indeks ularga
        # umuman tegmaydi: Kromka-1 oynasi 2,0 -> 1,1 s, hisobotlar 16-33% tez (prod nusxasida).
        Index("ix_andon_event_live", "kind", "machine_id", "happened_at", postgresql_where=text("NOT is_deleted")),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("bridge_agent.id"), default=None, kw_only=True)
    session: Mapped[str] = mapped_column(String(16), kw_only=True)
    seq: Mapped[int] = mapped_column(kw_only=True)
    kind: Mapped[str] = mapped_column(String(10), kw_only=True)
    state: Mapped[str | None] = mapped_column(String(16), default=None, kw_only=True)
    prev_state: Mapped[str | None] = mapped_column(String(16), default=None, kw_only=True)
    prev_duration_s: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    #: Hodisa stanokda ro'y bergan vaqt. Pico USB rejimida soatsiz (`ts: 0`) —
    #: vaqtni agent qo'yadi, u ham bo'lmasa server qabul qilgan payt.
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
