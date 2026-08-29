from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.exceptions import NotFoundException
from app.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseCRUD(Generic[ModelType]):
    """Umumiy CRUD. Hamma metodda `**kwargs` = WHERE tenglik zanjiri (field == value)."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    def _build_query(
        self,
        **kwargs: Any,
    ) -> Select[tuple[ModelType]]:
        """`is_deleted` ochiq berilmasa soft-delete filtri o'zi qo'shiladi."""
        query = select(self.model)
        if "is_deleted" not in kwargs:
            query = query.where(self.model.is_deleted == False)  # noqa: E712
        for field, value in kwargs.items():
            query = query.where(getattr(self.model, field) == value)
        return query

    async def get(
        self,
        db: AsyncSession,
        **kwargs: Any,
    ) -> ModelType | None:
        query = self._build_query(**kwargs)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_404(
        self,
        db: AsyncSession,
        detail: str,
        **kwargs: Any,
    ) -> ModelType:
        """`get()` kabi, lekin topilmasa (yoki soft-delete bo'lsa) NotFoundException.

        >>> client = await crud_clients.get_or_404(db, "Mijoz topilmadi.", id=client_id)
        """
        obj = await self.get(db, **kwargs)
        if obj is None:
            raise NotFoundException(detail)
        return obj

    async def get_multi(
        self,
        db: AsyncSession,
        offset: int = 0,
        limit: int = 100,
        **kwargs: Any,
    ) -> tuple[list[ModelType], int]:
        """(sahifa, umumiy son). `total` — paginatsiyasiz, filtrlarga mos qatorlar soni."""
        query = self._build_query(**kwargs)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Stable ordering — without it Postgres may return pages with duplicated/missing rows.
        data_query = query.order_by(self.model.id).offset(offset).limit(limit)
        rows = (await db.execute(data_query)).scalars().all()

        return list(rows), total

    async def exists(
        self,
        db: AsyncSession,
        **kwargs: Any,
    ) -> bool:
        query = self._build_query(**kwargs)

        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        count = result.scalar_one()
        return count > 0

    async def delete(
        self,
        db: AsyncSession,
        **kwargs: Any,
    ) -> bool:
        """Soft delete: is_deleted=True, deleted_at=now; topilmasa False.

        Sinfdagi yagona metod bo'lib, o'z tranzaksiyasini o'zi commit qiladi.
        """
        record = await self.get(db, **kwargs)
        if record is None:
            return False

        record.is_deleted = True
        record.deleted_at = datetime.now(UTC)
        db.add(record)
        await db.commit()
        return True
