"""Kalibrlash hisobi stansiya hisobi bilan BIR XIL (docs/12 §4.19, 2-qadam).

1) Ma'lum parametrli sun'iy o'tishlardan (`olchov` payload'i shaklida) `kromka_kalib.hisobla`
   D, B1, B2, C, K ni qaytarib topadimi; 1 uzunlik / 1 tezlikda soddaroq model tanlanadimi;
   ataylab buzilgan nuqta 3σ bilan chetlatiladimi.
2) Agar `KROMKA_STANSIYA_HTML` berilsa (jasper2233/kromka-stansiya-OYY: server/stansiya.html) —
   undagi ASL JS funksiyalar (`gauss` … `kalHisob`) Node'da xuddi shu nuqtalarda yurgiziladi va
   natija raqamma-raqam solishtiriladi.

3) DB berilsa — haqiqiy endpointlar (sessiya, bog'lanmaslik, chetlatish).
4) 3-qadam: qo'llash buyrug'i server → agent → Pico → tasdiq, chegaralar, orqaga qaytarish.

Yurgizish:
    cd backend && KROMKA_STANSIYA_HTML=../../ext/kromka-stansiya-OYY/server/stansiya.html \\
      uv run python ../scripts/oracles/kromka_kalib_oracle.py
"""

import json
import os
import random
import subprocess
import tempfile

from app.services.kromka_kalib import hisobla, nuqta

ASL = {"D": 2553.37, "B1": -2.19, "B2": -5.73, "C": 0.885, "K1": 0.30, "K2": -0.20}


def otishlar(lens: list[float], tez: list[int], n: int, shovqin: float, seed: int) -> list[dict]:
    """Model bo'yicha Pico payload'lari: t_i = (L+B_i)/v + k_i, dt_mid = D/v + C (ms; d1/d2 µs)."""
    r = random.Random(seed)
    out = []
    for L in lens:
        for S in tez:
            for _ in range(n):
                v = S / 60 * (1 + r.gauss(0, shovqin))  # mm/ms
                dtm = ASL["D"] / v + ASL["C"]
                t1 = (L + ASL["B1"]) / v + ASL["K1"] + r.gauss(0, 0.5)
                t2 = (L + ASL["B2"]) / v + ASL["K2"] + r.gauss(0, 0.5)
                out.append({"L_ref": L, "d1": t1 * 1000, "d2": t2 * 1000,
                            "ish_ms": dtm - (t2 - t1) / 2, "v_nom": S})
    return out


def py(ots: list[dict]) -> dict:
    pts = [p for i, o in enumerate(ots) if (p := nuqta(i, o["L_ref"], o))]
    r = hisobla(pts)
    assert r
    r["chet_i"] = sorted(p.i for p in pts if p.chet)
    return r


def js(html: str, ots: list[dict]) -> dict:
    src = open(html, encoding="utf-8").read()
    bosh, oxir = src.index("function gauss("), src.index("// Nuqtalar brauzerda saqlanadi")
    kod = src[bosh:oxir]
    pts = [{"L_ref": o["L_ref"], "S": o["v_nom"], "t1": o["d1"], "t2": o["d2"], "dt": o["ish_ms"] * 1000}
           for o in ots]
    skript = (f"let kalPts={json.dumps(pts)};\n{kod}\nconst r=kalHisob();"
              "console.log(JSON.stringify({D:r.D,B1:r.b1,B2:r.b2,K1:r.k1,K2:r.k2,C:r.C,tur:r.tur,sd:r.sd,"
              "max_err:r.maxErr,sd_dat:r.sdDat,sd_tez:r.sdTez,dif_ort:r.difOrt,V10:r.V10,V18:r.V18,"
              "n_ish:r.ish.length,chet_i:r.chet.map(p=>p.i).sort((a,b)=>a-b),"
              "grp:r.grp.map(g=>[g.L_ref,g.S,g.n,g.mean,g.sd])}));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(skript)
    return json.loads(subprocess.run(["node", f.name], capture_output=True, text=True, check=True).stdout)


def yaqin(a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(yaqin(x, y) for x, y in zip(a, b, strict=True))
    return a == b


natija: list[tuple[str, bool, str]] = []

toliq = otishlar([300, 580, 900, 1500, 2000, 2740], [10, 18], 5, 0.0002, 1)
r = py(toliq)
xato = {k: round(r[k] - ASL[k], 3) for k in ("D", "B1", "B2", "C")}
natija.append(("6 uzunlik × 2 tezlik: D, B1, B2, C qaytarib topildi (±0.5)",
               all(abs(v) < 0.5 for v in xato.values()), str(xato)))
natija.append(("to'liq ma'lumotda hukm ok yoki w, kam yo'q, qo'llasa bo'ladi",
               r["kam"] == [] and r["qollasa_boladi"], f"{r['hukm']} kam={r['kam']}"))

bir = py(otishlar([1500], [10, 18], 10, 0.0002, 2))
natija.append(("1 uzunlik: faqat D (B=0, C=0), qo'llash yo'q",
               (bir["B1"], bir["C"], bir["tur"], bir["qollasa_boladi"]) == (0.0, 0.0, {}, False),
               f"tur={bir['tur']} D={bir['D']:.2f}"))

tez1 = py(otishlar([580, 2000], [10], 10, 0.0002, 3))
natija.append(("1 tezlik: B bor, C/K yo'q", tez1["tur"] == {"B": 1} and tez1["C"] == 0.0, str(tez1["tur"])))

buzuq = otishlar([300, 900, 2000], [10, 18], 6, 0.0002, 4)
buzuq[7]["d1"] += 200_000
buzuq[7]["d2"] += 200_000
rb = py(buzuq)
natija.append(("buzilgan o'tish chetlatildi", 7 in rb["chet_i"], f"chet={rb['chet_i']}"))

html = os.environ.get("KROMKA_STANSIYA_HTML")
if html:
    for nom, ots in (("to'liq", toliq), ("1 uzunlik", otishlar([1500], [10, 18], 10, 0.0002, 2)),
                     ("1 tezlik", otishlar([580, 2000], [10], 10, 0.0002, 3)), ("buzuq", buzuq),
                     ("shovqinli", otishlar([300, 1200, 2740], [10, 18], 8, 0.002, 5))):
        a, b = py(ots), js(html, ots)
        a["grp"] = [[g["L_ref"], g["S"], g["n"], g["mean"], g["sd"]] for g in a["grp"]]
        farq = [k for k in b if not yaqin(a[k], b[k])]
        natija.append((f"JS bilan bir xil: {nom}", not farq, f"farq={farq}" if farq else f"D={a['D']:.4f}"))
else:
    print("  (KROMKA_STANSIYA_HTML yo'q — JS paritet o'tkazib yuborildi)")



async def db_qismi() -> None:
    """HAQIQIY endpointlar Postgres ustida: sessiya oralig'idagi o'tish skanga bog'lanmaydi,
    tafsilot sof hisob bilan bir xil, chetlatish ishlaydi, ikkinchi ochiq sessiya rad etiladi."""
    import hashlib
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from fastapi import HTTPException
    from sqlalchemy import func, select, text

    from app.api.routes.bridge_agents import push_andon_events
    from app.api.routes.kromka_kalib import (
        end_kalib_session,
        exclude_kalib_point,
        read_kalib_session,
        set_kalib_etalon,
        start_kalib_session,
    )
    from app.core.db import local_session
    import types

    from app.models import BridgeAgent, KromkaKalibSession, KromkaMeasurement, Machine, Post
    from app.models.enums import PostCode, PostUnit
    from app.schemas.bridge_agents import AndonPush
    from app.schemas.kromka_kalib import KalibEtalon, KalibExclude, KalibStart

    async with local_session() as db:
        for jadval in ("kromka_kalib_session", "kromka_measurement", "andon_event", "bridge_agent", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        k1 = Machine(name="Kromka-1", post_id=post.id)
        db.add(k1)
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="kromka-pc", token_hash=hashlib.sha256(token.encode()).hexdigest(), machine_id=k1.id))
        admin = types.SimpleNamespace(id=None)  # created_by ixtiyoriy; sinov bazasida foydalanuvchi yo'q
        await db.commit()

        s = await start_kalib_session(db, admin, KalibStart(machine_id=k1.id, L_ref=580))  # type: ignore[arg-type]
        try:
            await start_kalib_session(db, admin, KalibStart(machine_id=k1.id, L_ref=580))  # type: ignore[arg-type]
            natija.append(("ikkinchi ochiq sessiya rad etildi", False, "qabul qilindi"))
        except HTTPException as e:
            natija.append(("ikkinchi ochiq sessiya rad etildi", e.status_code == 409, str(e.status_code)))

        # Sessiyani 10 daqiqa oldinga suramiz: hodisalar o'tmish vaqtida keladi
        bosh = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=10)
        row = await db.get(KromkaKalibSession, s.id)
        assert row
        row.started_at = bosh
        row.segments = [{"L_ref": 580, "dan": bosh.isoformat()}, {"L_ref": 2000, "dan": (bosh + timedelta(minutes=5)).isoformat()}]
        await db.commit()

        ots = otishlar([580], [10, 18], 6, 0.0002, 7) + otishlar([2000], [10, 18], 6, 0.0002, 8)
        events = []
        for i, o in enumerate(ots):
            at = bosh + timedelta(seconds=20 + i * 20 if i < 12 else 320 + (i - 12) * 20)
            events.append({"type": "olchov", "session": "kal", "seq": i + 1, "ts": int(at.timestamp()),
                           "kod": "OK", "L": o["L_ref"], **{k: o[k] for k in ("d1", "d2", "ish_ms", "v_nom")}})
        # sessiyadan oldingi oddiy o'lchov — u bog'lanadi (skanersiz qator yoziladi)
        events.append({"type": "olchov", "session": "kal", "seq": 99, "ts": int((bosh - timedelta(minutes=1)).timestamp()),
                       "kod": "OK", "L": 600.0, "d1": 3.6e6, "d2": 3.6e6, "ish_ms": 15000, "v_nom": 10})
        await push_andon_events(db, AndonPush(events=events), authorization=f"Bearer {token}")
        bogl = await db.scalar(select(func.count()).select_from(KromkaMeasurement))
        natija.append(("sessiyadagi 24 o'tish skanga bog'lanmadi, tashqaridagi 1 ta bog'landi", bogl == 1, f"qator={bogl}"))

        d = await read_kalib_session(db, admin, s.id)  # type: ignore[arg-type]
        sof = py(ots)
        natija.append(("tafsilot: 24 nuqta, etalon bo'lak bo'yicha", (len(d.points), sorted({p.L_ref for p in d.points})) == (24, [580.0, 2000.0]), f"{len(d.points)}"))
        natija.append(("tafsilot natijasi sof hisob bilan bir xil", d.result is not None and yaqin(d.result["D"], sof["D"]), f"D={d.result and d.result['D']}"))

        await exclude_kalib_point(db, admin, s.id, d.points[0].event_id, KalibExclude(excluded=True))  # type: ignore[arg-type]
        d2 = await read_kalib_session(db, admin, s.id)  # type: ignore[arg-type]
        natija.append(("chetlatilgan nuqta hisobga kirmadi", d2.points[0].excluded and d2.points[0].err is None
                       and d2.result is not None and d2.result["n_ish"] + d2.result["n_chet"] == 23, f"n={d2.result and d2.result['n_ish']}"))

        await end_kalib_session(db, admin, s.id)  # type: ignore[arg-type]
        try:
            await set_kalib_etalon(db, admin, s.id, KalibEtalon(L_ref=900))  # type: ignore[arg-type]
            natija.append(("tugagan sessiyaga etalon qo'shilmaydi", False, "qo'shildi"))
        except HTTPException as e:
            natija.append(("tugagan sessiyaga etalon qo'shilmaydi", e.status_code == 409, str(e.status_code)))


async def qollash_qismi() -> None:
    """3-qadam uchidan-uchiga: HAQIQIY endpoint → HAQIQIY `push_andon_events` javobi → HAQIQIY
    agent (`_kromka_set_qabul`/`_kromka_set_yoz`, soxta port) → Pico'ning float32 `kal` javobi
    agent orqali → server tasdiqlaydi. Chegaralar, navbat, orqaga qaytarish, muddat."""
    import hashlib
    import importlib.util
    import struct
    import sys
    import types
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from fastapi import HTTPException
    from sqlalchemy import text

    from app.api.routes.bridge_agents import push_andon_events
    from app.api.routes.kromka_kalib import (
        apply_kalib_session,
        read_kalib_session,
        rollback_kal_apply,
    )
    from app.core.db import local_session
    from app.models import BridgeAgent, KromkaKalApply, KromkaKalibSession, Machine, Post
    from app.models.enums import PostCode, PostUnit
    from app.schemas.bridge_agents import AndonPush

    navbat = os.path.join(tempfile.mkdtemp(prefix="kalset-"), "q.jsonl")
    os.environ.update(BRIDGE_TOKEN="t", MES_URL="ws://localhost", ANDON="0", ANDON_QUEUE_FILE=navbat)
    for nom in ("websockets", "websockets.exceptions"):
        sys.modules.setdefault(nom, types.ModuleType(nom))
    sys.modules["websockets"].exceptions = sys.modules["websockets.exceptions"]  # type: ignore[attr-defined]
    spec = importlib.util.spec_from_file_location(
        "mx_agent", os.path.join(os.path.dirname(__file__), "..", "..", "bridge-agent", "agent.py")
    )
    agent = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(agent)  # type: ignore[union-attr]
    agent.ANDON_TUR.update({"tur": "kromka", "session": "", "seq": 0, "uskuna": None, "kal": None})

    class Port:
        def __init__(self) -> None:
            self.yozildi: list[str] = []

        def write(self, b: bytes) -> None:
            self.yozildi.append(b.decode())

    def f32(v: float) -> float:
        return struct.unpack("f", struct.pack("f", v))[0]

    def navbatni_ol() -> list[dict]:
        if not os.path.exists(navbat):
            return []
        out = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()]
        open(navbat, "w").close()
        return out

    admin = types.SimpleNamespace(id=None)
    req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="127.0.0.1"))
    joriy = {"D": 2550.0, "V10": 10.151, "V18": 18.227, "K1": 0.0, "K2": 0.0, "B1": -2.0, "B2": -5.0, "C": 0.5,
             "TD": 12.0, "AO": 0.0, "HQ": 2500.0, "HA": 1500.0, "AV": 1.0}
    async with local_session() as db:
        for jadval in ("kromka_kal_apply", "kromka_kalib_session", "kromka_measurement", "andon_event",
                       "bridge_agent", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        k1 = Machine(name="Kromka-1", post_id=post.id)
        db.add(k1)
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="pc", token_hash=hashlib.sha256(token.encode()).hexdigest(), machine_id=k1.id))
        await db.commit()

        async def push(events: list[dict]):  # noqa: ANN202
            return await push_andon_events(db, AndonPush(events=events), authorization=f"Bearer {token}")

        bosh = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=30)
        await push([{"type": "kal", "session": "k", "seq": 1, "ts": int(bosh.timestamp()) - 60, **joriy}])
        ots = otishlar([580, 2000], [10, 18], 8, 0.0002, 11)
        await push([{"type": "olchov", "session": "k", "seq": 10 + i, "ts": int(bosh.timestamp()) + 10 + i * 10,
                     "kod": "OK", "L": o["L_ref"], **{k: o[k] for k in ("d1", "d2", "ish_ms", "v_nom")}}
                    for i, o in enumerate(ots)])
        seg2 = bosh + timedelta(seconds=10 + 16 * 10 - 5)
        s = KromkaKalibSession(machine_id=k1.id, started_at=bosh, ended_at=None,
                               segments=[{"L_ref": 580, "dan": bosh.isoformat()}, {"L_ref": 2000, "dan": seg2.isoformat()}])
        db.add(s)
        await db.commit()

        try:
            await apply_kalib_session(db, admin, s.id, req)  # type: ignore[arg-type]
            natija.append(("ochiq sessiya qo'llanmaydi", False, "qo'llandi"))
        except HTTPException as e:
            natija.append(("ochiq sessiya qo'llanmaydi", e.status_code == 409, str(e.status_code)))
        s.ended_at = bosh + timedelta(minutes=10)
        await db.commit()

        a = await apply_kalib_session(db, admin, s.id, req)  # type: ignore[arg-type]
        natija.append(("qo'llash: qiymatlar hisobdan, oldingisi saqlandi",
                       abs(a.values["D"] - ASL["D"]) < 0.5 and a.previous["D"] == 2550.0 and a.status == "kutilmoqda",
                       a.line))
        try:
            await apply_kalib_session(db, admin, s.id, req)  # type: ignore[arg-type]
            natija.append(("javob kutilayotganda ikkinchi buyruq yo'q", False, "berildi"))
        except HTTPException as e:
            natija.append(("javob kutilayotganda ikkinchi buyruq yo'q", e.status_code == 409, str(e.status_code)))

        j = await push([])
        natija.append(("andon javobida buyruq bor", j.kal_set is not None and j.kal_set.line == a.line, str(j.kal_set)))

        port = Port()
        agent._kromka_set_qabul(j.kal_set.model_dump() if j.kal_set else None)  # noqa: SLF001
        agent._kromka_set_yoz(port)  # noqa: SLF001
        agent._kromka_set_yoz(port)  # noqa: SLF001
        natija.append(("agent Pico'ga aynan bir marta yozdi", port.yozildi == [a.line + "\n"], str(port.yozildi)))

        port2 = Port()
        for yomon in ("ALARM", "SET D=2550 ALARM", "SET TD=1", "SET D=1;ALARM", "KALIB 1"):
            agent._kromka_set_qabul({"id": 999, "line": yomon})  # noqa: SLF001
        agent.KROMKA["set_done"] = None
        agent.KROMKA["set"] = None
        agent._kromka_set_yoz(port2)  # noqa: SLF001
        natija.append(("agent SET dan boshqa matnni portga yozmaydi", port2.yozildi == [], str(port2.yozildi)))

        # Pico javobi: SET dan keyin qiymatlar float32 da qaytadi
        pico = {**joriy, **{k: f32(v) for k, v in a.values.items()}}
        agent._andon_line(json.dumps({"ev": "kal", **pico}))  # noqa: SLF001
        j2 = await push(navbatni_ol())
        row = await db.get(KromkaKalApply, a.id)
        natija.append(("Pico javobi (float32) tasdiq bo'ldi, buyruq boshqa berilmaydi",
                       row is not None and row.confirmed_at is not None and j2.kal_set is None, str(j2.kal_set)))
        # Tasdiqdan keyin Pico qayta ulansa eski buyruq yana yozilmasin
        agent.KROMKA.update(set=(a.id, a.line), set_done=a.id)
        agent._kromka_set_qabul(j2.kal_set)  # noqa: SLF001
        agent.KROMKA["set_done"] = None  # `_andon_session` yangi ulanishda shunday qiladi
        port3 = Port()
        agent._kromka_set_yoz(port3)  # noqa: SLF001
        natija.append(("tasdiqlangan buyruq qayta ulanishda yozilmaydi", port3.yozildi == [], str(port3.yozildi)))

        r = await rollback_kal_apply(db, admin, a.id, req)  # type: ignore[arg-type]
        natija.append(("orqaga qaytarish — eski qiymatlar bilan yangi buyruq",
                       r.values["D"] == 2550.0 and r.rollback_of_id == a.id, r.line))
        j3 = await push([])
        natija.append(("qaytarish ham agentga beriladi", j3.kal_set is not None and j3.kal_set.id == r.id, str(j3.kal_set)))

        # Pico javob bermadi — 10 daqiqadan keyin «javobsiz», boshqa berilmaydi, yangisiga yo'l ochiq
        rr = await db.get(KromkaKalApply, r.id)
        assert rr
        rr.created_at = datetime.now(UTC) - timedelta(minutes=11)
        await db.commit()
        j4 = await push([])
        d = await read_kalib_session(db, admin, s.id)  # type: ignore[arg-type]
        st = next(x.status for x in d.applies if x.id == r.id)
        natija.append(("javobsiz buyruq to'xtaydi", j4.kal_set is None and st == "javobsiz", st))

        # Chegara: joriy D 2520 bo'lsa yangi 2553 — 15 mm dan ko'p siljish, rad
        await push([{"type": "kal", "session": "k", "seq": 500, "ts": int(datetime.now(UTC).timestamp()),
                     **{**joriy, "D": 2520.0}}])
        try:
            await apply_kalib_session(db, admin, s.id, req)  # type: ignore[arg-type]
            natija.append(("D 15 mm dan ko'p siljisa rad etiladi", False, "qo'llandi"))
        except HTTPException as e:
            natija.append(("D 15 mm dan ko'p siljisa rad etiladi", e.status_code == 422, str(e.detail)))


if os.environ.get("POSTGRES_PORT"):
    import asyncio

    async def ikkalasi() -> None:  # bitta event loop — ulanishlar puli shunga bog'langan
        await db_qismi()
        await qollash_qismi()

    asyncio.run(ikkalasi())
else:
    print("  (POSTGRES_PORT yo'q — DB qismi o'tkazib yuborildi)")

for nom, ok, izoh in natija:
    print(f"  {'OK ' if ok else 'XATO'} {nom}: {izoh}")
print(f"\nXULOSA: {sum(ok for _, ok, _ in natija)}/{len(natija)} to'g'ri")
