from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MaterialType


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    type: MaterialType
    thickness: float | None
    width: float | None
    length: float | None
    default_supplier: str | None
    price_per_unit: Decimal | None
    color: str | None
    glossiness: str | None
    created_at: datetime


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=150, examples=["LDSP OQ GLYANETS"])
    code: str | None = Field(default=None, max_length=50)
    type: MaterialType
    thickness: float | None = Field(default=None, gt=0)
    width: float | None = Field(default=None, gt=0)
    length: float | None = Field(default=None, gt=0)
    default_supplier: str | None = Field(default=None, max_length=100)
    price_per_unit: Decimal | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=30)
    glossiness: str | None = Field(default=None, max_length=30)


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, max_length=50)
    thickness: float | None = Field(default=None, gt=0)
    width: float | None = Field(default=None, gt=0)
    length: float | None = Field(default=None, gt=0)
    default_supplier: str | None = Field(default=None, max_length=100)
    price_per_unit: Decimal | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=30)
    glossiness: str | None = Field(default=None, max_length=30)
