"""EKO 12: qo'lda furnitura — qidiruv, jamlash, rezerv, qayta yuborish, omborga berish, huquqlar (lokal, prod EMAS).

cd backend && .venv/Scripts/python.exe ../scripts/oracles/furnitura_qolda_oracle.py <demo parol> <order_id>

Buyurtma MX ga bog'langan, MX da kesilgan, «Texnologda» yoki «Jarayonda» bo'lishi kerak (masalan B-2026-102).
Oxirida qo'shilgan qatorlar o'chiriladi (berilgani qaytariladi).
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal as D

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
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw[:300].decode(errors="replace")


def login(nom: str) -> dict[str, str]:
    body = urllib.parse.urlencode({"username": nom, "password": PAROL}).encode()
    with urllib.request.urlopen(urllib.request.Request(MES + "/login/access-token", data=body), timeout=20) as r:
        return {"Authorization": "Bearer " + json.loads(r.read())["access_token"]}


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


tex, men, skl, kas = login("texnolog"), login("menejer"), login("skladchi"), login("kassir")
url = f"{MES}/ombor/buyurtma/{ORDER}/furnitura"


def qatorlar() -> list[dict[str, str]]:
    _, r = sorov(url, h=tex)
    assert isinstance(r, dict), r
    return r["qatorlar"]


def qator(kalit: str, manba: str = "qolda") -> dict[str, str] | None:
    return next((q for q in qatorlar() if q["kalit"] == kalit and q["manba"] == manba), None)


def rezerv_qatori(kalit: str) -> dict[str, str] | None:
    _, r = sorov(f"{MES}/ombor/rezerv/{ORDER}", h=tex)
    assert isinstance(r, dict), r
    return next((ln for ln in r["lines"] if ln["tashqi_kalit"] == kalit), None)


# Oldingi to'xtab qolgan yugurishdan qolgan qatorlar
for eski in [x for x in qatorlar() if x["manba"] == "qolda"]:
    if D(eski["berilgan"]) > 0 and eski["code"]:
        sorov(f"{MES}/ombor/berish/{ORDER}/qaytar", "POST", {"kod": eski["code"], "qty": str(eski["berilgan"])}, skl)
    sorov(f"{url}/{eski['id']}", "DELETE", None, tex)

print("Qidiruv:")
_, t = sorov(f"{MES}/ombor/furnitura/qidir?q=ugolnik", h=tex)
assert isinstance(t, list) and t, t
item = next(x for x in t if D(x["erkin"]) >= 5)
print("   tanlandi:", item["code"], item["name"], item["erkin"], item["unit"])
tek("nom bo'yicha topdi", "ugolnik" in item["name"].lower(), True)
_, t2 = sorov(f"{MES}/ombor/furnitura/qidir?q={urllib.parse.quote(item['code'].lower())}", h=tex)
assert isinstance(t2, list)
tek("kod bo'yicha (kichik harf), birinchi", t2[0]["code"] if t2 else None, item["code"])
_, t3 = sorov(f"{MES}/ombor/furnitura/qidir?q=F-KM", h=tex)
tek("kromka furnitura qidiruvida yo'q", t3, [])
tek("skladchi qidira olmaydi", sorov(f"{MES}/ombor/furnitura/qidir?q=ugolnik", h=skl)[0], 403)

print("Huquq:")
tek("kassir — 403", sorov(url, "POST", {"item_id": item["item_id"], "soni": 1}, kas)[0], 403)
tek("skladchi — 403", sorov(url, "POST", {"item_id": item["item_id"], "soni": 1}, skl)[0], 403)

print("Katalogdan qo'shish:")
c, r = sorov(url, "POST", {"item_id": item["item_id"], "soni": 2}, tex)
tek("qo'shildi", c, 200)
q = qator(item["code"])
assert q is not None
tek("soni", D(q["soni"]), D(2))
tek("moslangan", q["moslangan"], True)
tek("darhol band", D(q["qoplangan"]), D(2))
tek("kim yozildi", q["kim"], "Aziz Texnolog")
sorov(url, "POST", {"item_id": item["item_id"], "soni": 1}, men)
q = qator(item["code"])
assert q is not None
tek("ikkinchi marta — jamlandi, menejer ham qo'sha oladi", D(q["soni"]), D(3))
ln = rezerv_qatori(item["code"])
assert ln is not None
tek("rezervda kerak", D(ln["kerak_qty"]), D(3))

print("Katalogsiz:")
c, r = sorov(url, "POST", {"nom": "Maxsus  dasta Sinov", "soni": 1.5}, tex)
tek("qo'shildi", c, 200)
ks = "maxsus dasta sinov"
q2 = qator(ks)
assert q2 is not None
tek("kasr soni", D(q2["soni"]), D("1.5"))
tek("moslanmagan", q2["moslangan"], False)
c, r = sorov(url, "POST", {"nom": " ", "soni": 1}, tex)
tek("bo'sh nom rad", c, 403)
tek("nol soni rad", sorov(url, "POST", {"item_id": item["item_id"], "soni": 0}, tex)[0], 422)
_, need = sorov(f"{MES}/ombor/taminot", h=men)
tek("Ta'minotga tushdi", isinstance(need, list) and any(n.get("tashqi_kalit") == ks for n in need), True)

print("Qayta yuborish o'chirmaydi:")
c, res = sorov(f"{MES}/integ/kroy/orders/{ORDER}/ochish", "POST", {}, tex)
assert c == 200 and isinstance(res, dict), (c, res)
tok = urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)["token"][0]
pid, mx = res["project_id"], {"Authorization": f"Bearer {tok}"}
_, p = sorov(f"{MX}/projects/{pid}", h=mx)
assert isinstance(p, dict)
if p.get("mes_sent"):
    assert sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx)[0] == 200
tek("yuborildi", sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)[0], 200)
q = qator(item["code"])
tek("qo'lda qator qoldi", q and D(q["soni"]), D(3))
tek("katalogsiz ham qoldi", (qator(ks) or {}).get("nom"), "Maxsus dasta Sinov")
ln = rezerv_qatori(item["code"])
tek("rezervda ham", ln and D(ln["kerak_qty"]), D(3))

print("Kroydagi bilan jamlash:")
# Ikkinchi katalog pozitsiyasi kroyga MX orqali kiradi, keyin o'sha pozitsiya qo'lda qo'shiladi
_, tx = sorov(f"{MES}/ombor/furnitura/qidir?q=polka", h=tex)
assert isinstance(tx, list) and tx, tx
item2 = next(x for x in tx if D(x["erkin"]) >= 20 and x["code"] != item["code"])
_, p = sorov(f"{MX}/projects/{pid}", h=mx)
assert isinstance(p, dict)
assert sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx)[0] == 200
op = next((o for o in p["operations"] if o["type"] == "O"), None)
if op is None:
    _, p = sorov(f"{MX}/projects/{pid}/operations", "POST", {"type": "O", "code": "FURN", "name": "Furnitura"}, mx)
    assert isinstance(p, dict)
    op = p["operations"][-1]
asl_mats = (op.get("o") or {}).get("materials") or []
mats = [*asl_mats, {"code": item2["code"], "name": item2["name"], "unit": "шт", "qty": 8, "price": 0}]
assert sorov(f"{MX}/projects/{pid}/operations/{op['id']}", "PATCH", {"o": {"materials": mats}}, mx)[0] == 200
tek("kroy yuborildi", sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)[0], 200)
c, r = sorov(url, "POST", {"item_id": item2["item_id"], "soni": 2}, tex)
assert isinstance(r, dict)
print("   ogoh:", r.get("ogoh"))
tek("ogohlantirishda kroydagi soni", "8" in str(r.get("ogoh")) and "10" in str(r.get("ogoh")), True)
ln = rezerv_qatori(item2["code"])
tek("rezervda jami 10", ln and D(ln["kerak_qty"]), D(10))
tek("bitta rezerv qatori", ln and D(ln["qoplangan_qty"]), D(10))
q4 = qator(item2["code"])
assert q4 is not None
tek("qo'lda qator o'chdi", sorov(f"{url}/{q4['id']}", "DELETE", None, tex)[0], 200)
ln = rezerv_qatori(item2["code"])
tek("kroydagisi qoldi", ln and D(ln["kerak_qty"]), D(8))
assert sorov(f"{MX}/projects/{pid}/mes-reopen", "POST", {}, mx)[0] == 200
assert sorov(f"{MX}/projects/{pid}/operations/{op['id']}", "PATCH", {"o": {"materials": asl_mats}}, mx)[0] == 200
tek("kroy tiklandi", sorov(f"{MX}/projects/{pid}/mes-send", "POST", {}, mx)[0], 200)

print("Omborga berish va chegaralar:")
c, r = sorov(f"{MES}/ombor/berish/{ORDER}/skan", "POST", {"kod": item["code"], "qty": 2}, skl)
tek("omborchi 2 berdi", c, 200)
if c != 200:
    print("   ", r)
q = qator(item["code"])
assert q is not None
tek("berilgan", D(q["berilgan"]), D(2))
c, r = sorov(f"{url}/{q['id']}", "PATCH", {"soni": 1}, tex)
tek("berilgandan kam qilib bo'lmaydi", c, 403)
print("   xabar:", isinstance(r, dict) and r.get("detail"))
tek("o'chirib bo'lmaydi", sorov(f"{url}/{q['id']}", "DELETE", None, tex)[0], 403)
tek("berilganga teng — mumkin", sorov(f"{url}/{q['id']}", "PATCH", {"soni": 2}, tex)[0], 200)
tek("ko'paytirish — mumkin", sorov(f"{url}/{q['id']}", "PATCH", {"soni": 4}, tex)[0], 200)

print("Xato ko'p kiritilgani qaytariladi:")
c, r = sorov(f"{MES}/ombor/berish/{ORDER}/qaytar", "POST", {"kod": item["code"], "qty": 3}, skl)
tek("berilgandan ko'p qaytmaydi", c, 400)
c, r = sorov(f"{MES}/ombor/berish/{ORDER}/qaytar", "POST", {"kod": item["code"], "qty": 1}, skl)
tek("1 qaytdi (ortiqcha bo'lmasa ham)", c, 200)
q = qator(item["code"])
assert q is not None
tek("berilgan kamaydi", D(q["berilgan"]), D(1))
tek("endi kamaytirsa bo'ladi", sorov(f"{url}/{q['id']}", "PATCH", {"soni": 1}, tex)[0], 200)

print("Tozalash:")
tek("qaytarildi", sorov(f"{MES}/ombor/berish/{ORDER}/qaytar", "POST", {"kod": item["code"], "qty": 1}, skl)[0], 200)
q = qator(item["code"])
assert q is not None
tek("o'chirildi", sorov(f"{url}/{q['id']}", "DELETE", None, tex)[0], 200)
q2 = qator(ks)
assert q2 is not None
tek("katalogsiz o'chirildi", sorov(f"{url}/{q2['id']}", "DELETE", None, men)[0], 200)
tek("ro'yxatda yo'q", qator(item["code"]), None)
tek("rezervdan ham chiqdi", rezerv_qatori(ks), None)
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
