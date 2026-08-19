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

    Xabarlar O'ZBEKCHA — ular to'g'ridan-to'g'ri adminning ekraniga toast bo'lib
    chiqadi (frontend `detailMessage`), ya'ni bu ichki log matni emas, interfeys matni.
    """
    if len(v) < 8:
        raise ValueError("Parol kamida 8 belgi bo'lsin")
    if not any(c.islower() for c in v):
        raise ValueError("Parolda kamida bitta kichik harf bo'lsin")
    if not any(c.isupper() for c in v):
        raise ValueError("Parolda kamida bitta KATTA harf bo'lsin")
    if not any(c.isdigit() for c in v):
        raise ValueError("Parolda kamida bitta raqam bo'lsin")
    if not any(not c.isalnum() for c in v):
        raise ValueError("Parolda kamida bitta belgi bo'lsin (masalan ! yoki *)")
    return v


def validate_phone(v: str | None) -> str | None:
    """Telefon: +998 va 9 raqam.

    Pydantic `pattern` xatosi ekranga "String should match pattern ..." bo'lib
    chiqardi — regexp adminning ekraniga tushmasligi kerak.
    """
    if v is not None and not re.fullmatch(PHONE_PATTERN, v):
        raise ValueError("Telefon +998 bilan boshlanib, 9 ta raqamdan iborat bo'lsin")
    return v


#: 30 belgi yetmasdi: "Abdurahmonov Abdurahmon Abdurahmonovich" — 39 belgi.
#: `employee.full_name` allaqachon 100 belgi, ikkalasi bir xil bo'lsin.
_NAME_FIELD = Field(min_length=2, max_length=100, examples=["Abdurahmonov Sherzod"], default=None)
_USERNAME_FIELD = Field(min_length=2, max_length=20, pattern=r"^[a-z0-9]+$", examples=["userson"], default=None)
_PHONE_FIELD = Field(examples=["+998901234567"])
_OPTIONAL_PHONE_FIELD = Field(examples=["+998901234567"], default=None)


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
    phone: Annotated[str, _PHONE_FIELD]
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
    phone: Annotated[str | None, _OPTIONAL_PHONE_FIELD]

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
