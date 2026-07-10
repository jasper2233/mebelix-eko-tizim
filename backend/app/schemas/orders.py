from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FileKind, OrderPriority, OrderStatus, PostCode, ProjectGeneration, RouteSource


class OrderRead(BaseModel):
    """Registry row (TZ 10.3.1)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    status: OrderStatus
    priority: OrderPriority
    client_id: int
    client_name: str = ""  # joined in the route
    deadline: date | None
    amount: Decimal | None
    notes: str | None
    project_name: str | None
    project_generation: ProjectGeneration | None
    created_at: datetime
    production_started_at: datetime | None
    completed_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None


class OrderFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: FileKind
    filename: str
    size: int | None
    part_id: int | None
    created_at: datetime


class OrderDetail(OrderRead):
    """Order card (TZ 10.3.3): metadata + files; the parts matrix comes from /matrix."""

    machine_assignments: dict[str, int]
    project_uuid: str | None
    project_loaded_at: datetime | None
    files: list[OrderFileRead] = []
    parts_count: int = 0
    instances_count: int = 0


class OrderCreate(BaseModel):
    """Manager creates a DRAFT order (TZ 6.2). The number is auto-generated (B-2026-001)."""

    model_config = ConfigDict(extra="ignore")

    client_id: int
    deadline: date | None = None
    priority: OrderPriority = OrderPriority.MEDIUM
    amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_id: int | None = None
    deadline: date | None = None
    priority: OrderPriority | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderCancel(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=500)]


class MachineAssignments(BaseModel):
    """Manager's machine choice per post before production start (TZ 6.4)."""

    assignments: dict[PostCode, int]


class RouteCell(BaseModel):
    """One matrix cell: part × post (TZ 6.3.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    source: RouteSource
    is_enabled: bool
    per_instance: int
    total_required: int
    total_done: int
    machine_id: int | None


class MatrixPart(BaseModel):
    """One matrix row: part with its route cells."""

    id: int
    product_code: str
    code: str
    name: str
    count: int
    length: float | None
    width: float | None
    thickness: float | None
    label_num: int | None
    edges: dict[str, Any]
    xnc_summary: dict[str, Any]
    note: str | None
    routes: list[RouteCell]


class OrderMatrix(BaseModel):
    order_id: int
    parts: list[MatrixPart]


class MatrixPartEdit(BaseModel):
    """Texnolog edits one part's row (TZ 6.3.3): toggle stages, note, rare count fix."""

    part_id: int
    note: str | None = None
    count: int | None = Field(default=None, ge=1, le=1000)
    # post_id -> enabled; STOLYARKA toggling and disabling auto-detected stages
    stages: dict[int, bool] = {}


class MatrixEdit(BaseModel):
    edits: list[MatrixPartEdit]
