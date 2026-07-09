from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, SuperUserDep
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, ForbiddenException, NotFoundException
from app.core.security import get_password_hash, verify_password
from app.crud import crud_users
from app.models.user import User
from app.schemas.users import UpdatePassword, UserAdminUpdate, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


class PaginatedResponse(BaseModel):
    data: list[UserRead]
    count: int


async def _ensure_unique(db: SessionDep, *, phone: str | None, username: str | None, current: User) -> None:
    """Reject the update when another user already owns the requested phone or username."""
    if phone is not None and phone != current.phone and await crud_users.exists(db=db, phone=phone):
        raise DuplicateValueException("Bu telefon allaqachon ro'yxatdan o'tgan")
    if username is not None and username != current.username and await crud_users.exists(db=db, username=username):
        raise DuplicateValueException("Bu foydalanuvchi nomi band")


def _derive_username_from_phone(phone: str) -> str:
    """Strip the `+` prefix to use the digits as a fallback username (e.g. `+998901234567` → `998901234567`)."""
    return phone.lstrip("+")


def _drop_forbidden_nulls(update_data: dict) -> dict:
    """PATCH bodies may carry explicit `null`s; only `name` is genuinely nullable — the rest would
    hit NOT NULL columns and 500."""
    return {k: v for k, v in update_data.items() if v is not None or k == "name"}


@router.post("/", response_model=UserRead, status_code=201, operation_id="create_user")
async def write_user(
    user: UserCreate,
    current_user: SuperUserDep,
    db: SessionDep,
) -> UserRead:
    """Create a new user (superuser only). If `username` is omitted, derive one from the phone digits."""
    if await crud_users.exists(db=db, phone=user.phone):
        raise DuplicateValueException("Bu telefon allaqachon ro'yxatdan o'tgan")

    if user.username:
        if await crud_users.exists(db=db, username=user.username):
            raise DuplicateValueException("Bu foydalanuvchi nomi band")
    else:
        base_username = _derive_username_from_phone(user.phone)
        username = base_username
        counter = 1
        while await crud_users.exists(db=db, username=username):
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username

    created_user = await crud_users.create(db=db, user_create=user)
    return UserRead.model_validate(created_user)


@router.get("/", response_model=PaginatedResponse, operation_id="read_users")
async def read_users(
    current_user: SuperUserDep,
    db: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
) -> PaginatedResponse:
    """List users with pagination (superuser only — the list exposes every phone number)."""
    rows, total = await crud_users.get_multi(db=db, offset=skip, limit=limit)
    return PaginatedResponse(
        data=[UserRead.model_validate(user) for user in rows],
        count=total,
    )


@router.get("/me", response_model=UserRead, operation_id="read_user_me")
async def read_users_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, operation_id="update_user_me")
async def update_user_me(
    values: UserUpdate,
    current_user: CurrentUser,
    db: SessionDep,
) -> UserRead:
    """Update the caller's own profile. Privilege flags are not in the schema, so escalation is impossible here."""
    await _ensure_unique(db, phone=values.phone, username=values.username, current=current_user)
    update_data = _drop_forbidden_nulls(values.model_dump(exclude_unset=True))
    updated_user = await crud_users.update(db=db, db_user=current_user, user_update=update_data)
    return UserRead.model_validate(updated_user)


@router.patch("/me/password", response_model=dict[str, str], operation_id="update_password_me")
async def update_password_me(
    body: UpdatePassword,
    current_user: CurrentUser,
    db: SessionDep,
) -> dict[str, str]:
    if not await verify_password(body.current_password, current_user.hashed_password):
        raise ForbiddenException("Joriy parol noto'g'ri")
    if body.current_password == body.new_password:
        raise DuplicateValueException("Yangi parol joriy paroldan farq qilishi kerak")

    await crud_users.update(
        db=db, db_user=current_user, user_update={"hashed_password": await get_password_hash(body.new_password)}
    )
    return {"message": "Parol muvaffaqiyatli yangilandi"}


@router.delete("/me", response_model=dict[str, str], operation_id="delete_user_me")
async def delete_user_me(current_user: CurrentUser, db: SessionDep) -> dict[str, str]:
    if current_user.is_superuser:
        raise ForbiddenException(
            "Adminlar o'z hisobini o'zlari o'chira olmaydilar. Iltimos, boshqa adminga murojaat qiling."
        )
    await crud_users.delete(db=db, id=current_user.id)
    return {"message": "Foydalanuvchi muvaffaqiyatli o'chirildi"}


@router.get("/{user_id}", response_model=UserRead, operation_id="read_user_by_id")
async def read_user_by_id(user_id: int, current_user: CurrentUser, db: SessionDep) -> UserRead:
    """Read a user by id — only the user themselves or a superuser (phone numbers are private)."""
    if not current_user.is_superuser and user_id != current_user.id:
        raise ForbiddenException("Sizda yetarli huquq yo'q.")
    db_user = await crud_users.get(db=db, id=user_id)
    if db_user is None:
        raise NotFoundException("Foydalanuvchi topilmadi")
    return UserRead.model_validate(db_user)


@router.patch("/{user_id}", response_model=UserRead, operation_id="update_user")
async def patch_user(
    values: UserAdminUpdate,
    user_id: int,
    current_user: SuperUserDep,
    db: SessionDep,
) -> UserRead:
    """Update any user (superuser only). Self-updates should go through `PATCH /users/me`."""
    db_user = await crud_users.get(db=db, id=user_id)
    if db_user is None:
        raise NotFoundException("Foydalanuvchi topilmadi")

    await _ensure_unique(db, phone=values.phone, username=values.username, current=db_user)
    update_data = _drop_forbidden_nulls(values.model_dump(exclude_unset=True))
    updated_user = await crud_users.update(db=db, db_user=db_user, user_update=update_data)
    return UserRead.model_validate(updated_user)


@router.delete("/{user_id}", operation_id="delete_user")
async def erase_user(
    user_id: int,
    current_user: CurrentUser,
    db: SessionDep,
) -> dict[str, str]:
    """Soft-delete a user. Allowed for the user themselves or any superuser."""
    db_user = await crud_users.get(db=db, id=user_id)
    if not db_user:
        raise NotFoundException("Foydalanuvchi topilmadi")
    if not current_user.is_superuser and user_id != current_user.id:
        raise ForbiddenException()
    if current_user.is_superuser and user_id == current_user.id:
        raise ForbiddenException(
            "Adminlar o'z hisobini o'zlari o'chira olmaydilar. Iltimos, boshqa adminga murojaat qiling."
        )

    await crud_users.delete(db=db, id=user_id)
    return {"message": "Foydalanuvchi o'chirildi"}
