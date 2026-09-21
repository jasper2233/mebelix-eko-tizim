"""«Detal qayerda» — ofis uchun bitta nusxaning marshruti va joriy o'rni.

Buyurtmalar qidiruvi BUYURTMA qaytaradi, detal joylashuvini emas. Yangi
ma'lumot yig'ilmaydi: `Scan` + `PartRoute` + `PartDefect` bitta javobga
yig'iladi. Batafsil — docs/03.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep, StaffReadUser
from app.models import Order, Part, PartDefect, PartInstance, PartRoute, Post, Scan
from app.models.enums import DefectStatus, OrderStatus
from app.schemas.orders import InstanceStep, InstanceTrace

from ._common import _hidden_statuses

router = APIRouter()

#: Detal shu ikki holatda harakatlanadi. Qolganlarida harakat tugagan va
#: ro'yxatni shovqin bilan to'ldirardi — `status` bilan aniq so'ralsa keladi.
_DEFAULT_STATUSES = (OrderStatus.PRODUCTION, OrderStatus.COMPLETED)

#: Detal ID noyob (docs/11) — chegara faqat qisman kiritish uchun.
_LIMIT = 50

#: Sanoqqa kiradigan skan. Ikki so'rovda bir xil — ajralib ketmasin.
_TIRIK_SKAN = (
    Scan.is_cancelled == False,  # noqa: E712
    Scan.is_deleted == False,  # noqa: E712
)


@router.get("/instances", response_model=list[InstanceTrace], operation_id="trace_instances")
async def trace_instances(
    db: SessionDep,
    current_user: StaffReadUser,
    q: Annotated[str, Query(min_length=3, max_length=120)],
    status: OrderStatus | None = None,
) -> list[InstanceTrace]:
    """`q` — to'liq yoki qisman Detal ID (`B-2026-001_121301_01_002`)."""
    # `min_length` XOM satrni o'lchaydi: "  a" undan o'tib ketardi.
    matn = q.strip()
    if len(matn) < 3:
        return []
    yashirin = _hidden_statuses(current_user)
    holatlar = (status,) if status is not None else _DEFAULT_STATUSES

    # Ustunlar sanab tanlanadi: butun ORM obyektida `cutmap`/`survey`/
    # `xnc_summary` ham kelardi — 50 qatorga ~850 KB, keragi ~2.5 KB
    # (`lifecycle.py` reestrda shu darsni o'tgan).
    so_rov = (
        select(
            PartInstance.id,
            PartInstance.qr_text,
            PartInstance.instance_no,
            Part.id.label("part_id"),
            Part.name.label("part_name"),
            Order.id.label("order_id"),
            Order.number.label("order_number"),
            Order.status.label("order_status"),
        )
        .join(Part, Part.id == PartInstance.part_id)
        .join(Order, Order.id == PartInstance.order_id)
        .where(
            # `autoescape`: Detal ID da `_` bor, escapesiz u SQL jokeri bo'lardi.
            PartInstance.qr_text.icontains(matn, autoescape=True),
            PartInstance.is_deleted == False,  # noqa: E712
            Part.is_deleted == False,  # noqa: E712
            Order.is_deleted == False,  # noqa: E712
            Order.status.in_(holatlar),
        )
    )
    if yashirin:
        so_rov = so_rov.where(Order.status.not_in(yashirin))
    nusxalar = (await db.execute(so_rov.order_by(PartInstance.qr_text).limit(_LIMIT))).all()
    if not nusxalar:
        return []

    detal_ids = {n.part_id for n in nusxalar}
    inst_ids = {n.id for n in nusxalar}

    # Qadam ID kerak: skan sanog'i POST emas, QADAM bo'yicha — bitta post
    # marshrutda ikki marta uchraydi (`kromka → prisadka → yana kromka`).
    qadamlar: dict[int, list[Any]] = {}
    for q_ in (
        await db.execute(
            select(
                PartRoute.id,
                PartRoute.part_id,
                PartRoute.seq,
                Post.code,
                PartRoute.per_instance,
            )
            .join(Post, Post.id == PartRoute.post_id)
            .where(
                PartRoute.part_id.in_(detal_ids),
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(PartRoute.part_id, PartRoute.seq)
        )
    ).all():
        qadamlar.setdefault(q_.part_id, []).append(q_)

    sanoq: dict[tuple[int, int], int] = {
        (iid, rid): int(n)
        for iid, rid, n in (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count(Scan.id))
                .where(Scan.instance_id.in_(inst_ids), *_TIRIK_SKAN)
                .group_by(Scan.instance_id, Scan.route_id)
            )
        ).all()
    }
    # Oxirgi skan — detal jismonan shu yerda. `id DESC`: `created_at` ning
    # server sukuti `current_timestamp(0)`, ya'ni sekundgacha yaxlitlangan.
    oxirgi_s = (
        select(Scan.instance_id, Post.code, Scan.created_at)
        .join(Post, Post.id == Scan.post_id)
        .where(Scan.instance_id.in_(inst_ids), *_TIRIK_SKAN)
        .distinct(Scan.instance_id)
        .order_by(Scan.instance_id, Scan.created_at.desc(), Scan.id.desc())
    )
    oxirgi: dict[int, tuple[str, datetime]] = {
        iid: (code, vaqt) for iid, code, vaqt in (await db.execute(oxirgi_s)).all()
    }
    # Bir nusxada bir nechta ochiq brak bo'lishi mumkin: `defects.py` dagi
    # takrorlanish qorovuli SKAN bo'yicha, nusxa bo'yicha emas. Eng yangisi.
    braklar_s = (
        select(PartDefect.instance_id, Post.code, PartDefect.reason)
        .join(Post, Post.id == PartDefect.post_id)
        .where(
            PartDefect.instance_id.in_(inst_ids),
            PartDefect.status.in_((DefectStatus.PENDING, DefectStatus.CONFIRMED)),
            PartDefect.is_deleted == False,  # noqa: E712
        )
        .distinct(PartDefect.instance_id)
        .order_by(PartDefect.instance_id, PartDefect.created_at.desc(), PartDefect.id.desc())
    )
    braklar: dict[int, tuple[str, str]] = {
        iid: (code, reason) for iid, code, reason in (await db.execute(braklar_s)).all()
    }

    javob: list[InstanceTrace] = []
    for n in nusxalar:
        steps: list[InstanceStep] = []
        keyingi: str | None = None
        for q_ in qadamlar.get(n.part_id, []):
            done = sanoq.get((n.id, q_.id), 0)
            steps.append(InstanceStep(seq=q_.seq, post_code=q_.code, need=q_.per_instance, done=done))
            if keyingi is None and done < q_.per_instance:
                keyingi = q_.code
        brak = braklar.get(n.id)
        oxirgi_post = oxirgi.get(n.id)
        javob.append(
            InstanceTrace(
                qr_text=n.qr_text,
                order_id=n.order_id,
                order_number=n.order_number,
                order_status=n.order_status,
                part_name=n.part_name,
                instance_no=n.instance_no,
                steps=steps,
                last_post=oxirgi_post[0] if oxirgi_post else None,
                last_at=oxirgi_post[1] if oxirgi_post else None,
                next_post=keyingi,
                defect_post=brak[0] if brak else None,
                defect_reason=brak[1] if brak else None,
            )
        )
    return javob
