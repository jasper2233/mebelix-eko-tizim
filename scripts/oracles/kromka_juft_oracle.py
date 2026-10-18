"""KROMKA PAKETI (docs/12 §4.26) — 15 sm dan kichik detallar birga o'tkazilganda.

HAQIQIY `POST /bridge-agents/andon` HAQIQIY Postgres ustida: o'lchov agent yuborgandek
keladi, sozlamalar (`kromka_short_mm`, `kromka_filler_mm`) bazadan o'qiladi.

Nima tekshiriladi: 2/3/4 bo'lakli paket har qirrani yopadi; 5 bo'lak paket emas; yolg'iz
detal + 100 mm to'ldiruvchi; noaniq yig'indi yopmaydi; bitta skanning ikki qirrasi bitta
paketga tushmaydi; katta detal paketga qo'shilmaydi; kvota ikkinchi marta yopilmaydi;
dopusk `3·√n`; sozlama 0 bo'lsa eski xulq saqlanadi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/kromka_juft_oracle.py
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text

from app.api.routes.bridge_agents import push_andon_events
from app.core.db import local_session
from app.models import (
    BridgeAgent,
    Client,
    Employee,
    KromkaMeasurement,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    SystemSetting,
    WorkSession,
)
from app.models.enums import KromkaVerdict, PostCode, PostUnit
from app.schemas.bridge_agents import AndonPush

HOZIR = datetime.now(UTC).replace(microsecond=0)
KROMKALI = {"t": {"mat": "PVC"}}  # faqat UZUNLIK guruhi lentalanadi
natija: list[tuple[str, object, object]] = []
seq = [0]


def tekshir(nom: str, olingan: object, kutilgan: object) -> None:
    natija.append((nom, olingan, kutilgan))


class Muhit:
    """Bitta sinov holati uchun toza baza: stanok, smena, buyurtma va agent tokeni."""

    def __init__(self, db) -> None:
        self.db = db

    async def qur(self, short_mm: str = "150", filler_mm: str = "100") -> "Muhit":
        db = self.db
        for jadval in (
            "kromka_measurement", "part_defect", "scan", "work_session", "andon_event", "bridge_agent",
            "part_route", "part_instance", "part", "product", '"order"', "machine", "employee",
            "client", "post", "system_setting",
        ):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=1, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        self.post = post
        self.stanok = Machine(name="Kromka-1", post_id=post.id)
        self.hodim = Employee(full_name="Ali Valiyev", badge_id=uuid4().hex, assigned_post_ids=[post.id])
        mijoz = Client(full_name="Mijoz")
        db.add_all([self.stanok, self.hodim, mijoz])
        await db.flush()
        self.token = uuid4().hex
        db.add(BridgeAgent(name="kromka-pc", token_hash=hashlib.sha256(self.token.encode()).hexdigest(),
                           machine_id=self.stanok.id))
        db.add_all([
            SystemSetting(key="kromka_tolerance_mm", value="3"),
            SystemSetting(key="kromka_bind_window_s", value="60"),
            SystemSetting(key="kromka_bind_before_s", value="60"),
            SystemSetting(key="kromka_short_mm", value=short_mm),
            SystemSetting(key="kromka_filler_mm", value=filler_mm),
        ])
        self.smena = WorkSession(employee_id=self.hodim.id, machine_id=self.stanok.id, post_id=post.id)
        self.buyurtma = Order(number="B-2026-001", client_id=mijoz.id)
        db.add_all([self.smena, self.buyurtma])
        await db.flush()
        self.mahsulot = Product(order_id=self.buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(self.mahsulot)
        await db.flush()
        seq[0] = 0
        return self

    async def detal(self, nom: str, uzunlik: float, eni: float, edges: dict | None = None) -> PartInstance:
        """Detal + yagona nusxa + kromka marshruti. Qaytaradi: nusxa (skan uchun)."""
        db = self.db
        part = Part(order_id=self.buyurtma.id, product_id=self.mahsulot.id, code=f"01_{nom}", name=nom,
                    count=1, length=uzunlik, width=eni, thickness=16, edges=edges or KROMKALI)
        db.add(part)
        await db.flush()
        nusxa = PartInstance(order_id=self.buyurtma.id, part_id=part.id, instance_no=1,
                             qr_text=f"B-2026-001_01_{nom}_1")
        qadam = PartRoute(order_id=self.buyurtma.id, part_id=part.id, post_id=self.post.id, seq=1, process_code=2)
        db.add_all([nusxa, qadam])
        await db.flush()
        nusxa.route_id = qadam.id  # skan uchun eslab qo'yiladi (model maydoni emas)
        return nusxa

    async def skan(self, nusxa: PartInstance, at: datetime) -> Scan:
        row = Scan(order_id=self.buyurtma.id, part_id=nusxa.part_id, instance_id=nusxa.id,
                   route_id=nusxa.route_id, post_id=self.post.id, machine_id=self.stanok.id,
                   employee_id=self.hodim.id, session_id=self.smena.id,
                   client_event_id=uuid4().hex, created_at=at)
        self.db.add(row)
        await self.db.flush()
        return row

    async def olchov(self, L: float, at: datetime) -> KromkaMeasurement:
        """Pico o'lchovi — agent yuborgandek. Keyin OXIRGI yozilgan qator qaytariladi."""
        seq[0] += 1
        ev = {"type": "olchov", "session": "s1", "seq": seq[0], "ts": int(at.timestamp()),
              "ev": "olchov", "L": L, "kod": "OK", "v_nom": 18, "v_olch": 18.1, "ish_ms": 8000}
        await push_andon_events(self.db, AndonPush(events=[ev]), authorization=f"Bearer {self.token}")
        return (await self.db.execute(
            select(KromkaMeasurement).order_by(KromkaMeasurement.id.desc()).limit(1)
        )).scalar_one()

    async def yopilgan(self, nusxa: PartInstance) -> list[tuple[str, object, object]]:
        rows = (await self.db.execute(
            select(KromkaMeasurement)
            .where(KromkaMeasurement.instance_id == nusxa.id)
            .order_by(KromkaMeasurement.id)
        )).scalars().all()
        return [(r.verdict.value, r.side_group, r.pack_n) for r in rows]


async def main() -> None:  # noqa: PLR0915
    async with local_session() as db:
        m = Muhit(db)
        BOSH = HOZIR - timedelta(minutes=5)
        KEYIN = BOSH + timedelta(seconds=30)

        # --- 1. Ikki kichik detal birga: IKKALA qirra yopiladi
        await m.qur()
        a, b = await m.detal("A", 120, 80), await m.detal("B", 100, 80)
        await m.skan(a, BOSH)
        await m.skan(b, BOSH + timedelta(seconds=2))
        await db.commit()
        r = await m.olchov(220.4, KEYIN)
        tekshir("ikki detal: hukm mos", r.verdict, KromkaVerdict.MOS)
        tekshir("ikki detal: paketda 2 bo'lak", r.pack_n, 2)
        tekshir("ikki detal: A qirrasi yopildi", await m.yopilgan(a), [("mos", "length", 2)])
        tekshir("ikki detal: B qirrasi yopildi", await m.yopilgan(b), [("mos", "length", 2)])
        tekshir("paket qatorida delta bo'sh", r.delta_mm, None)
        tekshir("paket qatorida o'lchov — PAKETNING uzunligi", float(r.measured_mm), 220.4)

        # --- 2. Uch detal
        await m.qur()
        uch = [await m.detal(f"K{i}", uz, 80) for i, uz in enumerate((60, 70, 80))]
        for i, n in enumerate(uch):
            await m.skan(n, BOSH + timedelta(seconds=i))
        await db.commit()
        r = await m.olchov(211.0, KEYIN)
        tekshir("uch detal: paketda 3 bo'lak", (r.verdict, r.pack_n), (KromkaVerdict.MOS, 3))
        tekshir("uch detal: hamma qirra yopildi",
                [await m.yopilgan(n) for n in uch], [[("mos", "length", 3)]] * 3)

        # --- 3. To'rt detal (egasi aytgan eng katta paket)
        await m.qur()
        tort = [await m.detal(f"T{i}", uz, 80) for i, uz in enumerate((50, 60, 70, 90))]
        for i, n in enumerate(tort):
            await m.skan(n, BOSH + timedelta(seconds=i))
        await db.commit()
        r = await m.olchov(271.5, KEYIN)
        tekshir("to'rt detal: paketda 4 bo'lak", (r.verdict, r.pack_n), (KromkaVerdict.MOS, 4))
        yopildi = [await m.yopilgan(n) for n in tort]
        tekshir("to'rt detal: to'rt qirra yopildi", sum(len(x) for x in yopildi), 4)

        # --- 4. Besh bo'lak paketga sig'maydi
        await m.qur()
        besh = [await m.detal(f"B{i}", uz, 80) for i, uz in enumerate((50, 55, 60, 65, 70))]
        for i, n in enumerate(besh):
            await m.skan(n, BOSH + timedelta(seconds=i))
        await db.commit()
        r = await m.olchov(300.0, KEYIN)
        tekshir("besh bo'lak — paket emas, shubhali", r.verdict, KromkaVerdict.SHUBHALI)

        # --- 5. Yolg'iz detal + 100 mm to'ldiruvchi
        await m.qur()
        y = await m.detal("Y", 56, 80)
        await m.skan(y, BOSH)
        await db.commit()
        r = await m.olchov(155.9, KEYIN)
        tekshir("yolg'iz + to'ldiruvchi: mos", r.verdict, KromkaVerdict.MOS)
        tekshir("yolg'iz + to'ldiruvchi: paketda 2 bo'lak", r.pack_n, 2)
        tekshir("yolg'iz + to'ldiruvchi: BITTA qirra yopildi",
                await m.yopilgan(y), [("mos", "length", 2)])

        # --- 6. To'ldiruvchi o'chirilgan (0)
        await m.qur(filler_mm="0")
        y = await m.detal("Y", 56, 80)
        await m.skan(y, BOSH)
        await db.commit()
        r = await m.olchov(155.9, KEYIN)
        tekshir("to'ldiruvchi 0 bo'lsa — shubhali", r.verdict, KromkaVerdict.SHUBHALI)

        # --- 7. Noaniqlik: 60+120 = 180 va 80+100 = 180
        await m.qur()
        noaniq = [await m.detal(f"N{i}", uz, 70) for i, uz in enumerate((60, 120, 80, 100))]
        for i, n in enumerate(noaniq):
            await m.skan(n, BOSH + timedelta(seconds=i))
        await db.commit()
        r = await m.olchov(180.0, KEYIN)
        tekshir("ikki xil to'plam mos kelsa — shubhali", r.verdict, KromkaVerdict.SHUBHALI)
        yopildi = [await m.yopilgan(n) for n in noaniq]
        tekshir("noaniqlikda hech bir qirra yopilmadi",
                sum(len([x for x in q if x[0] == "mos"]) for q in yopildi), 0)

        # --- 8. Bitta skanning ikki qirrasi bitta paketga tushmaydi
        await m.qur()
        # 90 + 140 = 230; to'ldiruvchi izohi ham chiqmasin: 230−90 = 140 va 230−140 = 90,
        # ikkalasi ham 100 mm emas
        kv = await m.detal("KV", 90, 140, edges={"t": {"mat": "PVC"}, "l": {"mat": "PVC"}})
        await m.skan(kv, BOSH)
        await db.commit()
        r = await m.olchov(230.0, KEYIN)
        tekshir("bitta skanning ikki qirrasi paket bo'lmaydi", r.verdict, KromkaVerdict.SHUBHALI)

        # --- 9. Katta detal paketga qo'shilmaydi (faqat <short_mm uyalar)
        await m.qur()
        kichik, katta = await m.detal("Kichik", 100, 80), await m.detal("Katta", 400, 300)
        await m.skan(kichik, BOSH)
        await m.skan(katta, BOSH + timedelta(seconds=2))
        await db.commit()
        r = await m.olchov(500.0, KEYIN)
        tekshir("kichik + katta yig'indisi olinmaydi", r.verdict, KromkaVerdict.SHUBHALI)
        tekshir("katta detalning qirrasi yopilmadi",
                [x for x in await m.yopilgan(katta) if x[0] == "mos"], [])

        # --- 10. Yolg'iz o'tgan kichik detal — oddiy mos, paket emas
        await m.qur()
        k = await m.detal("Kichik", 120, 80)
        await m.skan(k, BOSH)
        await db.commit()
        r = await m.olchov(120.8, KEYIN)
        tekshir("yolg'iz o'tsa oddiy mos", (r.verdict, r.pack_n), (KromkaVerdict.MOS, None))
        tekshir("oddiy mos da delta yoziladi", float(r.delta_mm), 0.8)

        # --- 11. Dopusk: ikki bo'lakda 3·√2 = 4.24 mm
        for nom, L, kutilgan in (
            ("chegara ichida (+4.0 mm)", 224.0, KromkaVerdict.MOS),
            ("chegaradan tashqari (+5.0 mm)", 225.0, KromkaVerdict.SHUBHALI),
        ):
            await m.qur()
            a, b = await m.detal("A", 120, 80), await m.detal("B", 100, 80)
            await m.skan(a, BOSH)
            await m.skan(b, BOSH + timedelta(seconds=2))
            await db.commit()
            r = await m.olchov(L, KEYIN)
            tekshir(f"ikki bo'lak dopuski — {nom}", r.verdict, kutilgan)

        # --- 12. Qoida o'chirilgan (short_mm = 0) — eski xulq
        await m.qur(short_mm="0")
        a, b = await m.detal("A", 120, 80), await m.detal("B", 100, 80)
        await m.skan(a, BOSH)
        await m.skan(b, BOSH + timedelta(seconds=2))
        await db.commit()
        r = await m.olchov(220.4, KEYIN)
        tekshir("short_mm = 0 bo'lsa qoida ishlamaydi", r.verdict, KromkaVerdict.NOMOS)

        # --- 13. Kvota: paket yopgan qirra ikkinchi marta yopilmaydi
        await m.qur()
        a, b = await m.detal("A", 120, 80), await m.detal("B", 100, 80)
        await m.skan(a, BOSH)
        await m.skan(b, BOSH + timedelta(seconds=2))
        await db.commit()
        await m.olchov(220.4, KEYIN)
        r2 = await m.olchov(220.4, KEYIN + timedelta(seconds=30))
        tekshir("kvota tugagach ikkinchi paket yopilmaydi", r2.verdict, KromkaVerdict.SHUBHALI)
        tekshir("paket shubhalisida kutilgan va farq ko'rsatilmaydi",
                (r2.expected_mm, r2.delta_mm), (None, None))
        tekshir("A da faqat bitta mos qatori",
                len([x for x in await m.yopilgan(a) if x[0] == "mos"]), 1)

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
