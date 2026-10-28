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
from app.modules.ombor.models import Rezerv
from app.modules.ombor.services import rezerv


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
        tirik = set(
            (
                await db.execute(
                    select(Rezerv.order_id).where(Rezerv.holat.in_(rezerv.TIRIK), Rezerv.is_deleted == False)  # noqa: E712
                )
            ).scalars()
        )
        todo = [o for o in orders if o.id not in tirik]
        for o in todo:
            if not o.material_usage:
                print(f"  {o.number}: fayl yuklanmagan — o'tkazib yuborildi (yuklanganda rezerv o'zi quriladi)")
                continue
            print(f"  {o.number}: rezerv + ruxsat")
            if not apply:
                continue
            await rezerv.reserve_for_order(db, o)
            await rezerv.approve(db, o.id, None)
            log_action(
                db,
                module="rezerv",
                action="otish",
                entity_type="order",
                entity_id=o.id,
                message="Rezerv qoidasiga o'tish: rezerv qurildi va tizim nomidan ruxsat berildi",
            )
        print(f"Texnologda: {len(orders)}, rezervi bor: {len(orders) - len(todo)}, ishlov: {len(todo)}")
        if apply:
            await db.commit()
            print("YOZILDI.")
        else:
            print("Sinov rejimi — yozish uchun --apply")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--apply", action="store_true")
    asyncio.run(run(p.parse_args().apply))


if __name__ == "__main__":
    main()
