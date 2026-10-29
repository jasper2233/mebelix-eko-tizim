"""MX Kroy xizmat tokeni (`KROY_API_TOKEN`): MX → MES so'rovlari foydalanuvchi nomidan emas."""

import secrets

from fastapi import HTTPException, Request

from app.core.config import settings


async def kroy_token(request: Request) -> None:
    want = settings.KROY_API_TOKEN
    if not want:
        raise HTTPException(status_code=503, detail="MX Kroy integratsiyasi sozlanmagan (KROY_API_TOKEN)")
    got = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(got.encode(), want.encode()):
        raise HTTPException(status_code=401, detail="Token noto'g'ri")
