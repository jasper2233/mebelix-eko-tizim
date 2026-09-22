"""TABLO data API: orders × stages live matrix. Read-only, any authenticated device."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.orders._common import _get_visible_order
from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.exceptions import NotFoundException
from app.models import (
    ORDER_FAT_COLUMNS,
    PART_FAT_COLUMNS,
    PRIORITY_RANK,
    Downtime,
    DowntimeReason,
    Employee,
    KromkaMeasurement,
    Machine,
    Order,
    Part,
    PartDefect,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    WorkSession,
)
from app.models.enums import DowntimeKind, KromkaVerdict, OrderStatus, SessionStatus
from app.schemas.tablo import (
    StageAgg,
    TabloDefectRow,
    TabloMachineDetail,
    TabloMachineRow,
    TabloMatrix,
    TabloOrderDetail,
    TabloOrderRow,
    TabloPartRow,
    TabloPeriod,
    TabloPostCol,
    TabloScanRow,
    TabloStopRow,
)
from app.services.andon import read_live
from app.services.availability import plan_windows
from app.services.metrics import VolumeShare, part_volume
from app.services.settings_service import get_work_schedule

router = APIRouter(prefix="/tablo", tags=["tablo"])


@router.get("/machines", response_model=list[TabloMachineRow], operation_id="read_tablo_machines")
async def read_tablo_machines(db: SessionDep, user: CurrentUser) -> list[TabloMachineRow]:
    """Stanok taxtasi: Pico ulangan ish markazlarining JONLI holati va BUGUNGI OEE si.

    Raqamlar «Stanok vaqti» hisobotini bugungi kun uchun chaqirib olinadi — taxta
    va hisobot bitta manbadan gapirsin. Hisobotga faqat andon hodisasi bor ish
    markazlari tushadi, ya'ni «faqat Pico ulanganlari» filtri o'zidan chiqadi.

    Jonli holat Redis'dan (`read_live`): kalit yo'q bo'lsa `state = None` —
    bu «o'chiq» EMAS, «aloqa yo'q» (agent yoki Pico 90 soniyadan beri jim)."""
    bugun = datetime.now(TASHKENT_TZ).date()
    hisobot = await report_machine_time(db, user, date_from=bugun, date_to=bugun)
    if isinstance(hisobot, StreamingResponse) or not hisobot.rows:  # pragma: no cover — format="json"
        return []
    ids = [r.machine_id for r in hisobot.rows]
    jonli = await read_live(ids)
    postlar = dict(
        (
            await db.execute(
                select(Machine.id, Post.name).join(Post, Post.id == Machine.post_id).where(Machine.id.in_(ids))
            )
        )
        .tuples()
        .all()
    )
    kun_boshi = datetime.combine(bugun, time.min, tzinfo=TASHKENT_TZ)
    # Hisob qaysi lahzadan beri yuritilyapti: bugungi BIRINCHI ish oynasining boshi.
    # Kartada «08:00 dan beri · 3 soat 40 daq» bo'lib chiqadi — taxtaga qaragan odam
    # raqam nimaga nisbatan ekanini so'ramasin.
    oynalar = plan_windows(await get_work_schedule(db), kun_boshi, datetime.now(UTC))
    oyna_boshi = oynalar[0][0] if oynalar else None
    sababsiz = dict(
        (
            await db.execute(
                select(Downtime.machine_id, func.count())
                .where(
                    Downtime.machine_id.in_(ids),
                    Downtime.kind != DowntimeKind.LOCK,
                    Downtime.reason_id.is_(None),
                    Downtime.is_deleted == False,  # noqa: E712
                    or_(Downtime.ended_at.is_(None), Downtime.ended_at >= kun_boshi),
                )
                .group_by(Downtime.machine_id)
            )
        )
        .tuples()
        .all()
    )
    # Smenadagi brigada: bitta so'rovda hamma ish markazi bo'yicha (stanok boshiga
    # alohida so'rov taxtani 9 ta ortiqcha zapros bilan yuklardi)
    brigada: dict[int, list[str]] = {}
    for mid, ism in (
        (
            await db.execute(
                select(WorkSession.machine_id, Employee.full_name)
                .join(Employee, Employee.id == WorkSession.employee_id)
                .where(
                    WorkSession.machine_id.in_(ids),
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
                .order_by(WorkSession.created_at)
            )
        )
        .tuples()
        .all()
    ):
        if mid is not None:
            brigada.setdefault(mid, []).append(ism)

    # Bugungi o'lchov hisobi (kromka): kutilganiga mos tushgani va tushmagani.
    # `ortiqcha`/`shubhali`/`skanersiz` alohida sanalmaydi — ular na detalning,
    # na lentaning aybi (takroriy o'tish, datchik kodi, skan yo'qligi).
    hukmlar: dict[int, dict[str, int]] = {}
    for mid, hukm, soni in (
        (
            await db.execute(
                select(KromkaMeasurement.machine_id, KromkaMeasurement.verdict, func.count())
                .where(
                    KromkaMeasurement.machine_id.in_(ids),
                    KromkaMeasurement.measured_at >= kun_boshi,
                    KromkaMeasurement.is_deleted == False,  # noqa: E712
                )
                .group_by(KromkaMeasurement.machine_id, KromkaMeasurement.verdict)
            )
        )
        .tuples()
        .all()
    ):
        hukmlar.setdefault(mid, {})[hukm.value] = soni

    # Oxirgi o'lchov — faqat kromkada bor (`kromka_measurement`); bitta so'rovda
    # har stanokning eng yangisi olinadi
    olchovlar = {
        row.machine_id: row
        for row in (
            await db.execute(
                select(KromkaMeasurement)
                .where(
                    KromkaMeasurement.machine_id.in_(ids),
                    KromkaMeasurement.is_deleted == False,  # noqa: E712
                )
                .distinct(KromkaMeasurement.machine_id)
                .order_by(KromkaMeasurement.machine_id, KromkaMeasurement.measured_at.desc())
            )
        )
        .scalars()
        .all()
    }

    rows: list[TabloMachineRow] = []
    for r in hisobot.rows:
        live = jonli.get(r.machine_id)
        olchov = olchovlar.get(r.machine_id)
        rows.append(
            TabloMachineRow(
                machine_id=r.machine_id,
                machine_name=r.machine_name,
                post_name=postlar.get(r.machine_id, ""),
                state=str(live["state"]) if live and live.get("state") else None,
                since=datetime.fromtimestamp(live["since"], UTC) if live and live.get("since") else None,
                crew=brigada.get(r.machine_id, []),
                planned_s=r.planned_s,
                run_s=r.run_s,
                stop_s=r.unplanned_stop_s + r.no_data_s,
                availability_pct=r.availability_pct,
                parts=r.parts,
                performance_pct=r.performance_pct,
                defects=r.defects,
                quality_pct=r.quality_pct,
                oee_pct=r.oee_pct,
                pending_reasons=sababsiz.get(r.machine_id, 0),
                window_from=oyna_boshi,
                mos_count=hukmlar.get(r.machine_id, {}).get(KromkaVerdict.MOS.value, 0),
                nomos_count=hukmlar.get(r.machine_id, {}).get(KromkaVerdict.NOMOS.value, 0),
                last_mm=float(olchov.measured_mm) if olchov and olchov.measured_mm is not None else None,
                last_verdict=olchov.verdict.value if olchov else None,
                last_part=None,
            )
        )
    return rows


# TABLO'da FAQAT ishlab chiqarishdagi buyurtmalar ko'rinadi.
#
# Buyurtma taxtadan hamma detali TMO dan o'tgan zahoti tushadi — bu aynan
# COMPLETED holatining o'zi: oxirgi marshrut qadami TMO qabuli, va oxirgi
# qadam yopilganda `scanning.record_scan_at` statusni COMPLETED qiladi.
# Ya'ni bu yerda alohida "tayyorlarni ham ko'rsat" sharti KERAK EMAS,
# status filtri o'zi shu ma'noni beradi.
#
# Managerning "TOPSHIRILDI" tugmasi taxtaga TA'SIR QILMAYDI — u DELIVERED
# holatini va topshirish sanasini yozadi, taxta esa undan oldin tozalangan
# bo'ladi. Sabab: devordagi ekran TSEXNING ishi uchun, tsexda esa TMO dan
# o'tgan buyurtma ustida bajariladigan ish qolmaydi. Topshirish — tijoriy
# qadam, u reestrda kuzatiladi.
#
# Ilgari 30 kunlik oyna bor edi, sababi "chegarasiz qoldirilsa ekran
# sekinlashadi (100 buyurtmada 28 ms -> 1.9 s)". O'sha o'lchov keyingi
# optimizatsiyadan (ORDER_FAT_COLUMNS defer + faqat kerakli ustunlar,
# 669 ms -> 175 ms) OLDIN olingan. 2026-08-26 da qayta o'lchandi: 19 buyurtma
# uchun 84-120 ms, og'ir qism `part_route` agregatsiyasi. Oyna endi umuman
# kerak emas: ro'yxatni TMO ning o'zi cheklaydi.


#: Kartani bosganda ochiladigan oynadagi ro'yxatlar uzunligi — devor ekrani emas,
#: usta qo'lidagi oyna: aylantirmasdan ko'rinadigan uzunlik yetarli.
_DETAIL_N = 15


@router.get("/machines/{machine_id}", response_model=TabloMachineDetail, operation_id="read_tablo_machine")
async def read_tablo_machine(db: SessionDep, user: CurrentUser, machine_id: int) -> TabloMachineDetail:
    """Bitta stanok: bugungi/haftalik/oylik OEE va oxirgi hodisalari.

    OEE uchala davrda ham «Stanok vaqti» hisobotidan olinadi (uch chaqiruv) — taxtadagi
    raqam bilan hisobotdagi raqam bitta manbadan chiqsin. Bu oyna TV da emas, ustaning
    bosishi bilan ochiladi, ya'ni uch marta hisoblash narxi joyida."""
    machine = await db.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise NotFoundException("Ish markazi topilmadi.")
    post = await db.get(Post, machine.post_id)
    bugun = datetime.now(TASHKENT_TZ).date()

    davrlar: list[TabloPeriod] = []
    for nom, kun in (("Bugun", 0), ("7 kun", 6), ("30 kun", 29)):
        hisobot = await report_machine_time(db, user, date_from=bugun - timedelta(days=kun), date_to=bugun)
        if isinstance(hisobot, StreamingResponse):  # pragma: no cover — format="json"
            continue
        r = next((x for x in hisobot.rows if x.machine_id == machine_id), None)
        davrlar.append(
            TabloPeriod(
                label=nom,
                planned_s=r.planned_s if r else 0,
                run_s=r.run_s if r else 0,
                availability_pct=r.availability_pct if r else None,
                parts=r.parts if r else 0,
                defects=r.defects if r else 0,
                performance_pct=r.performance_pct if r else None,
                quality_pct=r.quality_pct if r else None,
                oee_pct=r.oee_pct if r else None,
            )
        )

    skanlar = [
        TabloScanRow(at=at, part_name=part_name, qr_text=qr, employee=ism)
        for at, part_name, qr, ism in (
            (
                await db.execute(
                    select(Scan.created_at, Part.name, PartInstance.qr_text, Employee.full_name)
                    .join(Part, Part.id == Scan.part_id)
                    .join(PartInstance, PartInstance.id == Scan.instance_id)
                    .outerjoin(Employee, Employee.id == Scan.employee_id)
                    .where(
                        Scan.machine_id == machine_id,
                        Scan.is_cancelled == False,  # noqa: E712
                        Scan.is_deleted == False,  # noqa: E712
                    )
                    .order_by(Scan.created_at.desc())
                    .limit(_DETAIL_N)
                )
            )
            .tuples()
            .all()
        )
    ]
    braklar = [
        TabloDefectRow(at=at, part_name=part_name, qr_text=qr, reason=sabab, status=holat.value)
        for at, part_name, qr, sabab, holat in (
            (
                await db.execute(
                    select(PartDefect.created_at, Part.name, PartInstance.qr_text, PartDefect.reason, PartDefect.status)
                    .join(Part, Part.id == PartDefect.part_id)
                    .join(PartInstance, PartInstance.id == PartDefect.instance_id)
                    .where(
                        PartDefect.machine_id == machine_id,
                        PartDefect.is_deleted == False,  # noqa: E712
                    )
                    .order_by(PartDefect.created_at.desc())
                    .limit(_DETAIL_N)
                )
            )
            .tuples()
            .all()
        )
    ]
    hozir = datetime.now(UTC)
    toxtashlar = [
        TabloStopRow(
            started_at=boshi,
            ended_at=oxiri,
            seconds=int(((oxiri or hozir) - boshi).total_seconds()),
            kind=turi.value,
            reason=sabab,
        )
        for boshi, oxiri, turi, sabab in (
            (
                await db.execute(
                    select(Downtime.started_at, Downtime.ended_at, Downtime.kind, DowntimeReason.name)
                    .outerjoin(DowntimeReason, DowntimeReason.id == Downtime.reason_id)
                    .where(
                        Downtime.machine_id == machine_id,
                        Downtime.is_deleted == False,  # noqa: E712
                    )
                    .order_by(Downtime.started_at.desc())
                    .limit(_DETAIL_N)
                )
            )
            .tuples()
            .all()
        )
    ]
    return TabloMachineDetail(
        machine_id=machine_id,
        machine_name=machine.name,
        post_name=post.name if post else "",
        periods=davrlar,
        recent_scans=skanlar,
        defects=braklar,
        stops=toxtashlar,
    )


@router.get("/matrix", response_model=TabloMatrix, operation_id="read_tablo_matrix")
async def read_tablo_matrix(db: SessionDep, _: CurrentUser) -> TabloMatrix:
    posts = (
        (await db.execute(select(Post).where(Post.is_deleted == False).order_by(Post.order_index)))  # noqa: E712
        .scalars()
        .all()
    )
    posts_by_id = {p.id: p for p in posts}

    orders = (
        (
            await db.execute(
                select(Order)
                .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
                .where(
                    Order.status == OrderStatus.PRODUCTION,
                    Order.is_deleted == False,  # noqa: E712
                )
                # Terminal ro'yxati bilan AYNAN bir xil tartib (`PRIORITY_RANK`):
                # ishchi o'z postida ko'rgan navbat devordagi taxta bilan
                # mos tushsin.
                .order_by(PRIORITY_RANK, Order.deadline.asc().nulls_last(), Order.id)
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        return TabloMatrix(posts=[_post_col(p) for p in posts], orders=[])

    order_ids = [o.id for o in orders]
    # ORM obyektlari emas, faqat kerakli ustunlar: butun tsex bo'yicha o'n minglab
    # marshrut yig'iladi, natija esa har postga bir nechta raqam (669 ms -> 175 ms)
    routes = (
        await db.execute(
            select(
                PartRoute.order_id,
                PartRoute.post_id,
                PartRoute.part_id,
                PartRoute.seq,
                PartRoute.total_done,
                PartRoute.total_required,
                Part.length,
                Part.width,
                Part.count.label("part_count"),  # Row.count band — Sequence metodi
                Part.edges,
            )
            .join(Part, Part.id == PartRoute.part_id)
            .where(
                PartRoute.order_id.in_(order_ids),
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).all()

    # Oxirgi harakat: bitta agregat, faqat ro'yxatdagi buyurtmalar bo'yicha.
    # `ix_scan_order_post` shu filtrga tushadi (prodda 39 484 skan bilan
    # ishlatilgan indeks). Bekor qilingan skan hisobga olinmaydi — u qaytarilgan
    # ish, ya'ni "harakat" emas.
    kun = func.date(func.timezone(TASHKENT_TZ.key, Scan.created_at))
    last_day: dict[int, date] = dict(
        (
            await db.execute(
                select(Scan.order_id, func.max(kun))
                .where(
                    Scan.order_id.in_(order_ids),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.order_id)
            )
        ).all()
    )
    # TSEX ishlagan kunlar — buyurtma filtrisiz: bir buyurtma turgan paytda
    # boshqasi ishlagan bo'lsa, o'sha kun "ish kuni" sanaladi. Oxirgi 60 kun
    # yetarli: undan uzoq turgan buyurtma baribir chegaradan oshgan.
    ish_kunlari = sorted(
        (
            await db.execute(
                select(kun)
                .where(
                    Scan.created_at > func.now() - text("interval '60 days'"),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(kun)
            )
        )
        .scalars()
        .all()
    )

    # Har detalning `seq` bo'yicha BIRINCHI tugallanmagan qadami — tayyor;
    # undan keyingilari shu detal uchun bloklangan. Detal darajasi yetarli:
    # nusxa darajasidagi hisob bilan prodda AYNAN bir xil chiqdi (35 juftlik,
    # farq 0), ya'ni qo'shimcha so'rov keraksiz.
    qadamlar: dict[int, list[Any]] = {}
    for row in routes:
        qadamlar.setdefault(row.part_id, []).append(row)
    tayyor: set[tuple[int, int]] = set()
    for detal in qadamlar.values():
        for r in sorted(detal, key=lambda x: x.seq):
            if r.total_done < r.total_required:
                tayyor.add((r.order_id, r.post_id))
                break

    agg: dict[tuple[int, int], StageAgg] = {}
    # Hajm HAR DETAL uchun postda BIR MARTA sanaladi, BAJARILGAN ulushi esa o'sha
    # detalning shu postdagi hamma qatoridan yig'iladi — qoida va sababi
    # `metrics.VolumeShare` da. `done`/`total` esa HAMMA qatordan yig'iladi: ular
    # skan soni, ikki o'tish rostdan ikki skan.
    # (detal, post) -> (agregat kaliti, ulush hisoblagichi)
    part_vol: dict[tuple[int, int], tuple[tuple[int, int], VolumeShare]] = {}
    for row in routes:
        key = (row.order_id, row.post_id)
        post = posts_by_id[row.post_id]
        entry = agg.get(key)
        if entry is None:
            entry = StageAgg(
                post_id=row.post_id,
                done=0,
                total=0,
                volume_total=0.0,
                volume_done=0.0,
                ready=key in tayyor,
            )
            agg[key] = entry
        entry.done += row.total_done
        entry.total += row.total_required
        pair = part_vol.get((row.part_id, row.post_id))
        if pair is None:
            vol = part_volume(str(post.code), length=row.length, width=row.width, count=row.part_count, edges=row.edges)
            pair = (key, VolumeShare(volume=vol))
            part_vol[(row.part_id, row.post_id)] = pair
        share = pair[1]
        share.scans += row.total_done
        share.required += row.total_required

    for agg_key, share in part_vol.values():
        entry = agg[agg_key]
        entry.volume_total += share.volume
        entry.volume_done += share.share()

    rows = [
        TabloOrderRow(
            id=o.id,
            number=o.number,
            name=o.project_name,
            deadline=o.deadline,
            status=str(o.status),
            priority=str(o.priority),
            stages={str(posts_by_id[pid].code): stage for (oid, pid), stage in agg.items() if oid == o.id},
            # Bazaviy kun: oxirgi skan, u bo'lmasa — ishlab chiqarishga uzatilgan kun.
            # Ilgari skansiz buyurtma `None` bo'lib, frontend uni DARHOL «BOSHLANMAGAN»
            # deb tamg'alardi — bugun uzatilgan buyurtma ham. Endi bir qoida: 2 ish
            # kuni harakat yo'q — teg (skani bor-yo'qligidan qat'i nazar).
            idle_days=_idle_days(ish_kunlari, last_day.get(o.id) or _prod_start_day(o)),
        )
        for o in orders
    ]
    return TabloMatrix(posts=[_post_col(p) for p in posts], orders=rows)


def _prod_start_day(o: Order) -> date | None:
    return o.production_started_at.astimezone(TASHKENT_TZ).date() if o.production_started_at else None


def _idle_days(ish_kunlari: list[date], base: date | None) -> int | None:
    """Bazaviy kundan keyingi TSEX ISHLAGAN kunlar soni; bazasi yo'q — `None`."""
    if base is None:
        return None
    return sum(1 for d in ish_kunlari if d > base)


@router.get("/orders/{order_id}", response_model=TabloOrderDetail, operation_id="read_tablo_order")
async def read_tablo_order(db: SessionDep, current_user: CurrentUser, order_id: int) -> TabloOrderDetail:
    """Drill-down: SONI NAZORATI — every part × stage."""
    # Reestrdagi o'qish yo'li bilan bir xil ko'rinuvchanlik: texnologdan
    # yashiringan buyurtma (DRAFT/CANCELLED) bu yerdan ham ochilmasin.
    order = await _get_visible_order(db, current_user, order_id)
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    tartib = {str(p.code): p.order_index for p in posts.values()}
    rows = (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            # Faqat id/code/name/count o'qiladi — `xnc_summary` JSONB bekorga uzatilardi
            .options(*(defer(c) for c in PART_FAT_COLUMNS))
            .where(
                PartRoute.order_id == order_id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartRoute.seq)
        )
    ).all()

    parts: dict[int, TabloPartRow] = {}
    marshrut: dict[int, list[str]] = {}
    #: Birinchi tugallanmagan qadamdan KEYIN shu detal bloklangan — qatorlar
    #: `seq` bo'yicha kelgani uchun buni yo'l-yo'lakay belgilash yetarli.
    bloklangan: set[int] = set()
    for route, part, product_code in rows:
        row = parts.get(part.id)
        if row is None:
            row = TabloPartRow(
                part_id=part.id, code=f"{product_code}_{part.code}", name=part.name, count=part.count, stages={}
            )
            parts[part.id] = row
        # Bitta post marshrutda takrorlanishi mumkin (kromka -> prisadka -> kromka).
        # Katakcha post bo'yicha bo'lgani uchun qadamlar QO'SHILADI — aks holda
        # oxirgi qadam oldingisining ustiga yozilib, bajarilgan ish yo'qolardi.
        key = str(posts[route.post_id].code)
        marshrut.setdefault(part.id, []).append(key)
        tugamagan = route.total_done < route.total_required
        tayyor_mi = tugamagan and part.id not in bloklangan
        if tugamagan:
            bloklangan.add(part.id)
        agg = row.stages.get(key)
        if agg is None:
            row.stages[key] = StageAgg(
                post_id=route.post_id,
                done=route.total_done,
                total=route.total_required,
                volume_total=float(route.total_required),
                volume_done=float(route.total_done),
                ready=tayyor_mi,
            )
        else:
            agg.done += route.total_done
            agg.total += route.total_required
            agg.volume_total += float(route.total_required)
            agg.volume_done += float(route.total_done)
            # Takrorlangan post: ikkinchi tashrif tayyor bo'lsa katak ham tayyor
            agg.ready = agg.ready or tayyor_mi
    # Takror SAQLANADI: `dict.fromkeys` bilan [K, P, K] -> [K, P] bo'lib ustun
    # tartibiga teng chiqadi va belgi yo'qoladi. Sabab va o'lchov: docs/03.
    for pid, kodlar in marshrut.items():
        if kodlar != sorted(kodlar, key=lambda c: tartib[c]):
            parts[pid].route_order = kodlar
    return TabloOrderDetail(id=order.id, number=order.number, name=order.project_name, parts=list(parts.values()))


def _post_col(p: Post) -> TabloPostCol:
    return TabloPostCol(
        id=p.id,
        code=str(p.code),
        name=p.name,
        unit=str(p.unit),
        order_index=p.order_index,
    )
