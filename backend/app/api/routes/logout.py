import contextlib

from fastapi import APIRouter, Request, Response
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, SessionDep, client_ip
from app.api.routes.login import mark_refresh_token_used, refresh_days
from app.core.security import REFRESH_COOKIE_NAME, TokenType, clear_auth_cookies, verify_token
from app.crud import log_action
from app.models import Employee, WorkSession
from app.models.enums import SessionStatus, UserRole
from app.schemas.common import Message
from app.services.scanning import end_session

router = APIRouter(tags=["login"])


@router.post("/logout", response_model=Message, operation_id="logout")
async def logout(
    request: Request,
    response: Response,
    db: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Chiqish — FAQAT SHU QURILMA.

    Ilgari bu yerda `token_version` oshirilardi va u hisobning HAMMA
    qurilmasidagi tokenni birdan o'ldirardi: monoblokdan chiqqan admin
    noutbukdagi ishidan ham uchib tushardi. Sanoat amaliyoti boshqacha —
    "Chiqish" joriy sessiyani yopadi, hamma joydan chiqarish esa alohida,
    ATAYLAB tanlanadigan amal. Bu yerda uni alohida tugma qilmaymiz: parol
    almashtirish allaqachon `token_version` ni oshiradi (`users.py`), ya'ni
    "hamma qurilmadan chiqish" kerak bo'lgan yagona jiddiy holat — token
    o'g'irlangani — parolni almashtirish bilan yopiladi.

    Shu qurilma haqiqatan uziladi: refresh token bir martalik va uning `jti` si
    Redis'ga "ishlatilgan" deb qo'yiladi (aylantirish mexanizmi allaqachon shu
    tombstone'ga tayanadi), cookie'lar esa tozalanadi. Access token 30 daqiqa
    texnik jihatdan amal qiladi, lekin u ham shu qurilmadan o'chiriladi.

    Tsex xodimi uchun chiqish SMENANI ham yopadi. Kirish uni ochgan
    (`login._open_shift_for`), shuning uchun chiqish uni yopmasa hisob yopilib,
    smena ochiq qolib ketardi: terminal "Kim ishlayapti?" ni ko'rsatar, ish haqi
    esa ketgan odamga yozilib turaverardi.

    Faqat O'Z smenasi yopiladi - beyjik bilan qo'shilgan sherigining smenasiga
    tegilmaydi, u boshqa odam va o'zi chiqadi.
    """
    mine = Employee.user_id == current_user.id
    # QURILMA hisobi (TERMINAL yoki post rolidagi texnik hisob) hech bir hodimga
    # bog'lanmagan — beyjik bilan ochilgan smenalar `work_session.user_id` da shu hisob
    # nomidan yoziladi (`login._terminal_user`). Ilgari ular chiqishda yopilmasdi va
    # harakatsizlikdan chiqarilgan monoblokning brigadasi tun bo'yi ochiq qolardi.
    if current_user.is_system or UserRole(current_user.role) == UserRole.TERMINAL:
        mine = or_(mine, WorkSession.user_id == current_user.id)
    sessions = (
        (
            await db.execute(
                select(WorkSession)
                .join(Employee, Employee.id == WorkSession.employee_id)
                .where(
                    mine,
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for session in sessions:
        await end_session(db, session)
    log_action(
        db,
        module="auth",
        action="logout",
        user_id=current_user.id,
        message=f"Chiqish: {current_user.username}",
        ip=client_ip(request),
    )
    await db.commit()
    # Joriy refresh tokenni bekor qilamiz — boshqa qurilmalarnikiga tegilmaydi
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw:
        with contextlib.suppress(Exception):  # buzuq/eskirgan token — chiqish baribir bajariladi
            data = verify_token(raw, TokenType.REFRESH)
            if data is not None and data.jti:
                await mark_refresh_token_used(data.jti, refresh_days(current_user) * 24 * 60 * 60)
    clear_auth_cookies(response)
    return Message(message="Tizimdan muvaffaqiyatli chiqildi")
