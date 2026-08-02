from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class BridgeAgentRead(BaseModel):
    """Admin ro'yxati. pair_code faqat hali ulanmagan agentda bo'ladi —
    ro'yxatning o'zi admin-only, shuning uchun kodni ko'rsatish xavfsiz."""

    id: int
    name: str
    paired: bool
    pair_code: str | None
    pair_expires_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    # Skan-forvard: stanok skaneri MES'ga shu stanok nomidan yoziladi
    machine_id: int | None = None
    machine_name: str | None = None
    # Agent exe versiyasi (oxirgi ulanishdan); null = eski (headersiz) exe
    version: str | None = None
    # False = printersiz stansiya (skan-forvard) — chek navbatidan ish olmaydi
    can_print: bool = True


class BridgeAgentCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Arrachi monoblok"])]


class BridgeAgentUpdate(BaseModel):
    """Stanok bog'lami va chek-chiqarish belgisi. can_print=None = tegilmaydi
    (machine_id'da None "olib tashlash" degani, shuning uchun sentinel farqli)."""

    machine_id: int | None = None
    can_print: bool | None = None


class BridgeScanRequest(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]
    client_event_id: Annotated[str, Field(min_length=8, max_length=64)]


class BridgePairRequest(BaseModel):
    code: Annotated[str, Field(min_length=4, max_length=16)]


class BridgePairResponse(BaseModel):
    """Token FAQAT shu javobda beriladi — bazada sha256 xeshi qoladi."""

    token: str
    name: str
