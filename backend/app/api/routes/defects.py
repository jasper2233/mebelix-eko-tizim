"""Terminal: brak qaydi — OEE Quality shundan (`docs/12-oee.md` §4.7).

Oqim eng qisqa yo'l bilan: operator detalni odatdagidek skanerlaydi, skan tasmasidagi
BRAK tugmasini bosadi va faqat NIMA bo'lganini tanlaydi (docs/12 §7 qarori — doimiy
tugma emas, kerak paytda chiqadigan oyna). Skan BEKOR QILINMAYDI va marshrut qayta
ochilmaydi: qayta ishlab chiqarish oqimi (`-B1` nusxa, yangi chek, aybdor post) —
keyingi bosqich. Ya'ni brak hozir faqat O'LCHANADI, ish oqimini o'zgartirmaydi.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip
from app.api.routes.terminal import TerminalCtx, TerminalUser
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import PartDefect, Scan
from app.models.enums import DefectStatus
from app.schemas.defects import DefectCreate, DefectRead
from app.services.kromka import AUTO_DEFECT_REASON
from app.services.scanning import active_session
from app.services.settings_service import get_defect_reasons

router = APIRouter(prefix="/terminal", tags=["terminal"])


@router.get("/defect-reasons", response_model=list[str], operation_id="read_terminal_defect_reasons")
async def read_terminal_defect_reasons(db: SessionDep, _: TerminalUser) -> list[str]:
    """Brak sabablari. Bo'sh ro'yxat — terminalda BRAK tugmasi umuman chizilmaydi
    (to'xtash sabablaridagi bilan bir xil qoida: kiritilmagan ro'yxat ishni to'smaydi)."""
    return (await get_defect_reasons(db)).reasons


@router.post("/defects", response_model=DefectRead, status_code=201, operation_id="mark_defect")
async def mark_defect(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, body: DefectCreate, request: Request
) -> PartDefect:
    """Skanerlangan nusxani brak deb belgilaydi. Kiritgan — brigadaning langar smenasi."""
    machine, post = ctx
    scan = await db.get(Scan, body.scan_id)
    if scan is None or scan.is_deleted:
        raise NotFoundException("Skan topilmadi.")
    if scan.is_cancelled:
        raise HTTPException(status_code=422, detail="Bekor qilingan skanni brak deb belgilab bo'lmaydi.")
    # Faqat O'Z postining skani: brakni ishni bajargan post belgilaydi, aks holda
    # bir nusxa ikki postdan ikki marta brak bo'lib Quality ikki barobar tushardi.
    if scan.post_id != post.id:
        raise ForbiddenException("Bu skan boshqa postda yozilgan — brakni o'sha post belgilaydi.")
    reasons = (await get_defect_reasons(db)).reasons
    if body.reason not in reasons:
        # Ro'yxat bo'sh yoki sabab o'chirilgan — terminal eskirgan ro'yxatni ko'rsatib turgan
        raise HTTPException(status_code=422, detail="Bunday brak sababi yo'q. Sahifani yangilang.")
    already = (
        await db.execute(
            select(PartDefect).where(
                PartDefect.scan_id == scan.id,
                PartDefect.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    session = await active_session(db, machine)  # E005/E006 — smena yo'q yoki hodim nofaol
    if already is not None:
        # Kromka stansiyasi o'lchov mos kelmaganda qaydni O'ZI ochadi (`services/kromka.py`)
        # va terminalda shu oyna chiqadi — operator tanlagan sabab o'sha qatorga yoziladi.
        # Ikkinchi qator yaratilsa bitta qirra ikki marta brak bo'lib Quality qo'sh tushardi.
        if already.reason != AUTO_DEFECT_REASON or already.status != DefectStatus.PENDING:
            raise HTTPException(status_code=422, detail="Bu skan allaqachon brak deb belgilangan.")
        already.reason = body.reason
        already.note = body.note or already.note
        already.employee_id = session.employee_id
        log_action(
            db,
            module="defect",
            action="updated",
            user_id=user.id,
            employee_id=session.employee_id,
            entity_type="defect",
            entity_id=already.id,
            message=f"Brak sababi: {body.reason} — {post.name}",
            ip=client_ip(request),
        )
        await db.commit()
        return already

    defect = PartDefect(
        order_id=scan.order_id,
        part_id=scan.part_id,
        instance_id=scan.instance_id,
        scan_id=scan.id,
        machine_id=machine.id,
        post_id=post.id,
        employee_id=session.employee_id,
        reason=body.reason,
        note=body.note or None,
    )
    db.add(defect)
    await db.flush()
    log_action(
        db,
        module="defect",
        action="created",
        user_id=user.id,
        employee_id=session.employee_id,
        entity_type="defect",
        entity_id=defect.id,
        message=f"Brak: {body.reason} — {post.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return defect


@router.delete("/defects/{defect_id}", response_model=DefectRead, operation_id="unmark_defect")
async def unmark_defect(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, defect_id: int, request: Request
) -> PartDefect:
    """Noto'g'ri bosilgan BRAK ni qaytaradi (yumshoq o'chirish).

    Faqat O'SHA ish markazida: brak tugmasi katta va skan tasmasining yonida turadi,
    ya'ni xato bosish real — usiz operator noto'g'ri raqamni tuzata olmasdi."""
    machine, _post = ctx
    defect = await db.get(PartDefect, defect_id)
    if defect is None or defect.is_deleted or defect.machine_id != machine.id:
        raise NotFoundException("Brak yozuvi topilmadi.")
    if defect.status != DefectStatus.PENDING:
        # Menejer qaror qabul qilib bo'lgan — operator uni jimgina o'chira olmaydi
        raise HTTPException(status_code=422, detail="Bu brakni menejer ko'rib chiqqan — o'zgartirishni undan so'rang.")
    defect.is_deleted = True
    defect.deleted_at = datetime.now(UTC)
    log_action(
        db,
        module="defect",
        action="deleted",
        user_id=user.id,
        employee_id=defect.employee_id,
        entity_type="defect",
        entity_id=defect.id,
        message=f"Brak bekor qilindi: {defect.reason}",
        ip=client_ip(request),
    )
    await db.commit()
    return defect
