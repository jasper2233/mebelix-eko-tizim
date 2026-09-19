"""Menejer: brakni tasdiqlash yoki «brak emas» deb rad etish (`docs/12-oee.md` §7).

Operator terminalda faqat QAYD qiladi — u kim aybdor va qayerdan qayta boshlanishini
bilmaydi. Menejer shu sahifada aybdor QADAMNI (post emas: bitta post marshrutda ikki
marta uchrashi mumkin) va qayta boshlash nuqtasini belgilaydi.

Qayta ishlab chiqarishning O'ZI (eski skanlarni bekor qilish, `-B1` nusxa, yangi chek,
marshrutni qayta ochish) hali YO'Q — bu sahifa hozircha QARORNI yozadi. Sabab: qaror
yozuvisiz brak statistikasi (aybdor post, qaytish nuqtasi) umuman yig'ilmaydi, remake
esa alohida katta oqim.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.api.deps import ManagerUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Employee, Machine, Order, Part, PartDefect, PartInstance, PartRoute, Post, Scan, User
from app.models.enums import DefectStatus
from app.schemas.defects import DefectPending, DefectReview, DefectRow, DefectStep

router = APIRouter(prefix="/defects", tags=["defects"])

#: Sahifada sahifalash yo'q — brak kuniga bir necha dona, oy davomida ham yuzdan oshmaydi.
_LIMIT = 300


async def _steps(db: AsyncSession, part_ids: set[int]) -> dict[int, list[DefectStep]]:
    """Detal marshruti + har qadamda skanerlagan hodim (oxirgi bekor qilinmagan skan).

    Marshrut detal TURIGA bog'langan (`part_route.part_id`, `seq` tartibi) va NOSTANDART
    detalda ham xuddi shunday o'qiladi — texnolog qo'lda chizgan qatorlar shu jadvalda
    turadi. Shuning uchun qaror POST emas, QADAM bo'yicha yoziladi: `[Kromka, Prisadka,
    Kromka]` marshrutida «Kromka aybdor» qaysi o'tish ekanini aytmaydi, «2. Prisadka» esa
    aniq. Kelajakdagi remake ham shu qatorlarni O'ZGARTIRMAYDI — yangi `-B1` nusxa o'sha
    `part_id` ni oladi (docs/12 §7 qarori), ya'ni saqlangan `restart_route_id` o'shanda ham
    to'g'ri qadamni ko'rsatib turadi."""
    if not part_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(PartRoute.id, PartRoute.part_id, PartRoute.seq, PartRoute.process_code, Post.code, Post.name)
                .join(Post, Post.id == PartRoute.post_id)
                .where(
                    PartRoute.part_id.in_(part_ids),
                    # Texnolog O'CHIRGAN qadam ro'yxatda turmaydi: detal u yerdan o'tmagan,
                    # ya'ni na ayb, na qayta boshlash nuqtasi bo'la oladi.
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.part_id, PartRoute.seq)
            )
        )
        .tuples()
        .all()
    )
    # Qaysi qadamda kim ishlagan: oxirgi bekor qilinmagan skan. Bitta so'rovda — qatorlar
    # kam, lekin har qadam uchun alohida so'rov N+1 bo'lardi.
    scans = (
        (
            await db.execute(
                select(Scan.route_id, Employee.id, Employee.full_name, func.max(Scan.created_at))
                .join(Employee, Employee.id == Scan.employee_id)
                .where(
                    Scan.route_id.in_([r[0] for r in rows]),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.route_id, Employee.id, Employee.full_name)
                .order_by(Scan.route_id, func.max(Scan.created_at))
            )
        )
        .tuples()
        .all()
    )
    oxirgi = {route_id: (emp_id, name) for route_id, emp_id, name, _at in scans}  # oxirgisi g'olib
    out: dict[int, list[DefectStep]] = {}
    for route_id, part_id, seq, process_code, post_code, post_name in rows:
        emp_id, emp_name = oxirgi.get(route_id, (None, None))
        out.setdefault(part_id, []).append(
            DefectStep(
                route_id=route_id,
                seq=seq,
                post_code=str(post_code),
                post_name=post_name,
                process_code=process_code,
                employee_id=emp_id,
                employee_name=emp_name,
            )
        )
    return out


async def _rows(db: AsyncSession, *, status: DefectStatus | None, defect_id: int | None = None) -> list[DefectRow]:
    """Sahifa qatorlari. `defect_id` berilsa faqat o'sha bitta yozuv (qaror javobida)."""
    query = (
        select(PartDefect, Order, Part, PartInstance, Post, Machine, Employee)
        .join(Order, Order.id == PartDefect.order_id)
        .join(Part, Part.id == PartDefect.part_id)
        .join(PartInstance, PartInstance.id == PartDefect.instance_id)
        .join(Post, Post.id == PartDefect.post_id)
        .outerjoin(Machine, Machine.id == PartDefect.machine_id)
        .outerjoin(Employee, Employee.id == PartDefect.employee_id)
        .where(PartDefect.is_deleted == False)  # noqa: E712
        .order_by(PartDefect.created_at.desc())
        .limit(_LIMIT)
        # Buyurtmaning og'ir JSONB ustunlari bu yerda o'qilmaydi
        .options(*(defer(getattr(Order, n)) for n in ("cutmap", "survey", "material_usage", "machine_assignments")))
    )
    if status is not None:
        query = query.where(PartDefect.status == status)
    if defect_id is not None:
        query = query.where(PartDefect.id == defect_id)
    rows = (await db.execute(query)).all()

    steps = await _steps(db, {r[2].id for r in rows})
    # Tasdiqlangan qatorlarda ayb SURATGA olingan hodimda — marshrutdagi joriy odamda emas
    blamed = {
        e.id: e.full_name
        for e in (
            await db.execute(
                select(Employee).where(Employee.id.in_([d.blame_employee_id for d, *_ in rows if d.blame_employee_id]))
            )
        ).scalars()
    }
    reviewers = {
        u.id: u.name
        for u in (
            await db.execute(select(User).where(User.id.in_([d.reviewed_by_id for d, *_ in rows if d.reviewed_by_id])))
        ).scalars()
    }
    return [
        DefectRow(
            id=defect.id,
            created_at=defect.created_at,
            status=defect.status,
            reason=defect.reason,
            note=defect.note,
            qr_text=instance.qr_text,
            order_id=order.id,
            order_number=order.number,
            part_code=part.code,
            part_name=part.name,
            post_name=post.name,
            machine_name=machine.name if machine else None,
            employee_name=employee.full_name if employee else None,
            steps=steps.get(part.id, []),
            blame_route_id=defect.blame_route_id,
            blame_employee_name=blamed.get(defect.blame_employee_id or 0),
            restart_route_id=defect.restart_route_id,
            reviewed_at=defect.reviewed_at,
            reviewed_by=reviewers.get(defect.reviewed_by_id or 0),
        )
        for defect, order, part, instance, post, machine, employee in rows
    ]


@router.get("/", response_model=list[DefectRow], operation_id="read_defects")
async def read_defects(
    db: SessionDep,
    _: ManagerUser,
    status: DefectStatus | None = Query(default=DefectStatus.PENDING),
) -> list[DefectRow]:
    """Brak ro'yxati. `status` berilmasa — HAMMASI (sahifadagi «Hammasi» tabi)."""
    return await _rows(db, status=status)


@router.get("/pending-count", response_model=DefectPending, operation_id="read_pending_defect_count")
async def read_pending_defect_count(db: SessionDep, _: ManagerUser) -> DefectPending:
    """Sidebar belgisi: menejer hali ko'rmagan braklar soni."""
    count = (
        await db.execute(
            select(func.count())
            .select_from(PartDefect)
            .where(
                PartDefect.status == DefectStatus.PENDING,
                PartDefect.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    return DefectPending(count=int(count))


@router.post("/{defect_id}/review", response_model=DefectRow, operation_id="review_defect")
async def review_defect(
    db: SessionDep, current_user: ManagerUser, defect_id: int, body: DefectReview, request: Request
) -> DefectRow:
    """Tasdiqlash yoki rad etish. Qarorni O'ZGARTIRISH mumkin — noto'g'ri bosilgani tuzatilsin."""
    defect = await db.get(PartDefect, defect_id)
    if defect is None or defect.is_deleted:
        raise NotFoundException("Brak yozuvi topilmadi.")
    if body.status == DefectStatus.PENDING:
        raise HTTPException(status_code=422, detail="Qaror tanlanmagan: tasdiqlash yoki «brak emas».")

    if body.status == DefectStatus.CONFIRMED:
        if body.restart_route_id is None:
            raise HTTPException(status_code=422, detail="Qayta ishlab chiqarish qaysi qadamdan boshlanishini tanlang.")
        # Ikkala qadam ham AYNAN shu detalning marshrutidan bo'lishi shart
        tanlangan = [r for r in (body.blame_route_id, body.restart_route_id) if r is not None]
        oz = set(
            (
                await db.execute(
                    select(PartRoute.id).where(
                        PartRoute.id.in_(tanlangan),
                        PartRoute.part_id == defect.part_id,
                        PartRoute.is_enabled == True,  # noqa: E712
                        PartRoute.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(oz) != len(set(tanlangan)):
            raise HTTPException(status_code=422, detail="Tanlangan qadam bu detalning marshrutida yo'q.")
        defect.blame_route_id = body.blame_route_id
        defect.restart_route_id = body.restart_route_id
        # Aybdor hodim SURATGA olinadi: keyin skan bekor qilinsa yoki qayta skanerlansa
        # ayb boshqa odamga ko'chib ketmasin
        defect.blame_employee_id = (
            (
                await db.execute(
                    select(Scan.employee_id)
                    .where(
                        Scan.route_id == body.blame_route_id,
                        Scan.instance_id == defect.instance_id,
                        Scan.is_cancelled == False,  # noqa: E712
                        Scan.is_deleted == False,  # noqa: E712
                    )
                    .order_by(Scan.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if body.blame_route_id is not None
            else None
        )
    else:  # rad etildi — qaror maydonlari tozalanadi, Quality'ga ham kirmaydi
        defect.blame_route_id = defect.restart_route_id = defect.blame_employee_id = None

    defect.status = body.status
    defect.reviewed_by_id = current_user.id
    defect.reviewed_at = datetime.now(UTC)
    log_action(
        db,
        module="defect",
        action="confirmed" if body.status == DefectStatus.CONFIRMED else "rejected",
        user_id=current_user.id,
        entity_type="defect",
        entity_id=defect.id,
        message=(
            f"Brak tasdiqlandi: {defect.reason}"
            if body.status == DefectStatus.CONFIRMED
            else f"«Brak emas» deb rad etildi: {defect.reason}"
        ),
        ip=client_ip(request),
    )
    await db.commit()
    return (await _rows(db, status=None, defect_id=defect.id))[0]
