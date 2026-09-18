from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def db_enum(enum_cls: type[StrEnum]) -> SAEnum:
    """VARCHAR-backed enum (no native PG enum type — painless ALTERs on new members)."""
    return SAEnum(enum_cls, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e])


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
    #: Oval (egri) kromka — alohida post. Detallar matritsasida ustuni YO'Q
    #: (`STANDARD_MATRIX_POSTS` faqat ARRA/KROMKA/PRISADKA): texnolog uni
    #: «Nostandart detallar» tabida jarayon kodi 5 bilan marshrutga qo'shadi.
    OVAL = "OVAL"
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


#: Frontenddagi `UNIT_LABELS` (routes/tablo.tsx) bilan AYNAN bir xil matn —
#: bitta post ikki ekranda ikki xil birlik bilan chiqmasin.
POST_UNIT_LABELS: dict[PostUnit, str] = {
    PostUnit.M2: "m²",
    PostUnit.METER: "m",
    PostUnit.PIECE: "dona",
}


class MachineStatus(StrEnum):
    """Ish markazining ish holati — BEZAK EMAS, tanlovga ta'sir qiladi.

    ACTIVE   ishlayapti.
    REPAIR   buzilgan, lekin post ishlashda davom etadi: avtomatik tanlanadi
             (oxirgi navbatda), YANGI buyurtma esa biriktirilmaydi.
    INACTIVE admin ataylab ishdan chiqargan: avtomatik TANLANMAYDI, unga
             bog'langan qurilma hisobi skan qila olmaydi.

    Qoida `app/services/scanning.post_machine` da, bitta joyda.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    REPAIR = "repair"


#: Xato xabarlari uchun — frontenddagi `MACHINE_STATUS_LABELS` bilan bir xil matn
MACHINE_STATUS_LABELS: dict[MachineStatus, str] = {
    MachineStatus.ACTIVE: "AKTIV",
    MachineStatus.INACTIVE: "NOAKTIV",
    MachineStatus.REPAIR: "TA'MIRDA",
}


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    TECHNICAL_REVIEW = "technical_review"
    PRODUCTION = "production"
    COMPLETED = "completed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


#: Foydalanuvchiga ko'rinadigan xabarlar uchun — frontenddagi `ORDER_STATUS_LABELS`
#: (lib/mes.ts) bilan AYNAN bir xil matn; birini o'zgartirsang ikkinchisini ham.
ORDER_STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.DRAFT: "QORALAMA",
    OrderStatus.TECHNICAL_REVIEW: "TEXNOLOGDA",
    OrderStatus.PRODUCTION: "JARAYONDA",
    OrderStatus.COMPLETED: "TAYYOR",
    OrderStatus.DELIVERED: "TOPSHIRILDI",
    OrderStatus.CANCELLED: "BEKOR QILINGAN",
}


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


class DowntimeKind(StrEnum):
    """To'xtash turi (`downtime.kind`). Frontenddagi `DOWNTIME_KIND_LABELS` (lib/mes.ts) bilan qo'lda oynalangan.

    FAULT/OFF/IDLE — Pico signal ustunidan chiqarilgan (`services/downtimes.py`), LOCK — operator
    qulf tugmasi bilan o'zi e'lon qilgan to'xtash."""

    FAULT = "fault"  # qizil chiroq — avariya
    OFF = "off"  # hamma chiroq o'chiq (Pico quvvatda, stanok o'chiq)
    IDLE = "idle"  # sariq chiroq chegaradan uzoq — stanok ishlamayapti
    LOCK = "lock"  # operator ketishdan oldin sababni aytib ekranni qulfladi
