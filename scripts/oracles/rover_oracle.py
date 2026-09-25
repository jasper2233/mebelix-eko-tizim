"""ROVER (CNC 2130) Pico'si — agent parseri va serverga yetib borishi.

Firmware alohida repoda (`jasper2233/cnc2130-oyy-mes`) va kromkadan boshqacha:
ikki tomonlama aloqa, davomiylikni Pico O'ZI o'lchaydi, hodisa `ack` kelmaguncha
fleshda qoladi. Bu yerda uning qatorlari agentdan o'tkaziladi va HAQIQIY
endpointga yuboriladi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/rover_oracle.py
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

from sqlalchemy import select, text

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


class SoxtaPort:
    """Pico o'rniga: agent yozgan JSON buyruqlarini yig'adi."""

    def __init__(self) -> None:
        self.xabarlar: list[dict] = []

    def write(self, data: bytes) -> None:
        for satr in data.decode().splitlines():
            if satr.strip():
                self.xabarlar.append(json.loads(satr))


def navbatni_oqi(fayl: str) -> list[dict]:
    return [json.loads(x) for x in open(fayl, encoding="utf-8").read().splitlines()]


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    navbat = os.path.join(tempfile.mkdtemp(prefix="rover-"), "andon-queue.jsonl")
    agent = agentni_yukla(navbat)
    agent.ANDON_TUR.update({"tur": None, "session": "", "seq": 0, "uskuna": None})
    port = SoxtaPort()

    # --- Pico ulandi: oxirgi tasdiqlangan seq 7
    agent._andon_line(json.dumps({  # noqa: SLF001
        "t": "hello", "machine": "CNC2130", "boot": 12, "seq": 9, "last_ack": 7, "need_time": 1}))
    natija.append(("tur rover deb aniqlandi", agent.ANDON_TUR["tur"], "rover"))
    natija.append(("tasdiqlangan joydan davom etadi",
                   (agent.ROVER["ack_upto"], agent.ROVER["seen"], agent.ROVER["boot"]), (7, 7, 12)))

    agent._rover_time(port)    # noqa: SLF001
    agent._rover_config(port)  # noqa: SLF001
    agent._rover_config(port)  # noqa: SLF001  — ikkinchi marta yuborilmasligi kerak
    natija.append(("vaqt yuborildi (Pico'da soat yo'q)",
                   [m["t"] for m in port.xabarlar], ["time", "config"]))
    natija.append(("vaqt yilgacha berilgan", len(port.xabarlar[0]["ts"]), 6))
    natija.append(("1-bosqichda avtomatik o'chirish o'chiq",
                   (port.xabarlar[1]["auto_shutdown"], port.xabarlar[1]["t_reason"]), (False, 300)))

    # --- Holat: stanok yoqildi, shpindel aylanmayapti
    agent._andon_line(json.dumps({"t": "state", "pwr": 1, "run": 0, "idle_sec": 40}))  # noqa: SLF001
    natija.append(("yoqiq-u aylanmasa — bo'sh turish", agent.ANDON_CURRENT["state"], "IDLE"))
    agent._andon_line(json.dumps({"t": "state", "pwr": 1, "run": 1, "on_sec": 120}))  # noqa: SLF001
    natija.append(("aylanayotgan bo'lsa — ishlov", agent.ANDON_CURRENT["state"], "PROCESSING"))
    agent._andon_line(json.dumps({"t": "state", "pwr": 1, "run": 1, "on_sec": 130}))  # noqa: SLF001
    q = navbatni_oqi(navbat)
    natija.append(("hodisa faqat O'ZGARISHDA yoziladi", len(q), 2))
    natija.append(("kromka bilan BIR XIL `uskuna` turi",
                   [(e["type"], e["holat"], e["manba"]) for e in q],
                   [("uskuna", 0, "rover"), ("uskuna", 1, "rover")]))

    # --- Pico o'lchab tugatgan davrlar; 7 va undan pastlari allaqachon tasdiqlangan
    for seq, tur, end in ((7, "POWER_ON", "2026-09-25T08:00:00"),
                          (8, "SPINDLE_IDLE", "2026-09-25T09:15:30"),
                          (9, "AUTO_SHUTDOWN", "2026-09-25T18:00:00")):
        agent._andon_line(json.dumps({  # noqa: SLF001
            "t": "event", "seq": seq, "type": tur, "start": "2026-09-25T07:00:00",
            "end": end, "dur": 3600}))
    agent._andon_line(json.dumps({  # noqa: SLF001  — tasdiq kutib QAYTA yuborildi
        "t": "event", "seq": 8, "type": "SPINDLE_IDLE", "start": "2026-09-25T07:00:00",
        "end": "2026-09-25T09:15:30", "dur": 3600}))
    hodisalar = navbatni_oqi(navbat)[2:]
    natija.append(("tasdiqlangani qayta olinmaydi, takrori ham",
                   [e["seq"] for e in hodisalar], [8, 9]))
    natija.append(("asl turi `rover_type` da qoladi",
                   [(e["type"], e["rover_type"]) for e in hodisalar],
                   [("rover", "SPINDLE_IDLE"), ("rover", "AUTO_SHUTDOWN")]))
    natija.append(("vaqt Pico bergan TUGASH paytidan",
                   hodisalar[0]["ts"], int(__import__("time").mktime(
                       __import__("time").strptime("2026-09-25T09:15:30", "%Y-%m-%dT%H:%M:%S")))))

    oldin = len(port.xabarlar)
    agent._rover_ack(port)  # noqa: SLF001
    natija.append(("server yozmaguncha tasdiq yo'q", len(port.xabarlar), oldin))

    # --- SERVER
    from app.api.routes.bridge_agents import push_andon_events
    from app.core.db import local_session
    from app.models import AndonEvent, BridgeAgent, Machine, Post
    from app.models.enums import PostCode, PostUnit
    from app.schemas.bridge_agents import AndonPush

    barchasi = navbatni_oqi(navbat)
    async with local_session() as db:
        for jadval in ("kromka_measurement", "andon_event", "bridge_agent", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.ROVER, name="Rover", order_index=6, unit=PostUnit.PIECE)
        db.add(post)
        await db.flush()
        stanok = Machine(name="Rover-1", post_id=post.id)
        db.add(stanok)
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="rover-pc", token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           machine_id=stanok.id))
        await db.commit()

        javob = await push_andon_events(db, AndonPush(events=barchasi), authorization=f"Bearer {token}")
        natija.append(("server hammasini qabul qildi", (javob.accepted, javob.skipped), (4, 0)))
        takror = await push_andon_events(db, AndonPush(events=barchasi), authorization=f"Bearer {token}")
        natija.append(("takror partiya yangi yozuv bermadi", (takror.accepted, takror.duplicates), (0, 4)))
        saqlangan = (await db.execute(
            select(AndonEvent.kind, AndonEvent.session, AndonEvent.seq, AndonEvent.payload)
            .order_by(AndonEvent.id))).tuples().all()
        natija.append(("rover hodisalari `rover` sessiyasida",
                       [(k, s, q) for k, s, q, _p in saqlangan if k == "rover"],
                       [("rover", "rover", 8), ("rover", "rover", 9)]))
        natija.append(("xom maydonlar saqlandi",
                       [p.get("dur") for k, _s, _q, p in saqlangan if k == "rover"], [3600, 3600]))

    # --- Server yozgach tasdiq ketadi
    agent._rover_acked(barchasi)  # noqa: SLF001
    agent._rover_ack(port)        # noqa: SLF001
    natija.append(("tasdiq eng katta uzluksiz seq bilan",
                   port.xabarlar[-1], {"t": "ack", "seq": 9}))
    oldin = len(port.xabarlar)
    agent._rover_ack(port)        # noqa: SLF001
    natija.append(("bir xil tasdiq takrorlanmaydi", len(port.xabarlar), oldin))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
