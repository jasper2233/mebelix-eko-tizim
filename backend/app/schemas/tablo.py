"""TABLO javob sxemalari: buyurtma × bosqich matritsasi va drill-down."""

from datetime import date, datetime

from pydantic import BaseModel


class StageAgg(BaseModel):
    post_id: int
    done: int
    total: int
    #: Post birligidagi hajm (m² / metr / dona) — FAQAT matritsada. Drill-down
    #: (`/tablo/orders/{id}`) bu yerga qadam SONINI takrorlaydi va uni hech kim
    #: o'qimaydi: u yerda frontend "hajm" rejimini "soni" ga almashtiradi.
    volume_total: float
    volume_done: float


class TabloPostCol(BaseModel):
    """Matritsa ustuni — post metadatasi (frontend ustun sarlavhalari shu bilan chiziladi)."""

    id: int
    code: str
    name: str
    unit: str
    order_index: int


class TabloOrderRow(BaseModel):
    id: int
    number: str
    name: str | None
    deadline: date | None
    #: Taxta prioritet bo'yicha saralanadi, lekin uni KO'RSATMASDI — ya'ni
    #: "nega bu qator birinchi?" degan savolga javob yo'q edi.
    priority: str
    stages: dict[str, StageAgg]  # keyed by post code
    #: Shu buyurtma oxirgi marta qimirlaganidan beri TSEX NECHA KUN ishlagani.
    #: `None` — hali bironta ham amal bajarilmagan (uzatilgan, tegilmagan);
    #: `0` — bugun qimirlagan. Ikkalasi ham "0 kun" emas, boshqa-boshqa fakt.
    #:
    #: Kalendar kuni EMAS, ataylab: tsex dam olgan kun hisobga olinmasa,
    #: dushanba ertalab butun taxta "2 kun to'xtagan" bo'lib yonardi va belgi
    #: ma'nosini yo'qotardi. "Tsex ishlagan kun" = o'sha kuni bironta skan
    #: bo'lgan kun, ya'ni bayram/ta'til/to'xtash ro'yxatini yuritish kerak emas.
    #: Doim PRODUCTION (so'rov shu bo'yicha filtrlaydi), lekin dashboard uni
    #: StatusBadge bo'lib chizadi — olib tashlash UI o'zgarishi, tozalash emas.
    status: str
    idle_days: int | None = None


class TabloMatrix(BaseModel):
    posts: list[TabloPostCol]
    orders: list[TabloOrderRow]


class TabloPartRow(BaseModel):
    part_id: int
    code: str
    name: str
    count: int
    stages: dict[str, StageAgg]


class TabloOrderDetail(BaseModel):
    id: int
    number: str
    name: str | None
    parts: list[TabloPartRow]


class TabloMachineRow(BaseModel):
    """Devordagi stanok taxtasining bitta kartasi — Pico ulangan BITTA ish markazi.

    Raqamlar «Stanok vaqti» hisobotining AYNAN o'zidan (bugungi kun uchun): taxta
    va hisobot hech qachon boshqa-boshqa raqam ko'rsatmasin."""

    machine_id: int
    machine_name: str
    post_name: str
    #: Jonli holat (Redis): PROCESSING / AWAIT_PART / IDLE / STOPPED / FAULT / OFF.
    #: `None` — Pico yoki agentdan 90 soniyadan beri xabar yo'q (kartada «aloqa yo'q»).
    state: str | None
    since: datetime | None  # holat qachondan beri
    crew: list[str]  # smenadagi hodimlar; bo'sh — smena ochilmagan
    #: Bugungi OEE — hisobotdagi ustunlar bilan bir xil
    planned_s: int
    run_s: int
    stop_s: int  # rejasiz to'xtash + ma'lumotsiz vaqt
    availability_pct: float | None
    parts: int
    performance_pct: float | None
    defects: int
    quality_pct: float | None
    oee_pct: float | None
    #: Sababi kiritilmagan to'xtashlar (bugun) — operator oynani yopib ketgan bo'lsa ko'rinadi
    pending_reasons: int
    #: KROMKA: oxirgi o'lchov (mm, hukm, detal nomi). Boshqa postda bo'sh
    last_mm: float | None = None
    last_verdict: str | None = None
    last_part: str | None = None
