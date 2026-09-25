"""Kromka proshivkasi v1.16 — o'zgargan joylari bizda ishlaydimi.

Yangiliklari (jasper2233/kromka-stansiya-OYY, 2026-09-21):
  * `tiqilish` hodisasi — detallar birga o'tgan yoki datchik ostida turib qolgan;
  * stansiya jim bo'lsa Pico USB ga UMUMAN yozmaydi (xotiraga yig'adi);
  * avariya boshlanganda `{"ev":"holat","alarm":1}` — ichida `uskuna` YO'Q.
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import types
from uuid import uuid4

from sqlalchemy import select, text

AGENT_PY = os.path.join(os.path.dirname(__file__), "..", "..", "bridge-agent", "agent.py")


def agentni_yukla(navbat):
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


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    import tempfile
    navbat = os.path.join(tempfile.mkdtemp(prefix="kromka116-"), "andon-queue.jsonl")
    agent = agentni_yukla(navbat)
    agent.ANDON_TUR.update({"tur": None, "session": "", "seq": 0, "uskuna": None})

    # --- v1.16 qatorlari (firmware `yubor()` aynan shunday yozadi)
    qatorlar = [
        json.dumps({"ev": "boot", "D": 2555.0, "V10": 10.0, "V18": 18.0}),
        json.dumps({"ev": "holat", "alarm": 0, "uskuna": 1, "v_nom": 18, "ver": "1.16",
                    "n": 0, "navbat": 0, "kalib": 0}),
        json.dumps({"ev": "olchov", "n": 1, "L": 2000.0, "kod": "OK", "shubha": 0,
                    "L1": 2000.4, "L2": 1999.6, "d1": 120000, "d2": 120000,
                    "v_olch": 18.1, "v_nom": 18, "yangi": 1, "ish_ms": 6.7,
                    "farq": 0.8, "navbat": 0}),
        # YANGI: tiqilish — ikki detal birga o'tgan, o'lchov chiqmagan
        json.dumps({"ev": "tiqilish", "sabab": "birga_otdi", "n": 2, "L2": 3900.0,
                    "L1": [2000.0, 1900.0]}),
        # Avariya boshlandi: bu xabarda `uskuna` YO'Q — stanok to'xtadi deb o'qilmasin
        json.dumps({"ev": "holat", "alarm": 1}),
        # Buferdan kelgan tiqilish (stansiya jim turgan payt yig'ilgani)
        json.dumps({"ev": "tiqilish", "sabab": "vaqt_mos_emas", "n": 1, "L2": 500.0,
                    "L1": [2000.0], "eski_ms": 30000}),
    ]
    for q in qatorlar:
        agent._andon_line(q)  # noqa: SLF001

    navbatdagi = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()]
    turlar = [e["type"] for e in navbatdagi]
    natija.append(("tur kromka deb aniqlandi", agent.ANDON_TUR["tur"], "kromka"))
    natija.append(("firmware versiyasi o'qildi", agent.ANDON_TUR.get("ver"), "1.16"))
    natija.append(("tiqilish hodisasi navbatga tushdi", turlar.count("tiqilish"), 2))
    natija.append(("o'lchov ham o'z joyida", turlar.count("olchov"), 1))
    natija.append(("avariya xabari uskuna hodisasi yasamadi",
                   [t for t in turlar if t == "uskuna"], ["uskuna"]))
    natija.append(("o'sha uskuna — HOLAT dan, holat=1",
                   [(e.get("holat"), e.get("manba")) for e in navbatdagi if e["type"] == "uskuna"],
                   [(1, "holat")]))
    eski = [e for e in navbatdagi if e["type"] == "tiqilish" and e.get("eski_ms")]
    yangi_tiq = [e for e in navbatdagi if e["type"] == "tiqilish" and not e.get("eski_ms")]
    natija.append(("buferdagi tiqilish vaqti 30 s orqaga surildi",
                   yangi_tiq[0]["ts"] - eski[0]["ts"] if (eski and yangi_tiq) else None, 30))
    natija.append(("sabab va o'lchamlar saqlandi",
                   (yangi_tiq[0]["sabab"], yangi_tiq[0]["L2"], yangi_tiq[0]["L1"]),
                   ("birga_otdi", 3900.0, [2000.0, 1900.0])))

    # --- SERVER: yangi tur qabul qilinadimi
    from app.api.routes.bridge_agents import push_andon_events
    from app.core.db import local_session
    from app.models import AndonEvent, BridgeAgent, Machine, Post
    from app.models.enums import PostCode, PostUnit
    from app.schemas.bridge_agents import AndonPush

    async with local_session() as db:
        for jadval in ("kromka_measurement", "andon_event", "bridge_agent", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        stanok = Machine(name="Kromka-1", post_id=post.id)
        db.add(stanok)
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="kromka-pc", token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           machine_id=stanok.id))
        await db.commit()

        javob = await push_andon_events(db, AndonPush(events=navbatdagi), authorization=f"Bearer {token}")
        natija.append(("server hammasini qabul qildi",
                       (javob.accepted, javob.skipped), (len(navbatdagi), 0)))
        tiq_rows = (await db.execute(select(AndonEvent).where(AndonEvent.kind == "tiqilish"))).scalars().all()
        natija.append(("tiqilish bazada", len(tiq_rows), 2))
        natija.append(("payload xom holida",
                       sorted(r.payload.get("sabab") for r in tiq_rows),
                       ["birga_otdi", "vaqt_mos_emas"]))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
