from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import async_get_db
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
from app.core.utils.rate_limit import RateLimit
from app.crud import crud_users
from app.schemas.auth import Token

router = APIRouter(prefix="/login", tags=["login"])

# Brute-force defence — tunable via LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_PERIOD.
_LOGIN_RATE_LIMIT = RateLimit(
    limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD
)

ACCESS_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _issue_token_pair(response: Response, username: str, token_version: int) -> str:
    """Generate access+refresh tokens and set both as httpOnly cookies. Returns the access token."""
    payload = {"sub": username, "token_version": token_version}
    access_token = create_access_token(data=payload)
    refresh_token = create_refresh_token(data=payload)
    set_auth_cookie(response, ACCESS_COOKIE_NAME, access_token, ACCESS_MAX_AGE)
    set_auth_cookie(response, REFRESH_COOKIE_NAME, refresh_token, REFRESH_MAX_AGE)
    return access_token


@router.post(
    "/access-token",
    response_model=Token,
    operation_id="login_access_token",
    dependencies=[Depends(_LOGIN_RATE_LIMIT)],
)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    user = await crud_users.authenticate(
        db=db, username_or_phone=form_data.username, password=form_data.password
    )
    if not user:
        raise UnauthorizedException("Foydalanuvchi nomi, telefon yoki parol noto'g'ri.")
    if not user.is_active:
        raise UnauthorizedException("Foydalanuvchi faol emas")

    access_token = _issue_token_pair(response, user.username, user.token_version)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", operation_id="refresh_access_token")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedException("Yangilash tokeni topilmadi.")

    token_data = verify_token(refresh_token, TokenType.REFRESH)
    if not token_data:
        raise UnauthorizedException("Yaroqsiz yangilash tokeni.")

    user = await crud_users.get_by_login(db=db, identifier=token_data.username_or_phone)
    if not user or not user.is_active or user.token_version != token_data.token_version:
        raise UnauthorizedException("Token bekor qilingan.")

    # Rotate both tokens — limits the reuse window if a refresh token is compromised.
    access_token = _issue_token_pair(response, user.username, user.token_version)
    return {"access_token": access_token, "token_type": "bearer"}
