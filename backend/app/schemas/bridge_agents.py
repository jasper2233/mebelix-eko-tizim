from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BridgeAgentRead(BaseModel):
    """Admin ro'yxati. pair_code faqat hali ulanmagan agentda bo'ladi —
    ro'yxatning o'zi admin-only, shuning uchun kodni ko'rsatish xavfsiz."""

    id: int
    name: str
    paired: bool
    pair_code: str | None
    pair_expires_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    # Skan-forvard: stanok skaneri MES'ga shu ish markazi nomidan yoziladi
    machine_id: int | None = None
    machine_name: str | None = None
    # Agent exe versiyasi (oxirgi ulanishdan); null = eski (headersiz) exe
    version: str | None = None
    # False = printersiz stansiya (skan-forvard) — chek navbatidan ish olmaydi
    can_print: bool = True


class BridgeAgentCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Arrachi monoblok"])]
    #: Ish markazi YARATISHDA so'raladi (ilgari alohida qadam edi va muntazam
    #: esdan chiqib qolardi). IXTIYORIY: chek chiqarish va skan-forvard uchun u
    #: shart (usiz `require_printer` -> 422, `bridge_scan` -> 409), lekin
    #: OFISDAGI beyjik printeriga ish markazi kerak emas — `printing_agents`
    #: agentni faqat `can_print` bo'yicha tanlaydi.
    machine_id: int | None = None


class BridgeAgentUpdate(BaseModel):
    """Ish markazi bog'lami va chek-chiqarish belgisi. can_print=None = tegilmaydi
    (machine_id'da None "olib tashlash" degani, shuning uchun sentinel farqli)."""

    machine_id: int | None = None
    can_print: bool | None = None


class BridgeScanRequest(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]
    client_event_id: Annotated[str, Field(min_length=8, max_length=64)]


class BridgePairRequest(BaseModel):
    code: Annotated[str, Field(min_length=4, max_length=16)]


class BridgePairResponse(BaseModel):
    """Token FAQAT shu javobda beriladi — bazada sha256 xeshi qoladi."""

    token: str
    name: str
    #: Bog'langan stanok nomi — agent ulanish xabarida ko'rsatadi (skan-forvard
    #: qaysi stanok nomidan yozilishini operator darhol bilsin); bog'lanmagan — None
    machine_name: str | None = None


class AgentRelease(BaseModel):
    """CI qurgan oxirgi agent exe haqida ma'lumot (`agent-dist/version.json`)."""

    version: str
    sha256: str


class BridgeLogPush(BaseModel):
    """Agent o'z log satrlarini yuboradi (diagnostika).

    Chegara ataylab qat'iy: agent ishlamay qolganda log oqimi sekundiga bir necha
    marta kelishi mumkin, server esa ularni faqat oxirgi 200 tasini saqlaydi."""

    lines: list[str] = Field(default_factory=list, max_length=200)


class AndonEventIn(BaseModel):
    """Pico hodisasi — agent uni o'zgartirmasdan uzatadi, faqat `ts` ni (USB rejimda
    Pico soatsiz), kromka uchun esa `session`/`seq` ni ham (proshivka v1.22 dan ular
    Pico'ning `xb`/`xq` si, undan oldingisida agent o'zi beradi).

    Qolgan maydonlar (lamps, wait_s, process_s, L, L1, L2, kod, holat ...) `extra="allow"`
    bilan `payload` ga TO'LIQ tushadi — hisob-kitob ularni shu yerdan oladi, ya'ni har
    firmware o'zgarishida sxemani yangilash shart emas."""

    model_config = ConfigDict(extra="allow")

    #: PRISADKA signal ustuni — `state` (chiroq holati) va `cycle` (detal sikli);
    #: KROMKA o'lchash stansiyasi — `olchov`, `uskuna` (RUN kirishi), `tezlik`,
    #: `ogoh` (datchik nosozligi), `avariya_toxtash`, `boot`, `tiqilish` (proshivka v1.16:
    #: detallar birga o'tgan yoki datchik ostida turib qolgan — o'lchov chiqmagan);
    #: ROVER (CNC 2130) —
    #: `rover` (Pico o'zi o'lchab tugatgan davr: POWER_ON, SPINDLE_IDLE, AUTO_SHUTDOWN ...)
    #: va o'sha stanokning RUN o'zgarishi uchun o'sha `uskuna`. Ro'yxat YOPIQ: noma'lum
    #: turni hech kim o'qimasdi, agent esa xatoni ko'rmay navbatni bo'shatardi.
    type: Literal[
        "state", "cycle", "olchov", "uskuna", "tezlik", "ogoh", "avariya_toxtash", "boot", "tiqilish", "rover"
    ]
    session: Annotated[str, Field(min_length=1, max_length=16, pattern=r"^[0-9A-Za-z_-]+$")]
    seq: Annotated[int, Field(ge=0, le=2_000_000_000)]
    ts: Annotated[int, Field(ge=0, le=4_102_444_800)] = 0
    state: Annotated[str | None, Field(max_length=16, pattern=r"^[A-Z_]+$")] = None
    prev_state: Annotated[str | None, Field(max_length=16, pattern=r"^[A-Z_]+$")] = None
    # int4 ustun: chegara tekshiruvda bo'lmasa, katta qiymat INSERT da yiqilib BUTUN partiyani 500 qilardi
    prev_duration_s: Annotated[int | None, Field(ge=0, le=2_000_000_000)] = None


class AndonCurrent(BaseModel):
    """Stanokning JONLI holati — agent oxirgi hodisa va snapshot'dan o'zi yig'adi."""

    state: Annotated[str, Field(min_length=1, max_length=16)]
    since: Annotated[int, Field(ge=0, le=4_102_444_800)]  # holat boshlangan vaqt, unix soniya
    lamps: dict[str, str] = Field(default_factory=dict)
    part_count: int | None = None


class AndonPush(BaseModel):
    """Agent partiyasi: navbatdagi hodisalar + jonli holat.

    `events` ATAYLAB xom lug'atlar: bitta buzuq hodisa butun partiyani 422 bilan rad
    etsa, agent uni qayta-qayta yuborib navbatni abadiy to'sib qo'yardi. Har hodisa
    serverda alohida tekshiriladi, buzug'i sanab o'tkazib yuboriladi (`skipped`)."""

    events: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    current: AndonCurrent | None = None


class AndonPushResult(BaseModel):
    accepted: int  # yangi yozilgan hodisalar
    duplicates: int  # allaqachon bor (agent qayta yuborgan)
    skipped: int  # buzuq — yozilmadi
