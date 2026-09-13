"""Ish vaqtidagi sozlamalar (`system_setting`) — o'qish va yozish bitta joyda.

`app/core/config.py` dagi `.env` sozlamalaridan farqi: bularni admin panelda
o'zgartiradi va konteynerni qayta ishga tushirish shart emas.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting

#: Bazisda detal nomi shu belgi bilan tugasa — yuklashda NOSTANDART.
#: Bo'sh qiymat qoidani BUTUNLAY o'chiradi (belgisiz hamma detal nostandart
#: bo'lib qolmasin — `str.endswith("")` har doim rost).
CUSTOM_PART_SUFFIX = "custom_part_suffix"

#: Sahifada ko'rsatiladigan sozlamalar va ularning sukut qiymati.
DEFAULTS: dict[str, str] = {CUSTOM_PART_SUFFIX: "#"}


async def get_setting(db: AsyncSession, key: str) -> str:
    """Qiymat yoki sukut. Yo'q kalit uchun ham xato emas — sahifa hali ochilmagan bo'lishi mumkin."""
    row = (
        await db.execute(
            select(SystemSetting.value).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    return row if row is not None else DEFAULTS.get(key, "")


async def set_setting(db: AsyncSession, key: str, value: str, user_id: int) -> SystemSetting:
    """Bor bo'lsa yangilaydi, yo'q bo'lsa yaratadi. `flush` chaqiruvchida."""
    row = (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by_id=user_id)
        db.add(row)
    else:
        row.value = value
        row.updated_by_id = user_id
    return row
