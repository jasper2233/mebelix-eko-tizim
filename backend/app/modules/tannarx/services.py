"""Ishbay ish haqi (EKO 10a): skanlar × hajm × stavka; vedomost; buyurtmaning mehnat tannarxi.

Qoidalar:
- Haq faqat bekor qilinmagan skanga (brak tasdiqlansa skan bekor bo'ladi — ish haqiga kirmaydi).
- Bitta skan hajmi = detalning shu postdagi to'liq hajmi ÷ shu post marshrut qatorlarining `total_required`
  yig'indisi (TABLO bilan bir xil: `services/metrics.VolumeShare`).
- Stavka — skan sanasida amalda bo'lgani; amalga oid (`process_code`) stavka post stavkasidan ustun.
- Stavkasi yo'q postdagi ish vedomostga jim nol bo'lib kirmaydi — vedomost yaratilmaydi, xato aytiladi.
- Tasdiqlashda skanlar qayta hisoblanadi: o'zgargan bo'lsa (skan bekor qilingan, kech skan) — rad, qaytadan.
- Buyurtma mehnat tannarxi — faqat TASDIQLANGAN vedomost davridagi skanlardan (buxgalteriya 2010 ga shu summa
  hisoblangan); tasdiqlanmagan ish tannarxga keyin, vedomost tasdiqlanganda kiradi.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Employee, Part, PartRoute, Post, Scan
from app.modules.tannarx.models import IshHaqiQator, IshHaqiVedomost, IshStavka
from app.services.metrics import part_volume

_0 = Decimal(0)
_Q = Decimal("0.01")


class TannarxXato(Exception):
    def __init__(self, xatolar: list[str]) -> None:
        super().__init__(" · ".join(xatolar))
        self.xatolar = xatolar


def bugun() -> date:
    return datetime.now(TASHKENT_TZ).date()


def _vaqt(d: date) -> datetime:
    return datetime.combine(d, time(), TASHKENT_TZ)


# ───────────────────────── stavkalar ─────────────────────────
Kalit = tuple[int, int | None]


async def stavkalar(db: AsyncSession) -> dict[Kalit, list[tuple[date, Decimal]]]:
    out: dict[Kalit, list[tuple[date, Decimal]]] = defaultdict(list)
    for s in (await db.execute(select(IshStavka).order_by(IshStavka.amal_boshi))).scalars():
        out[(s.post_id, s.process_code)].append((s.amal_boshi, s.narx))
    return out


def stavka(
    jadval: dict[Kalit, list[tuple[date, Decimal]]], post_id: int, process_code: int | None, d: date
) -> Decimal | None:
    for kalit in ((post_id, process_code), (post_id, None)):
        tarix = [n for a, n in jadval.get(kalit, []) if a <= d]
        if tarix:
            return tarix[-1]
    return None


async def stavka_qosh(
    db: AsyncSession, post_id: int, process_code: int | None, narx: Decimal, amal_boshi: date, user_id: int | None
) -> IshStavka:
    xato = []
    if await db.get(Post, post_id) is None:
        xato.append("Post topilmadi")
    if narx < 0:
        xato.append("Narx manfiy bo'lmaydi")
    band = await db.scalar(
        select(IshHaqiVedomost.no).where(IshHaqiVedomost.holat == "tasdiqlangan", IshHaqiVedomost.gacha >= amal_boshi)
    )
    if band:
        xato.append(f"{amal_boshi} dan keyingi davr {band} da tasdiqlangan — stavka keyingi sanadan o'zgaradi")
    if await db.scalar(
        select(IshStavka.id).where(
            IshStavka.post_id == post_id,
            IshStavka.process_code.is_(None) if process_code is None else IshStavka.process_code == process_code,
            IshStavka.amal_boshi == amal_boshi,
        )
    ):
        xato.append(f"{amal_boshi} dan bu stavka allaqachon yozilgan")
    if xato:
        raise TannarxXato(xato)
    s = IshStavka(post_id=post_id, process_code=process_code, narx=narx, amal_boshi=amal_boshi, yozgan_id=user_id)
    db.add(s)
    await db.flush()
    return s


# ───────────────────────── skan haqlari ─────────────────────────
@dataclass
class SkanHaq:
    employee_id: int
    post_id: int
    order_id: int
    hajm: Decimal
    skanlar: int
    summa: Decimal
    #: Stavka topilmagan skanlar soni (summa 0)
    stavkasiz: int


async def skan_haqlari(db: AsyncSession, dan: date, gacha: date, order_ids: list[int] | None = None) -> list[SkanHaq]:
    """[dan, gacha] kunlar (mahalliy) bo'yicha hodim × post × buyurtma kesimida."""
    kun = func.date(func.timezone("Asia/Tashkent", Scan.created_at)).label("kun")
    q = (
        select(Scan.employee_id, Scan.post_id, Scan.order_id, Scan.part_id, PartRoute.process_code, kun, func.count())
        .join(PartRoute, PartRoute.id == Scan.route_id)
        .where(
            Scan.is_cancelled == False,  # noqa: E712
            Scan.is_deleted == False,  # noqa: E712
            Scan.created_at >= _vaqt(dan),
            Scan.created_at < _vaqt(gacha + timedelta(days=1)),
        )
        .group_by(Scan.employee_id, Scan.post_id, Scan.order_id, Scan.part_id, PartRoute.process_code, kun)
    )
    if order_ids is not None:
        q = q.where(Scan.order_id.in_(order_ids))
    rows = (await db.execute(q)).all()
    if not rows:
        return []
    part_ids = {r[3] for r in rows}
    parts = {p.id: p for p in (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars()}
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    talab_q = (
        select(PartRoute.part_id, PartRoute.post_id, func.sum(PartRoute.total_required))
        .where(PartRoute.part_id.in_(part_ids))
        .group_by(PartRoute.part_id, PartRoute.post_id)
    )
    talab = {(pid, post): int(n) for pid, post, n in (await db.execute(talab_q)).all()}
    jadval = await stavkalar(db)
    agg: dict[tuple[int, int, int], list[Any]] = defaultdict(lambda: [_0, 0, _0, 0])
    for emp, post_id, order_id, part_id, pcode, d, n in rows:
        p, post = parts.get(part_id), posts.get(post_id)
        if p is None or post is None:
            continue
        hajm_detal = part_volume(post.code, length=p.length, width=p.width, count=p.count, edges=p.edges or {})
        req = talab.get((part_id, post_id)) or 1
        hajm = Decimal(str(hajm_detal)) * n / req
        narx = stavka(jadval, post_id, pcode, d)
        a = agg[(emp, post_id, order_id)]
        a[0] += hajm
        a[1] += n
        if narx is None:
            a[3] += n
        else:
            a[2] += hajm * narx
    return [
        SkanHaq(e, p, o, v[0].quantize(Decimal("0.001"), ROUND_HALF_UP), v[1], v[2].quantize(_Q, ROUND_HALF_UP), v[3])
        for (e, p, o), v in agg.items()
    ]


# ───────────────────────── vedomost ─────────────────────────
async def _next_no(db: AsyncSession) -> str:
    p = f"ISH-{bugun().year}-"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(p))))
    last = await db.scalar(
        select(func.max(cast(func.split_part(IshHaqiVedomost.no, "-", 3), Integer))).where(
            IshHaqiVedomost.no.like(f"{p}%")
        )
    )
    return f"{p}{(last or 0) + 1:04d}"


def _jamla(haqlar: list[SkanHaq]) -> dict[tuple[int, int], list[Any]]:
    out: dict[tuple[int, int], list[Any]] = defaultdict(lambda: [_0, 0, _0])
    for h in haqlar:
        a = out[(h.employee_id, h.post_id)]
        a[0] += h.hajm
        a[1] += h.skanlar
        a[2] += h.summa
    return out


async def vedomost_yarat(db: AsyncSession, dan: date, gacha: date, user_id: int | None) -> IshHaqiVedomost:
    xato = []
    if dan > gacha:
        xato.append("Davr noto'g'ri")
    if gacha >= bugun():
        xato.append("Davr kechagi kun bilan tugasin — bugungi skanlar hali davom etadi")
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("ish_haqi_vedomost"))))
    ust = await db.scalar(
        select(IshHaqiVedomost.no).where(
            IshHaqiVedomost.holat != "bekor", IshHaqiVedomost.dan <= gacha, IshHaqiVedomost.gacha >= dan
        )
    )
    if ust:
        xato.append(f"Davr {ust} bilan ustma-ust tushadi")
    haqlar = await skan_haqlari(db, dan, gacha)
    stavkasiz: dict[int, int] = defaultdict(int)
    for h in haqlar:
        if h.stavkasiz:
            stavkasiz[h.post_id] += h.stavkasiz
    if stavkasiz:
        nom = {p.id: p.name for p in (await db.execute(select(Post).where(Post.id.in_(stavkasiz)))).scalars()}
        xato.append("Stavka yo'q: " + ", ".join(f"{nom.get(k, k)} ({n} skan)" for k, n in stavkasiz.items()))
    if not haqlar:
        xato.append("Bu davrda skan yo'q")
    if xato:
        raise TannarxXato(xato)
    j = _jamla(haqlar)
    v = IshHaqiVedomost(
        no=await _next_no(db),
        dan=dan,
        gacha=gacha,
        holat="qoralama",
        jami=sum((a[2] for a in j.values()), _0),
        skanlar=sum(a[1] for a in j.values()),
        yaratgan_id=user_id,
    )
    db.add(v)
    await db.flush()
    for (emp, post_id), a in j.items():
        db.add(IshHaqiQator(vedomost_id=v.id, employee_id=emp, post_id=post_id, hajm=a[0], skanlar=a[1], summa=a[2]))
    await db.flush()
    return v


async def vedomost_tasdiq(db: AsyncSession, vedomost_id: int, user_id: int | None) -> IshHaqiVedomost:
    v = await db.get(IshHaqiVedomost, vedomost_id, with_for_update=True)
    if v is None:
        raise TannarxXato(["Vedomost topilmadi"])
    xato = []
    if v.holat != "qoralama":
        xato.append(f"{v.no} — {v.holat}")
    if user_id is not None and user_id == v.yaratgan_id:
        xato.append("Ikki kalit qoidasi: vedomostni yozgan xodim o'zi tasdiqlay olmaydi")
    if not xato:
        yangi = _jamla(await skan_haqlari(db, v.dan, v.gacha))
        eski = {
            (q.employee_id, q.post_id): q.summa
            for q in (await db.execute(select(IshHaqiQator).where(IshHaqiQator.vedomost_id == v.id))).scalars()
        }
        if {k: a[2] for k, a in yangi.items()} != eski:
            xato.append("Vedomost yozilgandan keyin skanlar o'zgargan — uni bekor qilib, qaytadan hisoblang")
    if xato:
        raise TannarxXato(xato)
    v.holat, v.tasdiqlagan_id, v.tasdiqlangan_at = "tasdiqlangan", user_id, datetime.now(UTC)
    await db.flush()
    return v


async def vedomost_bekor(db: AsyncSession, vedomost_id: int) -> IshHaqiVedomost:
    v = await db.get(IshHaqiVedomost, vedomost_id, with_for_update=True)
    if v is None:
        raise TannarxXato(["Vedomost topilmadi"])
    if v.holat != "qoralama":
        raise TannarxXato([f"{v.no} — faqat qoralama bekor qilinadi (tasdiqlangani buxgalteriyaga tushgan)"])
    v.holat = "bekor"
    await db.flush()
    return v


async def tasdiqlanganlar(db: AsyncSession) -> list[IshHaqiVedomost]:
    return list(
        (
            await db.execute(
                select(IshHaqiVedomost).where(IshHaqiVedomost.holat == "tasdiqlangan").order_by(IshHaqiVedomost.dan)
            )
        ).scalars()
    )


async def buyurtma_mehnati(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmalarning mehnat tannarxi — tasdiqlangan vedomost davrlaridagi skanlardan."""
    if not order_ids:
        return {}
    out: dict[int, Decimal] = defaultdict(lambda: _0)
    for v in await tasdiqlanganlar(db):
        for h in await skan_haqlari(db, v.dan, v.gacha, order_ids):
            out[h.order_id] += h.summa
    return dict(out)


async def hodim_nomlari(db: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {e.id: e.full_name for e in (await db.execute(select(Employee).where(Employee.id.in_(ids)))).scalars()}
