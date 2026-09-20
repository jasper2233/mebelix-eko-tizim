from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import DowntimeReason
from app.schemas.downtimes import DowntimeReasonCreate, DowntimeReasonRead, DowntimeReasonUpdate
from app.schemas.settings import (
    DefectReasons,
    IdealCycle,
    IdealCycleKromka,
    SystemSettingRead,
    SystemSettingUpdate,
    WorkSchedule,
)
from app.services.settings_service import (
    DEFAULTS,
    DEFECT_REASONS,
    IDEAL_CYCLE,
    IDEAL_CYCLE_KROMKA,
    INT_RANGES,
    WORK_SCHEDULE,
    get_defect_reasons,
    get_ideal_cycle,
    get_ideal_cycle_kromka,
    get_setting,
    get_work_schedule,
    schedule_error,
    set_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=list[SystemSettingRead], operation_id="read_system_settings")
async def read_system_settings(db: SessionDep, _: AdminUser) -> list[SystemSettingRead]:
    """Sahifada ko'rsatiladigan hamma sozlama — hali yozilmagani sukut qiymati bilan."""
    return [SystemSettingRead(key=key, value=await get_setting(db, key)) for key in DEFAULTS]


# NOTE: `/work-schedule` `/{key}` dan OLDIN turishi shart — aks holda PUT uni kalit deb o'qiydi.
@router.get("/work-schedule", response_model=WorkSchedule, operation_id="read_work_schedule")
async def read_work_schedule(db: SessionDep, _: AdminUser) -> WorkSchedule:
    """Ish jadvali: smenalar, ularning tanaffuslari, haftalik dam olish kunlari va bayramlar."""
    return await get_work_schedule(db)


@router.put("/work-schedule", response_model=WorkSchedule, operation_id="update_work_schedule")
async def update_work_schedule(
    db: SessionDep, current_user: AdminUser, body: WorkSchedule, request: Request
) -> WorkSchedule:
    """Jadval BUTUNICHA almashtiriladi — sahifa hamma smena va sanani bitta formada yuboradi."""
    if (error := schedule_error(body)) is not None:
        raise HTTPException(status_code=422, detail=error)
    body.days_off.sort()
    body.holidays.sort(key=lambda holiday: holiday.day)
    row = await set_setting(db, WORK_SCHEDULE, body.model_dump_json(), current_user.id)
    await db.flush()  # yangi qatorning id si audit yozuviga tushsin
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=(
            f"Ish jadvali o'zgardi: {len(body.shifts)} smena, "
            f"{len(body.days_off)} dam olish kuni, {len(body.holidays)} bayram sanasi"
        ),
        ip=client_ip(request),
    )
    await db.commit()
    return body


# NOTE: `/ideal-cycle` ham `/{key}` dan OLDIN — sabab yuqoridagidek.
@router.get("/ideal-cycle", response_model=IdealCycle, operation_id="read_ideal_cycle")
async def read_ideal_cycle(db: SessionDep, _: AdminUser) -> IdealCycle:
    """Prisadka ideal sikli koeffitsiyentlari (OEE Performance); kiritilmagan bo'lsa taxminiy sukut qiymatlar."""
    return await get_ideal_cycle(db)


@router.put("/ideal-cycle", response_model=IdealCycle, operation_id="update_ideal_cycle")
async def update_ideal_cycle(db: SessionDep, current_user: AdminUser, body: IdealCycle, request: Request) -> IdealCycle:
    """Beshta koeffitsiyent BIRGA almashtiriladi. Hisobot o'tgan kunlarni ham yangi qiymat bilan qayta hisoblaydi."""
    row = await set_setting(db, IDEAL_CYCLE, body.model_dump_json(), current_user.id)
    await db.flush()  # yangi qatorning id si audit yozuviga tushsin
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=(
            f"Ideal sikl o'zgardi: detalga {body.load_s:g} s, yuza teshik {body.bore_s:g} s, "
            f"qirra teshik {body.edge_bore_s:g} s, paz {body.groove_s:g} s, freza {body.mill_s:g} s"
        ),
        ip=client_ip(request),
    )
    await db.commit()
    return body


# NOTE: `/ideal-cycle-kromka` ham `/{key}` dan OLDIN — sabab yuqoridagidek.
@router.get("/ideal-cycle-kromka", response_model=IdealCycleKromka, operation_id="read_ideal_cycle_kromka")
async def read_ideal_cycle_kromka(db: SessionDep, _: AdminUser) -> IdealCycleKromka:
    """Kromka ideal sikli: detallar orasidagi bo'shliq (soniya). Qolganini lenta va
    o'lchangan uzunlik belgilaydi — taxminiy koeffitsiyent yo'q."""
    return await get_ideal_cycle_kromka(db)


@router.put("/ideal-cycle-kromka", response_model=IdealCycleKromka, operation_id="update_ideal_cycle_kromka")
async def update_ideal_cycle_kromka(
    db: SessionDep, current_user: AdminUser, body: IdealCycleKromka, request: Request
) -> IdealCycleKromka:
    """Hisobot o'tgan kunlarni ham yangi qiymat bilan qayta hisoblaydi (ideal vaqt saqlanmaydi)."""
    row = await set_setting(db, IDEAL_CYCLE_KROMKA, body.model_dump_json(), current_user.id)
    await db.flush()  # yangi qatorning id si audit yozuviga tushsin
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=f"Kromka ideal sikli o'zgardi: detallar oralig'i {body.gap_s:g} s",
        ip=client_ip(request),
    )
    await db.commit()
    return body


# NOTE: `/defect-reasons` ham `/{key}` dan OLDIN — sabab yuqoridagidek.
@router.get("/defect-reasons", response_model=DefectReasons, operation_id="read_defect_reasons")
async def read_defect_reasons(db: SessionDep, _: AdminUser) -> DefectReasons:
    """Brak sabablari (OEE Quality) — terminaldagi BRAK oynasida shu tugmalar chiqadi."""
    return await get_defect_reasons(db)


@router.put("/defect-reasons", response_model=DefectReasons, operation_id="update_defect_reasons")
async def update_defect_reasons(
    db: SessionDep, current_user: AdminUser, body: DefectReasons, request: Request
) -> DefectReasons:
    """Ro'yxat BUTUNICHA almashtiriladi. Eski brak yozuvlari tegilmaydi — ularda sabab MATN
    bo'lib saqlangan (`part_defect.reason`), ya'ni ro'yxatdan olib tashlansa ham o'qiladi."""
    body.reasons = [r for i, r in enumerate(body.reasons) if r not in body.reasons[:i]]  # takrorni tashlaydi
    row = await set_setting(db, DEFECT_REASONS, body.model_dump_json(), current_user.id)
    await db.flush()  # yangi qatorning id si audit yozuviga tushsin
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=f"Brak sabablari o'zgardi: {len(body.reasons)} ta",
        ip=client_ip(request),
    )
    await db.commit()
    return body


@router.put("/{key}", response_model=SystemSettingRead, operation_id="update_system_setting")
async def update_system_setting(
    db: SessionDep, current_user: AdminUser, key: str, body: SystemSettingUpdate, request: Request
) -> SystemSettingRead:
    if key not in DEFAULTS:
        # Noma'lum kalitni yozib qo'yish jimgina "ishladi" deb ko'rinardi, lekin
        # uni hech kim o'qimasdi.
        raise NotFoundException("Bunday sozlama yo'q.")
    value = body.value.strip()
    if (bounds := INT_RANGES.get(key)) is not None:
        low, high = bounds
        if not (value.isascii() and value.isdigit() and low <= int(value) <= high):
            raise HTTPException(status_code=422, detail=f"Daqiqa {low} dan {high} gacha butun son bo'lishi kerak.")
        value = str(int(value))  # "090" -> "90"
    row = await set_setting(db, key, value, current_user.id)
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=f"Sozlama o'zgardi: {key} = {row.value!r}",
        ip=client_ip(request),
    )
    await db.commit()
    return SystemSettingRead(key=row.key, value=row.value)


# --- To'xtash sabablari (terminal oynasidagi ro'yxat) ---------------------------------------


@router.get("/downtime-reasons", response_model=list[DowntimeReasonRead], operation_id="read_downtime_reasons")
async def read_downtime_reasons(db: SessionDep, _: AdminUser) -> list[DowntimeReason]:
    """Hamma sabab, nofaollari ham — admin ularni qayta yoqishi mumkin."""
    return list(
        (
            await db.execute(
                select(DowntimeReason)
                .where(DowntimeReason.is_deleted == False)  # noqa: E712
                .order_by(DowntimeReason.is_planned, DowntimeReason.order_index, DowntimeReason.id)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/downtime-reasons", response_model=DowntimeReasonRead, status_code=201, operation_id="create_downtime_reason"
)
async def create_downtime_reason(
    db: SessionDep, current_user: AdminUser, body: DowntimeReasonCreate, request: Request
) -> DowntimeReason:
    """Ro'yxat kodga yozilmaydi (statik bo'lib qolmasin) — egasining ro'yxatini ham admin shu yerdan kiritadi."""
    last = (
        await db.execute(select(func.max(DowntimeReason.order_index)).where(DowntimeReason.is_deleted == False))  # noqa: E712
    ).scalar()
    reason = DowntimeReason(
        name=body.name, is_planned=body.is_planned, needs_note=body.needs_note, order_index=(last or 0) + 1
    )
    db.add(reason)
    await db.flush()
    log_action(
        db,
        module="settings",
        action="created",
        user_id=current_user.id,
        entity_type="downtime_reason",
        entity_id=reason.id,
        message=f"To'xtash sababi qo'shildi: {reason.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return reason


@router.patch("/downtime-reasons/{reason_id}", response_model=DowntimeReasonRead, operation_id="update_downtime_reason")
async def update_downtime_reason(
    db: SessionDep, current_user: AdminUser, reason_id: int, body: DowntimeReasonUpdate, request: Request
) -> DowntimeReason:
    reason = await db.get(DowntimeReason, reason_id)
    if reason is None or reason.is_deleted:
        raise NotFoundException("Sabab topilmadi.")
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(reason, field, value)
    log_action(
        db,
        module="settings",
        action="updated",
        user_id=current_user.id,
        entity_type="downtime_reason",
        entity_id=reason.id,
        message=f"To'xtash sababi o'zgardi: {reason.name}" + ("" if reason.is_active else " (nofaol)"),
        ip=client_ip(request),
    )
    await db.commit()
    return reason
