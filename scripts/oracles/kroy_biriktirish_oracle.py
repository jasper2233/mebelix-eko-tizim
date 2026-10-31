"""EKO 12: MES siz ochilgan MX loyihasini buyurtmaga biriktirish, kroyni tozalash (MES 8005 + MX klon 8010, lokal).

cd backend && .venv/Scripts/python.exe ../scripts/oracles/kroy_biriktirish_oracle.py <demo parol>

Yangi sinov buyurtmalari va MX loyihalari yaratadi; oxirida navbat qo'lda yuborilmaydi — ajratish xabari tekshiriladi.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

MES = "http://localhost:8005/api/v1"
MX = "http://localhost:8010/api"
PAROL = sys.argv[1]
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


tex, men = login("texnolog"), login("menejer")


def yangi_buyurtma(izoh: str) -> dict[str, object]:
    _, klientlar = sorov(f"{MES}/clients/?limit=5", h=men)
    assert isinstance(klientlar, dict | list), klientlar
    k = (klientlar["data"] if isinstance(klientlar, dict) else klientlar)[0]
    c, o = sorov(
        f"{MES}/orders/", "POST", {"client_id": k["id"], "priority": "medium", "amount": "1000000", "notes": izoh}, men
    )
    assert c == 201 and isinstance(o, dict), (c, o)
    c, _ = sorov(f"{MES}/orders/{o['id']}/confirm", "POST", {}, men)
    assert c == 200, c
    return {**o, "mijoz": k["full_name"]}


# MX token: bog'langan sinov buyurtmasidan (MES orqali kirgan xodim)
b0 = yangi_buyurtma("Biriktirish oracle: token")
c, res = sorov(f"{MES}/integ/kroy/orders/{b0['id']}/ochish", "POST", {}, tex)
assert c == 200 and isinstance(res, dict), (c, res)
tok = urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)["token"][0]
mx = {"Authorization": f"Bearer {tok}"}
c, res = sorov(f"{MES}/integ/kroy/orders/{b0['id']}/ochish", "POST", {}, men)
assert isinstance(res, dict)
mx_men = {"Authorization": "Bearer " + urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)["token"][0]}


def mustaqil_loyiha(nom: str, customer: str = "", qty: int = 1) -> str:
    """MX da MES siz ochilgan, kesilgan loyiha."""
    _, p = sorov(f"{MX}/projects", "POST", {"name": nom, "customer": customer}, mx)
    assert isinstance(p, dict), p
    pid = p["id"]
    _, p = sorov(
        f"{MX}/projects/{pid}/operations", "POST", {"type": "CS", "code": "M-LD-001-01", "name": "LDSP Oq 16"}, mx
    )
    assert isinstance(p, dict)
    oid = p["operations"][-1]["id"]
    sorov(
        f"{MX}/projects/{pid}/operations/{oid}/parts",
        "POST",
        [{"name": "bok", "length": 700, "width": 300, "qty": qty}],
        mx,
    )
    c, _ = sorov(f"{MX}/projects/{pid}/operations/{oid}/optimize?quality=fast", "POST", {}, mx)
    assert c == 200, c
    return pid


print("Ro'yxat:")
b1 = yangi_buyurtma("Biriktirish oracle: 1")
pid = mustaqil_loyiha("Mustaqil 1", str(b1["mijoz"]), 2)
c, royxat = sorov(f"{MX}/projects/{pid}/mes-orders", h=mx)
tek("ochildi", c, 200)
assert isinstance(royxat, list)
tek("yangi buyurtma bor", any(o["id"] == b1["id"] for o in royxat), True)
c, q = sorov(f"{MX}/projects/{pid}/mes-orders?q={b1['number']}", h=mx)
tek("raqam bo'yicha qidiruv", isinstance(q, list) and [o["number"] for o in q], [b1["number"]])
tek("menejer ro'yxatni ko'rmaydi", sorov(f"{MX}/projects/{pid}/mes-orders", h=mx_men)[0], 403)
_, ya = sorov(f"{MES}/orders/?status=production&limit=1", h=men)
tek("xizmat tokenisiz yo'q", sorov(f"{MES}/integ/kroy/buyurtmalar", h=tex)[0] in (401, 403), True)

print("Tasdiq:")
tanlov = {"order_id": b1["id"], "order_number": b1["number"]}
c, t = sorov(f"{MX}/projects/{pid}/mes-check", "POST", tanlov, mx)
tek("tekshirildi", c, 200)
assert isinstance(t, dict), t
tek("buyurtma", t["buyurtma"]["number"], b1["number"])
tek("nusxalar", t["nusxalar"], 2)
tek("ogohlantirish yo'q", t["ogoh"], [])
_, p = sorov(f"{MX}/projects/{pid}", h=mx)
assert isinstance(p, dict)
tek("hali bog'lanmagan", p["mes_order_ref"], None)
pid2 = mustaqil_loyiha("Boshqa mijoz", "Umuman boshqa odam")
_, t2 = sorov(f"{MX}/projects/{pid2}/mes-check", "POST", tanlov, mx)
assert isinstance(t2, dict)
tek("mijoz farqi aytiladi", any("Umuman boshqa odam" in w for w in t2["ogoh"]), True)

print("Yuborish:")
c, r = sorov(f"{MX}/projects/{pid}/mes-send", "POST", tanlov, mx)
tek("qabul qilindi", c, 200)
assert isinstance(r, dict), r
tek("buyurtma", r.get("order_number"), b1["number"])
_, p = sorov(f"{MX}/projects/{pid}", h=mx)
assert isinstance(p, dict)
tek("MX da bog'landi", p["mes_order_ref"], b1["number"])
tek("MX qulflandi", (p.get("mes_sent") or {}).get("version"), 1)
_, o = sorov(f"{MES}/orders/{b1['id']}", h=tex)
assert isinstance(o, dict)
tek("MES da kroy", str(o["project_uuid"]), f"mx:{pid}")
_, k = sorov(f"{MES}/ombor/rezerv/{b1['id']}", h=tex)
tek("rezerv qurildi", isinstance(k, dict) and len(k["lines"]) >= 1, True)

print("Bog'langan loyiha boshqa buyurtmaga ketmaydi:")
b2 = yangi_buyurtma("Biriktirish oracle: 2")
tek(
    "rad",
    sorov(f"{MX}/projects/{pid}/mes-check", "POST", {"order_id": b2["id"], "order_number": b2["number"]}, mx)[0],
    409,
)

print("Boshqa kroy ustiga:")
_, t3 = sorov(f"{MX}/projects/{pid2}/mes-check", "POST", tanlov, mx)
assert isinstance(t3, dict)
tek("almashishi aytiladi", any("almashadi" in w for w in t3["ogoh"]), True)
tek("eski loyiha ajralishi aytiladi", any("ajratiladi" in w for w in t3["ogoh"]), True)
c, r = sorov(f"{MX}/projects/{pid2}/mes-send", "POST", tanlov, mx)
tek("o'tdi", c, 200)
_, o = sorov(f"{MES}/orders/{b1['id']}", h=tex)
assert isinstance(o, dict)
tek("buyurtmada yangi loyiha", o["project_uuid"], f"mx:{pid2}")

print("Uzatilgan buyurtmaga biriktirilmaydi:")
c, _ = sorov(f"{MES}/ombor/rezerv/{b2['id']}/qayta", "POST", {}, tex)
pid3 = mustaqil_loyiha("Uzatilganga")
_, ochiq = sorov(f"{MX}/projects/{pid3}/mes-orders", h=mx)
assert isinstance(ochiq, list)
tek("D-2026-203 (Jarayonda) ro'yxatda yo'q", any(x["number"] == "D-2026-203" for x in ochiq), False)
c, r = sorov(f"{MX}/projects/{pid3}/mes-send", "POST", {"order_id": 7, "order_number": "D-2026-203"}, mx)
tek("yuborish rad", c, 409)
_, p = sorov(f"{MX}/projects/{pid3}", h=mx)
assert isinstance(p, dict)
tek("rad etilganda bog'lanmadi", p["mes_order_ref"], None)

print("Tozalash:")
tek("menejer tozalay olmaydi", sorov(f"{MES}/integ/kroy/orders/{b1['id']}/kroy-tozala", "POST", {}, men)[0], 403)
c, _ = sorov(f"{MES}/integ/kroy/orders/{b1['id']}/kroy-tozala", "POST", {}, tex)
tek("tozalandi", c, 200)
_, o = sorov(f"{MES}/orders/{b1['id']}", h=tex)
assert isinstance(o, dict)
tek("kroy yo'q", o["project_uuid"], None)
tek("sarf yo'q", o["material_usage"], [])
_, v = sorov(f"{MES}/integ/kroy/orders/{b1['id']}/versiyalar", h=tex)
tek("versiya paneli bo'sh", isinstance(v, dict) and v["versiyalar"], [])
_, ch = sorov(f"{MX}/projects/{pid3}/mes-check", "POST", {"order_id": b1["id"], "order_number": b1["number"]}, mx)
tek("yana tanlasa bo'ladi", isinstance(ch, dict) and ch["buyurtma"]["kroy_bor"], False)
tek("ikkinchi marta — rad", sorov(f"{MES}/integ/kroy/orders/{b1['id']}/kroy-tozala", "POST", {}, tex)[0], 403)
tek("MX detach", sorov(f"{MX}/projects/{pid2}/mes-detach", "POST", {}, mx)[0], 200)
_, p = sorov(f"{MX}/projects/{pid2}", h=mx)
assert isinstance(p, dict)
tek("loyiha yana mustaqil", (p["mes_order_ref"], p.get("mes_sent")), (None, None))
c, r = sorov(f"{MX}/projects/{pid2}/mes-send", "POST", {"order_id": b1["id"], "order_number": b1["number"]}, mx)
tek("qayta biriktirildi", c, 200)
_, o = sorov(f"{MES}/orders/{b1['id']}", h=tex)
assert isinstance(o, dict)
tek("buyurtmada kroy", o["project_uuid"], f"mx:{pid2}")
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
