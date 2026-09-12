from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Case, Date, DateTime, ForeignKey, Index, Numeric, String, Text, case, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import FileKind, OrderPriority, OrderStatus, RouteSource, db_enum


class Order(BaseModel):
    """Production order. Lifecycle: DRAFT → TECHNICAL_REVIEW → PRODUCTION → COMPLETED → DELIVERED."""

    __tablename__ = "order"

    __table_args__ = (Index("ix_order_number", "number", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    number: Mapped[str] = mapped_column(String(20), kw_only=True)  # B-2026-001, auto
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), index=True, kw_only=True)
    status: Mapped[OrderStatus] = mapped_column(
        db_enum(OrderStatus), default=OrderStatus.DRAFT, index=True, kw_only=True
    )
    priority: Mapped[OrderPriority] = mapped_column(db_enum(OrderPriority), default=OrderPriority.MEDIUM, kw_only=True)
    deadline: Mapped[date | None] = mapped_column(Date, default=None, kw_only=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    # Boshlang'ich to'lov (avans) — manager buyurtma ochishda kiritadi
    advance_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)

    # .project file metadata (set by texnolog upload; file name is informational only)
    project_uuid: Mapped[str | None] = mapped_column(String(64), default=None, kw_only=True)
    project_name: Mapped[str | None] = mapped_column(String(255), default=None, kw_only=True)
    project_loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)

    # Cut map visual model built from CS data blob; rendered by ARRA terminal.
    cutmap: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None, kw_only=True)
    # Material consumption from the project file: [{name, code, kind, count, unit}]
    material_usage: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default_factory=list, kw_only=True)
    # Manager's machine choice per post: {"PRISADKA": 3, "ROVER": 5}
    machine_assignments: Mapped[dict[str, int]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    # Mijoz anketasi + o'lchov varag'i, xonalar bo'yicha (qog'oz forma o'rniga).
    # Manager to'ldiradi, texnolog o'qiydi va shunga qarab dizayn yasaydi. Sxema: schemas/orders.OrderSurvey
    survey: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None, kw_only=True)

    production_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)

    @property
    def needs_packaging(self) -> bool:
        """Anketadagi «Upakovka qilish» xizmati — marshrutga UPAKOVKA qadamini qo'shadimi.

        `survey` JSONB va eski yozuvda kalit umuman yo'q, shuning uchun o'qish
        shakli ehtiyotkor. Marshrut quruvchi uch joyda (ingest ikki marta,
        matritsa bir marta) shu qiymatga qaraydi — nusxalar ajralib ketmasin.
        """
        return bool((self.survey or {}).get("packaging"))


#: Ro'yxat/hisobot so'rovlarida KERAK EMAS bo'lgan og'ir JSONB ustunlar.
#: `defer()` bilan qoldiriladi — busiz 100 ta buyurtma reestri 2.2 MB kesish
#: xaritasini bazadan tortib, Python'da parse qilib, keyin tashlab yuborardi
#: (o'lchov: 284 ms -> 5 ms). Buyurtma kartochkasida ular baribir kerak,
#: shuning uchun ustunlar emas, faqat SHU so'rovlar cheklanadi.
ORDER_FAT_COLUMNS = (Order.cutmap, Order.survey, Order.material_usage, Order.machine_assignments)


class Product(BaseModel):
    """Furniture item inside an order — <good typeId="product">."""

    __tablename__ = "product"

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    code: Mapped[str] = mapped_column(String(50), kw_only=True)  # e.g. 301401
    name: Mapped[str] = mapped_column(String(255), kw_only=True)
    count: Mapped[int] = mapped_column(default=1, kw_only=True)


class Part(BaseModel):
    """Part definition — <part> inside product. Stable key: productCode_partCode."""

    __tablename__ = "part"

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True, kw_only=True)
    code: Mapped[str] = mapped_column(String(50), kw_only=True)  # e.g. 01_002
    name: Mapped[str] = mapped_column(String(255), kw_only=True)
    count: Mapped[int] = mapped_column(default=1, kw_only=True)
    length: Mapped[float | None] = mapped_column(default=None, kw_only=True)  # l, mm (finished)
    width: Mapped[float | None] = mapped_column(default=None, kw_only=True)  # w, mm
    thickness: Mapped[float | None] = mapped_column(default=None, kw_only=True)  # from sheet good t
    txt: Mapped[bool] = mapped_column(default=False, kw_only=True)  # texture lock
    material_name: Mapped[str | None] = mapped_column(String(150), default=None, kw_only=True)  # sheet good
    label_num: Mapped[int | None] = mapped_column(default=None, kw_only=True)  # CS stub order, 1-based
    # Edge banding per side: {"l": {"mat": "06-19 SASNA", "symbol": "A"}, "t": {...}} (ell/elr/elt/elb)
    edges: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    # Merged XNC summary: {"bores": N, "edge_bores": N, "grooves": N, "mills": N, "sides": 1|2}
    xnc_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)  # texnolog izohi
    #: Nostandart detal: marshrutini texnolog QO'LDA chizadi (Nostandart detallar tabi).
    #: Fayldan avtomatik marshrut olmaydi — roverdan chiqqan detal keyin bo'yalishi
    #: mumkinligi kabi holatlarni fayl bilmaydi. Standart detal: ARRA + kromka + prisadka.
    is_custom: Mapped[bool] = mapped_column(default=False, index=True, kw_only=True)
    #: Yig'ma buyum: bu MAYDA detal qaysi ASOSIY detalga biriktiriladi (stolyarkada
    #: yopishtiriladi va yaxlit buyumga aylanadi). Biriktirilgan detalning marshruti
    #: aynan birikish qadamida TUGAYDI — undan keyin qadoqlash ham, TMO ham faqat
    #: asosiy detalga tegishli, chunki alohida detal endi mavjud emas.
    #: Asosiy detalning skani biriktirilganlarnikini ham yopadi (scanning.py).
    assembly_parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("part.id"), default=None, index=True, kw_only=True
    )


#: TABLO va dashboard navbati faqat hajm hisoblaydi (metrics.part_volume:
#: length/width/count/edges). Bu ikkitasi butun ishlab chiqarish bo'yicha
#: o'qilib, tashlab yuborilardi. `edges` KERAK — u bu ro'yxatda yo'q.
PART_FAT_COLUMNS = (Part.xnc_summary, Part.note)


class PartInstance(BaseModel):
    """Physical copy of a part. QR = productCode_partCode_n; each copy tracked separately."""

    __tablename__ = "part_instance"

    __table_args__ = (
        # Detal ID GLOBAL unikal (docs/11) va shu indeks skan lookup'ini ham yopadi.
        # 2026-09-05 gacha predikatda `qr_text ~ '^B-...'` sharti bor edi — prefikssiz
        # eski qatorlar jonli buyurtmalar orasida takrorlanishi mumkin edi, ular
        # indeksdan tashqarida qolardi. Prodda bunday qator qolmadi (0), shart ketdi.
        # Bitta indeks yetadi: global unikal (order_id, qr_text) juftini ham qamraydi,
        # order bo'yicha skan esa `order_id` FK indeksidan yuradi.
        Index("ix_part_instance_qr_serial", "qr_text", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), index=True, kw_only=True)
    instance_no: Mapped[int] = mapped_column(kw_only=True)  # 1..count
    qr_text: Mapped[str] = mapped_column(String(120), kw_only=True)
    # Cut map cell binding: which pattern sheet / cell this copy occupies
    pattern_no: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    cell_index: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    label_printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    #: Chekni QAYSI POST chiqargan. Bekor qilish huquqi shunga bog'liq: chekni
    #: chiqargan post o'zi qaytaradi, boshqasi tegolmaydi. Marshrutdan taxmin
    #: qilib bo'lmaydi — bitta detalning chekini ARRA ham, ROVER ham chiqarishi
    #: mumkin, va chek chiqarish har doim ham skan yozmaydi.
    label_post_id: Mapped[int | None] = mapped_column(ForeignKey("post.id"), default=None, kw_only=True)


class PartRoute(BaseModel):
    """Marshrutning BITTA qadami: detal shu postdan shu navbatda o'tadi.
    QOLDIQ tez chiqishi uchun hisoblagichlar denormalizatsiya qilingan.

    Bitta post marshrutda BIR NECHA MARTA uchrashi mumkin (kromka -> prisadka -> kromka),
    shuning uchun yagonalik `(part_id, seq)` bo'yicha — post bo'yicha EMAS."""

    __tablename__ = "part_route"

    __table_args__ = (
        Index("ix_part_route_part_seq", "part_id", "seq", unique=True, postgresql_where=text("NOT is_deleted")),
        # Skan va terminal ro'yxatlari post bo'yicha qidiradi — yagona emas, faqat tezlik uchun
        Index("ix_part_route_part_post", "part_id", "post_id"),
        Index("ix_part_route_order_post", "order_id", "post_id"),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), kw_only=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    #: Marshrutdagi o'rni, 1 dan boshlanadi. Skan tartibi AYNAN shu bo'yicha tekshiriladi
    #: (postlarning global tartibi bilan emas — nostandart marshrut uni buzadi).
    seq: Mapped[int] = mapped_column(kw_only=True)
    #: Jarayon kodi 1..16 (PROCESS_POSTS; 15/16 — tizim qo'shadigan dum, TAIL_CODES).
    #: Post o'zi yetarli emas: STOLYARKA da 6 xil amal,
    #: KROMKA da 2 xil bor — operator qaysi biri kerakligini shu koddan biladi.
    process_code: Mapped[int] = mapped_column(kw_only=True)
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machine.id"), default=None, kw_only=True)
    source: Mapped[RouteSource] = mapped_column(db_enum(RouteSource), default=RouteSource.AUTO, kw_only=True)
    is_enabled: Mapped[bool] = mapped_column(default=True, kw_only=True)  # texnolog can switch off
    # Scans needed per instance at this post (KROMKA: sides count; else 1 — PRISADKA ham
    # bitta skan, ikki yuzli detalda ham: `giblab/models.py: prisadka_passes` 0 yoki 1 qaytaradi)
    per_instance: Mapped[int] = mapped_column(default=1, kw_only=True)
    total_required: Mapped[int] = mapped_column(default=0, kw_only=True)  # count × per_instance
    total_done: Mapped[int] = mapped_column(default=0, kw_only=True)


class OrderFile(BaseModel):
    """Stored file: uploaded .project, generated .scx per part, label PDFs, contract docs."""

    __tablename__ = "order_file"

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    # Har CNC skanida detalning SCX fayli shu ustun bo'yicha qidiriladi (scanning.py)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("part.id"), index=True, default=None, kw_only=True)
    kind: Mapped[FileKind] = mapped_column(db_enum(FileKind), kw_only=True)
    path: Mapped[str] = mapped_column(String(500), kw_only=True)
    filename: Mapped[str] = mapped_column(String(255), kw_only=True)
    size: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)


#: Buyurtma navbati: SHOSHILINCH birinchi, keyin muddat. Tsexda bitta tartib
#: bo'lishi kerak — ishchi terminalda ko'rgan navbat devordagi taxtadagi bilan
#: mos tushsin, aks holda "qaysi biri to'g'ri?" degan savol tug'iladi. Ilgari
#: taxta prioritetni umuman hisobga olmasdi va shoshilinch buyurtma 19 tadan
#: 16-o'rinda turib, ekran ostida kesilib qolishi mumkin edi.
PRIORITY_RANK: Case[int] = case(
    (Order.priority == OrderPriority.URGENT, 0),
    (Order.priority == OrderPriority.HIGH, 1),
    (Order.priority == OrderPriority.MEDIUM, 2),
    else_=3,
)


class WasteItem(BaseModel):
    """FOYDALI atxot (GibLab `business="true"`): saqlashga arziydigan yirik qoldiq.

    GibLab optimizatorning o'zi ajratadi — mayda qoldiq bu jadvalga tushmaydi,
    u o'tinga ketadi va cheki ham chiqarilmaydi (GibSaw xulqi bilan bir xil:
    mebelix.lbl dagi `business` bloki). Ombor moduli keyin shu jadval ustiga
    quriladi; hozircha vazifasi bitta — chek chiqarib ID ni yo'qotmaslik.
    """

    __tablename__ = "waste_item"

    __table_args__ = (Index("ix_waste_item_qr_text", "qr_text", unique=True, postgresql_where=text("NOT is_deleted")),)

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    material_name: Mapped[str] = mapped_column(String(150), kw_only=True)
    sheet_no: Mapped[int] = mapped_column(kw_only=True)  # material ichidagi list raqami
    length: Mapped[float] = mapped_column(kw_only=True)  # foydali o'lcham, mm
    width: Mapped[float] = mapped_column(kw_only=True)
    #: "ATX-{buyurtma}-{n}" — chekdagi QR. Detal QR'idan ataylab farqli prefiks:
    #: skan dvijoki uni detal deb qidirmasligi kerak.
    qr_text: Mapped[str] = mapped_column(String(120), kw_only=True)
    label_printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
