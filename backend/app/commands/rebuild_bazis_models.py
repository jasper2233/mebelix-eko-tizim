"""Saqlangan Bazis modellarining brauzer JSON'ini joriy parser bilan qayta yasaydi.

Run: python -m app.commands.rebuild_bazis_models

Model JSON'i yuklashda BIR MARTA yasaladi (`orders/bazis.py`), ya'ni parser
o'zgargach (masalan, bazischining o'lchamlari — `d` — yoki ilgak kosasini
eshikka bog'lash) avval yuklangan modellar eskicha qoladi. `.b3d` ning o'zi
diskda saqlanadi — texnolog qayta yuklashi shart emas, shu buyruq kifoya.
Idempotent: o'zgarmagan fayl qayta yozilmaydi.
"""

import logging

from app.core.config import upload_root
from app.services.bazis import BazisParseError, dump_model, read_b3d

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    yangilandi = bir_xil = xato = 0
    for b3d in sorted((upload_root() / "bazis").glob("*/*.b3d")):
        model = b3d.with_suffix(".json")
        try:
            yangi = dump_model(read_b3d(b3d.read_bytes()))
        except (BazisParseError, ValueError) as exc:
            # Yuklashda o'tgan fayl bu yerda yiqilsa — parser regressiyasi: eski
            # JSON o'z joyida qoladi, fayl nomi logda
            logger.warning("%s: %s", b3d, exc)
            xato += 1
            continue
        if model.exists() and model.read_bytes() == yangi:
            bir_xil += 1
            continue
        model.write_bytes(yangi)
        yangilandi += 1
    logger.info("Bazis modellari: %d yangilandi, %d o'zgarmagan, %d xato", yangilandi, bir_xil, xato)


if __name__ == "__main__":
    main()
