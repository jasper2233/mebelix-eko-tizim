from pydantic import BaseModel, ConfigDict, Field

from .base import TimestampSchema


class ItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemPublic(ItemBase, TimestampSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int


class ItemsPublic(BaseModel):
    data: list[ItemPublic]
    count: int
