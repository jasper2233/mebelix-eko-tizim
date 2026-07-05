from datetime import datetime

from pydantic import BaseModel


class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None
