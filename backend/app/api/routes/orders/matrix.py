"""Marshrut matritsasi (detal x qadam): texnolog shu yerda marshrutni chizadi.

TZ 6.3.3. Qadamlar TARTIBLI (`PartRoute.seq`), bitta post marshrutda bir necha
marta uchrashi mumkin — shuning uchun katakcha emas, QADAM ustida ishlaydi.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, func, select, update

from app.api.deps import SessionDep, StaffReadUser, TexnologUser, client_ip
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import Part, PartInstance, PartRoute, Post, Product, Scan
from app.models.enums import PostCode, RouteSource
from app.schemas.orders import MatrixEdit, MatrixPart, OrderMatrix, RouteCell
from app.services.giblab.ingest import park_tail, unpark_tail
from app.services.giblab.models import DEFAULT_PROCESS_CODE, PROCESS_NAMES, PROCESS_POSTS, TAIL_CODES

from ._common import _ROUTE_START_POSTS, _get_order, _get_visible_order, _require_editable

router = APIRouter()


@router.get("/{order_id}/matrix", response_model=OrderMatrix, operation_id="read_order_matrix")
async def read_order_matrix(db: SessionDep, current_user: StaffReadUser, order_id: int) -> OrderMatrix:
    await _get_visible_order(db, current_user, order_id)
    rows = (
        await db.execute(
            select(Part, Product.code)
            .join(Product, Product.id == Part.product_id)
            .where(Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
            .order_by(Product.code, Part.code)
        )
    ).all()
    routes = (
        (
            await db.execute(
                select(PartRoute).where(
                    PartRoute.order_id == order_id,
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    routes_by_part: dict[int, list[RouteCell]] = {}
    for r in routes:
        routes_by_part.setdefault(r.part_id, []).append(RouteCell.model_validate(r))

    children: dict[int, list[dict[str, Any]]] = {}
    for part, product_code in rows:
        if part.assembly_parent_id is not None:
            children.setdefault(part.assembly_parent_id, []).append(
                {"part_id": part.id, "code": f"{product_code}_{part.code}", "count": part.count}
            )

    parts = [
        MatrixPart(
            id=part.id,
            product_code=product_code,
            code=part.code,
            name=part.name,
            count=part.count,
            length=part.length,
            width=part.width,
            thickness=part.thickness,
            edges=part.edges,
            note=part.note,
            is_custom=part.is_custom,
            assembly_parent_id=part.assembly_parent_id,
            assembly_children=children.get(part.id, []),
            routes=sorted(routes_by_part.get(part.id, []), key=lambda c: c.seq),
        )
        for part, product_code in rows
    ]
    return OrderMatrix(order_id=order_id, parts=parts)


@router.patch("/{order_id}/matrix", response_model=OrderMatrix, operation_id="edit_order_matrix")
async def edit_order_matrix(
    db: SessionDep, current_user: TexnologUser, order_id: int, body: MatrixEdit, request: Request
) -> OrderMatrix:
    """Texnolog matrix edits (TZ 6.3.3): stage toggles, notes, rare count fixes. Pre-production only."""
    order = await _get_order(db, order_id)
    await _require_editable(db, order, "Matritsani o'zgartirib bo'lmaydi")

    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    # Anketadagi "Upakovka qilish" — qo'lda chizilgan marshrutga ham qadoqlash
    # qadamini qo'shadi (buyurtma qadoqlansa HAMMA detal qadoqlanadi).
    packaging = order.needs_packaging

    to_check: dict[int, Part] = {}
    for edit in body.edits:
        part = (
            await db.execute(
                select(Part).where(Part.id == edit.part_id, Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
            )
        ).scalar_one_or_none()
        if part is None:
            raise NotFoundException(f"Detal topilmadi: {edit.part_id}")

        if edit.note is not None:
            part.note = edit.note

        if edit.count is not None and edit.count != part.count:
            await _resize_instances(db, part, edit.count)

        # Nostandart bayrog'i marshrut manbasini almashtiradi. Avtomatik qadamlar
        # o'chirilmaydi — YUMSHOQ o'chiriladi, bayroq qaytarilsa aynan tiklanadi
        # (fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi).
        if edit.is_custom is not None and edit.is_custom != part.is_custom:
            part.is_custom = edit.is_custom
            drop, restore = (
                (RouteSource.AUTO, RouteSource.MANUAL) if edit.is_custom else (RouteSource.MANUAL, RouteSource.AUTO)
            )
            await db.execute(
                update(PartRoute)
                .where(PartRoute.part_id == part.id, PartRoute.source == drop, PartRoute.is_deleted == False)  # noqa: E712
                .values(is_deleted=True, deleted_at=datetime.now(UTC))
            )
            await db.execute(
                update(PartRoute)
                .where(PartRoute.part_id == part.id, PartRoute.source == restore, PartRoute.is_deleted == True)  # noqa: E712
                .values(is_deleted=False, deleted_at=None)
            )

        # Biriktirish marshrutdan OLDIN o'rnatiladi: `_set_custom_route` dumni
        # (qadoqlash/TMO) shu bayroqqa qarab qo'shadi yoki qo'shmaydi.
        parent_changed = "assembly_parent_id" in edit.model_fields_set
        if parent_changed:
            await _set_assembly_parent(db, part, edit.assembly_parent_id)

        if edit.route_codes is not None:
            if not part.is_custom:
                raise ForbiddenException("Marshrutni faqat nostandart detalga qo'lda chizish mumkin.")
            await _set_custom_route(db, order_id, part, edit.route_codes, posts, packaging)
        elif parent_changed and part.is_custom:
            # Marshrut o'zgarmadi, lekin dum o'zgardi — mavjud kodlardan qayta quramiz
            await _set_custom_route(db, order_id, part, await _route_codes(db, part), posts, packaging)

        # Marshrut qayta chizilganda ham tekshiriladi: bola allaqachon biriktirilgan
        # bo'lsa (parent tegilmagan) yangi oxirgi qadam ota marshrutida yo'q bo'lishi mumkin.
        # Tekshiruvning o'zi BATCH OXIRIDA (pastda): bitta PATCH'da ota marshrutiga amal
        # qo'shilib bola o'sha amalda tugatilsa, id tartibida bola avval ishlanadi va ota
        # hali eski bo'ladi — yakuniy holat bo'yicha tekshirish tartibga bog'liq emas.
        if part.assembly_parent_id is not None and (parent_changed or edit.route_codes is not None):
            to_check[part.id] = part

        for post_id, enabled in edit.stages.items():
            post = posts.get(post_id)
            if post is None:
                raise NotFoundException(f"Post topilmadi: {post_id}")
            if post.code == PostCode.ARRA and not enabled and not part.is_custom:
                raise ForbiddenException("ARRA bosqichini o'chirib bo'lmaydi — har standart detal uchun majburiy.")
            # Bitta post marshrutda takrorlanishi mumkin — bu yerdagi tugma HAMMA
            # qadamni birga yoqadi/o'chiradi (qadam-baqadam tahrir nostandart tabda).
            steps = (
                (
                    await db.execute(
                        select(PartRoute).where(
                            PartRoute.part_id == part.id,
                            PartRoute.post_id == post_id,
                            PartRoute.is_deleted == False,  # noqa: E712
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not steps and enabled:
                # Yangi qadam DUMDAN (UPAKOVKA/TMO) OLDIN turishi shart. Qat'iy
                # tartib `seq` bo'yicha tekshiradi, ya'ni dumdan keyin qo'yilgan
                # qadam "avval TMO" ni talab qilardi — TMO esa oxirgi qadam, ya'ni
                # skan MANGU E004 bilan rad etilardi.
                next_seq = (
                    await db.execute(
                        select(func.coalesce(func.max(PartRoute.seq), 0) + 1).where(
                            PartRoute.part_id == part.id,
                            PartRoute.process_code.not_in(TAIL_CODES),
                            PartRoute.is_deleted == False,  # noqa: E712
                        )
                    )
                ).scalar_one()
                # Dumni bir pog'ona yuqoriga surish IKKI QADAMDA (`park_tail`/`unpark_tail`
                # izohiga qarang) — qayta yuklashdagi marshrut tiklash ham shu yo'ldan boradi.
                await park_tail(db, part.id)
                # KROMKA har qirrani alohida yopishtiradi — skan qirralar soni marta
                # kutiladi (`_set_custom_route` va fayldan ingest ham shunday hisoblaydi).
                # Bu yerda KROMKA qadami hali yo'q (`steps` bo'sh), ya'ni bu birinchi o'tish.
                per_instance = (len(part.edges) or 1) if post.code == PostCode.KROMKA else 1
                db.add(
                    PartRoute(
                        order_id=order_id,
                        part_id=part.id,
                        post_id=post_id,
                        seq=next_seq,
                        process_code=DEFAULT_PROCESS_CODE[post.code],
                        source=RouteSource.MANUAL,
                        per_instance=per_instance,
                        total_required=part.count * per_instance,
                    )
                )
                await db.flush()
                await unpark_tail(db, part.id, 1)
            for step in steps:
                step.is_enabled = enabled

    for part in to_check.values():
        await _check_assembly_match(db, part)

    log_action(
        db,
        module="orders",
        action="matrix_edited",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Texnolog matritsani tahrirladi ({len(body.edits)} detal)",
        ip=client_ip(request),
    )
    await db.commit()
    return await read_order_matrix(db, current_user, order_id)


async def _route_codes(db: SessionDep, part: Part) -> list[int]:
    """Detalning HOZIRGI marshruti jarayon kodlari (dumsiz), tartib bilan."""
    codes = (
        (
            await db.execute(
                select(PartRoute.process_code)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.seq)
            )
        )
        .scalars()
        .all()
    )
    return [c for c in codes if c not in TAIL_CODES]


async def _set_assembly_parent(db: SessionDep, part: Part, parent_id: int | None) -> None:
    """Mayda detalni asosiy detalga biriktiradi (yoki bog'lamni uzadi).

    Bir pog'ona: biriktirilgan detalning o'zi asosiy bo'la olmaydi va aksincha —
    zanjirda kimning skani kimni yopishi tushunarsiz bo'lib qolardi."""
    if parent_id is None:
        part.assembly_parent_id = None
        return
    if parent_id == part.id:
        raise ForbiddenException("Detalni o'ziga biriktirib bo'lmaydi.")
    parent = (
        await db.execute(
            select(Part).where(
                Part.id == parent_id,
                Part.order_id == part.order_id,
                Part.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        raise NotFoundException("Asosiy detal topilmadi (boshqa buyurtmaga tegishli bo'lishi mumkin).")
    if parent.assembly_parent_id is not None:
        raise ForbiddenException(f"{parent.code} o'zi boshqa detalga biriktirilgan — zanjir bo'lmaydi.")
    has_children = (
        await db.execute(
            select(func.count())
            .select_from(Part)
            .where(
                Part.assembly_parent_id == part.id,
                Part.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if has_children:
        raise ForbiddenException(f"{part.code} ga mayda detallar biriktirilgan — avval ularni ajrating.")
    part.assembly_parent_id = parent_id


async def _check_assembly_match(db: SessionDep, part: Part) -> None:
    """Birikish nuqtasi: mayda detalning OXIRGI amali asosiy detal marshrutida ham bo'lishi shart.

    Aynan o'sha qadamda asosiy detal skanerlanadi va mayda detal ham yopiladi.
    Mos kelmasa birikish hech qachon ro'y bermasdi va mayda detal marshrutda osilib qolardi."""
    mine = await _route_codes(db, part)
    if not mine:
        return  # marshrut hali chizilmagan — ishlab chiqarishga uzatishda baribir bloklanadi
    parent = await db.get(Part, part.assembly_parent_id)
    assert parent is not None
    if mine[-1] not in await _route_codes(db, parent):
        op = PROCESS_NAMES.get(mine[-1], str(mine[-1]))
        raise ForbiddenException(
            f"{parent.code} marshrutida «{op}» yo'q — birikish shu amalda bo'ladi, avval uni qo'shing."
        )


async def _set_custom_route(
    db: SessionDep, order_id: int, part: Part, codes: list[int], posts: dict[int, Post], packaging: bool
) -> None:
    """Nostandart detal marshrutini jarayon kodlari ro'yxatidan qayta quradi.

    Ro'yxat TARTIBLI va kod takrorlanishi mumkin ([3, 6, 3] — kromkaga qaytish).
    KROMKA birinchi kelganda qirralar soni marta skanlanadi, takrorida bitta.
    OVAL har doim bitta: oval kromkada detal bitta o'tishda ishlanadi."""
    for code in codes:
        # 15/16 (qadoqlash, TMO) — dumni tizim qo'shadi, texnolog tanlamaydi
        if code not in PROCESS_POSTS or code in TAIL_CODES:
            raise ForbiddenException(f"Noma'lum jarayon kodi: {code}. Ruxsat etilgan: 1–14.")
    if codes and PROCESS_POSTS[codes[0]] not in _ROUTE_START_POSTS:
        raise ForbiddenException("Marshrut faqat Arra yoki Rover'dan boshlanadi — chek o'sha yerda chiqadi.")

    by_code = {p.code: p for p in posts.values()}
    # Eski QO'LDA chizilgan qadamlar BUTUNLAY o'chiriladi: ular almashtirilyapti,
    # tarix emas. Yumshoq o'chirilsa avlodlar to'planib qolardi va bayroq
    # standartga qaytarilib yana yoqilganda HAMMASI birdan tiklanib
    # `(part_id, seq)` yagonaligini buzardi.
    #
    # ISTISNO — skan TEGGAN qator: `scan.route_id` NOT NULL FK va `ON DELETE`
    # yo'q, ya'ni qattiq o'chirish 500 (ForeignKeyViolation) berardi. Buyurtma
    # PRODUCTION da bo'lib, hamma skani BEKOR QILINGAN bo'lsa tahrir ochiq
    # qoladi (`_first_work` bekor qilinganini sanamaydi), skan qatorlari esa
    # o'sha marshrut qadamiga ishora qilib turadi. Ular yumshoq o'chadi —
    # `ix_part_route_part_seq` faqat `NOT is_deleted` uchun yagona, to'qnashuv yo'q.
    scanned = select(Scan.route_id).where(Scan.route_id.is_not(None))
    await db.execute(
        update(PartRoute)
        .where(
            PartRoute.part_id == part.id,
            PartRoute.source == RouteSource.MANUAL,
            PartRoute.id.in_(scanned),
            PartRoute.is_deleted == False,  # noqa: E712
        )
        .values(is_deleted=True, deleted_at=datetime.now(UTC))
    )
    await db.execute(
        delete(PartRoute).where(
            PartRoute.part_id == part.id,
            PartRoute.source == RouteSource.MANUAL,
            PartRoute.id.not_in(scanned),
        )
    )
    # Fayldan kelgan qadamlar esa yumshoq o'chadi — detal standartga qaytsa tiklanadi.
    await db.execute(
        update(PartRoute)
        .where(
            PartRoute.part_id == part.id,
            PartRoute.source == RouteSource.AUTO,
            PartRoute.is_deleted == False,  # noqa: E712
        )
        .values(is_deleted=True, deleted_at=datetime.now(UTC))
    )
    edge_count = len(part.edges) or 1
    seen: set[PostCode] = set()
    for seq, code in enumerate(codes, start=1):
        post_code = PROCESS_POSTS[code]
        post = by_code.get(post_code)
        if post is None:
            raise NotFoundException(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
        # OVAL bu yerda YO'Q: oval kromkada detal bitta o'tishda ishlanadi — bitta skan.
        # KROMKA esa har qirrani alohida yopishtiradi, shuning uchun birinchi o'tishda
        # qirralar soni marta skanlanadi (takror kelsa — bitta).
        first_edge_pass = post_code == PostCode.KROMKA and post_code not in seen
        seen.add(post_code)
        per_instance = edge_count if first_edge_pass else 1
        db.add(
            PartRoute(
                order_id=order_id,
                part_id=part.id,
                post_id=post.id,
                seq=seq,
                process_code=code,
                source=RouteSource.MANUAL,
                per_instance=per_instance,
                total_required=part.count * per_instance,
            )
        )
    # Qadoqlash va TMO — texnolog tanlamaydi. Qadoqlashni anketadagi bayroq
    # qo'shadi, TMO esa HAR doim oxirgi qadam bo'ladi.
    # Biriktirilgan MAYDA detalga dum QO'SHILMAYDI: u asosiy detalga yopishib
    # yaxlit buyumga aylanadi, ya'ni alohida qadoqlanmaydi va TMO ga alohida
    # kirmaydi — aks holda qadoqlovchi mavjud bo'lmagan detalni qidirardi.
    if codes and part.assembly_parent_id is None:
        tail = [(15, PostCode.UPAKOVKA)] if packaging else []
        tail.append((16, PostCode.TMO))
        for offset, (code, post_code) in enumerate(tail):
            post = by_code.get(post_code)
            if post is None:
                raise NotFoundException(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
            db.add(
                PartRoute(
                    order_id=order_id,
                    part_id=part.id,
                    post_id=post.id,
                    seq=len(codes) + 1 + offset,
                    process_code=code,
                    source=RouteSource.MANUAL,
                    per_instance=1,
                    total_required=part.count,
                )
            )


async def _resize_instances(db: SessionDep, part: Part, new_count: int) -> None:
    """Adjust physical copies + route totals when texnolog changes count (pre-production only)."""
    product_code = (await db.execute(select(Product.code).where(Product.id == part.product_id))).scalar_one()
    instances = (
        (
            await db.execute(
                select(PartInstance).where(
                    PartInstance.part_id == part.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    existing = {i.instance_no: i for i in instances}
    key = f"{product_code}_{part.code}"
    # QR konvensiyasi (TZ 5.8): yagona nusxa suffikssiz, ko'p nusxada _1.._n.
    # Count o'zgarganda BARCHA tirik nusxalar qayta normallanadi (1↔N o'tishda
    # eski QR konvensiyaga zid qolib ketmasin) — bosqich pre-production,
    # yorliqlar hali chop etilmagan.
    new_qrs = {n: (key if new_count == 1 else f"{key}_{n}") for n in range(1, new_count + 1)}
    # To'qnashuvni OLDINDAN aniqlash (ingest'dagi qr_owner tekshiruvining juftligi):
    # "010" (2 nusxa) va "010_2" kodli detal bir xil QR beradi — unique indeks
    # xom 500 bermasin, do'stona 422 chiqsin.
    taken = set(
        (
            await db.execute(
                select(PartInstance.qr_text).where(
                    PartInstance.order_id == part.order_id,
                    PartInstance.part_id != part.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    clash = sorted(qr for qr in new_qrs.values() if qr in taken)
    if clash:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Detal ID to'qnashuvi: {', '.join(clash)} bu buyurtmada boshqa detalga tegishli. "
                "Detal kodini yoki sonini o'zgartiring."
            ),
        )
    for n, qr in new_qrs.items():
        if n in existing:
            existing[n].qr_text = qr
        else:
            db.add(
                PartInstance(
                    order_id=part.order_id,
                    part_id=part.id,
                    instance_no=n,
                    qr_text=qr,
                )
            )
    now = datetime.now(UTC)
    for no, inst in existing.items():
        if no > new_count:
            inst.is_deleted = True
            inst.deleted_at = now

    part.count = new_count
    # YUMSHOQ o'chirilganlari ham yangilanadi: nostandart bayrog'i qaytarilganda
    # o'sha qatorlar tiklanadi va eski `total_required` bilan tirilsa navbat,
    # QOLDIQ va TABLO foizlari buzilardi.
    routes = (await db.execute(select(PartRoute).where(PartRoute.part_id == part.id))).scalars().all()
    for route in routes:
        route.total_required = new_count * route.per_instance
