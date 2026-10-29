import base64
import functools
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import func, select

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Row
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.core.tenancy import DEFAULT_TENANT, tkey, use_tenant
from app.core.utils.queue import TENANT_KWARG
from app.core.ws import ws_manager
from app.crud import log_action
from app.models import AndonEvent, BridgeAgent, Employee, Order, Pachka, PachkaItem, Scan, WasteItem, WorkSession
from app.models.enums import SessionStatus
from app.modules.buxgalteriya import service as buxgalteriya
from app.modules.integratsiya import service as integratsiya
from app.modules.ombor import service as ombor
from app.modules.platforma import service as platforma
from app.modules.soliq import service as soliq
from app.services.activity import last_activity
from app.services.downtimes import SYNC_WINDOW, sync_machine
from app.services.labels import (
    BadgeLabelData,
    PachkaLabelData,
    WasteLabelData,
    load_label_data,
    render_badge_png,
    render_label_png,
    render_pachka_label_png,
    render_waste_label_png,
)
from app.services.settings_service import IDLE_OPERATOR_MINUTES, get_setting

logger = logging.getLogger(__name__)

PRINT_QUEUE_KEY = "mes:print:queue"  # kalit prefiksi; manzilsiz kalitning o'zi o'qilmaydi


def agent_revoked_key(agent_id: int) -> str:
    """Bekor qilingan agent bayrog'i. Jonli WS ulanish har iteratsiyada shuni
    o'qiydi va darhol uziladi — ilgari revoke faqat 5 daqiqalik `touch_agent`
    da sezilardi va bekor qilingan token o'sha vaqt davomida chek olib chop
    etaverardi (prod-repro bilan o'lchandi: 295 s). TTL 10 daqiqa — ulanish
    shu vaqt ichida albatta uziladi, keyin bayroq keraksiz."""
    return tkey(f"mes:agent:revoked:{agent_id}")


def bridge_conn_key(agent_id: int) -> str:
    """Agentning ENG OXIRGI `/ws/bridge` ulanishi (qiymat — ulanish id'si).

    Tarmoq uzilgach agent qayta ulanadi, eski yarim-ochiq soketi esa serverda yana
    20-40 s yashaydi (uvicorn ping'i shunda sezadi). U yopilganda chiqqan «uzildi»
    hodisasi yangi ulanishning «ulandi» sidan KEYIN kelardi va terminal «MES agent
    uzilgan» belgisida qotib qolardi, agent esa ishlab turardi (prod 2026-10-03).
    Endi «uzildi» ni faqat kalitda hali O'Z id'si turgan ulanish chiqaradi
    (`ws.py: _bridge_gone`). TTL 10 daqiqa — eski soket bundan ancha oldin yopiladi."""
    return tkey(f"mes:bridge:conn:{agent_id}")


def print_queue_key(agent_id: int) -> str:
    """Chek navbati kaliti — FAQAT o'sha agentniki.

    Ilgari navbat bitta umumiy ro'yxat edi va har ulangan agent undan `BRPOP`
    qilardi. Ikki printer ulanganda (Arra-1 va Prisadka-1) chek qaysi biriga
    tushishi tasodif bo'lib qolardi: arrachi bosgan yorliqning taxminan yarmi
    prisadka printeridan chiqar, arrachi esa "chek chiqarildi" yozuvini ko'rib
    turib qog'ozni kutardi. Bekor qilib qayta bosish yordam bergandek tuyulardi,
    chunki u yangi tasodif edi.

    `agent_id` MAJBURIY. Ilgari `None` berilsa umumiy `PRINT_QUEUE_KEY` ga
    tushardi, uni esa `ws.py` umuman o'qimaydi — job "queued" deb muvaffaqiyat
    qaytarib jimgina yo'qolardi. Endi taskning o'zida `agent_id` ning
    standart qiymati YO'Q, ya'ni agentni unutgan chaqiruvchi TypeError oladi.
    """
    return tkey(f"{PRINT_QUEUE_KEY}:{agent_id}")


#: Agent `last_seen_at` ni har 5 daqiqada yangilaydi — 6 daqiqadan yangi bo'lsa
#: onlayn hisoblanadi (frontend `agents.tsx` bilan AYNAN bir xil chegara).
AGENT_ONLINE_WINDOW = timedelta(minutes=6)


def agent_online(last_seen_at: datetime | None) -> bool:
    return last_seen_at is not None and datetime.now(UTC) - last_seen_at <= AGENT_ONLINE_WINDOW


async def printer_agent(db: "AsyncSession", machine_id: int | None) -> "Row | None":
    """Shu ish markazidagi chop etadigan agent: `(id, last_seen_at)`. Yo'q bo'lsa `None`.

    Agent ish markaziga `bridge_agent.machine_id` orqali bog'langan, ish markazi
    esa postga. Ya'ni "qaysi printer" savoliga javob bazada allaqachon bor edi,
    faqat chek jo'natishda ishlatilmasdi.
    """
    if machine_id is None:
        return None
    return (
        (
            await db.execute(
                select(BridgeAgent.id, BridgeAgent.last_seen_at)
                .where(
                    BridgeAgent.machine_id == machine_id,
                    BridgeAgent.can_print == True,  # noqa: E712
                    BridgeAgent.token_hash.is_not(None),  # juftlanmagan agent chek ololmaydi
                    BridgeAgent.is_deleted == False,  # noqa: E712
                )
                # DETERMINISTIK: bitta ish markaziga xato bilan ikki agent
                # bog'langan bo'lsa (endi 409 bilan to'silgan, lekin eski
                # ma'lumotda uchrashi mumkin) tartibsiz `.first()` cheklarni
                # ikkiga bo'lib yuborardi — biri chiqadi, biri o'lik navbatda
                # qoladi. Eng yangi ko'ringani ustun, so'ng eng katta id.
                .order_by(BridgeAgent.last_seen_at.desc().nullslast(), BridgeAgent.id.desc())
            )
        )
        # `.scalars()` YO'Q: u faqat BIRINCHI ustunni oladi va bu yerda `Row`
        # o'rniga `int` qaytarardi — chaqiruvchidagi `agent.id` esa
        # `AttributeError: 'int' object has no attribute 'id'` bilan yiqilardi.
        .first()
    )


class NoPrinterBound(Exception):
    """Bu ish markaziga chop etadigan agent biriktirilmagan."""


async def require_printer(db: "AsyncSession", machine_id: int | None) -> "Row":
    """Chek qaysi agentga ketishini ANIQ aytadi, aks holda xato.

    Ilgari agent topilmasa `None` qaytarilib job UMUMIY navbatga tushardi va uni
    istalgan ulangan printer tortib olardi — chek boshqa postda, hatto ofisdagi
    test printeridan chiqib ketardi. Endi "printeri yo'q" holati JIM emas:
    chaqiruvchi 422 bilan aytadi va omborchi/operator sababini biladi.

    DIQQAT: agent OFFLINE bo'lishi xato EMAS — job o'sha agentning navbatida
    kutadi va u ulanganda chiqadi. Xato faqat agent umuman BIRIKTIRILMAGANDA.
    """
    agent = await printer_agent(db, machine_id)
    if agent is None:
        raise NoPrinterBound
    return agent


async def printing_agents(db: "AsyncSession") -> "Sequence[Row]":
    """Chop eta oladigan, juftlangan barcha agentlar — beyjik uchun tanlov ro'yxati.

    Beyjik ofisdagi admin panelidan chop etiladi, ya'ni ish markazi YO'Q va
    `printer_agent()` ga uzatadigan `machine_id` ham yo'q. Ilgari job umumiy
    navbatga tushardi va uni birinchi ulgurgan printer olardi — beyjik qaysi
    tsex printeridan chiqishi tasodif edi, admin esa uni qidirib yurishi kerak
    bo'lardi. Endi admin printerni ATAYLAB tanlaydi (yoki bitta bo'lsa — o'sha).
    """
    return (
        await db.execute(
            select(BridgeAgent.id, BridgeAgent.name, BridgeAgent.last_seen_at)
            .where(
                BridgeAgent.can_print == True,  # noqa: E712
                BridgeAgent.token_hash.is_not(None),
                BridgeAgent.is_deleted == False,  # noqa: E712
            )
            .order_by(BridgeAgent.name)
        )
    ).all()


def _print_job(ref_id: int, png_b64: str, queued_at: datetime | None = None) -> str:
    """Bitta chop etish topshirig'i. `job_id` — HAR YUBORISHDA yangi.

    Agent shu `job_id` bo'yicha takrorni tashlaydi. `ref_id` bu vazifani
    bajara OLMAYDI: chek bekor qilinganda o'sha nusxa qayta ishlatiladi
    (`terminal.py` da `label_printed_at = None`), ya'ni qayta chiqarishda
    `ref_id` bir xil keladi — u bo'yicha filtrlash operatorning yagona
    tuzatish yo'lini yopib qo'yardi.

    Wire maydoni `instance_id` deb ataladi, lekin qadoq/atxot/beyjik joblarida
    u `pachka_id`/`waste_id`/`employee_id` bo'ladi. Nom MEROS: uni `ref_id` ga
    o'zgartirish `bridge-agent/agent.py` ni ham yangilashni talab qiladi.
    """
    job: dict[str, Any] = {"type": "print", "job_id": uuid4().hex, "instance_id": ref_id, "png": png_b64}
    if queued_at is not None:
        # Navbatga qo'yilgan lahza (unix soniya) — agent qabul qilganda `/ws/bridge`
        # chek kechikishini o'lchaydi («Tizim holati»). Agent noma'lum maydonni e'tiborsiz qoldiradi.
        job["queued_at"] = queued_at.timestamp()
    return json.dumps(job)


async def _enqueue(ctx: dict[str, Any], ref_id: int, png_b64: str, agent_id: int, label: str) -> str:
    """Chizilgan PNG ni AYNAN shu agentning navbatiga qo'yadi."""
    redis = ctx.get("redis")  # arq worker context carries its Redis connection
    if redis is None:
        logger.error("%s %s uchun Redis navbati mavjud emas", label, ref_id)
        return f"lost:{ref_id}"
    await redis.lpush(print_queue_key(agent_id), _print_job(ref_id, png_b64, ctx.get("enqueue_time")))
    return f"queued:{ref_id}"


async def print_label(ctx: dict[str, Any], instance_id: int, agent_id: int) -> str:
    """Render the label PNG for one physical copy and queue it.

    LPUSH to the Redis print queue — the shop-floor bridge-agent draws the PNG on the
    USB GoDEX (G500-U) via the Windows driver. PNG is printer-dialect agnostic, so no
    EZPL is generated; the shop hardware has no network port.
    """
    async with local_session() as db:
        data = await load_label_data(db, instance_id)
        if data is None:
            return f"skip:{instance_id}"
        png_b64 = base64.b64encode(render_label_png(data)).decode()

    return await _enqueue(ctx, instance_id, png_b64, agent_id, "Print job")


async def print_pachka_label(ctx: dict[str, Any], pachka_id: int, agent_id: int) -> str:
    """Qadoq chekini chizib navbatga qo'yadi — detal yorlig'i bilan bir xil zanjir."""
    async with local_session() as db:
        pachka = await db.get(Pachka, pachka_id)
        if pachka is None or pachka.is_deleted:
            return f"skip:{pachka_id}"
        order = await db.get(Order, pachka.order_id)
        count = (
            await db.execute(
                select(func.count())
                .select_from(PachkaItem)
                .where(PachkaItem.pachka_id == pachka.id, PachkaItem.is_deleted == False)  # noqa: E712
            )
        ).scalar_one()
        png_b64 = base64.b64encode(
            render_pachka_label_png(
                PachkaLabelData(
                    code=pachka.code,
                    order_number=order.number if order else "",
                    project_name=(order.project_name if order else "") or "",
                    part_count=int(count),
                    printed_at=datetime.now(UTC).astimezone(TASHKENT_TZ),
                )
            )
        ).decode()

    return await _enqueue(ctx, pachka_id, png_b64, agent_id, "Qadoq cheki")


async def print_waste_label(ctx: dict[str, Any], waste_id: int, agent_id: int) -> str:
    """Foydali atxot chekini chizib navbatga qo'yadi — detal cheki bilan bir xil zanjir."""
    async with local_session() as db:
        w = await db.get(WasteItem, waste_id)
        if w is None or w.is_deleted:
            return f"skip:{waste_id}"
        order = await db.get(Order, w.order_id)
        png_b64 = base64.b64encode(
            render_waste_label_png(
                WasteLabelData(
                    qr_text=w.qr_text,
                    order_number=order.number if order else "",
                    project_name=(order.project_name if order else "") or "",
                    material=w.material_name,
                    length=w.length,
                    width=w.width,
                    sheet_no=w.sheet_no,
                    printed_at=datetime.now(UTC).astimezone(TASHKENT_TZ),
                )
            )
        ).decode()
        # `label_printed_at` ni ENDPOINT yozadi (terminal.py) — bu yerda yozilsa
        # javob bilan yozuv orasida poyga bo'lardi va terminal katagi darhol
        # yangilanmasdi.

    return await _enqueue(ctx, waste_id, png_b64, agent_id, "Atxot cheki")


async def print_badge(ctx: dict[str, Any], employee_id: int, agent_id: int) -> str:
    """Hodim beyjigini chizib navbatga qo'yadi — detal cheki bilan bir xil zanjir.

    Brauzerdan chop etish o'rniga: u drayverdagi saqlangan qog'oz o'lchamiga
    tayanardi va 80x60 bo'lmasa kontent yorliqqa mos tushmasdi.
    """
    async with local_session() as db:
        employee = await db.get(Employee, employee_id)
        if employee is None or employee.is_deleted:
            return f"skip:{employee_id}"
        png_b64 = base64.b64encode(
            render_badge_png(
                BadgeLabelData(
                    full_name=employee.full_name,
                    position=employee.position or "",
                    badge_id=employee.badge_id,
                )
            )
        ).decode()

    return await _enqueue(ctx, employee_id, png_b64, agent_id, "Beyjik")


#: To'xtashlarni qayta hisoblash oralig'i. Terminal ochiq bo'lsa u o'zi ham hisoblaydi (sababni
#: so'rash uchun) — bu cron kompyuter/terminal o'chiq paytdagi to'xtashlar ham yozilsin deb.
DOWNTIME_SWEEP_MINUTES = 5


async def sync_downtimes(ctx: dict[str, Any]) -> str:
    """Oxirgi hisob oynasida Pico hodisasi kelgan HAR ish markazining to'xtashlarini yozadi (`services/downtimes`)."""
    now = datetime.now(UTC)
    async with local_session() as db:
        machine_ids = (
            (
                await db.execute(
                    select(AndonEvent.machine_id)
                    .where(AndonEvent.happened_at >= now - SYNC_WINDOW, AndonEvent.is_deleted == False)  # noqa: E712
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for machine_id in machine_ids:
            await sync_machine(db, machine_id, now)
        await db.commit()
    return f"synced:{len(machine_ids)}"


#: Worker cron oralig'i — smena chegara oshgandan ko'pi bilan shuncha keyin yopiladi.
IDLE_SWEEP_MINUTES = 10


async def close_idle_sessions(ctx: dict[str, Any]) -> str:
    """Harakatsiz BRIGADANING ochiq smenalarini yopadi (cron, `IDLE_SWEEP_MINUTES` da bir).

    Brauzer ochiq bo'lsa uni o'zi login sahifasiga qaytaradi va logout smenani yopadi.
    Bu — brauzer YO'Q holat uchun: monoblok o'chirilgan, oyna yopilgan. Ilgari smena
    muddati yo'q edi va Prisadka smenasi 12 kun ochiq turib qolgan (2026-09-05 dan).

    Brigada birga baholanadi: skan langar smenaga yoziladi (`active_session`), ya'ni
    sherigining smenasida skan bo'lmaydi — alohida baholansa ishlab turgan sherik yopilardi.
    Faollik = eng so'nggisi: smena ochilishi, brigada smenalariga yozilgan skan (bazadan —
    Redis tozalansa ham, brauzer yopiq stanok skaneri ishlasa ham to'g'ri) va smenani
    ochgan hisobning brauzerdagi harakati. Ish jadvali ATAYLAB hisobga olinmaydi —
    smena kechroq tugashi mumkin.

    `ended_at` — yopilgan payt emas, OXIRGI FAOLLIK: odam 18:00 da ketgan bo'lsa smena
    19:40 da emas, 18:00 da tugagan.
    """
    redis = ctx.get("redis")
    now = datetime.now(UTC)
    closed: list[WorkSession] = []
    async with local_session() as db:
        limit = timedelta(minutes=int(await get_setting(db, IDLE_OPERATOR_MINUTES)))
        open_sessions = (
            await db.execute(
                select(WorkSession).where(
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars()
        crews: dict[int | None, list[WorkSession]] = {}
        for session in open_sessions:
            crews.setdefault(session.machine_id, []).append(session)

        for crew in crews.values():
            seen = [session.created_at for session in crew]
            last_scan = (
                await db.execute(select(func.max(Scan.created_at)).where(Scan.session_id.in_([s.id for s in crew])))
            ).scalar()
            if last_scan is not None:
                seen.append(last_scan)
            for user_id in {session.user_id for session in crew if session.user_id is not None}:
                if (at := await last_activity(redis, user_id)) is not None:
                    seen.append(at)
            last = max(seen)
            if now - last <= limit:
                continue
            # ponytail: shu oraliqda kelgan skan yopilgan smenaga yozilishi mumkin (millisekundlar
            # oynasi, faqat aynan chegarada qaytgan odamda). Qator qulfi kerak bo'lsa — FOR UPDATE.
            for session in crew:
                session.status = SessionStatus.ENDED
                session.ended_at = last
                log_action(
                    db,
                    module="sessions",
                    action="ended",
                    employee_id=session.employee_id,
                    entity_type="session",
                    entity_id=session.id,
                    message=f"Harakatsizlik: {int(limit.total_seconds() // 60)} daqiqa ish bo'lmadi",
                )
                closed.append(session)
        await db.commit()

    # Worker protsessida WS mijozlari yo'q — hodisa Redis kanali orqali API workerlariga boradi
    if redis is not None:
        ws_manager.redis = redis
    for session in closed:
        await ws_manager.publish("session.ended", {"session_id": session.id, "machine_id": session.machine_id})
    return f"closed:{len(closed)}"


TaskFn = Callable[..., Coroutine[Any, Any, str]]


def tenant_task(fn: TaskFn) -> TaskFn:
    """Vazifani navbatga qo'ygan obunachi nomidan bajaradi (`queue.enqueue` uzatgan `eko_tenant`).

    `functools.wraps` — arq vazifani `__qualname__` bo'yicha taniydi, nom o'zgarmasin.
    """

    @functools.wraps(fn)
    async def run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> str:
        with use_tenant(kwargs.pop(TENANT_KWARG, DEFAULT_TENANT)):
            return await fn(ctx, *args, **kwargs)

    return run


def per_tenant_cron(fn: TaskFn) -> TaskFn:
    """Cron vazifasini HAR faol obunachi uchun ketma-ket bajaradi. Bittasi yiqilsa qolganlari
    to'xtamaydi — xato logga yoziladi va natijada `<kod>:xato` bo'ladi."""

    @functools.wraps(fn)
    async def run(ctx: dict[str, Any]) -> str:
        results: list[str] = []
        for kod in await platforma.active_tenants():
            with use_tenant(kod):
                try:
                    results.append(f"{kod}:{await fn(ctx)}")
                except Exception:
                    logger.exception("Cron %s obunachi %s da yiqildi", fn.__name__, kod)
                    results.append(f"{kod}:xato")
        return "; ".join(results)

    return run


#: Rezerv muddatini tekshirish oralig'i (EKO TZ §5 B3)
REZERV_SWEEP_MINUTES = 5


async def expire_reservations(ctx: dict[str, Any]) -> str:
    """To'lov muddati o'tgan rezervlarni bo'shatadi — material yana sotuvga ochiladi."""
    async with local_session() as db:
        n = await ombor.expire_reservations(db)
        await db.commit()
    return f"expired:{n}"


async def ombor_solishtirish(ctx: dict[str, Any]) -> str:
    """Kechki solishtirish (EKO 2.4): farq bo'lsa ERROR logi — monitoring ushlaydi. Hech narsani tuzatmaydi."""
    async with local_session() as db:
        farqlar = await ombor.reconcile(db)
    for f in farqlar[:50]:
        logger.error("ombor solishtirish: [%s] %s hisobda=%s kerak=%s — %s", f.tur, f.kalit, f.hisobda, f.kerak, f.izoh)
    return f"farq:{len(farqlar)}"


async def kroy_outbox(ctx: dict[str, Any]) -> str:
    """MES → MX xabarlar navbatini yuborish (EKO 3d): tartib bilan, xatoda keyinroq qayta."""
    async with local_session() as db:
        r = await integratsiya.outbox_yubor(db)
    return f"yuborildi:{r['yuborildi']} rad:{r['rad']}"


async def kroy_katalog(ctx: dict[str, Any]) -> str:
    """MES katalogining o'zgargan pozitsiyalarini MX ga navbatga qo'yish (EKO 3e, K5)."""
    async with local_session() as db:
        n = await integratsiya.katalog_sinxron(db)
        await db.commit()
    return f"navbatga:{n}"


async def bux_sinxron(ctx: dict[str, Any]) -> str:
    """Avtomatik provodkalarni manbalarga moslash (EKO 7). Tarifda buxgalteriya yo'q obunachi — o'tadi."""
    if not await platforma.module_enabled("buxgalteriya"):
        return "buxgalteriya o'chiq"
    async with local_session() as db:
        n = await buxgalteriya.sinxron(db)
        await db.commit()
    return f"yozildi:{n.yozildi} tuzatish:{n.tuzatish}"


async def soliq_esf(ctx: dict[str, Any]) -> str:
    """ESF navbati (EKO 6): yuborish, holat so'rash, kiruvchilarni olish. Tarifda soliq yo'q obunachi — o'tadi."""
    if not await platforma.module_enabled("soliq"):
        return "soliq o'chiq"
    async with local_session() as db:
        n = await soliq.ishlov(db)
        await db.commit()
    return f"yuborildi:{n.yuborildi} javob:{n.javob} xato:{n.xato} kiruvchi:{n.kiruvchi}"


all_tasks = [tenant_task(f) for f in (print_label, print_pachka_label, print_waste_label, print_badge)]
sync_downtimes_all = per_tenant_cron(sync_downtimes)
close_idle_sessions_all = per_tenant_cron(close_idle_sessions)
expire_reservations_all = per_tenant_cron(expire_reservations)
ombor_solishtirish_all = per_tenant_cron(ombor_solishtirish)
kroy_outbox_all = per_tenant_cron(kroy_outbox)
kroy_katalog_all = per_tenant_cron(kroy_katalog)
soliq_esf_all = per_tenant_cron(soliq_esf)
bux_sinxron_all = per_tenant_cron(bux_sinxron)
