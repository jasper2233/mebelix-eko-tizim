"""MX Kroy ↔ MES qoldiq ombori (K3) va webhook (K4) — ISHLAB TURGAN MES serveriga HTTP orqali, MX yuboradigan
so'rovlar aynan o'z shaklida (`MebeliX_Kroy/backend/app/services/remnant_store.py`, `mes.send_webhook`).

    1) tokensiz — 401
    2) kirim: karta 1 (2 nusxa, 2 dona) va karta 2 — bo'laklar `pending`, qty 0
    3) `map.done` karta 1, done 1 — 1 dona `available`; takror xabar — `duplicate`; boshqa op — tegmaydi
    4) qidirish: nom katta-kichik harf/bo'shliqsiz mos; boshqa material — yo'q
    5) band: P2 qo'shadi; P3 o'sha bo'lakni — 409 `conflicts` (P2 raqami bilan); `set` — faqat ro'yxatdagilar
    6) P2 kirimi o'sha bo'lakni ishlatadi — omborda qolmaydi; P2 kirimi bekor — bo'lak qaytadi
    7) MX `_norm_item` maydonlari javobda bor
Yurgizish: MES `KROY_API_TOKEN=<token>` bilan ishlab turgan bo'lsin (lokal sinov serveri, prod EMAS):
    python scripts/oracles/kroy_http_oracle.py http://localhost:8005 <token>
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = sys.argv[1].rstrip("/") + "/api/v1"
TOKEN = sys.argv[2]
MES = BASE + "/ombor/kroy"
natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


def req(method: str, url: str, body: dict | None = None, token: str | None = TOKEN) -> tuple[int, dict]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(params: dict) -> list[dict]:
    code, body = req("GET", MES + "/remnants?" + urllib.parse.urlencode(params))
    assert code == 200, (code, body)
    return body["items"]


uid = uuid.uuid4().hex[:8]
P1, P2, P3 = f"p1{uid}", f"p2{uid}", f"p3{uid}"
OP = {"id": f"op{uid}", "name": f"LDSP Kashmir Sinov {uid}", "code": "", "type": "LDSP", "thickness": 16, "linear": False}

print("1) token")
tek("tokensiz 401", req("GET", MES + "/remnants", token=None)[0], 401)

print("2) kirim")
code, out = req(
    "POST",
    MES + "/remnants/intake",
    {
        "order": {"project_id": P1, "number": 1000050, "name": "Shkaf", "mes_order_ref": None, "customer": ""},
        "op": OP,
        "sheet_area_m2": 5.0325,
        "keep_percent": 30,
        "rule_source": "type",
        "sheet_price": 650000,
        "m2_price": 129160.5,
        "pieces": [
            {"map": 1, "length": 2534, "width": 1256, "qty": 2, "copies": 2, "percent": 63.2},
            {"map": 2, "length": 900, "width": 600, "qty": 1, "copies": 1, "percent": 10.7},
        ],
        "client_pieces": [{"length": 1830, "width": 380, "qty": 1, "percent": 13.8}],
        "consumed": [],
    },
)
tek("kirim 200, IN- raqami", (code, str(out.get("intake_id", "")).startswith("IN-")), (200, True))
b1, b2 = out["ids"]
items = {d["id"]: d for d in get({"ids": f"{b1},{b2}"})}
tek("karta 1: pending, qty 0, kutmoqda 2", (items[b1]["status"], items[b1]["qty"], items[b1]["qty_pending"]), ("pending", 0, 2))

print("3) map.done webhook")
ev = {"event": "map.done", "project_id": P1, "number": 1000050, "mes_order_ref": None, "op_id": OP["id"], "map": 1, "done": 1, "copies": 2}
code, w = req("POST", BASE + "/integ/kroy/webhook", ev)
tek("qabul 201, 1 dona ochildi", (code, w.get("natija")), (201, "ochildi:1"))
tek("takror — duplicate", req("POST", BASE + "/integ/kroy/webhook", ev)[1].get("status"), "duplicate")
code, w = req("POST", BASE + "/integ/kroy/webhook", {**ev, "op_id": "boshqa-op", "done": 2})
tek("boshqa operatsiya kartasi — tegmaydi", w.get("natija"), "ochildi:0")
items = {d["id"]: d for d in get({"ids": f"{b1},{b2}"})}
tek("karta 1: available, 1 + 1 kutmoqda", (items[b1]["status"], items[b1]["qty"], items[b1]["qty_pending"]), ("available", 1, 1))
tek("karta 2 hali pending", items[b2]["status"], "pending")

print("4) qidirish")
topildi = get({"material": OP["name"].upper().replace(" ", "  "), "code": "", "type": "LDSP", "thickness": 16, "status": "available", "linear": "false"})
tek("nom harf/bo'shliqsiz mos", [d["id"] for d in topildi], [b1])
tek("boshqa material — yo'q", get({"material": "LDSP Boshqa", "status": "available"}), [])

print("5) band")
o2 = {"project_id": P2, "number": 1000051, "name": "Oshxona", "mes_order_ref": None, "customer": ""}
tek("P2 add", req("POST", MES + "/remnants/reservations", {"order": o2, "ids": [b1], "mode": "add"})[0], 200)
code, c = req("POST", MES + "/remnants/reservations", {"order": {**o2, "project_id": P3, "number": 1000052}, "ids": [b1], "mode": "add"})
tek("P3 — 409 conflicts", (code, c.get("conflicts")), (409, [{"id": b1, "order_number": "1000051"}]))
tek("kutishdagi bo'lakni band — 409", req("POST", MES + "/remnants/reservations", {"order": o2, "ids": [b2], "mode": "add"})[0], 409)
tek("holat reserved", get({"ids": str(b1)})[0]["status"], "reserved")

print("6) ishlatish va bekor")
code, out2 = req(
    "POST",
    MES + "/remnants/intake",
    {"order": o2, "op": OP, "pieces": [], "client_pieces": [], "consumed": [{"id": b1, "qty": 1, "length": 2534, "width": 1256, "area_m2": 3.18, "sale_price": 411000}]},
)
tek("P2 kirimi 200", code, 200)
d = get({"ids": str(b1)})[0]
tek("ishlatildi: qty 0, 1 dona hali kutmoqda", (d["qty"], d["qty_pending"], d["status"]), (0, 1, "pending"))
tek("bekor 200", req("POST", MES + f"/remnants/intake/{out2['intake_id']}/cancel", {})[0], 200)
tek("takror bekor — xavfsiz", req("POST", MES + f"/remnants/intake/{out2['intake_id']}/cancel", {})[0], 200)
d = get({"ids": str(b1)})[0]
tek("bo'lak qaytdi", (d["qty"], d["status"]), (1, "available"))

print("7) MX _norm_item maydonlari")
kerak = {"id", "material_code", "material_name", "length", "width", "thickness", "qty", "sheet_area_m2", "note", "source_project",
         "source_number", "created_at", "reserved_project", "reserved_number", "linear", "qty_pending", "source_map", "type",
         "status", "clean_edges"}
tek("hammasi bor", kerak - set(d), set())

print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
