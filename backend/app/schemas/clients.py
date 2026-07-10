from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClientType

from .users import PHONE_PATTERN

_NAME_FIELD = Field(min_length=2, max_length=150, examples=["Azamat Karimov"])
_PHONE = Field(pattern=PHONE_PATTERN, examples=["+998901234567"], default=None)


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    client_type: ClientType
    phone: str | None
    phone_alt: str | None
    address: str | None
    inn: str | None
    notes: str | None
    created_at: datetime
    orders_count: int = 0  # computed in the route, not stored


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str, _NAME_FIELD]
    client_type: ClientType = ClientType.INDIVIDUAL
    phone: Annotated[str | None, _PHONE]
    phone_alt: Annotated[str | None, _PHONE]
    address: str | None = Field(default=None, max_length=255)
    inn: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str | None, Field(min_length=2, max_length=150, default=None)]
    client_type: ClientType | None = None
    phone: Annotated[str | None, _PHONE]
    phone_alt: Annotated[str | None, _PHONE]
    address: str | None = Field(default=None, max_length=255)
    inn: str | None = Field(default=None, max_length=20)
    notes: str | None = None
