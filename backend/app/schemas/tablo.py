"""TABLO (TZ 9) javob sxemalari: buyurtma × bosqich matritsasi va drill-down."""

from datetime import date

from pydantic import BaseModel


class StageAgg(BaseModel):
    post_id: int
    done: int
    total: int
    volume_total: float  # unit amount (m² / meter / dona) per post unit
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
    status: str
    stages: dict[str, StageAgg]  # keyed by post code
    #: Shu buyurtma oxirgi marta qimirlaganidan beri TSEX NECHA KUN ishlagani.
    #: `None` — hali bironta ham amal bajarilmagan (uzatilgan, tegilmagan);
    #: `0` — bugun qimirlagan. Ikkalasi ham "0 kun" emas, boshqa-boshqa fakt.
    #:
    #: Kalendar kuni EMAS, ataylab: tsex dam olgan kun hisobga olinmasa,
    #: dushanba ertalab butun taxta "2 kun to'xtagan" bo'lib yonardi va belgi
    #: ma'nosini yo'qotardi. "Tsex ishlagan kun" = o'sha kuni bironta skan
    #: bo'lgan kun, ya'ni bayram/ta'til/to'xtash ro'yxatini yuritish kerak emas.
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
