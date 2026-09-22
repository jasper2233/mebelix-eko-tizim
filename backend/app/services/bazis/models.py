"""Bazis `.b3d` dan o'qilgan ma'lumot. Oddiy dataclass — ORM yo'q (`giblab` kabi)."""

from dataclasses import dataclass, field


class BazisParseError(Exception):
    """Fayl o'qilmadi. Xabar texnologga ko'rsatiladi, shuning uchun o'zbekcha."""


@dataclass
class BazisEdge:
    """Panelning bitta chetidagi kromka."""

    #: Kontur segmentining tartib raqami (`Butt.Elem`) — kromka QAYSI chetda
    #: ekani shundan bilinadi, yig'uvchiga eng kerakli ma'lumot.
    elem: int
    mat: str
    thick: float
    width: float


@dataclass
class BazisPanel:
    #: Bazis `Des` — `.project` dagi detal `code` ning AYNAN o'zi (`01_005`).
    #: Bo'sh bo'lishi MUMKIN: prodda o'lchandi, 22 fayldan birida 12/190 panel
    #: kodsiz edi. Kodsiz panel MES detali bilan bog'lanmaydi.
    des: str
    name: str
    #: `"nom\\rkod"` shaklida keladi, ajratilgan holda saqlanadi
    mat_name: str
    mat_code: str
    thick: float
    #: Kontur ko'pburchagi (mm, panelning o'z tekisligida). To'rtburchakda 4 nuqta.
    poly: list[list[float]] = field(default_factory=list)
    #: Paneldagi aylana kesmalar `[cx, cy, r]` — rozetka, rakovina, kabel teshigi.
    circles: list[list[float]] = field(default_factory=list)
    #: Konturning O'ZI aylana (yumaloq javon). `poly` ko'pburchak bilan
    #: taqribiy chizilgan, ya'ni `BazisEdge.elem` endi uning nuqtalariga mos
    #: kelmaydi — kromka chizig'i bunday panelda chizilmaydi.
    is_round: bool = False
    #: Mahsulot ichidagi DUNYO joylashuvi va burilishi (three.js uchun tayyor).
    pos: list[float] = field(default_factory=list)
    quat: list[float] = field(default_factory=list)
    #: Eshiklar/tortmalar OCHILGAN holatdagi o'sha ikkilik. Harakatsiz panelda
    #: `pos`/`quat` bilan bir xil — brauzer faqat ikkisi orasida yuradi.
    pos_open: list[float] = field(default_factory=list)
    quat_open: list[float] = field(default_factory=list)

    @property
    def animated(self) -> bool:
        return self.pos_open != self.pos or self.quat_open != self.quat

    edges: list[BazisEdge] = field(default_factory=list)

    @property
    def size(self) -> tuple[float, float]:
        """Konturning gabariti (eni, bo'yi) — Bazis buni alohida saqlamaydi."""
        if not self.poly:
            return 0.0, 0.0
        xs = [p[0] for p in self.poly]
        ys = [p[1] for p in self.poly]
        return round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)


@dataclass
class ParsedBazis:
    """Bitta `.b3d` fayl = bitta MAHSULOT (`.project` dagi `<good>`)."""

    #: Sarlavhadagi `Code` — `Product.code` ning AYNAN o'zi (`208301`). Bu
    #: bog'lanishning YAGONA ishonchli kaliti: detal kodlari (`01_001`)
    #: mahsulotlar ichida qayta boshlanadi, ya'ni ular bo'yicha bog'lab
    #: bo'lmaydi (prodda o'lchandi — har fayl har mahsulot bilan kesishadi).
    code: str
    #: `01 Kuxniya` — mahsulot nomi
    name: str
    #: `1207 Rustam` — loyiha nomi (buyurtmaga tegishli, mahsulotga emas)
    order_name: str
    #: Sarlavhadagi tayyor 256x256 PNG — mahsulotning ko'rinishi. Bazis uni
    #: o'zi chizib qo'yadi, ya'ni ochiq sahifadagi kartochka rasmi tekin.
    thumbnail: bytes
    panels: list[BazisPanel] = field(default_factory=list)
    #: O'qish to'liq bo'lmasa — nima o'qilmagani. Bo'sh = to'liq o'qildi.
    warnings: list[str] = field(default_factory=list)

    @property
    def coded_panels(self) -> list[BazisPanel]:
        return [p for p in self.panels if p.des]
