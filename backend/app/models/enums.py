from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def db_enum(enum_cls: type[StrEnum], length: int = 30) -> SAEnum:
    """VARCHAR-backed enum (no native PG enum type — painless ALTERs on new members)."""
    return SAEnum(enum_cls, native_enum=False, length=length, values_callable=lambda e: [m.value for m in e])


class UserRole(StrEnum):
    ADMIN = "admin"
    DIRECTOR = "director"
    MANAGER = "manager"
    TEXNOLOG = "texnolog"
    TERMINAL = "terminal"
    TABLO = "tablo"
    ARRACHI = "arrachi"
    KROMKACHI = "kromkachi"
    PRISADKACHI = "prisadkachi"
    PAZCHI = "pazchi"
    ROVERCHI = "roverchi"
    STOLYAR = "stolyar"


class PostCode(StrEnum):
    ARRA = "ARRA"
    KROMKA = "KROMKA"
    PRISADKA = "PRISADKA"
    PAZ = "PAZ"
    ROVER = "ROVER"
    STOLYARKA = "STOLYARKA"


# Operator roles log in with their own account and see their post's terminal —
# no machine binding, no badge (unlike TERMINAL device accounts).
POST_ROLES: dict[UserRole, PostCode] = {
    UserRole.ARRACHI: PostCode.ARRA,
    UserRole.KROMKACHI: PostCode.KROMKA,
    UserRole.PRISADKACHI: PostCode.PRISADKA,
    UserRole.PAZCHI: PostCode.PAZ,
    UserRole.ROVERCHI: PostCode.ROVER,
    UserRole.STOLYAR: PostCode.STOLYARKA,
}


class PostUnit(StrEnum):
    M2 = "m2"
    METER = "meter"
    PIECE = "piece"


class MachineStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REPAIR = "repair"


class CapacityUnit(StrEnum):
    M2_PER_HOUR = "m2_per_hour"
    METER_PER_HOUR = "meter_per_hour"
    UNITS_PER_HOUR = "units_per_hour"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ClientType(StrEnum):
    INDIVIDUAL = "individual"
    LEGAL = "legal"


class MaterialType(StrEnum):
    SHEET = "sheet"
    BAND = "band"
    HARDWARE = "hardware"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    TECHNICAL_REVIEW = "technical_review"
    PRODUCTION = "production"
    COMPLETED = "completed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProjectGeneration(StrEnum):
    PROCESSED = "processed"
    TEMPLATE = "template"


class RouteSource(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class FileKind(StrEnum):
    PROJECT = "project"
    SCX = "scx"
    LABEL_PDF = "label_pdf"
    DOCUMENT = "document"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
