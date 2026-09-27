"""Buyurtma modullari uchun umumiy: KO'RINISH va TAHRIRLASH huquqi.

Ikkala qoida ham bir nechta modulda kerak, va ikkalasi ham bir joyda
turishi SHART: tahrirlash sharti `read_order` javobidagi `can_edit` ga ham,
mutatsiyalarning 403 iga ham shu yerdan boradi — ikki nusxa bo'lsa tugma
ko'rinishi bilan server javobi ajralib ketardi.
"""

from sqlalchemy import Row, func, select

from app.api.deps import SessionDep
from app.core.config import TASHKENT_TZ
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import crud_orders
from app.models import Order, PartRoute, Post, Scan
from app.models.enums import ORDER_STATUS_LABELS, OrderStatus, PostCode, UserRole
from app.models.user import User

_EDITABLE_STATUSES = (OrderStatus.DRAFT, OrderStatus.TECHNICAL_REVIEW)


#: Ishlab chiqarishga uzatilgan buyurtma HAM tahrirlanadi — TO shu paytgacha
#: hech bir postda amal bajarilmagan bo'lsa. Sabab: texnolog faylni yuklab,
#: marshrutni chizib, "uzatish" ni bosgach xatoni ko'rishi odatiy hol; tsex esa
#: hali ishga kirishmagan bo'ladi. Ilgari bu holatda buyurtmani bekor qilib
#: qaytadan yaratishdan boshqa yo'l yo'q edi.
_EDITABLE_IF_UNTOUCHED = (*_EDITABLE_STATUSES, OrderStatus.PRODUCTION)


def _first_n(items: list[str], n: int = 5) -> str:
    """Birinchi n ta nom + «va yana N ta» — xato xabari yuzlab detal bilan to'lib ketmasin."""
    return ", ".join(items[:n]) + (f" va yana {len(items) - n} ta" if len(items) > n else "")


async def _first_work(db: SessionDep, order_id: int) -> "Row | None":
    """Buyurtmada bajarilgan BIRINCHI amal: `(post nomi, soni, vaqti)` yoki `None`.

    "Amal bajarilgan" = BEKOR QILINMAGAN skan. Bekor qilingani hisobga olinmaydi
    va bu ataylab: arrachi ikki detalga chek chiqarib, keyin bekor qilsa —
    jarayonda hech narsa qolmaydi, ya'ni buyurtma yana tahrirlanadigan bo'ladi.
    `PartRoute.total_done` ham bekor qilinganda kamayadi, ya'ni ikki hisob mos
    keladi (prodda 8 buyurtmada tekshirildi: tirik skan == sum(total_done)).
    """
    return (
        await db.execute(
            select(Post.name, func.count(Scan.id).label("soni"), func.min(Scan.created_at).label("vaqti"))
            .join(Scan, Scan.post_id == Post.id)
            .where(
                Scan.order_id == order_id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .group_by(Post.name)
            .order_by(func.min(Scan.created_at))
        )
    ).first()


async def _edit_block_reason(db: SessionDep, order: Order) -> str | None:
    """Tahrirlashga to'sqinlik qiladigan sabab, yoki `None` (mumkin).

    Bitta joyda: fayl qayta yuklash, matritsa va ish markazi tanlovi shundan
    o'tadi, `read_order` esa shu bilan `can_edit` ni hisoblaydi — ya'ni tugma
    ko'rinishi va server javobi hech qachon ajralib ketmaydi.
    """
    if order.status not in _EDITABLE_IF_UNTOUCHED:
        return (
            f"buyurtma holati «{ORDER_STATUS_LABELS[order.status]}». Faqat qoralama, texnologdagi "
            "yoki hali ishlanmagan jarayondagi buyurtmaning fayli va marshruti o'zgartiriladi."
        )
    if order.status != OrderStatus.PRODUCTION:
        return None
    work = await _first_work(db, order.id)
    if work is None:
        return None
    vaqt = work.vaqti.astimezone(TASHKENT_TZ).strftime("%d-%m %H:%M") if work.vaqti else ""
    return (
        f"tsexda ish allaqachon boshlangan — {work.name} postida {work.soni} ta skan ({vaqt}). "
        "Tahrirlash uchun avval o'sha skanlarni bekor qilish kerak."
    )


async def _require_editable(db: SessionDep, order: Order, nima: str) -> None:
    reason = await _edit_block_reason(db, order)
    if reason is not None:
        raise ForbiddenException(f"{nima} — {reason}")


def _hidden_statuses(user: User) -> set[OrderStatus]:
    """Texnolog navbatiga tushmagan holatlar: qoralama (hali tasdiqlanmagan,
    tijoriy bosqich) va bekor qilinganlar. Buyurtma texnologga confirm'dan
    keyin (TECHNICAL_REVIEW) ko'rinadi."""
    if user.role == UserRole.TEXNOLOG and not user.is_superuser:
        return {OrderStatus.DRAFT, OrderStatus.CANCELLED}
    return set()


async def _get_order(db: SessionDep, order_id: int) -> Order:
    return await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)


async def _get_visible_order(db: SessionDep, user: User, order_id: int) -> Order:
    """O'QISH yo'llari uchun: ro'yxatdan yashiringan buyurtma to'g'ridan ID bilan ham ochilmasin.

    Faqat o'qishda ishlatiladi. Mutatsiyalarga tarqatilmaydi: texnolog bekor
    qilingan buyurtmaga fayl yuklashga urinsa, "topilmadi" emas, nima uchun
    mumkin emasligini aytadigan xato chiqishi kerak.
    """
    order = await _get_order(db, order_id)
    if order.status in _hidden_statuses(user):
        raise NotFoundException("Buyurtma topilmadi.")
    return order


#: Nostandart marshrut faqat shu postlardan boshlanadi: detal yo arrada kesiladi,
#: yo roverda. Ikkalasi ham chek chiqaradi — boshqa post boshlansa detalda QR bo'lmaydi.
_ROUTE_START_POSTS = (PostCode.ARRA, PostCode.ROVER)


async def stamp_route_machines(db: SessionDep, order: Order) -> None:
    """Tanlangan ish markazini buyurtma marshrut qatorlariga muhrlash.

    Terminal ro'yxati ham, skan tekshiruvi ham `PartRoute.machine_id` ga
    qaraydi — tanlov faqat `order.machine_assignments` da qolsa, buyurtma
    yangi stanok terminalida ko'rinmaydi va skan E001 beradi. Shuning uchun
    ishlab chiqarishga uzatishda ham, tanlov keyin o'zgartirilganda ham
    muhrlash shu yerdan bo'ladi. Commit chaqiruvchida.
    """
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    used_post_ids = (
        (
            await db.execute(
                select(PartRoute.post_id)
                .where(
                    PartRoute.order_id == order.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    for pid in used_post_ids:
        machine_id = order.machine_assignments.get(str(posts[pid].code))
        if machine_id is None:
            continue
        routes = (
            (
                await db.execute(
                    select(PartRoute).where(
                        PartRoute.order_id == order.id,
                        PartRoute.post_id == pid,
                        PartRoute.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        for route in routes:
            route.machine_id = machine_id
