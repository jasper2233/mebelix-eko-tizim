import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update

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
    verify_token,
)
from app.core.utils.rate_limit import RateLimit, rate_limiter
from app.core.ws import ws_manager
from app.crud import crud_users, log_action
from app.models import BridgeAgent, Machine, Post
from app.models.enums import POST_ROLES, UserRole
from app.models.user import User
from app.schemas.auth import (
    BadgeLoginRequest,
    BadgeLoginResponse,
    DevicePairRequest,
    DevicePairResponse,
    Token,
)
from app.services.scanning import ScanRejected, badge_employee, open_badge_session

router = APIRouter(prefix="/login", tags=["login"])

# Brute-force defence — tunable via LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_PERIOD.
_LOGIN_RATE_LIMIT = RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)
# Beyjikda chegara kengroq: parolni topish mumkin, 122-bitli UUID'ni esa yo'q —
# ustiga qurilma tokeni ham kerak. Tor chegara esa zarar qilardi: smena
# almashuvida ketma-ket skanlar butun sexni (bitta tashqi IP) qulflab qo'yardi.
_BADGE_RATE_LIMIT = RateLimit(limit=30, period=60)

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


@router.post("/device", response_model=DevicePairResponse, operation_id="pair_terminal_device")
async def pair_terminal_device(db: SessionDep, body: DevicePairRequest, request: Request) -> DevicePairResponse:
    """OCHIQ endpoint: monoblok bir martalik kodni doimiy qurilma tokeniga almashtiradi.

    Atomik UPDATE — bitta kod ikki qurilmaga tushmaydi. Kod noto'g'ri yoki eskirgani
    bir xil xato bilan qaytadi (kod bor-yo'qligi oshkor bo'lmaydi).
    """
    code = body.code.replace("-", "").replace(" ", "").upper()
    token = secrets.token_hex(24)
    row = (
        await db.execute(
            update(Machine)
            .where(
                Machine.pair_code == code,
                Machine.is_deleted == False,  # noqa: E712
                Machine.pair_expires_at > datetime.now(UTC),
            )
            .values(token_hash=hashlib.sha256(token.encode()).hexdigest(), pair_code=None, pair_expires_at=None)
            .returning(Machine.id, Machine.name, Machine.post_id)
        )
    ).first()
    if row is None:
        await db.rollback()
        # Admin panelda ikkita ulanish kodi bor va ikkalasi ham 8 belgili. Printer
        # agentiniki bu yerga terilsa "kod noto'g'ri" deyish adashtirardi — kod
        # to'g'ri, joyi noto'g'ri. Faqat XATO yo'lida so'raladi.
        agent = (
            await db.execute(
                select(BridgeAgent.name).where(
                    BridgeAgent.pair_code == code,
                    BridgeAgent.is_deleted == False,  # noqa: E712
                    BridgeAgent.pair_expires_at > datetime.now(UTC),
                )
            )
        ).scalar_one_or_none()
        if agent is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Bu kod printer agenti uchun ({agent}). Terminal kodi Stanoklar sahifasidan olinadi.",
            )
        raise HTTPException(status_code=400, detail="Ulanish kodi noto'g'ri yoki muddati o'tgan.")
    post = await db.get(Post, row.post_id)
    log_action(
        db,
        module="machines",
        action="device_paired",
        user_id=None,
        entity_type="machine",
        entity_id=row.id,
        message=f"Terminal qurilmasi bog'landi: {row.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await ws_manager.publish("machine.paired", {"machine_id": row.id})
    return DevicePairResponse(token=token, machine_name=row.name, post_name=post.name if post else "")


async def _device_machine(db: SessionDep, device_token: str) -> tuple[Machine, Post]:
    machine = (
        await db.execute(
            select(Machine).where(
                Machine.token_hash == hashlib.sha256(device_token.encode()).hexdigest(),
                Machine.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if machine is None:
        raise UnauthorizedException("Qurilma bog'lanmagan. Adminga murojaat qiling.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise UnauthorizedException("Stanok posti topilmadi.")
    return machine, post


async def _terminal_user(db: SessionDep, machine: Machine, post: Post) -> User:
    """Qurilma qaysi hisob nomidan ishlaydi.

    Avval shu stanokka biriktirilgan hisob, bo'lmasa post rolidagi hisob (prodda
    operator hisoblari stanoksiz turibdi). Hisob hech qaysi hodimni bildirmaydi —
    KIM ishlayotgani beyjik ochgan smenada.
    """
    post_role = next((r for r, code in POST_ROLES.items() if code == post.code), None)
    roles = [UserRole.TERMINAL, *([post_role] if post_role else [])]
    user = (
        await db.execute(
            select(User)
            .where(
                User.role.in_(roles),
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
            # Stanokka biriktirilgani ustun, keyin TERMINAL roli
            .order_by((User.machine_id == machine.id).desc(), (User.role == UserRole.TERMINAL).desc(), User.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if user is None:
        raise UnauthorizedException(f"{machine.name} uchun terminal hisobi yo'q. Admin hisob yaratishi kerak.")
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
    """Sexdagi kirish: bog'langan qurilma + beyjik skani, parolsiz.

    Ikki omil: token qurilmani (sexda turibdi), beyjik hodimni tasdiqlaydi. Beyjik
    QR qog'ozda — yolg'iz o'zi hech qayerdan kira olmaydi.
    """
    machine, post = await _device_machine(db, body.device_token)
    try:
        employee = await badge_employee(db, body.badge_id, post)
    except ScanRejected as exc:
        raise UnauthorizedException(exc.message) from None
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
