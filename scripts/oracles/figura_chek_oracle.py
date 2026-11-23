"""MX figurali detal: paket → ParsedPart → OVAL marshruti, chek eskizi (shtrix + figurali kromka), terminal sxemasi.

Bazasiz, lokal: cd backend && .venv/Scripts/python.exe ../scripts/oracles/figura_chek_oracle.py

Figura — MX `MES_PAKET_V1` `parts[].figure`: 600x400 detalning o'ng-yuqori burchagi (100x100) kesiladi, yangi qirra
(200 mm) kromkali. Chekda kesilgan burchak shtrixlanadi, kesilmagan joy oq qoladi.
"""

import io
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from PIL import Image  # noqa: E402

from app.schemas.terminal import CutmapFigure  # noqa: E402
from app.services.giblab.mx_paket import parse_package  # noqa: E402
from app.services.labels import (  # noqa: E402
    LabelData,
    figure_removed_sides,
    figure_side_spans,
    kromka_nomi,
    render_label_png,
)

ORDER = "B-2026-901"
natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


FIGURA = {
    "size": [600, 400],
    "removed": [[[500, 0], [500, 100], [600, 100], [600, 0]]],
    "cuts": [
        {
            "path": [[500, 0], [500, 100], [600, 100]],
            "length": 200,
            "edge": {"ref": "el1", "symbol": "A", "name": "Kromka oq"},
            "source": "auto",
            "rule": "corner",
        }
    ],
    "edge_m": 0.2,
}
PAKET = {
    "package": {"format": "mebelix.kroy.mes-package", "version": 1},
    "source": {"project_id": "p1", "project_number": 1, "project_name": "figura", "mes_order_number": ORDER},
    "products": [{"mx_id": "pr1", "code": "01", "name": "Shkaf", "qty": 1}],
    "materials": [{"ref": "cs1", "kind": "sheet", "code": "", "name": "LDSP oq", "thickness": 16}],
    "edge_bands": [
        {
            "ref": "el1",
            "code": "",
            "name": "Kromka oq",
            "symbol": "A",
            "thickness": 0,
            "width": 19,
            "work_m": 2,
            "material_m": 2.1,
            "figure_work_m": 0.2,
            "figure_material_m": 0.24,
        }
    ],
    "parts": [
        {
            "mx_id": "a",
            "mx_uid": 1,
            "key": "01_001",
            "product_code": "01",
            "product_mx_id": "pr1",
            "code": "001",
            "name": "bok",
            "material_ref": "cs1",
            "length": 600,
            "width": 400,
            "thickness": 16,
            "qty_total": 1,
            "edges": {
                "t": {"ref": "el1", "symbol": "A", "name": "Kromka oq"},
                "r": {"ref": "el1", "symbol": "A", "name": "Kromka oq"},
            },
            "figure": FIGURA,
            "instances": [{"qr": f"{ORDER}_01_001"}],
        },
        {
            "mx_id": "b",
            "mx_uid": 2,
            "key": "01_002",
            "product_code": "01",
            "product_mx_id": "pr1",
            "code": "002",
            "name": "polka",
            "material_ref": "cs1",
            "length": 500,
            "width": 300,
            "thickness": 16,
            "qty_total": 1,
            "edges": {},
            "instances": [{"qr": f"{ORDER}_01_002"}],
        },
    ],
}

print("1. Paket → ParsedPart")
pk = parse_package(PAKET, ORDER)
dets = {p.code: p for pr in pk.project.products for p in pr.parts}
tek("figurali detalda figure bor", bool(dets["001"].figure), True)
tek("oval kromka metri (1 dona, egri qirra)", round(dets["001"].oval_edge_m, 3), 0.2)
tek("oddiy detalda figura yo'q", (dets["002"].figure, dets["002"].oval_edge_m), (None, 0.0))

print("1b. Marshrut: egri figurali kromka — OVAL, to'g'ri chiziqli — oddiy KROMKA")
d1 = dets["001"]  # 2 to'g'ri tomon (t, r) + 1 kromkali EGRI figurali qirra (shape yo'q, 3 nuqta)
tek("egri qirra — KROMKA 2 + OVAL", d1.kromka_marshrut(oval_post_bor=True), (2, True))
tek("OVAL posti sozlanmagan — egri qirra ham KROMKA: 3", d1.kromka_marshrut(oval_post_bor=False), (3, False))
d1.figure = dict(
    d1.figure,
    cuts=[dict(c, shape="line") for c in d1.figure["cuts"]]
    + [
        {"path": [[0, 0], [10, 10], [20, 30]], "length": 40, "edge": {"ref": "el1", "symbol": "A"}, "shape": "curve"},
        {"path": [[0, 300], [50, 400]], "length": 112, "edge": None, "shape": "line"},
    ],
)
tek("to'g'ri qirra KROMKA ga (+1), egri — OVAL", d1.kromka_marshrut(oval_post_bor=True), (3, True))
tek("OVAL metri faqat egri qirralardan", round(d1.oval_edge_m, 3), 0.04)
d1.figure = dict(d1.figure, cuts=[c for c in d1.figure["cuts"] if c.get("shape") == "line"])
tek("faqat to'g'ri qirra — OVAL yo'q, KROMKA 3", d1.kromka_marshrut(oval_post_bor=True), (3, False))
tek("figurasiz detal o'zgarmaydi", dets["002"].kromka_marshrut(oval_post_bor=True), (0, False))

print("2. Terminal sxemasi")
cf = CutmapFigure.model_validate(FIGURA)
tek("cuts[0].edge.symbol", cf.cuts[0].edge.symbol if cf.cuts[0].edge else None, "A")

print("3. Butunlay kesilgan tomon (to'g'ri kromka chizilmaydi)")
tek("burchak kesigi — hech bir tomon butunlay emas", figure_removed_sides(FIGURA), set())
yoy = {"size": [600, 400], "removed": [[[0, 0], [300, 60], [600, 0]]], "cuts": []}
tek("tepa butunlay kesilgan (yoy)", figure_removed_sides(yoy), {"t"})

print("4. Chek eskizi")


def chek(figura: dict | None) -> Image.Image:
    xs = {"groove_sides": [], "mill_sides": [], "groove_paths": [], "mill_paths": []}
    if figura:
        xs["figure"] = figura
    d = LabelData(
        qr_text=f"{ORDER}_01_001",
        part_name="bok",
        project_name="figura",
        material="LDSP oq",
        length=600,
        width=400,
        count=1,
        instance_no=None,
        edges={"t": {"mat": "Kromka oq", "symbol": "A"}, "r": {"mat": "Kromka oq", "symbol": "A"}},
        xnc_summary=xs,
        label_num=1,
        printed_at=datetime(2026, 11, 22),
    )
    return Image.open(io.BytesIO(render_label_png(d))).convert("L")


oddiy, fig = chek(None), chek(FIGURA)
farq = [
    (x, y) for y in range(oddiy.height) for x in range(oddiy.width) if oddiy.getpixel((x, y)) != fig.getpixel((x, y))
]
tek("figura chekni o'zgartiradi", len(farq) > 50, True)
# Eskiz 15x46 mm sohada (x 58.5..73.5 mm), burilgan: detal uzunligi vertikal.
# O'zgargan piksellar eskiz ichida bo'lishi kerak
mm = 8
tek("o'zgarish faqat eskiz sohasida", all(55 * mm <= x <= 76 * mm for x, _y in farq), True)
qora = sum(1 for x, y in farq if fig.getpixel((x, y)) < 128)
tek("shtrix + kromka chizig'i qora piksel qo'shadi", qora > 30, True)

print("4. Tomon kromkasi faqat qoladigan qismda, kromka nomi (2026-11-23)")


def oraliq(f, t):
    o = figure_side_spans(f, t)
    return None if o is None else [tuple(round(v) for v in q) for q in o]


burchak = {"size": [320, 199], "removed": [[[260, 199], [320, 199], [320, 139], [260, 139]]]}
tek("pastki tomon: yoygacha (0..260)", oraliq(burchak, "b"), [(0, 260)])
tek("o'ng tomon: yoygacha (0..139)", oraliq(burchak, "r"), [(0, 139)])
tek("tepa tomon butun", oraliq(burchak, "t"), [(0, 320)])
ikki = {"size": [1780, 310], "removed": [[[1750, 0], [1780, 0], [1780, 30]], [[1750, 310], [1780, 310], [1780, 280]]]}
tek("ikki burchak: o'ng tomon o'rtasi (30..280)", oraliq(ikki, "r"), [(30, 280)])
tek("figurasiz — butun tomon (None)", oraliq(None, "t"), None)
tek("!СмЧт prefiksi olib tashlanadi", kromka_nomi("!СмЧт 06-19"), "06-19")
tek("oddiy nom o'zgarmaydi", kromka_nomi("06-19 qora"), "06-19 qora")

print(f"\n{sum(natija)}/{len(natija)} OK")
sys.exit(0 if all(natija) else 1)
