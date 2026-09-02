import asyncio
import logging

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.db import AsyncSession, local_session
from app.core.security import get_password_hash
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_first_user(session: AsyncSession) -> None:
    name = settings.ADMIN_NAME
    phone = settings.ADMIN_PHONE
    username = settings.ADMIN_USERNAME

    # Soft-delete qilingan eski admin qatori yangi seed'ni bloklamasin.
    # Telefon VA username bo'yicha qidiramiz: ADMIN_PHONE rotatsiya qilinsa ham
    # eski qatordagi username `ix_user_username` (partial unique) ni buzmasin.
    query = select(User).where(
        User.is_deleted.is_(False),
        or_(User.phone == phone, User.username == username),
    )
    result = await session.execute(query)
    user = result.scalars().first()

    if user is None:
        user = User(
            name=name,
            phone=phone,
            username=username,
            hashed_password=await get_password_hash(settings.ADMIN_PASSWORD),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        logger.info("Admin user %s created successfully.", username)
    else:
        logger.info(
            "Admin user already exists (username=%s, phone=%s), no changes needed.",
            user.username,
            user.phone,
        )


async def main() -> None:
    async with local_session() as session:
        await create_first_user(session)


if __name__ == "__main__":
    asyncio.run(main())
