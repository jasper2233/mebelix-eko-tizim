#!/usr/bin/env python3
r"""MebeliX bridge-agent (TZ 2.2.2) — printerli kompyuterdagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX G500-U (USB) printerga Windows drayveri
orqali chiqaradi. Chiquvchi ulanish — sex routerida hech narsa ochilmaydi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (faqat printer ulangan kompyuterda):
    mebelix-agent.exe ni ishga tushiring va admin paneldagi ulanish kodini kiriting.
    Kod bir marta so'raladi — token %APPDATA%\MebelixAgent\.env ga saqlanadi.

Printer avto-topiladi (nomida "godex" bor Windows printeri) — sozlash shart emas.

Env sozlamalari (ixtiyoriy, pairing o'zi to'ldiradi):
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN  — token (pairing bergan yoki serverdagi umumiy token)
    PRINTER_NAME  — printer nomini qo'lda berish (avto-topish o'rniga)
    QUEUE_FILE    — lokal navbat fayli (default ./print-queue.jsonl)
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path

import websockets
import websockets.exceptions

# Windows konsoli standart cp866 — o'zbekcha tinish belgilari buzilmasin
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge-agent")

# O'rnatish konfiguratsiyasi shu yerda saqlanadi (exe qayerdan ishlatilishidan qat'i nazar)
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "MebelixAgent"


def _load_dotenv() -> None:
    r"""Config o'qish tartibi: env var > exe yonidagi .env > %APPDATA%\MebelixAgent\.env."""
    base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    for env_file in (base / ".env", CONFIG_DIR / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"'))


def _pair_interactive() -> None:
    """Birinchi o'rnatish: admin panel bergan ulanish kodini doimiy tokenga
    almashtiradi va %APPDATA% ga saqlaydi. Serverga SSH ham, .env tahriri ham
    kerak emas. Kod bir martalik va 15 daqiqa yashaydi; token muddatsiz."""
    import json as _json
    import urllib.error
    import urllib.request

    if os.environ.get("BRIDGE_TOKEN") or not sys.stdin or not sys.stdin.isatty():
        return  # allaqachon ulangan yoki headless (Task Scheduler) — prompt yo'q
    try:
        print("=== MebeliX printer agenti — birinchi ulanish ===")
        url = (
            input("Server manzili [Enter = wss://mes.mebelix.uz]: ").strip()
            or "wss://mes.mebelix.uz"
        )
        code = input("Ulanish kodi (admin panel > Printer agentlar): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not code:
        return

    # Sxema normalizatsiyasi: https://, http://, sxemasiz — hammasi qabul qilinadi
    url = url.rstrip("/")
    if "://" not in url:
        url = "wss://" + url
    url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    if url.startswith("ws://"):
        from urllib.parse import urlparse

        if urlparse(url).hostname not in ("localhost", "127.0.0.1"):
            print(
                "DIQQAT: TLS'siz (ws://) — token ochiq tarmoqdan o'tadi; wss:// tavsiya etiladi."
            )
    http = url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)

    req = urllib.request.Request(
        f"{http}/api/v1/bridge-agents/pair",
        data=_json.dumps({"code": code}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
            token, name = data["token"], data["name"]
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = _json.loads(exc.read()).get("detail", "")
        raise SystemExit(f"Kod qabul qilinmadi: {detail or exc}") from None
    except OSError as exc:
        raise SystemExit(f"Serverga ulanib bo'lmadi ({http}): {exc}") from None
    except (ValueError, KeyError):
        raise SystemExit(
            f"Server javobi tushunarsiz — manzil to'g'riligini tekshiring: {http}"
        ) from None

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / ".env").write_text(
        f"MES_URL={url}\nBRIDGE_TOKEN={token}\n", encoding="utf-8"
    )
    os.environ["MES_URL"] = url
    os.environ["BRIDGE_TOKEN"] = token
    print(f"Ulandi: {name}. Sozlama saqlandi — keyingi safar so'ralmaydi.")


def _detect_printer() -> str:
    """PRINTER_NAME berilmasa nomida 'godex' bor lokal printerni topadi —
    printer almashsa ham config o'zgarmaydi, drayver o'rnatilsa bas."""
    try:
        import win32print

        for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
            if "godex" in p[2].lower():
                return p[2]
    except Exception:  # noqa: BLE001 — win32 yo'q (Linux) yoki printer topilmadi
        pass
    return ""


_load_dotenv()
_pair_interactive()

MES_URL = os.environ.get("MES_URL", "ws://localhost:8000")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PRINTER_NAME = os.environ.get("PRINTER_NAME", "") or _detect_printer()
QUEUE_FILE = Path(os.environ.get("QUEUE_FILE", "print-queue.jsonl"))

# Yangi job kelganda flusher darhol uyg'onadi (5s siklni kutmaydi)
FLUSH_EVENT = asyncio.Event()


def local_enqueue(job: dict) -> None:
    """Durable local queue — survives agent restarts and power cuts (TZ 8.7)."""
    with QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(job, ensure_ascii=False) + "\n")


def local_drain() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    jobs = []
    for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                jobs.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("Buzilgan navbat qatori tashlab yuborildi")
    return jobs


def local_rewrite(jobs: list[dict]) -> None:
    tmp = QUEUE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    tmp.replace(QUEUE_FILE)


def _print_png_gdi(png_b64: str) -> None:
    """PNG yorliqni Windows drayveri orqali chiqaradi (GibSaw 'Used the printer driver'
    rejimi bilan bir xil yo'l). DEVMODE'da qog'oz 80x60mm ga majburlanadi."""
    import base64
    import io as _io

    import win32con
    import win32gui
    import win32print
    import win32ui
    from PIL import Image, ImageWin

    img = Image.open(_io.BytesIO(base64.b64decode(png_b64))).convert("RGB")

    h = win32print.OpenPrinter(PRINTER_NAME)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
    finally:
        win32print.ClosePrinter(h)
    dm.PaperSize = 256  # DMPAPER_USER
    dm.PaperWidth = 800  # 0.1mm — 80mm
    dm.PaperLength = 600  # 60mm
    dm.Orientation = 1  # portret
    dm.Fields |= (
        win32con.DM_PAPERSIZE
        | win32con.DM_PAPERWIDTH
        | win32con.DM_PAPERLENGTH
        | win32con.DM_ORIENTATION
    )

    hdc_raw = win32gui.CreateDC("WINSPOOL", PRINTER_NAME, dm)
    hdc = win32ui.CreateDCFromHandle(hdc_raw)
    try:
        w = hdc.GetDeviceCaps(8)  # HORZRES
        ht = hdc.GetDeviceCaps(10)  # VERTRES
        scale = min(w / img.width, ht / img.height)
        dw, dh = int(img.width * scale), int(img.height * scale)
        hdc.StartDoc("MebeliX yorliq")
        hdc.StartPage()
        ImageWin.Dib(img).draw(hdc.GetHandleOutput(), (0, 0, dw, dh))
        hdc.EndPage()
        hdc.EndDoc()
    finally:
        hdc.DeleteDC()


def send_to_printer(png_b64: str) -> bool:
    """PNG yorliqni USB GoDEX'ga chiqaradi. False = printer band/yo'q — job navbatda qoladi."""
    if not PRINTER_NAME:
        log.error("GoDEX printer topilmadi — drayver o'rnatilganini tekshiring")
        return False
    if not png_b64:
        log.warning(
            "PNG'siz job tashlab yuborildi"
        )  # eski formatdagi yozuv navbatni to'smasin
        return True
    try:
        _print_png_gdi(png_b64)
        return True
    except Exception as exc:  # noqa: BLE001 — printer xatosi navbatda qolsin
        log.warning("Printer xatosi (%s): %s", PRINTER_NAME, exc)
        return False


async def flusher() -> None:
    """Lokal navbatni printerga oqizadi — printer qaytganda o'zi davom etadi."""
    while True:
        jobs = local_drain()
        if jobs:
            remaining = []
            for i, job in enumerate(jobs):
                if send_to_printer(job.get("png", "")):
                    log.info("Yorliq chop etildi: instance %s", job.get("instance_id"))
                else:
                    remaining = jobs[i:]
                    break
            local_rewrite(remaining)
            if remaining:
                log.info("Printer kutilmoqda — navbatda %d ta yorliq", len(remaining))
        # Yangi job kelsa darhol, aks holda 5s da bir (printer tiklanishini kutish)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(FLUSH_EVENT.wait(), timeout=5)
        FLUSH_EVENT.clear()


# v14+ additional_headers, eski v13- extra_headers
_HDR_KW = (
    "additional_headers"
    if int(websockets.__version__.split(".")[0]) >= 14
    else "extra_headers"
)
# Rad etilgan handshake (403) — v14+ InvalidStatus, eski v13- InvalidStatusCode
_REJECTED: tuple[type[Exception], ...] = (
    (websockets.exceptions.InvalidStatus,)
    if hasattr(websockets.exceptions, "InvalidStatus")
    else (websockets.exceptions.InvalidStatusCode,)
)


async def uplink() -> None:
    """Serverga doimiy outbound ulanish; uzilsa 5s backoff bilan qayta ulanadi."""
    # Token Authorization headerda — URL query'da emas (server loglariga tushmasin)
    url = f"{MES_URL.rstrip('/')}/api/v1/ws/bridge"
    kwargs = {_HDR_KW: {"Authorization": f"Bearer {BRIDGE_TOKEN}"}}
    while True:
        try:
            async with websockets.connect(url, ping_interval=30, **kwargs) as ws:
                log.info("Serverga ulandi: %s", MES_URL)
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "ping":
                        await ws.send(json.dumps({"ok": True}))
                        continue
                    if msg.get("type") == "print":
                        # Avval diskka — keyin ack. Server ackdan keyin jobni unutadi (TZ 2.2.2).
                        local_enqueue(msg)
                        await ws.send(json.dumps({"ok": True}))
                        FLUSH_EVENT.set()
                        log.info(
                            "Print job qabul qilindi: instance %s",
                            msg.get("instance_id"),
                        )
        except _REJECTED as exc:
            log.error(
                "Server ulanishni rad etdi (%s) — token bekor qilingan bo'lishi mumkin. "
                "Yangi kod bilan ulash uchun %s faylini o'chirib agentni qayta ishga tushiring.",
                exc,
                CONFIG_DIR / ".env",
            )
            await asyncio.sleep(60)
        except Exception as exc:
            log.warning("Ulanish uzildi (%s) — 5s dan keyin qayta urinish", exc)
            await asyncio.sleep(5)


async def main() -> None:
    if not BRIDGE_TOKEN:
        raise SystemExit(
            "Token yo'q — agentni ishga tushirib admin paneldagi ulanish kodini kiriting"
        )
    log.info("Printer: %s", PRINTER_NAME or "TOPILMADI — GoDEX drayverini o'rnating")
    await asyncio.gather(uplink(), flusher())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        # Exe ikki marta bosilganda oyna darhol yopilmasin — xato o'qilsin
        print("\nXATO:", exc)
        if sys.stdin and sys.stdin.isatty():
            with contextlib.suppress(Exception):
                input("Yopish uchun Enter bosing...")
        raise
