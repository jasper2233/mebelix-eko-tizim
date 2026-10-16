"""Kromka Pico'sidagi joriy kalibrlash MES ga yetib boradi (docs/12 §4.18, 1-qadam — faqat o'qish).

HAQIQIY agent parseri (`bridge-agent/agent.py`) → HAQIQIY `POST /bridge-agents/andon`
(`push_andon_events`) → HAQIQIY `GET /machines/kromka-calibration`, Postgres ustida.

    - `HOLAT` javobidagi `KAL` qiymatlari `kal` hodisasi bo'lib navbatga tushadi;
    - xuddi shu qiymatlar qayta kelsa (har 30 s lik `HOLAT`) — YANGI hodisa yo'q;
    - qiymat o'zgarsa (`SET` javobi `{"ev":"kal",...}`) — yana bitta hodisa, `manba: set`;
    - qayta ulanishda birinchi `HOLAT` baribir yuboriladi (MES joriy holatni bilsin);
    - endpoint har Kromka stanogi uchun OXIRGI qiymatlarni qaytaradi, agent hali yubormaganida bo'sh.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \\
      && uv run python ../scripts/oracles/kromka_kal_oracle.py
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from uuid import uuid4

from sqlalchemy import text

AGENT_PY = os.path.join(os.path.dirname(__file__), "..", "..", "bridge-agent", "agent.py")


def agentni_yukla(navbat: str):
    os.environ.setdefault("BRIDGE_TOKEN", "sinov-token")
    os.environ.setdefault("MES_URL", "ws://localhost:8000")
    os.environ.setdefault("ANDON", "0")
    os.environ["ANDON_QUEUE_FILE"] = navbat
    for nom in ("websockets", "websockets.exceptions"):
        sys.modules.setdefault(nom, types.ModuleType(nom))
    sys.modules["websockets"].exceptions = sys.modules["websockets.exceptions"]  # type: ignore[attr-defined]
    spec = importlib.util.spec_from_file_location("mx_agent", os.path.abspath(AGENT_PY))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["mx_agent"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


KAL = {"D": 2553.37, "V10": 10.151, "V18": 18.227, "K1": -0.001, "K2": -0.002, "B1": -2.19, "B2": -5.73,
       "C": 0.885, "TD": 12.0, "AO": 1.0, "HQ": 2500.0, "HA": 1500.0, "AV": 1.0}


def holat(**kal) -> str:
    return json.dumps({"ev": "holat", "alarm": 0, "uskuna": 1, "v_nom": 10, "kalib": 0, "n": 5, "navbat": 0,
                       "ver": "1.22", "sabab": "wdt", "up": 123456, "xotira": 0, "xb": "abcd1234", **kal})


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    navbat = os.path.join(tempfile.mkdtemp(prefix="kal-"), "andon-queue.jsonl")
    agent = agentni_yukla(navbat)
    agent.ANDON_TUR.update({"tur": None, "session": "", "seq": 0, "uskuna": None, "kal": None})

    def kal_hodisalar() -> list[dict]:
        if not os.path.exists(navbat):
            return []
        return [e for e in (json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines())
                if e.get("type") == "kal"]

    agent._andon_line(json.dumps({"ev": "boot", "sabab": "wdt", "ver": "1.22"}))  # noqa: SLF001 — tur kromka
    agent._andon_line(holat(**KAL))  # noqa: SLF001
    agent._andon_line(holat(**KAL))  # noqa: SLF001  — 30 s dan keyin xuddi shu
    natija.append(("HOLAT qiymatlari bitta hodisa bo'ldi, takror yozilmadi", len(kal_hodisalar()), 1))
    birinchi = kal_hodisalar()[0]
    natija.append(("hodisada Pico qiymatlari, versiya va manba",
                   ({k: birinchi[k] for k in ("D", "B1", "AO")}, birinchi["ver"], birinchi["manba"]),
                   ({"D": 2553.37, "B1": -2.19, "AO": 1.0}, "1.22", "holat")))

    yangi = {**KAL, "D": 2554.0, "AO": 0.0}
    agent._andon_line(json.dumps({"ev": "kal", **yangi}))  # noqa: SLF001  — SET javobi
    agent._andon_line(holat(**yangi))  # noqa: SLF001  — keyingi HOLAT o'sha qiymat
    hodisalar = kal_hodisalar()
    natija.append(("SET javobi yangi hodisa (manba set), keyingi HOLAT takrorlamadi",
                   [(e["D"], e["manba"]) for e in hodisalar], [(2553.37, "holat"), (2554.0, "set")]))

    agent.ANDON_TUR["kal"] = None  # `_andon_session` qayta ulanishda shunday qiladi
    agent._andon_line(holat(**yangi))  # noqa: SLF001
    natija.append(("qayta ulanishda birinchi HOLAT baribir yuborildi", len(kal_hodisalar()), 3))

    # --- SERVER
    from app.api.routes.bridge_agents import push_andon_events
    from app.api.routes.machines import read_kromka_calibration
    from app.core.db import local_session
    from app.models import BridgeAgent, Machine, Post
    from app.models.enums import PostCode, PostUnit
    from app.schemas.bridge_agents import AndonPush

    barchasi = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()]
    async with local_session() as db:
        for jadval in ("kromka_measurement", "andon_event", "bridge_agent", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        k1 = Machine(name="Kromka-1", post_id=post.id)
        k2 = Machine(name="Kromka-2", post_id=post.id)
        db.add_all([k1, k2])
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="kromka-pc", token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           machine_id=k1.id))
        await db.commit()
        javob = await push_andon_events(db, AndonPush(events=barchasi), authorization=f"Bearer {token}")
        natija.append(("server kal hodisalarini qabul qildi (rad yo'q)", javob.skipped, 0))
        qatorlar = {r.machine_name: r for r in await read_kromka_calibration(db, None)}  # type: ignore[arg-type]
        r1, r2 = qatorlar["Kromka-1"], qatorlar["Kromka-2"]
        natija.append(("endpoint OXIRGI qiymatlarni beradi",
                       (r1.values["D"], r1.values["AO"], r1.ver), (2554.0, 0.0, "1.22")))
        natija.append(("13 ta parametrning hammasi", len(r1.values), 13))
        natija.append(("agent yubormagan stanok bo'sh", (r2.at, r2.values), (None, {})))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
