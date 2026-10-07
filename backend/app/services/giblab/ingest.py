"""Persist a parsed .project into the order: products, parts, instances, routes,
materials auto-registry, SCX files and the cut map. Re-upload fully replaces previous results
(gate — `_require_editable`: PRODUCTION included, until the first live scan)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models import Order, OrderFile, Part, PartInstance, PartRoute, Post, Product, WasteItem
from app.models.enums import FileKind, PostCode, RouteSource

from ..settings_service import CUSTOM_PART_SUFFIX, get_setting
from .cutmap import build_cutmap
from .models import TAIL_CODES, ParsedPart, ParsedProject, ParseError, paths_json
from .parser import parse_project
from .routes import build_manual_route, resolve_post
from .scx import build_scx_files, plate_thickness_map


@dataclass
class PartSnapshot:
    """Detalning fayldan TIKLANMAYDIGAN, ya'ni texnolog qo'li bilan kiritilgan holati."""

    is_custom: bool
    parent_key: tuple[str, str] | None = None
    note: str | None = None  # texnolog izohi — faylda yo'q, qayta yuklashda yo'qolmasin
    codes: list[int] = field(default_factory=list)  # QO'LDA chizilgan qadamlar, tartibli
    #: `is_enabled=False` qilingan jarayon kodlari. Matritsadagi tugma postning HAMMA
    #: qadamini birga o'chiradi, shuning uchun kod darajasida saqlash yetarli.
    disabled: set[int] = field(default_factory=set)

    @property
    def has_route(self) -> bool:
        """Marshrutga aloqador saqlanma — «tiklandi»/«yo'qoldi» hisobiga faqat shular kiradi
        (izoh yoki o'chirilgan qadam uchungina saqlangan detal marshrut sanog'ini shishirmasin)."""
        return bool(self.codes) or self.is_custom or self.parent_key is not None


#: `(mahsulot kodi, detal kodi)` -> saqlangan holat
RouteSnapshot = dict[tuple[str, str], PartSnapshot]


#: Dumni vaqtincha ko'chirish oralig'i — marshrutda hech qachon shuncha qadam bo'lmaydi.
SEQ_PARK = 1000


def _tail_where(part_id: int) -> tuple[Any, ...]:
    """Detalning TIRIK dum (qadoqlash/TMO) qadamlari."""
    return (
        PartRoute.part_id == part_id,
        PartRoute.process_code.in_(TAIL_CODES),
        PartRoute.is_deleted == False,  # noqa: E712
    )


async def park_tail(db: AsyncSession, part_id: int) -> None:
    """Dumni bo'sh `seq` diapazoniga olib chiqish — o'rtaga yangi qadam sig'sin.

    `(part_id, seq)` qisman UNIQUE indeks dublikatni satr-ma-satr tekshiradi, ya'ni
    to'g'ridan-to'g'ri `seq + n` o'rtada to'qnashardi: avval dum chetga ko'chiriladi,
    yangi qadamlar yoziladi, keyin `unpark_tail` uni joyiga tushiradi."""
    await db.execute(update(PartRoute).where(*_tail_where(part_id)).values(seq=PartRoute.seq + SEQ_PARK))


async def unpark_tail(db: AsyncSession, part_id: int, shift: int) -> None:
    """Dumni joyiga qaytarish — o'rtaga qo'shilgan `shift` qadam hisobga olinadi."""
    await db.execute(
        update(PartRoute)
        .where(*_tail_where(part_id), PartRoute.seq >= SEQ_PARK)
        .values(seq=PartRoute.seq - SEQ_PARK + shift)
    )


async def snapshot_custom_routes(db: AsyncSession, order: Order) -> RouteSnapshot:
    """Qo'lda kiritilgan marshrutlarni `(mahsulot kodi, detal kodi)` bo'yicha eslab qolish.

    Qayta yuklash eski parse'ni butunlay o'chiradi — texnolog yuzlab detalga chizgan
    marshrut ham yo'qolardi. Kalit sifatida detal KODI olinadi: u fayl ichidagi ID'dan
    farqli o'laroq qayta eksportda ham o'zgarmaydi.

    Nostandart detallar ham, matritsadan qo'lda qadam qo'shilgan STANDART detallar ham
    olinadi — ikkalasi ham fayldan tiklanmaydi. Bayroq, izoh va o'chirilgan qadamlar
    ham shu yerda saqlanadi: ularning hech biri `.project` faylida yo'q."""
    # Yig'ma bog'lam ham eslab qolinadi: id qayta yuklashda o'zgaradi, shuning
    # uchun asosiy detal ham KOD bilan yoziladi.
    keys: dict[int, tuple[str, str]] = {}
    custom: dict[int, bool] = {}
    notes: dict[int, str | None] = {}
    for part_id, product_code, part_code, is_custom, note in (
        await db.execute(
            select(Part.id, Product.code, Part.code, Part.is_custom, Part.note)
            .join(Product, Product.id == Part.product_id)
            .where(
                Part.order_id == order.id,
                Part.is_deleted == False,  # noqa: E712
            )
        )
    ).tuples():
        keys[part_id] = (product_code, part_code)
        custom[part_id] = is_custom
        notes[part_id] = note
    parents: dict[int, tuple[str, str] | None] = {
        part_id: keys.get(parent_id) if parent_id is not None else None
        for part_id, parent_id in (
            await db.execute(
                select(Part.id, Part.assembly_parent_id).where(
                    Part.order_id == order.id,
                    Part.assembly_parent_id.is_not(None),
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        ).tuples()
    }

    # HAMMA tirik qadam olinadi (faqat MANUAL emas): o'chirilgan bayroq fayldan
    # qurilgan AUTO qadamda ham turishi mumkin.
    rows = (
        await db.execute(
            select(PartRoute.part_id, PartRoute.process_code, PartRoute.source, PartRoute.is_enabled)
            .join(Part, Part.id == PartRoute.part_id)
            .where(
                Part.order_id == order.id,
                Part.is_deleted == False,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(PartRoute.part_id, PartRoute.seq)
        )
    ).tuples()
    saved: RouteSnapshot = {}

    def entry_for(part_id: int) -> PartSnapshot:
        # Bayroq, izoh va ota-detal MANUAL qatorlardan EMAS, detalning O'ZIDAN olinadi:
        # "Nostandart" deb belgilangan (yoki yig'maga biriktirilgan) detalda hali bironta
        # ham qo'lda qadam bo'lmasligi mumkin — o'shanda bayroq jimgina yo'qolardi.
        key = keys[part_id]
        entry = saved.get(key)
        if entry is None:
            entry = saved[key] = PartSnapshot(
                is_custom=custom[part_id], parent_key=parents.get(part_id), note=notes[part_id]
            )
        return entry

    for part_id in keys:
        if custom[part_id] or parents.get(part_id) is not None or notes[part_id] is not None:
            entry_for(part_id)
    for part_id, process_code, source, is_enabled in rows:
        # Dum (qadoqlash/TMO) kodlar ro'yxatiga TUSHMAYDI — tiklashda o'zi qo'shiladi.
        # Saqlansa har qayta yuklashda ikkilanib borardi: ... UPAKOVKA TMO UPAKOVKA TMO.
        if source == RouteSource.MANUAL and process_code not in TAIL_CODES:
            entry_for(part_id).codes.append(process_code)
        if not is_enabled:
            entry_for(part_id).disabled.add(process_code)
    return saved


def _nostandart_qoidasi(belgi: str) -> Callable[[str], bool]:
    """Nomi `belgi` bilan tugagan detal — NOSTANDART (bazisda texnolog qo'yadi).

    Sabab: belgilanmagan nostandart detal ishlab chiqarishga o'tib ketardi, chunki
    uni faqat odam eslab qolishi kerak edi. Belgi nomda QOLADI — chek, terminal va
    xaritada ko'rinadi, ya'ni ishchi nega nostandart ekanini o'qiydi.

    Bo'sh belgi qoidani o'chiradi: `"x".endswith("")` har doim rost, ya'ni sozlama
    tozalansa HAMMA detal nostandart bo'lib qolardi.
    """
    kesilgan = belgi.strip()
    if not kesilgan:
        return lambda _nom: False
    return lambda nom: nom.strip().endswith(kesilgan)


async def restore_custom_routes(db: AsyncSession, order: Order, saved: RouteSnapshot) -> tuple[int, list[str]]:
    """Saqlangan marshrutlarni yangi detallarga qaytarish. Qaytadi: (tiklangan, yo'qolgan)."""
    if not saved:
        return 0, []
    posts = {p.code: p for p in (await db.execute(select(Post))).scalars()}
    # Anketadagi "Upakovka qilish" xizmati (manager kelishadi) — marshrutga
    # qadoqlash qadamini qo'shadimi. `survey` JSONB, eski yozuvda kalit umuman yo'q.
    packaging = order.needs_packaging
    posts_by_id = {p.id: p.code for p in posts.values()}
    parts = (
        await db.execute(
            select(Product.code, Part)
            .join(Part, Part.product_id == Product.id)
            .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
        )
    ).tuples()
    by_key = {(product_code, part.code): part for product_code, part in parts}
    # Buyurtmaning HAMMA tirik marshruti bitta so'rovda: sikl ichida har detal uchun
    # alohida SELECT qilinmasin (detallar soni yuzlab bo'lishi mumkin).
    live_by_part: dict[int, list[PartRoute]] = {}
    for route in (
        await db.execute(
            select(PartRoute).where(
                PartRoute.order_id == order.id,
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars():
        live_by_part.setdefault(route.part_id, []).append(route)

    # Nostandart detalda marshrut TO'LIQ qo'lda — fayldan qurilgani o'chadi. Sikldan
    # OLDIN va bitta UPDATE bilan: sikl ichida bo'lsa, avval qo'shilgan MANUAL
    # qatorlar autoflush bo'lib qolar edi.
    custom_ids = [by_key[key].id for key, entry in saved.items() if entry.is_custom and key in by_key]
    if custom_ids:
        await db.execute(
            update(PartRoute)
            .where(PartRoute.part_id.in_(custom_ids), PartRoute.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=datetime.now(UTC))
        )

    # Yig'ma bog'lamlar marshrutdan OLDIN tiklanadi: dum (qadoqlash/TMO)
    # biriktirilgan detalga qo'shilmasligi shu bayroqqa qarab hal bo'ladi.
    for key, entry in saved.items():
        part, parent_key = by_key.get(key), entry.parent_key
        if part is None:
            continue
        parent = by_key.get(parent_key) if parent_key else None
        part.assembly_parent_id = parent.id if parent is not None else None

    restored = 0
    for key, entry in saved.items():
        part = by_key.get(key)
        if part is None:
            continue
        # FAYL G'OLIB: nomi belgi bilan tugagan detalni `ingest_project` allaqachon
        # nostandart qilib qo'ygan. Snapshot uni PASAYTIRMAYDI — texnolog bayroqni
        # qo'lda olib tashlagan bo'lsa ham, fayl hali ham nostandart deyapti; belgini
        # bazisdagi NOMDAN olib tashlash kerak. Faqat KO'TARISH tomonga ishlaydi.
        was_custom, codes = entry.is_custom or part.is_custom, entry.codes
        part.is_custom = was_custom
        # Izoh ham fayldan kelmaydi: yangi detal uni doim bo'sh boshlaydi.
        part.note = entry.note
        if was_custom:
            # AUTO qatorlari yuqorida bitta UPDATE bilan allaqachon o'chirilgan.
            start_seq, seen = 1, set()
        else:
            # Standart detalda qo'lda qo'shilgan qadam fayl qadamlariga QO'SHIMCHA edi
            # (matritsadagi tugma) — fayl qadamlari joyida qoladi, bular ketidan tushadi.
            # Dum (qadoqlash/TMO) OXIRIDA qolishi shart: undan keyin tushgan qadam
            # qat'iy tartib tekshiruvida "avval TMO" ni talab qilib, mangu E004 berardi.
            live = live_by_part.get(part.id, [])
            start_seq = max((r.seq for r in live if r.process_code not in TAIL_CODES), default=0) + 1
            seen = {posts_by_id[r.post_id] for r in live if r.post_id in posts_by_id}
            if codes:
                await park_tail(db, part.id)
        # Nostandart detalning marshruti to'liq qayta yozilgani uchun dum (qadoqlash/TMO)
        # ham shu yerda tiklanadi; standart detalda u fayldan qurilib joyida turadi.
        build_manual_route(
            db, order.id, part, codes, posts, packaging=packaging, start_seq=start_seq, seen=seen, with_tail=was_custom
        )
        if not was_custom and codes:
            # Yangi qadamlar yozilsin, keyin dum ularning ustiga tushadi.
            await db.flush()
            await unpark_tail(db, part.id, len(codes))
        if entry.has_route:
            restored += 1

    # O'chirilgan qadamlar oxirida bitta UPDATE bilan: qayta yuklash hamma qatorni `is_enabled=True`
    # bilan yaratadi — texnolog o'chirgan amal (matritsadan AUTO qadam ham) jim qayta yonardi.
    await db.flush()
    for key, entry in saved.items():
        part = by_key.get(key)
        if part is None or not entry.disabled:
            continue
        await db.execute(
            update(PartRoute)
            .where(
                PartRoute.part_id == part.id,
                PartRoute.process_code.in_(entry.disabled),
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .values(is_enabled=False)
        )

    lost = [f"{p}_{c}" for (p, c), entry in saved.items() if entry.has_route and (p, c) not in by_key]
    return restored, lost


async def wipe_previous_parse(db: AsyncSession, order: Order, upload_root: Path) -> list[str]:
    """Re-upload replaces everything derived from the old file.

    Eski `.project`/SCX fayllari diskdan O'CHIRILMAYDI — `<yo'l>.stale` ga qayta nomlanadi
    va yo'llar ro'yxati qaytariladi. Yangi ingest aynan o'sha nomlarga yozadi (SCX nomi = QR,
    project nomi = fayl nomi); ingest yiqilsa chaqiruvchi `db.rollback()` dan keyin
    `restore_stale_files` bilan eskilarni qaytaradi (yarim yozilgan yangining ustidan),
    muvaffaqiyatda `db.commit()` dan keyin `drop_stale_files` `.stale` larni o'chiradi."""
    now = datetime.now(UTC)
    for model in (Product, Part, PartInstance, PartRoute, WasteItem):
        await db.execute(
            update(model)
            .where(model.order_id == order.id, model.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=now)
        )
    # Fayllarda yo'l ham kerak (diskdan o'chirish uchun) — avval yo'llar, keyin bulk UPDATE
    file_where = (
        OrderFile.order_id == order.id,
        OrderFile.kind.in_([FileKind.PROJECT, FileKind.SCX]),
        OrderFile.is_deleted == False,  # noqa: E712
    )
    paths = (await db.execute(select(OrderFile.path).where(*file_where))).scalars().all()
    await db.execute(update(OrderFile).where(*file_where).values(is_deleted=True, deleted_at=now))
    for rel in paths:
        f = upload_root / rel
        if f.is_file():
            f.replace(_stale(f))
    return list(paths)


def _stale(f: Path) -> Path:
    return f.with_name(f.name + ".stale")


def restore_stale_files(stale: list[str], upload_root: Path) -> None:
    """Ingest yiqildi: eski fayllar asl nomiga qaytadi (yangi yozilganning ustidan)."""
    for rel in stale:
        f = upload_root / rel
        if _stale(f).is_file():
            _stale(f).replace(f)


def drop_stale_files(stale: list[str], upload_root: Path) -> None:
    """Eski parse fayllarining `.stale` nusxalarini COMMIT'DAN KEYIN o'chirish."""
    for rel in stale:
        _stale(upload_root / rel).unlink(missing_ok=True)


# Sarf birligi: list va kromkada faylda `unit` yo'q, furnitura esa doim 'шт' beradi.
_USAGE_UNITS = {"sheet": "list", "band": "metr", "hardware": "dona"}


def _build_and_write_scx(
    scx_dir: Path, pp: ParsedPart, qr_texts: list[str], plate_thickness: float | None
) -> list[tuple[str, int]]:
    """SCX XML'ni qurib diskka yozadi (thread'da chaqiriladi). Qaytadi: (fayl nomi, hajmi)."""
    scx_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, content in build_scx_files(pp, qr_texts, plate_thickness=plate_thickness):
        (scx_dir / filename).write_text(content, encoding="utf-8")
        written.append((filename, len(content.encode())))
    return written


async def write_and_register_scx(
    db: AsyncSession,
    order_id: int,
    part_id: int,
    pp: ParsedPart,
    qr_texts: list[str],
    upload_root: Path,
    plate_thickness: float | None = None,
) -> int:
    """SCX fayllarni diskka yozib, har biriga OrderFile qatori qo'shadi.

    Ham birinchi ingest, ham "SCX qayta yaratish" (orders.regenerate_order_scx) shu yo'ldan
    o'tadi — fayl nomi/joyi va OrderFile maydonlari bir joyda. Nechta fayl yaratilgani qaytadi.
    """
    scx_dir = upload_root / "scx" / str(order_id)
    # XML qurish ham, diskka yozish ham thread'da: bittasi ham event loop'ni
    # (terminallar, TABLO, WebSocket) to'xtatib qo'ymasin.
    written = await run_in_threadpool(_build_and_write_scx, scx_dir, pp, qr_texts, plate_thickness)
    for filename, size in written:
        db.add(
            OrderFile(
                order_id=order_id,
                part_id=part_id,
                kind=FileKind.SCX,
                path=str((scx_dir / filename).relative_to(upload_root)),
                filename=filename,
                size=size,
            )
        )
    return len(written)


async def rebuild_order_scx(db: AsyncSession, order: Order, upload_root: Path) -> tuple[int, list[str]] | None:
    """SCX fayllarni saqlangan `.project` dan qayta yaratadi. Caller commits.

    Qaytadi: `(yaratilgan fayl soni, almashtirilgan eski yo'llar)`, yoki `.project`
    diskda bo'lmasa `None`. QR'lar BAZADAN olinadi — matritsada soni o'zgargan
    detalning yangi nusxasi ham fayl oladi (fayl nomi = nusxa QR'i).
    Eski yo'llarni commit'dan KEYIN `purge_replaced_scx` o'chiradi.
    """
    project_row = (
        await db.execute(
            select(OrderFile)
            .where(
                OrderFile.order_id == order.id,
                OrderFile.kind == FileKind.PROJECT,
                OrderFile.is_deleted == False,  # noqa: E712
            )
            .order_by(OrderFile.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if project_row is None or not (upload_root / project_row.path).is_file():
        return None

    project_path = upload_root / project_row.path
    # Saqlangan fayl: ID'lar bazada bor — yuklash qoidasi (`check_ids`) qo'llanmaydi, aks holda qoidadan
    # oldin yuklangan kirill ID'li buyurtmaning SCX'i endi qayta yaratilmay qolardi
    project = await run_in_threadpool(lambda: parse_project(project_path.read_bytes(), check_ids=False))

    parts_by_key: dict[str, Part] = {
        f"{product_code}_{part.code}": part
        for part, product_code in (
            await db.execute(
                select(Part, Product.code)
                .join(Product, Product.id == Part.product_id)
                .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
            )
        ).all()
    }
    qr_by_part: dict[int, list[str]] = {}
    for inst in (
        (
            await db.execute(
                select(PartInstance)
                .where(PartInstance.order_id == order.id, PartInstance.is_deleted == False)  # noqa: E712
                .order_by(PartInstance.part_id, PartInstance.instance_no)
            )
        )
        .scalars()
        .all()
    ):
        qr_by_part.setdefault(inst.part_id, []).append(inst.qr_text)

    now = datetime.now(UTC)
    old_files = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order.id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    # Yo'llar HOZIR yig'iladi, o'chirish esa commit'dan keyin: generatsiya yiqilsa DB
    # rollback qatorlarni tiriltiradi, fayl esa diskda qolishi shart.
    old_paths = [f.path for f in old_files]
    for f in old_files:
        f.is_deleted = True
        f.deleted_at = now

    plate_by_name = plate_thickness_map(project)
    created = 0
    for pp in project.all_parts:
        part = parts_by_key.get(pp.key)
        if part is None or not pp.xnc_ops:
            continue
        created += await write_and_register_scx(
            db,
            order.id,
            part.id,
            pp,
            qr_by_part.get(part.id, []),
            upload_root,
            plate_thickness=plate_by_name.get(pp.material_name or ""),
        )
    return created, old_paths


async def purge_replaced_scx(db: AsyncSession, order_id: int, old_paths: list[str], upload_root: Path) -> None:
    """`rebuild_order_scx` almashtirgan eski fayllarni diskdan olib tashlaydi (commit'dan KEYIN).

    Nom = nusxa QR'i, ya'ni yangi fayl eskisi bilan ustma-ust tushishi mumkin —
    hali ham tirik qator ishora qilayotgan yo'lga tegilmaydi.
    """
    if not old_paths:
        return
    live_paths = set(
        (
            await db.execute(
                select(OrderFile.path).where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars()
    )
    for path in old_paths:
        if path not in live_paths:
            (upload_root / path).unlink(missing_ok=True)


async def ingest_project(
    db: AsyncSession,
    order: Order,
    project: ParsedProject,
    raw_content: bytes,
    original_filename: str,
    upload_root: Path,
) -> dict[str, Any]:
    """Create all DB rows + files for a parsed PROCESSED project. Caller commits."""
    # Nostandart qoidasi sozlamadan BIR MARTA o'qiladi: sikl ichida har detal uchun
    # so'rov qilinsa yuzlab ortiqcha SELECT chiqardi.
    nostandart = _nostandart_qoidasi(await get_setting(db, CUSTOM_PART_SUFFIX))
    nostandart_ids: list[int] = []

    # Yuklangan fayl nomi yo'l qismisiz saqlanadi — "../" bilan uploads tashqarisiga
    # yozishning oldi olinadi
    original_filename = Path(original_filename).name or "project.project"

    # QR to'qnashuvini OLDINDAN aniqlash: masalan "010" (2 nusxa) va "010_2" kodli
    # detal bir xil QR beradi — unique indeks 500 bermasin, do'stona xato bersin
    qr_owner: dict[str, str] = {}
    for pp in project.all_parts:
        for qr in pp.qr_texts:
            if qr in qr_owner:
                raise ParseError(
                    f"Detal ID to'qnashuvi: {qr} ham {qr_owner[qr]}, ham {pp.key} uchun chiqdi. "
                    "GibLab'da detal kodlarini tekshiring."
                )
            qr_owner[qr] = pp.key

    # Kalit — matn: marshrut kodlari ham matn (PROCESS_POSTS), va noma'lum post
    # `get()` da None beradi (enumga aylantirilsa ValueError -> 500 bo'lardi)
    posts = {str(p.code): p for p in (await db.execute(select(Post))).scalars()}
    # Anketadagi "Upakovka qilish" xizmati — marshrutga qadoqlash qadamini
    # qo'shadimi. `survey` JSONB, eski yozuvda kalit umuman bo'lmasligi mumkin.
    packaging = order.needs_packaging

    # Kesish xaritasi CS blobini ochadi va katakchalarni hisoblaydi — sof CPU, thread'da.
    cutmap = await run_in_threadpool(build_cutmap, project) if any(c.data_blob for c in project.cut_ops) else None

    # --- store the raw project file ---
    project_dir = upload_root / "projects" / str(order.id)
    project_dir.mkdir(parents=True, exist_ok=True)
    project_path = project_dir / original_filename
    await run_in_threadpool(project_path.write_bytes, raw_content)
    db.add(
        OrderFile(
            order_id=order.id,
            kind=FileKind.PROJECT,
            path=str(project_path.relative_to(upload_root)),
            filename=original_filename,
            size=len(raw_content),
        )
    )

    # Plita qalinligi material nomi bo'yicha — qo'shqavat detal SCX'i uchun (scx.py)
    _plate_thickness = plate_thickness_map(project)

    # --- products, parts, instances, routes, scx ---
    bindings_by_key: dict[str, list[Any]] = {}
    if cutmap:
        for b in cutmap.bindings:
            bindings_by_key.setdefault(b.part_key, []).append(b)

    parts_created = 0
    instances_created = 0
    for parsed_product in project.products:
        product = Product(
            order_id=order.id,
            code=parsed_product.code,
            name=parsed_product.name,
            count=parsed_product.count,
        )
        db.add(product)
        await db.flush()

        for pp in parsed_product.parts:
            merged = pp.merged_machining()
            part = Part(
                order_id=order.id,
                product_id=product.id,
                code=pp.code,
                name=pp.name,
                count=pp.count,
                length=pp.length,
                width=pp.width,
                thickness=pp.thickness,
                txt=pp.txt,
                material_name=pp.material_name,
                is_custom=nostandart(pp.name),
                label_num=pp.label_num,
                edges=pp.edges,
                xnc_summary={
                    "bores": len(merged.bores) if merged else 0,
                    "edge_bores": len(merged.edge_bores) if merged else 0,
                    "grooves": len(merged.grooves) if merged else 0,
                    "mills": len(merged.mills) if merged else 0,
                    # Paz va freza QAYSI qirrada — chek va KROMKA terminali shundan
                    # o'qiydi (`XncOp.machined_sides`, sabab docs/09 da). `sides` NOMI BAND:
                    # `1cfd3b2182fc` downgrade'i uni BUTUN SON deb o'qiydi
                    # (`(xnc_summary->>'sides')::int = 2`), shuning uchun `mill_sides`.
                    "groove_sides": merged.machined_sides(pp.length, pp.width, tur="paz") if merged else [],
                    "mill_sides": merged.machined_sides(pp.length, pp.width, tur="freza") if merged else [],
                    # Xom yo'llar — chek eskizi va kesish xaritasi kartochkasi qirraga
                    # tushmagan ishlovni (o'rtadagi ariq, doira o'yiq) SHULARDAN chizadi.
                    # Ishlovli 123 detalda o'rtacha 209 bayt, jami 25 KB (ixcham JSON,
                    # 45 loyihali korpusda o'lchangan).
                    "groove_paths": paths_json(merged.paths("paz")) if merged else [],
                    "mill_paths": paths_json(merged.paths("freza")) if merged else [],
                },
            )
            db.add(part)
            await db.flush()
            parts_created += 1
            if part.is_custom:
                nostandart_ids.append(part.id)

            # instances with cut-map cell binding
            cell_bindings = bindings_by_key.get(pp.key, [])
            qrs = pp.serial_qrs(order.number)
            for n in range(1, pp.count + 1):
                binding = cell_bindings[n - 1] if n - 1 < len(cell_bindings) else None
                db.add(
                    PartInstance(
                        order_id=order.id,
                        part_id=part.id,
                        instance_no=n,
                        qr_text=qrs[n - 1],
                        pattern_no=binding.pattern_no if binding else None,
                        cell_index=binding.cell_index if binding else None,
                    )
                )
                instances_created += 1

            # STANDART marshrut — faqat fayl mazmunidan. Qadamlar TARTIBLI:
            # (process_code, post_code, per_instance); tartib skan navbatini belgilaydi.
            # Rover/stolyarka/bo'yoq bu yerdan CHIQMAYDI: roverdan chiqqan detal keyin
            # bo'yalishi mumkinligini fayl bilmaydi — texnolog uni "nostandart" deb
            # belgilab, marshrutini o'zi chizadi.
            # Post sozlanmagan bo'lsa `resolve_post()` tushunarli ParseError beradi.
            steps: list[tuple[int, PostCode, int]] = []
            # ARRA — faqat listdan kesiladigan detalga. Optimizatsiya qilingan faylda
            # materiali ham, yorliq raqami ham yo'q detal umuman listga joylashtirilmagan
            # (masalan kupe alyuminiy profillari) — unga ARRA vazifasi berilsa arrachi
            # kesa olmaydigan soxta ish paydo bo'lardi. CS ro'yxatida turgani ham yetarli
            # emas: `usedCount="0"` detalni GibLab ataylab joylashtirmagan (`pp.placed`).
            if pp.placed and (pp.material_name or pp.label_num is not None):
                steps.append((1, PostCode.ARRA, 1))  # 1 = Raspil
            if pp.kromka_sides:
                steps.append((3, PostCode.KROMKA, pp.kromka_sides))  # 3 = Kromka
            if prisadka := pp.prisadka_passes():
                steps.append((6, PostCode.PRISADKA, prisadka))  # 6 = Prisadka
            # Qadoqlash — anketada belgilangan bo'lsa HAMMA detalga oxirgi qadam.
            # Qisman qadoqlash yo'q: buyurtma yo butunlay qadoqlanadi, yo yo'q.
            if packaging:
                steps.append((15, PostCode.UPAKOVKA, 1))
            # TMO — eng oxirgi qadam, qadoqlangan-qadoqlanmaganidan qat'i nazar.
            # Omborchi qabul qilmaguncha detal tugallanmagan bo'lib turadi.
            steps.append((16, PostCode.TMO, 1))
            for seq, (process_code, post_code, per_instance) in enumerate(steps, start=1):
                post = resolve_post(posts, post_code)
                db.add(
                    PartRoute(
                        order_id=order.id,
                        part_id=part.id,
                        post_id=post.id,
                        seq=seq,
                        process_code=process_code,
                        source=RouteSource.AUTO,
                        per_instance=per_instance,
                        total_required=pp.count * per_instance,
                    )
                )

            # SCX: har nusxaga bitta TO'LIQ fayl (old + orqa Face=6
            # birlashgan, nom/ID = QR — Nanxing skaneri to'g'ridan-to'g'ri topadi).
            # plate: qo'shqavat detalda (32mm) eksport qalinligi plita bo'yicha
            plate = _plate_thickness.get(pp.material_name or "")
            await write_and_register_scx(db, order.id, part.id, pp, qrs, upload_root, plate_thickness=plate)

    # --- order metadata ---
    # `code` — tsexning `goods.xls` katalogidagi SKU. Parser uni o'qiydi, lekin bu yerda
    # tushib qolardi: materiallar ombori va material hisoboti faqat nomni ko'rardi. Tsex katalogga
    # o'tgandan keyin (yangi eksportlarda `code="110083"`, `code="КРМ1009"`) nom emas, kod
    # barqaror kalit. Eski fayllarda `code` yo'q — o'shanda `None` bo'lib qoladi.
    order.material_usage = [
        {"name": m.name, "code": m.code, "kind": m.kind, "count": m.count, "unit": _USAGE_UNITS[m.kind]}
        for m in project.materials
        if m.count
    ]
    order.project_uuid = project.uuid
    # Nomi bo'yicha nostandart bo'lgan detalning AUTO marshruti YUMSHOQ o'chiriladi —
    # `restore_custom_routes` dagi bilan bir xil naqsh va bir xil sabab. Umuman
    # qurmaslik yaramaydi: texnolog keyin bayroqni olib tashlasa (matritsadagi
    # checkbox) tiklanadigan qator qolmasdi va detal marshrutsiz qolardi.
    if nostandart_ids:
        await db.execute(
            update(PartRoute)
            .where(PartRoute.part_id.in_(nostandart_ids), PartRoute.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=datetime.now(UTC))
        )

    # Nom YUKLANGAN FAYL nomidan olinadi (kengaytmasiz): "2064 alisher.project" -> "2064 alisher".
    # Ilgari `project.name` — ya'ni fayl ICHIDAGI `<root name=...>` atributi ishlatilardi, lekin
    # GibLab eksportlarining bir qismida u umuman bo'lmaydi: prodda 39 buyurtmadan faqat 19 tasida
    # nom bor edi, qolganlarida `.project` fayli yuklangan bo'lsa ham nom BO'SH qolardi va reestrda
    # ham, TABLOda ham ko'rinmasdi. Fayl nomi esa doim bor.
    order.project_name = Path(original_filename).stem or project.name
    order.project_loaded_at = datetime.now(UTC)
    order.cutmap = cutmap.model if cutmap else None

    # FOYDALI atxotlar (GibLab `business="true"`) — chek va treking uchun yozuv.
    # QR prefiksi "ATX-": skan dvijoki detal QR'i bilan adashtirmasin. Raqamlash
    # material/list tartibida — chekdagi raqam xaritadagi bilan mos keladi.
    if cutmap:
        atx_n = 0
        for mat in cutmap.model.get("materials", []):
            for sh in mat.get("sheets", []):
                for cell in sh.get("parts", []):
                    if not (cell.get("waste") and cell.get("business")):
                        continue
                    atx_n += 1
                    # Katakka raqam yoziladi (order.cutmap JSONB ga tushadi) —
                    # frontend shu raqam orqali WasteItem'ni topadi.
                    cell["atx"] = atx_n
                    db.add(
                        WasteItem(
                            order_id=order.id,
                            material_name=str(mat.get("name") or "")[:150],
                            sheet_no=int(sh.get("no") or 0),
                            length=float(cell.get("w") or 0),
                            width=float(cell.get("h") or 0),
                            qr_text=f"ATX-{order.number}-{atx_n}",
                        )
                    )

    # Kesish xaritasi qurilgan bo'lsa: unda joyi yo'q detallarni texnolog bilishi shart.
    # Uch sabab bo'ladi — (a) listdan kesilmaydigan profil, (b) GibLab uni ataylab
    # joylashtirmagan (usedCount=0), ya'ni material yetmagan yoki dizayner chiqarib tashlagan,
    # (c) material optimallashtirilmagan (blobsiz CS — `build_cutmap` uni o'tkazib yuboradi).
    unplaced: list[str] = []
    if cutmap:
        placed = {b.part_key for b in cutmap.bindings}
        ghosts = [p for p in project.all_parts if p.key not in placed]
        # To'liq ro'yxat yuklash javobiga ham ketadi — texnolog oynada hammasini ko'radi
        # (ogohlantirish matnidagi 5 ta nom va 4 soniyalik toast ko'zdan qochgan edi)
        unplaced = [f"{p.key} ({p.name})" for p in ghosts]
        if ghosts:
            names = ", ".join(f"{p.code} ({p.name})" for p in ghosts[:5])
            more = f" va yana {len(ghosts) - 5} ta" if len(ghosts) > 5 else ""
            project.warnings.append(
                f"Kesish xaritasida {len(ghosts)} ta detalning joyi yo'q: {names}{more}. "
                f"Ular arrachi ro'yxatiga tushmaydi."
            )

    return {
        "products": len(project.products),
        "parts": parts_created,
        "instances": instances_created,
        "materials": len(project.materials),
        "warnings": project.warnings,
        "unplaced": unplaced,
    }
