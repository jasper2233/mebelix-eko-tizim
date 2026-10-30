"""MX «Раскроечные станки» + MES SSO (A variant): stanok standarti faqat xodimning MES paroli bilan. Lokal: MES 8005, MX klon 8010.

cd backend && uv run python ../scripts/oracles/mx_parol_oracle.py <demo parol>   (lokal sinov, prod EMAS)
"""

import json
import sys
import urllib.error
import urllib.request

from app.models import User
from app.models.enums import UserRole
from app.modules.integratsiya import kroy

MX = "http://localhost:8010/api"
MES = "http://localhost:8005/api/v1/integ/kroy/parol-tekshir"
PAROL = sys.argv[1]
natija: list[bool] = []


def so(method: str, url: str, tok: str, body: object = None) -> tuple[int, object]:
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


def user(username: str, rol: UserRole) -> str:
    return kroy.sso_token(
        User(
            username=username,
            name=username,
            role=rol,
            hashed_password="",
            phone="+998900000000",
        )
    )


tok = user("texnolog", UserRole.TEXNOLOG)
s, d = so("GET", MX + "/saw-machines", tok)
assert isinstance(d, dict), d
tek("SSO rejimida parol so'raladi", d["password_required"], True)
m = d["machines"][0]
saqla = {"machine": {"id": m["id"], "name": m["name"], "cut": m["cut"]}}
tek("parolsiz — rad", so("POST", MX + "/saw-machines/save", tok, saqla)[0], 403)
tek(
    "noto'g'ri parol — rad",
    so("POST", MX + "/saw-machines/save", tok, {**saqla, "password": "xato"})[0],
    403,
)
s, d = so("POST", MX + "/saw-machines/save", tok, {**saqla, "password": PAROL})
tek(
    "to'g'ri MES paroli — saqlandi, kim yozgani",
    (s, isinstance(d, dict) and d["machines"][0]["updated_by"]),
    (200, "texnolog"),
)
tek(
    "boshqa xodim nomidan (direktor tokeni, texnolog paroli) — rad",
    so(
        "POST",
        MX + "/saw-machines/save",
        user("direktor", UserRole.DIRECTOR),
        {**saqla, "password": "xato2"},
    )[0],
    403,
)
tek(
    "MES: tokensiz — 401/403",
    so("POST", MES, "", {"login": "texnolog", "password": PAROL})[0] in (401, 403),
    True,
)
tek(
    "MES: telefon bilan login — ok emas (faqat foydalanuvchi nomi)",
    so(
        "POST",
        MES,
        "lokal-sinov-kroy-token",
        {"login": "+998900009006", "password": PAROL},
    )[1],
    {"ok": False},
)
# login bo'yicha cheklov: 5 xato → 429, boshqa login ishlayveradi
for _ in range(6):
    s, _d = so(
        "POST", MES, "lokal-sinov-kroy-token", {"login": "menejer", "password": "xato"}
    )
tek("MES: 5 xatodan keyin shu login — 429", s, 429)
tek(
    "MES: boshqa login to'silmagan",
    so("POST", MES, "lokal-sinov-kroy-token", {"login": "texnolog", "password": PAROL})[
        1
    ],
    {"ok": True},
)
tek(
    "MX: MES 429 → foydalanuvchiga 429",
    so(
        "POST",
        MX + "/saw-machines/save",
        user("menejer", UserRole.DIRECTOR),
        {**saqla, "password": PAROL},
    )[0],
    429,
)
print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")
