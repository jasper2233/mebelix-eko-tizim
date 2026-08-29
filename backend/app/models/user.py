from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import UserRole, db_enum


class User(BaseModel):
    __tablename__ = "user"

    # Partial unique indexes: uniqueness only among live rows, so a soft-deleted user's
    # username/phone can be re-registered without an IntegrityError.
    __table_args__ = (
        Index("ix_user_username", "username", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_user_phone", "phone", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    # 100 — `schemas/users.py:_NAME_FIELD` va `employee.full_name` bilan bir xil
    name: Mapped[str | None] = mapped_column(String(100), default=None, kw_only=True)
    username: Mapped[str] = mapped_column(String(20), kw_only=True)
    # E.164 Uzbek mobile: '+998' + 9 digits = 13 chars total. Stored canonical, no spaces.
    phone: Mapped[str] = mapped_column(String(13), kw_only=True)
    #: TIZIM hisobi — `seed_defaults` yaratgan post hisobi. Beyjik bilan kirishda
    #: smena shu hisob nomidan ochiladi, lekin uning O'ZI hech qachon kirmaydi
    #: (paroli tasodifiy). Odamning shaxsiy hisobida `False` (`e7a35c19d840`).
    is_system: Mapped[bool] = mapped_column(default=False, server_default=text("false"), kw_only=True)
    hashed_password: Mapped[str] = mapped_column(String, kw_only=True)

    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)
    is_superuser: Mapped[bool] = mapped_column(default=False, kw_only=True)
    token_version: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)

    # TZ 3: admin/director/manager/texnolog — odamlar; terminal/tablo — ish markaziga
    # bog'langan QURILMA hisoblari (TZ 8.1, B varianti). Post rollari (arrachi..omborchi)
    # IKKI xil hisobda uchraydi: yuqoridagi `is_system` texnik hisob (faqat beyjik bilan
    # ochilgan smenani nomlaydi, `login._terminal_user`) va odamning SHAXSIY hisobi — u
    # parol bilan kiradi va `login._open_shift_for` `employee.user_id` orqali smenasini
    # ochadi. Parolni ROL emas, hisob TURI to'sadi (`login.py`: `if user.is_system`).
    role: Mapped[UserRole] = mapped_column(
        db_enum(UserRole), default=UserRole.ADMIN, server_default="admin", kw_only=True
    )
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
