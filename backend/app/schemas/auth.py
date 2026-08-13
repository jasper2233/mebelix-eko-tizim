from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str


class BadgeLoginRequest(BaseModel):
    """Beyjik skani = kirish. Post beyjik egasining biriktirilgan postlaridan aniqlanadi."""

    badge_id: str = Field(min_length=1, max_length=36)
    #: Hodim bir nechta postga biriktirilgan bo'lsa qaysi biriga kirayotgani.
    #: Bittasida bo'lsa berilmaydi — server o'zi tanlaydi.
    post_id: int | None = None


class PinLoginRequest(BaseModel):
    """Skaneri yo'q postda kirish: monoblokda ism bosiladi + 4-6 raqamli shaxsiy kod."""

    employee_id: int
    pin: str = Field(min_length=4, max_length=4)
    post_id: int | None = None


class PinEmployee(BaseModel):
    """Kirish sahifasidagi tanlov tugmasi. FAQAT PIN o'rnatilgan faol hodimlar."""

    id: int
    full_name: str
    position: str | None


class BadgePostOption(BaseModel):
    id: int
    code: str
    name: str


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
