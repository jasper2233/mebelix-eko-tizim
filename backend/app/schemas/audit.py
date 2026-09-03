from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    employee_id: int | None
    module: str
    action: str
    entity_type: str | None
    entity_id: int | None
    message: str | None
    meta: dict[str, Any]
    ip: str | None
    created_at: datetime
    # Loglar sahifasi "kim" ustuni — alohida so'rovsiz
    user_name: str | None = None
    employee_name: str | None = None


class AuditSummaryRow(BaseModel):
    """Loglar sahifasi tab'lari: modul × amal bo'yicha yozuvlar soni (sana filtri bilan)."""

    module: str
    action: str
    count: int
