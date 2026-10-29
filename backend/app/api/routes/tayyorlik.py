"""Ishga tayyorlik (EKO TZ §11, 7-bosqich «Ishga tushirish»): obunachining tizimni real ishlatishga tayyorligi.

Har tekshiruv bazadan hisoblanadi (qo'lda belgilanmaydi): rekvizitlar, soliq rejimi, hisoblar, xodimlar, MXIK,
ochilish qoldiqlari, inventarizatsiya, buxgalteriya nazorati. Tarifda yo'q modul tekshirilmaydi.
Kompozitsiya qatlami: modullarga faqat `.service` orqali murojaat qiladi.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_roles
from app.models import User
from app.models.enums import UserRole
from app.modules.buxgalteriya import service as bux
from app.modules.kassa import service as kassa
from app.modules.ombor import service as ombor
from app.modules.platforma import service as platforma
from app.modules.soliq import service as soliq

router = APIRouter(prefix="/tayyorlik", tags=["tayyorlik"])

TayyorlikUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]


class Tekshiruv(BaseModel):
    modul: str
    nom: str
    #: `ok` — tayyor; `ogoh` — ishlaydi, lekin e'tibor kerak; `xato` — ishga tushirishdan oldin tuzatilsin
    holat: Literal["ok", "ogoh", "xato"]
    izoh: str
    #: Frontend bo'lim yo'li (tuzatish joyi)
    havola: str


async def _rol_soni(db: SessionDep, *rollar: UserRole) -> int:
    return int(
        await db.scalar(
            select(func.count()).where(
                User.role.in_(rollar),
                User.is_active == True,  # noqa: E712
            )
        )
        or 0
    )


@router.get("", response_model=list[Tekshiruv], operation_id="tayyorlik")
async def tayyorlik(db: SessionDep, _: TayyorlikUser) -> list[Tekshiruv]:
    mod = {m for m in platforma.MODULLAR if await platforma.module_enabled(m)}
    out: list[Tekshiruv] = []

    def add(modul: str, nom: str, ok: bool, izoh: str, havola: str, ogoh: bool = False) -> None:
        out.append(
            Tekshiruv(
                modul=modul, nom=nom, holat="ok" if ok else ("ogoh" if ogoh else "xato"), izoh=izoh, havola=havola
            )
        )

    if "kassa" in mod:
        n = await _rol_soni(db, UserRole.KASSIR)
        add(
            "Kassa",
            "Kassir akkaunti",
            n > 0,
            f"{n} ta kassir" if n else "Kassir roli bilan foydalanuvchi yo'q",
            "/admin",
        )
        hs = await kassa.hisoblar(db)
        bank = [h for h, _ in hs if h.tur != "naqd"]
        bosh = [h.nom for h in bank if h.boshlangich]
        add(
            "Kassa",
            "Karta va bank boshlang'ich qoldig'i",
            bool(bosh),
            ("Kiritilgan: " + ", ".join(bosh)) if bosh else "Kiritilmagan — 0 bo'lsa ham tekshirib tasdiqlang",
            "/moliya?b=sozlamalar",
            ogoh=True,
        )
        add(
            "Kassa",
            "Birinchi smena",
            await kassa.boshlangan(db),
            "Kassa ishlayapti — buyurtmadagi qo'lda avans yopiq"
            if await kassa.boshlangan(db)
            else "Hali order yo'q — birinchi smenada naqd sanaladi (boshlang'ich qoldiq)",
            "/kassa",
            ogoh=True,
        )
    if "moliya" in mod or "kassa" in mod:
        n = await _rol_soni(db, UserRole.DIRECTOR, UserRole.MOLIYACHI)
        add(
            "Moliya",
            "Ikki kalit uchun kamida 2 xodim",
            n >= 2,
            f"Direktor + moliyachi: {n}. Storno va davrni qayta ochish boshqa xodim tasdig'ini talab qiladi",
            "/admin",
        )
        och = await kassa.ochilishlar(db)
        m = sum(1 for r in och if r.tur == "mijoz")
        t = sum(1 for r in och if r.tur == "taminotchi")
        add(
            "Moliya",
            "Ochilish qoldiqlari (eski qarzlar)",
            bool(och),
            f"Mijoz qatorlari: {m}, ta'minotchi: {t}" if och else "Kiritilmagan — eski qarz bo'lmasa ham tasdiqlang",
            "/ishga-tushirish",
            ogoh=True,
        )
    if "soliq" in mod:
        k = await soliq.korxona_tayyor(db)
        add(
            "Soliq",
            "Korxona rekvizitlari (nomi, STIR)",
            k,
            "Kiritilgan" if k else "Nomi va STIR kerak",
            "/soliq?b=sozlamalar",
        )
        r = await soliq.rejim_boshi(db)
        add(
            "Soliq",
            "Soliq rejimi (QQS / aylanma)",
            r is not None,
            f"{r:%d.%m.%Y} dan yozilgan" if r else "Rejim yozilmagan — soliq va P&L hisoblanmaydi",
            "/soliq?b=sozlamalar",
        )
        add(
            "Soliq",
            "ESF operatori",
            False,
            "Lokal SINOV operatori — haqiqiy operator (API kaliti, E-IMZO) keyin ulanadi",
            "/soliq?b=sozlamalar",
            ogoh=True,
        )
    if "ombor" in mod:
        jami, mxik = await ombor.mxik_qamrovi(db)
        add(
            "Ombor",
            "MXIK (qoldig'i bor pozitsiyalarda)",
            jami > 0 and mxik == jami,
            f"{mxik} / {jami} pozitsiyada" + ("" if mxik == jami else " — ESF ga MXIK siz pozitsiya kirmaydi"),
            "/soliq?b=sozlamalar",
            ogoh=True,
        )
        inv = await ombor.inventarizatsiya_bormi(db)
        add(
            "Ombor",
            "Boshlang'ich qoldiq sanab tekshirilgan",
            inv,
            "Inventarizatsiya o'tkazilgan" if inv else "Inventarizatsiya hujjati yo'q — real qoldiq bilan solishtiring",
            "/warehouse/inv",
            ogoh=True,
        )
    if "buxgalteriya" in mod:
        await bux.sinxron(db)
        await db.commit()
        farq = [n for n in await bux.nazorat(db) if abs(n.farq) >= 1]
        add(
            "Buxgalteriya",
            "Nazorat: buxgalteriya = modullar",
            not farq,
            "Farq yo'q" if not farq else "Farq: " + ", ".join(n.nom for n in farq),
            "/buxgalteriya?b=nazorat",
        )
    return out
