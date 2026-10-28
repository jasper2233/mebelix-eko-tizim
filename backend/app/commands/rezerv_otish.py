"""Rezerv qoidasiga o'tish kuni — bir martalik (EKO TZ §4.3, foydalanuvchi qarori 2026-10-28).

Texnologdagi (TECHNICAL_REVIEW) buyurtmalar yangi qoidadan oldin qabul qilingan: ularga rezerv
quriladi va tizim nomidan direktor ruxsati qo'yiladi — ishlab chiqarishga uzatish to'xtab qolmasin.

PRODUCTION dagi buyurtmalarga TEGILMAYDI: ular darvozadan allaqachon o'tgan va materiali sexga
berilgan bo'lishi mumkin — rezerv qilinsa ombordagi bo'sh qoldiq ikki marta band bo'lardi.

    python -m app.commands.rezerv_otish            # nima qilinishini ko'rsatadi
    python -m app.commands.rezerv_otish --apply    # bajaradi (takror ishga tushirish xavfsiz)
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.db import local_session
from app.crud import log_action
from app.models import Order
from app.models.enums import OrderStatus
from app.modules.ombor import service as ombor


async def run(apply: bool) -> None:
    async with local_session() as db:
        orders = list(
            (
                await db.execute(
                    select(Order)
                    .where(Order.status == OrderStatus.TECHNICAL_REVIEW, Order.is_deleted == False)  # noqa: E712
                    .order_by(Order.id)
                )
            ).scalars()
        )
        done = 0
        for o in orders:
            if not o.material_usage:
                print(f"  {o.number}: fayl yuklanmagan — o'tkazib yuborildi (yuklanganda rezerv o'zi quriladi)")
            elif await ombor.adopt_open_order(db, o):
                done += 1
                print(f"  {o.number}: rezerv + ruxsat")
                log_action(
                    db,
                    module="rezerv",
                    action="otish",
                    entity_type="order",
                    entity_id=o.id,
                    message="Rezerv qoidasiga o'tish: rezerv qurildi va tizim nomidan ruxsat berildi",
                )
        print(f"Texnologda: {len(orders)}, yangi rezerv + ruxsat: {done}")
        if apply:
            await db.commit()
            print("YOZILDI.")
        else:
            await db.rollback()
            print("Sinov rejimi (hech narsa yozilmadi) — yozish uchun --apply")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--apply", action="store_true")
    asyncio.run(run(p.parse_args().apply))


if __name__ == "__main__":
    main()
