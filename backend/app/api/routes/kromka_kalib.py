"""Kromka kalibrlash sessiyalari (docs/12 §4.19, 2-qadam — hisob, Pico'ga QO'LLAMASDAN).

Admin sessiyani boshlaydi va etalon detallarni oddiy ish rejimida o'tkazadi: Pico har o'tishda
`olchov` yuboradi (`d1`, `d2`, `ish_ms`), shu oraliqdagi hodisalar nuqta bo'ladi. Hisob —
stansiyaning aynan algoritmi (`services/kromka_kalib.py`).

3-qadam (§4.20): tugagan sessiya natijasini Pico'ga qo'llash va orqaga qaytarish. Qiymatlar
mijozdan OLINMAYDI — server sessiyadan qayta hisoblaydi va chegaralarni tekshiradi."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.crud import log_action
from app.models import AndonEvent, KromkaKalApply, KromkaKalibSession, Machine, Post
from app.models.enums import PostCode
from app.schemas.kromka_kalib import (
    KalApplyRow,
    KalibDetail,
    KalibEtalon,
    KalibExclude,
    KalibPoint,
    KalibSessionRow,
    KalibStart,
)
from app.services.kromka_kalib import (
    Nuqta,
    etalon,
    hisobla,
    holati,
    nuqta,
    qollash_qiymatlari,
    set_qatori,
    tekshir,
)

router = APIRouter(prefix="/kromka-kalib", tags=["kromka-kalib"])

_KAL_KEYS = ("D", "V10", "V18", "K1", "K2", "B1", "B2", "C", "TD")


def _row(s: KromkaKalibSession, name: str) -> KalibSessionRow:
    return KalibSessionRow(
        id=s.id,
        machine_id=s.machine_id,
        machine_name=name,
        started_at=s.started_at,
        ended_at=s.ended_at,
        segments=s.segments,
    )


async def _get(db: SessionDep, session_id: int) -> tuple[KromkaKalibSession, str]:
    row = (
        await db.execute(
            select(KromkaKalibSession, Machine.name)
            .join(Machine, Machine.id == KromkaKalibSession.machine_id)
            .where(KromkaKalibSession.id == session_id, KromkaKalibSession.is_deleted == False)  # noqa: E712
        )
    ).first()
    if row is None:
        raise NotFoundException("Kalibrlash sessiyasi topilmadi")
    return row[0], row[1]


async def _ochiq(db: SessionDep, session_id: int) -> tuple[KromkaKalibSession, str]:
    s, name = await _get(db, session_id)
    if s.ended_at is not None:
        raise DuplicateValueException("Sessiya allaqachon tugagan")
    return s, name


@router.get("", response_model=list[KalibSessionRow], operation_id="read_kalib_sessions")
async def read_kalib_sessions(db: SessionDep, _: AdminUser) -> list[KalibSessionRow]:
    rows = await db.execute(
        select(KromkaKalibSession, Machine.name)
        .join(Machine, Machine.id == KromkaKalibSession.machine_id)
        .where(KromkaKalibSession.is_deleted == False)  # noqa: E712
        .order_by(KromkaKalibSession.started_at.desc())
        .limit(30)
    )
    return [_row(s, name) for s, name in rows.tuples().all()]


@router.post("", response_model=KalibSessionRow, operation_id="start_kalib_session")
async def start_kalib_session(db: SessionDep, user: AdminUser, body: KalibStart) -> KalibSessionRow:
    machine = (
        await db.execute(
            select(Machine)
            .join(Post, Post.id == Machine.post_id)
            .where(Machine.id == body.machine_id, Post.code == PostCode.KROMKA, Machine.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if machine is None:
        raise NotFoundException("Kromka ish markazi topilmadi")
    ochiq = await db.scalar(
        select(KromkaKalibSession.id).where(
            KromkaKalibSession.machine_id == body.machine_id,
            KromkaKalibSession.ended_at.is_(None),
            KromkaKalibSession.is_deleted == False,  # noqa: E712
        )
    )
    if ochiq is not None:
        raise DuplicateValueException("Bu stanokda kalibrlash sessiyasi allaqachon ochiq")
    now = datetime.now(UTC)
    s = KromkaKalibSession(
        machine_id=machine.id,
        started_at=now,
        created_by_id=user.id,
        segments=[{"L_ref": body.L_ref, "dan": now.isoformat()}],
    )
    db.add(s)
    await db.commit()
    return _row(s, machine.name)


@router.put("/{session_id}/etalon", response_model=KalibSessionRow, operation_id="set_kalib_etalon")
async def set_kalib_etalon(db: SessionDep, _: AdminUser, session_id: int, body: KalibEtalon) -> KalibSessionRow:
    """Keyingi o'tishlar boshqa etalon — shu lahzadan yangi bo'lak."""
    s, name = await _ochiq(db, session_id)
    s.segments = [*s.segments, {"L_ref": body.L_ref, "dan": datetime.now(UTC).isoformat()}]
    await db.commit()
    return _row(s, name)


@router.post("/{session_id}/end", response_model=KalibSessionRow, operation_id="end_kalib_session")
async def end_kalib_session(db: SessionDep, _: AdminUser, session_id: int) -> KalibSessionRow:
    s, name = await _ochiq(db, session_id)
    s.ended_at = datetime.now(UTC)
    await db.commit()
    return _row(s, name)


@router.put("/{session_id}/points/{event_id}", response_model=KalibSessionRow, operation_id="exclude_kalib_point")
async def exclude_kalib_point(
    db: SessionDep, _: AdminUser, session_id: int, event_id: int, body: KalibExclude
) -> KalibSessionRow:
    """Nuqtani hisobdan chetlatish/qaytarish (etalon noto'g'ri qo'yilgan, qo'l tegdi va h.k.)."""
    s, name = await _get(db, session_id)
    qolgan = [i for i in s.excluded if i != event_id]
    s.excluded = [*qolgan, event_id] if body.excluded else qolgan
    await db.commit()
    return _row(s, name)


def _son(v: object) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


async def _joriy(db: SessionDep, machine_id: int) -> dict[str, float]:
    """Pico'dagi joriy KAL — oxirgi `kal` hodisasidan."""
    kal = await db.scalar(
        select(AndonEvent.payload)
        .where(AndonEvent.machine_id == machine_id, AndonEvent.kind == "kal", AndonEvent.is_deleted == False)  # noqa: E712
        .order_by(AndonEvent.happened_at.desc(), AndonEvent.id.desc())
        .limit(1)
    )
    return {k: v for k in _KAL_KEYS if (v := _son((kal or {}).get(k))) is not None}


async def _hisob(
    db: SessionDep, s: KromkaKalibSession
) -> tuple[list[tuple[int, datetime, dict[str, Any], Nuqta]], dict[str, Any] | None]:
    """Sessiya nuqtalari `(hodisa id, vaqt, payload, Nuqta)` va hisob natijasi."""
    q = select(AndonEvent.id, AndonEvent.happened_at, AndonEvent.payload).where(
        AndonEvent.machine_id == s.machine_id,
        AndonEvent.kind == "olchov",
        AndonEvent.is_deleted == False,  # noqa: E712
        AndonEvent.happened_at >= s.started_at,
    )
    if s.ended_at is not None:
        q = q.where(AndonEvent.happened_at <= s.ended_at)
    events = (await db.execute(q.order_by(AndonEvent.happened_at, AndonEvent.id))).tuples().all()
    excluded = set(s.excluded)
    jadval = []
    for eid, at, payload in events:
        L = etalon(s.segments, at)
        p = nuqta(eid, L, payload) if L else None
        if p is not None:
            jadval.append((eid, at, payload, p))
    return jadval, hisobla([p for eid, _a, _p, p in jadval if eid not in excluded])


def _apply_row(a: KromkaKalApply, now: datetime) -> KalApplyRow:
    return KalApplyRow(
        id=a.id,
        session_id=a.session_id,
        rollback_of_id=a.rollback_of_id,
        values=a.values,
        previous=a.previous,
        created_at=a.created_at,
        sent_at=a.sent_at,
        confirmed_at=a.confirmed_at,
        status=holati(a.confirmed_at, a.created_at, now),
        line=set_qatori(a.values),
    )


@router.get("/{session_id}", response_model=KalibDetail, operation_id="read_kalib_session")
async def read_kalib_session(db: SessionDep, _: AdminUser, session_id: int) -> KalibDetail:
    s, name = await _get(db, session_id)
    jadval, result = await _hisob(db, s)
    excluded = set(s.excluded)
    now = datetime.now(UTC)
    applies = (
        await db.scalars(
            select(KromkaKalApply)
            .where(KromkaKalApply.machine_id == s.machine_id, KromkaKalApply.is_deleted == False)  # noqa: E712
            .order_by(KromkaKalApply.created_at.desc())
            .limit(10)
        )
    ).all()
    return KalibDetail(
        **_row(s, name).model_dump(),
        points=[
            KalibPoint(
                event_id=eid,
                at=at,
                L_ref=p.L_ref,
                S=p.S,
                L_pico=_son(payload.get("L")),
                kod=str(payload["kod"]) if payload.get("kod") else None,
                t1=p.t1,
                t2=p.t2,
                dtm=p.dtm,
                Lfit=p.Lfit if eid not in excluded else None,
                err=p.err if eid not in excluded else None,
                chet=p.chet,
                excluded=eid in excluded,
            )
            for eid, at, payload, p in jadval
        ],
        result=result,
        current=await _joriy(db, s.machine_id),
        applies=[_apply_row(a, now) for a in applies],
    )


async def _kutilayotgan(db: SessionDep, machine_id: int) -> None:
    """Stanokda javob kutayotgan buyruq bo'lsa — yangisi berilmaydi (ikkalasi navbatlashib ketmasin)."""
    now = datetime.now(UTC)
    rows = await db.scalars(
        select(KromkaKalApply).where(
            KromkaKalApply.machine_id == machine_id,
            KromkaKalApply.confirmed_at.is_(None),
            KromkaKalApply.is_deleted == False,  # noqa: E712
        )
    )
    if any(holati(None, a.created_at, now) == "kutilmoqda" for a in rows.all()):
        raise DuplicateValueException("Oldingi buyruq hali Pico javobini kutmoqda")


async def _yoz(db: SessionDep, user_id: int | None, request: Request, a: KromkaKalApply, action: str) -> KalApplyRow:
    db.add(a)
    await db.flush()
    log_action(
        db,
        module="kromka_kalib",
        action=action,
        user_id=user_id,
        entity_type="kromka_kal_apply",
        entity_id=a.id,
        message=set_qatori(a.values),
        meta={"machine_id": a.machine_id, "values": a.values, "previous": a.previous},
        ip=client_ip(request),
    )
    await db.commit()
    return _apply_row(a, datetime.now(UTC))


@router.post("/{session_id}/apply", response_model=KalApplyRow, operation_id="apply_kalib_session")
async def apply_kalib_session(db: SessionDep, user: AdminUser, session_id: int, request: Request) -> KalApplyRow:
    """Tugagan sessiya natijasini Pico'ga qo'llash (`SET`). Agent keyingi andon javobida oladi."""
    s, _name = await _get(db, session_id)
    if s.ended_at is None:
        raise HTTPException(status_code=409, detail="Avval sessiyani tugating")
    _jadval, result = await _hisob(db, s)
    if not result or not result["qollasa_boladi"]:
        raise HTTPException(status_code=409, detail="Qo'llash uchun kamida 2 xil uzunlikdagi etalon kerak")
    joriy = await _joriy(db, s.machine_id)
    if "D" not in joriy:
        raise HTTPException(
            status_code=409, detail="Pico'dagi joriy qiymatlar noma'lum — agent 1.11.0+ va ulangan Pico kerak"
        )
    values = qollash_qiymatlari(result)
    if xato := tekshir(values, joriy):
        raise HTTPException(status_code=422, detail=f"Qo'llanmadi: {xato}")
    await _kutilayotgan(db, s.machine_id)
    a = KromkaKalApply(
        machine_id=s.machine_id,
        session_id=s.id,
        values=values,
        previous={k: joriy[k] for k in values if k in joriy},
        created_by_id=user.id,
    )
    return await _yoz(db, user.id, request, a, "kal_apply")


@router.post("/applies/{apply_id}/rollback", response_model=KalApplyRow, operation_id="rollback_kal_apply")
async def rollback_kal_apply(db: SessionDep, user: AdminUser, apply_id: int, request: Request) -> KalApplyRow:
    """Qo'llashdan oldingi qiymatlarni qaytarish — yangi buyruq. Chegara tekshiruvisiz: bu
    qiymatlar Pico'ning o'zida turgan edi."""
    old = await db.get(KromkaKalApply, apply_id)
    if old is None or old.is_deleted:
        raise NotFoundException("Qo'llash topilmadi")
    await _kutilayotgan(db, old.machine_id)
    joriy = await _joriy(db, old.machine_id)
    a = KromkaKalApply(
        machine_id=old.machine_id,
        session_id=old.session_id,
        values=old.previous,
        previous={k: joriy[k] for k in old.previous if k in joriy},
        rollback_of_id=old.id,
        created_by_id=user.id,
    )
    return await _yoz(db, user.id, request, a, "kal_rollback")
