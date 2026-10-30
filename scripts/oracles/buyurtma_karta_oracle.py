"""EKO 11b: moliya buyurtma kartasi — to'lovlar, ESF va tannarx hisobotlardagi raqamlar bilan bir xilmi.

cd backend && uv run python ../scripts/oracles/buyurtma_karta_oracle.py <demo parol>   (lokal sinov, prod EMAS)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal

API = "http://localhost:8005/api/v1"
PAROL = sys.argv[1]
natija: list[bool] = []


def token(login: str) -> str:
    body = urllib.parse.urlencode({"username": login, "password": PAROL}).encode()
    with urllib.request.urlopen(urllib.request.Request(API + "/login/access-token", data=body), timeout=20) as r:
        return str(json.loads(r.read())["access_token"])


def ol(path: str, tok: str) -> tuple[int, object]:
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


D = Decimal
mol = token("moliyachi")
tek("kassir — ruxsat yo'q", ol("/moliya/buyurtma/1", token("kassir"))[0], 403)
tek("yo'q buyurtma — 404", ol("/moliya/buyurtma/999999", mol)[0], 404)

# P&L dagi buyurtma tannarxi va foydasi = kartadagi
bugun = date.today()
for oy in [f"{(bugun.year * 12 + bugun.month - 1 - i) // 12}-{(bugun.month - 1 - i) % 12 + 1:02d}" for i in range(12)]:
    _, p = ol(f"/moliya/pnl?oy={oy}", mol)
    assert isinstance(p, dict)
    for r in p["buyurtmalar"][:5]:
        _, k = ol(f"/moliya/buyurtma/{r['order_id']}", mol)
        assert isinstance(k, dict)
        tek(f"{oy} {r['number']}: tannarx P&L bilan", D(k["tannarx"]), D(r["tannarx"]))
        tek(f"{oy} {r['number']}: foyda P&L bilan", D(k["foyda"]), D(r["foyda"]))
        tek(f"{oy} {r['number']}: tannarx = material + mehnat", D(k["tannarx"]), D(k["material"]) + D(k["mehnat"]))
        tolov = sum((D(t["summa"]) for t in k["tolovlar"]), D(0))
        tek(f"{oy} {r['number']}: to'langan = kassagacha + to'lovlar", D(k["tolangan"]), D(k["kassagacha"]) + tolov)
        tek(f"{oy} {r['number']}: qarz = summa − to'langan", D(k["qarz"]), max(D(k["summa"]) - D(k["tolangan"]), D(0)))

# ESF: kartadagi ESF lar buyurtmaga tegishli (soliq ro'yxatidagi order_id bilan)
_, esf = ol("/soliq/esf?tur=chiquvchi", mol)
if isinstance(esf, list):
    for e in [x for x in esf if x.get("order_id")][:5]:
        _, k = ol(f"/moliya/buyurtma/{e['order_id']}", mol)
        assert isinstance(k, dict)
        tek(f"ESF {e['no']} kartada", e["no"] in [x["no"] for x in k["esflar"]], True)
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
