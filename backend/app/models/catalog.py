from decimal import Decimal
from typing import Any

from sqlalchemy import Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class CatalogItem(BaseModel):
    """Mahsulotlar ombori katalogi — bitta pozitsiya (`M-LD-054-03`).

    KODI — yagona haqiqiy kalit. U to'rt qismdan iborat va HECH QACHON o'zgarmaydi
    (katalog qoidasi, `docs/14` §1): katalog harfi, guruh, model raqami, variant
    raqami. Qismlar alohida ustun bo'lib ham yotadi — kategoriya daraxti va
    saralash o'shalardan quriladi, matnni qayta bo'lish shart emas.

    Nega BITTA jadval: M (material), F (furnitura) va X (xizmat) bir xil kod
    tuzilishiga, bir xil narx va qoldiq ustunlariga ega. Uchta jadval bo'lsa har
    so'rov `UNION` bo'lardi, kod unikalligini esa hech kim ushlab turolmasdi —
    «bir kod = bir mahsulot» qoidasi aynan shu jadvaldagi unikal indeks.

    `extra` — varaqdan kelgan, lekin ustun bo'lishga arzimaydigan maydonlar
    (rang, xarakteristika, `1 list m²`, marja, ishlab chiqaruvchi). Ular
    ko'rsatiladi, lekin ular bo'yicha qidirilmaydi va hisob yuritilmaydi.
    """

    __tablename__ = "catalog_item"

    __table_args__ = (
        # Kategoriya daraxti (katalog -> guruh) va guruh ichidagi tartib
        Index("ix_catalog_item_group", "catalog", "group_code", "model_no", "variant_no"),
    )

    #: To'liq variant kodi — `M-LD-054-03`. Katalogning yagona identifikatori.
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, kw_only=True)
    #: Katalog harfi: `M` material, `F` furnitura, `X` xizmat
    catalog: Mapped[str] = mapped_column(String(1), kw_only=True)
    #: Guruh kodi (`LD`, `RC`, `PR` ...) va uning nomi — nomi kodda emas, varaqda
    group_code: Mapped[str] = mapped_column(String(2), kw_only=True)
    group_name: Mapped[str] = mapped_column(String(60), kw_only=True)
    model_no: Mapped[int] = mapped_column(kw_only=True)
    variant_no: Mapped[int] = mapped_column(kw_only=True)

    name: Mapped[str] = mapped_column(String(200), kw_only=True)
    #: `list`, `dona`, `metr` — xizmatlarda bo'lmasligi mumkin
    unit: Mapped[str | None] = mapped_column(String(10), default=None, kw_only=True)
    #: `2750x1830x16` ko'rinishidagi o'lcham MATNI: u hujjatlarda shu ko'rinishda
    #: yuritiladi, uzunlik/eni alohida kerak bo'lgan joy hozircha yo'q
    size_text: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), default=None, kw_only=True)
    #: Zavod artikuli (dekorlarda `117003`, furnituralarda yetkazuvchiniki)
    article: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)

    #: Dekor bo'yicha mahsulotlar (M-LD / M-LM) uchun — dekor raqami, nomi, matritsasi
    decor_no: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    decor_name: Mapped[str | None] = mapped_column(String(80), default=None, kw_only=True)
    matrix: Mapped[str | None] = mapped_column(String(20), default=None, kw_only=True)
    image_url: Mapped[str | None] = mapped_column(String(300), default=None, kw_only=True)

    #: Ombor qoldig'i. `Numeric`, `float` emas: `metr` va `m²` da o'lchanadigan
    #: pozitsiyalar bor, pul bilan bir jadvalda suzuvchi nuqta xatosi kerak emas
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0), kw_only=True)
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None, kw_only=True)
    location: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    #: `Aktiv` / `Arxiv` — kod band qoladi, pozitsiya esa ro'yxatdan chiqadi
    status: Mapped[str] = mapped_column(String(10), default="Aktiv", kw_only=True)

    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)

    # --- Ombor narxi (docs/14 §8, 2026-10-16): narx katalog varag'idan emas, OMBORDAN boshqariladi ---
    #: Qisqa tavsif — rang / o'lcham (`bronza · 128 mm`). Ro'yxatda nom ostida, qidiruvda ham
    description: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
    #: Xarid narxi DOLLARDA (kirim dollarda yoziladi). Bo'lsa `purchase_price` = shu × kurs —
    #: kurs o'zgarganda so'mdagi xarid va ustamali sotuv narxi qayta hisoblanadi
    purchase_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), default=None, kw_only=True)
    #: LDSP/LMDF dekor sinfi: `S` standart, `M` medium, `P` premium — sotuv narxi sinf narxidan
    tier: Mapped[str | None] = mapped_column(String(1), default=None, kw_only=True)
    #: Furnitura ustamasi (%) — shu pozitsiyaga xos; bo'lmasa guruhniki, u ham bo'lmasa umumiy
    markup_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None, kw_only=True)
    #: Material «zaxiraga olingan» — kam qoldiq ogohlantirishi FAQAT shularda (2 000+ dekorning
    #: hammasi omborda turmaydi, aks holda ro'yxat doim qizil bo'lardi)
    tracked: Mapped[bool] = mapped_column(default=False, server_default="false", kw_only=True)
