import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateValueException
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.users import UserCreate, UserUpdate

from .base import BaseCRUD

logger = logging.getLogger(__name__)

# Verified against when the login identifier doesn't exist, so a miss costs the same
# bcrypt work as a wrong password — otherwise response timing leaks which users exist.
# Birinchi kerak bo'lganda hisoblanadi: import paytida hisoblansa `app.crud` ni import
# qiladigan HAR jarayon (web, arq worker) kirishga aloqasi
# bo'lmasa ham ~250 ms bcrypt ishini bloklab bajarardi.
_DUMMY_HASH: str | None = None


class CRUDUser(BaseCRUD[User]):
    async def _get_by_login(self, db: AsyncSession, identifier: str) -> User | None:
        """Look up a user by phone if the identifier starts with `+`, otherwise by username."""
        if identifier.startswith("+"):
            return await self.get(db, phone=identifier)
        return await self.get(db, username=identifier)

    async def _flush_unique(self, db: AsyncSession) -> None:
        """INSERT/UPDATE shu yerda ketadi — unique to'qnashuv ham shu yerda chiqadi."""
        try:
            await db.flush()
        except IntegrityError:
            # Race with a concurrent create/update — the exists() pre-check can't prevent this.
            await db.rollback()
            raise DuplicateValueException("Telefon yoki foydalanuvchi nomi allaqachon band")

    async def create(self, db: AsyncSession, user_create: UserCreate) -> User:
        """Create a new user with hashed password. Caller should pre-check phone/username uniqueness.

        Tranzaksiya route'niki: bu yerda faqat flush — commit chaqiruvchi zimmasida.
        """
        hashed_password = await get_password_hash(user_create.password)
        user_data = user_create.model_dump(exclude={"password"})
        db_user = User(**user_data, hashed_password=hashed_password)
        db.add(db_user)
        await self._flush_unique(db)
        return db_user

    async def update(
        self,
        db: AsyncSession,
        db_user: User,
        user_update: UserUpdate | dict[str, Any],
    ) -> User:
        """Update user fields. Only fields present in `user_update` are touched. Commit chaqiruvchi zimmasida."""
        if isinstance(user_update, dict):
            update_data = dict(user_update)
        else:
            update_data = user_update.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["hashed_password"] = await get_password_hash(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(db_user, field, value)

        db.add(db_user)
        await self._flush_unique(db)
        return db_user

    async def authenticate(
        self,
        db: AsyncSession,
        username_or_phone: str,
        password: str,
    ) -> User | None:
        db_user = await self._get_by_login(db, identifier=username_or_phone)
        if db_user is None:
            global _DUMMY_HASH
            if _DUMMY_HASH is None:
                _DUMMY_HASH = await get_password_hash("timing-equalizer")
            await verify_password(password, _DUMMY_HASH)
            return None
        if not await verify_password(password, db_user.hashed_password):
            logger.warning("Failed login attempt for: %s", username_or_phone)
            return None
        return db_user

    async def increment_token_version(self, db: AsyncSession, user: User) -> None:
        """Increment `token_version`, which invalidates every outstanding access/refresh token.

        Commit chaqiruvchi zimmasida — bu yerda faqat flush.
        """
        user.token_version += 1
        db.add(user)
        await db.flush()


crud_users = CRUDUser(User)
