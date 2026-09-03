import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt
from fastapi import Response
from pydantic import SecretStr
from starlette.concurrency import run_in_threadpool

from app.schemas.auth import TokenData

from .config import EnvironmentOption, settings

SECRET_KEY: SecretStr = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


# bcrypt algoritmi 72 baytdan keyingi qismni HISOBGA OLMAYDI, bcrypt 5.0.0 esa
# uzun parolni jimgina kesmasdan `ValueError` otadi — `hashpw` ham, `checkpw` ham.
BCRYPT_MAX_BYTES = 72


def _bcrypt_bytes(password: str) -> bytes:
    """Parolni bcrypt qabul qiladigan uzunlikka keltiradi — kesish BITTA joyda.

    Sxemaga `max_length` qo'yish yetmaydi: login `OAuth2PasswordRequestForm` dan
    o'tadi, unda sxema yo'q, ya'ni uzun parol AUTENTIFIKATSIYASIZ 500 berardi.
    Bu hujum emas, oddiy holat ham: o'zbek/kirill harflari 2 bayt, 40 belgili
    parol ham chegaradan oshadi. Mavjud hash'lar ≤72 baytdan yasalgan, shuning
    uchun kesish eski parollarni buzmaydi.
    """
    return password.encode()[:BCRYPT_MAX_BYTES]


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(bcrypt.checkpw, _bcrypt_bytes(plain_password), hashed_password.encode())


async def get_password_hash(password: str) -> str:
    # bcrypt with 12 rounds takes ~250ms — must not block the event loop.
    return await run_in_threadpool(_hash_password_sync, password)


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_bytes(password), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()


def _create_token(data: dict[str, Any], token_type: TokenType, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC).replace(tzinfo=None) + expires_delta
    payload = {**data, "exp": expire, "token_type": token_type.value}
    return jwt.encode(payload, SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)


def create_access_token(data: dict[str, Any]) -> str:
    return _create_token(data, TokenType.ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict[str, Any], days: int | None = None) -> str:
    # `jti` makes every refresh token unique, so it can be marked as used after one rotation.
    payload = {**data, "jti": uuid.uuid4().hex}
    return _create_token(payload, TokenType.REFRESH, timedelta(days=days or settings.REFRESH_TOKEN_EXPIRE_DAYS))


def verify_token(token: str, expected_token_type: TokenType, *, verify_exp: bool = True) -> TokenData | None:
    """Decode JWT and return TokenData if it matches expected type, else None.

    `verify_exp=False` — faqat imzo/tur tekshiriladi, muddat emas: ochiq WS soketi
    ulanishdagi tokenni BEKOR QILINGANI (token_version, is_active) bo'yicha qayta
    tekshiradi, 30 daqiqalik access muddati bo'yicha emas.
    """
    try:
        payload = jwt.decode(
            token, SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM], options={"verify_exp": verify_exp}
        )
    except jwt.PyJWTError:
        return None

    subject = payload.get("sub")
    if subject is None or payload.get("token_type") != expected_token_type.value:
        return None

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None

    return TokenData(user_id=user_id, token_version=payload.get("token_version", 0), jti=payload.get("jti"))


def set_auth_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    """Set an httpOnly auth cookie.

    - ``secure`` is auto-disabled in local env so cookies work over plain HTTP.
    - ``samesite="strict"`` blocks the cookie from being sent on cross-site requests, which neutralises the
      classic CSRF vector for state-changing endpoints.
    """
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=settings.ENVIRONMENT != EnvironmentOption.LOCAL,
        samesite="strict",
        max_age=max_age,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE_NAME)
    response.delete_cookie(key=REFRESH_COOKIE_NAME)
