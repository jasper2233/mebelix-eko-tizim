#!/usr/bin/env python3
r"""MebeliX bridge-agent (TZ 2.2.2) — printerli kompyuterdagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX G500-U (USB) printerga Windows drayveri
orqali chiqaradi. Chiquvchi ulanish — tsex routerida hech narsa ochilmaydi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (faqat printer ulangan kompyuterda):
    mebelix-agent.exe ni ishga tushiring - kichik oyna server manzili va admin
    paneldagi ulanish kodini so'raydi. Shundan keyin oyna umuman ko'rinmaydi:
    agent fonda ishlaydi, kompyuter yonganda o'zi tushadi (avtostart), holati esa
    admin panelda Ulandi/Uzilgan bo'lib ko'rinadi.
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
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

# websockets>=14 shart: additional_headers= va InvalidStatus.response.status_code
# API'si ishlatiladi (exe hozir 16.x bilan yig'iladi — README'dagi install qatori)
import websockets
import websockets.exceptions

# Windows konsoli standart cp866 — o'zbekcha tinish belgilari buzilmasin.
# Oynasiz (--noconsole) rejimda stdout umuman yo'q, shuning uchun suppress.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Har agent o'zgarishida qo'lda +1 (commit bilan birga). WS headerida serverga
# yuboriladi — admin paneldagi "Printerlar"da qaysi exe ishlayotgani ko'rinadi.
AGENT_VERSION = "1.4.0"

# O'rnatish konfiguratsiyasi shu yerda saqlanadi (exe qayerdan ishlatilishidan qat'i nazar)
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "MebelixAgent"
LOG_FILE = CONFIG_DIR / "agent.log"

# Exe (PyInstaller frozen) yoki dev-skript turgan katalog — yonidagi .env va
# eski navbat fayli shu yerdan qidiriladi
BASE_DIR = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)

# Pairing oynasi/konsolida taklif qilinadigan server manzili
DEFAULT_SERVER_URL = "wss://mes.mebelix.uz"

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

# ── Loglarni SERVERGA ham yuborish ────────────────────────────────────────────
# Admin panelda ko'rinsin: ilgari nosozlikni topish uchun operatordan tsexdagi
# kompyuterda agent log faylini ochishni so'rash kerak edi
# (masofadan kirish yo'q). Bufer chegaralangan: agent uzluksiz xato bersa ham
# xotira o'smaydi, eski satrlar o'zi tushib qoladi.
LOG_BUFFER: deque[str] = deque(maxlen=200)


class _ServerLogHandler(logging.Handler):
    """Satrni buferga qo'yadi — yuborishni alohida vazifa bajaradi.

    Bu yerda TARMOQQA CHIQILMAYDI: logging chaqiruvi chop etish yoki skan
    oqimining o'rtasida bo'lishi mumkin, tarmoq esa sekin. Bloklab qo'ysa
    yorliq kechikardi."""

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            LOG_BUFFER.append(self.format(record))


_server_handler = _ServerLogHandler()
_server_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_server_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(_server_handler)
log = logging.getLogger("bridge-agent")


def _load_dotenv() -> None:
    r"""Config o'qish tartibi: env var > exe yonidagi .env > %APPDATA%\MebelixAgent\.env."""
    for env_file in (BASE_DIR / ".env", CONFIG_DIR / ".env"):
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
    import urllib.error
    import urllib.request

    # Sxema normalizatsiyasi: https://, http://, sxemasiz - hammasi qabul qilinadi
    url = url.strip().rstrip("/") or DEFAULT_SERVER_URL
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
        data=json.dumps({"code": code}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return url, data["token"], data["name"]
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = json.loads(exc.read()).get("detail", "")
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
    url_var = tk.StringVar(value=DEFAULT_SERVER_URL)
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
        url = input(f"Server manzili [Enter = {DEFAULT_SERVER_URL}]: ").strip()
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
    _exe_env = BASE_DIR / ".env"
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
#: Qo'lda berilgan nom har doim ustun; avto-topilgani esa qayta tekshiriladi.
PRINTER_FIXED = bool(os.environ.get("PRINTER_NAME", ""))


def refresh_printer() -> str:
    """Printer nomini qayta aniqlaydi — drayver qaytganda agent qayta ishga
    tushirilishini talab qilmasin (ilgari nom faqat startda bir marta olinardi)."""
    global PRINTER_NAME
    if not PRINTER_FIXED:
        PRINTER_NAME = _detect_printer()
    return PRINTER_NAME
# Default %APPDATA%\MebelixAgent ichida: avtostartda ishchi papka System32 bo'ladi —
# u yerga yozib bo'lmaydi va navbat fayli jimgina yo'qolardi
QUEUE_FILE = Path(os.environ.get("QUEUE_FILE") or (CONFIG_DIR / "print-queue.jsonl"))

# Eski o'rnatish migratsiyasi: exe yonidagi qadimgi navbat faylida kutayotgan
# joblar bo'lsa yangi joyga ko'chiriladi — yorliq yo'qolmasin
_legacy_queue = BASE_DIR / "print-queue.jsonl"
if "QUEUE_FILE" not in os.environ and _legacy_queue.is_file() and not QUEUE_FILE.exists():
    with contextlib.suppress(OSError):
        _legacy_queue.replace(QUEUE_FILE)
        log.info("Eski navbat fayli ko'chirildi: %s", QUEUE_FILE)
# Skan-forvard (TZ 12.5): stanok skaneri (klaviatura-HID) terganini MES'ga ham
# yuborish. SCAN_FORWARD=0 o'chiradi; pynput bo'lmasa o'zi jim o'chadi.
SCAN_FORWARD = os.environ.get("SCAN_FORWARD", "1") != "0"

# Yangi job kelganda flusher darhol uyg'onadi (5s siklni kutmaydi)
FLUSH_EVENT = asyncio.Event()


#: Yaqinda qabul qilingan `job_id` lar. Server ack'ni ololmasa AYNAN o'sha jobni
#: qayta yuboradi — takrorni shu yerda to'xtatamiz, aks holda bitta bosishga
#: ikkita yorliq chiqardi. `instance_id` bu vazifaga YARAMAYDI: chek bekor
#: qilinganda o'sha nusxa qayta ishlatiladi, ya'ni qonuniy qayta chiqarishda ham
#: `instance_id` bir xil keladi va u bo'yicha filtr operatorning tuzatish yo'lini
#: yopib qo'yardi.
SEEN_JOBS: deque[str] = deque(maxlen=500)


def already_seen(job_id: str) -> bool:
    """Shu job allaqachon qabul qilinganmi. `job_id` siz (eski server) — doim yo'q.

    FAQAT tekshiradi — belgilash `mark_seen` da, diskka yozish MUVAFFAQIYATLI
    bo'lgandan keyin. Ilgari tekshirishning o'zi belgilab qo'yardi: local_enqueue
    yiqilsa (disk to'la, antivirus) ulanish ack'siz uzilar, server jobni qayta
    yuborar — endi esa "takror" deb soxta ok bilan yutilardi. Isbotlangan."""
    return bool(job_id) and job_id in SEEN_JOBS


def mark_seen(job_id: str) -> None:
    if job_id:
        SEEN_JOBS.append(job_id)


def local_enqueue(job: dict) -> None:
    """Durable local queue — survives agent restarts and power cuts (TZ 8.7).

    fsync SHART: usiz yozuv OS sahifa keshida qolar, ack esa serverga ketib
    bo'lgan bo'lardi — ack bilan lazy-writer orasidagi soniyalarda tok o'chsa
    yorliq hech qayerda qolmasdi (strace bilan tekshirilgan: oddiy write+close
    fsync bermaydi)."""
    with QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(job, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


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
        f.flush()
        os.fsync(f.fileno())
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
    if dm is None:
        # Ba'zi drayver holatlarida DEVMODE kelmaydi — aniq xabar bilan
        # yiqilamiz (job navbatda qoladi), AttributeError tashlamasdan
        raise RuntimeError("printer DEVMODE bermadi — drayverni qayta o'rnating")
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
        try:
            hdc.StartPage()
            ImageWin.Dib(img).draw(hdc.GetHandleOutput(), (0, 0, dw, dh))
            hdc.EndPage()
            hdc.EndDoc()
        except Exception:
            # Ochiq hujjatni bekor qilmasdan DeleteDC qilish spooler'da
            # chala hujjat qoldirardi
            with contextlib.suppress(Exception):
                hdc.AbortDoc()
            raise
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


async def log_shipper() -> None:
    """Buferdagi log satrlarini serverga yuboradi (har 30 s).

    HTTP, `/ws/bridge` orqali EMAS: o'sha soketda chek jo'natish, ack kutish va
    qayta navbatga qo'yish mantiqi bor — log xabari ack o'rniga o'qilsa job
    "nak" deb hisoblanib chop etish buzilardi. Diagnostika uchun ishlab
    chiqarish yo'lini xavf ostiga qo'yish mantiqsiz.

    Yuborilmasa satrlar TASHLAB YUBORILADI (qayta urinilmaydi): log yordamchi
    ma'lumot, u uchun navbat saqlash agentni murakkablashtirardi. Muhimi —
    fayl nusxasi baribir kompyuterda qoladi."""
    import urllib.error
    import urllib.request

    while True:
        await asyncio.sleep(30)
        if not LOG_BUFFER or not BRIDGE_TOKEN:
            continue
        lines = list(LOG_BUFFER)
        LOG_BUFFER.clear()
        http = MES_URL.replace("wss://", "https://", 1).replace("ws://", "http://", 1).rstrip("/")
        req = urllib.request.Request(
            f"{http}/api/v1/bridge-agents/logs",
            data=json.dumps({"lines": lines[-200:]}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {BRIDGE_TOKEN}",
            },
        )
        # Tarmoq chaqiruvi hodisa siklini bloklamasin — alohida oqimda
        with contextlib.suppress(Exception):
            await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=10).close())


async def flusher() -> None:
    """Lokal navbatni printerga oqizadi — printer qaytganda o'zi davom etadi.

    BITTADAN: har chop etishdan keyin fayl QAYTA o'qiladi va faqat chiqqan job
    olib tashlanadi. Ilgari butun batch bitta snapshot bilan yurar va oxirida
    `local_rewrite(remaining)` qilinardi — bu ikkita isbotlangan yo'qotish
    berardi: (1) chop etish (~3s GDI) paytida uplink qo'shgan va ack qilingan
    yangi job eski snapshot ustiga yozishda o'chib ketardi — serverda ham yo'q,
    yorliq izsiz yo'qolardi; (2) batch o'rtasida tok o'chsa chiqqan yorliqlar
    diskda qolib, restartda IKKINCHI marta chiqardi (bitta detalga ikkita bir
    xil QR). Endi xavf oynasi bitta yorliq: chop etish o'rtasida o'chsa faqat
    o'sha yorliq takrorlanishi mumkin — printersiz idempotentlikda bundan
    kichik oyna yo'q."""
    while True:
        while True:
            # Har aylanishda yangidan o'qiladi — snapshot eskirmaydi
            jobs = local_drain()
            if not jobs:
                break
            refresh_printer()
            job = jobs[0]
            # ALOHIDA OQIMDA: GDI chop etish bir necha soniya davom etadi va
            # to'g'ridan-to'g'ri chaqirilganda hodisa siklini qotirardi — WS
            # xabarlari o'qilmay, ack 15 soniyalik server chegarasidan
            # kechikardi, server esa jobni qaytarib IKKINCHI yorliq chiqarardi.
            if not await asyncio.to_thread(send_to_printer, job.get("png", "")):
                log.info("Printer kutilmoqda — navbatda %d ta yorliq", len(jobs))
                break
            log.info("Yorliq chop etildi: instance %s", job.get("instance_id"))
            # await'dan keyin fayl qayta o'qiladi: shu oraliqda kelganlar
            # SAQLANADI. local_enqueue faqat oxiriga qo'shadi, ya'ni birinchi
            # qator hali ham hozir chiqqan job — himoya sharti shunchaki
            # kutilmagan holatga qarshi.
            current = local_drain()
            if current and current[0] == job:
                current = current[1:]
            else:
                current = [j for j in current if j != job]
            local_rewrite(current)
        # Yangi job kelsa darhol, aks holda 5s da bir (printer tiklanishini kutish)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(FLUSH_EVENT.wait(), timeout=5)
        FLUSH_EVENT.clear()


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
        headers = {
            "Authorization": f"Bearer {BRIDGE_TOKEN}",
            "X-Agent-Version": AGENT_VERSION,
        }
        try:
            async with websockets.connect(
                url, ping_interval=30, additional_headers=headers
            ) as ws:
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
                        job_id = str(msg.get("job_id") or "")
                        # PRINTER YO'Q — rad etamiz. Ilgari job baribir qabul
                        # qilinib faylda MANGU qolardi, server esa "yetkazildi"
                        # deb hisoblardi: operator "chek yuborildi" xabarini
                        # ko'rib turib qog'oz kutardi. Rad etilsa job serverning
                        # navbatida qoladi va printer qaytganda chiqadi.
                        if not refresh_printer():
                            await ws.send(json.dumps({"ok": False}))
                            log.error(
                                "GoDEX printer topilmadi — job rad etildi, "
                                "serverda navbatda qoladi (instance %s)",
                                msg.get("instance_id"),
                            )
                            continue
                        if already_seen(job_id):
                            # Ack yo'lda yo'qolgan: server qayta yubordi. Faylga
                            # ikkinchi marta yozsak ikkita yorliq chiqardi.
                            await ws.send(json.dumps({"ok": True}))
                            log.info("Takroriy job tashlandi: %s", job_id)
                            continue
                        # Avval diskka — keyin belgi, keyin ack. Server ackdan
                        # keyin jobni unutadi (TZ 2.2.2); yozish yiqilsa belgi
                        # ham qo'yilmaydi va serverning retry'si qabul qilinadi.
                        local_enqueue(msg)
                        mark_seen(job_id)
                        await ws.send(json.dumps({"ok": True}))
                        FLUSH_EVENT.set()
                        log.info(
                            "Print job qabul qilindi: instance %s",
                            msg.get("instance_id"),
                        )
        except websockets.exceptions.InvalidStatus as exc:
            status = exc.response.status_code
            if status in (401, 403):
                reject_streak += 1
                if reject_streak >= 3:
                    log.error(
                        "Server %d marta rad etdi (HTTP %s) - token bekor qilingan",
                        reject_streak,
                        status,
                    )
                    reject_streak = 0
                    # ALOHIDA OQIMDA: _repair ichida tk mainloop (operator kod
                    # kiritguncha), urllib va messagebox bor — event loop'da
                    # chaqirilsa dialog ochiq turgan butun vaqt flusher lokal
                    # navbatdagi (allaqachon ack qilingan!) cheklarni ishlab
                    # turgan printerga chiqara olmasdi. Isbotlangan. Tk to'liq
                    # shu oqim ichida yaratiladi va yopiladi — thread-safe.
                    await asyncio.to_thread(_repair)
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
            data=json.dumps({"qr_text": qr, "client_event_id": uuid4().hex}).encode(),
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
                detail = str(json.loads(exc.read()).get("detail", ""))
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


def _newer(latest: str, current: str) -> bool:
    """'1.4.1' > '1.4.0'. Buzuq satr — yangilanish yo'q deb hisoblanadi."""
    try:
        lt = tuple(int(x) for x in latest.split("."))
        ct = tuple(int(x) for x in current.split("."))
        return lt > ct
    except ValueError:
        return False


def _apply_update(new_exe: Path) -> None:
    """O'zini almashtirish: .bat agent chiqishini kutadi, exe'ni almashtiradi,
    qayta ishga tushiradi. Yo'l o'zgarmaydi — avtostart registri amal qilaveradi;
    token/sozlama %APPDATA% da — ulanish saqlanadi."""
    import subprocess

    exe = Path(sys.executable)
    bat = CONFIG_DIR / "update.bat"
    bat.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        ":kutish\r\n"
        f'del "{exe}" >nul 2>&1\r\n'
        f'if exist "{exe}" (timeout /t 1 /nobreak >nul & goto kutish)\r\n'
        f'move /y "{new_exe}" "{exe}" >nul\r\n'
        f'start "" "{exe}"\r\n'
        f'del "%~f0"\r\n',
        encoding="ascii",
    )
    # DETACHED + NO_WINDOW: bat agent o'lgandan keyin ham yashaydi, oyna ochmaydi
    subprocess.Popen(  # noqa: S602
        ["cmd", "/c", str(bat)], creationflags=0x00000008 | 0x08000000
    )
    log.info("Yangilanish qo'llanmoqda — agent qayta ishga tushadi")
    os._exit(0)  # navbat fayli fsync qilingan, tozalash shart emas


async def self_update() -> None:
    """Har 6 soatda serverdan versiya so'raydi; yangi bo'lsa JIM yangilanadi.

    Flashka bilan tarqatish o'rniga: CI har deploy'da exe qurib serverga qo'yadi,
    agent o'zi tortadi. Operator hech narsa qilmaydi — tsexda "yuklab ol" tugmasi
    ishlamaydi. sha256 mos kelmasa (yarim yuklangan fayl) o'tkazib yuboriladi,
    keyingi siklda qayta urinadi. Dev-skript (frozen emas) o'zini yangilamaydi."""
    import hashlib
    import urllib.request

    if not getattr(sys, "frozen", False):
        return
    await asyncio.sleep(60)  # start + pairing tinchlansin
    while True:
        try:
            http = MES_URL.replace("wss://", "https://", 1).replace("ws://", "http://", 1).rstrip("/")
            info = json.loads(
                await asyncio.to_thread(
                    lambda: urllib.request.urlopen(f"{http}/api/v1/bridge-agents/latest", timeout=15).read()
                )
            )
            if _newer(str(info.get("version", "")), AGENT_VERSION):
                log.info("Yangilanish topildi: v%s -> v%s", AGENT_VERSION, info["version"])
                new_exe = CONFIG_DIR / "mebelix-agent-new.exe"
                data = await asyncio.to_thread(
                    lambda: urllib.request.urlopen(f"{http}/api/v1/bridge-agents/download", timeout=120).read()
                )
                if hashlib.sha256(data).hexdigest() != info.get("sha256"):
                    log.warning("Yangilanish sha256 mos emas — o'tkazib yuborildi")
                else:
                    new_exe.write_bytes(data)
                    _apply_update(new_exe)
        except Exception as exc:  # noqa: BLE001 — yangilanish hech qachon agentni yiqitmasin
            log.info("Yangilanish tekshiruvi o'tmadi: %s", exc)
        await asyncio.sleep(6 * 3600)


async def main() -> None:
    if not BRIDGE_TOKEN:
        raise SystemExit(
            "Token yo'q — agentni ishga tushirib admin paneldagi ulanish kodini kiriting"
        )
    log.info("MebeliX agent v%s", AGENT_VERSION)
    log.info("Printer: %s", PRINTER_NAME or "TOPILMADI — GoDEX drayverini o'rnating")
    start_scan_forward()
    await asyncio.gather(uplink(), flusher(), log_shipper(), self_update())


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
