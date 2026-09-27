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
from app.schemas.bazis import BazisModelRead, BazisState
from app.schemas.common import Message
from app.services.bazis import BazisParseError, ParsedBazis, dump_model, read_b3d, thumbnail_png

from ._common import _get_order, _get_visible_order

router = APIRouter()

#: Namunalardagi eng katta fayl 20 MB. Ikki barobar zaxira qoldiramiz: undan
#: kattasi ochishda ~300 MB xotira talab qilardi.
MAX_BAZIS_FILE_SIZE = 40 * 1024 * 1024
#: Mahsulot kodi fayl nomiga aylanadi — yo'l bo'ylab chiqib ketmasligi uchun.
_XAVFSIZ_KOD = re.compile(r"[^A-Za-z0-9_-]")


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


def _tayyorla(parsed: ParsedBazis) -> tuple[bytes, bytes | None]:
    """Diskka yoziladigan model JSON'i va eskiz — ikkalasi ham sof CPU."""
    return dump_model(parsed), thumbnail_png(parsed.thumbnail) if parsed.thumbnail else None


def model_paths(root: Path, order_id: int, code: str) -> tuple[Path, Path, Path]:
    """Bitta mahsulotning uchta fayli: manba, brauzer modeli, eskiz."""
    katalog = root / "bazis" / str(order_id)
    return katalog / f"{code}.b3d", katalog / f"{code}.json", katalog / f"{code}.png"


def _read(row: OrderFile) -> BazisModelRead:
    return BazisModelRead(
        file_id=row.id,
        product_code=str(row.meta.get("product_code") or ""),
        product_name=str(row.meta.get("product_name") or ""),
        filename=row.filename,
        size=row.size,
        panels=int(row.meta.get("panels") or 0),
        matched=bool(row.meta.get("matched")),
        warnings=list(row.meta.get("warnings") or []),
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


@router.get("/{order_id}/bazis", response_model=BazisState, operation_id="read_order_bazis")
async def read_order_bazis(db: SessionDep, current_user: StaffReadUser, order_id: int) -> BazisState:
    """Buyurtmaning 3D modellari va ochiq havolasi."""
    order = await _get_visible_order(db, current_user, order_id)
    return BazisState(models=[_read(r) for r in await _models(db, order_id)], share_token=order.share_token)


@router.post("/{order_id}/bazis", response_model=BazisModelRead, status_code=201, operation_id="upload_order_bazis")
async def upload_order_bazis(
    db: SessionDep,
    current_user: TexnologUser,
    order_id: int,
    file: UploadFile,
    request: Request,
    tasdiq: bool = False,
) -> BazisModelRead:
    """Bitta mahsulotning Bazis faylini yuklaydi.

    Bitta buyurtmada bir nechta bo'ladi — har mahsulotga bittadan. Bir xil
    kodli fayl qayta yuklansa eskisining o'rnini oladi.

    Ishlab chiqarishdagi buyurtmaga ham yuklanadi: model aynan yig'uv paytida,
    ya'ni ish tugagandan KEYIN kerak bo'ladi.

    Fayldagi mahsulot nomi buyurtmanikidan farq qilsa — 409 va hech narsa
    yozilmaydi; texnolog nomlarni ko'rib tasdiqlasa (`tasdiq=true`) yuklanadi.
    """
    order = await _get_order(db, order_id)
    if not (file.filename or "").lower().endswith(".b3d"):
        raise HTTPException(status_code=422, detail="Faqat Bazis `.b3d` fayli qabul qilinadi.")
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
    product = (
        await db.execute(
            select(Product).where(
                Product.order_id == order_id,
                Product.code == parsed.code,
                Product.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()

    ogohlar = list(parsed.warnings)
    if product is None:
        ogohlar.append(
            f"`{parsed.code}` kodli mahsulot bu buyurtmada topilmadi — model ko'rinadi, "
            "lekin detallari MES detallari bilan bog'lanmaydi."
        )
    elif _nomi(product.name) != _nomi(parsed.name):
        # Bazis raqamlari mijozlar orasida takrorlanadi: `2083 Ilyos aka` ham,
        # `2083 Anvar` ham `208301` kodli. Kod bo'yicha bog'lansa boshqa mijozning
        # TV zonasi bu buyurtmaning kupesi deb ko'rsatilardi (36 detal kodi mos,
        # o'lchami 0/36). `.project` dagi mahsulot nomi va `.b3d` dagi nom — ikkalasi
        # ham Bazisning `Article.Name` idan (GibLab eksport skripti), ya'ni to'g'ri
        # faylda ular mos keladi.
        #
        # Ogohlantirish bilan yuklash YETMAYDI: model baribir shu kod bilan ochiq
        # sahifada chiqib, chekdagi Detal ID uning panellarini AYNAN topardi —
        # usta boshqa o'lchamdagi detalni ko'rardi. Shuning uchun FAYL YOZILMASDAN
        # rad etiladi; nom rostdan o'zgargan bo'lsa texnolog tasdiqlaydi.
        farq = f"Bu buyurtmadagi `{parsed.code}` mahsuloti «{product.name}», Bazis faylidagisi esa «{parsed.name}»"
        if not tasdiq:
            raise HTTPException(status_code=409, detail=f"{farq} — fayl boshqa buyurtmaniki bo'lishi mumkin.")
        ogohlar.append(f"{farq} — texnolog tasdiqlab yukladi.")

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
            "product_name": product.name if product else parsed.name,
            "panels": parsed.part_count,
            "matched": product is not None,
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
    return _read(row)


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
    return BazisState(models=[_read(r) for r in await _models(db, order_id)], share_token=order.share_token)


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
