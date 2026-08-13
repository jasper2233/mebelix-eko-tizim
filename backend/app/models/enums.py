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
    OVALCHI = "ovalchi"
    PRISADKACHI = "prisadkachi"
    ROVERCHI = "roverchi"
    STOLYAR = "stolyar"
    BOYOQCHI = "boyoqchi"
    UPAKOVKACHI = "upakovkachi"
    OMBORCHI = "omborchi"


class PostCode(StrEnum):
    ARRA = "ARRA"
    KROMKA = "KROMKA"
    OVAL = "OVAL"  # oval (egri) kromka — alohida post, texnolog matritsada belgilaydi
    PRISADKA = "PRISADKA"
    # PAZ olib tashlandi: paz ham frezer stanogida kesiladi, ya'ni ROVER postida.
    # order_index 5 bo'sh qoldirildi — qayta raqamlash hech narsa bermaydi.
    ROVER = "ROVER"
    STOLYARKA = "STOLYARKA"
    BOYOQ = "BOYOQ"
    #: Qadoqlash — oxirgi bosqich. Marshrutga anketadagi `packaging` bayrog'i
    #: bo'yicha qo'shiladi (buyurtma qadoqlansa — HAMMA detalga).
    UPAKOVKA = "UPAKOVKA"
    #: TMO — Tayyor Mahsulot Ombori, marshrutning ENG OXIRGI qadami, har detalda.
    #: Qabul qilinganda yopiladi: qadoqsiz buyurtmada detal QR'i bilan,
    #: qadoqlanganda esa qadoq QR'i bitta skanda ichidagi hammasini yopadi.
    #:
    #: ATAMA QOIDASI (kelishilgan): tsexda IKKITA ombor bor va ikkalasi ham o'z
    #: nomi bilan ataladi — MATERIALLAR OMBORI va TMO. Yolg'iz "Ombor" ham,
    #: "sklad" ham ishlatilmaydi: qaysi biri ekani yo'qoladi. UPAKOVKA esa
    #: ombor emas — QADOQLASH BO'LIMI, ya'ni marshrutning oddiy posti.
    TMO = "TMO"


# Operator roles log in with their own account and see their post's terminal —
# no machine binding, no badge (unlike TERMINAL device accounts).
POST_ROLES: dict[UserRole, PostCode] = {
    UserRole.ARRACHI: PostCode.ARRA,
    UserRole.KROMKACHI: PostCode.KROMKA,
    UserRole.OVALCHI: PostCode.OVAL,
    UserRole.PRISADKACHI: PostCode.PRISADKA,
    UserRole.ROVERCHI: PostCode.ROVER,
    UserRole.STOLYAR: PostCode.STOLYARKA,
    UserRole.BOYOQCHI: PostCode.BOYOQ,
    UserRole.UPAKOVKACHI: PostCode.UPAKOVKA,
    # Rol kodi "omborchi" bo'lib qoladi (ODAMNING kasbi), lekin ekranda "TMO
    # omborchisi" — materiallar ombori omborchisidan farqi ko'rinib tursin
    UserRole.OMBORCHI: PostCode.TMO,
}


class PachkaStatus(StrEnum):
    """Qadoq holati: ochiq (detal qo'shiladi) -> yopiq (chek chiqadi) -> jo'natildi."""

    OPEN = "open"
    CLOSED = "closed"
    SHIPPED = "shipped"


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
