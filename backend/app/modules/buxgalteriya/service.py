"""buxgalteriya moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.buxgalteriya import services


async def sinxron(db: AsyncSession) -> services.Sinxron:
    """Avtomatik provodkalarni manba jurnallariga moslaydi (fon ishi va hisobotdan oldin)."""
    return await services.sinxron(db)


async def nazorat(db: AsyncSession) -> list[services.Nazorat]:
    """Buxgalteriya schyotlari ↔ kassa, ombor, Moliya (farq bo'lsa — biror operatsiya tushmagan)."""
    return await services.nazorat(db)
