from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip
from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    TokenType,
    create_access_token,
    create_refresh_token,
    set_auth_cookie,
    verify_token,
)
from app.core.utils.rate_limit import RateLimit, rate_limiter
from app.core.ws import ws_manager
from app.crud import crud_users, log_action
from app.models import Employee, Machine, Post
from app.models.enums import POST_ROLES, EmployeeStatus, UserRole
from app.models.user import User
from app.schemas.auth import BadgeLoginRequest, BadgeLoginResponse, BadgePostOption, Token
from app.services.scanning import MACHINE_MISSING, open_badge_session, post_machine

router = APIRouter(prefix="/login", tags=["login"])

# Brute-force defence — tunable via LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_PERIOD.
_LOGIN_RATE_LIMIT = RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)
# Beyjikda chegara kengroq: parolni topish mumkin, 122-bitli UUID'ni esa yo'q.
# Tor chegara esa zarar qilardi — smena almashuvida ketma-ket skanlar butun tsexni
# (bitta tashqi IP) qulflab qo'yardi.
_BADGE_RATE_LIMIT = RateLimit(limit=30, period=60)

ACCESS_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

_USED_JTI_PREFIX = "auth:refresh:used:"


def refresh_days(user: User) -> int:
    """Shu hisobning refresh tokeni necha kun yashaydi.

    BITTA joyda: tokenni berish ham, bir martalik ishlatish belgisining (tombstone)
    muddati ham shundan oladi. Ilgari tombstone qotirilgan 7 kunlik qiymat
    bilan qo'yilardi, qurilma tokeni esa 90 kun yashardi — ya'ni 8-kundan 90-kungacha
    ALLAQACHON aylantirilgan token qayta ishlatilsa bo'lardi va bir martalik
    kafolat jimgina yo'qolardi (o'lchandi: 83 kunlik replay oynasi).
    """
    device = UserRole(user.role) in (UserRole.TERMINAL, UserRole.TABLO)
    return settings.DEVICE_REFRESH_TOKEN_EXPIRE_DAYS if device else settings.REFRESH_TOKEN_EXPIRE_DAYS


def _issue_token_pair(response: Response, user: User) -> str:
    """Generate access+refresh tokens and set both as httpOnly cookies. Returns the access token.

    Qurilma hisoblari (TERMINAL, TABLO) uzun refresh oladi: monoblokda klaviatura
    yo'q va u parolni FAQAT o'rnatishda bir marta teradi. Odam hisoblarida muddat
    qisqa qoladi — o'g'irlangan cookie oynasi kengaymasin.
    """
    payload = {"sub": str(user.id), "token_version": user.token_version}
    days = refresh_days(user)
    access_token = create_access_token(data=payload)
    refresh_token = create_refresh_token(data=payload, days=days)
    set_auth_cookie(response, ACCESS_COOKIE_NAME, access_token, ACCESS_MAX_AGE)
    set_auth_cookie(response, REFRESH_COOKIE_NAME, refresh_token, days * 24 * 60 * 60)
    return access_token


async def _claim_refresh_jti(jti: str, max_age: int) -> bool:
    """Tokenni ATOMIK «ishlatildi» deb belgilaydi. False = jti allaqachon ishlatilgan.

    Bitta `SET NX`: ilgari EXISTS bilan tekshirib, keyin alohida SET qilinardi —
    ikki parallel replay orasidagi oynada IKKALASI ham o'tib ketardi va bir martalik
    kafolat ishlamasdi.
    """
    if rate_limiter.client is None:  # No lifespan (tests/scripts) — Redis is always on in the app.
        return True
    return bool(await rate_limiter.client.set(_USED_JTI_PREFIX + jti, 1, ex=max_age, nx=True))


async def mark_refresh_token_used(jti: str, max_age: int) -> None:
    if rate_limiter.client is None:
        return
    # Tombstone token qancha yashashi mumkin bo'lsa — shuncha turadi (`refresh_days`).
    await rate_limiter.client.set(_USED_JTI_PREFIX + jti, 1, ex=max_age)


async def _audit_auth(db: SessionDep, request: Request, action: str, *, user_id: int | None, message: str) -> None:
    """Admin paneliga kirish/chiqishni audit logga yozadi (`auth` moduli).

    SHU YERDA commit qilinadi: rad etish yo'lida keyin 401 ko'tariladi va sessiya
    rollback bo'lardi — ya'ni aynan brute-force izi yo'qolardi.
    """
    log_action(db, module="auth", action=action, user_id=user_id, message=message, ip=client_ip(request))
    await db.commit()


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
    request: Request,
) -> dict[str, str]:
    # Chegara FAQAT muvaffaqiyatsiz urinishni hisoblaydi (`_LOGIN_RATE_LIMIT.hit`):
    # tsex bitta tashqi IP orqali chiqadi va har so'rov hisoblanganda bir necha
    # operator kirgach admin bloklanib qolardi.
    user = await crud_users.authenticate(db=db, username_or_phone=form_data.username, password=form_data.password)
    if not user:
        await _LOGIN_RATE_LIMIT.hit(request)
        await _audit_auth(
            db, request, "login_failed", user_id=None, message=f"Kirish urinishi rad etildi: {form_data.username}"
        )
        raise UnauthorizedException("Foydalanuvchi nomi, telefon yoki parol noto'g'ri.")
    if not user.is_active:
        await _LOGIN_RATE_LIMIT.hit(request)
        await _audit_auth(db, request, "login_failed", user_id=user.id, message=f"Nofaol hisob: {form_data.username}")
        raise UnauthorizedException("Foydalanuvchi faol emas")
    # TIZIM hisobi hech qachon kirmaydi: u beyjik bilan ochilgan smena qaysi hisob
    # nomidan yozilishini hal qiladi, xolos (`_terminal_user`). Odamning SHAXSIY
    # hisobi esa kiradi — skaneri yo'q postda (ARRA) yagona yo'l shu.
    if user.is_system:
        await _LOGIN_RATE_LIMIT.hit(request)
        await _audit_auth(
            db, request, "login_failed", user_id=user.id, message=f"Texnik hisob bilan kirish: {form_data.username}"
        )
        raise UnauthorizedException("Bu texnik hisob — u bilan kirilmaydi. Beyjik yoki shaxsiy hisobdan foydalaning.")

    await _audit_auth(db, request, "login", user_id=user.id, message=f"Parol bilan kirish: {form_data.username}")

    # Tsex hisobi bo'lsa smena SHU YERDA ochiladi: aks holda operator kirib, keyin
    # yana ekranda ismini bosishi kerak bo'lardi — ikki marta bir ish
    if POST_ROLES.get(UserRole(user.role)) is not None:
        await _open_shift_for(db, user, request)

    access_token = _issue_token_pair(response, user)
    return {"access_token": access_token, "token_type": "bearer"}


async def _open_shift_for(db: SessionDep, user: User, request: Request) -> None:
    """Tsex xodimi parol bilan kirganda smenasini ochadi.

    Hodim yozuvi `employee.user_id` orqali topiladi — u bo'lmasa smena ochilmaydi
    va terminal ekranida odam o'zini tanishtiradi (ismini bosadi yoki beyjik).
    Post rolidan keladi, ish markazi esa `post_machine` qoidasidan.

    Smena ochilishi audit logga yoziladi (`sessions/started`) — beyjik yo'li va
    terminaldagi yo'l bilan BIR XIL, aks holda parol bilan ochilgan smena izsiz qolardi.
    """
    employee = (
        await db.execute(
            select(Employee).where(
                Employee.user_id == user.id,
                Employee.status == EmployeeStatus.ACTIVE,
                Employee.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if employee is None:
        return
    post_code = POST_ROLES[UserRole(user.role)]
    post = (
        await db.execute(select(Post).where(Post.code == post_code, Post.is_deleted == False))  # noqa: E712
    ).scalar_one_or_none()
    if post is None or post.id not in (employee.assigned_post_ids or []):
        return
    machine = await post_machine(db, post)
    if machine is None:
        return
    session = await open_badge_session(db, user=user, machine=machine, post=post, employee=employee)
    log_action(
        db,
        module="sessions",
        action="started",
        user_id=user.id,
        employee_id=employee.id,
        entity_type="session",
        entity_id=session.id,
        message=f"Parol bilan kirish: {employee.full_name} — {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    # Beyjik yo'li (login_with_badge) va terminal bilan bir xil: tablo/dashboard smena boshlanganini ko'rsin
    await ws_manager.publish(
        "session.started",
        {"session_id": session.id, "employee": employee.full_name, "machine_id": machine.id, "post_id": post.id},
    )


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


async def _terminal_user(db: SessionDep, machine: Machine, post: Post) -> User:
    """Kirish qaysi hisob nomidan yoziladi.

    Ikki manba, shu tartibda: shu ish markaziga biriktirilgan TERMINAL hisobi, bo'lmasa
    post rolidagi hisob. Ikkalasi ham `resolve_terminal` bilan BIR XIL postga
    olib keladi (biri ish markazi orqali, ikkinchisi rol orqali) — aks holda operator
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
                    # TEXNIK hisob: shu rolda odamning SHAXSIY hisobi ham bo'ladi
                    # (skaneri yo'q post). Usiz eng kichik ID olinardi va beyjik
                    # ochgan smena BOSHQA ishchining hisobi nomidan yozilardi.
                    User.is_system == True,  # noqa: E712
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
        await _BADGE_RATE_LIMIT.hit(request)
        raise UnauthorizedException("Beyjik topilmadi.")
    if employee.status != EmployeeStatus.ACTIVE:
        await _BADGE_RATE_LIMIT.hit(request)
        raise UnauthorizedException("Beyjik nofaol. Adminga murojaat qiling.")

    # Postga biriktirilganini `_badge_post` tekshiradi (terminaldagi `badge_employee`
    # bilan bir xil qoida, faqat u yerda post ma'lum, bu yerda esa aniqlanadi).
    post = await _badge_post(db, employee, body.post_id)
    # Ish markazi qoidasi `scanning.post_machine` da: beyjik kirishi va terminal
    # konteksti BIR XIL javob berishi kerak, aks holda operator bir joyda kirib
    # boshqa joyda skan qilardi.
    machine = await post_machine(db, post)
    if machine is None:
        raise UnauthorizedException(f"{post.name} {MACHINE_MISSING}")
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
        message=f"Beyjik bilan kirish: {employee.full_name} — {machine.name}",
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

    user = await crud_users.get(db=db, id=token_data.user_id)
    if not user or not user.is_active or user.token_version != token_data.token_version:
        raise UnauthorizedException("Token bekor qilingan.")

    # One-time use: a replayed refresh token means the cookie was stolen or the client is broken —
    # either way the whole session is revoked by bumping token_version. Tombstone AVVAL qo'yiladi
    # (atomik claim), shuning uchun parallel ikki replaydan faqat bittasi o'tadi.
    if token_data.jti and not await _claim_refresh_jti(token_data.jti, refresh_days(user) * 24 * 60 * 60):
        await crud_users.increment_token_version(db=db, user=user)
        await db.commit()  # revoke pastdagi raise'dan oldin saqlansin — aks holda rollback bo'lardi
        raise UnauthorizedException("Token bekor qilingan.")

    access_token = _issue_token_pair(response, user)
    return {"access_token": access_token, "token_type": "bearer"}
