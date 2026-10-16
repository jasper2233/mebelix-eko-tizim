"""Kromka kalibrlash sessiyalari (docs/12 §4.19, 2-qadam — hisob, Pico'ga QO'LLAMASDAN).

Admin sessiyani boshlaydi va etalon detallarni oddiy ish rejimida o'tkazadi: Pico har o'tishda
`olchov` yuboradi (`d1`, `d2`, `ish_ms`), shu oraliqdagi hodisalar nuqta bo'ladi. Hisob —
stansiyaning aynan algoritmi (`services/kromka_kalib.py`). Natija faqat ko'rsatiladi;
`SET` bilan Pico'ga yozish — 3-qadam."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, SessionDep
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.models import AndonEvent, KromkaKalibSession, Machine, Post
from app.models.enums import PostCode
from app.schemas.kromka_kalib import (
    KalibDetail,
    KalibEtalon,
    KalibExclude,
    KalibPoint,
    KalibSessionRow,
    KalibStart,
)
from app.services.kromka_kalib import etalon, hisobla, nuqta

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


@router.get("/{session_id}", response_model=KalibDetail, operation_id="read_kalib_session")
async def read_kalib_session(db: SessionDep, _: AdminUser, session_id: int) -> KalibDetail:
    s, name = await _get(db, session_id)
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
    jadval = []  # (hodisa, nuqta)
    for eid, at, payload in events:
        L = etalon(s.segments, at)
        p = nuqta(eid, L, payload) if L else None
        if p is not None:
            jadval.append((eid, at, payload, p))
    result = hisobla([p for eid, _a, _p, p in jadval if eid not in excluded])

    oxirgi_kal = await db.scalar(
        select(AndonEvent.payload)
        .where(AndonEvent.machine_id == s.machine_id, AndonEvent.kind == "kal", AndonEvent.is_deleted == False)  # noqa: E712
        .order_by(AndonEvent.happened_at.desc(), AndonEvent.id.desc())
        .limit(1)
    )
    kal = oxirgi_kal or {}

    def son(v: object) -> float | None:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    return KalibDetail(
        **_row(s, name).model_dump(),
        points=[
            KalibPoint(
                event_id=eid,
                at=at,
                L_ref=p.L_ref,
                S=p.S,
                L_pico=son(payload.get("L")),
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
        current={k: v for k in _KAL_KEYS if (v := son(kal.get(k))) is not None},
    )
