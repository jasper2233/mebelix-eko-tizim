#!/usr/bin/env python3
r"""MebeliX bridge-agent (TZ 2.2.2) — printerli kompyuterdagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX G500-U (USB) printerga Windows drayveri
orqali chiqaradi. Chiquvchi ulanish — sex routerida hech narsa ochilmaydi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (faqat printer ulangan kompyuterda):
    mebelix-agent.exe ni ishga tushiring - kichik oyna server manzili va admin
    paneldagi ulanish kodini so'raydi. Shundan keyin oyna umuman ko'rinmaydi:
    agent fonda ishlaydi, kompyuter yonganda o'zi tushadi (avtostart), holati esa
    admin panelda Onlayn/Oflayn bo'lib ko'rinadi.
    Sozlama: %APPDATA%\MebelixAgent\.env, loglar: %APPDATA%\MebelixAgent\agent.log

Printer avto-topiladi (nomida "godex" bor Windows printeri) — sozlash shart emas.

Env sozlamalari (ixtiyoriy, pairing o'zi to'ldiradi):
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN  — token (pairing bergan yoki serverdagi umumiy token)
    PRINTER_NAME  — printer nomini qo'lda berish (avto-topish o'rniga)
    QUEUE_FILE    — lokal navbat fayli (default %APPDATA%\MebelixAgent\print-queue.jsonl)
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import websockets
import websockets.exceptions

# Windows konsoli standart cp866 — o'zbekcha tinish belgilari buzilmasin.
# Oynasiz (--noconsole) rejimda stdout umuman yo'q, shuning uchun suppress.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Har agent o'zgarishida qo'lda +1 (commit bilan birga). WS headerida serverga
# yuboriladi — admin paneldagi "Printerlar"da qaysi exe ishlayotgani ko'rinadi.
AGENT_VERSION = "1.2.0"

# O'rnatish konfiguratsiyasi shu yerda saqlanadi (exe qayerdan ishlatilishidan qat'i nazar)
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "MebelixAgent"
LOG_FILE = CONFIG_DIR / "agent.log"

# Agent oynasiz ishlaydi — nima bo'layotganini bilishning yagona yo'li shu fayl.
# 1 MB x 3: yillar davomida ishlaydi, disk to'lib ketmaydi.
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
_handlers: list[logging.Handler] = [
    RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
]
if sys.stdout is not None:  # konsolli rejimda (dev) ekranga ham chiqsin
    _handlers.append(logging.StreamHandler())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("bridge-agent")


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


_MUTEX = None


def _single_instance() -> bool:
    """Ikkinchi nusxa ishga tushmasin. Agentda oyna yo'q, shuning uchun
    "ishlayaptimi?" deb exe'ni qayta bosish tabiiy — mutex shuni to'xtatadi.
    Ikki agent bir printerga ulansa navbat ular orasida bo'linib ketardi."""
    global _MUTEX
    try:
        import win32api
        import win32event
        import winerror

        _MUTEX = win32event.CreateMutex(None, False, "MebelixAgentSingleton")
        return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
    except Exception:  # noqa: BLE001 - win32 yo'q (dev/Linux): cheklovsiz ishlaymiz
        return True


def _alert(title: str, message: str, error: bool = False) -> None:
    """Oynasiz rejimda foydalanuvchiga yetadigan yagona xabar turi."""
    log.error(message) if error else log.info(message)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, message)
        root.destroy()
    except Exception:  # noqa: BLE001 - GUI yo'q: log fayli yetarli
        pass


def _register_autostart() -> None:
    """Kompyuter yonganda agent o'zi ishga tushsin. HKCU - admin huquqi kerak
    emas va faqat shu foydalanuvchiga tegishli. Dev skriptni ro'yxatga olmaymiz."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key, "MebelixAgent", 0, winreg.REG_SZ, f'"{sys.executable}"'
            )
        log.info("Avtostart yoqildi: %s", sys.executable)
    except Exception as exc:  # noqa: BLE001 - avtostartsiz ham ishlayveradi
        log.warning("Avtostart yozilmadi (%s) - qo'lda qo'shish kerak", exc)


class _PairError(Exception):
    """Foydalanuvchiga ko'rsatiladigan, tuzatib qayta urinsa bo'ladigan xato."""


def _exchange(url: str, code: str) -> tuple[str, str, str]:
    """Bir martalik kodni doimiy tokenga almashtiradi.
    Qaytaradi: (normallashgan ws url, token, agent nomi)."""
    import json as _json
    import urllib.error
    import urllib.request

    # Sxema normalizatsiyasi: https://, http://, sxemasiz - hammasi qabul qilinadi
    url = url.strip().rstrip("/") or "wss://mes.mebelix.uz"
    if "://" not in url:
        url = "wss://" + url
    url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    if url.startswith("ws://"):
        from urllib.parse import urlparse

        if urlparse(url).hostname not in ("localhost", "127.0.0.1"):
            log.warning("TLS'siz (ws://) ulanish - token ochiq tarmoqdan o'tadi")
    http = url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)

    req = urllib.request.Request(
        f"{http}/api/v1/bridge-agents/pair",
        data=_json.dumps({"code": code}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
            return url, data["token"], data["name"]
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = _json.loads(exc.read()).get("detail", "")
        raise _PairError(detail or f"Server rad etdi: {exc}") from None
    except OSError:
        raise _PairError(
            f"Serverga ulanib bo'lmadi: {http}\nManzil va internetni tekshiring."
        ) from None
    except (ValueError, KeyError):
        raise _PairError(
            f"Server javobi tushunarsiz - manzil to'g'rimi?\n{http}"
        ) from None


def _pair_dialog(error: str = "") -> tuple[str, str] | None:
    """Ikki maydonli sozlash oynasi. None = foydalanuvchi bekor qildi."""
    import tkinter as tk
    from tkinter import ttk

    picked: dict[str, str] = {}
    root = tk.Tk()
    root.title("MebeliX printer agenti")
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=18)
    frm.grid()

    ttk.Label(frm, text="Printerni ulash", font=("Segoe UI", 13, "bold")).grid(
        column=0, row=0, columnspan=2, sticky="w"
    )
    ttk.Label(
        frm, text="Kodni admin paneldan oling:\nPrinter agentlar > Yangi agent"
    ).grid(column=0, row=1, columnspan=2, sticky="w", pady=(2, 12))

    ttk.Label(frm, text="Server manzili").grid(
        column=0, row=2, sticky="w", padx=(0, 10)
    )
    url_var = tk.StringVar(value="wss://mes.mebelix.uz")
    ttk.Entry(frm, textvariable=url_var, width=32).grid(column=1, row=2, pady=4)

    ttk.Label(frm, text="Ulanish kodi").grid(column=0, row=3, sticky="w", padx=(0, 10))
    code_var = tk.StringVar()
    code_entry = ttk.Entry(frm, textvariable=code_var, width=32, font=("Consolas", 11))
    code_entry.grid(column=1, row=3, pady=4)

    if error:
        ttk.Label(
            frm, text=error, foreground="#b00020", wraplength=330, justify="left"
        ).grid(column=0, row=4, columnspan=2, sticky="w", pady=(10, 0))

    def submit(*_: object) -> None:
        if code_var.get().strip():
            picked["url"] = url_var.get()
            picked["code"] = code_var.get().strip()
            root.destroy()

    ttk.Button(frm, text="Ulash", command=submit).grid(
        column=1, row=5, sticky="e", pady=(16, 0)
    )
    root.bind("<Return>", submit)
    code_entry.focus_set()
    with contextlib.suppress(Exception):
        root.eval("tk::PlaceWindow . center")
    root.mainloop()
    return (picked["url"], picked["code"]) if picked else None


def _pair_console() -> tuple[str, str] | None:
    """GUI bo'lmagan muhit (dev, Linux) uchun zaxira."""
    if not sys.stdin or not sys.stdin.isatty():
        return None
    try:
        url = input("Server manzili [Enter = wss://mes.mebelix.uz]: ").strip()
        code = input("Ulanish kodi: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return (url, code) if code else None


def _pair() -> None:
    """Birinchi ishga tushish: kodni tokenga almashtiradi va %APPDATA% ga saqlaydi.
    Kod noto'g'ri bo'lsa oyna xato bilan qayta ochiladi - dasturni qayta ishga
    tushirish shart emas. Kod bir martalik va 15 daqiqa yashaydi; token muddatsiz."""
    if os.environ.get("BRIDGE_TOKEN"):
        return  # allaqachon ulangan
    error = ""
    while True:
        try:
            picked = _pair_dialog(error)
        except Exception:  # noqa: BLE001 - tkinter yo'q: konsolga tushamiz
            picked = _pair_console()
        if picked is None:
            raise SystemExit("Ulanish bekor qilindi.")
        try:
            url, token, name = _exchange(*picked)
            break
        except _PairError as exc:
            error = str(exc)
            log.warning("Ulanmadi: %s", error)

    def _rewrite_env(path: Path) -> None:
        """MES_URL/BRIDGE_TOKEN yangilanadi, qo'lda yozilgan boshqa kalitlar
        (PRINTER_NAME, QUEUE_FILE, SCAN_FORWARD...) SAQLANADI — aks holda
        re-pair'dan keyin nostandart nomli printer chek chiqarmay qolardi."""
        kept: list[str] = []
        if path.exists():
            with contextlib.suppress(OSError):
                for line in path.read_text(encoding="utf-8").splitlines():
                    key = line.split("=", 1)[0].strip()
                    if line.strip() and key not in ("MES_URL", "BRIDGE_TOKEN"):
                        kept.append(line)
        body = "\n".join([f"MES_URL={url}", f"BRIDGE_TOKEN={token}", *kept]) + "\n"
        path.write_text(body, encoding="utf-8")

    _rewrite_env(CONFIG_DIR / ".env")
    # Exe yonida qo'lda qo'yilgan .env bo'lsa u ham yangilanadi: o'qish tartibida
    # u APPDATA'dan USTUN turadi — eski (bekor qilingan) tokenli nusxasi qolsa
    # har yonganda o'sha yuklanib, dialog aylanasiga olib borardi
    _exe_env = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    ) / ".env"
    if _exe_env.exists():
        with contextlib.suppress(OSError):
            _rewrite_env(_exe_env)
    os.environ["MES_URL"] = url
    os.environ["BRIDGE_TOKEN"] = token
    _register_autostart()
    _alert(
        "MebeliX",
        f"Ulandi: {name}\n\nAgent fonda ishlaydi va kompyuter yonganda o'zi "
        f"tushadi - oyna ko'rinmaydi. Holatini admin paneldan kuzatasiz.",
    )


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
if not _single_instance():
    _alert("MebeliX", "Agent allaqachon ishlab turibdi.")
    raise SystemExit(0)
_pair()

MES_URL = os.environ.get("MES_URL", "ws://localhost:8000")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PRINTER_NAME = os.environ.get("PRINTER_NAME", "") or _detect_printer()
# Default %APPDATA%\MebelixAgent ichida: avtostartda ishchi papka System32 bo'ladi —
# u yerga yozib bo'lmaydi va navbat fayli jimgina yo'qolardi
QUEUE_FILE = Path(os.environ.get("QUEUE_FILE") or (CONFIG_DIR / "print-queue.jsonl"))

# Eski o'rnatish migratsiyasi: exe yonidagi qadimgi navbat faylida kutayotgan
# joblar bo'lsa yangi joyga ko'chiriladi — yorliq yo'qolmasin
_legacy_queue = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
) / "print-queue.jsonl"
if "QUEUE_FILE" not in os.environ and _legacy_queue.is_file() and not QUEUE_FILE.exists():
    with contextlib.suppress(OSError):
        _legacy_queue.replace(QUEUE_FILE)
        log.info("Eski navbat fayli ko'chirildi: %s", QUEUE_FILE)
# Skan-forvard (TZ 12.5): stanok skaneri (klaviatura-HID) terganini MES'ga ham
# yuborish. SCAN_FORWARD=0 o'chiradi; pynput bo'lmasa o'zi jim o'chadi.
SCAN_FORWARD = os.environ.get("SCAN_FORWARD", "1") != "0"

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


def _handshake_status(exc: Exception) -> int | None:
    """Handshake HTTP kodi: v14 InvalidStatus.response.status_code, v13 .status_code."""
    resp = getattr(exc, "response", None)
    if resp is not None:
        return getattr(resp, "status_code", None)
    return getattr(exc, "status_code", None)


def _repair() -> None:
    """Token bekor qilingan (admin "yangi kod" yoki "o'chirish" bosgan): saqlangan
    sozlamani tozalab, yangi kod so'raymiz. Busiz foydalanuvchi .env ni qo'lda
    o'chirishga majbur bo'lardi - agent esa fonda ishlab turgani uchun avval uni
    Task Manager orqali yopishi kerak edi (oyna yo'q, mutex ikkinchi nusxani
    qo'ymaydi). Bekor qilinsa agent to'xtaydi."""
    global BRIDGE_TOKEN, MES_URL

    # .env ATAYIN o'chirilmaydi: muvaffaqiyatli pairing uni baribir qayta yozadi,
    # dialog bekor qilinsa/agent o'chirilsa esa eski holat saqlanib qoladi
    # (token baribir bekor — keyingi ishga tushishda yana so'raladi)
    os.environ.pop("BRIDGE_TOKEN", None)
    _pair()
    BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
    MES_URL = os.environ.get("MES_URL", MES_URL)


_connected_once = False


def _notify_connected() -> None:
    """Birinchi muvaffaqiyatli ulanishda 5 soniyalik xabar (o'zi yopiladi) —
    monoblok yonganda arrachi agent tayyorligini shu yerdan biladi; bosish
    shart emas, ish oqimini to'smaydi. Alohida threadda: asyncio loop
    (flusher/uplink) bloklanmasin."""
    import ctypes
    import threading

    def show() -> None:
        with contextlib.suppress(Exception):
            # MessageBoxTimeoutW — timeout bilan yopiladigan MessageBox
            # (XP dan beri bor); topilmasa xabar shunchaki chiqmaydi, log yetadi
            ctypes.windll.user32.MessageBoxTimeoutW(  # type: ignore[attr-defined]
                0,
                f"Printer agenti serverga ulandi (v{AGENT_VERSION}).\nChek chiqarishga tayyor.",
                "MebeliX",
                0x00000040 | 0x00040000,  # MB_ICONINFORMATION | MB_TOPMOST
                0,
                5000,  # 5 soniyada o'zi yopiladi
            )

    threading.Thread(target=show, daemon=True).start()


async def uplink() -> None:
    """Serverga doimiy outbound ulanish; uzilsa 5s backoff bilan qayta ulanadi.

    Token FAQAT server 401/403 bilan KETMA-KET 3 marta rad etgandagina bekor
    hisoblanadi (webda "yangi kod"/"o'chirish" — server shunda 403 qaytaradi).
    Boshqa har qanday holat (deploy paytidagi 502/503, monoblok yonganda tarmoq
    hali tik turmagani, server qayta yonayotgani) — oddiy qayta urinish: saqlangan
    kod O'CHIRILMAYDI, dialog ochilmaydi."""
    reject_streak = 0
    while True:
        # Har urinishda qayta o'qiladi: token bekor qilinib qayta ulangan bo'lsa
        # (_repair) yangi qiymat darhol ishlatilsin.
        # Token Authorization headerda - URL query'da emas (server loglariga tushmasin)
        url = f"{MES_URL.rstrip('/')}/api/v1/ws/bridge"
        kwargs = {
            _HDR_KW: {
                "Authorization": f"Bearer {BRIDGE_TOKEN}",
                "X-Agent-Version": AGENT_VERSION,
            }
        }
        try:
            async with websockets.connect(url, ping_interval=30, **kwargs) as ws:
                log.info("Serverga ulandi: %s", MES_URL)
                reject_streak = 0
                global _connected_once
                if not _connected_once:
                    _connected_once = True
                    _notify_connected()
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "ping":
                        # pong != job-ack: {"ok":true} yuborilsa kechikkan javob
                        # serverda keyingi jobning ack'i deb o'qilishi mumkin edi
                        await ws.send(json.dumps({"type": "pong"}))
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
            status = _handshake_status(exc)
            if status in (401, 403):
                reject_streak += 1
                if reject_streak >= 3:
                    log.error(
                        "Server %d marta rad etdi (HTTP %s) - token bekor qilingan",
                        reject_streak,
                        status,
                    )
                    reject_streak = 0
                    _repair()
                    continue
                log.warning(
                    "Handshake rad etildi (HTTP %s, %d/3) — 5s dan keyin qayta urinish",
                    status,
                    reject_streak,
                )
            else:
                # 5xx / redirect / g'alati javob — server yoki tarmoq holati,
                # token aybdor emas; streak ham nolga — "ketma-ket" chin bo'lsin
                reject_streak = 0
                log.warning(
                    "Handshake muvaffaqiyatsiz (HTTP %s) — 5s dan keyin qayta urinish",
                    status,
                )
            await asyncio.sleep(5)
        except Exception as exc:
            reject_streak = 0
            log.warning("Ulanish uzildi (%s) — 5s dan keyin qayta urinish", exc)
            await asyncio.sleep(5)


def start_scan_forward() -> None:
    """Stanok skaneri o'qiganini MES'ga ham yuboradi (TZ 12.5).

    Skaner klaviatura kabi teradi: juda tez ketma-ket belgilar + Enter = skan
    (odam terishi bunday tez emas — 50ms/belgi chegarasi ajratib beradi).
    Passiv kuzatuv: Nanxing dasturi belgilarni avvalgidek oladi, biz nusxasini
    /bridge-agents/scan ga yuboramiz — bitta fizik skan ikkala tizimga tushadi."""
    if not SCAN_FORWARD:
        return
    try:
        from pynput import keyboard
    except ImportError:
        log.info("pynput o'rnatilmagan — skan-forvard o'chiq")
        return

    import json as _json
    import re
    import threading
    import time as _time
    import urllib.error
    import urllib.request
    from uuid import uuid4

    scan_re = re.compile(r"^[0-9A-Za-z_\-]{6,64}$")
    buf: list[str] = []
    first = [0.0]
    last = [0.0]

    def send(qr: str) -> None:
        # MES_URL har chaqiruvda o'qiladi: re-pairing manzilni almashtirgan
        # bo'lsa skan-forvard ham yangi serverga yozsin
        http = MES_URL.replace("wss://", "https://", 1).replace("ws://", "http://", 1).rstrip("/")
        req = urllib.request.Request(
            f"{http}/api/v1/bridge-agents/scan",
            data=_json.dumps({"qr_text": qr, "client_event_id": uuid4().hex}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {BRIDGE_TOKEN}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                log.info("Skan-forvard OK: %s", qr)
        except urllib.error.HTTPError as exc:
            detail = ""
            with contextlib.suppress(Exception):
                detail = str(_json.loads(exc.read()).get("detail", ""))
            log.warning("Skan-forvard rad (%s): %s — %s", exc.code, qr, detail)
        except OSError as exc:
            log.warning("Skan-forvard ulanish xatosi: %s", exc)

    def on_press(key: object) -> None:
        now = _time.monotonic()
        if now - last[0] > 0.25:
            buf.clear()
            first[0] = now
        last[0] = now
        if key == keyboard.Key.enter:
            s = "".join(buf)
            n = len(s)
            buf.clear()
            # skanerga xos tezlik: o'rtacha <50ms/belgi; odam terishi bundan sekin
            if n >= 6 and scan_re.match(s) and (last[0] - first[0]) / n < 0.05:
                threading.Thread(target=send, args=(s,), daemon=True).start()
            return
        ch = getattr(key, "char", None)
        if ch:
            buf.append(ch)

    keyboard.Listener(on_press=on_press, daemon=True).start()
    log.info("Skan-forvard yoqildi — skaner o'qigani MES'ga ham boradi")


async def main() -> None:
    if not BRIDGE_TOKEN:
        raise SystemExit(
            "Token yo'q — agentni ishga tushirib admin paneldagi ulanish kodini kiriting"
        )
    log.info("MebeliX agent v%s", AGENT_VERSION)
    log.info("Printer: %s", PRINTER_NAME or "TOPILMADI — GoDEX drayverini o'rnating")
    start_scan_forward()
    await asyncio.gather(uplink(), flusher())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        # Oyna yo'q - xato messagebox va log fayli orqali ko'rinadi
        if exc.code:
            _alert("MebeliX agenti", str(exc), error=True)
        raise
