"""Yig'uvchi uchun OCHIQ 3D sahifa — MESdagi YAGONA autentifikatsiyasiz modul.

Havolani texnolog beradi, uni usta ham, mijoz ham ochadi va kim ekani
bilinmaydi (ustalar hech qayerda qayd etilmaydi). Shu sababli himoya
«imkoniyat-havola» (capability URL) naqshiga quriladi:

* Manzilda buyurtma raqami YO'Q — faqat `uuid4` token (122 bit). Raqam bo'lsa
  havolani olgan odam uni o'zgartirib butun sexning buyurtmalarini ochardi.
* Har so'rov TOKEN bo'yicha buyurtmani topadi; `order_id` bu modulga hech
  qachon tashqaridan kirmaydi, ya'ni boshqa buyurtmaga o'tish yo'li yo'q.
* Yopilgan token 404 qaytaradi (403 emas): «bunday buyurtma bormi» degan
  savolga ham javob bermaymiz.
* Noto'g'ri token urinishlari IP bo'yicha cheklanadi — tokenni taxmin qilib
  bo'lmasa ham, skanerlash shovqinini to'xtatadi.

Javoblarda mijoz nomi, telefoni, narx va ichki holat YO'Q: faqat buyurtma
raqami, mahsulot nomi va geometriya.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.config import upload_root
from app.core.exceptions import NotFoundException
from app.core.utils.rate_limit import RateLimit
from app.models import Order, OrderFile
from app.models.enums import FileKind
from app.schemas.bazis import PublicOrder, PublicProduct

#: Tokenni taxmin qilishga qarshi: faqat MUVAFFAQIYATSIZ urinish hisoblanadi.
_SHARE_RATE_LIMIT = RateLimit(limit=60, period=300)

router = APIRouter(prefix="/public", tags=["public"], dependencies=[Depends(_SHARE_RATE_LIMIT)])

#: Qidiruv tizimlari ochiq havolani indekslamasin; havolani faqat uni olgan
#: odam bilishi kerak. `no-cache`: model qayta yuklanganda token va manzil
#: o'zgarmaydi, fayl esa o'sha joyda yangilanadi — brauzer eskisini taxminiy
#: "yangilik" bilan qayta ishlatmasin, har safar ETag bo'yicha so'rasin.
_HEADERS = {"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer", "Cache-Control": "no-cache"}


async def _order(db: SessionDep, request: Request, token: str) -> Order:
    order = (
        await db.execute(
            select(Order).where(
                Order.share_token == token,
                Order.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if order is None:
        await _SHARE_RATE_LIMIT.hit(request)
        raise NotFoundException("Havola topilmadi yoki yopilgan.")
    return order


async def _models(db: SessionDep, order_id: int) -> list[OrderFile]:
    return list(
        (
            await db.execute(
                select(OrderFile)
                .where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.BAZIS,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
                .order_by(OrderFile.id)
            )
        )
        .scalars()
        .all()
    )


async def _fayl(db: SessionDep, request: Request, token: str, code: str, kengaytma: str) -> Path:
    """Mahsulot faylini topadi. Yo'l DBdagi qatordan olinadi, manzildagi `code`
    dan EMAS — shu sababli `..` bilan katalogdan chiqib bo'lmaydi."""
    order = await _order(db, request, token)
    row = next((r for r in await _models(db, order.id) if r.meta.get("product_code") == code), None)
    if row is None:
        raise NotFoundException("Model topilmadi.")
    yol = (upload_root() / row.path).with_suffix(kengaytma)
    if not yol.is_file():
        raise NotFoundException("Model topilmadi.")
    return yol


@router.get("/3d/{token}", response_model=PublicOrder, operation_id="read_public_order")
async def read_public_order(db: SessionDep, request: Request, token: str, response: Response) -> PublicOrder:
    """Havoladagi buyurtma: raqami va 3D modeli bor mahsulotlar."""
    order = await _order(db, request, token)
    response.headers.update(_HEADERS)
    return PublicOrder(
        number=order.number,
        products=[
            PublicProduct(
                code=str(r.meta.get("product_code") or ""),
                name=str(r.meta.get("product_name") or ""),
                panels=int(r.meta.get("panels") or 0),
            )
            for r in await _models(db, order.id)
        ],
    )


@router.get("/3d/{token}/{code}/model", operation_id="read_public_model")
async def read_public_model(db: SessionDep, request: Request, token: str, code: str) -> FileResponse:
    """Mahsulotning brauzerga tayyor modeli (yuklashda yasalgan JSON)."""
    return FileResponse(await _fayl(db, request, token, code, ".json"), media_type="application/json", headers=_HEADERS)


@router.get("/3d/{token}/{code}/thumb", operation_id="read_public_thumb")
async def read_public_thumb(db: SessionDep, request: Request, token: str, code: str) -> FileResponse:
    """Mahsulot kartochkasi rasmi: Bazis eskizi, foni shaffof, kesilgan va kattalashtirilgan."""
    return FileResponse(await _fayl(db, request, token, code, ".png"), media_type="image/png", headers=_HEADERS)
