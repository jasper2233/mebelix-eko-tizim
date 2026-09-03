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
    """The 9-post chain is fixed; only presentation/behavior fields are editable.

    `order_index` ataylab yo'q: uning yagona egasi `seed_defaults.POSTS`, u har
    prestart'da tartibni sinxronlaydi — PATCH bilan qilingan tahrir keyingi
    deploy'da jimgina yo'qolardi. `extra="ignore"` tufayli eski klient yuborsa
    e'tiborsiz qoladi.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=2, max_length=50)
    requires_assignment_choice: bool | None = None
