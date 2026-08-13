from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip
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
    verify_password,
    verify_token,
)
from app.core.utils.rate_limit import RateLimit, rate_limiter
from app.core.ws import ws_manager
from app.crud import crud_users, log_action
from app.models import Employee, Machine, Post
from app.models.enums import POST_ROLES, EmployeeStatus, UserRole
from app.models.user import User
from app.schemas.auth import (
    BadgeLoginRequest,
    BadgeLoginResponse,
    BadgePostOption,
    PinEmployee,
    PinLoginRequest,
    Token,
)
from app.services.scanning import open_badge_session

router = APIRouter(prefix="/login", tags=["login"])

# Brute-force defence — tunable via LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_PERIOD.
_LOGIN_RATE_LIMIT = RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)
# Beyjikda chegara kengroq: parolni topish mumkin, 122-bitli UUID'ni esa yo'q.
# Tor chegara esa zarar qilardi — smena almashuvida ketma-ket skanlar butun tsexni
# (bitta tashqi IP) qulflab qo'yardi.
_BADGE_RATE_LIMIT = RateLimit(limit=30, period=60)

ACCESS_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

_USED_JTI_PREFIX = "auth:refresh:used:"

# PIN 4-6 raqam, ya'ni beyjikning 122 bitiga nisbatan zaif. Chegara Redis'da
# HODIM bo'yicha sanaladi (IP bo'yicha emas): butun tsex bitta tashqi IP ostida
# turadi, ya'ni IP chegarasi yonidagi odamning to'g'ri kodini ham bloklardi.
_PIN_FAIL_PREFIX = "auth:pin:fail:"
_PIN_MAX_FAILURES = 5
_PIN_LOCK_MINUTES = 5


async def _pin_locked(employee_id: int) -> bool:
    if rate_limiter.client is None:
        return False
    fails = await rate_limiter.client.get(_PIN_FAIL_PREFIX + str(employee_id))
    return int(fails or 0) >= _PIN_MAX_FAILURES


async def _register_pin_failure(employee_id: int) -> int:
    """Xato urinishni sanaydi, qolgan urinishlar sonini qaytaradi."""
    if rate_limiter.client is None:
        return _PIN_MAX_FAILURES
    key = _PIN_FAIL_PREFIX + str(employee_id)
    fails = await rate_limiter.client.incr(key)
    # Muddat HAR xatoda yangilanadi: sekin terib chiqishga urinsa oyna surilib boradi.
    await rate_limiter.client.expire(key, _PIN_LOCK_MINUTES * 60)
    return max(0, _PIN_MAX_FAILURES - int(fails))


async def _clear_pin_failures(employee_id: int) -> None:
    if rate_limiter.client is not None:
        await rate_limiter.client.delete(_PIN_FAIL_PREFIX + str(employee_id))


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
    # Tsexda kirish yo'li BITTA — beyjik. Har postda bitta operator hisobi bor,
    # ya'ni parol butun smenaga ma'lum: u bilan kirilsa smena "arrachi" mirror
    # hodimiga ochilib, skan va ish haqi haqiqiy odamga emas, o'shanga yozilardi.
    # Ustiga u istalgan joydan ishlardi — tsexdan tashqarida ham skan qilinardi.
    if POST_ROLES.get(UserRole(user.role)) is not None:
        raise UnauthorizedException("Tsexda beyjik bilan kiriladi.")

    access_token = _issue_token_pair(response, user)
    return {"access_token": access_token, "token_type": "bearer"}


async def _badge_post(db: SessionDep, employee: Employee, post_id: int | None) -> Post:
    """Beyjik egasi qaysi postda ishlaydi.

    Post BEYJIKDAN chiqadi: hodim biriktirilgan postlar ro'yxati bitta bo'lsa
    tanlash so'ralmaydi, bir nechtasi bo'lsa monoblok tanlash oynasini ko'rsatadi
    (409 + ro'yxat).
    """
    posts = list(
        (
            await db.execute(
                select(Post)
                .where(
                    Post.id.in_(employee.assigned_post_ids or []),
                    Post.is_deleted == False,  # noqa: E712
                )
                .order_by(Post.order_index)
            )
        )
        .scalars()
        .all()
    )
    if not posts:
        raise UnauthorizedException(f"{employee.full_name} biror postga biriktirilmagan. Adminga murojaat qiling.")
    if post_id is not None:
        chosen = next((p for p in posts if p.id == post_id), None)
        if chosen is None:
            raise UnauthorizedException(f"{employee.full_name} bu postda ishlay olmaydi.")
        return chosen
    if len(posts) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POST_CHOICE",
                "employee_name": employee.full_name,
                "posts": [BadgePostOption(id=p.id, code=p.code, name=p.name).model_dump() for p in posts],
            },
        )
    return posts[0]


async def _post_machine(db: SessionDep, post: Post) -> Machine:
    """Postning stanogi. Bir nechta bo'lsa birinchisi — `resolve_terminal` ham
    operator rolida aynan shunday tanlaydi, ya'ni ikkalasi bir xil javob beradi."""
    machine = (
        await db.execute(
            select(Machine)
            .where(
                Machine.post_id == post.id,
                Machine.is_deleted == False,  # noqa: E712
            )
            .order_by(Machine.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if machine is None:
        raise UnauthorizedException(f"{post.name} postida stanok yo'q. Admin stanok qo'shishi kerak.")
    return machine


async def _terminal_user(db: SessionDep, machine: Machine, post: Post) -> User:
    """Kirish qaysi hisob nomidan yoziladi.

    Ikki manba, shu tartibda: shu stanokka biriktirilgan TERMINAL hisobi, bo'lmasa
    post rolidagi hisob. Ikkalasi ham `resolve_terminal` bilan BIR XIL postga
    olib keladi (biri stanok orqali, ikkinchisi rol orqali) — aks holda operator
    boshqa postning ekranida paydo bo'lardi.

    Hisob hech qaysi hodimni bildirmaydi — KIM ishlayotgani beyjik ochgan smenada.
    """
    user = (
        await db.execute(
            select(User)
            .where(
                User.role == UserRole.TERMINAL,
                User.machine_id == machine.id,
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
            .order_by(User.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if user is not None:
        return user

    post_role = next((r for r, code in POST_ROLES.items() if code == post.code), None)
    if post_role is not None:
        user = (
            await db.execute(
                select(User)
                .where(
                    User.role == post_role,
                    User.is_active == True,  # noqa: E712
                    User.is_deleted == False,  # noqa: E712
                )
                .order_by(User.id)
                .limit(1)
            )
        ).scalar_one_or_none()
    if user is None:
        raise UnauthorizedException(f"{post.name} uchun terminal hisobi yo'q. Admin hisob yaratishi kerak.")
    return user


async def _open_shift(
    db: SessionDep,
    response: Response,
    request: Request,
    *,
    employee: Employee,
    post_id: int | None,
    how: str,
) -> BadgeLoginResponse:
    """Kimlik aniqlangandan keyingi umumiy qism — beyjik va PIN uchun BIR XIL.

    Kirish usuli faqat "kim" degan savolga javob beradi; undan keyin smena, audit
    va token har ikkalasida aynan bir yo'ldan o'tadi, ya'ni skan va ish haqi
    atributsiyasi usulga bog'liq emas.
    """
    post = await _badge_post(db, employee, post_id)
    machine = await _post_machine(db, post)
    user = await _terminal_user(db, machine, post)

    session = await open_badge_session(db, user=user, machine=machine, post=post, employee=employee)
    log_action(
        db,
        module="sessions",
        action="started",
        user_id=user.id,
        employee_id=employee.id,
        entity_type="session",
        entity_id=session.id,
        message=f"{how} bilan kirish: {employee.full_name} — {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await ws_manager.publish(
        "session.started",
        {"session_id": session.id, "employee": employee.full_name, "machine_id": machine.id, "post_id": post.id},
    )
    access_token = _issue_token_pair(response, user)
    return BadgeLoginResponse(
        access_token=access_token,
        token_type="bearer",
        employee_name=employee.full_name,
        machine_name=machine.name,
        post_name=post.name,
    )


@router.post(
    "/badge",
    response_model=BadgeLoginResponse,
    operation_id="login_with_badge",
    dependencies=[Depends(_BADGE_RATE_LIMIT)],
)
async def login_with_badge(
    response: Response, db: SessionDep, body: BadgeLoginRequest, request: Request
) -> BadgeLoginResponse:
    """Tsexdagi kirish: beyjik skani, parolsiz.

    Beyjik ham KIMLIGINI, ham QAYERDA ishlashini aytadi: post hodimning
    biriktirilgan postlaridan chiqadi (bir nechtasi bo'lsa 409 + tanlash ro'yxati).

    XAVFSIZLIK: beyjik yagona omil, ya'ni QR qog'ozdan nusxa olingan bo'lsa
    istalgan qurilmadan kirsa bo'ladi. Bu ataylab tanlangan (2026-08-12): tsexda
    parol terish smena almashuvini sekinlashtiradi va amalda umumiy akkauntga
    olib keladi. Buning o'rniga hisob imtiyozi tor (terminal ekranlari, admin
    paneli emas) va har kirish audit logga tushadi.
    """
    employee = (
        await db.execute(
            select(Employee).where(
                Employee.badge_id == body.badge_id.strip(),
                Employee.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if employee is None:
        raise UnauthorizedException("Beyjik topilmadi.")
    if employee.status != EmployeeStatus.ACTIVE:
        raise UnauthorizedException("Beyjik nofaol. Adminga murojaat qiling.")

    # Postga biriktirilganini `_badge_post` tekshiradi (terminaldagi `badge_employee`
    # bilan bir xil qoida, faqat u yerda post ma'lum, bu yerda esa aniqlanadi).
    return await _open_shift(db, response, request, employee=employee, post_id=body.post_id, how="Beyjik")


@router.get("/pin/employees", response_model=list[PinEmployee], operation_id="list_pin_employees")
async def list_pin_employees(db: SessionDep) -> list[Employee]:
    """Monoblokdagi tanlov ro'yxati — PIN o'rnatilgan faol hodimlar.

    Autentifikatsiyasiz: kirish sahifasi bu ro'yxatni kirishdan OLDIN ko'rsatishi
    kerak. Chiqadigan ma'lumot ism va lavozim bilan cheklangan — kirish uchun
    PIN'ning o'zi kerak. Ro'yxat qisqa: PIN faqat skaneri yo'q postdagilarga
    qo'yiladi, qolganlar beyjik bilan kiradi va bu yerda umuman ko'rinmaydi.
    """
    return list(
        (
            await db.execute(
                select(Employee)
                .where(
                    Employee.pin_hash.is_not(None),
                    Employee.status == EmployeeStatus.ACTIVE,
                    Employee.is_deleted == False,  # noqa: E712
                )
                .order_by(Employee.full_name)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/pin",
    response_model=BadgeLoginResponse,
    operation_id="login_with_pin",
    dependencies=[Depends(_BADGE_RATE_LIMIT)],
)
async def login_with_pin(
    response: Response, db: SessionDep, body: PinLoginRequest, request: Request
) -> BadgeLoginResponse:
    """Skaneri yo'q postda kirish: ism + shaxsiy PIN. Natijasi beyjik bilan bir xil.

    NEGA rol paroli emas: `arrachi` paroli butun smenaga ma'lum bo'lgan BITTA hisob,
    ya'ni kim ishlaganini yo'qotadi. PIN esa hodimga tegishli — ish haqi atributsiyasi
    beyjik bilan bir xil aniqlikda qoladi.

    Kuchi cheklangan va bu ataylab: monoblokda teriladi, yonidagi odam ko'rib qolishi
    mumkin. U tasodifiy noto'g'ri atributsiyani to'xtatadi, ataylab kuzatgan odamni
    emas — beyjik ham xuddi shunday (QR qog'ozda, nusxa olsa bo'ladi). Shuning uchun
    xato terish soni cheklanadi: 5 marta xato — 5 daqiqa blok.
    """
    employee = await db.get(Employee, body.employee_id)
    if employee is None or employee.is_deleted or employee.pin_hash is None:
        raise UnauthorizedException("Hodim topilmadi.")
    if employee.status != EmployeeStatus.ACTIVE:
        raise UnauthorizedException("Hodim nofaol. Adminga murojaat qiling.")
    if await _pin_locked(employee.id):
        raise UnauthorizedException(f"Kod {_PIN_MAX_FAILURES} marta xato terildi. {_PIN_LOCK_MINUTES} daqiqa kuting.")
    if not await verify_password(body.pin, employee.pin_hash):
        left = await _register_pin_failure(employee.id)
        raise UnauthorizedException(f"Kod noto'g'ri. {left} ta urinish qoldi.")

    await _clear_pin_failures(employee.id)
    return await _open_shift(db, response, request, employee=employee, post_id=body.post_id, how="PIN")


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
