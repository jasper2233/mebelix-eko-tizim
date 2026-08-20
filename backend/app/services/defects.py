"""Brak va qayta ishlab chiqarish — OEE ning Quality qismi.

Oqim: operator o'z terminalida brakni belgilaydi -> yozuv KUTILMOQDA holatida
turadi -> menejer aybdor postni, hodimni va qayta boshlash postini belgilab
tasdiqlaydi -> detal ishlab chiqarishga qaytadi.

Menejer tasdig'i ATAYLAB majburiy: aks holda har xato skan yangi nusxa yaratib,
buyurtma miqdorini shishirardi va Quality ko'rsatkichi ishonchsiz bo'lardi.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Defect, Part, PartInstance, PartRoute, Post, Product, Scan
from app.models.enums import DefectStatus, PostCode

#: Yangi NUSXA faqat shu postlardan qayta boshlanganda yaratiladi: chek aynan
#: shu ikki postda chiqadi (`orders._ROUTE_START_POSTS`), ya'ni detal yangi QR
#: oladi. Boshqa postdan boshlansa detalning O'ZI to'g'rilanadi — u jismonan
#: mavjud va QR'i ishlaydi.
NEW_INSTANCE_POSTS = (PostCode.ARRA, PostCode.ROVER)


async def suggest_blame(db: AsyncSession, instance: PartInstance) -> tuple[int | None, int | None]:
    """Aybdor post va hodimni TAKLIF qiladi — nusxaning oxirgi skanidan.

    Taklif, qaror emas: fayl ham, hisoblagich ham detalning qaysi bosqichda
    buzilganini bilmaydi. Odatiy holat esa shu — nuqson oxirgi ishlangan
    joyda paydo bo'ladi va keyingi post uni topadi.
    """
    row = (
        await db.execute(
            select(Scan.post_id, Scan.employee_id)
            .where(
                Scan.instance_id == instance.id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else (None, None)


async def approve(
    db: AsyncSession,
    *,
    defect: Defect,
    blamed_post_id: int,
    blamed_employee_id: int | None,
    restart_post_id: int,
    user_id: int,
) -> PartInstance | None:
    """Brakni tasdiqlaydi va detalni ishlab chiqarishga qaytaradi.

    Yangi nusxa yaratilgan bo'lsa qaytariladi, aks holda None.
    """
    from app.services.scanning import reopen_instance_from

    instance = await db.get(PartInstance, defect.instance_id)
    if instance is None:
        raise ValueError("Nusxa topilmadi.")
    restart_post = await db.get(Post, restart_post_id)
    if restart_post is None:
        raise ValueError("Post topilmadi.")

    defect.status = DefectStatus.APPROVED
    defect.blamed_post_id = blamed_post_id
    defect.blamed_employee_id = blamed_employee_id
    defect.restart_post_id = restart_post_id
    defect.reviewed_by_id = user_id
    defect.reviewed_at = datetime.now(UTC)

    if PostCode(restart_post.code) in NEW_INSTANCE_POSTS:
        new_instance = await _clone_instance(db, instance)
        defect.new_instance_id = new_instance.id
        return new_instance

    # Bori to'g'rilanadi: o'sha qadamdan keyingi skanlar bekor qilinadi, ya'ni
    # detal shu postning navbatiga qaytadi
    step = (
        await db.execute(
            select(func.min(PartRoute.seq)).where(
                PartRoute.part_id == instance.part_id,
                PartRoute.post_id == restart_post_id,
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if step is None:
        raise ValueError(f"{restart_post.name} bu detal marshrutida yo'q.")
    await reopen_instance_from(db, instance=instance, from_seq=step)
    return None


async def _clone_instance(db: AsyncSession, instance: PartInstance) -> PartInstance:
    """Yaroqsiz nusxa o'rniga yangisini yaratadi.

    Detal soni oshadi va marshrutning HAR qadamidagi `total_required` ham —
    aks holda QOLDIQ yangi nusxani hisobga olmasdi va u navbatga chiqmasdi.

    QR yangi raqam oladi (`{mahsulot}_{detal}_{raqam}` — `ParsedPart.qr_texts`
    bilan bir xil qoida). Mavjud nusxalarning QR'iga TEGILMAYDI: ular allaqachon
    chop etilgan va tsexda yurgan bo'lishi mumkin. Shuning uchun bitta nusxali
    detalda `key` va `key_2` yonma-yon yashaydi — bu ataylab.
    """
    part = await db.get(Part, instance.part_id)
    if part is None:
        raise ValueError("Detal topilmadi.")
    product = await db.get(Product, part.product_id)
    if product is None:
        raise ValueError("Mahsulot topilmadi.")
    part.count += 1
    new_no = part.count
    clone = PartInstance(
        order_id=instance.order_id,
        part_id=instance.part_id,
        instance_no=new_no,
        qr_text=f"{product.code}_{part.code}_{new_no}",
        pattern_no=instance.pattern_no,
        cell_index=instance.cell_index,
        cut_meters=instance.cut_meters,
    )
    db.add(clone)
    await db.execute(
        update(PartRoute)
        .where(PartRoute.part_id == part.id, PartRoute.is_deleted == False)  # noqa: E712
        .values(total_required=PartRoute.total_required + PartRoute.per_instance)
    )
    await db.flush()
    return clone
