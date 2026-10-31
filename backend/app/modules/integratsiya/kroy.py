"""MX Kroy: buyurtma → loyiha (K1) va yagona kirish (K6) — `MES_INTEGRATSIYA.md` §4.1, §4.3.

SSO: MES RS256 bilan imzolaydi (`MX_SSO_PRIVATE_KEY`), MX ochiq kalit bilan tekshiradi (`MEBELIX_JWT_PUBLIC_KEY`).
Brauzer MX ni `?token=…#/p/{pid}` bilan ochadi — MX frontendi tokenni manzildan olib, darhol o'chiradi.
Server → server so'rovlar xizmat tokeni bilan (`sub=mes`, rol `admin`, 5 daqiqa).

HTTP — standart `urllib` (alohida oqimda): MES da yangi HTTP kutubxona yo'q, so'rovlar kam va qisqa.
"""

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Client, Order, User
from app.models.enums import UserRole
from app.modules.integratsiya.models import KroyLoyiha

#: MES roli → MX roli (`MebeliX_Kroy/backend/app/auth.py: _ROLE_ALIASES`)
MX_ROLES: dict[UserRole, list[str]] = {
    UserRole.ADMIN: ["admin"],
    UserRole.DIRECTOR: ["admin"],
    UserRole.TEXNOLOG: ["texnolog", "kroychi"],
    UserRole.MANAGER: ["ko'ruvchi"],
    UserRole.SKLADCHI: ["ko'ruvchi"],
}


class KroyXato(Exception):
    """Foydalanuvchiga ko'rsatiladigan sabab (o'zbekcha)."""


def enabled() -> bool:
    return bool(settings.MX_URL and settings.MX_SSO_PRIVATE_KEY)


def _key() -> str:
    assert settings.MX_SSO_PRIVATE_KEY is not None
    return settings.MX_SSO_PRIVATE_KEY.get_secret_value().replace("\\n", "\n")


def _token(sub: str, name: str, roles: list[str], ttl_s: int) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "name": name,
        "roles": roles,
        "iat": now,
        "exp": now + ttl_s,
        "iss": "mebelix-mes",
    }
    if settings.MX_SSO_AUDIENCE:
        claims["aud"] = settings.MX_SSO_AUDIENCE
    return jwt.encode(claims, _key(), algorithm="RS256")


def mx_roles(user: User) -> list[str]:
    if user.is_superuser:
        return ["admin"]
    return MX_ROLES.get(UserRole(user.role), [])


def sso_token(user: User) -> str:
    roles = mx_roles(user)
    if not roles:
        raise KroyXato("Bu lavozimga MX Kroy ochilmaydi.")
    return _token(user.username, user.name or user.username, roles, settings.MX_SSO_TTL_MIN * 60)


def token_login(token: str) -> str:
    """MX yuborgan foydalanuvchi tokeni (MES o'zi imzolagan SSO) → login; yaroqsiz bo'lsa `KroyXato`."""
    public = serialization.load_pem_private_key(_key().encode(), password=None).public_key()
    try:
        claims = jwt.decode(
            token,
            public,  # type: ignore[arg-type]
            algorithms=["RS256"],
            issuer="mebelix-mes",
            audience=settings.MX_SSO_AUDIENCE,
            options={"verify_aud": bool(settings.MX_SSO_AUDIENCE), "require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise KroyXato("Sessiya eskirgan: MX ni MES dagi «Kroy (MX)» tugmasi orqali qayta oching.") from e
    return str(claims["sub"])


def _request(method: str, path: str, body: Any, idempotency_key: str | None = None) -> tuple[int, Any]:
    assert settings.MX_URL is not None
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_token('mes', 'MES', ['admin'], 300)}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    req = urllib.request.Request(
        settings.MX_URL.rstrip("/") + "/api" + path,
        method=method,
        data=json.dumps(body, ensure_ascii=False, default=str).encode() if body is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 — manzil sozlamadan; paket katta bo'lishi mumkin
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError) as e:
        raise KroyXato(f"MX Kroy bilan aloqa yo'q ({type(e).__name__}).") from e


async def _mx(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    return await asyncio.to_thread(_request, method, path, body)


async def mx_get(path: str) -> tuple[int, Any]:
    return await _mx("GET", path)


async def order_body(db: AsyncSession, order: Order) -> dict[str, Any]:
    """MX `MesOrder`: sarlavha. Detallarni kroychi MX da loyiha faylidan (.project) yuklaydi."""
    client = await db.get(Client, order.client_id)
    return {
        "mes_order_ref": order.number,
        "name": order.project_name or order.number,
        "customer": client.full_name if client else "",
        "order_date": order.created_at.date().isoformat(),
        "ready_date": order.deadline.isoformat() if order.deadline else None,
        "note": (order.notes or "")[:500],
    }


async def ochish(db: AsyncSession, order: Order, user: User) -> tuple[KroyLoyiha, str]:
    """MX loyihasini (faqat bog'lanmagan bo'lsa) yaratadi va brauzer manzilini qaytaradi (`commit` — chaqiruvchida).

    Bog'langan loyiha QAYTA YUBORILMAYDI: MX `merge_order` MES dan kelgan mahsulotlar ro'yxatini MES niki deb
    biladi — detalsiz sarlavha yuborilsa kroychining MX da yuklagan detallari va CS operatsiyasi o'chib ketardi
    (brauzerda ko'rilgan, EKO 3d). Loyiha MX da o'chirilgan bo'lsa (404) — qaytadan yaratiladi."""
    if not enabled():
        raise KroyXato("MX Kroy ulanmagan (MX_URL, MX_SSO_PRIVATE_KEY).")
    token = sso_token(user)
    link = (
        await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order.id).with_for_update())
    ).scalar_one_or_none()
    if link is not None:
        code, p = await _mx("GET", f"/projects/{link.project_id}")
        if code == 200 and isinstance(p, dict):
            link.holat = int(p.get("status") or link.holat)
            public = (settings.MX_PUBLIC_URL or settings.MX_URL or "").rstrip("/")
            return link, f"{public}/?token={token}#/p/{link.project_id}"
        if code != 404:
            detail = p.get("detail") if isinstance(p, dict) else None
            raise KroyXato(f"MX Kroy loyihani bermadi ({code}): {detail or ''}".strip())
    code, p = await _mx("POST", "/mes/orders", await order_body(db, order))
    if code == 200 and isinstance(p, dict):
        if link is None:
            link = KroyLoyiha(order_id=order.id, project_id=str(p["id"]), number=str(p.get("number") or ""))
            db.add(link)
        else:
            link.project_id, link.number = str(p["id"]), str(p.get("number") or link.number)
        link.holat = int(p.get("status") or 0)
        await db.flush()
    elif code == 409 and link is not None:
        pass  # MX da tasdiqlangan — sarlavha yangilanmaydi, loyiha o'sha
    else:
        detail = p.get("detail") if isinstance(p, dict) else None
        raise KroyXato(f"MX Kroy loyihani qabul qilmadi ({code}): {detail or ''}".strip())
    public = (settings.MX_PUBLIC_URL or settings.MX_URL or "").rstrip("/")
    return link, f"{public}/?token={token}#/p/{link.project_id}"


async def holat_webhook(db: AsyncSession, body: dict[str, Any]) -> str:
    """`project.status`: loyiha holati buyurtma bog'lanishiga yoziladi (rezerv qoidasi — K2 bilan, 3c)."""
    link = (
        await db.execute(select(KroyLoyiha).where(KroyLoyiha.project_id == str(body.get("project_id") or "")))
    ).scalar_one_or_none()
    if link is None:
        return "bog'lanmagan loyiha"
    link.holat = int(body.get("status") or 0)
    await db.flush()
    return f"holat:{link.holat}"


async def qayta_ochildi_webhook(db: AsyncSession, body: dict[str, Any]) -> str:
    """`project.reopened`: MX da yuborilgan loyiha qayta ochildi — MES dagi kroy eskirgan bo'lishi mumkin."""
    link = (
        await db.execute(select(KroyLoyiha).where(KroyLoyiha.project_id == str(body.get("project_id") or "")))
    ).scalar_one_or_none()
    if link is None:
        return "bog'lanmagan loyiha"
    link.qayta_ochilgan = True
    await db.flush()
    return "qayta ochildi"
