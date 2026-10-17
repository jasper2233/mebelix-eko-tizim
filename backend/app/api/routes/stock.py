"""Mahsulotlar ombori — kirim/chiqim hujjatlari, partiyalar va harakatlar (docs/14 §9, 2-bosqich).

Qoralama `POST /stock/docs` bilan saqlanadi (qoldiqqa ta'sir qilmaydi), `POST /stock/docs/confirm` —
saqlab, BIR tranzaksiyada tasdiqlaydi. Tasdiqlangan hujjat o'zgarmaydi. Qoidalar `services/stock.py`."""

from datetime import date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from app.api.deps import SessionDep, WarehouseReadUser, WarehouseUser, client_ip
from app.core.config import TASHKENT_TZ
from app.crud import log_action
from app.models import CatalogItem, StockDoc, StockDocLine, StockLot, StockMovement
from app.schemas.stock import (
    DocIn,
    DocLineRead,
    DocRead,
    DocRow,
    InventoryIn,
    ItemHistory,
    LotRead,
    MoveRead,
    SexLogRow,
    StockReport,
)
from app.services.stock import KIND_NAME, DocError, confirm, inventory, open_lots, report, save_draft

router = APIRouter(prefix="/stock", tags=["stock"])


def _who(doc: StockDoc) -> str:
    h = doc.head
    if doc.kind == "kirim":
        parts = [h.get("supplier"), h.get("invoice"), f"qabul: {h['receiver']}" if h.get("receiver") else None]
    elif doc.kind == "sex":
        parts = [h.get("taker"), h.get("equip"), h.get("order"), f"berdi: {h['giver']}" if h.get("giver") else None]
    elif doc.kind == "inv":
        parts = [f"guruh {h['group']}" if h.get("group") else "Ombor", h.get("note")]
    else:
        parts = [h.get("client"), h.get("order"), f"sotuvchi: {h['seller']}" if h.get("seller") else None]
    return " · ".join(p for p in parts if p)


async def _read(db: SessionDep, doc: StockDoc) -> DocRead:
    rows = (
        await db.execute(
            select(StockDocLine, CatalogItem.code, CatalogItem.unit, CatalogItem.catalog)
            .outerjoin(CatalogItem, CatalogItem.id == StockDocLine.item_id)
            .where(StockDocLine.doc_id == doc.id)
            .order_by(StockDocLine.line_no)
        )
    ).all()
    return DocRead(
        id=doc.id,
        no=doc.no,
        kind=doc.kind,
        status=doc.status,
        doc_date=doc.doc_date,
        head={k: str(v) for k, v in doc.head.items()},
        rate=doc.rate,
        total=doc.total,
        cogs=doc.cogs,
        confirmed_at=doc.confirmed_at,
        created_at=doc.created_at,
        lines=[
            DocLineRead.model_validate(ln).model_copy(update={"code": code, "unit": unit, "catalog": cat})
            for ln, code, unit, cat in rows
        ],
    )


@router.get("/docs", response_model=list[DocRow], operation_id="read_stock_docs")
async def read_stock_docs(
    db: SessionDep,
    _: WarehouseReadUser,
    status: Annotated[Literal["draft", "confirmed"] | None, Query()] = None,
    kind: Annotated[Literal["kirim", "chiqim", "sex", "inv"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[DocRow]:
    """«Hujjatlar»: yangisi birinchi. Qatorlar soni bitta so'rovda (subquery)."""
    rows_n = (
        select(func.count(StockDocLine.id))
        .where(StockDocLine.doc_id == StockDoc.id)
        .correlate(StockDoc)
        .scalar_subquery()
    )
    q = select(StockDoc, rows_n).where(StockDoc.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(StockDoc.status == status)
    if kind:
        q = q.where(StockDoc.kind == kind)
    res = await db.execute(q.order_by(StockDoc.created_at.desc(), StockDoc.id.desc()).limit(limit))
    return [
        DocRow(
            id=d.id,
            no=d.no,
            kind=d.kind,
            status=d.status,
            doc_date=d.doc_date,
            who=_who(d),
            rows=n,
            total=d.total,
            cogs=d.cogs,
            rate=d.rate,
            confirmed_at=d.confirmed_at,
            created_at=d.created_at,
        )
        for d, n in res.tuples().all()
    ]


@router.get("/docs/{doc_id}", response_model=DocRead, operation_id="read_stock_doc")
async def read_stock_doc(db: SessionDep, _: WarehouseReadUser, doc_id: int) -> DocRead:
    doc = await db.get(StockDoc, doc_id)
    if doc is None or doc.is_deleted:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")
    return await _read(db, doc)


@router.post("/docs", response_model=DocRead, operation_id="save_stock_doc")
async def save_stock_doc(db: SessionDep, current_user: WarehouseUser, body: DocIn) -> DocRead:
    """Qoralama: yaratadi yoki (`id` bilan) yangilaydi. Qoldiqqa ta'sir qilmaydi."""
    try:
        doc = await save_draft(db, body, current_user.id)
    except DocError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    await db.commit()
    return await _read(db, doc)


@router.post("/docs/confirm", response_model=DocRead, operation_id="confirm_stock_doc")
async def confirm_stock_doc(db: SessionDep, current_user: WarehouseUser, body: DocIn, request: Request) -> DocRead:
    """Saqlaydi va TASDIQLAYDI — bitta tranzaksiya: xato bo'lsa hech narsa yozilmaydi (qoralama ham
    oldingi holicha qoladi). Rad etish xabarlari 422 da, « · » bilan."""
    try:
        doc = await save_draft(db, body, current_user.id)
        await confirm(db, doc, current_user.id)
    except DocError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
    log_action(
        db,
        module="stock",
        action="confirm",
        user_id=current_user.id,
        entity_type="stock_doc",
        entity_id=doc.id,
        message=f"{doc.no} · {KIND_NAME[doc.kind]} · {_who(doc)} · {doc.total} so'm",
        ip=client_ip(request),
    )
    await db.commit()
    return await _read(db, doc)


@router.post("/inventory", response_model=DocRead, operation_id="confirm_stock_inventory")
async def confirm_stock_inventory(
    db: SessionDep, current_user: WarehouseUser, body: InventoryIn, request: Request
) -> DocRead:
    """Inventarizatsiya: haqiqiy miqdorlar bo'yicha qoldiq to'g'rilanadi (ortiqcha — partiya, kami — FIFO),
    TASDIQLANGAN `INV` hujjati yoziladi. Bitta tranzaksiya."""
    try:
        doc = await inventory(db, body.doc_date, body.head, [(c.item_id, c.qty) for c in body.counts], current_user.id)
    except DocError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
    log_action(
        db,
        module="stock",
        action="inventory",
        user_id=current_user.id,
        entity_type="stock_doc",
        entity_id=doc.id,
        message=f"{doc.no} · {len(body.counts)} pozitsiya · farq {doc.total} so'm",
        ip=client_ip(request),
    )
    await db.commit()
    return await _read(db, doc)


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """Sukut — joriy OY (oy boshidan bugungacha). Hisobot oyma-oy o'qiladi: kirim, chiqim va
    harakatsizlik shu ritmda baholanadi. Chegaralar inklyuziv, mahalliy kun (Asia/Tashkent)."""
    oxiri = date_to or datetime.now(TASHKENT_TZ).date()
    boshi = date_from or oxiri.replace(day=1)
    return (
        datetime.combine(boshi, time.min, tzinfo=TASHKENT_TZ),
        datetime.combine(oxiri, time.max, tzinfo=TASHKENT_TZ),
    )


@router.get("/report", response_model=StockReport, operation_id="read_stock_report")
async def read_stock_report(
    db: SessionDep,
    _: WarehouseReadUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> StockReport:
    """Ombor hisoboti (docs/14 §11): guruh bo'yicha qoldiq va aylanma, ABC tahlili, harakatsiz tovarlar.

    Qoldiq va qiymat — HOZIRGI holat (ombor bugun nima bilan turibdi), kirim/chiqim va harakatsizlik
    esa so'ralgan ORALIQDA. Ikkisi ataylab aralash: omborchiga «hozir shuncha pul yotibdi, shundan
    bu oyda qimirlamagani shu» degan javob kerak."""
    start, end = _range(date_from, date_to)
    return StockReport(date_from=start.date(), date_to=end.date(), **await report(db, start, end))


@router.get("/sex-log", response_model=list[SexLogRow], operation_id="read_stock_sex_log")
async def read_stock_sex_log(
    db: SessionDep, _: WarehouseReadUser, limit: Annotated[int, Query(ge=1, le=20000)] = 5000
) -> list[SexLogRow]:
    """«Sex sarfi»: tasdiqlangan «Sexga kirim» hujjatlarining qatorlari — yangisi birinchi."""
    rows = (
        await db.execute(
            select(StockDocLine, StockDoc, CatalogItem.code, CatalogItem.unit)
            .join(StockDoc, StockDoc.id == StockDocLine.doc_id)
            .join(CatalogItem, CatalogItem.id == StockDocLine.item_id)
            .where(StockDoc.kind == "sex", StockDoc.status == "confirmed", StockDoc.is_deleted == False)  # noqa: E712
            .order_by(StockDoc.confirmed_at.desc(), StockDocLine.line_no)
            .limit(limit)
        )
    ).all()
    return [
        SexLogRow(
            doc_id=d.id,
            doc_no=d.no,
            doc_date=d.doc_date,
            taker=d.head.get("taker", ""),
            equip=d.head.get("equip", ""),
            order=d.head.get("order", ""),
            giver=d.head.get("giver", ""),
            item_id=ln.item_id,  # type: ignore[arg-type]
            code=code,
            name=ln.name,
            unit=unit,
            qty=ln.qty,
            amount=ln.cost,
        )
        for ln, d, code, unit in rows
    ]


@router.delete("/docs/{doc_id}", response_model=DocRow, operation_id="delete_stock_doc")
async def delete_stock_doc(db: SessionDep, _: WarehouseUser, doc_id: int) -> DocRow:
    """Faqat QORALAMA o'chiriladi; tasdiqlangan hujjat qulflangan."""
    doc = await db.get(StockDoc, doc_id)
    if doc is None or doc.is_deleted:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")
    if doc.status != "draft":
        raise HTTPException(status_code=409, detail=f"{doc.no} tasdiqlangan — o'chirib bo'lmaydi")
    doc.is_deleted = True
    await db.commit()
    return DocRow(
        id=doc.id,
        no=doc.no,
        kind=doc.kind,
        status=doc.status,
        doc_date=doc.doc_date,
        who=_who(doc),
        rows=0,
        total=doc.total,
        cogs=doc.cogs,
        rate=doc.rate,
        confirmed_at=doc.confirmed_at,
        created_at=doc.created_at,
    )


def _moves_query():  # type: ignore[no-untyped-def]
    return (
        select(StockMovement, CatalogItem.code, CatalogItem.name, StockDoc.no)
        .join(CatalogItem, CatalogItem.id == StockMovement.item_id)
        .outerjoin(StockDoc, StockDoc.id == StockMovement.doc_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )


def _move(m: StockMovement, code: str, name: str, no: str | None) -> MoveRead:
    return MoveRead(
        id=m.id,
        created_at=m.created_at,
        item_id=m.item_id,
        code=code,
        name=name,
        kind=m.kind,
        qty=m.qty,
        balance=m.balance,
        amount=m.amount,
        note=m.note,
        doc_id=m.doc_id,
        doc_no=no,
    )


@router.get("/moves", response_model=list[MoveRead], operation_id="read_stock_moves")
async def read_stock_moves(
    db: SessionDep, _: WarehouseReadUser, limit: Annotated[int, Query(ge=1, le=20000)] = 5000
) -> list[MoveRead]:
    """Barcha harakatlar — «Harakatlarni Excel'ga chiqarish» uchun."""
    rows = (await db.execute(_moves_query().limit(limit))).tuples().all()
    return [_move(*r) for r in rows]


@router.get("/items/{item_id}/history", response_model=ItemHistory, operation_id="read_stock_item_history")
async def read_stock_item_history(db: SessionDep, _: WarehouseReadUser, item_id: int) -> ItemHistory:
    """Kartochka: qolgan partiyalar (FIFO tartibida) va oxirgi 50 harakat.

    Partiyasi hali bo'lmagan qoldiq «Boshlang'ich» bo'lib KO'RSATILADI (bazaga yozilmaydi — birinchi
    harakatda yoziladi), tannarxi xarid narxi."""
    item = await db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Pozitsiya topilmadi")
    lots = [LotRead.model_validate(lot) for lot in await open_lots(db, item_id)]
    if not lots and item.quantity > 0:
        ever = await db.scalar(select(StockLot.id).where(StockLot.item_id == item_id).limit(1))
        if ever is None:
            lots = [
                LotRead(
                    id=0,
                    received_on=item.created_at.date(),
                    source="Boshlang'ich",
                    qty=item.quantity,
                    qty_left=item.quantity,
                    unit_cost=item.purchase_price or 0,  # type: ignore[arg-type]
                    usd=None,
                )
            ]
    rows = (await db.execute(_moves_query().where(StockMovement.item_id == item_id).limit(50))).tuples().all()
    return ItemHistory(lots=lots, moves=[_move(*r) for r in rows], next_cost=lots[0].unit_cost if lots else None)
