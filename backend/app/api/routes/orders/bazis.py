"""Bazis `.b3d` modellari va yig'uvchi uchun ochiq havola.

Texnolog `.project` YONIGA har mahsulotning Bazis faylini yuklaydi; buyurtmaga
bitta ochiq havola ochiladi va u ustaga yoki mijozga beriladi. Ochiq tomoni —
`api/routes/public.py`.

Yuklashda model brauzerga tayyor JSON'ga aylantiriladi va diskda saqlanadi:
ochiq sahifa parserni umuman ishga tushirmaydi (460 faylda 1.7 s gacha CPU).
"""

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.api.deps import ManagerOrTexnologUser, SessionDep, StaffReadUser, TexnologUser, client_ip
from app.core.config import upload_root
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Order, OrderFile, Product
from app.models.enums import FileKind
from app.schemas.bazis import BazisModelRead, BazisProductRead, BazisState
from app.schemas.common import Message
from app.services.bazis import BazisParseError, ParsedBazis, dump_model, read_b3d, thumbnail_png

from ._common import _get_order, _get_visible_order

router = APIRouter()

#: Namunalardagi eng katta fayl 20 MB. Ikki barobar zaxira qoldiramiz: undan
#: kattasi ochishda ~300 MB xotira talab qilardi.
MAX_BAZIS_FILE_SIZE = 40 * 1024 * 1024
#: Mahsulot kodi fayl nomiga aylanadi — yo'l bo'ylab chiqib ketmasligi uchun.
_XAVFSIZ_KOD = re.compile(r"[^A-Za-z0-9_-]")
#: 2026-09-27 gacha kodi buyurtmada yo'q fayl ham saqlanib, «mahsulot topilmadi»
#: matni `meta.warnings` ga yozilardi. Endi bunday fayl RAD etiladi; eski qatorlar
#: `matched=false` bo'lib ko'rinadi va ulardagi matn o'qishda tashlanadi — aks
#: holda panelda holat ikki marta chiqardi.
_TOPILMADI = "kodli mahsulot bu buyurtmada topilmadi"


def _tozala(code: str) -> str:
    """Kodni fayl nomiga yaroqli holga keltiradi. Bo'sh chiqishi MUMKIN."""
    return _XAVFSIZ_KOD.sub("", code)[:40]


def _kod_fayl(code: str) -> str:
    tozalangan = _tozala(code)
    if not tozalangan:
        raise HTTPException(status_code=422, detail="Bazis faylida mahsulot kodi yo'q — Bazisda kodni to'ldiring.")
    return tozalangan


def _nomi(nom: str) -> str:
    return " ".join(nom.split()).casefold()


def _mahsulotlar(products: list[Product]) -> str:
    """Xabar uchun: «01 shkaf» (120601), … — texnolog mahsulotni NOMIDAN taniydi, kod aniqlik uchun."""
    qism = ", ".join(f"«{p.name}» ({p.code})" for p in products[:6])
    return qism + (f" va yana {len(products) - 6} ta" if len(products) > 6 else "")


def _tayyorla(parsed: ParsedBazis) -> tuple[bytes, bytes | None]:
    """Diskka yoziladigan model JSON'i va eskiz — ikkalasi ham sof CPU."""
    return dump_model(parsed), thumbnail_png(parsed.thumbnail) if parsed.thumbnail else None


def model_paths(root: Path, order_id: int, code: str) -> tuple[Path, Path, Path]:
    """Bitta mahsulotning uchta fayli: manba, brauzer modeli, eskiz."""
    katalog = root / "bazis" / str(order_id)
    return katalog / f"{code}.b3d", katalog / f"{code}.json", katalog / f"{code}.png"


def _read(row: OrderFile, codes: set[str]) -> BazisModelRead:
    """`codes` — buyurtmadagi tirik mahsulot kodlari: bog'lanish HOZIRGI holatdan
    olinadi, yuklash paytidagi `meta.matched` dan emas (`.project` keyin qayta
    yuklansa u eskirib qolardi)."""
    code = str(row.meta.get("product_code") or "")
    return BazisModelRead(
        file_id=row.id,
        product_code=code,
        product_name=str(row.meta.get("product_name") or ""),
        filename=row.filename,
        size=row.size,
        panels=int(row.meta.get("panels") or 0),
        matched=code in codes,
        warnings=[w for w in row.meta.get("warnings") or [] if _TOPILMADI not in w],
        created_at=row.created_at,
    )


async def _models(db: SessionDep, order_id: int) -> list[OrderFile]:
    return list(
        (
            await db.execute(
                select(OrderFile)
                .where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.BAZIS,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
                .order_by(OrderFile.id)
            )
        )
        .scalars()
        .all()
    )


async def _products(db: SessionDep, order_id: int) -> list[Product]:
    return list(
        (
            await db.execute(
                select(Product)
                .where(Product.order_id == order_id, Product.is_deleted == False)  # noqa: E712
                .order_by(Product.id)
            )
        )
        .scalars()
        .all()
    )


async def _state(db: SessionDep, order: Order) -> BazisState:
    products = await _products(db, order.id)
    codes = {p.code for p in products}
    return BazisState(
        models=[_read(r, codes) for r in await _models(db, order.id)],
        products=[BazisProductRead(code=p.code, name=p.name, count=p.count) for p in products],
        share_token=order.share_token,
    )


@router.get("/{order_id}/bazis", response_model=BazisState, operation_id="read_order_bazis")
async def read_order_bazis(db: SessionDep, current_user: StaffReadUser, order_id: int) -> BazisState:
    """Buyurtmaning 3D modellari, mahsulotlari (qaysi biriga model yetishmaydi) va ochiq havolasi."""
    order = await _get_visible_order(db, current_user, order_id)
    return await _state(db, order)


@router.post("/{order_id}/bazis", response_model=BazisModelRead, status_code=201, operation_id="upload_order_bazis")
async def upload_order_bazis(
    db: SessionDep,
    current_user: TexnologUser,
    order_id: int,
    file: UploadFile,
    request: Request,
    product_code: str | None = None,
) -> BazisModelRead:
    """Bitta mahsulotning Bazis faylini yuklaydi.

    Bitta buyurtmada bir nechta bo'ladi — har mahsulotga bittadan. Bir xil
    kodli fayl qayta yuklansa eskisining o'rnini oladi.

    Ishlab chiqarishdagi buyurtmaga ham yuklanadi: model aynan yig'uv paytida,
    ya'ni ish tugagandan KEYIN kerak bo'ladi.

    Fayl `.project` dagi mahsulotga MOS bo'lishi shart — kod ham, nom ham (ikkalasi
    Bazisning bitta `Article` idan keladi). Mos kelmasa 409 va hech narsa yozilmaydi.
    `product_code` — panelda fayl QAYSI mahsulot qatoriga yuklangani: fayl boshqa
    kodli mahsulotniki bo'lsa (hatto shu buyurtmaniki bo'lsa ham) rad etiladi — texnolog
    bir qatorni to'ldirib, boshqasiga jimgina yozilib ketgani sezilmasin.
    """
    order = await _get_order(db, order_id)
    if not (file.filename or "").lower().endswith(".b3d"):
        raise HTTPException(status_code=422, detail="Faqat Bazis `.b3d` fayli qabul qilinadi.")
    # Parserdan (1.7 s gacha CPU) OLDIN: mahsulotsiz buyurtmada fayl baribir rad etilardi
    products = await _products(db, order_id)
    if not products:
        raise HTTPException(
            status_code=422,
            detail="Avval project faylni yuklang — Bazis fayllar uning mahsulotlariga bog'lanadi.",
        )
    maqsad: Product | None = None
    if product_code is not None:
        maqsad = next((p for p in products if p.code == product_code), None)
        if maqsad is None:
            raise NotFoundException("Bu mahsulot buyurtmada topilmadi — sahifani yangilang.")
    content = await file.read()
    if len(content) > MAX_BAZIS_FILE_SIZE:
        raise HTTPException(status_code=422, detail=f"Fayl {MAX_BAZIS_FILE_SIZE // 1024**2} MB dan katta bo'lmasin.")

    try:
        # Sof CPU: 460 faylda 1.7 s gacha. Event loop'da bajarilsa TABLO ham,
        # terminallar ham shu vaqtga muzlardi (`.project` bilan bir xil sabab).
        parsed = await run_in_threadpool(read_b3d, content)
    except BazisParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not parsed.panels:
        raise HTTPException(status_code=422, detail="Bu Bazis faylida bitta ham detal yo'q.")
    try:
        # Eskiz (to'kish, kesish, Lanczos, palitra) ham 100-225 ms CPU — u ham oqimda.
        model_json, eskiz_png = await run_in_threadpool(_tayyorla, parsed)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Bazis faylida buzuq son bor (NaN yoki cheksiz) — faylni Bazisda qayta saqlang."
        ) from None

    kod = _kod_fayl(parsed.code)
    # Bir buyurtmada bir xil kodli ikki mahsulot bo'lishi mumkin (parser takror
    # kodlarga ruxsat beradi, docs/11) — nomi mosi olinadi. Ilgari
    # `scalar_one_or_none()` shu holatda 500 berardi.
    faylda = f"«{parsed.name}» ({parsed.code})"
    bir_kodli = [p for p in products if p.code == parsed.code]
    if not bir_kodli:
        # Ilgari bunday fayl «bog'lanmagan» bo'lib SAQLANARDI: model ochiq havolada
        # chiqardi, lekin chekdagi Detal ID uning detallarini topmasdi (prodda 12
        # yuklashdan bittasi — B-2026-060 `120602`: `.project` da bunday mahsulot yo'q).
        raise HTTPException(
            status_code=409,
            detail=f"Bu Bazis fayli shu buyurtmaning project fayliga tegishli emas: faylda {faylda} mahsuloti "
            f"bor, project faylda esa {_mahsulotlar(products)}. To'g'ri buyurtmaning Bazis faylini tanlang.",
        )
    product = next((p for p in bir_kodli if _nomi(p.name) == _nomi(parsed.name)), None)
    if product is None:
        # Bazis raqamlari mijozlar orasida takrorlanadi: `2083 Ilyos aka` ham,
        # `2083 Anvar` ham `208301` kodli. Kod bo'yicha bog'lansa boshqa mijozning
        # TV zonasi bu buyurtmaning kupesi deb ko'rsatilardi (36 detal kodi mos,
        # o'lchami 0/36). `.project` dagi mahsulot nomi va `.b3d` dagi nom — ikkalasi
        # ham Bazisning `Article.Name` idan (GibLab eksport skripti), ya'ni to'g'ri
        # faylda ular mos keladi. 2026-09-27 gacha texnolog «Baribir yuklash» bilan
        # tasdiqlay olardi — prodda bir marta ham ishlatilmagan, olib tashlandi: nom
        # Bazisda rostdan o'zgargan bo'lsa, uni buyurtmadagi bilan tenglab qayta
        # eksport qilinadi.
        raise HTTPException(
            status_code=409,
            detail=f"Bu Bazis fayli project faylga mos emas: kodi bir xil ({parsed.code}), lekin nomi boshqa — "
            f"project faylda «{bir_kodli[0].name}», Bazis faylida «{parsed.name}». Bu boshqa mijozning fayli "
            "bo'lishi mumkin (Bazis raqamlari takrorlanadi). Nomni Bazisda o'zgartirgan bo'lsangiz, uni "
            "project fayldagi bilan bir xil qilib qayta eksport qiling.",
        )
    if maqsad is not None and maqsad.code != product.code:
        # Fayl shu buyurtmaniki, lekin BOSHQA mahsulotniki — noto'g'ri qatorga tashlangan.
        # Nom tekshiruvidan KEYIN: aks holda boshqa mijozning fayli «B qatoriga yuklang»
        # deb yuborilar, B qatori esa uni nomi uchun baribir rad etardi.
        raise HTTPException(
            status_code=409,
            detail=f"Bu fayl «{maqsad.name}» ({maqsad.code}) uchun emas — unda {faylda} mahsuloti bor. "
            f"Uni «{product.name}» qatoriga yuklang.",
        )

    ogohlar = list(parsed.warnings)

    root = upload_root()
    b3d, model, eskiz = model_paths(root, order_id, kod)
    b3d.parent.mkdir(parents=True, exist_ok=True)
    await run_in_threadpool(b3d.write_bytes, content)
    await run_in_threadpool(model.write_bytes, model_json)
    if eskiz_png is not None:
        await run_in_threadpool(eskiz.write_bytes, eskiz_png)
    else:
        # Eskizsiz fayl bilan almashtirilsa eskisi o'chadi — aks holda yangi yozuv uchun
        # oldingi faylning eskizi ko'rsatilardi (texnolog aynan shu bilan faylni tekshiradi)
        eskiz.unlink(missing_ok=True)

    # Solishtirish TOZALANGAN kod bo'yicha: `2083.01` va `208301` bir xil
    # faylga yoziladi, ya'ni eskisini almashtirmasak diskda bittasi ikkinchisini
    # jimgina bosib ketardi va o'chirishda ikkalasining fayli ham yo'qolardi.
    eski = [r for r in await _models(db, order_id) if _tozala(str(r.meta.get("product_code") or "")) == kod]
    for r in eski:
        r.is_deleted = True
    row = OrderFile(
        order_id=order_id,
        kind=FileKind.BAZIS,
        path=str(b3d.relative_to(root)),
        filename=(file.filename or f"{kod}.b3d")[:255],
        size=len(content),
        meta={
            "product_code": parsed.code,
            "product_name": product.name,
            "panels": parsed.part_count,
            # `matched` yozilmaydi — u o'qishda tirik mahsulotlardan hisoblanadi (`_read`);
            # 2026-09-27 gacha yozilgan qatorlarda bu kalit qolgan, hech kim o'qimaydi
            "warnings": ogohlar,
        },
    )
    db.add(row)
    await db.flush()
    log_action(
        db,
        module="orders",
        action="bazis_uploaded",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Bazis modeli yuklandi: {parsed.code} ({parsed.part_count} detal)",
        meta={"product_code": parsed.code, "replaced": len(eski), "warnings": ogohlar},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(row)
    return _read(row, {parsed.code})


@router.get("/{order_id}/bazis/{file_id}/thumb", operation_id="read_order_bazis_thumb")
async def read_order_bazis_thumb(
    db: SessionDep, current_user: StaffReadUser, order_id: int, file_id: int
) -> FileResponse:
    """Modelning eskizi — texnolog TO'G'RI faylni yuklaganini shundan ko'radi."""
    await _get_visible_order(db, current_user, order_id)
    row = next((r for r in await _models(db, order_id) if r.id == file_id), None)
    if row is None:
        raise NotFoundException("Model topilmadi.")
    yol = (upload_root() / row.path).with_suffix(".png")
    if not yol.is_file():
        raise NotFoundException("Eskiz topilmadi.")
    return FileResponse(yol, media_type="image/png")


@router.get("/{order_id}/bazis/{file_id}/model", operation_id="read_order_bazis_model")
async def read_order_bazis_model(
    db: SessionDep, current_user: StaffReadUser, order_id: int, file_id: int
) -> FileResponse:
    """Modelning brauzerga tayyor JSON'i — texnolog uni ochiq havolasiz, panelning
    o'zida ko'radi (ustaga aynan nima ketishini). Ochiq sahifadagi bilan bitta fayl."""
    await _get_visible_order(db, current_user, order_id)
    row = next((r for r in await _models(db, order_id) if r.id == file_id), None)
    if row is None:
        raise NotFoundException("Model topilmadi.")
    yol = (upload_root() / row.path).with_suffix(".json")
    if not yol.is_file():
        raise NotFoundException("Model topilmadi.")
    return FileResponse(yol, media_type="application/json")


@router.post("/{order_id}/bazis/share", response_model=BazisState, operation_id="open_order_share")
async def open_order_share(
    db: SessionDep, current_user: ManagerOrTexnologUser, order_id: int, request: Request
) -> BazisState:
    """Ochiq havolani ochadi yoki YANGILAYDI.

    Yangilash eski havolani o'lik qiladi — havola noto'g'ri odamga ketib
    qolganda yagona chora shu. Menejerga ham ochiq: havolani mijozga ko'pincha
    u uzatadi.
    """
    order = await _get_order(db, order_id)
    yangi = order.share_token is not None
    order.share_token = uuid4().hex
    log_action(
        db,
        module="orders",
        action="share_opened",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"3D havola {'yangilandi' if yangi else 'ochildi'}: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    return await _state(db, order)


@router.delete("/{order_id}/bazis/share", response_model=Message, operation_id="close_order_share")
async def close_order_share(
    db: SessionDep, current_user: ManagerOrTexnologUser, order_id: int, request: Request
) -> Message:
    """Havolani yopadi — ochilgan manzil shu zahoti 404 bera boshlaydi."""
    order: Order = await _get_order(db, order_id)
    if order.share_token is None:
        raise NotFoundException("Bu buyurtmada ochiq havola yo'q.")
    order.share_token = None
    log_action(
        db,
        module="orders",
        action="share_closed",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"3D havola yopildi: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Havola yopildi.")


# NOTE: `/bazis/share` dan KEYIN turishi shart — aks holda DELETE .../share
# `file_id` deb o'qiladi va 422 qaytaradi (`orders/__init__.py` dagi qoida).
@router.delete("/{order_id}/bazis/{file_id}", response_model=Message, operation_id="delete_order_bazis")
async def delete_order_bazis(
    db: SessionDep, current_user: TexnologUser, order_id: int, file_id: int, request: Request
) -> Message:
    """Modelni olib tashlaydi. Havola ochiq qolsa, qolgan modellar ko'rinaveradi."""
    await _get_order(db, order_id)
    row = next((r for r in await _models(db, order_id) if r.id == file_id), None)
    if row is None:
        raise NotFoundException("Model topilmadi.")
    row.is_deleted = True
    kod = _tozala(str(row.meta.get("product_code") or ""))
    if kod:
        for p in model_paths(upload_root(), order_id, kod):
            p.unlink(missing_ok=True)
    log_action(
        db,
        module="orders",
        action="bazis_deleted",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Bazis modeli o'chirildi: {row.meta.get('product_code')}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Model o'chirildi.")
