from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PostCode, PostUnit


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: PostCode
    name: str
    order_index: int
    unit: PostUnit
    requires_assignment_choice: bool


class PostUpdate(BaseModel):
    """The 9-post chain is fixed (TZ 4.4); only presentation/behavior fields are editable."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=2, max_length=50)
    order_index: int | None = Field(default=None, ge=1)
    requires_assignment_choice: bool | None = None
