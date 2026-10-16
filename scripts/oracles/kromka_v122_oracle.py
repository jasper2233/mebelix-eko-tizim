"""Kromka proshivkasi v1.22 — tasdiq (ACK) bilan yetkazish.

Pico endi har muhim hodisaga `xb` (yonish belgisi) va `xq` (raqam) qo'yadi va
`ACK <xb> <xq>` kelmaguncha uni HAR 5 SONIYADA QAYTA yuboradi.

Tekshiriladi: takror hodisa navbatga bir marta tushishi, kalit Pico'niki
(`xb`/`xq`) bo'lishi, tasdiq FAQAT server yozgandan keyin ketishi, Pico qayta
yonganda hisob noldan boshlanishi va ESKI proshivka (xb/xq siz) ishlashda
davom etishi.
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


class SoxtaPort:
    """Pico o'rniga: agent yozgan buyruqlarni yig'adi."""

    def __init__(self):
        self.satrlar: list[str] = []

    def write(self, data: bytes) -> None:
        self.satrlar.extend(x for x in data.decode().splitlines() if x)


def olchov(xb, xq, L, eski_ms=None):
    """v1.22 firmware yozadigan o'lchov qatori."""
    d = {"ev": "olchov", "n": xq, "L": L, "kod": "OK", "shubha": 0,
         "L1": L + 0.4, "L2": L - 0.4, "d1": 120000, "d2": 120000,
         "v_olch": 18.1, "v_nom": 18, "yangi": 1, "ish_ms": 8200.0,
         "farq": 0.8, "navbat": 0, "xb": xb, "xq": xq}
    if eski_ms:
        d["eski_ms"] = eski_ms
    return json.dumps(d)


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    import tempfile
    navbat = os.path.join(tempfile.mkdtemp(prefix="kromka122-"), "andon-queue.jsonl")
    agent = agentni_yukla(navbat)
    agent.ANDON_TUR.update({"tur": None, "session": "", "seq": 0, "uskuna": None})
    port = SoxtaPort()

    XB = "a1b2c3d4"
    # --- Boot + ikkita o'lchov (v1.21 dan `sabab` bilan)
    qatorlar = [
        json.dumps({"ev": "boot", "D": 2555.0, "V10": 10.0, "V18": 18.0,
                    "sabab": "wdt", "xb": XB, "xq": 1}),
        olchov(XB, 2, 2000.0),
        olchov(XB, 3, 1800.0),
        # Pico tasdiq kutib O'SHA ikkitasini qayta yuboradi (eski_ms bilan)
        olchov(XB, 2, 2000.0, eski_ms=5000),
        olchov(XB, 3, 1800.0, eski_ms=5000),
        # v1.20 dan: lampa fazasi va xotira hisoboti — MESga yozilmaydi
        json.dumps({"ev": "sig", "r": "avariya", "on": 1, "ms": 1000}),
        json.dumps({"ev": "yigilgan", "n": 3, "yoqolgan": 0}),
    ]
    for q in qatorlar:
        agent._andon_line(q)  # noqa: SLF001

    navbatdagi = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()]
    natija.append(("tur kromka deb aniqlandi", agent.ANDON_TUR["tur"], "kromka"))
    natija.append(("takror hodisa navbatga BIR marta tushdi", len(navbatdagi), 3))
    natija.append(("kalit Pico'niki (xb/xq)",
                   [(e["session"], e["seq"]) for e in navbatdagi], [(XB, 1), (XB, 2), (XB, 3)]))
    natija.append(("qayta yuklanish sababi saqlandi",
                   next((e.get("sabab") for e in navbatdagi if e["type"] == "boot"), None), "wdt"))
    natija.append(("sig va yigilgan yozilmaydi",
                   [e["type"] for e in navbatdagi], ["boot", "olchov", "olchov"]))
    natija.append(("server yozmaguncha tasdiq yo'q",
                   [x for x in port.satrlar if x.startswith("ACK")], []))

    # --- SERVER: hammasi yoziladi, takror partiya yangi yozuv bermaydi
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
        natija.append(("server hammasini qabul qildi", (javob.accepted, javob.skipped), (3, 0)))
        takror = await push_andon_events(db, AndonPush(events=navbatdagi), authorization=f"Bearer {token}")
        natija.append(("takror partiya yangi yozuv bermadi", (takror.accepted, takror.duplicates), (0, 3)))
        saqlangan = (await db.execute(select(AndonEvent))).scalars().all()
        natija.append(("bazada 3 ta hodisa", len(saqlangan), 3))

    # --- Server yozgach tasdiq ketadi
    agent._kromka_acked(navbatdagi)  # noqa: SLF001
    agent._kromka_ack(port)          # noqa: SLF001
    acks = [x for x in port.satrlar if x.startswith("ACK")]
    natija.append(("tasdiq bitta qatorda ketdi", len(acks), 1))
    natija.append(("tasdiqda yonish belgisi va raqamlar",
                   acks[0] if acks else "", f"ACK {XB} 1 2 3"))
    agent._kromka_ack(port)          # noqa: SLF001
    natija.append(("bir xil tasdiq ikki marta yuborilmaydi",
                   len([x for x in port.satrlar if x.startswith("ACK")]), 1))

    # --- Pico QAYTA YONDI: yangi `xb`, raqamlar 1 dan
    YANGI_XB = "ffee0011"
    agent._andon_line(olchov(YANGI_XB, 1, 1500.0))  # noqa: SLF001
    keyin = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()]
    natija.append(("qayta yonishdan keyin hisob noldan",
                   (keyin[-1]["session"], keyin[-1]["seq"]), (YANGI_XB, 1)))
    natija.append(("eski tasdiqlar tashlandi", agent.KROMKA["ack"], set()))

    # --- ESKI proshivka (xb/xq siz) ishlayveradi
    agent._andon_line(json.dumps({"ev": "olchov", "L": 999.0, "kod": "OK", "v_nom": 18}))  # noqa: SLF001
    eski = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()][-1]
    natija.append(("eski proshivkaga agent kalit beradi",
                   (eski["session"] != YANGI_XB, isinstance(eski["seq"], int)), (True, True)))

    # --- 1.10.0: TARTIBSIZ kelish. Agent uzilgan paytda 60 ta o'lchov yig'ilgan; Pico
    # zaxirani 40 talab qayta yuboradi, orasiga jonli o'lchov (61) tushadi: 1..40, 61, 41..60
    TXB = "0badc0de"
    oldin = len(open(navbat, encoding="utf-8").read().splitlines())
    for xq in [*range(1, 41), 61, *range(41, 61)]:
        agent._andon_line(olchov(TXB, xq, 700.0))  # noqa: SLF001
    yangi = [json.loads(x) for x in open(navbat, encoding="utf-8").read().splitlines()][oldin:]
    natija.append(("tartibsiz: 61 ta o'lchovning hammasi navbatda",
                   sorted(e["seq"] for e in yangi), list(range(1, 62))))
    agent._andon_line(olchov(TXB, 45, 700.0))  # noqa: SLF001  — tasdiq kutib qayta kelgan
    natija.append(("tartibsiz: qayta kelgani takror yozilmadi",
                   len(open(navbat, encoding="utf-8").read().splitlines()) - oldin, 61))
    # Server yozdi → ACK ketdi, LEKIN port uzilib Pico uni olmadi va 7 ni qayta yubordi
    port2 = SoxtaPort()
    agent._kromka_acked(yangi)  # noqa: SLF001
    agent._kromka_ack(port2)    # noqa: SLF001
    agent._kromka_ack(port2)    # noqa: SLF001
    jami = sorted(int(x) for s in port2.satrlar for x in s.split()[2:])
    natija.append(("tartibsiz: hammasi tasdiqlandi (40 talab)", jami, list(range(1, 62))))
    agent._andon_line(olchov(TXB, 7, 700.0))  # noqa: SLF001
    agent._kromka_ack(port2)    # noqa: SLF001
    natija.append(("yo'qolgan ACK: qayta kelganda qayta aytiladi", port2.satrlar[-1], f"ACK {TXB} 7"))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
