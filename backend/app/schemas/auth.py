from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str


class DevicePairRequest(BaseModel):
    """Monoblokni stanokka bog'lash: admin bergan bir martalik kod."""

    code: str = Field(min_length=4, max_length=16)


class DevicePairResponse(BaseModel):
    token: str
    machine_name: str
    post_name: str


class BadgeLoginRequest(BaseModel):
    """Bog'langan qurilmada beyjik skani = kirish. Token qurilmani, beyjik hodimni tasdiqlaydi."""

    badge_id: str = Field(min_length=1, max_length=36)
    device_token: str = Field(min_length=8, max_length=64)


class BadgeLoginResponse(Token):
    employee_name: str
    machine_name: str
    post_name: str


class TokenData(BaseModel):
    # Immutable subject — the user's primary key. Never a username/phone: those can be renamed,
    # which would orphan live sessions and allow account confusion after re-registration.
    user_id: int
    token_version: int = 0
    # Unique id of a refresh token, used for one-time-use enforcement. None on access tokens.
    jti: str | None = None
