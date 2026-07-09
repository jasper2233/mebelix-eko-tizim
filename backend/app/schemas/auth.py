from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    # Immutable subject — the user's primary key. Never a username/phone: those can be renamed,
    # which would orphan live sessions and allow account confusion after re-registration.
    user_id: int
    token_version: int = 0
    # Unique id of a refresh token, used for one-time-use enforcement. None on access tokens.
    jti: str | None = None
