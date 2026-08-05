from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser, SessionDep, SuperUserDep, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, ForbiddenException
from app.core.security import get_password_hash, verify_password
from app.crud import crud_users, log_action
from app.models.user import User
from app.schemas.common import Message, Paginated
from app.schemas.users import UpdatePassword, UserAdminUpdate, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


async def _ensure_unique(db: SessionDep, *, phone: str | None, username: str | None, current: User) -> None:
    """Reject the update when another user already owns the requested phone or username."""
    if phone is not None and phone != current.phone and await crud_users.exists(db=db, phone=phone):
        raise DuplicateValueException("Bu telefon allaqachon ro'yxatdan o'tgan")
    if username is not None and username != current.username and await crud_users.exists(db=db, username=username):
        raise DuplicateValueException("Bu foydalanuvchi nomi band")


def _derive_username_from_phone(phone: str) -> str:
    """Strip the `+` prefix to use the digits as a fallback username (e.g. `+998901234567` → `998901234567`)."""
    return phone.lstrip("+")


_NULLABLE_FIELDS = ("name", "machine_id")  # null = qiymatni olib tashlash (stanok bog'lamini uzish)


def _drop_forbidden_nulls(update_data: dict) -> dict:
    """PATCH bodies may carry explicit `null`s; faqat haqiqatan nullable ustunlar
    null qabul qiladi — qolganlari NOT NULL ustunga tushib 500 berardi."""
    return {k: v for k, v in update_data.items() if v is not None or k in _NULLABLE_FIELDS}


@router.post("/", response_model=UserRead, status_code=201, operation_id="create_user")
async def create_user(
    user: UserCreate,
    current_user: SuperUserDep,
    db: SessionDep,
    request: Request,
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
    log_action(
        db,
        module="users",
        action="created",
        user_id=current_user.id,
        entity_type="user",
        entity_id=created_user.id,
        message=f"Foydalanuvchi yaratildi: {created_user.username}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(created_user)
    return UserRead.model_validate(created_user)


@router.get("/", response_model=Paginated[UserRead], operation_id="read_users")
async def read_users(
    current_user: SuperUserDep,
    db: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> Paginated[UserRead]:
    """List users with pagination (superuser only — the list exposes every phone number)."""
    rows, total = await crud_users.get_multi(db=db, offset=skip, limit=limit)
    return Paginated(data=[UserRead.model_validate(user) for user in rows], count=total)


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
    await db.commit()
    await db.refresh(updated_user)
    return UserRead.model_validate(updated_user)


@router.patch("/me/password", response_model=Message, operation_id="update_password_me")
async def update_password_me(
    body: UpdatePassword,
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
) -> Message:
    if not await verify_password(body.current_password, current_user.hashed_password):
        raise ForbiddenException("Joriy parol noto'g'ri")
    if body.current_password == body.new_password:
        raise DuplicateValueException("Yangi parol joriy paroldan farq qilishi kerak")

    await crud_users.update(
        db=db, db_user=current_user, user_update={"hashed_password": await get_password_hash(body.new_password)}
    )
    log_action(
        db,
        module="users",
        action="updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        message="Parol o'zgartirildi",  # parol materiali loglanmaydi
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Parol muvaffaqiyatli yangilandi")


@router.delete("/me", response_model=Message, operation_id="delete_user_me")
async def delete_user_me(current_user: CurrentUser, db: SessionDep, request: Request) -> Message:
    """delete_user'ning o'z-o'ziga qisqartmasi — qoidalar bitta joyda tursin."""
    return await delete_user(current_user.id, current_user, db, request)


@router.get("/{user_id}", response_model=UserRead, operation_id="read_user_by_id")
async def read_user_by_id(user_id: int, current_user: CurrentUser, db: SessionDep) -> UserRead:
    """Read a user by id — only the user themselves or a superuser (phone numbers are private)."""
    if not current_user.is_superuser and user_id != current_user.id:
        raise ForbiddenException("Sizda yetarli huquq yo'q.")
    db_user = await crud_users.get_or_404(db, "Foydalanuvchi topilmadi", id=user_id)
    return UserRead.model_validate(db_user)


@router.patch("/{user_id}", response_model=UserRead, operation_id="update_user")
async def update_user(
    values: UserAdminUpdate,
    user_id: int,
    current_user: SuperUserDep,
    db: SessionDep,
    request: Request,
) -> UserRead:
    """Update any user (superuser only). Self-updates should go through `PATCH /users/me`."""
    db_user = await crud_users.get_or_404(db, "Foydalanuvchi topilmadi", id=user_id)

    await _ensure_unique(db, phone=values.phone, username=values.username, current=db_user)
    update_data = _drop_forbidden_nulls(values.model_dump(exclude_unset=True))
    updated_user = await crud_users.update(db=db, db_user=db_user, user_update=update_data)
    log_action(
        db,
        module="users",
        action="updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=db_user.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(updated_user)
    return UserRead.model_validate(updated_user)


@router.delete("/{user_id}", response_model=Message, operation_id="delete_user")
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
) -> Message:
    """Soft-delete a user. Allowed for the user themselves or any superuser."""
    db_user = await crud_users.get_or_404(db, "Foydalanuvchi topilmadi", id=user_id)
    if not current_user.is_superuser and user_id != current_user.id:
        raise ForbiddenException()
    if current_user.is_superuser and user_id == current_user.id:
        raise ForbiddenException(
            "Adminlar o'z hisobini o'zlari o'chira olmaydilar. Iltimos, boshqa adminga murojaat qiling."
        )

    log_action(
        db,
        module="users",
        action="deleted",
        user_id=current_user.id,
        entity_type="user",
        entity_id=db_user.id,
        message=f"Foydalanuvchi o'chirildi: {db_user.username}",
        ip=client_ip(request),
    )
    await crud_users.delete(db=db, id=user_id)  # BaseCRUD.delete o'zi commit qiladi — audit ham shu bilan saqlanadi
    return Message(message="Foydalanuvchi o'chirildi")
