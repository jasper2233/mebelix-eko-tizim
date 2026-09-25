"""`scripts/kromka_dedup.sql` — v1.22 tasdiqsiz yig'ilgan takrorlarni tozalash.

Prodda bo'lgan holat qayta yasaladi: Pico v1.22 (`xb`/`xq` bilan), agent 1.7.1
(tasdiq yubormaydi, kalitni o'zi beradi) — ya'ni bitta o'lchov har 5 soniyada
qayta kelib, HAR safar yangi yozuv bo'lgan. Shundan keyin SQL yurgiziladi va
tekshiriladi: takrorlar yo'qoldimi, HAQIQIY yozuvlar joyidami, hisobot
(Performance, o'lchov sanog'i) to'g'rilandimi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/kromka_dedup_oracle.py
"""

import asyncio
import os
import subprocess
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select, text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ, settings
from app.core.db import local_session
from app.models import (
    AndonEvent,
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
    User,
    WorkSession,
)
from app.models.enums import KromkaVerdict, PostCode, PostUnit, UserRole

SQL = os.path.join(os.path.dirname(__file__), "..", "kromka_dedup.sql")
KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0, s=0: KECHA + timedelta(hours=h, minutes=m, seconds=s)  # noqa: E731
JADVAL = ('{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00","breaks":[]}],'
          '"days_off":[],"holidays":[]}')
XB = "a1b2c3d4"
#: Pico har o'lchovni tasdiq kelmaguncha shuncha marta qayta yuborgan
NUSXA = 12


def sqlni_yurgiz(faqat_hisobot: bool = False) -> str:
    """Skriptni AYNAN psql orqali — `\\if`, `\\set` va tranzaksiya haqiqiy bo'lsin."""
    buyruq = ["psql", "-X", "-v", "ON_ERROR_STOP=1",
              "-h", settings.POSTGRES_SERVER, "-p", str(settings.POSTGRES_PORT),
              "-U", settings.POSTGRES_USER, "-d", settings.POSTGRES_DB]
    if faqat_hisobot:
        buyruq += ["-v", "faqat_hisobot=1"]
    muhit = {**os.environ}
    if settings.POSTGRES_PASSWORD:
        muhit["PGPASSWORD"] = settings.POSTGRES_PASSWORD
    with open(os.path.abspath(SQL), encoding="utf-8") as f:
        p = subprocess.run(buyruq, stdin=f, capture_output=True, text=True, env=muhit, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"psql xato ({p.returncode}):\n{p.stderr[-2000:]}")
    return p.stdout


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in (
            "kromka_measurement", "part_defect", "scan", "work_session", "downtime", "downtime_reason",
            "andon_event", "part_route", "part_instance", "part", "product", '"order"',
            "machine", "employee", '"user"', "client", "post", "system_setting",
        ):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()

        db.add_all([
            SystemSetting(key="work_schedule", value=JADVAL),
            SystemSetting(key="stop_prompt_idle_minutes", value="5"),
            SystemSetting(key="kromka_idle_minutes", value="240"),
        ])
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        stanok = Machine(name="Kromka-1", post_id=post.id)
        hodim = Employee(full_name="Ikromov Samariddin", badge_id=uuid4().hex, assigned_post_ids=[post.id])
        mijoz = Client(full_name="Mijoz")
        admin = User(username="admin", phone="+998900000002", hashed_password="x",
                     name="Admin", role=UserRole.ADMIN)
        db.add_all([stanok, hodim, mijoz, admin])
        await db.flush()
        smena = WorkSession(employee_id=hodim.id, machine_id=stanok.id, post_id=post.id)
        buyurtma = Order(number="B-2026-020", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        detal = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon",
                     count=60, length=900, width=430, thickness=16)
        db.add(detal)
        await db.flush()
        qadam = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=post.id, seq=1,
                          process_code=2, per_instance=1, total_required=60)
        nusxa = PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=1,
                             qr_text="B-2026-020_01_001_1")
        db.add_all([qadam, nusxa])
        await db.flush()
        skan = Scan(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id, route_id=qadam.id,
                    post_id=post.id, machine_id=stanok.id, employee_id=hodim.id, session_id=smena.id,
                    client_event_id=uuid4().hex, created_at=T(8))
        db.add(skan)
        await db.flush()

        seq = 0

        def hodisa(kind, at, payload):
            nonlocal seq
            seq += 1                       # agent 1.7.1: kalit O'ZINIKI, har takror yangi
            db.add(AndonEvent(machine_id=stanok.id, session="ag1", seq=seq, kind=kind,
                              happened_at=at, payload=payload))

        # RUN yoqiq: 08:00-17:00
        hodisa("uskuna", T(8), {"ev": "uskuna", "holat": 1, "xb": XB, "xq": 1})
        hodisa("uskuna", T(17), {"ev": "uskuna", "holat": 0, "xb": XB, "xq": 60})
        # 30 ta HAQIQIY o'lchov — har biri NUSXA marta qayta kelgan.
        # MUHIM: agent 1.7.1 har takrorda vaqtni `hozir − eski_ms` deb QAYTA hisoblagan,
        # ya'ni bitta hodisaning nusxalari bir necha xil soniyaga tarqalgan (prodda
        # 2026-09-24: 185 hodisa, 881 xil vaqt tamg'asi). Shu siljish shu yerda ham bor —
        # `measured_at` ning o'zi bo'yicha tozalash YETMAYDI.
        for i in range(30):
            at = T(8) + timedelta(minutes=i * 2)
            for j in range(NUSXA):
                siljigan = at + timedelta(seconds=j % 4)   # 0,1,2,3 s — o'sha hodisa
                hodisa("olchov", siljigan, {"ev": "olchov", "L": 900.0, "kod": "OK", "v_nom": 18,
                                            "xb": XB, "xq": 2 + i})
                db.add(KromkaMeasurement(machine_id=stanok.id, measured_at=siljigan, code="OK",
                                         verdict=KromkaVerdict.MOS, measured_mm=900.0,
                                         expected_mm=900.0, delta_mm=0.0, side_group="length",
                                         scan_id=skan.id, instance_id=nusxa.id, order_id=buyurtma.id))
        # BIR SONIYAGA ikki HAR XIL hodisa tushgan (prodda 3b bo'limida 5911 satr shunday
        # edi): ikkalasi ham qolishi, nusxalari o'chishi kerak. Ajratuvchi — o'lcham.
        for xq, mm in ((90, 500.0), (91, 600.0)):
            for _ in range(5):
                hodisa("olchov", T(8, 30, 30), {"ev": "olchov", "L": mm, "kod": "OK",
                                                "v_nom": 18, "xb": XB, "xq": xq})
                db.add(KromkaMeasurement(machine_id=stanok.id, measured_at=T(8, 30, 30), code="OK",
                                         verdict=KromkaVerdict.MOS, measured_mm=mm,
                                         expected_mm=mm, delta_mm=0.0, side_group="length"))
        # ESKI proshivkadan (xb/xq YO'Q) kelgan yozuv — unga TEGILMASLIGI kerak
        hodisa("olchov", T(16), {"ev": "olchov", "L": 640.0, "kod": "OK", "v_nom": 10})
        db.add(KromkaMeasurement(machine_id=stanok.id, measured_at=T(16), code="OK",
                                 verdict=KromkaVerdict.SKANERSIZ, measured_mm=640.0))
        # BIR XIL soniyadagi ikki o'lchov, lekin xb/xq HAR XIL — takror emas, qolsin
        hodisa("olchov", T(15), {"ev": "olchov", "L": 700.0, "kod": "OK", "v_nom": 18,
                                 "xb": XB, "xq": 50})
        hodisa("olchov", T(15), {"ev": "olchov", "L": 710.0, "kod": "OK", "v_nom": 18,
                                 "xb": XB, "xq": 51})
        await db.commit()

        kutilgan_hodisa = 2 + 30 * NUSXA + 10 + 3
        jami = await db.scalar(select(func.count()).select_from(AndonEvent))
        natija.append(("fixture: takrorlar bilan hodisa", jami, kutilgan_hodisa))

        oldin = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r0 = oldin.rows[0]
        # Takrorlar tufayli 30 ta o'tish 30 × NUSXA bo'lib sanalgan (+3 ta yolg'iz yozuv),
        # ideal vaqt ham shuncha shishgan: 2177.5 s ÷ 10680 s = 20.4%
        natija.append(("tozalashdan OLDIN detal soni shishgan", r0.parts, 30 * NUSXA + 13))
        natija.append(("tozalashdan OLDIN Performance shishgan", r0.performance_pct, 20.8))

    # ---------- FAQAT HISOBOT: hech narsa o'zgarmasligi kerak ----------
    chiqish = sqlni_yurgiz(faqat_hisobot=True)
    natija.append(("faqat hisobot rejimi ishladi", "FAQAT HISOBOT" in chiqish, True))
    async with local_session() as db:
        tirik = await db.scalar(select(func.count()).select_from(AndonEvent)
                                .where(AndonEvent.is_deleted == False))  # noqa: E712
        natija.append(("faqat hisobot hech narsa o'chirmadi", tirik, kutilgan_hodisa))

    # ---------- TOZALASH ----------
    chiqish = sqlni_yurgiz()
    natija.append(("tozalash rejimida hisobot ham chiqdi", "TAKROR HODISALAR" in chiqish, True))

    async with local_session() as db:
        qolgan = (await db.execute(
            select(AndonEvent.kind, func.count())
            .where(AndonEvent.is_deleted == False)  # noqa: E712
            .group_by(AndonEvent.kind).order_by(AndonEvent.kind))).tuples().all()
        natija.append(("takrorlar o'chdi, haqiqiylari qoldi",
                       dict(qolgan), {"olchov": 35, "uskuna": 2}))
        ochirilgan = await db.scalar(select(func.count()).select_from(AndonEvent)
                                     .where(AndonEvent.is_deleted == True))  # noqa: E712
        natija.append(("o'chirilgani = ortiqcha nusxalar", ochirilgan, 30 * (NUSXA - 1) + 8))
        yumshoq = await db.scalar(select(func.count()).select_from(AndonEvent)
                                  .where(AndonEvent.is_deleted == True,  # noqa: E712
                                         AndonEvent.deleted_at.is_not(None)))
        natija.append(("yumshoq o'chirish — vaqt yozilgan", yumshoq, ochirilgan))

        eski = await db.scalar(select(func.count()).select_from(AndonEvent).where(
            AndonEvent.is_deleted == False,  # noqa: E712
            AndonEvent.payload["L"].astext == "640.0"))
        natija.append(("xb/xq siz eski yozuvga tegilmadi", eski, 1))
        bir_soniya = await db.scalar(select(func.count()).select_from(AndonEvent).where(
            AndonEvent.is_deleted == False,  # noqa: E712
            AndonEvent.happened_at == T(15)))
        natija.append(("bir soniyadagi HAR XIL xq qoldi", bir_soniya, 2))
        tuqnash = await db.scalar(select(func.count()).select_from(KromkaMeasurement).where(
            KromkaMeasurement.is_deleted == False,  # noqa: E712
            KromkaMeasurement.measured_at == T(8, 30, 30)))
        natija.append(("bir soniyada ikki hodisa — ikkalasi ham qoldi", tuqnash, 2))

        olchov_qoldi = await db.scalar(select(func.count()).select_from(KromkaMeasurement)
                                       .where(KromkaMeasurement.is_deleted == False))  # noqa: E712
        # Har HODISAGA bitta: 30 + tegilmaydigan eski yozuv. Vaqt bo'yicha tozalash
        # bu yerda 30 × 4 = 120 satr qoldirardi — kalit `xb`/`xq` bo'lgani shu uchun muhim.
        natija.append(("o'lchov tarixi: har hodisaga BITTA yozuv", olchov_qoldi, 33))

        keyin = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r1 = keyin.rows[0]
        natija.append(("tozalashdan KEYIN detal soni haqiqiy", r1.parts, 35))
        # 197.5 s ÷ 10680 s — endi Pico rostdan qilgan ish
        natija.append(("tozalashdan KEYIN Performance haqiqiy", r1.performance_pct, 1.9))
        # Ishlagan vaqt deyarli o'zgarmaydi: bo'sh yurish chegarasi o'lchov BELGILARIGA
        # tayanadi, takror nusxalar esa o'sha belgilarni bir necha soniyaga cho'zib
        # turgan edi. Farq siljish oynasidan katta bo'lsa — tozalash ortiqcha yozuvni
        # emas, haqiqiy o'lchovni o'chirgan bo'lardi.
        natija.append(("ishlagan vaqt siljish oynasidan ortiq o'zgarmadi",
                       abs(r1.run_s - r0.run_s) <= 4, True))
        natija.append(("Performance tushdi (haqiqiy)", r1.performance_pct < r0.performance_pct, True))

        # Ikkinchi marta yurgizish xavfsiz (idempotent)
        oldingi_ochirilgan = ochirilgan

    sqlni_yurgiz()
    async with local_session() as db:
        yana = await db.scalar(select(func.count()).select_from(AndonEvent)
                               .where(AndonEvent.is_deleted == True))  # noqa: E712
        natija.append(("ikkinchi yurgizish hech narsa qo'shmadi", yana, oldingi_ochirilgan))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
