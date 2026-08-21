from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import PostCode, PostUnit, db_enum


class Post(BaseModel):
    """Production stage (TZ 4.4): ARRA, KROMKA, OVAL, PRISADKA, ROVER, STOLYARKA, BOYOQ."""

    __tablename__ = "post"

    __table_args__ = (Index("ix_post_code", "code", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    code: Mapped[PostCode] = mapped_column(db_enum(PostCode), kw_only=True)
    name: Mapped[str] = mapped_column(String(50), kw_only=True)
    order_index: Mapped[int] = mapped_column(kw_only=True)
    unit: Mapped[PostUnit] = mapped_column(db_enum(PostUnit), kw_only=True)
    # requires_qr_print/auto_skip_if_empty olib tashlandi: hech qayerda o'qilmasdi —
    # ARRA chek-oqimi post.code bilan aniqlanadi (e8b1... keyingi migratsiyada drop)
    requires_assignment_choice: Mapped[bool] = mapped_column(default=False, kw_only=True)
