from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.core.security import clear_auth_cookies
from app.crud import crud_users

router = APIRouter(tags=["login"])


@router.post("/logout", operation_id="logout")
async def logout(
    response: Response,
    db: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    """Log the user out by bumping `token_version`, which invalidates every outstanding access/refresh token."""
    await crud_users.increment_token_version(db=db, user=current_user)
    clear_auth_cookies(response)
    return {"message": "Tizimdan muvaffaqiyatli chiqildi"}
