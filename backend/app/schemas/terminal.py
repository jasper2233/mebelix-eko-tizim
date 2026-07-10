from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PostCode, SessionStatus


class BadgeStart(BaseModel):
    badge_id: Annotated[str, Field(min_length=8, max_length=36)]


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: str = ""
    machine_id: int | None
    post_id: int
    status: SessionStatus
    created_at: datetime
    ended_at: datetime | None


class TerminalContext(BaseModel):
    machine_id: int
    machine_name: str
    post_id: int
    post_code: PostCode
    post_name: str
    session: SessionRead | None = None


class TaskRow(BaseModel):
    """One aggregated row in NAVBATDAGI VAZIFALAR (TZ 8.3.2)."""

    part_id: int
    order_id: int
    order_number: str
    deadline: date | None
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    qoldiq: int  # remaining scans at this post
    total: int
    edges: dict[str, Any] = {}


class ScanRequest(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]
    client_event_id: Annotated[str, Field(min_length=8, max_length=64)]  # client UUID (TZ 8.4.4)


class ScanResult(BaseModel):
    scan_id: int
    duplicate: bool = False  # idempotent replay — already counted, not an error
    qr_text: str
    part_code: str
    part_name: str
    instance_no: int
    qoldiq: int  # remaining for this part at this post after the scan
    scx_file_ids: list[int] = []  # served on EVERY scan for CNC posts (TZ 12.5)
    order_stage_completed: bool = False
    order_completed: bool = False


class ScanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_text: str = ""
    part_code: str = ""
    is_cancelled: bool
    created_at: datetime


class CutmapInstanceState(BaseModel):
    instance_id: int
    instance_no: int
    qr_text: str
    pattern_no: int | None
    cell_index: int | None
    done: bool
    label_printed_at: datetime | None


class CutmapState(BaseModel):
    """ARRA cut-map screen payload (TZ 7.1.7): the visual model + live per-cell state."""

    order_id: int
    order_number: str
    model: dict[str, Any] | None
    instances: list[CutmapInstanceState]
