from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import ACCESS_COOKIE_NAME, TokenType, verify_token
from app.crud import crud_users
from app.models.enums import UserRole
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(async_get_db)]

# auto_error=False so a missing Bearer header doesn't 401 — the cookie is tried as a fallback.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token", auto_error=False)


def client_ip(request: Request) -> str | None:
    """log_action uchun mijoz IP. X-Forwarded-For allaqachon `ProxyHeadersMiddleware`
    orqali qo'llanadi (`core/setup.py`) — bu funksiya faqat `request.client` ni o'qiydi."""
    return request.client.host if request.client else None


async def resolve_user(db: AsyncSession, token: str, *, verify_exp: bool = True) -> User | None:
    """Token -> User, sessiya hali amal qilsa. token_version bump = global revoke."""
    token_data = verify_token(token, TokenType.ACCESS, verify_exp=verify_exp)
    if token_data is None:
        return None
    user = await crud_users.get(db=db, id=token_data.user_id)
    if user is None or not user.is_active or user.token_version != token_data.token_version:
        return None
    return user


async def get_current_user(
    request: Request,
    db: SessionDep,
    bearer_token: Annotated[str | None, Depends(_oauth2_scheme)] = None,
) -> User:
    # Avval Authorization header, keyin httpOnly access cookie.
    token = bearer_token or request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise UnauthorizedException("Tizimga kirilmagan.")

    user = await resolve_user(db, token)
    if user is None:
        raise UnauthorizedException("Tizimga kirilmagan.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise ForbiddenException("Sizda yetarli huquq yo'q.")
    return current_user


SuperUserDep = Annotated[User, Depends(get_current_superuser)]


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory: allow only the given roles. ADMIN role and superusers always pass."""

    async def checker(current_user: CurrentUser) -> User:
        if current_user.is_superuser or current_user.role == UserRole.ADMIN or current_user.role in roles:
            return current_user
        raise ForbiddenException("Sizda yetarli huquq yo'q.")

    return checker


# Common role groups (TZ 3.7 role/module matrix)
ManagerUser = Annotated[User, Depends(require_roles(UserRole.MANAGER))]
TexnologUser = Annotated[User, Depends(require_roles(UserRole.TEXNOLOG))]
#: Ish markazi biriktirish (`orders/{id}/machines`) va ishlab chiqarishga uzatish
#: (`orders/{id}/start`). TZ 6.4.2 da bu faqat menejer
#: amali edi; egasining qaroriga ko'ra texnologga ham ochildi — faylni u yuklaydi,
#: marshrutni u chizadi, ya'ni buyurtma tayyorligini birinchi bo'lib u biladi.
ManagerOrTexnologUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.TEXNOLOG))]
StaffReadUser = Annotated[
    User, Depends(require_roles(UserRole.MANAGER, UserRole.TEXNOLOG, UserRole.DIRECTOR))
]  # read-only lists shared by office roles
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
