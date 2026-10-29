"""Mahsulotlar ombori — hujjatlar va FIFO (docs/14 §9, 2-bosqich).

Qoidalar dizayndagi `confirmDoc` / `consume` / `lotsOf` bilan bir xil:

* qoralama qoldiqqa ta'sir qilmaydi; tasdiqlanganda qoldiq, partiya va harakat yoziladi va hujjat qulflanadi;
* chiqimda qoldiqdan ko'p berilmaydi (pozitsiya bo'yicha jami); xizmat sotiladi, lekin omborga ta'sir qilmaydi;
* kirim dollarda: partiya tannarxi = round($ × kurs); pozitsiyaning xaridi va ustamali sotuvi yangilanadi;
* chiqim ENG ESKI partiyadan oladi (FIFO); tannarx — olingan partiyalar narxi; foyda = summa − tannarx;
* partiyasi yo'q, lekin qoldig'i bor pozitsiya (1-bosqichdagi boshlang'ich qoldiq) birinchi harakatda
  «Boshlang'ich» partiya oladi — tannarxi shu paytdagi xarid narxi (dizayndagi `lotsOf`).
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem, StockDoc, StockDocLine, StockLot, StockMovement
from app.modules.ombor.schemas.stock import DocIn
from app.modules.ombor.services import birlik, rezerv
from app.modules.ombor.services.warehouse import abc_classes, get_pricing, reprice

PREFIX = {"kirim": "KIR", "chiqim": "CHQ", "sex": "SEX", "inv": "INV"}
KIND_NAME = {"kirim": "Kirim", "chiqim": "Chiqim (sotuv)", "sex": "Sexga kirim", "inv": "Inventarizatsiya"}


class DocError(Exception):
    """Tasdiqlash rad etildi — xabarlar foydalanuvchiga (o'zbekcha)."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(" · ".join(errors))
        self.errors = errors


def _so_m(v: Decimal) -> Decimal:
    return v.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def fmt(v: Decimal) -> str:
    n = v.normalize()
    s = f"{n:f}"
    if "." not in s:
        return f"{int(n):,}".replace(",", " ")
    return s


def line_sum(qty: Decimal, price: Decimal, discount: Decimal) -> Decimal:
    """Qator summasi: soni × narx − chegirma (chegirma summadan oshmaydi)."""
    g = qty * price
    return max(Decimal(0), g - min(discount, g))


def head_rate(head: dict[str, Any]) -> Decimal | None:
    raw = str(head.get("rate") or "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        r = Decimal(raw)
    except ArithmeticError:
        return None
    return r if r > 0 else None


async def next_no(db: AsyncSession, kind: str, year: int) -> str:
    """`KIR-2026-0148` — turi va yili bo'yicha keyingi raqam (o'chirilgan qoralamalar ham hisobda).

    Ikki parallel hujjat bir raqam olmasin (EKO 2.4 parallel sinovi topgan): shu prefiks uchun
    tranzaksiya qulfi — keyingisi birinchisi commit bo'lguncha kutadi. Raqam SON sifatida
    solishtiriladi: matn bo'yicha `…-10000` `…-9999` dan «kichik» chiqardi."""
    prefix = f"{PREFIX[kind]}-{year}-"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(prefix))))
    last = await db.scalar(
        select(func.max(cast(func.split_part(StockDoc.no, "-", 3), Integer))).where(StockDoc.no.like(f"{prefix}%"))
    )
    return f"{prefix}{(last or 0) + 1:04d}"


async def save_draft(db: AsyncSession, body: DocIn, user_id: int | None) -> StockDoc:
    """Qoralamani yaratadi yoki yangilaydi (qatorlar to'liq almashtiriladi). `flush` qiladi."""
    if body.id is not None:
        doc = await db.get(StockDoc, body.id)
        if doc is None or doc.is_deleted:
            raise DocError(["Hujjat topilmadi"])
        if doc.status != "draft":
            raise DocError([f"{doc.no} tasdiqlangan — o'zgartirib bo'lmaydi"])
        if doc.kind != body.kind:
            raise DocError(["Hujjat turi o'zgarmaydi"])
        for old in (await db.execute(select(StockDocLine).where(StockDocLine.doc_id == doc.id))).scalars():
            await db.delete(old)
    else:
        doc = StockDoc(
            no=await next_no(db, body.kind, body.doc_date.year),
            kind=body.kind,
            doc_date=body.doc_date,
            created_by_id=user_id,
        )
        db.add(doc)
    doc.doc_date = body.doc_date
    doc.head = {k: v.strip() for k, v in body.head.items() if v and v.strip()}
    await db.flush()
    n = 0
    for ln in body.lines:
        if ln.item_id is None and not ln.name.strip() and ln.qty == 0:
            continue  # bo'sh qator
        n += 1
        db.add(
            StockDocLine(
                doc_id=doc.id,
                line_no=n,
                item_id=ln.item_id,
                name=ln.name.strip(),
                qty=ln.qty,
                price=ln.price,
                discount=ln.discount if body.kind == "chiqim" else Decimal(0),
                note=ln.note.strip(),
                hajm=ln.hajm if body.kind == "kirim" else None,
            )
        )
    await db.flush()
    return doc


async def _ensure_initial_lot(db: AsyncSession, item: CatalogItem) -> None:
    """Partiyasi hech qachon bo'lmagan, lekin qoldig'i bor pozitsiya — «Boshlang'ich» partiya.
    Sanasi — pozitsiya yaratilgan kun: FIFO da u har doim eng eski."""
    if item.quantity <= 0:
        return
    bor = await db.scalar(select(StockLot.id).where(StockLot.item_id == item.id).limit(1))
    if bor is None:
        db.add(
            StockLot(
                item_id=item.id,
                received_on=item.created_at.date(),
                qty=item.quantity,
                qty_left=item.quantity,
                unit_cost=item.purchase_price or Decimal(0),
                source="Boshlang'ich",
            )
        )
        await db.flush()


async def open_lots(db: AsyncSession, item_id: int, lock: bool = False) -> list[StockLot]:
    q = (
        select(StockLot)
        .where(StockLot.item_id == item_id, StockLot.qty_left > 0, StockLot.is_deleted == False)  # noqa: E712
        .order_by(StockLot.received_on, StockLot.id)
    )
    return list((await db.execute(q.with_for_update() if lock else q)).scalars())


async def consume(db: AsyncSession, item: CatalogItem, qty: Decimal) -> Decimal:
    """FIFO: eng eski partiyadan `qty` oladi, tannarxini (so'm) qaytaradi."""
    await _ensure_initial_lot(db, item)
    left, cost, last = qty, Decimal(0), None
    for lot in await open_lots(db, item.id, lock=True):
        if left <= 0:
            break
        t = min(lot.qty_left, left)
        cost += t * lot.unit_cost
        lot.qty_left -= t
        left -= t
        last = lot
    if left > 0:  # partiyalar yetmadi (qo'lda kiritilgan qoldiq) — oxirgi ma'lum narx bilan
        cost += left * (last.unit_cost if last else (item.purchase_price or Decimal(0)))
    return _so_m(cost)


def add_lot(
    db: AsyncSession,
    item: CatalogItem,
    qty: Decimal,
    unit_cost: Decimal,
    today: date,
    source: str,
    doc_id: int | None = None,
    usd: Decimal | None = None,
    rate: Decimal | None = None,
) -> None:
    db.add(
        StockLot(
            item_id=item.id,
            doc_id=doc_id,
            received_on=today,
            qty=qty,
            qty_left=qty,
            unit_cost=unit_cost,
            usd=usd,
            rate=rate,
            source=source,
        )
    )


async def _check_free(db: AsyncSession, need: dict[int, Decimal], items: dict[int, CatalogItem]) -> list[str]:
    """Chiqim/sexga berishda yetarlimi. Buyurtmalarga band (rezerv) qism sotilmaydi va sexga
    berilmaydi — faqat bo'sh qoldiq (EKO TZ §4.3)."""
    errors: list[str] = []
    band = await rezerv.reserved_qty(db, need)
    for iid, q in need.items():
        it = items[iid]
        free = it.quantity - band.get(iid, Decimal(0))
        if q > it.quantity:
            errors.append(f"{it.name}: {fmt(q)} {it.unit or ''} kerak, omborda {fmt(it.quantity)} bor")
        elif q > free:
            errors.append(
                f"{it.name}: {fmt(q)} {it.unit or ''} kerak, bo'sh {fmt(max(free, Decimal(0)))} — "
                f"{fmt(band[iid])} buyurtmalarga band"
            )
    return errors


def _plan_birlik(
    is_k: bool, it: CatalogItem, ln: StockDocLine, birliklar: dict[int, list[Decimal]], errors: list[str]
) -> None:
    """Kirimda barkodli pozitsiya qatori qanday birliklarga bo'linadi (list — dona-dona, rulon — uzunligi)."""
    if not is_k or not birlik.tracked(it):
        return
    sizes = birlik.split(it, ln.qty, ln.hajm)
    if isinstance(sizes, str):
        errors.append(f"{ln.line_no}-qator: {sizes}")
    else:
        birliklar[ln.id] = sizes


async def confirm(db: AsyncSession, doc: StockDoc, user_id: int | None) -> None:
    """Qoralamani tasdiqlaydi: tekshiradi, qoldiq/partiya/harakat yozadi, qulflaydi. Xato — `DocError`."""
    if doc.status != "draft":
        raise DocError([f"{doc.no} allaqachon tasdiqlangan"])
    is_k = doc.kind == "kirim"
    head = doc.head
    cfg = await get_pricing(db)
    lines = list(
        (
            await db.execute(select(StockDocLine).where(StockDocLine.doc_id == doc.id).order_by(StockDocLine.line_no))
        ).scalars()
    )
    ids = {ln.item_id for ln in lines if ln.item_id is not None}
    # Qoldiqni bir vaqtda ikki hujjat sotib yubormasin — pozitsiyalar qulflanadi
    items = {
        i.id: i
        for i in (await db.execute(select(CatalogItem).where(CatalogItem.id.in_(ids)).with_for_update())).scalars()
        if not i.is_deleted
    }

    is_sx = doc.kind == "sex"
    errors: list[str] = []
    rate = (head_rate(head) or cfg.usd_rate) if is_k else None
    if is_k and not head.get("supplier"):
        errors.append("Yetkazib beruvchi kiritilmagan")
    if is_sx and not head.get("taker"):
        errors.append("Kim olgani kiritilmagan")
    if doc.kind == "chiqim" and not head.get("client"):
        errors.append("Mijoz F.I.Sh. kiritilmagan")
    if not lines:
        errors.append("Birorta ham mahsulot qatori yo'q")
    need: dict[int, Decimal] = {}
    #: Kirim qatori → yaratiladigan barkodli birliklar hajmi (list/rulon)
    birliklar: dict[int, list[Decimal]] = {}
    for ln in lines:
        it = items.get(ln.item_id) if ln.item_id is not None else None
        if it is None:
            errors.append(f"{ln.line_no}-qator: «{ln.name}» nomenklaturada yo'q — ro'yxatdan tanlang")
        elif ln.qty <= 0:
            errors.append(f"{ln.line_no}-qator: soni kiritilmagan")
        elif is_k and it.catalog == "X":
            errors.append(f"{ln.line_no}-qator: xizmat kirim qilinmaydi — omborda saqlanmaydi")
        elif is_sx and it.catalog == "X":
            errors.append(f"{ln.line_no}-qator: xizmat sexga berilmaydi")
        elif doc.kind == "chiqim" and it.catalog == "S":
            errors.append(f"{ln.line_no}-qator: «{it.name}» sex xo'jaligiga tegishli — sotilmaydi")
        elif it.catalog != "X":
            need[it.id] = need.get(it.id, Decimal(0)) + ln.qty
            _plan_birlik(is_k, it, ln, birliklar, errors)
    if not is_k:
        errors += await _check_free(db, need, items)
    if errors:
        raise DocError(errors)

    today = doc.doc_date
    total, cogs = Decimal(0), Decimal(0)
    if is_k:
        who, verb = head.get("supplier", ""), "Kirim"
    elif is_sx:
        who, verb = " · ".join(x for x in (head.get("taker"), head.get("equip")) if x), "Sexga kirim"
    else:
        who, verb = " · ".join(x for x in (head.get("client"), head.get("seller")) if x), "Sotuv"
    for ln in lines:
        it = items[ln.item_id]  # type: ignore[index]
        s = line_sum(ln.qty, ln.price, ln.discount)
        if it.catalog == "X":
            total += s
            continue
        if is_k:
            assert rate is not None
            cs = _so_m(ln.price * rate)
            await _ensure_initial_lot(db, it)
            unit = cs or it.purchase_price or Decimal(0)
            add_lot(db, it, ln.qty, unit, today, doc.no, doc.id, ln.price or None, rate)
            if ln.price:
                it.purchase_usd = ln.price
                reprice(it, cfg.model_copy(update={"usd_rate": rate}))
            it.quantity += ln.qty
            await birlik.create(db, it, birliklar.get(ln.id, []), doc.id)
            amount = ln.qty * unit
            total += _so_m(s * rate)
        else:
            amount = await consume(db, it, ln.qty)
            ln.cost = amount
            it.quantity -= ln.qty
            await birlik.sync_down(db, it)
            cogs += amount
            # Sexga — sotuv emas: summasi tannarxning o'zi (dizayndagi `sum += isSx ? fc`)
            total += amount if is_sx else s
        db.add(
            StockMovement(
                item_id=it.id,
                doc_id=doc.id,
                kind=doc.kind,
                qty=ln.qty if is_k else -ln.qty,
                balance=it.quantity,
                amount=_so_m(amount),
                note=f"{verb} · {who}"[:200],
                user_id=user_id,
            )
        )
    doc.status = "confirmed"
    doc.rate = rate
    doc.total = _so_m(total)
    doc.cogs = None if is_k else _so_m(cogs)
    doc.confirmed_at = datetime.now(UTC)
    doc.confirmed_by_id = user_id
    await db.flush()
    if is_k:
        # Yangi kelgan material yetmay turgan rezervlarga navbat bilan beriladi (TZ §4.3 7-band)
        await rezerv.recover_shortages(db, items)


async def inventory(
    db: AsyncSession, doc_date: date, head: dict[str, str], counts: list[tuple[int, Decimal]], user_id: int | None
) -> StockDoc:
    """Inventarizatsiya — haqiqiy miqdor bo'yicha qoldiqni to'g'rilaydi va TASDIQLANGAN `INV` hujjati yozadi.

    Ortiqcha — yangi partiya (xarid narxida), kami — FIFO bo'yicha chiqim (dizayndagi `confirmInv`).
    Hujjat summasi — farqlar yig'indisi (ishorali): ortiqcha qiymati minus kamomad tannarxi."""
    if not counts:
        raise DocError(["Avval kamida bitta «haqiqiy miqdor» kiriting"])
    ids = [i for i, _ in counts]
    items = {
        i.id: i
        for i in (await db.execute(select(CatalogItem).where(CatalogItem.id.in_(ids)).with_for_update())).scalars()
        if not i.is_deleted
    }
    errors = [f"{iid}: pozitsiya topilmadi" for iid in ids if iid not in items]
    errors += [f"«{items[i].name}» — xizmat sanalmaydi" for i in ids if i in items and items[i].catalog == "X"]
    if errors:
        raise DocError(errors)
    doc = StockDoc(
        no=await next_no(db, "inv", doc_date.year),
        kind="inv",
        doc_date=doc_date,
        head={k: v for k, v in head.items() if v},
        created_by_id=user_id,
    )
    db.add(doc)
    await db.flush()
    diff_sum = Decimal(0)
    for n, (iid, real) in enumerate(counts, start=1):
        it = items[iid]
        book = it.quantity
        d = real - book
        amount = Decimal(0)
        if d > 0:
            await _ensure_initial_lot(db, it)
            add_lot(db, it, d, it.purchase_price or Decimal(0), doc_date, doc.no, doc.id)
            amount = _so_m(d * (it.purchase_price or Decimal(0)))
        elif d < 0:
            amount = -(await consume(db, it, -d))
        diff_sum += amount
        it.quantity = real
        await birlik.sync_down(db, it)
        db.add(
            StockDocLine(doc_id=doc.id, line_no=n, item_id=it.id, name=it.name, qty=real, book_qty=book, cost=amount)
        )
        if d != 0:
            db.add(
                StockMovement(
                    item_id=it.id,
                    doc_id=doc.id,
                    kind="inv",
                    qty=d,
                    balance=real,
                    amount=abs(amount),
                    note="Inventarizatsiya tuzatishi",
                    user_id=user_id,
                )
            )
    doc.status = "confirmed"
    doc.total = diff_sum
    doc.confirmed_at = datetime.now(UTC)
    doc.confirmed_by_id = user_id
    await db.flush()
    return doc


async def adjust_quantity(
    db: AsyncSession, item: CatalogItem, new_qty: Decimal, user_id: int | None, note: str = "Qo'lda tuzatish"
) -> None:
    """Qoldiqni qo'lda to'g'rilash: ortiqcha — yangi partiya (xarid narxida), kami — FIFO bo'yicha chiqim."""
    d = new_qty - item.quantity
    if d == 0:
        return
    today = datetime.now(UTC).date()
    if d > 0:
        await _ensure_initial_lot(db, item)
        add_lot(db, item, d, item.purchase_price or Decimal(0), today, "Tuzatish")
        amount = d * (item.purchase_price or Decimal(0))
    else:
        amount = await consume(db, item, -d)
    item.quantity = new_qty
    await birlik.sync_down(db, item)
    db.add(
        StockMovement(
            item_id=item.id,
            kind="tuzatish",
            qty=d,
            balance=new_qty,
            amount=_so_m(amount),
            note=note,
            user_id=user_id,
        )
    )
    await db.flush()


#: «Harakatsiz tovarlar» ro'yxatida ko'rsatiladigan qatorlar soni. Dizayn 5 ta beradi; bizda
#: katalog 2 700 pozitsiya, ya'ni 5 ta qator omborchiga hech narsa aytmaydi — jami soni esa
#: alohida qaytariladi (`dead_total`).
DEAD_ROWS = 20


async def report(db: AsyncSession, start: datetime, end: datetime) -> dict[str, Any]:
    """Ombor hisoboti (docs/14 §11): guruh bo'yicha qoldiq va aylanma, ABC, harakatsizlar.

    Qiymat dizayndagi `V(i)` bilan bir xil: PARTIYALAR bo'yicha (`qty_left × unit_cost`), partiyasi
    bo'lmaganda `qoldiq × (xarid yoki sotuv)`. Partiya tannarxi — haqiqiy FIFO narxi, ya'ni
    kurs o'zgarganda omborda turgan tovar qayta baholanmaydi.

    Xizmat (`X`) chiqarib tashlanadi: unda qoldiq ham, qiymat ham yo'q."""
    items = list(
        (
            await db.execute(
                select(CatalogItem).where(
                    CatalogItem.is_deleted == False,  # noqa: E712
                    CatalogItem.catalog != "X",
                )
            )
        ).scalars()
    )
    lot_value = dict(
        (
            await db.execute(
                select(StockLot.item_id, func.sum(StockLot.qty_left * StockLot.unit_cost))
                .where(StockLot.qty_left > 0, StockLot.is_deleted == False)  # noqa: E712
                .group_by(StockLot.item_id)
            )
        )
        .tuples()
        .all()
    )
    # Oraliqdagi kirim va chiqim: `qty` ishorali (+ kirim, − chiqim)
    moves = {
        item_id: (kirim or Decimal(0), -(chiqim or Decimal(0)))
        for item_id, kirim, chiqim in (
            await db.execute(
                select(
                    StockMovement.item_id,
                    func.sum(StockMovement.qty).filter(StockMovement.qty > 0),
                    func.sum(StockMovement.qty).filter(StockMovement.qty < 0),
                )
                .where(
                    StockMovement.is_deleted == False,  # noqa: E712
                    StockMovement.created_at >= start,
                    StockMovement.created_at <= end,
                )
                .group_by(StockMovement.item_id)
            )
        )
        .tuples()
        .all()
    }

    def qiymat(i: CatalogItem) -> Decimal:
        bor = lot_value.get(i.id)
        return bor if bor is not None else i.quantity * (i.purchase_price or i.sale_price or Decimal(0))

    guruh: dict[tuple[str, str], dict[str, Any]] = {}
    for i in items:
        kalit = (i.catalog, i.group_code)
        row = guruh.setdefault(
            kalit,
            {
                "group_name": i.group_name,
                "positions": 0,
                "qty_in": Decimal(0),
                "qty_out": Decimal(0),
                "value": Decimal(0),
            },
        )
        row["positions"] += 1
        row["value"] += qiymat(i)
        kirim, chiqim = moves.get(i.id, (Decimal(0), Decimal(0)))
        row["qty_in"] += kirim
        row["qty_out"] += chiqim

    sinf = abc_classes(items)
    abc: dict[str, dict[str, Any]] = {c: {"positions": 0, "value": Decimal(0)} for c in ("A", "B", "C")}
    for i in items:
        hujayra = abc[sinf.get(i.id, "C")]
        hujayra["positions"] += 1
        hujayra["value"] += qiymat(i)
    jami_qiymat = sum((v["value"] for v in abc.values()), Decimal(0))

    # Harakatsiz: qoldig'i BOR, lekin oraliqda bitta ham harakati yo'q
    olik = sorted(
        ((i, qiymat(i)) for i in items if i.quantity > 0 and i.id not in moves),
        key=lambda z: -z[1],
    )
    return {
        "groups": sorted(
            (
                {"catalog": k[0], "group_code": k[1], **v}  # type: ignore[dict-item]
                for k, v in guruh.items()
            ),
            key=lambda r: -r["value"],
        ),
        "abc": [
            {
                "cls": c,
                "positions": abc[c]["positions"],
                "value": abc[c]["value"],
                "pct": round(abc[c]["value"] * 100 / jami_qiymat) if jami_qiymat else 0,
            }
            for c in ("A", "B", "C")
        ],
        "dead": [
            {
                "item_id": i.id,
                "code": i.code,
                "name": i.name,
                "unit": i.unit,
                "quantity": i.quantity,
                "value": v,
            }
            for i, v in olik[:DEAD_ROWS]
        ],
        "dead_total": len(olik),
        "value": jami_qiymat,
        "positions": len(items),
    }
