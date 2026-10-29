from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser, SessionDep, StaffReadUser, SuperUserDep, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, ForbiddenException, NotFoundException
from app.core.security import get_password_hash, verify_password
from app.core.utils.rate_limit import rate_limiter
from app.crud import crud_machines, crud_users, log_action
from app.models.enums import UserRole
from app.models.user import User
from app.modules.platforma import service as platforma
from app.schemas.common import Message, Paginated
from app.schemas.users import IdleLimit, UpdatePassword, UserAdminUpdate, UserCreate, UserRead, UserUpdate
from app.services.activity import idle_minutes, touch_activity

router = APIRouter(prefix="/users", tags=["users"])

_NULLABLE_FIELDS = ("name", "machine_id")  # null = qiymatni olib tashlash (ish markazi bog'lamini uzish)


async def _ensure_unique(db: SessionDep, *, phone: str | None, username: str | None, current: User) -> None:
    """Reject the update when another user already owns the requested phone or username."""
    if phone is not None and phone != current.phone and await crud_users.exists(db=db, phone=phone):
        raise DuplicateValueException("Bu telefon allaqachon ro'yxatdan o'tgan")
    if username is not None and username != current.username and await crud_users.exists(db=db, username=username):
        raise DuplicateValueException("Bu foydalanuvchi nomi band")


def _derive_username_from_phone(phone: str) -> str:
    """Strip the `+` prefix to use the digits as a fallback username (e.g. `+998901234567` → `998901234567`)."""
    return phone.lstrip("+")


async def _check_machine(db: SessionDep, role: UserRole | None, machine_id: int | None) -> None:
    """Rol va ish markazi bog'lami mos kelishini tekshiradi.

    TERMINAL/TABLO hisobi KONKRET ish markazining o'zi: `resolve_terminal` postni
    aynan `user.machine_id` dan oladi, bo'lmasa skan E009 bilan rad etiladi.
    Boshqa rolda esa bog'lam ma'nosiz — odam ish markaziga biriktirilmaydi.

    Mavjud bo'lmagan `machine_id` ilgari FK xatosiga tushib, `crud` da
    "Telefon yoki foydalanuvchi nomi allaqachon band" degan ADASHTIRUVCHI xabar
    berardi (IntegrityError hammasi bir joyda tutiladi).
    """
    if role in (UserRole.TERMINAL, UserRole.TABLO):
        if machine_id is None:
            raise DuplicateValueException(f"{role} hisobi uchun ish markazi tanlanishi shart.")
        if await crud_machines.get(db, id=machine_id) is None:
            raise NotFoundException("Ish markazi topilmadi.")
    elif machine_id is not None:
        raise DuplicateValueException("Ish markazi faqat terminal va TABLO hisoblariga biriktiriladi.")


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
    await _check_machine(db, user.role, user.machine_id)

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
    # Ro'yxat BOSHQARUVGA ochiq: birlashgan "Hodimlar" sahifasi har odamning kirish
    # usulini shu ro'yxatdan biladi. YOZISH amallari (yaratish, rol berish, parol
    # tiklash, o'chirish) superuser'da qoladi — pastdagi endpointlarga qarang.
    current_user: StaffReadUser,
    db: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> Paginated[UserRead]:
    """List users with pagination (manager/texnolog/director/admin — the list exposes every phone number)."""
    rows, total = await crud_users.get_multi(db=db, offset=skip, limit=limit)
    return Paginated(data=[UserRead.model_validate(user) for user in rows], count=total)


@router.get("/me/modullar", response_model=list[str], operation_id="read_user_modullar")
async def read_user_modullar(_: CurrentUser) -> list[str]:
    """Joriy obunachi tarifidagi modullar (menyu shundan; backend baribir `require_module` bilan tekshiradi)."""
    return [m for m in platforma.MODULLAR if await platforma.module_enabled(m)]


@router.get("/me", response_model=UserRead, operation_id="read_user_me")
async def read_users_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/me/idle-limit", response_model=IdleLimit, operation_id="read_idle_limit")
async def read_idle_limit(current_user: CurrentUser, db: SessionDep) -> IdleLimit:
    """Harakatsizlik chegarasi — brauzer shundan keyin login sahifasiga qaytaradi (`useIdleLogout`)."""
    return IdleLimit(idle_minutes=await idle_minutes(db, current_user))


@router.post("/me/activity", response_model=Message, operation_id="touch_user_activity")
async def touch_user_activity(current_user: CurrentUser) -> Message:
    """Brauzerda haqiqiy harakat bo'ldi (bosish, klaviatura, shu ish markazidagi skan).

    Polling so'rovlari faollik EMAS — ochiq qolgan sahifa o'zicha so'rov yuboraveradi.
    Shu sabab faollik alohida, faqat odam harakatidan keyin yuboriladi (daqiqasiga ko'pi
    bilan bir marta). Server undan refresh'ni rad etishda va ochiq smenani yopishda foydalanadi."""
    await touch_activity(rate_limiter.client, current_user.id)
    return Message(message="OK")


@router.patch("/me", response_model=UserRead, operation_id="update_user_me")
async def update_user_me(
    values: UserUpdate,
    current_user: CurrentUser,
    db: SessionDep,
) -> UserRead:
    """Update the caller's own profile. Privilege flags are not in the schema, so escalation is impossible here."""
    await _ensure_unique(db, phone=values.phone, username=values.username, current=current_user)
    update_data = drop_forbidden_nulls(values.model_dump(exclude_unset=True), _NULLABLE_FIELDS)
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
    # Parol almashgach hamma qurilmadan chiqariladi (shu brauzer ham) — parolni
    # almashtirishning maqsadi aynan eski kirishni bekor qilish
    await crud_users.increment_token_version(db=db, user=current_user)
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
    update_data = drop_forbidden_nulls(values.model_dump(exclude_unset=True), _NULLABLE_FIELDS)
    if "role" in update_data or "machine_id" in update_data:
        await _check_machine(
            db,
            UserRole(update_data.get("role", db_user.role)),
            update_data.get("machine_id", db_user.machine_id),
        )
    # O'zini qulflab qo'yish yo'li yopiq: tiklash uchun BOSHQA superuser kerak, u esa
    # bitta bo'lgan o'rnatishda umuman yo'q — tizimga kirishning yagona yo'li yopilardi
    if user_id == current_user.id:
        if update_data.get("is_active") is False:
            raise ForbiddenException("O'z hisobingizni nofaol qila olmaysiz.")
        if update_data.get("is_superuser") is False:
            raise ForbiddenException("O'zingizdan superuser huquqini ola olmaysiz.")
    password_changed = bool(update_data.get("password"))
    updated_user = await crud_users.update(db=db, db_user=db_user, user_update=update_data)
    # Admin parolni almashtirsa egasining TIRIK sessiyalari ham uzilishi kerak:
    # aks holda o'g'irlangan cookie parol almashtirilgandan keyin ham ishlayverardi
    if password_changed:
        await crud_users.increment_token_version(db=db, user=updated_user)
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
    # Tekshiruv AVVAL: aks holda begona odam 404 va 403 farqidan qaysi id borligini bilib olardi
    if not current_user.is_superuser and user_id != current_user.id:
        raise ForbiddenException("Sizda yetarli huquq yo'q.")
    db_user = await crud_users.get_or_404(db, "Foydalanuvchi topilmadi", id=user_id)
    # Qurilma va post hisoblari ODAM EMAS: TERMINAL monoblokning o'zi, post rollari esa
    # beyjik bilan ochilgan smena qaysi hisob nomidan yozilishini hal qiladi
    # (`login._terminal_user`). O'chirilsa o'sha postda beyjik kirishi o'ladi.
    # Post hisobi = `is_system` (seed_defaults va `e7a35c19d840` migratsiyasi qo'yadi) —
    # `employees._validate_user_link` bilan bir xil qoida; nom bo'yicha tanish ishonchsiz
    # (qayta nomlangan yoki eski seed hisobi o'chib ketardi). Tsex xodimining SHAXSIY logini
    # ham post rolida bo'ladi — u odamniki, o'chirish mumkin (aks holda PersonDialog'dagi
    # «loginni olib tashlash» 403 ga urilardi).
    role = UserRole(db_user.role)
    if role in (UserRole.TERMINAL, UserRole.TABLO) or db_user.is_system:
        raise ForbiddenException(
            f"{db_user.username} — qurilma yoki post hisobi, odam emas. O'chirilsa o'sha postda "
            "beyjik bilan kirish ishlamay qoladi. Kerak bo'lsa nofaol qiling."
        )
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
