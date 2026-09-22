"""TABLO javob sxemalari: buyurtma × bosqich matritsasi va drill-down."""

from datetime import date, datetime

from pydantic import BaseModel


class StageAgg(BaseModel):
    post_id: int
    done: int
    total: int
    #: Shu postda HOZIR boshlash mumkin bo'lgan ish bormi — postlarning global
    #: tartibi emas, har detalning O'Z marshruti bo'yicha (`scanning.py` E004).
    #: Bir buyurtmada bir vaqtda bir nechtasi tayyor bo'ladi; o'lchov docs/03.
    ready: bool = False
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
    #: Post kodlari marshrut tartibida, TAKRORI bilan — FAQAT bu tartib ustun
    #: tartibidan (`order_index`) farq qilganda; `None` = qator chapdan o'ngga
    #: to'g'ri o'qiladi. Shart «nostandart» emas, ataylab — sabab docs/03 da.
    route_order: list[str] | None = None


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
    #: Hisob QAYSI lahzadan beri yuritilayotgani — kartada «08:00 dan beri» bo'lib
    #: yoziladi. Reja vaqti hozirgi lahzada kesiladi: 11:00 da 3 soat, 18:00 da to'liq smena
    window_from: datetime | None = None
    #: KROMKA: bugungi o'lchovlar hisobi — kutilgan tomonga MOS tushgani va
    #: tushmagani. Ikki raqam devor ekranida «lenta to'g'ri ishlayaptimi» degan
    #: savolga javob beradi; nolga teng bo'lsa qator umuman chizilmaydi.
    mos_count: int = 0
    nomos_count: int = 0
    #: KROMKA: oxirgi o'lchov (mm, hukm, detal nomi). Boshqa postda bo'sh
    last_mm: float | None = None
    last_verdict: str | None = None
    last_part: str | None = None


class TabloPeriod(BaseModel):
    """Bitta davr (bugun / hafta / oy) yakuni — kartani bosganda ochiladigan oynada."""

    label: str
    planned_s: int
    run_s: int
    availability_pct: float | None
    parts: int
    defects: int
    performance_pct: float | None
    quality_pct: float | None
    oee_pct: float | None


class TabloScanRow(BaseModel):
    """Stanokda bajarilgan oxirgi ishlardan bittasi."""

    at: datetime
    part_name: str
    qr_text: str
    employee: str | None


class TabloDefectRow(BaseModel):
    at: datetime
    part_name: str
    qr_text: str
    reason: str
    status: str  # pending | confirmed | rejected


class TabloStopRow(BaseModel):
    started_at: datetime
    ended_at: datetime | None
    seconds: int  # davom etayotgani hozirgacha
    kind: str  # off | fault | idle | lock
    reason: str | None  # None — sabab kiritilmagan


class TabloMachineDetail(BaseModel):
    """Stanok kartasini bosganda: uch davr OEE si va shu stanokning oxirgi hodisalari."""

    machine_id: int
    machine_name: str
    post_name: str
    periods: list[TabloPeriod]  # bugun, 7 kun, 30 kun
    recent_scans: list[TabloScanRow]
    defects: list[TabloDefectRow]
    stops: list[TabloStopRow]
