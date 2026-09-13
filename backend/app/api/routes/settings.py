from fastapi import APIRouter, Request

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.schemas.settings import SystemSettingRead, SystemSettingUpdate
from app.services.settings_service import DEFAULTS, get_setting, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=list[SystemSettingRead], operation_id="read_system_settings")
async def read_system_settings(db: SessionDep, _: AdminUser) -> list[SystemSettingRead]:
    """Sahifada ko'rsatiladigan hamma sozlama — hali yozilmagani sukut qiymati bilan."""
    return [SystemSettingRead(key=key, value=await get_setting(db, key)) for key in DEFAULTS]


@router.put("/{key}", response_model=SystemSettingRead, operation_id="update_system_setting")
async def update_system_setting(
    db: SessionDep, current_user: AdminUser, key: str, body: SystemSettingUpdate, request: Request
) -> SystemSettingRead:
    if key not in DEFAULTS:
        # Noma'lum kalitni yozib qo'yish jimgina "ishladi" deb ko'rinardi, lekin
        # uni hech kim o'qimasdi.
        raise NotFoundException("Bunday sozlama yo'q.")
    row = await set_setting(db, key, body.value.strip(), current_user.id)
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
