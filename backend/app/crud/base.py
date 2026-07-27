from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.exceptions import NotFoundException
from app.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseCRUD(Generic[ModelType]):
    """Base class for CRUD operations on SQLAlchemy models.

    Provides common database operations that can be inherited by
    model-specific CRUD classes.

    Requirements
    ------------
    Models MUST inherit from `app.models.base.BaseModel`, which guarantees:

    - **ID field**: `id: int` (primary key, auto-increment)
    - **Timestamps**: `created_at`, `updated_at` (automatic tracking)
    - **Soft Delete**: `is_deleted: bool`, `deleted_at: datetime | None`

    These fields enable the generic `delete()` method
    to work correctly across all models.

    For Custom Models
    -----------------
    If you have a model that should NOT inherit from BaseModel:

    1. **Option A**: Inherit from BaseModel anyway (unused fields are okay)
    2. **Option B**: Create a custom CRUD class without extending BaseCRUD
    3. **Option C**: Override the `delete()` method in your model's CRUD class

    Type Parameters
    ---------------
    ModelType : BaseModel
        The SQLAlchemy model type this CRUD instance operates on.
        Must inherit from `app.models.base.BaseModel`.

    Examples
    --------
    Create a CRUD instance for your model:

    >>> from app.models.user import User
    >>> from app.crud.base import BaseCRUD
    >>>
    >>> class CRUDUser(BaseCRUD[User]):
    >>>     async def create(self, db, user_create):
    >>>         # Custom create logic here
    >>>         pass
    >>>
    >>> crud_users = CRUDUser(User)
    """

    exclude_deleted: bool = True
    """When True, automatically filters out soft-deleted records (is_deleted=False).
    Override at the class level or pass is_deleted explicitly to bypass."""

    def __init__(self, model: type[ModelType]):
        """Initialize the CRUD instance with a model.

        Parameters
        ----------
        model : type[ModelType]
            The SQLAlchemy model class to perform operations on.
        """
        self.model = model

    def _build_query(
        self,
        **kwargs: Any,
    ) -> Select[tuple[ModelType]]:
        """Build the base query with equality filters.

        If the model has soft-delete support (is_deleted field) and
        exclude_deleted is True, automatically filters out deleted records
        unless is_deleted is explicitly provided in kwargs.
        """
        query = select(self.model)
        # Auto-apply soft delete filter when not explicitly overridden by caller
        if self.exclude_deleted and hasattr(self.model, "is_deleted") and "is_deleted" not in kwargs:
            query = query.where(getattr(self.model, "is_deleted") == False)  # noqa: E712
        for field, value in kwargs.items():
            query = query.where(getattr(self.model, field) == value)
        return query

    async def get(
        self,
        db: AsyncSession,
        **kwargs: Any,
    ) -> ModelType | None:
        """Fetch a single record by any field.

        Parameters
        ----------
        db : AsyncSession
            The database session.
        **kwargs : Any
            Field-value pairs to filter by (e.g., email="user@example.com").

        Returns
        -------
        ModelType | None
            The matching record, or None if not found.

        Examples
        --------
        >>> user = await crud.get(db, username="john", is_deleted=False)
        """
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

        Examples
        --------
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
        """Fetch a page of records and the total matching count.

        Parameters
        ----------
        offset, limit
            Pagination window.
        **kwargs
            Equality filters (e.g. ``owner_id=1, is_deleted=False``).

        Returns
        -------
        (data, total)
            ``data`` is the page; ``total`` is the unpaginated count of matching rows.

        Examples
        --------
        >>> data, total = await crud.get_multi(db, offset=0, limit=10)
        """
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
        """Check if a record exists.

        Parameters
        ----------
        db : AsyncSession
            The database session.
        **kwargs : Any
            Field-value pairs to filter by.

        Returns
        -------
        bool
            True if a matching record exists, False otherwise.

        Examples
        --------
        >>> exists = await crud.exists(db, email="user@example.com")
        """
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
        """Soft delete a record (sets is_deleted=True, deleted_at=now).

        This method requires the model to inherit from BaseModel,
        which provides the soft-delete fields.

        Parameters
        ----------
        db : AsyncSession
            The database session.
        **kwargs : Any
            Field-value pairs to identify the record to delete.

        Returns
        -------
        bool
            True if a record was deleted, False if not found.

        Notes
        -----
        This is a "soft delete" - the record remains in the database
        but is marked as deleted.

        Examples
        --------
        >>> deleted = await crud.delete(db, username="john")
        >>> # User still exists in DB but is_deleted=True
        """
        record = await self.get(db, **kwargs)
        if record is None:
            return False

        record.is_deleted = True
        record.deleted_at = datetime.now(UTC)
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return True
