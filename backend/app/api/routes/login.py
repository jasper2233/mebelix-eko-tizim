from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    TokenType,
    create_access_token,
    create_refresh_token,
    set_auth_cookie,
    verify_token,
)
from app.core.utils.rate_limit import RateLimit, rate_limiter
from app.crud import crud_users
from app.models.user import User
from app.schemas.auth import Token

router = APIRouter(prefix="/login", tags=["login"])

# Brute-force defence — tunable via LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_PERIOD.
_LOGIN_RATE_LIMIT = RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)

ACCESS_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

_USED_JTI_PREFIX = "auth:refresh:used:"


def _issue_token_pair(response: Response, user: User) -> str:
    """Generate access+refresh tokens and set both as httpOnly cookies. Returns the access token."""
    payload = {"sub": str(user.id), "token_version": user.token_version}
    access_token = create_access_token(data=payload)
    refresh_token = create_refresh_token(data=payload)
    set_auth_cookie(response, ACCESS_COOKIE_NAME, access_token, ACCESS_MAX_AGE)
    set_auth_cookie(response, REFRESH_COOKIE_NAME, refresh_token, REFRESH_MAX_AGE)
    return access_token


async def _is_refresh_token_used(jti: str) -> bool:
    if rate_limiter.client is None:  # No lifespan (tests/scripts) — Redis is always on in the app.
        return False
    return bool(await rate_limiter.client.exists(_USED_JTI_PREFIX + jti))


async def _mark_refresh_token_used(jti: str) -> None:
    if rate_limiter.client is None:
        return
    # Keep the tombstone exactly as long as the token could still be valid.
    await rate_limiter.client.set(_USED_JTI_PREFIX + jti, 1, ex=REFRESH_MAX_AGE)


@router.post(
    "/access-token",
    response_model=Token,
    operation_id="login_access_token",
    dependencies=[Depends(_LOGIN_RATE_LIMIT)],
)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDep,
) -> dict[str, str]:
    user = await crud_users.authenticate(db=db, username_or_phone=form_data.username, password=form_data.password)
    if not user:
        raise UnauthorizedException("Foydalanuvchi nomi, telefon yoki parol noto'g'ri.")
    if not user.is_active:
        raise UnauthorizedException("Foydalanuvchi faol emas")

    access_token = _issue_token_pair(response, user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", operation_id="refresh_access_token")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: SessionDep,
) -> dict[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedException("Yangilash tokeni topilmadi.")

    token_data = verify_token(refresh_token, TokenType.REFRESH)
    if not token_data:
        raise UnauthorizedException("Yaroqsiz yangilash tokeni.")

    # One-time use: a replayed refresh token means the cookie was stolen or the client is broken —
    # either way the whole session is revoked by bumping token_version.
    if token_data.jti and await _is_refresh_token_used(token_data.jti):
        user = await crud_users.get(db=db, id=token_data.user_id)
        if user is not None:
            await crud_users.increment_token_version(db=db, user=user)
            await db.commit()  # revoke pastdagi raise'dan oldin saqlansin — aks holda rollback bo'lardi
        raise UnauthorizedException("Token bekor qilingan.")

    user = await crud_users.get(db=db, id=token_data.user_id)
    if not user or not user.is_active or user.token_version != token_data.token_version:
        raise UnauthorizedException("Token bekor qilingan.")

    if token_data.jti:
        await _mark_refresh_token_used(token_data.jti)
    access_token = _issue_token_pair(response, user)
    return {"access_token": access_token, "token_type": "bearer"}
