"""ESF operatori adapteri (EKO TZ §9 «Arxitektura»): yuborish, holat olish, kiruvchilar, javob, bekor.

Har obunachi o'z operatorini sozlamada tanlaydi (`soliq_korxona.esf_operator`); yangi operator — yadroga
tegmasdan shu yerga yangi sinf. Hozir faqat `sinov`: LOKAL sinov operatori — haqiqiy soliq tizimiga hech narsa
ketmaydi. U operator tekshiradigan narsalarni tekshiradi (STIR, MXIK, summalar) va ESF ni qabul/rad qiladi —
shu bilan butun oqim (navbat, qayta urinish, holatlar, QQS kitobi) operator API siz sinaladi.
Haqiqiy operator (Didox, Faktura.uz va h.k.) uchun: API kaliti, hujjat formati va E-IMZO imzosi kerak.
"""

import re
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.soliq.models import SoliqSinovOperator


class OperatorXato(Exception):
    """Operator vaqtincha ishlamayapti — navbat keyinroq qayta uradi."""


@dataclass
class Javob:
    #: `yuborildi` | `qabul_qilindi` | `rad_etildi` | `bekor`
    holat: str
    xabar: str = ""


class OperatorAdapter(Protocol):
    nom: str

    async def yubor(self, db: AsyncSession, hujjat: dict[str, Any]) -> str: ...

    async def holat(self, db: AsyncSession, operator_id: str) -> Javob: ...

    async def kiruvchilar(self, db: AsyncSession) -> list[tuple[str, dict[str, Any]]]: ...

    async def javob(self, db: AsyncSession, operator_id: str, qabul: bool, sabab: str) -> None: ...

    async def bekor(self, db: AsyncSession, operator_id: str) -> None: ...


def tekshir(h: dict[str, Any]) -> list[str]:
    """Operator darajasidagi tekshiruv: rekvizit formati va summalar."""
    xato = []
    if not re.fullmatch(r"\d{9}", str(h.get("sotuvchi", {}).get("stir", ""))):
        xato.append("Sotuvchi STIR 9 raqam emas")
    x = h.get("xaridor", {})
    if not (re.fullmatch(r"\d{9}", str(x.get("stir", ""))) or re.fullmatch(r"\d{14}", str(x.get("jshshir", "")))):
        xato.append("Xaridor STIR (9) yoki JShShIR (14) noto'g'ri")
    jami = Decimal(0)
    for i, q in enumerate(h.get("qatorlar", []), 1):
        if not re.fullmatch(r"\d{17}", str(q.get("mxik", ""))):
            xato.append(f"{i}-qator: MXIK 17 raqam emas")
        if Decimal(str(q["summa"])) + Decimal(str(q["qqs"])) != Decimal(str(q["jami"])):
            xato.append(f"{i}-qator: summa + QQS ≠ jami")
        jami += Decimal(str(q["jami"]))
    if not h.get("qatorlar"):
        xato.append("Qator yo'q")
    if jami != Decimal(str(h.get("jami", 0))):
        xato.append("Qatorlar yig'indisi jamiga teng emas")
    return xato


class SinovOperator:
    """Lokal sinov operatori: yuborilgan ESF birinchi holat so'rovida qabul (yoki tekshiruvdan o'tmasa rad)."""

    nom = "sinov"

    async def _row(self, db: AsyncSession, operator_id: str) -> SoliqSinovOperator:
        r = (
            await db.execute(select(SoliqSinovOperator).where(SoliqSinovOperator.operator_id == operator_id))
        ).scalar_one_or_none()
        if r is None:
            raise OperatorXato(f"Operatorda {operator_id} topilmadi")
        return r

    async def yubor(self, db: AsyncSession, hujjat: dict[str, Any]) -> str:
        oid = f"SINOV-{secrets.token_hex(6).upper()}"
        db.add(SoliqSinovOperator(operator_id=oid, yonalish="chiquvchi", holat="yuborildi", hujjat=hujjat))
        await db.flush()
        return oid

    async def holat(self, db: AsyncSession, operator_id: str) -> Javob:
        r = await self._row(db, operator_id)
        if r.yonalish == "chiquvchi" and r.holat == "yuborildi":
            xato = tekshir(r.hujjat)
            r.holat, r.xabar = ("rad_etildi", " · ".join(xato)[:300]) if xato else ("qabul_qilindi", "")
            await db.flush()
        return Javob(r.holat, r.xabar)

    async def kiruvchilar(self, db: AsyncSession) -> list[tuple[str, dict[str, Any]]]:
        rows = (
            await db.execute(
                select(SoliqSinovOperator).where(
                    SoliqSinovOperator.yonalish == "kiruvchi", SoliqSinovOperator.holat == "kutilmoqda"
                )
            )
        ).scalars()
        return [(r.operator_id, r.hujjat) for r in rows]

    async def javob(self, db: AsyncSession, operator_id: str, qabul: bool, sabab: str) -> None:
        r = await self._row(db, operator_id)
        r.holat, r.xabar = ("qabul_qilindi", "") if qabul else ("rad_etildi", sabab[:300])
        await db.flush()

    async def bekor(self, db: AsyncSession, operator_id: str) -> None:
        r = await self._row(db, operator_id)
        r.holat = "bekor"
        await db.flush()

    async def kiruvchi_qosh(self, db: AsyncSession, hujjat: dict[str, Any]) -> str:
        """Sinov uchun: «yetkazib beruvchi bizga ESF yubordi»."""
        oid = f"SINOV-K-{secrets.token_hex(5).upper()}"
        db.add(SoliqSinovOperator(operator_id=oid, yonalish="kiruvchi", holat="kutilmoqda", hujjat=hujjat))
        await db.flush()
        return oid


OPERATORLAR: dict[str, OperatorAdapter] = {"sinov": SinovOperator()}


def adapter(nom: str) -> OperatorAdapter:
    a = OPERATORLAR.get(nom)
    if a is None:
        raise OperatorXato(f"«{nom}» operatori ulanmagan")
    return a
