"""EKO 12: «MES ga yuborish» — huquq, qulf, qayta ochish, versiya va farq (MES 8005 + MX klon 8010, lokal sinov, prod EMAS).

cd backend && .venv/Scripts/python.exe ../scripts/oracles/kroy_yuborish_oracle.py <demo parol> <order_id>

Buyurtma MX loyihasiga bog'langan va MX da kesilgan bo'lishi kerak (masalan B-2026-101).
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

MES = "http://localhost:8005/api/v1"
MX = "http://localhost:8010/api"
SERVIS = "lokal-sinov-kroy-token"
PAROL, ORDER = sys.argv[1], int(sys.argv[2])
natija: list[bool] = []


def sorov(
    url: str, method: str = "GET", body: object = None, headers: dict[str, str] | None = None
) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw[:200].decode(errors="replace")


def login(nom: str) -> dict[str, str]:
    body = urllib.parse.urlencode({"username": nom, "password": PAROL}).encode()
    with urllib.request.urlopen(urllib.request.Request(MES + "/login/access-token", data=body), timeout=20) as r:
        return {"Authorization": "Bearer " + str(json.loads(r.read())["access_token"])}


def mx_token(mes_h: dict[str, str]) -> tuple[str, str]:
    """MES «Kroy (MX)» qaytargan manzildan: SSO token va loyiha id."""
    c, r = sorov(f"{MES}/integ/kroy/orders/{ORDER}/ochish", "POST", {}, mes_h)
    assert c == 200 and isinstance(r, dict), (c, r)
    url = urllib.parse.urlsplit(r["url"])
    return urllib.parse.parse_qs(url.query)["token"][0], r["project_id"]


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


def versiyalar(h: dict[str, str]) -> dict[str, object]:
    c, r = sorov(f"{MES}/integ/kroy/orders/{ORDER}/versiyalar", headers=h)
    assert c == 200 and isinstance(r, dict), (c, r)
    return r


tex, men = login("texnolog"), login("menejer")
tok, pid = mx_token(tex)
mx = {"Authorization": f"Bearer {tok}"}
tok_men, _ = mx_token(men)
mx_men = {"Authorization": f"Bearer {tok_men}"}
c, p = sorov(f"{MX}/projects/{pid}", headers=mx)
assert c == 200 and isinstance(p, dict)
if not p.get("mes_sent"):
    tek("boshlanish: yuborish", sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)[0], 200)
    c, p = sorov(f"{MX}/projects/{pid}", headers=mx)
    assert isinstance(p, dict)
op = p["operations"][0]["id"]
v0 = versiyalar(tex)["versiyalar"][0]["versiya"]  # type: ignore[index]

print("Qulf (MX):")
tek("yuborilganda detal qo'shish — 409", sorov(f"{MX}/projects/{pid}/operations/{op}/parts", "POST", {}, mx)[0], 409)
tek("Ctrl+Z — 409", sorov(f"{MX}/projects/{pid}/undo", "POST", {}, mx)[0], 409)
tek("takror yuborish — 409", sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)[0], 409)
c, _ = sorov(f"{MX}/projects/{pid}/operations/{op}/maps/0", "PATCH", {"done_count": 0}, mx)
tek("arra «karta bajarildi» qulfga urilmaydi", c != 409, True)
tek("o'qish ochiq", sorov(f"{MX}/projects/{pid}", headers=mx)[0], 200)

print("Huquq (MES):")
srv = {"Authorization": f"Bearer {SERVIS}"}
c, pk = sorov(
    f"{MX}/projects/{pid}/mes-package?version=1&pp=enabled&files=inline&mes_order_number=B-2026-101", headers=mx
)
assert c == 200, (c, pk)
url = f"{MES}/integ/kroy/loyiha/{pid}/paket"
tek("xizmat tokenisiz — 401/403", sorov(url, "POST", pk, {"X-Mes-User-Token": tok})[0] in (401, 403), True)
tek("xodim tokenisiz — 401", sorov(url, "POST", pk, srv)[0], 401)
tek("soxta xodim tokeni — 401", sorov(url, "POST", pk, {**srv, "X-Mes-User-Token": tok[:-6] + "AAAAAA"})[0], 401)
tek("menejer yubora olmaydi — 403", sorov(url, "POST", pk, {**srv, "X-Mes-User-Token": tok_men})[0], 403)
tek(
    "bog'lanmagan loyiha — 404",
    sorov(f"{MES}/integ/kroy/loyiha/yoq000/paket", "POST", pk, {**srv, "X-Mes-User-Token": tok})[0],
    404,
)
tek("rad etilganda versiya o'smadi", versiyalar(tex)["versiyalar"][0]["versiya"], v0)  # type: ignore[index]

print("Qayta ochish:")
tek("menejer ocha olmaydi — 403", sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx_men)[0], 403)
c, r = sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx)
tek("texnolog ochdi", c, 200)
tek("qulf yechildi", isinstance(r, dict) and r.get("mes_sent"), None)
time.sleep(1.5)
tek("MES ogohlantirish oldi", versiyalar(tex)["qayta_ochilgan"], True)

print("2-yuborish:")
c, r = sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)
tek("yuborildi", c, 200)
assert isinstance(r, dict)
tek("versiya +1", r.get("version"), v0 + 1)
tek("MES manzili buyurtmaga", str(r.get("mes_url")).endswith(f"/orders/{ORDER}"), True)
v = versiyalar(tex)
tek("ogohlantirish yechildi", v["qayta_ochilgan"], False)
tek("o'zgarmagan kroyda farq yo'q", v["farq"], [])
c, p = sorov(f"{MX}/projects/{pid}", headers=mx)
assert isinstance(p, dict)
tek("MX da yangi versiya", (p.get("mes_sent") or {}).get("version"), v0 + 1)

print("Farq (xulosalar bo'yicha):")
from app.modules.integratsiya.routes import _farq  # noqa: E402

d = {"nom": "bok", "soni": 2, "L": 700, "W": 300}
a = {"listlar": 2, "nusxalar": 2, "detallar": {"a": d}, "sarf": {"LDSP": [2.0, "sheets"]}}
b = {
    "listlar": 3,
    "nusxalar": 5,
    "detallar": {"a": {**d, "soni": 4}, "b": {"nom": "polka", "soni": 1, "L": 500, "W": 200}},
    "sarf": {"LDSP": [3.0, "sheets"], "Kromka": [4.5, "m"]},
}
tek(
    "farq",
    _farq(a, b),
    [
        "Listlar: 2 → 3",
        "Detal nusxalari: 2 → 5",
        "Qo'shilgan detal: 1 ta (polka)",
        "O'zgargan detal: 1 ta (bok)",
        "Kromka: 0 → 4,5 m",
        "LDSP: 2 → 3 list",
    ],
)

print("\nMES «Kroyni olish» ham versiya yozadi:")
c, r = sorov(f"{MES}/integ/kroy/orders/{ORDER}/kroy-olish", "POST", {}, tex)
tek("olindi", c, 200)
v = versiyalar(tex)
tek("versiya +2", v["versiyalar"][0]["versiya"], v0 + 2)  # type: ignore[index]
tek("manba", v["versiyalar"][0]["manba"], "mes")  # type: ignore[index]
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
