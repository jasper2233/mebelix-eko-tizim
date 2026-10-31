"""EKO 12: furnitura MX dan MES ga — nom, birlik, yo'qolganda ogohlantirish (MES 8005 + MX klon 8010, lokal, prod EMAS).

cd backend && .venv/Scripts/python.exe ../scripts/oracles/kroy_furnitura_oracle.py <demo parol> <order_id>

Buyurtma MX ga bog'langan, MX da kesilgan va skansiz bo'lishi kerak (masalan B-2026-102). Oxirida furnitura tiklanadi.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

MES = "http://localhost:8005/api/v1"
MX = "http://localhost:8010/api"
PAROL, ORDER = sys.argv[1], int(sys.argv[2])
natija: list[bool] = []


def sorov(url: str, method: str = "GET", body: object = None, h: dict[str, str] | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(h or {})}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode(errors="replace")


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


body = urllib.parse.urlencode({"username": "texnolog", "password": PAROL}).encode()
with urllib.request.urlopen(urllib.request.Request(MES + "/login/access-token", data=body), timeout=20) as r:
    tex = {"Authorization": "Bearer " + json.loads(r.read())["access_token"]}
c, res = sorov(f"{MES}/integ/kroy/orders/{ORDER}/ochish", "POST", {}, tex)
assert c == 200 and isinstance(res, dict), (c, res)
tok = urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)["token"][0]
pid, mx = res["project_id"], {"Authorization": f"Bearer {tok}"}


def yubor(mats: list[dict[str, object]]) -> tuple[list[dict[str, str]], list[str]]:
    """Furniturani yozib, kroyni yuboradi; (MES material_usage dagi furnitura, ogohlantirishlar)."""
    _, p = sorov(f"{MX}/projects/{pid}", h=mx)
    assert isinstance(p, dict)
    if p.get("mes_sent"):
        assert sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx)[0] == 200
        _, p = sorov(f"{MX}/projects/{pid}", h=mx)
        assert isinstance(p, dict)
    op = next((o for o in p["operations"] if o["type"] == "O"), None)
    if op is None:
        _, p = sorov(f"{MX}/projects/{pid}/operations", "POST", {"type": "O", "code": "FURN", "name": "Furnitura"}, mx)
        assert isinstance(p, dict)
        op = p["operations"][-1]
    assert sorov(f"{MX}/projects/{pid}/operations/{op['id']}", "PATCH", {"o": {"materials": mats}}, mx)[0] == 200
    c, r = sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)
    assert c == 200 and isinstance(r, dict), (c, r)
    _, o = sorov(f"{MES}/orders/{ORDER}", h=tex)
    assert isinstance(o, dict)
    return [m for m in o["material_usage"] if m["kind"] == "hardware"], list(r.get("warnings") or [])


asl = [
    {"code": "SINOV-DASTA", "name": "Dasta", "unit": "шт", "qty": 2, "price": 0},
    {"code": "SINOV-PROFIL", "name": "Profil", "unit": "м", "qty": 2.5, "price": 0},
    {"code": "", "name": "Kodsiz vint", "unit": "компл.", "qty": 4, "price": 0},
]
print("Nom va birlik:")
f, _w = yubor(asl)
kor = {m["name"]: (m["count"], m["unit"]) for m in f}
tek("dona", kor.get("Dasta"), (2.0, "dona"))
tek("metr, soni kasr", kor.get("Profil"), (2.5, "metr"))
tek("komplekt, kodsiz", kor.get("Kodsiz vint"), (4.0, "komplekt"))
tek("nom oldida operatsiya nomi yo'q", any("Furnitura —" in m["name"] for m in f), False)

print("O'zgarmaganda ogohlantirish yo'q:")
_f, w = yubor(asl)
tek("yo'qolgan haqida xabar yo'q", [x for x in w if "furnitura yangisida yo'q" in x], [])

print("Yo'qolganda:")
_f, w = yubor(asl[:1])
tek(
    "birinchi ogohlantirish",
    w[0] if w else "",
    "Avvalgi kroydagi furnitura yangisida yo'q: Profil (2,5 metr), Kodsiz vint (4 komplekt). "
    "Kerak bo'lsa, loyihaga qo'shib qayta yuboring.",
)

print("Tiklash:")
f, _w = yubor(asl)
tek("3 ta qaytdi", len(f), 3)

# Rezerv qatori birligi (Ta'minot va uzatish tasdig'i shundan)
c, rez = sorov(f"{MES}/ombor/rezerv/{ORDER}", h=tex)
assert c == 200 and isinstance(rez, dict), (c, rez)
tek("rezervda metr", next(ln["fayl_birlik"] for ln in rez["lines"] if ln["tashqi_kalit"] == "SINOV-PROFIL"), "metr")
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
