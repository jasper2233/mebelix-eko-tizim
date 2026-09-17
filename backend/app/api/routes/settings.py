from fastapi import APIRouter, HTTPException, Request

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.schemas.settings import SystemSettingRead, SystemSettingUpdate, WorkSchedule
from app.services.settings_service import (
    DEFAULTS,
    IDLE_MINUTES_RANGE,
    IDLE_OPERATOR_MINUTES,
    IDLE_STAFF_MINUTES,
    WORK_SCHEDULE,
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


@router.put("/{key}", response_model=SystemSettingRead, operation_id="update_system_setting")
async def update_system_setting(
    db: SessionDep, current_user: AdminUser, key: str, body: SystemSettingUpdate, request: Request
) -> SystemSettingRead:
    if key not in DEFAULTS:
        # Noma'lum kalitni yozib qo'yish jimgina "ishladi" deb ko'rinardi, lekin
        # uni hech kim o'qimasdi.
        raise NotFoundException("Bunday sozlama yo'q.")
    value = body.value.strip()
    if key in (IDLE_OPERATOR_MINUTES, IDLE_STAFF_MINUTES):
        low, high = IDLE_MINUTES_RANGE
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
