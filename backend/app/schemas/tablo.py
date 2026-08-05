"""TABLO (TZ 9) javob sxemalari: buyurtma × bosqich matritsasi va drill-down."""

from datetime import date

from pydantic import BaseModel


class StageAgg(BaseModel):
    post_id: int
    done: int
    total: int
    volume_total: float  # unit amount (m² / meter / dona) per post unit
    volume_done: float


class TabloPostCol(BaseModel):
    """Matritsa ustuni — post metadatasi (frontend ustun sarlavhalari shu bilan chiziladi)."""

    id: int
    code: str
    name: str
    unit: str
    color: str | None
    order_index: int


class TabloOrderRow(BaseModel):
    id: int
    number: str
    name: str | None
    deadline: date | None
    status: str
    stages: dict[str, StageAgg]  # keyed by post code


class TabloMatrix(BaseModel):
    posts: list[TabloPostCol]
    orders: list[TabloOrderRow]


class TabloPartRow(BaseModel):
    part_id: int
    code: str
    name: str
    count: int
    stages: dict[str, StageAgg]


class TabloOrderDetail(BaseModel):
    id: int
    number: str
    name: str | None
    parts: list[TabloPartRow]
