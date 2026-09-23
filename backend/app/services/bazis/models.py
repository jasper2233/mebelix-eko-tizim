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
    #: Tashqi chegara (mm, panelning o'z tekisligida), segmentlar uchlari bo'yicha
    #: ulangan halqa. To'rtburchakda 4 nuqta; yoy nuqtalarga bo'lingan.
    poly: list[list[float]] = field(default_factory=list)
    #: Chiziq/yoydan chizilgan ichki kesmalar (rakovina, plita teshigi) — har biri halqa.
    holes: list[list[list[float]]] = field(default_factory=list)
    #: Paneldagi aylana kesmalar `[cx, cy, r]` — rozetka, kabel teshigi.
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
    #: Harakat birligi — bitta eshik yoki tortmaning BARCHA panellari (tortma:
    #: fasad + quti, 5 panel). Brauzer ularni birga ochadi: kaskadda ham, bitta
    #: eshikni ochganda ham. Harakatsiz panelda `None`.
    group: int | None = None
    #: Bazis turi: `4002` panel, `2004` profil (cho'zilgan jism — muzlatkich
    #: korpusi, tortma relsi), `999` egilgan panel (rakovina kosasi, rels
    #: tutqich). Uchalasi ham kontur + qalinlik — geometriyasi bir xil.
    kind: int = 4002
    #: Profil uchlarini kesuvchi tekisliklar `[nx, ny, nz, d]` (o'z fazosida,
    #: `n·p + d >= 0` qoladi) — 45° li burchak ulanishlari. 460 faylda 163 profilda.
    clip: list[list[float]] = field(default_factory=list)
    #: Tekstura tolasi kontur X bo'ylabmi (`TexDir = 1`). Aks holda — Y bo'ylab.
    grain_x: bool = False

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
class BazisMeshPart:
    """Uchburchaklar to'plamining bitta materialli qismi (mahsulot o'z fazosida, mm)."""

    mat_name: str
    #: Uchlar `[x, y, z, ...]` va ularning normallari (Bazis faylda yozib qo'ygan)
    positions: list[float] = field(default_factory=list)
    normals: list[float] = field(default_factory=list)
    #: Uchburchaklar — `positions` dagi uch indekslari, uchtadan
    indices: list[int] = field(default_factory=list)


@dataclass
class BazisMesh:
    """Furnitura yoki texnikaning geometriyasi — BIR MARTA saqlanadi, joylari alohida."""

    parts: list[BazisMeshPart] = field(default_factory=list)


@dataclass
class BazisFurniture:
    """Furnitura/texnika nusxasi: qaysi mesh, qayerda. Detal EMAS — kodi yo'q,
    qidiruvga kirmaydi; eshikka o'rnatilgan bo'lsa eshik bilan birga ochiladi."""

    name: str
    #: `ParsedBazis.meshes` dagi indeks
    mesh: int
    pos: list[float] = field(default_factory=list)
    quat: list[float] = field(default_factory=list)
    pos_open: list[float] = field(default_factory=list)
    quat_open: list[float] = field(default_factory=list)
    group: int | None = None

    @property
    def animated(self) -> bool:
        return self.pos_open != self.pos or self.quat_open != self.quat


@dataclass
class BazisDim:
    """Bazischi qo'ygan o'lcham chizig'i (`Размер`, Obj 9000) — mahsulot fazosida, mm."""

    #: Yozuvdagi qiymat (`Value`; 22 namunada 127/127 da `Size` ga teng)
    value: float
    #: O'lchangan ikki nuqta (yopiq holatda)
    a: list[float]
    b: list[float]
    #: O'lcham chizig'ining ikkala nuqtadan surilishi — vektor, mm
    o: list[float]
    #: Harakat birligi — o'lcham eshik yoki tortma yig'masi ichida bo'lsa
    group: int | None = None


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
    #: Furnitura va texnika (tutqich, oyoq, ilgak, vityajka, aylanma jism)
    meshes: list[BazisMesh] = field(default_factory=list)
    furniture: list[BazisFurniture] = field(default_factory=list)
    #: Bazischining o'lchamlari (yashirilganlari kirmaydi)
    dims: list[BazisDim] = field(default_factory=list)
    #: O'qish to'liq bo'lmasa — nima o'qilmagani. Bo'sh = to'liq o'qildi.
    warnings: list[str] = field(default_factory=list)

    @property
    def coded_panels(self) -> list[BazisPanel]:
        return [p for p in self.panels if p.des]

    @property
    def part_count(self) -> int:
        """Kartochkadagi «N detal»: panellar va KODLI jismlar. Kodsiz profil —
        muzlatkich korpusi, rels — detal emas, texnika yoki furnitura."""
        return sum(1 for p in self.panels if p.kind == 4002 or p.des)
