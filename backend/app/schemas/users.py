import re
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.enums import UserRole

# Uzbekistan E.164 phone — `+998` country code + 9 digits. Stored canonical, no spaces.
PHONE_PATTERN = r"^\+998\d{9}$"


def validate_password_strength(v: str) -> str:
    """Zaif parolni rad etadi: 8+ belgi, kichik va katta harf, raqam, belgi.

    Xabarlar O'ZBEKCHA, lekin ekranga CHIQMAYDI: pydantic ularni 422 massiv
    `detail` ichiga soladi, frontend `detailParts` (utils.ts) esa har qanday
    massivni "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring" ga
    almashtiradi. Admin ko'radigan matn `lib/validation.ts:passwordSchema` da
    qo'lda oynalangan — bu yerdagi qoidani o'zgartirsang, u yerni ham yangila.

    "Belgi" qoidasi ATAYLAB ASCII (`[^A-Za-z0-9]`): `str.isalnum()` Unicode-aware
    bo'lgani uchun oʻ/gʻ apostrofi (ʻ, ʼ — kategoriya Lm) "belgi" hisoblanmasdi,
    natijada zod o'tkazgan parol serverda 422 bilan qaytardi.
    """
    if len(v) < 8:
        raise ValueError("Parol kamida 8 belgi bo'lsin")
    if not any(c.islower() for c in v):
        raise ValueError("Parolda kamida bitta kichik harf bo'lsin")
    if not any(c.isupper() for c in v):
        raise ValueError("Parolda kamida bitta KATTA harf bo'lsin")
    if not any(c.isdigit() for c in v):
        raise ValueError("Parolda kamida bitta raqam bo'lsin")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Parolda kamida bitta belgi bo'lsin (masalan ! yoki *)")
    return v


def validate_phone(v: str | None) -> str | None:
    """Telefon: +998 va 9 raqam.

    `pattern` o'rniga funksiya: pydantic xatosi "String should match pattern ..."
    bo'lib chiqadi — OpenAPI/logda regexp emas, o'zbekcha matn tursin
    (ekranga chiqmasligi haqida `validate_password_strength` ga qarang).
    """
    if v is not None and not re.fullmatch(PHONE_PATTERN, v):
        raise ValueError("Telefon +998 bilan boshlanib, 9 ta raqamdan iborat bo'lsin")
    return v


#: 30 belgi yetmasdi: "Abdurahmonov Abdurahmon Abdurahmonovich" — 39 belgi.
#: `employee.full_name` allaqachon 100 belgi, ikkalasi bir xil bo'lsin.
_NAME_FIELD = Field(min_length=2, max_length=100, examples=["Abdurahmonov Sherzod"], default=None)
_USERNAME_FIELD = Field(min_length=2, max_length=20, pattern=r"^[a-z0-9]+$", examples=["userson"], default=None)


class UserRead(BaseModel):
    """Public-facing user representation. Used for every read response."""

    model_config = ConfigDict(from_attributes=True)

    # ATAYLAB str (boshqa Read sxemalarda int): JWT `sub` ham str — frontend
    # currentUser.id ni token bilan solishtiradi; int'ga o'tkazish client'dagi
    # barcha id taqqoslashlarni sindiradi, foydasi yo'q
    id: Annotated[str, BeforeValidator(lambda v: str(v)), Field(examples=["1"])]
    # O'QISHDA SHABLON/UZUNLIK CHEKLOVI YO'Q: chiqish sxemasi bazadagi narsani
    # TASVIRLAYDI, cheklamaydi. Ilgari bu yerda kirish shabloni turardi va
    # shablonga mos kelmagan BITTA qator butun `GET /users/` ni 500 qilardi
    # (`/users/me` ham shu sxemadan o'tadi — ya'ni bunday qator egasi ilovaga
    # umuman kira olmasdi). Cheklov faqat yozish sxemalarida: `UserCreate`,
    # `UserUpdate`, `UserAdminUpdate`.
    name: str | None = None
    username: str
    phone: str
    is_active: bool
    is_superuser: bool
    role: UserRole
    machine_id: int | None = None


class UserCreate(BaseModel):
    """Body for `POST /users` — superuser-only endpoint, so privilege flags live here."""

    model_config = ConfigDict(extra="ignore")

    name: Annotated[str | None, _NAME_FIELD]
    username: Annotated[str | None, _USERNAME_FIELD]
    phone: str = Field(examples=["+998901234567"])
    password: Annotated[str, Field(examples=["Str1ngst!"])]
    is_superuser: bool = False
    is_active: bool = True
    role: UserRole = UserRole.MANAGER
    machine_id: int | None = None  # required in practice for TERMINAL/TABLO roles

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return validate_phone(v)


class UserUpdate(BaseModel):
    """Body for `PATCH /users/me` — self-update only.

    Privilege flags can only be changed via `UserAdminUpdate` on the admin endpoint.
    Password changes go through `PATCH /users/me/password` so the current password is verified.
    """

    model_config = ConfigDict(extra="ignore")

    name: Annotated[str | None, _NAME_FIELD]
    username: Annotated[str | None, _USERNAME_FIELD]
    phone: str | None = Field(default=None, examples=["+998901234567"])

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return validate_phone(v)


class UserAdminUpdate(UserUpdate):
    """Body for `PATCH /users/{user_id}` — superuser-only endpoint."""

    password: str | None = Field(default=None)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role: UserRole | None = None
    machine_id: int | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str | None) -> str | None:
        return validate_password_strength(v) if v is not None else v


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class IdleLimit(BaseModel):
    #: Necha daqiqa harakatsizlikdan keyin chiqariladi; `None` — chiqarilmaydi (TABLO).
    idle_minutes: int | None
