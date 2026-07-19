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


class BridgeAgentCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Arrachi monoblok"])]


class BridgePairRequest(BaseModel):
    code: Annotated[str, Field(min_length=4, max_length=16)]


class BridgePairResponse(BaseModel):
    """Token FAQAT shu javobda beriladi — bazada sha256 xeshi qoladi."""

    token: str
    name: str
