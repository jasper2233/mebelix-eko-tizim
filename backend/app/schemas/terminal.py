from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderPriority, OrderStatus, PachkaStatus, PostCode, SessionStatus


class ShiftStart(BaseModel):
    """Smenani boshlash — IKKI yo'l, natijasi bir xil.

    `badge_id` — skaneri bor postda bitta harakat. `employee_id` — ekrandagi
    ro'yxatdan ismni bosish (ARRA da skaner yo'q: u yerda chek chiqarish skanning
    o'zi, ya'ni skaner faqat kirish uchun sotib olinardi).
    """

    badge_id: Annotated[str | None, Field(default=None, min_length=8, max_length=36)]
    employee_id: int | None = None
    #: Brigadaga QO'SHILISH. Sukut `False` — almashtiradi (chiqishni unutish
    #: xavfsiz tomonga og'sin).
    join: bool = False


class TerminalEmployee(BaseModel):
    """ "Kim ishlayapti?" ro'yxatidagi tugma."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    position: str | None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: str = ""
    machine_id: int | None
    post_id: int
    status: SessionStatus
    created_at: datetime
    ended_at: datetime | None
    #: Shu smena KIRGAN ODAMNING o'ziniki. Tsex hisobi bilan kirgan operator
    #: o'zini brigada chipida ko'rmasligi kerak - u kimligini login allaqachon
    #: aytgan, chip esa faqat QO'SHILGAN sherik uchun.
    is_me: bool = False


class TerminalContext(BaseModel):
    machine_id: int
    machine_name: str
    post_id: int
    post_code: PostCode
    post_name: str
    #: Brigada — ish markazidagi OCHIQ smenalar (ARRA da ikki kishi birga ishlaydi).
    #: Bo'sh ro'yxat: hali hech kim smenani boshlamagan.
    crew: list[SessionRead] = []
    #: None = bu ish markaziga agent biriktirilmagan (chip chiqmaydi); aks holda
    #: paneldagi bilan bir xil 6 daqiqalik oyna bo'yicha onlaynlik. can_print'siz
    #: (faqat skan-forvard) agent ham qamraladi: u o'lsa skanlar MES'ga jimgina
    #: tushmay qolardi. Jonli o'zgarish `bridge.connected/disconnected` dan.
    agent_online: bool | None = None
    #: Biriktirilgan agent chek chiqaradimi (ikonka tanlash uchun): True — printer,
    #: False — faqat skan-forvard. agent_online None bo'lsa ma'nosiz.
    agent_prints: bool = False


class TerminalOrderCard(BaseModel):
    """Terminal proyekt tanlagichi kartasi (/terminal/orders): done/total post turiga moslangan."""

    id: int
    number: str
    project_name: str | None
    deadline: date | None
    priority: OrderPriority
    done: int
    total: int
    materials: list[str] = []  # karta uchun: arrachi plita bo'yicha partiyalab kesadi
    sheets_total: int
    has_cutmap: bool


class QrOrderRef(BaseModel):
    """QR qaysi aktiv buyurtmaga tegishli (/terminal/qr/{qr}/order) — terminal o'sha sahifani ochadi."""

    order_id: int
    order_number: str


class KromkaInstance(BaseModel):
    """Bitta fizik nusxa KROMKA nazarida: nechta tomoni yopishtirilgan, arradan o'tganmi."""

    instance_id: int
    instance_no: int
    qr_text: str
    done: int  # shu nusxada bajarilgan kromka skanlari (tomonlar)
    arra_passed: bool  # chek chiqarilgan yoki ARRA skan bor — kesilgan hisoblanadi


class KromkaPartRow(BaseModel):
    part_id: int
    route_id: int  # marshrut qadami — ro'yxat kaliti
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    sides: int  # har nusxa uchun kerakli skanlar = kromkalanadigan tomonlar
    edges: dict[str, Any] = {}
    process_code: int  # 3 = Kromka, 4 = Fasat kromka, 5 = Oval kromka
    total_done: int
    total_required: int
    instances: list[KromkaInstance] = []


class KromkaOrderState(BaseModel):
    """KROMKA post sahifasi (proyekt ochilganda): faqat kromkali detallar."""

    order_id: int
    order_number: str
    parts: list[KromkaPartRow]


class PrisadkaFile(BaseModel):
    """Detalning SCX fayli — stanok kompyuteriga yuklab olish uchun."""

    id: int
    filename: str


class PrisadkaInstance(BaseModel):
    """Nusxa darajasi: QR chiqarish tugmasi va holat uchun."""

    instance_id: int
    qr_text: str
    label_printed: bool
    done: bool
    #: Nusxa bo'yicha skanlar: prisadkada bir nusxa 2 skan talab qilishi mumkin
    #: (`per_instance`) — chip yarim yo'lni ko'rsatsin (ilgari faqat done/undone edi)
    scans: int = 0
    need: int = 1


class PrisadkaPartRow(BaseModel):
    part_id: int
    route_id: int  # marshrut qadami — ro'yxat kaliti
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    done: int
    total: int
    files: list[PrisadkaFile] = []
    arra_route: bool  # marshrutida ARRA bormi — bo'lmasa QR chek shu sahifadan chiqadi (ROVER)
    instances: list[PrisadkaInstance] = []


class PrisadkaOrderState(BaseModel):
    """CNC post sahifasi (PRISADKA/ROVER): shu postga tegishli detallar + SCX fayllari."""

    order_id: int
    order_number: str
    project_name: str | None
    parts: list[PrisadkaPartRow]


class ScanRequest(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]
    client_event_id: Annotated[str, Field(min_length=8, max_length=64)]  # client UUID


class ScanResult(BaseModel):
    scan_id: int
    duplicate: bool = False  # idempotent replay — already counted, not an error
    qr_text: str
    part_code: str
    part_name: str
    instance_no: int
    qoldiq: int  # remaining for this part at this post after the scan
    order_stage_completed: bool = False
    order_completed: bool = False


class ScanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_text: str = ""
    part_code: str = ""
    is_cancelled: bool
    created_at: datetime


class CutmapInstanceState(BaseModel):
    instance_id: int
    instance_no: int
    qr_text: str
    pattern_no: int | None
    cell_index: int | None
    done: bool
    label_printed_at: datetime | None
    #: Nostandart detal (`Part.is_custom`) — marshrutini texnolog qo'lda chizgan.
    #: Xaritada binafsha (`PART_CUSTOM`) bo'lib turadi: arrachi uni odatdagi detal deb o'ylamasin,
    #: chunki marshruti arradan boshlanmasligi ham mumkin (o'shanda skan qabul
    #: qilinmaydi va arrachi "plan topilmadi" xatosiga uchrardi).
    custom: bool = False
    #: Detal marshrutida yoqilgan ARRA qadami bormi. Listning EGASI shundan
    #: aniqlanadi: giyotina kesimi listni chetdan chetgacha kesadi, ya'ni bitta
    #: katakni chetlab o'tib bo'lmaydi — list yo butunlay arraniki, yo butunlay
    #: roverniki (rover butun listni o'zi nesting bilan kesadi). Arrachida
    #: roverning listlari xira, roverchida esa faqat o'ziniki ko'rinadi.
    arra_route: bool = True


class CutmapDim(BaseModel):
    """Root strip dimension chain entry (GibSaw style)."""

    ax: Literal["X", "Y"]
    a: float
    b: float
    v: float


class CutmapCut(BaseModel):
    """Guillotine cut line — edge to edge across its parent region."""

    x1: float
    y1: float
    x2: float
    y2: float


class CutmapCell(BaseModel):
    """Listdagi bitta fizik katak: detal yoki ro'yxatga olingan atxot.

    Ikkala tur BITTA model bilan tasvirlanadi. Atxot katagida detal maydonlari
    (`key`, `num`, `rot`, `eW`, `eH`) bo'lmaydi — ularni ixtiyoriy qilib qo'yish
    ajratilgan union'dan sodda va saqlangan eski JSON'ni rad etmaydi (bu yerda
    validatsiya xatosi butun xaritani 500 bilan yiqitardi). Ajratish `waste`
    bo'yicha.
    """

    cell: int
    x: float
    y: float
    w: float
    h: float
    id: int
    name: str
    waste: bool
    #: Foydali atxot raqami (`WasteItem` bilan bog'laydi) — faqat `business` atxotda
    atx: int | None = None
    #: GibLab "business" bayrog'i: saqlanadigan foydali qoldiq
    business: bool | None = None
    key: str | None = None
    num: int | None = None
    rot: bool = False
    #: Qirra belgilari joylashgan holatda: eW = [chap, o'ng], eH = [tepa, past].
    eW: list[str | None] | None = None
    eH: list[str | None] | None = None
    txt: bool = False


class CutmapSheet(BaseModel):
    """Bitta kesish sxemasi. `mult` — u nechta bir xil listni bildiradi."""

    no: int
    L: float
    W: float
    mult: int
    parts: list[CutmapCell]
    dims: list[CutmapDim] = Field(default_factory=list)
    cuts: list[CutmapCut] = Field(default_factory=list)


class CutmapMaterial(BaseModel):
    """Bitta CS operatsiyasi = bitta list materiali (reja ko'rsatkichlari chiqarilmaydi)."""

    name: str
    sheets: list[CutmapSheet] = Field(default_factory=list)


class CutmapBore(BaseModel):
    """Yuza teshigi: detal tekisligida (x, y)."""

    x: float
    y: float
    d: float


class CutmapEdgeBore(BaseModel):
    """Qirra teshigi: `side` — l/r/t/b, `pos` — o'sha qirra bo'ylab masofa."""

    side: str
    pos: float
    d: float
    dp: float


class CutmapHole(BaseModel):
    """Bitta detalning birlashtirilgan XNC qatlami."""

    l: float | None = None  # noqa: E741 — model kaliti, `length` deb o'zgartirib bo'lmaydi
    w: float | None = None
    bores: list[CutmapBore] = Field(default_factory=list)
    edge: list[CutmapEdgeBore] = Field(default_factory=list)


class CutmapModel(BaseModel):
    """`order.cutmap` — kesish xaritasining vizual modeli (`build_cutmap` chiqishi).

    Ilgari bu `dict[str, Any]` edi, ya'ni generatsiya qilingan klient ham bo'sh
    tur berardi va frontend butun xaritani `any` ustida yozishga majbur edi —
    `p.cell`, `s.no` kabi murojaatlar umuman tekshirilmasdi.
    """

    materials: list[CutmapMaterial] = Field(default_factory=list)
    #: Kalit — `file_part_id` matn ko'rinishida (JSON obyekt kaliti butun son bo'lolmaydi).
    holes: dict[str, CutmapHole] = Field(default_factory=dict)


class CutmapWasteItem(BaseModel):
    """Foydali atxot yozuvi — kesish xaritasidagi `atx` raqamiga bog'lanadi."""

    id: int
    qr_text: str
    sheet_no: int
    length: float
    width: float
    label_printed_at: datetime | None = None


class CutmapState(BaseModel):
    """ARRA cut-map screen payload: the visual model + live per-cell state."""

    order_id: int
    order_number: str
    model: CutmapModel | None
    instances: list[CutmapInstanceState]
    #: Foydali atxotlar (`business`) — katakdagi `atx` raqami orqali bog'lanadi
    waste_items: list[CutmapWasteItem] = []


class PostQueueRow(BaseModel):
    """Bitta NUSXA post navbatida (BOYOQ, keyinchalik STOLYARKA ham).

    Nusxa darajasida, chunki ish har bir buyumda alohida bajariladi: bo'yoqchi
    oltita eshikning to'rttasini bo'yab, qolganini ertaga qilishi mumkin.
    """

    instance_id: int
    qr_text: str
    part_code: str  # productCode_partCode
    part_name: str
    length: float | None
    width: float | None
    thickness: float | None
    #: Material nomi — bo'yoqchi uchun bu RANG. Busiz u nimaga bo'yashini bilmaydi.
    material: str | None
    note: str | None  # texnolog izohi
    process_code: int
    ready: bool  # oldingi bosqichlar tugadimi (tugamagan bo'lsa skan rad etiladi)
    stage: str  # oxirgi bajarilgan post nomi — detal hozir qayerda turibdi
    done: bool  # shu postdagi qadam yopilgan
    assembly: list[str] = []  # yig'ma buyum: biriktirilgan mayda detallar


class PostQueueState(BaseModel):
    """Post navbati sahifasi: proyekt tanlangach shu post uchun kelgan nusxalar."""

    order_id: int
    order_number: str
    project_name: str | None
    post_code: PostCode
    rows: list[PostQueueRow]


class PachkaItemRow(BaseModel):
    """Qadoq ichidagi bitta nusxa."""

    instance_id: int
    qr_text: str
    part_code: str  # productCode_partCode
    part_name: str
    length: float | None
    width: float | None
    thickness: float | None
    weight_kg: float  # taxminiy: hajm × zichlik


class PachkaRow(BaseModel):
    id: int
    code: str
    status: PachkaStatus
    items: list[PachkaItemRow] = []
    weight_kg: float = 0  # taxminiy jami — faqat KO'RSATILADI, hech narsani bloklamaydi


class UpakovkaPending(BaseModel):
    """Qadoqlanmagan tayyor detal: qadoqlovchi nimani yig'ish kerakligini shundan biladi."""

    instance_id: int
    qr_text: str
    part_code: str
    part_name: str
    ready: bool  # oldingi bosqichlar tugaganmi (tugamagan bo'lsa skan rad etiladi)


class UpakovkaOrderState(BaseModel):
    """UPAKOVKA post sahifasi: ochiq qadoqlar, yopilganlari va qolgan detallar."""

    order_id: int
    order_number: str
    project_name: str | None
    pachkas: list[PachkaRow] = []
    pending: list[UpakovkaPending] = []


class PachkaScan(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]


class TmoPending(BaseModel):
    """TMO ga hali qabul qilinmagan nusxa."""

    instance_id: int
    qr_text: str
    part_code: str
    part_name: str
    pachka_code: str | None  # qaysi qadoq ichida — qadoqsiz buyurtmada None
    ready: bool  # oldingi bosqichlar tugaganmi (tugamagan bo'lsa qabul rad etiladi)
    #: Tayyor bo'lmasa — detal HOZIR qaysi bosqichda turibdi ("Kromka", "Prisadka").
    #: Omborchiga "tsexda" degan umumiy so'z hech narsa bermaydi: u buyumni qidirib
    #: qaysi postga borishni bilishi kerak.
    stage: str = ""


class TmoDone(BaseModel):
    """TMO ga QABUL QILINGAN nusxa — skan qilingani.

    Ilgari qabul qilingan nusxa javobdan butunlay chiqib ketardi va ekranda
    faqat SHU SMENADAGI skanlar (React state) ko'rinardi: sahifa yangilansa
    omborchi o'zi qabul qilgan detallarni boshqa ko'rmasdi.
    """

    instance_id: int
    qr_text: str
    part_code: str
    part_name: str
    pachka_code: str | None  # qaysi qadoq cheki bilan kelgan (qadoqsizda None)
    accepted_at: datetime


class TmoOrderState(BaseModel):
    """TMO post sahifasi: qabul (skan) va topshirish tablari uchun bitta holat."""

    order_id: int
    order_number: str
    project_name: str | None
    order_status: OrderStatus
    total: int
    #: TMO ga JISMONAN yetib kelgan nusxalar — oldingi barcha bosqichlari tugaganlar.
    #: Skan qilinganlar ham shu songa kiradi (ular ham kelgan), ya'ni
    #: `accepted <= arrived <= total`. Omborchi "40 dan 20 tasi keldi, 10 tasi
    #: qabul qilindi" ni bir qarashda ko'rishi kerak.
    arrived: int
    accepted: int
    #: Qabul qilinganlar — "Qabul qilingan" tabi shundan chiziladi.
    done: list[TmoDone] = []
    #: Hali qabul qilinmaganlar: `ready=True` — TMO da turibdi (skanerlash mumkin),
    #: `ready=False` — hali tsexda (`stage` qaysi postdaligini aytadi).
    pending: list[TmoPending] = []
