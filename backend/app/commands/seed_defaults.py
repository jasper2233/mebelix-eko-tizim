"""Idempotent bootstrap: tashkilot, 9 ishlab chiqarish posti va post hisoblari (TZ 4.4).

Run: python -m app.commands.seed_defaults (called from prestart/setup scripts).
"""

import asyncio
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import local_session
from app.core.security import get_password_hash
from app.models import Post
from app.models.enums import POST_ROLES, PostCode, PostUnit, UserRole
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POSTS: list[dict[str, object]] = [
    {
        "code": PostCode.ARRA,
        "name": "Arra",
        "order_index": 1,
        "unit": PostUnit.M2,
    },
    {
        "code": PostCode.KROMKA,
        "name": "Kromka",
        "order_index": 2,
        "unit": PostUnit.METER,
    },
    {
        # Oval (egri) kromka: fayldan avto-aniqlanmaydi — matritsada ustuni yo'q,
        # texnolog nostandart marshrutda qo'lda qo'shadi (per_instance=1, bitta skan = bosqich tugadi)
        "code": PostCode.OVAL,
        "name": "Oval kromka",
        "order_index": 3,
        "unit": PostUnit.METER,
    },
    {
        "code": PostCode.PRISADKA,
        "name": "Prisadka",
        "order_index": 4,
        "unit": PostUnit.PIECE,
    },
    # order_index 5 (eski PAZ) ataylab bo'sh: tartib faqat nisbiy ishlatiladi,
    # qayta raqamlash esa mavjud bazalarda bekorga siljish beradi.
    {
        "code": PostCode.ROVER,
        "name": "Rover",
        "order_index": 6,
        "unit": PostUnit.PIECE,
        "requires_assignment_choice": True,
    },
    {
        "code": PostCode.STOLYARKA,
        "name": "Stolyarka",
        "order_index": 7,
        "unit": PostUnit.PIECE,
    },
    # Bo'yoq oxirgi bosqich: haqiqiy marshrut {7;11;8} = rover -> petlya (stolyarka) -> bo'yoq.
    # Ish markazi tanlash shart emas — bo'yoq kamerasi bitta, terminalda umumiy vazifalar ro'yxati.
    {
        "code": PostCode.BOYOQ,
        "name": "Bo'yoq",
        "order_index": 8,
        "unit": PostUnit.PIECE,
    },
    # Qadoqlash — bo'yoqdan keyingi oxirgi bosqich. Birligi m2: ish haqi
    # qadoqlangan detallar kvadraturasi bo'yicha hisoblanadi.
    {
        "code": PostCode.UPAKOVKA,
        "name": "Qadoqlash",
        "order_index": 9,
        "unit": PostUnit.M2,
    },
    # TMO (Tayyor Mahsulot Ombori) — eng oxirgi qadam, HAR buyurtmada (qadoqlangan
    # ham, qadoqlanmagan ham). Omborchi qabul qilmaguncha detal "tayyor" hisoblanmaydi:
    # shu tufayli oxirgi postda qolib ketgan detal ro'yxatda ko'rinib turadi.
    {
        "code": PostCode.TMO,
        "name": "TMO",
        "order_index": 10,
        "unit": PostUnit.PIECE,
    },
]


async def _seed_post_accounts(db: AsyncSession) -> None:
    """Har post uchun bitta TEXNIK hisob (arrachi, kromkachi, ...).

    Beyjik bilan kirishda smena kimningdir hisobi nomidan ochilishi kerak:
    `login._terminal_user` avval ish markazining TERMINAL hisobini, bo'lmasa
    post rolidagi hisobni oladi. Ikkalasi ham bo'lmasa post BUTUNLAY ishlamaydi
    — bo'yoqchi beyjigini urganda 401 oladi. Aynan shu holat bugun BOYOQ postida
    edi: `boyoqchi` hisobi hech qachon yaratilmagan.

    Bu hisoblar ODAM EMAS va admin ularni yuritmaydi — shuning uchun ular
    Hodimlar sahifasida ko'rinmaydi va shu yerda, o'rnatishda yaratiladi.
    Parol tasodifiy va hech kimga aytilmaydi: post rollariga parol bilan kirish
    kodda yopilgan (`login.py` — `is_system` tekshiruvi), ya'ni parol
    faqat NOT NULL ustunni to'ldirish uchun turadi.

    Telefon `+99800000000N` ajratilgan diapazondan — haqiqiy raqam bilan
    to'qnashmasin (ustunda UNIQUE indeks bor).
    """
    existing = {
        UserRole(u.role): u
        for u in (
            await db.execute(
                # `is_system` SHART: post rolida odamning SHAXSIY hisobi ham bo'ladi
                # (skaneri yo'q post). Usiz seed o'shani texnik hisob deb o'ylab,
                # postni texnik hisobsiz qoldirardi — beyjik bilan kirish sinardi.
                select(User).where(
                    User.role.in_(list(POST_ROLES)),
                    User.is_system == True,  # noqa: E712
                    User.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    }
    for index, (role, post_code) in enumerate(POST_ROLES.items(), start=1):
        account = existing.get(role)
        if account is not None:
            if not account.is_active:
                account.is_active = True
                logger.info("Post hisobi qayta faollashtirildi: %s", role)
            continue
        db.add(
            User(
                name=f"{post_code} posti",
                username=str(role),
                phone=f"+9980000000{index:02d}",
                hashed_password=await get_password_hash(secrets.token_urlsafe(24)),
                role=role,
                is_active=True,
                is_system=True,
            )
        )
        logger.info("Post hisobi yaratildi: %s (%s)", role, post_code)


async def seed_defaults() -> None:
    async with local_session() as db:
        # Tashkilot qatorini `1393a241b793` migratsiyasi qo'yadi (prestart migratsiyani
        # seed'dan OLDIN yuritadi) — bu yerda takroran yaratishga urinish o'lik shox edi.
        existing = {p.code: p for p in (await db.execute(select(Post))).scalars()}
        for data in POSTS:
            code: PostCode = data["code"]  # type: ignore[assignment]
            post = existing.get(code)
            if post is None:
                db.add(Post(**data))  # type: ignore[arg-type]
                logger.info("Post %s created", data["code"])
            elif post.order_index != data["order_index"]:
                # Yangi post qo'shilganda tartib siljiydi (masalan OVAL=3) —
                # mavjud bazalarda ham sinxronlanadi
                post.order_index = data["order_index"]  # type: ignore[assignment]
                logger.info("Post %s order_index -> %s", data["code"], data["order_index"])

        await _seed_post_accounts(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_defaults())
