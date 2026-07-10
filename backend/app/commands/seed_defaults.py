"""Idempotent bootstrap: default organization and the 6 production posts (TZ 4.4).

Run: python -m app.commands.seed_defaults (called from prestart/setup scripts).
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.db import local_session
from app.models import Organization, Post
from app.models.enums import PostCode, PostUnit

logger = logging.getLogger(__name__)

POSTS: list[dict[str, object]] = [
    {
        "code": PostCode.ARRA,
        "name": "Arra",
        "order_index": 1,
        "unit": PostUnit.M2,
        "requires_qr_print": True,
        "color": "#c2410c",
        "icon": "saw",
    },
    {
        "code": PostCode.KROMKA,
        "name": "Kromka",
        "order_index": 2,
        "unit": PostUnit.METER,
        "color": "#0e7490",
        "icon": "band",
    },
    {
        "code": PostCode.PRISADKA,
        "name": "Prisadka",
        "order_index": 3,
        "unit": PostUnit.PIECE,
        "color": "#7c3aed",
        "icon": "drill",
    },
    {
        "code": PostCode.PAZ,
        "name": "Paz",
        "order_index": 4,
        "unit": PostUnit.METER,
        "requires_assignment_choice": True,
        "color": "#b45309",
        "icon": "groove",
    },
    {
        "code": PostCode.ROVER,
        "name": "Rover",
        "order_index": 5,
        "unit": PostUnit.PIECE,
        "requires_assignment_choice": True,
        "color": "#be185d",
        "icon": "mill",
    },
    {
        "code": PostCode.STOLYARKA,
        "name": "Stolyarka",
        "order_index": 6,
        "unit": PostUnit.PIECE,
        "color": "#15803d",
        "icon": "assembly",
    },
]


async def seed_defaults() -> None:
    async with local_session() as db:
        org = (await db.execute(select(Organization).limit(1))).scalar_one_or_none()
        if org is None:
            db.add(Organization(name="Mebelix"))
            logger.info("Default organization created")

        existing = {p.code for p in (await db.execute(select(Post))).scalars()}
        for data in POSTS:
            if data["code"] not in existing:
                db.add(Post(**data))  # type: ignore[arg-type]
                logger.info("Post %s created", data["code"])

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_defaults())
