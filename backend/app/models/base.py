from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BaseModel(Base):
    """Hamma jadvalning umumiy ustunlari: id + vaqt tamg'alari + yumshoq o'chirish."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), server_default=text("current_timestamp(0)")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        onupdate=lambda: datetime.now(UTC),
        server_default=text("current_timestamp(0)"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
