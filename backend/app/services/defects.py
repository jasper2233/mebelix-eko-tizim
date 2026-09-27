"""Tasdiqlangan brak: nusxani tanlangan qadamdan QAYTA ochish (`docs/12-oee.md` §7).

Alohida "qayta ishlab chiqarish ro'yxati" YO'Q va kerak emas: terminaldagi har post o'z
ishini MARSHRUTDAN o'qiydi — qadam yopilmagan bo'lsa detal o'sha postda turadi, oldingi
qadamlari yopiq bo'lsa «tayyor» bo'ladi, keyingilari esa qat'iy tartib (E004) bilan
kutadi. Demak brakni qaytarish uchun yagona ish — `restart_route_id` dan BOSHLAB yozilgan
skanlarni bekor qilish: detal o'sha postning ro'yxatida o'zidan paydo bo'ladi (kesish
xaritasida yashil emas, odatdagi rangda) va keyin postma-post oldinga yuradi.

Bekor qilish YAGONA yo'ldan — `scanning.revoke_scan` (hosila skanlar, hisoblagichlar,
COMPLETED → PRODUCTION hammasi o'sha yerda).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PartDefect, PartInstance, PartRoute, Post, Scan
from app.models.enums import PostCode
from app.models.pachka import PachkaItem
from app.services.scanning import revoke_scan

#: Chek shu postlarda chiqariladi va «chek chiqarildi = kesildi» degan ma'noni tashiydi
#: (`terminal.print_instance_label`). Shulardan qayta boshlansa chek ham qaytariladi,
#: aks holda kesish xaritasidagi katak YASHIL bo'lib turaverardi va yangi chek chiqmasdi.
_CUT_POSTS = (PostCode.ARRA, PostCode.ROVER)


async def reopen_from_step(db: AsyncSession, defect: PartDefect) -> list[dict[str, Any]]:
    """Nusxani `defect.restart_route_id` qadamidan qayta ochadi. Qaytadi: WS hodisalari.

    Idempotent: qayta chaqirilsa bekor qilingan skanlarni ikkinchi marta qaytarmaydi,
    ya'ni menejer qarorni o'zgartirib qayta tasdiqlasa ham hisob buzilmaydi."""
    if defect.restart_route_id is None:
        return []
    restart = await db.get(PartRoute, defect.restart_route_id)
    if restart is None:
        return []

    rows = (
        (
            await db.execute(
                select(Scan)
                .join(PartRoute, PartRoute.id == Scan.route_id)
                .where(
                    Scan.instance_id == defect.instance_id,
                    PartRoute.seq >= restart.seq,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.seq.desc(), Scan.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    events: list[dict[str, Any]] = []
    for scan in rows:
        route = await revoke_scan(db, scan, at=now)
        events.append(
            {
                "type": "scan.cancelled",
                "payload": {
                    "scan_id": scan.id,
                    "order_id": scan.order_id,
                    "part_id": scan.part_id,
                    "post_id": scan.post_id,
                    "qoldiq": (route.total_required - route.total_done) if route else None,
                },
                "post_id": scan.post_id,
                "machine_id": scan.machine_id,
            }
        )

    # Qadoqdan CHIQARILADI — yopiq qadoqda ham. Terminaldagi bekor qilish yopiq qadoqni
    # rad etadi (qadoqlovchi o'zi qayta ochsin), bu esa MENEJER qarori: brak detal qadoqda
    # qolsa omborga yaroqsiz buyum ketardi. Qadoq cheki qayta chiqariladi (docs/12 §7).
    for item in (
        (
            await db.execute(
                select(PachkaItem).where(
                    PachkaItem.instance_id == defect.instance_id,
                    PachkaItem.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    ):
        item.is_deleted = True
        item.deleted_at = now

    # Kesish postidan qayta boshlansa chek ham qaytariladi: katak odatdagi rangga qaytadi
    # va arrachi yangi chekni o'sha katakdan chiqaradi.
    if restart.post_id is not None:
        post = await db.get(Post, restart.post_id)
        if post is not None and post.code in _CUT_POSTS:
            instance = await db.get(PartInstance, defect.instance_id)
            if instance is not None:
                instance.label_printed_at = None
                instance.label_post_id = None
    await db.flush()
    return events
