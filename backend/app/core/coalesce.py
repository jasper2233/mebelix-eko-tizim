"""Hamma uchun bir xil og'ir o'qish — ishchida bir vaqtda BITTA hisob.

Tsexdagi har skan WS orqali hamma TABLO ekraniga boradi va ular matritsani ko'pincha deyarli
bir paytda so'raydi (prod, 2026-09-27: bir nechta so'rovli 29 to'dadan 17 tasida 1–13 ms farq). Har so'rov o'zi
hisoblasa bir ishchida 2–4 ta bir xil hisob ustma-ust tushib, event loop'ni 200–650 ms
band qilardi — o'sha paytda shu ishchiga kelgan chek va skan so'rovlari kutadi.

Qoida: hisob ketayotganda kelgan so'rovlar o'sha hisobga QO'SHILMAYDI — keyingi bitta
hisobni birga kutadi, u ular kelgandan KEYIN boshlanadi. Demak javob hech qachon so'rov
kelishidan oldingi holatni ko'rsatmaydi: skandan keyin so'ragan ekran o'sha skanni ko'radi.
Oddiy «tayyor natijani ulash» yoki TTL kesh buni kafolatlamaydi — ekran skandan oldingi
matritsani olib, keyingi pollgacha (60 s) eski qolardi.

Prodda A/B (ishchiga o'xshash jarayon, 3 takror x 55 so'rov, 1/2/4 talik to'dalar):
>=200 ms muzlash 20 -> 7, javob p95 ~800 -> ~500 ms, eski javob 0. Ikki ishchi uchun
umumiy (Redis) hisob kerak emas: ikki jarayon bir soniyada hisoblaganda muzlash yakka
hisobdagidek chiqdi (loop max 195 va 187 ms).

Jonli trafik (2026-09-27..10-03) to'dalardan iborat emas ekan: 1567 muzlashdan 1370 tasida
ishchida BITTA matritsa so'rovi bo'lgan, ya'ni bu mexanizm kam hollarda ishlaydi va muzlashlar
bitta hisobning o'zidan edi — u `tablo.py: build_tablo_matrix` da yengillashtirilgan. Boshqa
ishchida ham hisob ketayotgan bo'lsa so'rov sekinroq (p50 317 -> 364 ms, 6 083 so'rov).
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Coalesced(Generic[T]):
    """`await coalesced()` — `fn()` natijasi; bir vaqtda ko'pi bilan bitta `fn()` ishlaydi, hisob
    davomida kelganlar keyingisini baham ko'radi. Xato o'sha hisobni kutganlarning hammasiga
    boradi, keyingi chaqiruv yangidan hisoblaydi. Kutuvchi bekor qilinsa (mijoz uzildi) hisob
    va boshqa kutuvchilar davom etadi."""

    def __init__(self, fn: Callable[[], Awaitable[T]]) -> None:
        self._fn = fn
        #: Keyingi (hali BOSHLANMAGAN) hisobni kutayotganlarning umumiy natijasi
        self._pending: asyncio.Future[T] | None = None
        #: Hisoblarni ketma-ket bajaruvchi vazifa; havola saqlanadi — aks holda GC uni yig'ib yuborishi mumkin
        self._runner: asyncio.Task[None] | None = None

    async def __call__(self) -> T:
        if self._pending is None:
            self._pending = asyncio.get_running_loop().create_future()
        fut = self._pending
        if self._runner is None:
            self._runner = asyncio.create_task(self._run())
        return await asyncio.shield(fut)

    async def _run(self) -> None:
        try:
            while self._pending is not None:
                # Shu paytgacha kelganlar — shu hisobga; bundan keyin keladigani yangi `_pending` ochadi
                fut, self._pending = self._pending, None
                try:
                    result = await self._fn()
                except asyncio.CancelledError:  # ishchi to'xtayapti — kutuvchilar osilib qolmasin
                    fut.cancel()
                    # Keyingi hisobni kutayotganlar ham: uni endi hech kim boshlamaydi
                    if self._pending is not None:
                        self._pending.cancel()
                        self._pending = None
                    raise
                except Exception as e:  # noqa: BLE001 — kutuvchilarga uzatiladi, har biri o'zi ko'taradi
                    fut.set_exception(e)
                else:
                    fut.set_result(result)
        finally:
            self._runner = None
