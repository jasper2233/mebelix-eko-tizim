"""Buyurtma fayllari: `.project` yuklash, SCX yaratish/berish, kesish xaritasi."""

import io
import zipfile
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.api.deps import SessionDep, StaffReadUser, TexnologUser, client_ip
from app.core.config import settings, upload_root
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import OrderFile, Part, PartInstance, Post, Product
from app.models.enums import FileKind, OrderStatus, PostCode
from app.schemas.common import Message
from app.schemas.terminal import CutmapState
from app.services.giblab import ParseError, parse_project
from app.services.giblab.cutmap import build_cutmap_state
from app.services.giblab.ingest import (
    drop_stale_files,
    ingest_project,
    restore_custom_routes,
    restore_stale_files,
    snapshot_custom_routes,
    wipe_previous_parse,
    write_and_register_scx,
)
from app.services.giblab.scx import plate_thickness_map

from ._common import _get_order, _get_visible_order, _require_editable

router = APIRouter()


@router.post("/{order_id}/upload", response_model=Message, operation_id="upload_order_project")
async def upload_order_project(
    db: SessionDep, current_user: TexnologUser, order_id: int, file: UploadFile, request: Request
) -> Message:
    """Texnolog uploads the .project file (TZ 6.3). Exactly ONE file per order; re-upload
    replaces all previous parse results.

    Ishlab chiqarishga uzatilgan buyurtmaga ham QAYTA yuklash mumkin — TO hech bir
    postda amal bajarilmagan bo'lsa (`_require_editable`). Bekor qilingan skan
    hisobga olinmaydi: arrada ikki detalga chek chiqarib keyin bekor qilinsa,
    jarayonda hech narsa qolmaydi va fayl yana almashtiriladi.
    """
    order = await _get_order(db, order_id)
    if order.status == OrderStatus.DRAFT:
        raise ForbiddenException(
            "Fayl faqat tasdiqlangan buyurtmaga yuklanadi. Avval manager buyurtmani tasdiqlashi kerak."
        )
    await _require_editable(db, order, "Faylni qayta yuklab bo'lmaydi")
    if not (file.filename or "").lower().endswith(".project"):
        raise HTTPException(status_code=422, detail="Faqat .project kengaytmali fayl qabul qilinadi.")

    # QAYTA yuklashni AJRATIB olamiz — pastdagi `wipe_previous_parse` va `ingest`
    # `project_uuid` ni almashtiradi, ya'ni logni yozish paytida bu fakt yo'qolgan
    # bo'ladi. Loglarda "yuklandi" va "qayta yuklandi" bir xil ko'rinsa, texnolog
    # faylni necha marta almashtirgani bilinmasdi.
    qayta_yuklash = order.project_uuid is not None

    content = await file.read()
    if len(content) > settings.MAX_PROJECT_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Fayl juda katta.")

    try:
        # Parse sof CPU (50 MB gacha XML) — event loop'da bajarilsa hamma terminal,
        # TABLO va WebSocket shu vaqtga muzlab qolardi.
        project = await run_in_threadpool(parse_project, content)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if project.generation == "template":
        # TZ 5.3.3: TEMPLATE = not yet optimized in GibLab — reject with the exact guidance text.
        raise HTTPException(
            status_code=422,
            detail=(
                "Bu fayl GibLabda hali optimizatsiya qilinmagan. Iltimos, kesish chizmasini va "
                "kromka materiallarini belgilab, qaytadan eksport qilib yuklang."
            ),
        )

    root = upload_root()
    # Qo'lda chizilgan marshrutlar fayldan kelmaydi — qayta yuklashda ular bilan birga
    # yo'qolib ketmasligi uchun detal kodi bo'yicha saqlab turiladi.
    saved_routes = await snapshot_custom_routes(db, order)
    # Eski fayllar `.stale` ga qayta nomlanadi: ingest yiqilsa qaytariladi, commit'dan
    # keyin o'chiriladi. Ilgari unlink tranzaksiya ichida edi — ParseError'da DB orqaga
    # qaytar, fayllar esa qaytmasdi.
    stale_files = await wipe_previous_parse(db, order, root)
    try:
        summary = await ingest_project(db, order, project, content, file.filename or "project.project", root)
        restored, lost = await restore_custom_routes(db, order, saved_routes)
    except Exception as exc:
        await db.rollback()
        restore_stale_files(stale_files, root)
        if isinstance(exc, ParseError):
            raise HTTPException(status_code=422, detail=str(exc)) from None
        raise
    if restored:
        # Nostandart detalgina emas: standart detalga matritsadan qo'shilgan
        # qadam ham MANUAL bo'lib saqlanadi va shu sanoqqa kiradi.
        summary["warnings"].append(f"{restored} detalning qo'lda kiritilgan marshrut qadamlari tiklandi.")
    if lost:
        names = ", ".join(lost[:5]) + (f" va yana {len(lost) - 5} ta" if len(lost) > 5 else "")
        summary["warnings"].append(f"Yangi faylda topilmagani uchun marshruti yo'qolgan detallar: {names}")

    log_action(
        db,
        module="orders",
        action="project_uploaded",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Project fayl {'qayta ' if qayta_yuklash else ''}yuklandi: {file.filename}",
        meta=summary,
        ip=client_ip(request),
    )
    await db.commit()
    drop_stale_files(stale_files, root)
    warnings = summary["warnings"]
    text = (
        f"Fayl qabul qilindi: {summary['products']} mahsulot, {summary['parts']} detal, {summary['instances']} nusxa."
    )
    if warnings:
        # Ogohlantirishlar avval faqat audit logga tushardi — menejer ularni ko'rmasdi.
        text += f" Diqqat ({len(warnings)}): " + " | ".join(warnings[:3])
        if len(warnings) > 3:
            text += f" | va yana {len(warnings) - 3} ta (audit logda to'liq)"
    return Message(message=text)


# NOTE: /{order_id}/files/{file_id} dan OLDIN turishi shart — aks holda
# "scx.zip" file_id deb o'qiladi va 422 qaytadi.
@router.get("/{order_id}/files/scx.zip", operation_id="download_order_scx_zip")
async def download_order_scx_zip(db: SessionDep, current_user: StaffReadUser, order_id: int) -> Response:
    """Barcha SCX dasturlarini bitta arxivda berish — prisadkachi stanokka bittalab emas,
    bitta ZIP ko'chiradi. Fayllar kichik (bir necha KB), xotirada yig'ish yetarli."""
    order = await _get_visible_order(db, current_user, order_id)
    rows = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise NotFoundException("SCX fayllar topilmadi.")
    root = upload_root()
    buf = io.BytesIO()
    written = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            full_path = root / row.path
            if full_path.is_file():
                zf.write(full_path, row.filename)
                written += 1
    # DB'da qator bor, lekin diskda fayl yo'q — bo'sh arxiv o'rniga aniq xato.
    if not written:
        raise NotFoundException("SCX fayllar diskda topilmadi.")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{order.number}_scx.zip"'},
    )


@router.post("/{order_id}/scx/regenerate", response_model=Message, operation_id="regenerate_order_scx")
async def regenerate_order_scx(db: SessionDep, current_user: TexnologUser, order_id: int, request: Request) -> Message:
    """SCX fayllarni saqlangan .project'dan qayta yaratish — eski buyurtmalarni yangi
    nomlashga (har nusxa = QR nomli fayl, Nanxing skan mosligi) o'tkazadi. Detallar,
    marshrutlar va skanlarga TEGILMAYDI."""
    order = await _get_order(db, order_id)
    root = upload_root()

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
    if project_row is None or not (root / project_row.path).is_file():
        raise NotFoundException(".project fayli diskda topilmadi — qayta yaratib bo'lmaydi.")

    project_path = root / project_row.path
    try:
        project = await run_in_threadpool(lambda: parse_project(project_path.read_bytes()))
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=f"Fayl o'qilmadi: {exc}") from None

    # Mavjud detallar (matritsada soni o'zgargan bo'lishi mumkin — QR'lar bazadan olinadi)
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
    for f in old_files:
        f.is_deleted = True
        f.deleted_at = now
        (root / f.path).unlink(missing_ok=True)

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
            root,
            plate_thickness=plate_by_name.get(pp.material_name or ""),
        )

    log_action(
        db,
        module="orders",
        action="scx_regenerated",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"SCX qayta yaratildi: {created} ta fayl ({order.number})",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message=f"{created} ta SCX fayl qayta yaratildi — endi nomlar nusxa QR'i bilan.")


@router.get("/{order_id}/files/{file_id}", operation_id="download_order_file")
async def download_order_file(db: SessionDep, current_user: StaffReadUser, order_id: int, file_id: int) -> FileResponse:
    """Download a stored file (project / SCX / document)."""
    await _get_visible_order(db, current_user, order_id)
    row = (
        await db.execute(
            select(OrderFile).where(
                OrderFile.id == file_id,
                OrderFile.order_id == order_id,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Fayl topilmadi.")
    full_path = upload_root() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    if row.kind in (FileKind.PROJECT, FileKind.SCX):
        media_type = "application/xml"
    else:
        # anketa rasmlari <img> da ko'rsatiladi — to'g'ri turi bo'lmasa brauzer yuklab oladi
        media_type = str(row.meta.get("content_type") or "application/octet-stream")
    return FileResponse(full_path, filename=row.filename, media_type=media_type)


@router.get("/{order_id}/cutmap", response_model=CutmapState, operation_id="read_order_cutmap")
async def read_order_cutmap(db: SessionDep, current_user: StaffReadUser, order_id: int) -> CutmapState:
    """Kesish xaritalari (TZ 10.3): manager/texnolog view + browser-print for a paper copy."""
    order = await _get_visible_order(db, current_user, order_id)
    arra_post = (await db.execute(select(Post).where(Post.code == PostCode.ARRA))).scalar_one_or_none()
    if arra_post is None:
        raise NotFoundException("ARRA posti topilmadi.")
    return await build_cutmap_state(db, order, arra_post.id)
