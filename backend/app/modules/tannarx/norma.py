"""Buyurtmaning to'liq (boshqaruv) tannarxi va OEE yo'qotishi pulda (EKO 10b–10d).

To'liq tannarx = material (FIFO sarf) + kromka (norma) + mehnat (ishbay) + stanok vaqti + asbob (tig') sarfi.

- Stanok vaqti — Prisadka va Roverda skan qilingan detallarning IDEAL sikl vaqti (OEE Performance bilan bir xil
  formula, `services/performance.py`) × stanok soat narxi. Ideal vaqt — buyurtmaning o'ziga tegishli ulush;
  yo'qotilgan vaqt (to'xtash, sekin ishlash, brak) buyurtmaga emas, OEE yo'qotishiga yoziladi.
- Asbob — `xnc_summary` sanoqlari (teshik, qirra teshigi, paz, freza), Rover kontur metri, kromka metri, arra m²
  × amal normasi.
- Brak tasdiqlab bekor qilingan skan ham sanaladi: stanok va asbob baribir ishlagan (OEE bilan bir xil qoida).

Stanok va asbob BUXGALTERIYAGA yozilmaydi: ularning haqiqiy puli (asbob xaridi, elektr, ijara) allaqachon
xarajat yoki 2510 da — normani ham provodka qilsak ikki marta sanalardi. Bu boshqaruv hisobi: qaysi buyurtma
va qaysi stanok pul yo'qotayotganini ko'rsatadi.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Machine, Order, Part, PartRoute, Post, Scan
from app.models.enums import PostCode
from app.modules.ombor import service as ombor
from app.modules.tannarx import services as t
from app.modules.tannarx.models import AsbobStavka, StanokNarx
from app.services.metrics import part_volume
from app.services.performance import ideal_seconds, rover_ideal_seconds
from app.services.settings_service import get_ideal_cycle, get_ideal_cycle_rover

_0 = Decimal(0)
_Q = Decimal("0.01")
AMALLAR = {
    "teshik": "Teshik (sverlo)",
    "qirra_teshik": "Qirra teshigi",
    "paz": "Paz",
    "freza": "Freza konturi",
    "rover_metr": "Rover kontur metri",
    "kromka_metr": "Kromka metri (yelim, pichoq)",
    "arra_m2": "Arra m² (disk)",
}


def _amaldagi(tarix: list[tuple[date, Decimal]], d: date) -> Decimal | None:
    q = [n for a, n in tarix if a <= d]
    return q[-1] if q else None


async def stanok_narxlari(db: AsyncSession) -> dict[int, list[tuple[date, Decimal]]]:
    out: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
    for s in (await db.execute(select(StanokNarx).order_by(StanokNarx.amal_boshi))).scalars():
        out[s.machine_id].append((s.amal_boshi, s.soat_narxi))
    return out


async def asbob_stavkalari(db: AsyncSession) -> dict[str, list[tuple[date, Decimal]]]:
    out: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for s in (await db.execute(select(AsbobStavka).order_by(AsbobStavka.amal_boshi))).scalars():
        out[s.amal].append((s.amal_boshi, s.narx))
    return out


def _takror(takror: bool, amal_boshi: date, nom: str) -> None:
    # Norma buxgalteriyaga yozilmaydi — o'tgan sanaga ham yoziladi (vedomost davri cheklovi yo'q)
    if takror:
        raise t.TannarxXato([f"{nom}: {amal_boshi} dan narx allaqachon yozilgan"])


async def stanok_narx_qosh(
    db: AsyncSession, machine_id: int, soat_narxi: Decimal, amal_boshi: date, user_id: int | None
) -> StanokNarx:
    m = await db.get(Machine, machine_id)
    if m is None:
        raise t.TannarxXato(["Stanok topilmadi"])
    takror = await db.scalar(
        select(StanokNarx.id).where(StanokNarx.machine_id == machine_id, StanokNarx.amal_boshi == amal_boshi)
    )
    _takror(takror is not None, amal_boshi, m.name)
    s = StanokNarx(machine_id=machine_id, soat_narxi=soat_narxi, amal_boshi=amal_boshi, yozgan_id=user_id)
    db.add(s)
    await db.flush()
    return s


async def asbob_stavka_qosh(
    db: AsyncSession, amal: str, narx: Decimal, amal_boshi: date, user_id: int | None
) -> AsbobStavka:
    if amal not in AMALLAR:
        raise t.TannarxXato(["Noma'lum amal"])
    takror = await db.scalar(
        select(AsbobStavka.id).where(AsbobStavka.amal == amal, AsbobStavka.amal_boshi == amal_boshi)
    )
    _takror(takror is not None, amal_boshi, AMALLAR[amal])
    s = AsbobStavka(amal=amal, narx=narx, amal_boshi=amal_boshi, yozgan_id=user_id)
    db.add(s)
    await db.flush()
    return s


# ───────────────────────── buyurtma tannarxi ─────────────────────────
@dataclass
class Tannarx:
    order_id: int
    material: Decimal = _0
    kromka: Decimal = _0
    kromka_metr: Decimal = _0
    mehnat: Decimal = _0
    #: Mehnatning tasdiqlangan vedomostlarga kirgan qismi (buxgalteriyada shu)
    mehnat_tasdiqlangan: Decimal = _0
    stanok: Decimal = _0
    stanok_soat: Decimal = _0
    asbob: Decimal = _0
    #: Narxi yozilmagan stanok yoki amal bor — summa to'liq emas
    kamchilik: set[str] = field(default_factory=set)

    @property
    def jami(self) -> Decimal:
        return self.material + self.kromka + self.mehnat + self.stanok + self.asbob


async def buyurtma_tannarxi(db: AsyncSession, order_ids: list[int]) -> dict[int, Tannarx]:
    out = {oid: Tannarx(oid) for oid in order_ids}
    if not order_ids:
        return out
    for oid, s in (await ombor.buyurtma_tannarxi(db, order_ids)).items():
        out[oid].material = s
    for oid, (m, s) in (await ombor.kromka_normasi(db, order_ids)).items():
        out[oid].kromka_metr, out[oid].kromka = m, s
    # Mehnat: hamma skan bugungi stavka tarixi bilan (tasdiqlanmagani — taxmin), tasdiqlangani alohida
    for h in await t.skan_haqlari(db, date(2000, 1, 1), t.bugun(), order_ids):
        out[h.order_id].mehnat += h.summa
        if h.stavkasiz:
            out[h.order_id].kamchilik.add("ish haqi stavkasi")
    for oid, s in (await t.buyurtma_mehnati(db, order_ids)).items():
        out[oid].mehnat_tasdiqlangan = s

    ideal, rover = await get_ideal_cycle(db), await get_ideal_cycle_rover(db)
    stanok, asbob = await stanok_narxlari(db), await asbob_stavkalari(db)
    kun = func.date(func.timezone("Asia/Tashkent", Scan.created_at))
    rows = (
        await db.execute(
            select(
                Scan.order_id,
                Scan.machine_id,
                Post.code,
                kun,
                Part.length,
                Part.width,
                Part.count,
                Part.edges,
                Part.xnc_summary,
                Scan.part_id,
                func.count(),
            )
            .join(Post, Post.id == Scan.post_id)
            .join(Part, Part.id == Scan.part_id)
            .where(
                Scan.order_id.in_(order_ids),
                or_(Scan.is_cancelled == False, Scan.defect_id.is_not(None)),  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
                Post.code.in_((PostCode.PRISADKA, PostCode.ROVER, PostCode.KROMKA, PostCode.ARRA)),
            )
            .group_by(
                Scan.order_id,
                Scan.machine_id,
                Post.code,
                kun,
                Part.length,
                Part.width,
                Part.count,
                Part.edges,
                Part.xnc_summary,
                Scan.part_id,
            )
        )
    ).all()
    talab = await _talab(db, {r[9] for r in rows})

    def asbob_qosh(tn: Tannarx, amal: str, miqdor: Decimal, d: date) -> None:
        if not miqdor:
            return
        n = _amaldagi(asbob.get(amal, []), d)
        if n is None:
            tn.kamchilik.add(f"asbob: {AMALLAR[amal]}")
        else:
            tn.asbob += miqdor * n

    for oid, mid, code, d, length, width, count, edges, xnc, part_id, n in rows:
        tn = out[oid]
        x = xnc or {}
        sanoq = {k: int(x.get(k) or 0) for k in ("bores", "edge_bores", "grooves", "mills")}
        if code in (PostCode.PRISADKA, PostCode.ROVER):
            sek = (
                ideal_seconds(ideal, sanoq["bores"], sanoq["edge_bores"], sanoq["grooves"], sanoq["mills"])
                if code == PostCode.PRISADKA
                else rover_ideal_seconds(rover, length, width)
            ) * n
            soat = Decimal(str(sek)) / 3600
            tn.stanok_soat += soat
            narx = _amaldagi(stanok.get(mid, []), d) if mid else None
            if narx is None:
                tn.kamchilik.add("stanok soat narxi")
            else:
                tn.stanok += soat * narx
        if code == PostCode.PRISADKA:
            for amal, k in (
                ("teshik", "bores"),
                ("qirra_teshik", "edge_bores"),
                ("paz", "grooves"),
                ("freza", "mills"),
            ):
                asbob_qosh(tn, amal, Decimal(sanoq[k] * n), d)
        elif code == PostCode.ROVER:
            asbob_qosh(tn, "rover_metr", Decimal(str(2 * ((length or 0) + (width or 0)) / 1000)) * n, d)
        else:
            hajm = part_volume(code, length=length, width=width, count=count, edges=edges or {})
            ulush = Decimal(str(hajm)) * n / (talab.get((part_id, code)) or 1)
            asbob_qosh(tn, "kromka_metr" if code == PostCode.KROMKA else "arra_m2", ulush, d)
    for tn in out.values():
        for k in ("stanok", "asbob", "kromka", "stanok_soat"):
            setattr(tn, k, getattr(tn, k).quantize(_Q, ROUND_HALF_UP))
    return out


async def _talab(db: AsyncSession, part_ids: set[int]) -> dict[tuple[int, str], int]:
    if not part_ids:
        return {}
    q = (
        select(PartRoute.part_id, Post.code, func.sum(PartRoute.total_required))
        .join(Post, Post.id == PartRoute.post_id)
        .where(PartRoute.part_id.in_(part_ids))
        .group_by(PartRoute.part_id, Post.code)
    )
    return {(p, c): int(n) for p, c, n in (await db.execute(q)).all()}


async def buyurtmalar(db: AsyncSession, dan: date, gacha: date) -> list[Order]:
    """Davrda yetkazilgan buyurtmalar."""
    return list(
        (
            await db.execute(
                select(Order)
                .where(
                    Order.delivered_at >= datetime.combine(dan, time(), TASHKENT_TZ),
                    Order.delivered_at < datetime.combine(gacha + timedelta(days=1), time(), TASHKENT_TZ),
                )
                .order_by(Order.delivered_at)
            )
        ).scalars()
    )


async def jarayondagilar(db: AsyncSession) -> list[Order]:
    """Hali yetkazilmagan, lekin sexda ishi boshlangan (skani bor) buyurtmalar — tannarx yig'ilib bormoqda."""
    skanli = select(Scan.order_id).where(Scan.is_deleted == False).distinct()  # noqa: E712
    q = select(Order).where(Order.delivered_at.is_(None), Order.id.in_(skanli)).order_by(Order.id)
    return list((await db.execute(q)).scalars())


# ───────────────────────── OEE yo'qotishi pulda ─────────────────────────
@dataclass
class Yoqotish:
    machine_id: int
    nom: str
    soat_narxi: Decimal | None
    planned_s: int
    to_xtash_s: int
    sekin_s: int
    brak_s: int
    oee_pct: float | None
    sabablar: list[tuple[str, int]]
    #: Stanokdan umuman ma'lumot kelmagan kunlar (o'rnatilmagan, Pico o'chiq) — hisobga kirmadi
    malumotsiz_kun: int = 0

    def pul(self, s: int) -> Decimal | None:
        if self.soat_narxi is None:
            return None
        return (Decimal(s) / 3600 * self.soat_narxi).quantize(_Q, ROUND_HALF_UP)


async def oee_yoqotish(db: AsyncSession, dan: date, gacha: date) -> list[Yoqotish]:
    """Stanok bo'yicha yo'qotilgan vaqt uch qismda: to'xtash (Availability), sekin ishlash (Performance),
    brak (Quality) — va ularning puli soat narxi bilan (davr oxiridagi narx).

    Faqat stanokdan ma'lumot kelgan kunlar: MES hisobotida ma'lumotsiz vaqt «o'chiq» (to'xtash) sanaladi, lekin
    stanok hali o'rnatilmagan yoki Pico ulanmagan kunni pulli yo'qotish deyish — soxta raqam (bir oyda yuzlab soat)."""
    from app.api.routes.reports import build_machine_time_report

    rep = await build_machine_time_report(db, dan, gacha)
    narx = await stanok_narxlari(db)
    out = []
    kunlar: dict[int, list[tuple[int, int]]] = defaultdict(list)  # stanok -> [(reja, ishladi)] ma'lumotli kunlar
    bosh: dict[int, int] = defaultdict(int)
    for d in rep.days:
        if sum(d.seconds.values()) > 0:
            kunlar[d.machine_id].append((d.planned_s, d.run_s))
        elif d.planned_s > 0:
            bosh[d.machine_id] += 1
    for r in rep.rows:
        planned = sum(p for p, _ in kunlar[r.machine_id])
        run = sum(x for _, x in kunlar[r.machine_id])
        if planned <= 0:
            continue
        sekin = max(run - r.ideal_s, 0) if r.ideal_s > 0 else 0
        brak = round(r.ideal_s * r.defects / r.parts) if r.parts > 0 and r.ideal_s > 0 else 0
        oee = round(r.ideal_s * max(r.parts - r.defects, 0) * 100 / (planned * r.parts), 1) if r.parts else None
        out.append(
            Yoqotish(
                machine_id=r.machine_id,
                nom=r.machine_name,
                soat_narxi=_amaldagi(narx.get(r.machine_id, []), gacha),
                planned_s=planned,
                to_xtash_s=planned - run,
                sekin_s=sekin,
                brak_s=brak,
                oee_pct=oee if r.ideal_s > 0 else None,
                malumotsiz_kun=bosh[r.machine_id],
                sabablar=[(s.name, s.seconds) for s in r.reasons if not s.is_planned][:5],
            )
        )
    return out
