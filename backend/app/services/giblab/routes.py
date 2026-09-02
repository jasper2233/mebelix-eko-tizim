"""Qo'lda chizilgan marshrutni qurish — qoidaning YAGONA nusxasi.

Ikki chaqiruvchisi bor: matritsadagi tahrir (`orders.matrix._set_custom_route`) va
qayta yuklashdan keyingi tiklash (`ingest.restore_custom_routes`). Qoida ish haqi va
skan sonini belgilaydi (KROMKA birinchi o'tishda qirralar soni marta skanlanadi,
oxiriga qadoqlash/TMO dumi qo'shiladi), shuning uchun u ikki nusxada saqlanganda
bittasiga tegilishi ikkinchisidan JIMGINA ajralib ketishga olib kelardi.
"""

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Part, PartRoute, Post
from app.models.enums import PostCode, RouteSource

from .models import PROCESS_POSTS, TAIL_CODES, ParseError

#: posts lug'ati ingest'da str, marshrut qurishda PostCode kalitli
_K = TypeVar("_K", str, PostCode)


def resolve_post(posts: dict[_K, Post], post_code: _K) -> Post:
    """Postni kodi bo'yicha topadi; sozlanmagan bo'lsa tushunarli xato beradi."""
    post = posts.get(post_code)
    if post is None:
        raise ParseError(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
    return post


def build_manual_route(
    db: AsyncSession,
    order_id: int,
    part: Part,
    codes: list[int],
    posts: dict[PostCode, Post],
    *,
    packaging: bool,
    start_seq: int = 1,
    seen: set[PostCode] | None = None,
    with_tail: bool = True,
) -> None:
    """`codes` bo'yicha MANUAL marshrut qadamlarini (kerak bo'lsa dumni ham) sessiyaga qo'shadi.

    Ro'yxat TARTIBLI va kod takrorlanishi mumkin ([3, 6, 3] — kromkaga qaytish).
    `seen` — detalda ALLAQACHON mavjud postlar (standart detalga qo'shimcha qadam
    chizilganda fayldan kelgan qadamlar): KROMKA birinchi o'tishmi — shunga qarab hal
    bo'ladi. `with_tail=False` — dum joyida turibdi (standart detal), qayta qo'shilmaydi.
    Post sozlanmagan bo'lsa `ParseError` uchadi.
    """
    edge_count = len(part.edges) or 1
    seen = set() if seen is None else seen
    for offset, code in enumerate(codes):
        post_code = PROCESS_POSTS[code]
        # OVAL bu yerda YO'Q: oval kromkada detal bitta o'tishda ishlanadi — bitta skan.
        # KROMKA esa har qirrani alohida yopishtiradi, shuning uchun birinchi o'tishda
        # qirralar soni marta skanlanadi (takror kelsa — bitta).
        first_edge_pass = post_code == PostCode.KROMKA and post_code not in seen
        seen.add(post_code)
        per_instance = edge_count if first_edge_pass else 1
        db.add(
            PartRoute(
                order_id=order_id,
                part_id=part.id,
                post_id=resolve_post(posts, post_code).id,
                seq=start_seq + offset,
                process_code=code,
                source=RouteSource.MANUAL,
                per_instance=per_instance,
                total_required=part.count * per_instance,
            )
        )
    # Qadoqlash va TMO — texnolog tanlamaydi. Qadoqlashni anketadagi bayroq qo'shadi,
    # TMO esa HAR doim oxirgi qadam bo'ladi.
    # Biriktirilgan MAYDA detalga dum QO'SHILMAYDI: u asosiy detalga yopishib yaxlit
    # buyumga aylanadi, ya'ni alohida qadoqlanmaydi va TMO ga alohida kirmaydi —
    # aks holda qadoqlovchi mavjud bo'lmagan detalni qidirardi.
    if not (with_tail and codes and part.assembly_parent_id is None):
        return
    for offset, code in enumerate(c for c in TAIL_CODES if packaging or PROCESS_POSTS[c] is not PostCode.UPAKOVKA):
        db.add(
            PartRoute(
                order_id=order_id,
                part_id=part.id,
                post_id=resolve_post(posts, PROCESS_POSTS[code]).id,
                seq=start_seq + len(codes) + offset,
                process_code=code,
                source=RouteSource.MANUAL,
                per_instance=1,
                total_required=part.count,
            )
        )
