from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.security import clear_auth_cookies
from app.crud import crud_users
from app.models import Employee, WorkSession
from app.models.enums import SessionStatus
from app.schemas.common import Message
from app.services.scanning import end_session

router = APIRouter(tags=["login"])


@router.post("/logout", response_model=Message, operation_id="logout")
async def logout(
    response: Response,
    db: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Log the user out by bumping `token_version`, which invalidates every outstanding access/refresh token.

    Tsex xodimi uchun chiqish SMENANI ham yopadi. Kirish uni ochgan
    (`login._open_shift_for`), shuning uchun chiqish uni yopmasa hisob yopilib,
    smena ochiq qolib ketardi: terminal "Kim ishlayapti?" ni ko'rsatar, ish haqi
    esa ketgan odamga yozilib turaverardi.

    Faqat O'Z smenasi yopiladi - beyjik bilan qo'shilgan sherigining smenasiga
    tegilmaydi, u boshqa odam va o'zi chiqadi.
    """
    sessions = (
        (
            await db.execute(
                select(WorkSession)
                .join(Employee, Employee.id == WorkSession.employee_id)
                .where(
                    Employee.user_id == current_user.id,
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
    await crud_users.increment_token_version(db=db, user=current_user)
    await db.commit()
    clear_auth_cookies(response)
    return Message(message="Tizimdan muvaffaqiyatli chiqildi")
