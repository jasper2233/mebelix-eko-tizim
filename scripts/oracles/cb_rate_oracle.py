"""Markaziy bank dollar kursi (docs/14 §8.1) — o'qish, kesh va bank javob bermagani.

`services/cb_rate.py` ning HAQIQIY funksiyalari HAQIQIY Redis bilan. Bankning o'ziga bitta
marta chiqiladi (tarmoq bo'lmasa o'sha tekshiruv o'tkazib yuboriladi), qolgani soxta javob
bilan — bank javobining har xil buzuq shakllariga qanday munosabat qilishini tekshirish uchun.

Yurgizish (lokal, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/cb_rate_oracle.py
"""

import asyncio
import json
from decimal import Decimal

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.services import cb_rate as M

HAQIQIY = [
    {
        "id": 1, "Code": "840", "Ccy": "USD", "CcyNm_UZ": "AQSH dollari",
        "Nominal": "1", "Rate": "12055.90", "Diff": "44.25", "Date": "17.10.2026",
    }
]


async def tozala() -> None:
    async with AsyncRedis.from_url(settings.REDIS_URL) as r:
        await r.delete(M.CACHE_KEY, M.FAIL_KEY)


async def main() -> None:
    natija: list[tuple[str, object, object]] = []

    # --- 1. Javobni o'qish (sof funksiya)
    k = M._parse(HAQIQIY)  # noqa: SLF001
    natija.append(("bank javobidan kurs, sana va farq",
                   (k.rate, k.date, k.diff) if k else None,
                   (Decimal("12055.90"), "17.10.2026", Decimal("44.25"))))
    natija.append(("bitta lug'at ham (ro'yxatsiz) o'qiladi",
                   (M._parse(HAQIQIY[0]) or M.CbRate(Decimal(0), "", None)).rate,  # noqa: SLF001
                   Decimal("12055.90")))

    buzuq = [
        ("bo'sh ro'yxat", []),
        ("boshqa valyuta", [{**HAQIQIY[0], "Ccy": "EUR"}]),
        ("kurs yo'q", [{k2: v for k2, v in HAQIQIY[0].items() if k2 != "Rate"}]),
        ("kurs son emas", [{**HAQIQIY[0], "Rate": "—"}]),
        ("kurs manfiy", [{**HAQIQIY[0], "Rate": "-5"}]),
        # Nominal 1 dan boshqa bo'lsa kurs BITTA dollarga tegishli emas
        ("nominal 100", [{**HAQIQIY[0], "Nominal": "100"}]),
        ("umuman boshqa narsa", {"xato": True}),
    ]
    for nom, xom in buzuq:
        natija.append((f"buzuq javob tashlanadi — {nom}", M._parse(xom), None))  # noqa: SLF001

    # --- 2. Kesh: bank BIR marta so'raladi
    await tozala()
    chaqirildi = {"n": 0}
    asl = M._fetch  # noqa: SLF001

    def soxta():
        chaqirildi["n"] += 1
        return M._parse(HAQIQIY)  # noqa: SLF001

    M._fetch = soxta  # noqa: SLF001
    try:
        birinchi = await M.cb_usd()
        ikkinchi = await M.cb_usd()
        natija.append(("ikkala chaqiruv ham kursni qaytardi",
                       (birinchi.rate if birinchi else None, ikkinchi.rate if ikkinchi else None),
                       (Decimal("12055.90"), Decimal("12055.90"))))
        natija.append(("bankka FAQAT bir marta chiqildi", chaqirildi["n"], 1))
        async with AsyncRedis.from_url(settings.REDIS_URL) as r:
            keshda = json.loads(await r.get(M.CACHE_KEY))
            umr = await r.ttl(M.CACHE_KEY)
        natija.append(("kesh qiymati", keshda["rate"], "12055.90"))
        natija.append(("kesh muddati qo'yilgan", 0 < umr <= M.CACHE_TTL, True))

        # --- 3. Bank javob bermasa: `None`, lekin qayta-qayta urinmaydi
        await tozala()

        def yiqil():
            chaqirildi["n"] += 1
            raise TimeoutError("bank javob bermadi")

        M._fetch = yiqil  # noqa: SLF001
        oldin = chaqirildi["n"]
        natija.append(("bank javob bermasa None", await M.cb_usd(), None))
        natija.append(("ikkinchi so'rov bankka chiqmaydi (salbiy kesh)",
                       (await M.cb_usd(), chaqirildi["n"] - oldin), (None, 1)))

        # --- 4. Bank tiklandi: salbiy kesh muddati o'tgach qayta so'raladi
        async with AsyncRedis.from_url(settings.REDIS_URL) as r:
            await r.delete(M.FAIL_KEY)
        M._fetch = soxta  # noqa: SLF001
        tiklandi = await M.cb_usd()
        natija.append(("bank tiklangach kurs qaytadi",
                       tiklandi.rate if tiklandi else None, Decimal("12055.90")))
    finally:
        M._fetch = asl  # noqa: SLF001
        await tozala()

    # --- 5. Haqiqiy bank (tarmoq bo'lsa)
    haqiqiy = await M.cb_usd()
    if haqiqiy is None:
        print("  (tarmoq yo'q — bankning o'zi tekshirilmadi)")
    else:
        natija.append(("haqiqiy bank kursi mantiqiy oraliqda",
                       Decimal(5000) < haqiqiy.rate < Decimal(100000), True))
        natija.append(("haqiqiy sana kun.oy.yil ko'rinishida",
                       len(haqiqiy.date.split(".")) == 3, True))
    await tozala()

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
