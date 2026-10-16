#!/usr/bin/env python3
r"""MebeliX bridge-agent — printerli kompyuterdagi yengil servis.

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

Printer avto-topiladi (tanish yorliq-printer rusumlari: godex, xprinter,
gprinter, tsc, zebra, argox, postek). Boshqa rusum — PRINTER_NAME bilan.

Env sozlamalari (ixtiyoriy, pairing o'zi to'ldiradi):
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN — token (pairing bergan yoki serverdagi umumiy token)
    PRINTER_NAME — printer nomini qo'lda berish (avto-topish o'rniga)
    QUEUE_FILE    — lokal navbat fayli (default %APPDATA%\MebelixAgent\print-queue.jsonl)
    ANDON         — stanok signal ustuni (Pico, USB) o'qish; 0 = o'chiq (default yoniq,
                    Pico topilmagan kompyuterda o'zi jim turadi)
    ANDON_PORT    — Pico COM porti (bo'sh = Raspberry Pi VID bo'yicha o'zi topadi)
    ANDON_TUR     — Pico turi: prisadka | kromka | rover (bo'sh = birinchi qatordan o'zi aniqlaydi)
    ROVER_T_REASON, ROVER_AUTO_SHUTDOWN — rover Pico'siga yuboriladigan sozlama
    ANDON_TAKEOVER — 0 = port band bo'lsa eski PrisadkaMES.exe ni to'xtatmaslik
    ANDON_QUEUE_FILE — andon navbati (default %APPDATA%\MebelixAgent\andon-queue.jsonl)
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

# websockets>=14 shart: additional_headers= va InvalidStatus.response.status_code
# API'si ishlatiladi (CI exe'ni pinlanmagan `websockets>=14` ning eng so'nggi versiyasi
# bilan yig'adi — README'dagi install qatori)
import websockets
import websockets.exceptions

# Windows konsoli standart cp866 — o'zbekcha tinish belgilari buzilmasin.
# Oynasiz (--noconsole) rejimda stdout umuman yo'q, shuning uchun suppress.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Har agent o'zgarishida qo'lda +1 (commit bilan birga). WS headerida serverga
# yuboriladi — admin paneldagi "MES agentlar" sahifasida qaysi exe ishlayotgani ko'rinadi.
AGENT_VERSION = "1.9.0"

# MX logotipi (PNG, 112px balandlik, base64). MANBAGA JOYLANGAN sabab:
# PyInstaller onefile'da --add-data va runtime yo'l topish o'rniga bitta
# konstanta — dev skriptda ham, exe'da ham bir xil ishlaydi. QO'LDA TAHRIRLANMAYDI:
# design/logo/icon-navy.png dan `scripts/brand-assets.py --write` yasaydi, CI tekshiradi.
_LOGO_B64 = (
    "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"
    "kP82/xsBWgHcgOaAqUDHwJWBfUGkoAVB1UEPgs2CRcE9IXBIYMj2kLvzDecL53eFgtCA0O2h98KMw5aFfR+OCQ8Lrwl/GGET"
    "URDRv4C6YMmClgWvIr0iyyLvRJlESaJ6oxWjE6Kbo1/HeMeUx0hjrWJXxl6K04gTxHXHY+Oj45vipxf6LNy5cDzBPqE44foi"
    "40V5iy4s1licvvj4EsUlnCVHEtGJMYktie85oZwGzvTSgKW1S6e4bO4u7hOeB28Hb5Lvyi/nTyS5JpUnPUp2Td6ePJninlKR"
    "8lTAFlQLnqf6p9alvk4LTduf9ik9Jr09A5eRmHFUSBGmCfsytTPzMoezzLOKs6TLnJftXDYlChI1ZUPZi7K7xTTZz9SAxESy"
    "XjKa45ZTk/MmNzr3SJ5ynjBvYLnZ8k3LJ/J9879egVrBXdFboFuwtmB0pefK+lXQqqWrelfrry5aPb7Gb82BtYS1aWt/KLQu"
    "LC98uS5mXU+RVtGaorH1futbixWKRcU3NrhsqNuI2ijYOLhp7qaqTR9LeCUXS61LK0rfb+ZuvviVzVeVX33akrRlsMyhbM9W"
    "zFbh1uvb3LcdKFcuzy8f2x6yvXMHY0fJjpc7l+y8UGFXUbeLsEuyS1oZXNldZVC1tep9dUr1SI1XTXutZu2m2te7ebuv7PHY"
    "01anVVda926vYO/Ner/6zgajhop9mH05+x42Rjf2f836urlJo6m06cN+4X7pgYgDfc2Ozc0tmi1lrXCrpHXyYMLBy994f9Pd"
    "xmyrb6e3lx4ChySHHn+b+O31w0GHe4+wjrR9Z/hdbQe1o6QT6lzeOdWV0iXtjusePhp4tLfHpafje8vv9x/TPVZzXOV42QnC"
    "iaITn07mn5w+lXXq6enk02O9S3rvnIk9c60vvG/wbNDZ8+d8z53p9+w/ed71/LELzheOXmRd7LrkcKlzwH6g4wf7HzoGHQY7"
    "hxyHui87Xe4Znjd84or7ldNXva+euxZw7dLI/JHh61HXb95IuCG9ybv56Fb6ree3c27P3FlzF3235J7SvYr7mvcbfjT9sV3q"
    "ID0+6j068GDBgztj3LEnP2X/9H686CH5YcWEzkTzI9tHxyZ9Jy8/Xvh4/EnWk5mnxT8r/1z7zOTZd794/DIwFTs1/lz0/NOv"
    "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"
    "TkSuQmCC"
)

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


#: Pairing dialogi ochiq — self_update shu paytda exe'ni almashtirmasligi kerak
#: (os._exit ochiq oynani o'ldirib, operatorni kod kiritolmay qoldirardi)
PAIRING = threading.Event()


class _PairError(Exception):
    """Foydalanuvchiga ko'rsatiladigan, tuzatib qayta urinsa bo'ladigan xato."""


def _exchange(url: str, code: str) -> tuple[str, str, str, str]:
    """Bir martalik kodni doimiy tokenga almashtiradi.
    Qaytaradi: (normallashgan ws url, token, agent nomi, stanok nomi yoki "")."""
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
            return url, data["token"], data["name"], str(data.get("machine_name") or "")
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            # 422 da `detail` — lug'atlar ro'yxati; xom pydantic tuzilmasini
            # ko'rsatmaslik uchun faqat matn bo'lsa qabul qilamiz.
            raw = json.loads(exc.read()).get("detail", "")
            detail = raw if isinstance(raw, str) else ""
        raise _PairError(detail or f"Server rad etdi: {exc}") from None
    except OSError:
        raise _PairError(
            f"Serverga ulanib bo'lmadi: {http}\nManzil va internetni tekshiring."
        ) from None
    except (ValueError, KeyError):
        raise _PairError(
            f"Server javobi tushunarsiz - manzil to'g'rimi?\n{http}"
        ) from None


def _brand_root(title: str) -> tuple[Any, Any, Any]:
    """Brendlangan Tk oyna: oq fon, clam mavzu, style'lar, logo va kapa qatori.

    Qaytaradi (root, frm, kapa): logo kapa'ning 0-ustunida turadi — chaqiruvchi
    sarlavhasini 1-ustunga, qolgan mazmunini frm'ning 1+ qatorlariga qo'yadi."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    root.configure(bg="#ffffff")
    st = ttk.Style(root)
    with contextlib.suppress(Exception):
        st.theme_use("clam")
    # Monoblok oldida TIK TURIB o'qiladi — 11-12pt mayda edi, hammasi bir
    # pog'ona katta.
    st.configure("K.TFrame", background="#ffffff")
    st.configure("K.TLabel", background="#ffffff", font=("Segoe UI", 14))
    st.configure("Title.TLabel", background="#ffffff", font=("Segoe UI", 22, "bold"))
    st.configure("Ok.TLabel", background="#ffffff", font=("Segoe UI", 22, "bold"), foreground="#15803d")
    st.configure("Sub.TLabel", background="#ffffff", font=("Segoe UI", 12), foreground="#5b6b73")
    st.configure("Err.TLabel", background="#ffffff", font=("Segoe UI", 12, "bold"), foreground="#b00020")
    st.configure("K.TButton", font=("Segoe UI", 15, "bold"), padding=(0, 12))

    frm = ttk.Frame(root, padding=(36, 28, 36, 30), style="K.TFrame")
    frm.grid()
    frm.columnconfigure(0, minsize=520)
    kapa = ttk.Frame(frm, style="K.TFrame")
    kapa.grid(column=0, row=0, sticky="w")
    # Logo sarlavha yonida; iconphoto — taskbar/alt-tab uchun
    with contextlib.suppress(Exception):
        logo2x = tk.PhotoImage(data=_LOGO_B64)
        logo = logo2x.subsample(2)
        root.iconphoto(True, logo2x)
        lbl = ttk.Label(kapa, image=logo, style="K.TLabel")
        lbl.image = logo  # type: ignore[attr-defined]  # GC dan saqlash
        lbl.grid(column=0, row=0, padx=(0, 14))
    return root, frm, kapa


def _success_window(name: str, stanok: str) -> None:
    """Ulanish muvaffaqiyati — pairing oynasi uslubidagi brendlangan oyna.

    Oddiy messagebox o'rnatuvchining ko'zi tushadigan YAGONA tasdiq edi —
    endi logo, katta sarlavha va aniq satrlar. Tk bo'lmasa log yetadi."""
    try:
        from tkinter import ttk

        root, frm, kapa = _brand_root("MebeliX MES agent")
        ttk.Label(kapa, text="Ulandi ✓", style="Ok.TLabel").grid(column=1, row=0)
        satrlar = [f"Agent: {name}", f"Versiya: v{AGENT_VERSION}"]
        if stanok:
            satrlar.append(f"Ish markazi: {stanok} — skan-forvard shu stanok nomidan yoziladi")
        satrlar.append("")
        satrlar.append(
            "Agent fonda ishlaydi va kompyuter yonganda o'zi tushadi.\n"
            "Holati — tray'dagi MX belgisi (yashil = ulandi) va admin panel."
        )
        ttk.Label(frm, text="\n".join(satrlar), style="K.TLabel", justify="left").grid(
            column=0, row=1, sticky="w", pady=(14, 0)
        )
        ttk.Button(frm, text="Tushunarli", command=root.destroy, style="K.TButton").grid(
            column=0, row=2, sticky="we", pady=(20, 0)
        )
        root.bind("<Return>", lambda *_: root.destroy())
        with contextlib.suppress(Exception):
            root.attributes("-topmost", True)
            root.lift()
        with contextlib.suppress(Exception):
            root.eval("tk::PlaceWindow . center")
        root.mainloop()
    except Exception:  # noqa: BLE001 — GUI yo'q: log yetarli
        log.info("Ulandi: %s (%s)", name, stanok or "stanoksiz")


def _pair_dialog(error: str = "") -> tuple[str, str] | None:
    """Ikki maydonli sozlash oynasi. None = foydalanuvchi bekor qildi."""
    import tkinter as tk
    from tkinter import ttk

    # Tsex monobloki uchun KATTA: eski 18px padding + default shriftli oyna
    # ~360px chiqardi — sensorli ekranda maydon topish qiyin, matn mayda edi.
    # Endi shriftlar 12-20pt, maydonlar to'liq en, tugma butun pastki qator.
    picked: dict[str, str] = {}
    # "printer agenti" EMAS: agent printersiz stanok kompyuterida ham ishlaydi
    # (skan-forvard) — nom ikkala vazifani qamrasin
    root, frm, kapa = _brand_root("MebeliX MES agent")
    ttk.Label(kapa, text="MebeliX MES agent", style="Title.TLabel").grid(
        column=1, row=0, sticky="w"
    )
    ttk.Label(
        frm,
        text="Serverga bir marta ulanadi, keyin fonda ishlaydi.\n"
        "Kod: admin panel > MES agentlar > Yangi agent (15 daqiqa amal qiladi).",
        style="Sub.TLabel",
        justify="left",
    ).grid(column=0, row=1, sticky="w", pady=(4, 18))

    ttk.Label(frm, text="Server manzili", style="K.TLabel").grid(
        column=0, row=2, sticky="w"
    )
    url_var = tk.StringVar(value=DEFAULT_SERVER_URL)
    ttk.Entry(frm, textvariable=url_var, font=("Segoe UI", 14)).grid(
        column=0, row=3, sticky="we", pady=(2, 14), ipady=7
    )

    ttk.Label(frm, text="Ulanish kodi", style="K.TLabel").grid(
        column=0, row=4, sticky="w"
    )
    code_var = tk.StringVar()
    # Kod maydoni eng katta — u yagona qo'lda teriladigan qiymat: katta mono
    # shriftda 8 belgi + defis, xato terish darhol ko'rinadi.
    # AVTO-KATTA harf: server baribir upper() qiladi, lekin kichik harfda
    # terilgan kod ekranda paneldagidan boshqacha ko'rinib ishonchsizlik berardi
    code_var.trace_add("write", lambda *_: code_var.set(code_var.get().upper()))
    code_entry = ttk.Entry(
        frm, textvariable=code_var, font=("Consolas", 22, "bold"), justify="center"
    )
    code_entry.grid(column=0, row=5, sticky="we", pady=(2, 0), ipady=10)

    if error:
        ttk.Label(
            frm, text=error, style="Err.TLabel", wraplength=520, justify="left"
        ).grid(column=0, row=6, sticky="w", pady=(14, 0))

    def submit(*_: object) -> None:
        if code_var.get().strip():
            picked["url"] = url_var.get()
            picked["code"] = code_var.get().strip()
            root.destroy()

    ttk.Button(frm, text="Ulash", command=submit, style="K.TButton").grid(
        column=0, row=7, sticky="we", pady=(22, 0)
    )
    root.bind("<Return>", submit)
    # USTKI QATLAM + majburiy fokus: terminal to'liq ekran kiosk rejimida
    # ishlaydi, oyna uning ORTIDA ochilsa operator hech narsa ko'rmasdi va
    # "agent yangi kod so'ramayapti" degan xulosaga kelardi.
    with contextlib.suppress(Exception):
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
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
    PAIRING.set()
    try:
        _pair_loop()
    finally:
        PAIRING.clear()


def _pair_loop() -> None:
    """`_pair` ning asosiy qismi — PAIRING bayrog'i bilan o'ralgan."""
    error = ""
    while True:
        try:
            picked = _pair_dialog(error)
        except Exception:  # noqa: BLE001 - tkinter yo'q: konsolga tushamiz
            picked = _pair_console()
        if picked is None:
            raise SystemExit("Ulanish bekor qilindi.")
        try:
            url, token, name, stanok = _exchange(*picked)
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
    # Stanok bog'langan bo'lsa aytamiz: skan-forvard AYNAN shu stanokning aktiv
    # sessiyasi nomidan yoziladi — noto'g'ri bog'lanish shu yerda darhol ko'rinadi
    _success_window(name, stanok)


#: Yorliq printerlarining tanish rusumlari — avto-topish shu ro'yxat bo'yicha.
#: RUSUMGA QOTIB QOLMASLIK uchun ro'yxat keng: tsexda GoDEX ham, Xprinter ham
#: bor (Rover). Ro'yxatda yo'q rusum kelsa — PRINTER_NAME env bilan qo'lda
#: ko'rsatiladi (%APPDATA%\MebelixAgent\.env), chop etish yo'li GDI —
#: har qanday Windows drayveri bilan ishlaydi.
_PRINTER_KEYWORDS = ("godex", "xprinter", "gprinter", "tsc", "zebra", "argox", "postek")


def _detect_printer() -> str:
    """PRINTER_NAME berilmasa nomi tanish yorliq-printerga o'xshagan lokal
    printerni topadi — printer almashsa ham config o'zgarmaydi, drayver
    o'rnatilsa bas."""
    try:
        import win32print

        for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
            if any(k in p[2].lower() for k in _PRINTER_KEYWORDS):
                return p[2]
    except Exception:  # noqa: BLE001 — win32 yo'q (Linux) yoki printer topilmadi
        pass
    return ""


def _local_printer_names() -> list[str]:
    """Diagnostika: kompyuterda qanday printerlar ko'rinayapti."""
    try:
        import win32print

        return [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
    except Exception:  # noqa: BLE001
        return []


_load_dotenv()
if not _single_instance():
    _alert(
        "MebeliX",
        "Agent allaqachon fonda ishlayapti — tray'dagi MX belgisiga qarang.\n\n"
        "Yangi kod bilan qayta ulash uchun tray menyusidan "
        "\"Qayta ulash (yangi kod)\" ni tanlang.",
    )
    raise SystemExit(0)
_pair()
# HAR startda qayta yoziladi, faqat pairing'da emas. Ilgari bir marta yozilardi:
# exe keyin ko'chirilsa registry o'lik yo'lga ishora qilib, reboot'dan keyin
# agent turmasdi va o'zini hech qachon tuzatmasdi (Prisadkada aynan shu kuzatilgan).
# Yozuv idempotent va HKCU — arzon, har startda yangilash zarari yo'q.
_register_autostart()

MES_URL = os.environ.get("MES_URL", "ws://localhost:8000")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PRINTER_NAME = os.environ.get("PRINTER_NAME", "") or _detect_printer()
#: Qo'lda berilgan nom har doim ustun; avto-topilgani esa qayta tekshiriladi.
PRINTER_FIXED = bool(os.environ.get("PRINTER_NAME", ""))


def _http_base() -> str:
    """MES_URL ning http(s) shakli (REST chaqiruvlari uchun).

    MES_URL har chaqiruvda qayta o'qiladi: re-pairing manzilni almashtirgan
    bo'lsa log/skan/yangilanish darhol yangi serverga boradi."""
    return MES_URL.replace("wss://", "https://", 1).replace("ws://", "http://", 1).rstrip("/")


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
# Skan-forvard: stanok skaneri (klaviatura-HID) terganini MES'ga ham
# yuborish. SCAN_FORWARD=0 o'chiradi; pynput bo'lmasa o'zi jim o'chadi.
SCAN_FORWARD = os.environ.get("SCAN_FORWARD", "1") != "0"

# Andon: stanok signal ustunini Pico o'qiydi, USB orqali shu agentga beradi.
# Pico bo'lmagan kompyuterda (arra, kromka...) hech narsa qilmaydi — faqat port qidiradi.
ANDON = os.environ.get("ANDON", "1") != "0"
ANDON_PORT = os.environ.get("ANDON_PORT", "")
ANDON_TAKEOVER = os.environ.get("ANDON_TAKEOVER", "1") != "0"
ANDON_QUEUE_FILE = Path(os.environ.get("ANDON_QUEUE_FILE") or (CONFIG_DIR / "andon-queue.jsonl"))
#: ROVER Pico'siga yuboriladigan sozlama. Avtomatik o'chirish 1-bosqichda O'CHIQ:
#: avval qancha bo'sh turish qayd bo'layotgani ko'riladi, taymerlar tsexdagi real
#: ritmga moslanadi, keyingina rele yoqiladi (noto'g'ri o'chirish ishni to'xtatadi).
ROVER_AUTO_SHUTDOWN = os.environ.get("ROVER_AUTO_SHUTDOWN", "0") != "0"
#: Pico shu soniyadan uzun to'xtashni alohida hodisa qilib yozadi. MES'dagi umumiy
#: chegara bilan bir xil (5 daqiqa) — aks holda undan qisqa to'xtash Pico jurnalida
#: umuman ko'rinmasdi.
ROVER_T_REASON = int(os.environ.get("ROVER_T_REASON", "300"))

# Yangi job kelganda flusher darhol uyg'onadi (5s siklni kutmaydi)
FLUSH_EVENT = asyncio.Event()
# Serverga (qayta) ulanildi — self_update darhol tekshiradi. Deploy WS'ni uzadi,
# agent qayta ulanadi: yangi versiya deploy'dan daqiqalar ichida yetib boradi,
# 10 daqiqalik zaxira tekshiruvini kutmaydi.
CONNECTED_EVENT = asyncio.Event()


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
    """Durable local queue — survives agent restarts and power cuts.

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


def _print_png_gdi(img: Any) -> None:
    """Yorliq rasmini (PIL, RGB) Windows drayveri orqali chiqaradi (GibSaw 'Used the
    printer driver' rejimi bilan bir xil yo'l). DEVMODE'da qog'oz 80x60mm ga majburlanadi."""
    import win32con
    import win32gui
    import win32print
    import win32ui
    from PIL import ImageWin

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
        log.error(
            "Yorliq printeri topilmadi — drayver o'rnatilganini tekshiring. Bor printerlar: %s",
            ", ".join(_local_printer_names()) or "yo'q",
        )
        return False
    if not png_b64:
        log.warning(
            "PNG'siz job tashlab yuborildi"
        )  # eski formatdagi yozuv navbatni to'smasin
        return True
    import base64
    import io as _io

    from PIL import Image

    try:
        img = Image.open(_io.BytesIO(base64.b64decode(png_b64))).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        # Buzuq PNG printer xatosi EMAS — qayta urinish uni tuzatmaydi. False qaytsa
        # flusher navbat BOSHIDA to'xtab, orqasidagi hamma yorliqni abadiy to'sardi.
        log.error("Buzuq yorliq tashlab yuborildi (PNG o'qilmadi): %s", exc)
        return True
    try:
        _print_png_gdi(img)
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
    import urllib.request

    while True:
        await asyncio.sleep(30)
        if not LOG_BUFFER or not BRIDGE_TOKEN:
            continue
        lines = list(LOG_BUFFER)
        LOG_BUFFER.clear()
        req = urllib.request.Request(
            f"{_http_base()}/api/v1/bridge-agents/logs",
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
    kichik oyna yo'q.

    Butun tanasi `except Exception` bilan o'ralgan: navbat faylini antivirus
    yoki zaxira dasturi qulflab qo'yishi Windows'da odatiy hol, va ilgari
    o'sha bitta OSError `asyncio.gather` orqali BUTUN agentni (chop etish +
    skan-forvard) o'ldirardi — oynasiz exe hech narsa ko'rsatmasdan yo'q
    bo'lardi. Endi xato logga yoziladi va 5 soniyadan keyin qayta urinamiz."""
    while True:
        try:
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
        except Exception:  # noqa: BLE001 — vazifa o'lmasin, keyingi aylanishda qayta urinadi
            log.exception("Navbatni oqizishda xato — 5s dan keyin qayta urinish")
            await asyncio.sleep(5)
            continue
        # Yangi job kelsa darhol, aks holda 5s da bir (printer tiklanishini kutish)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(FLUSH_EVENT.wait(), timeout=5)
        FLUSH_EVENT.clear()


def _repair() -> None:
    """Token bekor qilingan (admin "yangi kod" yoki "o'chirish" bosgan): saqlangan
    sozlamani tozalab, yangi kod so'raymiz. Busiz foydalanuvchi .env ni qo'lda
    o'chirishga majbur bo'lardi - agent esa fonda ishlab turgani uchun avval uni
    Task Manager orqali yopishi kerak edi (oyna yo'q, mutex ikkinchi nusxani
    qo'ymaydi). Bekor qilinsa `_pair` SystemExit ko'taradi — `uplink` uni ushlab
    30 s kutadi va qayta urinadi (agent to'xtamaydi, oyna yana ochiladi)."""
    global BRIDGE_TOKEN, MES_URL

    # .env ATAYIN o'chirilmaydi: muvaffaqiyatli pairing uni baribir qayta yozadi,
    # dialog bekor qilinsa/agent o'chirilsa esa eski holat saqlanib qoladi
    # (token baribir bekor — keyingi ishga tushishda yana so'raladi)
    os.environ.pop("BRIDGE_TOKEN", None)
    _pair()
    BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
    MES_URL = os.environ.get("MES_URL", MES_URL)


_connected_once = False
#: Tray belgisi rangi uchun jonli holat (uplink yozadi, tray o'qiydi)
CONNECTED = False


def _notify_connected() -> None:
    """Birinchi muvaffaqiyatli ulanishda 5 soniyalik xabar (o'zi yopiladi) —
    monoblok yonganda arrachi agent tayyorligini shu yerdan biladi; bosish
    shart emas, ish oqimini to'smaydi. Alohida threadda: asyncio loop
    (flusher/uplink) bloklanmasin."""
    import ctypes

    # Skan-forvard stansiyasida (printer yo'q) "chek chiqarishga tayyor" yolg'on
    # bo'lardi — xabar rejimga qarab tanlanadi
    holat = (
        "Chek chiqarishga tayyor."
        if PRINTER_NAME
        else "Skan-forvard rejimi (printer ulanmagan)."
    )

    def show() -> None:
        with contextlib.suppress(Exception):
            # MessageBoxTimeoutW — timeout bilan yopiladigan MessageBox
            # (XP dan beri bor); topilmasa xabar shunchaki chiqmaydi, log yetadi
            ctypes.windll.user32.MessageBoxTimeoutW(  # type: ignore[attr-defined]
                0,
                f"MebeliX MES agent serverga ulandi (v{AGENT_VERSION}).\n{holat}",
                "MebeliX",
                0x00000040 | 0x00040000,  # MB_ICONINFORMATION | MB_TOPMOST
                0,
                5000,  # 5 soniyada o'zi yopiladi
            )

    threading.Thread(target=show, daemon=True).start()


async def uplink() -> None:
    """Serverga doimiy outbound ulanish; uzilsa 5s backoff bilan qayta ulanadi.

    Token FAQAT server 401/403 bilan KETMA-KET 2 marta rad etgandagina bekor
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
                global CONNECTED
                CONNECTED = True
                CONNECTED_EVENT.set()
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
                                "Yorliq printeri topilmadi — job rad etildi, "
                                "serverda navbatda qoladi (instance %s). "
                                "Kompyuterdagi printerlar: %s. Kerakligini "
                                "PRINTER_NAME bilan .env da ko'rsatish mumkin.",
                                msg.get("instance_id"),
                                ", ".join(_local_printer_names()) or "yo'q",
                            )
                            continue
                        if already_seen(job_id):
                            # Ack yo'lda yo'qolgan: server qayta yubordi. Faylga
                            # ikkinchi marta yozsak ikkita yorliq chiqardi.
                            await ws.send(json.dumps({"ok": True}))
                            log.info("Takroriy job tashlandi: %s", job_id)
                            continue
                        # Avval diskka — keyin belgi, keyin ack. Server ackdan
                        # keyin jobni unutadi; yozish yiqilsa belgi
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
            CONNECTED = False
            status = exc.response.status_code
            if status in (401, 403):
                reject_streak += 1
                if reject_streak >= 2:
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
                    # SystemExit himoyasi: dialog bekor qilinsa `_pair` uni
                    # ko'taradi va `except Exception` uni TUTMAYDI (BaseException)
                    # — butun agent jimgina o'lardi. Endi eski holat saqlanadi
                    # va qayta urinaveradi (tray menyusidagi yo'l ham ochiq).
                    try:
                        await asyncio.to_thread(_repair)
                    except SystemExit:
                        log.warning("Qayta ulanish bekor qilindi — agent ishlashda davom etadi")
                        await asyncio.sleep(30)
                    continue
                log.warning(
                    "Handshake rad etildi (HTTP %s, %d/2) — 3s dan keyin qayta urinish",
                    status,
                    reject_streak,
                )
                await asyncio.sleep(3)
                continue
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
            CONNECTED = False
            # `reject_streak` BU YERDA NOLGA TUSHIRILMAYDI. Ilgari tushirilardi
            # va notekis tsex tarmog'ida ketma-ket 403 hech yig'ilmasdi: 403 ->
            # TCP timeout (streak=0) -> 403 -> ... — bekor qilingan agent yangi
            # kod SO'RAMAY qolardi. Streak faqat MUVAFFAQIYATLI ulanishda va
            # auth bo'lmagan HTTP javobida nolga tushadi — o'shanda token
            # aybdor emasligi aniq.
            log.warning("Ulanish uzildi (%s) — 5s dan keyin qayta urinish", exc)
            await asyncio.sleep(5)


def start_scan_forward() -> None:
    """Stanok skaneri o'qiganini MES'ga ham yuboradi.

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

    import ctypes
    import re
    import time as _time
    import urllib.error
    import urllib.request

    # MES terminali fokusda bo'lsa forvard YUBORILMAYDI: forvard Nanxing'ga ketayotgan
    # skanning nusxasi, terminal fokusda bo'lsa skanni brauzerning O'ZI yozadi
    # (2026-09-12 hodisasi — docs/09). Sarlavha QISM-SATR bo'yicha: brauzer oynaga
    # " - Google Chrome" quyrug'ini qo'shadi; TABLO va kirish ekrani ataylab mos kelmaydi.
    terminal_title = "Terminal | MebeliX"

    def _terminal_fokusda() -> bool:
        """Fokusdagi oyna MES terminalimi. Xato bo'lsa — False (skan yo'qolmasin)."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False
            uzunlik = user32.GetWindowTextLengthW(hwnd)
            bufer = ctypes.create_unicode_buffer(uzunlik + 1)
            user32.GetWindowTextW(hwnd, bufer, uzunlik + 1)
            return terminal_title in bufer.value
        except Exception:  # noqa: BLE001 — Windows'siz muhit yoki API xatosi
            return False

    scan_re = re.compile(r"^[0-9A-Za-z_\-]{6,64}$")
    # Beyjik (UUID) — detal QR'i EMAS: uni terminalning o'z oqimi qabul qiladi.
    # Yubormaymiz, aks holda server uni detal deb tekshirib rad etardi va
    # operator qonuniy beyjik skanida qizil banner + xato ovozini olardi.
    badge_re = re.compile(
        r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
    )
    buf: list[str] = []
    first = [0.0]
    last = [0.0]

    def send(qr: str) -> None:
        req = urllib.request.Request(
            f"{_http_base()}/api/v1/bridge-agents/scan",
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
                if badge_re.match(s):
                    log.info("Beyjik skani — MES'ga yuborilmadi")
                    return
                if _terminal_fokusda():
                    log.info("MES terminali fokusda — forvard yuborilmadi: %s", s)
                    return
                threading.Thread(target=send, args=(s,), daemon=True).start()
            return
        ch = getattr(key, "char", None)
        if ch:
            buf.append(ch)

    keyboard.Listener(on_press=on_press, daemon=True).start()
    log.info("Skan-forvard yoqildi — skaner o'qigani MES'ga ham boradi")


# ── Andon: stanok signal ustuni (Pico, USB) ──────────────────────────────────
#
# Pico (MicroPython, `prisadka-mes-nanxing` firmware) stanok chiroqlarini o'qiydi
# va USB serial orqali qatorlar yuboradi:
#     Pico -> agent :  MES event {json}   holat o'zgarishi yoki detal sikli
#                      MES state {json}   snapshot (har 30 s)
#     agent -> Pico :  PING               har 5 s — Pico 15 s eshitmasa o'zini
#                                         oflayn deb hisoblab buferga yig'adi
# Boshqa qatorlar (print, traceback) — Pico jurnali.
#
# O'qish OQIMI (thread) hodisani diskdagi navbatga yozadi, `andon_shipper`
# korutinasi navbatni serverga partiyalab yuboradi. Chek chop etish va skan-forvard
# yo'llariga TEGILMAYDI: alohida fayl, alohida endpoint, har bosqich o'z xatosini
# o'zi ushlaydi — andon yiqilsa ham chek chiqaveradi.

_PICO_VID = 0x2E8A  # Raspberry Pi (RP2040)
#: Uch xil Pico bor va hammasi shu VID bilan keladi:
#:   PRISADKA — signal ustuni, qatorlari "MES event {...}" ko'rinishida (firmware `fsm.py`);
#:   KROMKA   — uzunlik o'lchash stansiyasi, YALANG'OCH JSON qator: {"ev":"olchov",...};
#:   ROVER    — CNC 2130, ikki tomonlama JSON: {"t":"hello"|"state"|"event"|...}.
#: Tur BIRINCHI tushunarli qatordan aniqlanadi va har tushunarli qator uni qayta belgilaydi.
#: `ANDON_TUR` env faqat boshlang'ich taxmin — qurilma hali jim turganda HB/PING/vaqt
#: yuborish oralig'ini belgilaydi; qaysi portni o'qishni esa `ANDON_PORT` hal qiladi.
_TUR_PRISADKA, _TUR_KROMKA, _TUR_ROVER = "prisadka", "kromka", "rover"
#: Kromka Pico'si `XOST_MS` = 3 s ichida BUYRUQ ko'rmasa o'zini «stansiya yo'q» deb
#: hisoblaydi va hodisalarni RAM ga yig'a boshlaydi (300 ta, keyin eng eskisi tushadi).
#: Shuning uchun unga har soniyada `HB` yuboriladi; prisadkaga 5 soniyalik `PING` yetadi.
_ANDON_PING_S = 5
_KROMKA_HB_S = 1
#: Kromkadan MES ga yoziladigan hodisalar (`tiqilish` — proshivka v1.16 dan: detallar
#: birga o'tgan yoki datchik ostida turib qolgan, o'lchov chiqmagan).
#: `holat`/`pong`/`kal`/`kalib_rejim`/`yigilgan`
#: — javob va diagnostika qatorlari, tarixga kerak emas.
#: v1.20 dan kelgan `sig` (lampa fazasi — MES tovushni shundan boshlaydi) va
#: `yigilgan` (xotira hisoboti) ATAYLAB ro'yxatda yo'q: ular MESga yozilmaydi.
_KROMKA_EVENTS = ("olchov", "ogoh", "uskuna", "tezlik", "avariya_toxtash", "boot", "tiqilish")
#: ROVER (CNC 2130) Pico'si IKKI TOMONLAMA gaplashadi — kromkadan farqi shu. Undan
#: hodisa olish uchun unga har 10 soniyada kompyuter vaqti yuborilishi SHART: 30 s
#: jim qolsa u «kompyuter yo'q» deb biladi va hodisalarni fleshga yig'a boshlaydi.
#: Hodisa TASDIQ (`ack`) kelmaguncha Pico xotirasida qoladi va har 10 s qayta keladi.
#: Tasdiq faqat SERVER yozgandan keyin beriladi (`andon_shipper`), ya'ni internet
#: uzilsa hodisa Pico'da ham, navbatda ham saqlanib turadi.
_ROVER_TIME_S = 10
#: Rover hodisasining `seq` i fleshda saqlanadi va hech qachon takrorlanmaydi —
#: shuning uchun serverdagi `(machine_id, session, seq)` kaliti aynan shu juftlik
#: bilan ishlaydi va qayta yuborilgan hodisa jimgina tashlanadi.
_ROVER_SESSION = "rover"
#: `andon_shipper` bir so'rovda yuboradigan eng ko'p hodisa.
_ANDON_BATCH = 200
#: Internet uzoq yo'q bo'lsa navbat shundan oshmaydi — eng eskilari tashlanadi
#: (bitta stanok kuniga ~1000 hodisa beradi, ya'ni bu ~20 kunlik zaxira).
_ANDON_QUEUE_MAX = 20000
_ANDON_WARN_EVERY_S = 600
_PRISADKAMES_EXE = "PrisadkaMES.exe"
#: Eski PrisadkaMES.exe bir marta to'xtatilgach qo'yiladi: kimdir uni keyin ataylab
#: qayta o'rnatsa agent uni qayta-qayta o'ldirib yurmaydi, faqat logga yozadi.
_ANDON_TAKEOVER_MARK = CONFIG_DIR / "andon-takeover.done"
_CREATE_NO_WINDOW = 0x08000000

ANDON_LOCK = threading.Lock()
#: Aniqlangan Pico turi va kromka hodisalari uchun kalit. Kromka firmware'i
#: prisadkadagi `session`/`seq` ni yubormaydi, shuning uchun ularni AGENT beradi:
#: `session` har ulanishda yangi, `seq` uning ichida uzluksiz — serverdagi
#: `(machine_id, session, seq)` unikal indeksi qayta yuborilgan partiyani o'zi tashlaydi.
ANDON_TUR: dict[str, Any] = {"tur": os.environ.get("ANDON_TUR", "").strip().lower() or None,
                             "session": "", "seq": 0}
#: Stanokning jonli holati — o'qish oqimi yozadi, `andon_shipper` o'qiydi (lock ostida)
ANDON_CURRENT: dict[str, Any] = {}
#: Pico porti hozir ochiqmi (tray va jonli holat uchun)
ANDON_CONNECTED = False


def _andon_enqueue(event: dict[str, Any]) -> None:
    """Hodisani navbat oxiriga yozadi. fsync — tok o'chsa ham hodisa diskda qoladi."""
    with ANDON_LOCK, ANDON_QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _andon_write(lines: list[str]) -> None:
    """Navbatni atomik qayta yozadi. Chaqiruvchi ANDON_LOCK ni ushlab turadi."""
    tmp = ANDON_QUEUE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in lines))
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(ANDON_QUEUE_FILE)


def _andon_peek(limit: int) -> tuple[list[dict[str, Any]], int]:
    """Navbat boshidan `limit` ta qator: (hodisalar, o'qilgan qatorlar soni).

    Buzuq qator ham SANALADI — ack'da birga o'chadi, lekin serverga yuborilmaydi."""
    with ANDON_LOCK:
        if not ANDON_QUEUE_FILE.exists():
            return [], 0
        lines = ANDON_QUEUE_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > _ANDON_QUEUE_MAX:
            ortiqcha = len(lines) - _ANDON_QUEUE_MAX
            lines = lines[ortiqcha:]
            _andon_write(lines)
            log.warning("Andon navbati to'ldi — eng eski %d ta hodisa tashlandi", ortiqcha)
    batch = lines[:limit]
    events: list[dict[str, Any]] = []
    for line in batch:
        with contextlib.suppress(ValueError):
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
    return events, len(batch)


def _andon_ack(count: int) -> None:
    """Server qabul qilgan partiyani navbat boshidan olib tashlaydi.

    Shu orada oxiriga qo'shilganlar SAQLANADI: o'qish oqimi faqat oxiriga yozadi va
    ikkala tomon ham ANDON_LOCK ostida ishlaydi."""
    if count <= 0:
        return
    with ANDON_LOCK:
        if not ANDON_QUEUE_FILE.exists():
            return
        lines = ANDON_QUEUE_FILE.read_text(encoding="utf-8").splitlines()
        _andon_write(lines[count:])


#: KROMKA Pico'si bilan tasdiq (ACK) holati — proshivka v1.22 dan.
#: Har muhim hodisa `xb` (yonish belgisi) va `xq` (shu yonishdagi raqami) bilan
#: keladi va Pico uni `ACK <xb> <xq>` kelmaguncha HAR 5 SONIYADA QAYTA yuboradi.
#: Tasdiqsiz agent har takrorni yangi hodisa deb yozardi: bitta o'lchov daqiqada
#: 12 marta sanalib, Performance ham, o'lchov tarixi ham shishib ketardi.
KROMKA: dict[str, Any] = {
    "xb": None,      # Pico'ning joriy yonish belgisi (o'zgarsa hisob noldan)
    "seen": 0,       # navbatga olingan eng katta `xq` — takror shundan past keladi
    "ack": set(),    # server YOZGAN, lekin Pico'ga hali aytilmagan `xq` lar
}


def _kromka_kalit() -> tuple[str, int]:
    """Kromka hodisasiga (session, seq) beradi — ESKI firmware ularni yubormaydi.

    v1.22 dan kalit Pico'ning o'zidan keladi (`xb`/`xq`), bu esa faqat undan
    oldingi proshivkalar uchun zaxira yo'l."""
    if not ANDON_TUR["session"]:
        ANDON_TUR["session"] = uuid4().hex[:8]
        ANDON_TUR["seq"] = 0
    ANDON_TUR["seq"] += 1
    return str(ANDON_TUR["session"]), int(ANDON_TUR["seq"])


#: Kromka Pico'sidan joriy holat SO'RALADIGAN oraliq. `uskuna` hodisasi faqat RUN
#: kirishi O'ZGARGANDA keladi — stanok ertalab yoqilgan bo'lsa-yu agent kunduzi
#: ulansa, hech qanday hodisa kelmaydi va MES «ma'lumot yo'q» deb qolardi.
#: `HOLAT` javobidagi `uskuna` — o'sha lahzadagi haqiqiy holat.
_KROMKA_HOLAT_S = 30


def _kromka_holat(data: dict[str, Any]) -> None:
    """`HOLAT` javobi: joriy holatni o'qiydi va O'ZGARGAN bo'lsa hodisa qilib yozadi.

    O'zgarmagan bo'lsa hech narsa yozilmaydi — aks holda har 30 soniyada bir xil
    yozuv tushib, oraliqlar maydalanib ketardi."""
    if "uskuna" not in data:
        return
    if data.get("ver"):
        ANDON_TUR["ver"] = str(data["ver"])
    holat = 1 if data.get("uskuna") else 0
    if ANDON_TUR.get("uskuna") == holat:
        return
    ANDON_TUR["uskuna"] = holat
    # `manba` — bu yozuv chekka o'zgarishidan emas, SO'ROVDAN olingani ko'rinib tursin
    _kromka_line({"ev": "uskuna", "holat": holat, "manba": "holat"})


def _kromka_line(data: dict[str, Any]) -> None:
    """KROMKA stansiyasi Pico'sidan bitta hodisa (`{"ev": ...}`).

    Hodisa xom holida uzatiladi (server `payload` ga to'liq yozadi), agent faqat
    uchta narsa qo'shadi: `type` (server sxemasi shuni kutadi), `ts` va `(session, seq)`.

    `eski_ms` — hodisa Pico xotirasida qancha kutgani (stansiya/agent uzilgan payt).
    Vaqt shundan tiklanadi, aks holda tun bo'yi yig'ilgani bitta daqiqaga tiqilardi.
    """
    ev = str(data.get("ev") or "")
    if ev not in _KROMKA_EVENTS:
        return
    now = int(time.time())
    data["type"] = ev
    data["ts"] = now - int(data.get("eski_ms") or 0) // 1000
    kalit = _kromka_xbxq(data)
    if kalit is None:
        return                       # Pico takror yuborgan — navbatda allaqachon bor
    data["session"], data["seq"] = kalit
    _andon_enqueue(data)

    # Jonli holat: kromkada chiroq yo'q — uskuna kirishi (RUN) bor. Ishlayapti =
    # PROCESSING, to'xtagan = OFF (bizda OFF darhol to'xtash deb sanaladi, sariq
    # chiroqning mikro-to'xtash chegarasi bu yerda ma'nosiz).
    if ev == "uskuna":
        ANDON_TUR["uskuna"] = 1 if data.get("holat") else 0
        holat = "PROCESSING" if data.get("holat") else "OFF"
        with ANDON_LOCK:
            if ANDON_CURRENT.get("state") != holat:
                ANDON_CURRENT["since"] = int(data["ts"])
            ANDON_CURRENT.update(state=holat, lamps={})
    elif ev == "tezlik":
        with ANDON_LOCK:
            ANDON_CURRENT["part_count"] = None


#: ROVER Pico'si bilan aloqa holati. O'qish OQIMI va yuborish TASKI ikkalasi ham
#: tegadi — har ikkalasi `ANDON_LOCK` ostida.
ROVER: dict[str, Any] = {
    "boot": None,      # Pico yuklanishlar soni (hello'dan); None — hello hali kelmagan, sozlama keyin
    "ack_upto": 0,     # server YOZGAN eng katta uzluksiz seq
    "ack_sent": 0,     # Pico'ga aytilgan oxirgi tasdiq
    "config": False,   # sozlama shu ulanishda yuborildimi
    "holat": None,     # oxirgi holat (PROCESSING/IDLE/OFF) — faqat O'ZGARISH hodisaga aylanadi
    "seen": 0,         # navbatga olingan eng katta hodisa seq'i
}


def _rover_line(data: dict[str, Any]) -> None:
    """ROVER (CNC 2130) Pico'sidan bitta xabar: `hello` / `state` / `event` / `log`.

    Bu firmware kromkadan boshqacha ishlaydi: u DAVOMIYLIKNI o'zi o'lchaydi va
    tugagan davrni tayyor hodisa qilib beradi (`POWER_ON`, `SPINDLE_IDLE`,
    `AUTO_SHUTDOWN` ...). Ular xom holida serverga uzatiladi — tasdiqlanmaguncha
    Pico ularni qayta-qayta yuboraveradi, ya'ni agent o'chib qolsa ham yo'qolmaydi.

    Jonli holat (span va «ishladi» vaqti) esa `state` xabaridan olinadi: `run`
    o'zgarganda kromkadagi bilan BIR XIL `uskuna` hodisasi yoziladi, shuning uchun
    serverdagi to'xtash/OEE zanjiri qayta yozilmaydi."""
    kind = str(data.get("t") or "")
    if kind == "hello":
        with ANDON_LOCK:
            ROVER["boot"] = data.get("boot")
            # Pico allaqachon tasdiqlangan hodisalarni qayta yubormaydi — biz ham
            # o'sha joydan davom etamiz, aks holda eski seq'ni qayta tasdiqlardik
            ROVER["ack_upto"] = ROVER["ack_sent"] = int(data.get("last_ack") or 0)
            # Tasdiqlanganidan keyingilari qayta keladi — o'shalardan boshlab qabul qilamiz
            ROVER["seen"] = int(data.get("last_ack") or 0)
            ROVER["config"] = False
            ROVER["holat"] = None
        log.info(
            "Andon: ROVER Pico'si — %s, yuklanish #%s, seq=%s, tasdiqlangan=%s%s",
            data.get("machine"), data.get("boot"), data.get("seq"), data.get("last_ack"),
            ", vaqt so'radi" if data.get("need_time") else "",
        )
    elif kind == "state":
        _rover_state(data)
    elif kind == "event":
        _rover_event(data)
    elif kind == "log":
        log.info("[pico] %s", str(data.get("msg"))[:200])


def _rover_state(data: dict[str, Any]) -> None:
    """Har 10 soniyalik holat xabari — jonli holat va RUN o'zgarishi.

    Hodisa faqat O'ZGARISHDA yoziladi: aks holda kuniga 8000 dan ortiq bir xil
    qator bazaga tushardi (kromkada ham shu qoida)."""
    pwr = 1 if data.get("pwr") else 0
    run = 1 if data.get("run") else 0
    holat = 1 if (pwr and run) else 0
    # Stanok o'chiq bo'lsa OFF; yoqiq-u shpindel aylanmasa IDLE (bo'sh turish);
    # aylanayotgan bo'lsa PROCESSING. Ekrandagi nomlar `lib/mes.ts` dan.
    state = "PROCESSING" if run else ("IDLE" if pwr else "OFF")
    now = int(time.time())
    with ANDON_LOCK:
        # O'zgarish UCHALA holat bo'yicha (holat 0/1 emas): server yoqiq-u shpindel
        # to'xtagan stanokni IDLE, o'chiqni OFF deb hisoblaydi (`andon.uskuna_state`).
        # Faqat 0/1 bo'yicha yozilsa IDLE → OFF (stanok o'chirildi) hech qachon kelmasdi.
        oldingi = ROVER["holat"]
        ROVER["holat"] = state
        if ANDON_CURRENT.get("state") != state:
            ANDON_CURRENT["since"] = now
        ANDON_CURRENT.update(state=state, lamps={}, part_count=None)
    if oldingi == state:
        return
    session, seq = _kromka_kalit()
    _andon_enqueue({
        "type": "uskuna", "ev": "uskuna", "holat": holat, "manba": "rover",
        "pwr": pwr, "run": run, "home": 1 if data.get("home") else 0,
        "maint": 1 if data.get("maint") else 0, "relay": 1 if data.get("relay") else 0,
        "idle_sec": data.get("idle_sec"), "on_sec": data.get("on_sec"),
        "ts": now, "session": session, "seq": seq,
    })


def _rover_event(data: dict[str, Any]) -> None:
    """Pico o'lchab tugatgan davr (`POWER_ON`, `SPINDLE_IDLE`, `AUTO_SHUTDOWN` ...).

    Xom holida saqlanadi: `seq` Pico'niki (takrorlanmaydi), `session` esa doimiy
    `rover` — server takrorni o'zi tashlaydi. Vaqt: hodisa TUGAGAN payt, Pico soati
    noma'lum bo'lsa (`start`/`end` = null) — hozirgi vaqt, davomiylik esa xabarning
    ichida qoladi."""
    seq = data.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq <= 0:
        return
    # Tasdiq kelmaguncha Pico o'sha hodisani har 10 soniyada QAYTA yuboradi — navbatga
    # bir marta olinadi. Serverdagi unikal indeks ham tashlardi, lekin u paytgacha
    # navbat va trafik bekorga to'lardi.
    with ANDON_LOCK:
        if seq <= int(ROVER["seen"]):
            return
        ROVER["seen"] = seq
    data = dict(data)
    # Pico hodisaning turini `type` da beradi (POWER_ON, SPINDLE_IDLE ...), server
    # sxemasi esa `type` ni O'ZI uchun band qilgan — asl turi `rover_type` da qoladi,
    # aks holda «qanday hodisa» degan asosiy ma'lumot yo'qolardi.
    data["rover_type"] = data.get("type")
    data["type"] = "rover"
    data["session"] = _ROVER_SESSION
    data["seq"] = seq
    data["ts"] = _rover_ts(data.get("end")) or int(time.time())
    _andon_enqueue(data)


def _rover_ts(iso: Any) -> int | None:
    """Pico bergan mahalliy vaqt (`2026-09-15T14:32:11`) — unix soniyaga."""
    if not isinstance(iso, str) or len(iso) < 19:
        return None
    try:
        return int(time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")))
    except (ValueError, OverflowError):
        return None


def _kromka_xbxq(data: dict[str, Any]) -> tuple[str, int] | None:
    """(session, seq) — v1.22 da Pico'ning `xb`/`xq` sidan, eskisida agentdan.

    `None` — bu hodisa allaqachon navbatga olingan (Pico tasdiq kutib qayta
    yuborgan). Serverdagi unikal indeks ham uni tashlardi, lekin u paytgacha
    navbat va trafik bekorga to'lardi."""
    xb, xq = data.get("xb"), data.get("xq")
    if not isinstance(xb, str) or not xb or isinstance(xq, bool) or not isinstance(xq, int) or xq <= 0:
        return _kromka_kalit()
    with ANDON_LOCK:
        if KROMKA["xb"] != xb:
            # Pico qayta yongan: raqamlar 1 dan boshlanadi, eski tasdiqlar ham keraksiz
            KROMKA.update(xb=xb, seen=0, ack=set())
        if xq <= int(KROMKA["seen"]):
            return None
        KROMKA["seen"] = xq
    return xb[:16], xq


def _kromka_acked(events: list[dict[str, Any]]) -> None:
    """Server yozgan kromka hodisalari — keyingi `ACK` uchun navbatga."""
    with ANDON_LOCK:
        xb = KROMKA["xb"]
        if not xb:
            return
        for e in events:
            seq = e.get("seq")
            if e.get("session") == str(xb)[:16] and isinstance(seq, int) and not isinstance(seq, bool):
                KROMKA["ack"].add(seq)


#: Bitta `ACK` qatoriga sig'adigan raqamlar soni. Pico bir qadamda 40 tagacha
#: yozuvni qayta yuboradi — javob ham shuncha bo'lsa yetadi, qator ham qisqa qoladi.
_KROMKA_ACK_MAX = 40


def _kromka_ack(port: Any) -> None:
    """Server YOZGAN hodisalarni Pico'ga tasdiqlaydi — u shundan keyin o'chiradi.

    Tasdiq serverdan oldin berilsa, internet uzilgan paytdagi o'lchov Pico'da
    ham o'chib, bizda ham yozilmay yo'qolardi (rover bilan bir xil qoida)."""
    with ANDON_LOCK:
        xb = KROMKA["xb"]
        if not xb or not KROMKA["ack"]:
            return
        raqamlar = sorted(KROMKA["ack"])[:_KROMKA_ACK_MAX]
        KROMKA["ack"].difference_update(raqamlar)
    port.write(f"ACK {xb} {' '.join(str(q) for q in raqamlar)}\n".encode())


def _andon_line(text: str) -> None:
    """Pico'dan kelgan bitta qator — uchala firmware ham shu yerdan o'tadi.

    Tur BIRINCHI tushunarli qatordan aniqlanadi: prisadka `MES ...`, kromka
    `{"ev":...}`, rover `{"t":...}`. Aniqlangach `_andon_session` PING/HB/vaqt
    yuborishini shunga moslaydi."""
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            log.warning("Andon: buzuq JSON qator tashlandi: %s", text[:120])
            return
        if not isinstance(data, dict):
            return
        # Ikkala JSON firmware'i ham `{` bilan boshlanadi, kalit so'zi farq qiladi:
        # kromka `{"ev": ...}`, rover `{"t": ...}`.
        if isinstance(data.get("t"), str):
            if ANDON_TUR["tur"] != _TUR_ROVER:
                ANDON_TUR["tur"] = _TUR_ROVER
                log.info("Andon: ROVER (CNC 2130) Pico'si aniqlandi")
            _rover_line(data)
            return
        if "ev" not in data:
            return
        if ANDON_TUR["tur"] != _TUR_KROMKA:
            ANDON_TUR["tur"] = _TUR_KROMKA
            log.info("Andon: KROMKA stansiyasi Pico'si aniqlandi")
        if data.get("ev") == "holat":
            _kromka_holat(data)
        else:
            _kromka_line(data)
        return
    if not text.startswith("MES "):
        if text:
            log.info("[pico] %s", text[:200])
        return
    if ANDON_TUR["tur"] != _TUR_PRISADKA:
        ANDON_TUR["tur"] = _TUR_PRISADKA
        log.info("Andon: PRISADKA signal ustuni Pico'si aniqlandi")
    try:
        _, kind, payload = text.split(" ", 2)
        data = json.loads(payload)
    except ValueError:
        log.warning("Andon: buzuq qator tashlandi: %s", text[:120])
        return
    if not isinstance(data, dict):
        return
    now = int(time.time())
    if kind == "event":
        # USB rejimda Pico soatsiz (`ts: 0`) — hodisa vaqti shu yerda qo'yiladi.
        # `age_ms` (firmware yuborsa) — hodisa Pico buferida qancha kutib turgani.
        if not data.get("ts"):
            data["ts"] = now - int(data.get("age_ms") or 0) // 1000
        _andon_enqueue(data)
        if data.get("type") == "state" and data.get("state"):
            with ANDON_LOCK:
                ANDON_CURRENT.update(state=str(data["state"]), since=int(data["ts"]), lamps=data.get("lamps") or {})
    elif kind == "state":
        state = str(data.get("state") or "")
        if not state:
            return
        with ANDON_LOCK:
            # Holat o'zgarmagan bo'lsa boshlanish vaqti SAQLANADI: `since_s` butun
            # soniya, har snapshotda qayta hisoblansa vaqt ±1 s sakrab, server har
            # 30 soniyada "holat o'zgardi" deb ekranlarga xabar tarqatardi.
            if ANDON_CURRENT.get("state") != state:
                ANDON_CURRENT["since"] = now - int(data.get("since_s") or 0)
            ANDON_CURRENT.update(state=state, lamps=data.get("lamps") or {}, part_count=data.get("part_count"))


def _rover_send(port: Any, obj: dict[str, Any]) -> None:
    port.write((json.dumps(obj) + "\n").encode())


def _rover_time(port: Any) -> None:
    """Kompyuter vaqti — Pico'da soat moduli yo'q, kun vaqti faqat shundan keladi."""
    lt = time.localtime()
    _rover_send(port, {"t": "time", "ts": [lt.tm_year, lt.tm_mon, lt.tm_mday,
                                           lt.tm_hour, lt.tm_min, lt.tm_sec]})


def _rover_ack(port: Any) -> None:
    """Server YOZGAN hodisalarni Pico'ga tasdiqlaydi (u shundan keyin ularni o'chiradi).

    Tasdiq serverdan oldin berilsa, internet uzilgan paytdagi hodisa Pico'da ham
    o'chib, bizda ham yozilmay yo'qolardi."""
    with ANDON_LOCK:
        upto, sent = int(ROVER["ack_upto"]), int(ROVER["ack_sent"])
        if upto <= sent:
            return
        ROVER["ack_sent"] = upto
    _rover_send(port, {"t": "ack", "seq": upto})


def _rover_config(port: Any) -> None:
    """Sozlama — har ulanishda bir marta. Pico uni fleshga saqlaydi.

    1-bosqichda avtomatik o'chirish O'CHIQ: stanokni o'chirish qaroriga o'tishdan
    oldin tsexda qancha bo'sh turish yig'ilayotgani ko'riladi."""
    with ANDON_LOCK:
        if ROVER["config"] or ROVER["boot"] is None:
            return
        ROVER["config"] = True
    _rover_send(port, {"t": "config", "t_reason": ROVER_T_REASON,
                       "auto_shutdown": ROVER_AUTO_SHUTDOWN})
    log.info("Andon: ROVER sozlamasi yuborildi (t_reason=%s, auto_shutdown=%s)",
             ROVER_T_REASON, ROVER_AUTO_SHUTDOWN)


def _andon_session(port: Any) -> None:
    """Ochiq port bilan ishlash: yurak urishi yuborish va qatorlarni o'qish.

    Tur ANIQLANGUNCHA har soniyada `PING`: kromka Pico'si uni ham «stansiya tirik»
    deb hisoblaydi (uning chegarasi 3 s), prisadka esa `pong` bilan javob beradi.
    Tur aniqlangach oraliq o'ziga moslanadi — kromkaga `HB` (1 s), prisadkaga
    `PING` (5 s)."""
    global ANDON_CONNECTED
    ANDON_CONNECTED = True
    ANDON_TUR["session"] = ""          # har ulanish — yangi kalit
    ANDON_TUR["uskuna"] = None         # holat noma'lum: birinchi javob yoziladi
    with ANDON_LOCK:
        ROVER.update(boot=None, config=False, holat=None, seen=0)
        # Pico'ning yonish belgisi o'zgarmagan bo'lishi mumkin (faqat kabel uzilgan):
        # `seen` ni saqlaymiz, aks holda u qayta yuborayotgan hammasi takror yozilardi
        KROMKA["ack"] = set()
    next_ping = 0.0
    next_holat = 0.0
    pending = b""
    try:
        while True:
            now = time.monotonic()
            if ANDON_TUR["tur"] == _TUR_ROVER:
                # ROVER: `PING`/`HB` o'rniga kompyuter VAQTI. U ham «kompyuter shu
                # yerda» degan belgi: 30 s jim qolsak Pico hodisalarni fleshga yig'a
                # boshlaydi. Tasdiq va sozlama ham shu yerdan ketadi.
                if now >= next_ping:
                    _rover_time(port)
                    next_ping = now + _ROVER_TIME_S
                _rover_ack(port)
                _rover_config(port)
            elif now >= next_ping:
                kromka = ANDON_TUR["tur"] == _TUR_KROMKA
                port.write(b"HB\n" if kromka else b"PING\n")
                next_ping = now + (
                    _KROMKA_HB_S if kromka else (_ANDON_PING_S if ANDON_TUR["tur"] else _KROMKA_HB_S)
                )
            # Joriy holatni so'rab turish — faqat kromkada (prisadka o'zi har 30 s
            # snapshot yuboradi)
            if ANDON_TUR["tur"] == _TUR_KROMKA:
                if now >= next_holat:
                    port.write(b"HOLAT\n")
                    next_holat = now + _KROMKA_HOLAT_S
                _kromka_ack(port)
            # timeout 0.2 s: vaqt tugasa YARIM qator ham qaytishi mumkin — yig'ib boramiz
            chunk = port.readline()
            if not chunk:
                continue
            pending += chunk
            if not pending.endswith(b"\n"):
                if len(pending) > 8192:  # yangi qatorsiz shovqin
                    pending = b""
                continue
            line, pending = pending, b""
            try:
                _andon_line(line.decode("utf-8", "replace").strip())
            except Exception:  # noqa: BLE001 — bitta qator o'qishni to'xtatmasin
                log.exception("Andon: qatorni qayta ishlashda xato")
    except Exception as exc:  # noqa: BLE001 — kabel sug'urildi yoki Pico qayta yuklandi
        log.warning("Andon: Pico bilan aloqa uzildi (%s)", exc)
    finally:
        with ANDON_LOCK:
            ANDON_CONNECTED = False
            # Qayta ulanganda ESKI holat (va uning boshlanish vaqti) serverga ketmasin —
            # Pico qayta yuklangan bo'lishi mumkin; yangi holat birinchi snapshotdan olinadi
            ANDON_CURRENT.clear()
        with contextlib.suppress(Exception):
            port.close()


def _andon_takeover() -> bool:
    """Port band va uni eski PrisadkaMES.exe ushlab turgan bo'lsa — to'xtatib, avtozapuskdan oladi.

    Andon ilgari alohida PrisadkaMES.exe (Telegram bot bilan) orqali o'qilardi; endi
    Pico'ni shu agent o'qiydi, bitta COM portni esa ikki dastur ocha olmaydi.
    `PrisadkaMES.exe --uninstall` CHAQIRILMAYDI: exe joyi noma'lum, u oxirida hamma
    oynalar ustida xabar oynasi ochib, Nanxing dasturidan fokusni tortib olardi —
    skaner cheki o'sha oynaga yozilib ketardi. O'sha buyruqning ikki ishi shu yerda
    jim bajariladi. Bir marta (`_ANDON_TAKEOVER_MARK`). True — to'xtatildi."""
    if not ANDON_TAKEOVER or _ANDON_TAKEOVER_MARK.exists():
        return False
    import subprocess

    try:
        royxat = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_PRISADKAMES_EXE}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        ).stdout
        # CSV: tizim tiliga bog'liq emas ("PrisadkaMES.exe","1234",...)
        if not any(q.split(",")[0].strip('"').lower() == _PRISADKAMES_EXE.lower() for q in royxat.splitlines()):
            return False
        with contextlib.suppress(OSError):
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, "PrisadkaMES")
        natija = subprocess.run(
            ["taskkill", "/F", "/IM", _PRISADKAMES_EXE],
            capture_output=True,
            timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as exc:  # noqa: BLE001 — tasklist/taskkill yo'q yoki qotdi
        log.warning("Andon: PrisadkaMES.exe tekshirilmadi (%s)", exc)
        return False
    if natija.returncode != 0:
        log.warning("Andon: PrisadkaMES.exe to'xtatilmadi (taskkill kodi %s)", natija.returncode)
        return False
    with contextlib.suppress(OSError):
        _ANDON_TAKEOVER_MARK.write_text(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} PrisadkaMES.exe to'xtatildi\n", encoding="utf-8"
        )
    log.warning("Andon: eski PrisadkaMES.exe to'xtatildi va avtozapuskdan olindi — Pico porti agentga o'tdi")
    return True


def _andon_loop() -> None:
    """Pico'ni topadi, portni ochadi, uzilsa qayta ulanadi. Hech qachon qaytmaydi."""
    import serial
    from serial.tools import list_ports

    # Manfiy boshlang'ich: avtostartda monotonic soat hali kichik — birinchi tekshiruv kechikmasin
    ogohlantirildi = -float(_ANDON_WARN_EVERY_S)
    tekshirildi = -60.0
    while True:
        try:
            name = ANDON_PORT or next((p.device for p in list_ports.comports() if p.vid == _PICO_VID), "")
            if not name:
                time.sleep(5)
                continue
            try:
                # write_timeout: Pico USB kiritishni o'qimay qo'ysa PING yozish abadiy qotib
                # qolmasin — SerialTimeoutException bilan sessiya tugaydi va qayta ulanadi
                port = serial.Serial(name, 115200, timeout=0.2, write_timeout=2)
            except serial.SerialException as exc:
                # tasklist har 5 soniyada emas — daqiqada bir marta yetarli
                if time.monotonic() - tekshirildi >= 60:
                    tekshirildi = time.monotonic()
                    if _andon_takeover():
                        time.sleep(3)
                        continue
                if time.monotonic() - ogohlantirildi >= _ANDON_WARN_EVERY_S:
                    ogohlantirildi = time.monotonic()
                    log.warning("Andon: %s ochilmadi — boshqa dastur band qilgan bo'lishi mumkin (%s)", name, exc)
                time.sleep(5)
                continue
            log.info("Andon: Pico ulandi (%s)", name)
            _andon_session(port)
        except Exception:  # noqa: BLE001 — oqim o'lmasin, chek va skan yo'liga ta'sir qilmaydi
            log.exception("Andon oqimida xato — qayta urinish")
        time.sleep(3)


def start_andon() -> None:
    """Andon o'qish oqimini ishga tushiradi. pyserial o'rnatilmagan bo'lsa jim o'chadi."""
    if not ANDON:
        return
    try:
        import serial  # noqa: F401
    except ImportError:
        log.info("pyserial o'rnatilmagan — andon (Pico) o'chiq")
        return
    threading.Thread(target=_andon_loop, daemon=True, name="andon").start()


def _andon_post(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST /bridge-agents/andon — (HTTP holat kodi, javob JSON). Tarmoq xatosi istisno bo'lib chiqadi."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{_http_base()}/api/v1/bridge-agents/andon",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BRIDGE_TOKEN}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status, raw = int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = int(exc.code), b""
    javob: dict[str, Any] = {}
    with contextlib.suppress(ValueError):
        parsed = json.loads(raw or b"{}")
        if isinstance(parsed, dict):
            javob = parsed
    return status, javob


def _andon_current() -> dict[str, Any] | None:
    """Serverga yuboriladigan jonli holat — Pico ulangan va holat ma'lum bo'lsagina.

    Qiymatlar turga keltiriladi: Pico'dan g'alati qiymat kelsa server butun partiyani
    422 bilan rad etib, hodisalar ham ketmay qolardi."""
    with ANDON_LOCK:
        if not ANDON_CONNECTED or not ANDON_CURRENT.get("state"):
            return None
        cur = dict(ANDON_CURRENT)
    lamps = cur.get("lamps")
    part_count = cur.get("part_count")
    return {
        "state": str(cur["state"])[:16],
        "since": max(0, int(cur.get("since") or time.time())),
        "lamps": {str(k): str(v) for k, v in lamps.items()} if isinstance(lamps, dict) else {},
        "part_count": part_count if isinstance(part_count, int) else None,
    }


def _rover_acked(events: list[dict[str, Any]]) -> None:
    """Server qabul qilgan partiyadagi eng katta ROVER seq — keyingi `ack` uchun.

    Navbat FIFO, ya'ni bu seq gacha hammasi allaqachon yozilgan: Pico esa aynan
    «uzilishsiz saqlangan eng katta seq» ni kutadi."""
    seqlar = [e.get("seq") for e in events if e.get("session") == _ROVER_SESSION]
    eng = max((s for s in seqlar if isinstance(s, int)), default=0)
    if not eng:
        return
    with ANDON_LOCK:
        if eng > int(ROVER["ack_upto"]):
            ROVER["ack_upto"] = eng


async def andon_shipper() -> None:
    """Andon navbatini serverga yuboradi; navbat bo'sh bo'lsa ham har 30 s jonli holatni
    yangilaydi (server 90 s xabar olmasa "aloqa yo'q" ko'rsatadi).

    Chek va skan yo'llaridan butunlay ajralgan: o'z fayli, o'z endpointi, butun tanasi
    `except Exception` bilan — xatosi `asyncio.gather` orqali agentni yiqitmaydi."""
    if not ANDON:
        return
    oxirgi = 0.0
    ogohlantirildi = 0.0
    while True:
        await asyncio.sleep(3)
        try:
            if not BRIDGE_TOKEN:
                continue
            events, count = await asyncio.to_thread(_andon_peek, _ANDON_BATCH)
            current = _andon_current()
            if not count and (current is None or time.monotonic() - oxirgi < 30):
                continue
            body: dict[str, Any] = {"events": events}
            if current is not None:
                body["current"] = current
            status, javob = await asyncio.to_thread(_andon_post, body)
            if status == 422 and current is not None:
                # Rad etilgan jonli holat bo'lishi mumkin — hodisalar u sababli yo'qolmasin:
                # jonli holatsiz qayta urinamiz
                log.warning("Andon: jonli holat rad etildi (422): %s", current)
                status, javob = await asyncio.to_thread(_andon_post, {"events": events})
            if status == 200:
                oxirgi = time.monotonic()
                await asyncio.to_thread(_andon_ack, count)
                _rover_acked(events)
                _kromka_acked(events)
                if javob.get("skipped"):
                    log.warning("Andon: server %s ta buzuq hodisani yozmadi", javob.get("skipped"))
                continue
            if status == 422:
                # Partiya shakli rad etildi — qayta yuborish tuzatmaydi, navbatni esa
                # abadiy to'sib qo'yardi
                log.error("Andon: server partiyani rad etdi (422) — %d ta qator tashlandi", count)
                await asyncio.to_thread(_andon_ack, count)
                continue
            if time.monotonic() - ogohlantirildi >= _ANDON_WARN_EVERY_S:
                ogohlantirildi = time.monotonic()
                log.warning("Andon: server qabul qilmadi (HTTP %s) — hodisalar navbatda saqlanadi", status)
        except Exception as exc:  # noqa: BLE001 — tarmoq yo'q; navbat diskda turadi
            if time.monotonic() - ogohlantirildi >= _ANDON_WARN_EVERY_S:
                ogohlantirildi = time.monotonic()
                log.warning("Andon: yuborilmadi (%s) — hodisalar navbatda saqlanadi", exc)
        await asyncio.sleep(30)


def _newer(latest: str, current: str) -> bool:
    """'1.4.1' > '1.4.0'. Buzuq satr — yangilanish yo'q deb hisoblanadi."""
    try:
        lt = tuple(int(x) for x in latest.split("."))
        ct = tuple(int(x) for x in current.split("."))
        return lt > ct
    except ValueError:
        return False


def _spawn_bat(name: str, text: str, yollar: dict[str, str]) -> bool:
    """bat'ni oynasiz cmd'da ishga tushiradi — agent o'lgandan keyin ham yashaydi.

    FAQAT `CREATE_NO_WINDOW` — `DETACHED_PROCESS` QO'SHILMAYDI: Microsoft
    ularni bir-birini istisno qiladi deydi va konsolsiz qolgan cmd o'ziga yangi,
    KO'RINADIGAN konsol ajratadi. Bola jarayonning otadan keyin yashashi uchun
    `DETACHED_PROCESS` kerak emas.

    Yo'llar bat MATNIGA emas, env orqali beriladi va ichkarida `%NOM%` bilan
    ochiladi — shu sabab matn sof ASCII qoladi. Ilgari yo'l matnga yozilardi va
    ASCII bo'lmagan Windows profil nomida (`%APPDATA%` ichida, masalan `Oʻktam`)
    `write_text` UnicodeEncodeError bilan yiqilib, qayta ishga tushish ham,
    avto-yangilanish ham JIMGINA o'lardi. Xato bo'lsa `False` — chaqiruvchi
    `os._exit` qilmasin.

    `_PYI_*` o'zgaruvchilari ATAYLAB tozalanadi. PyInstaller onefile bootloader'i
    ularni (`_PYI_ARCHIVE_FILE`, `_PYI_PARENT_PROCESS_LEVEL`) bola jarayonga
    meros qoldiradi; 6.22 dan (2026-08, GHSA-9fxf-4qw3-ghmr) boshlab bola
    jarayon OTA jarayonning exe yo'li o'ziniki bilan bir xilligini tekshiradi.
    bat orqali qayta ishga tushgan agentning otasi cmd.exe (u ham darhol o'lib
    ketadi) — tekshiruv «Security validation failure: failed to obtain
    executable path for parent process!» bilan yiqilar, yangilangan agent
    umuman turmasdi (Prisadka/Arra 2026-08-28). Meros bo'lmasa bootloader uni
    mustaqil ilova deb oladi va tekshirmaydi."""
    import subprocess

    try:
        bat = CONFIG_DIR / name
        bat.write_text(text, encoding="ascii")
        toza = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_")}
        subprocess.Popen(  # noqa: S602
            ["cmd", "/c", str(bat)],
            creationflags=0x08000000,  # CREATE_NO_WINDOW — yuqoridagi izohga qara
            env={**toza, **yollar},
        )
    except Exception:  # noqa: BLE001 - sabab log'da, qaror chaqiruvchida
        log.exception("%s ishga tushmadi", name)
        return False
    return True


def _restart_self() -> None:
    """Agentni toza qayta ishga tushiradi (bat: eski jarayon o'lishini kutadi —
    mutex poygasi bo'lmasin). Tray'dan qayta ulashda ishlatiladi: eski token
    bilan ochilgan WS ulanishini uzishning eng ishonchli yo'li — yangi jarayon."""
    if not _spawn_bat(
        "restart.bat",
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        'start "" "%MBX_EXE%"\r\n'
        'del "%~f0"\r\n',
        {"MBX_EXE": sys.executable},
    ):
        _alert(
            "MebeliX MES agent",
            "Agentni qayta ishga tushirib bo'lmadi — uni qo'lda yopib qayta oching.",
            error=True,
        )
        return
    log.info("Qayta ulash — agent qayta ishga tushmoqda")
    os._exit(0)


def _repair_from_tray() -> None:
    """Tray menyusidagi "Qayta ulash": yangi kod bilan qayta bog'lash.

    Yangi kod olingani ESKI tokenni bekor qilmaydi (u boshqa agent yozuviga
    tegishli bo'lishi mumkin) — shuning uchun exe'ni qayta bosish "allaqachon
    ulangan" beraveradi. Bu menyu aynan shu holat uchun: dialog ochiladi, yangi
    kod kiritilsa .env yangilanib agent qayta ishga tushadi. Bekor qilinsa eski
    ulanish SAQLANADI (token qaytariladi)."""
    eski = os.environ.pop("BRIDGE_TOKEN", None)
    try:
        _pair()
    except SystemExit:
        # dialog bekor qilindi — eski holat qaytadi, agent ishlashda davom etadi
        if eski:
            os.environ["BRIDGE_TOKEN"] = eski
        log.info("Qayta ulash bekor qilindi — eski ulanish saqlanib qoldi")
        return
    _restart_self()


def _apply_update(new_exe: Path) -> None:
    """O'zini almashtirish. Yo'l o'zgarmaydi — avtostart registri amal qilaveradi;
    token/sozlama %APPDATA% da — ulanish saqlanadi.

    Agent HALI TIRIK ekan almashtiriladi: Windows ishlab turgan exe'ni
    o'chirishga qo'ymaydi, lekin QAYTA NOMLASHGA qo'yadi. Almashtirib bo'lmasa
    agent O'LMAYDI — monoblok agentsiz qolmasligi kerak (`docs/07`).
    """
    import shutil

    exe = Path(sys.executable)
    eski = exe.with_name(exe.name + ".old")
    try:
        exe.replace(eski)  # `replace` — oldingi yangilanishdan qolgani ustiga yozadi
    except OSError as xato:
        log.warning("Yangilanish: exe qayta nomlanmadi (%s) — o'tkazib yuborildi", xato)
        return
    try:
        # `Path.replace` EMAS: yangi exe `%APPDATA%` da, agent esa boshqa diskda
        # turishi mumkin va `replace` disklar orasida `WinError 17` beradi.
        shutil.move(str(new_exe), str(exe))
    except OSError as xato:
        # Eskisini qaytaramiz — avtostart yo'lida fayl qolishi shart.
        try:
            eski.replace(exe)
        except OSError:
            log.error("Yangilanish: exe %s nomida qoldi — qo'lda tiklash kerak", eski.name)
        else:
            log.warning("Yangilanish: yangi exe ko'chmadi (%s) — eskisi tiklandi", xato)
        return

    # Exe allaqachon yangi; bat faqat eski jarayon o'lishini kutadi — belgisi
    # `.old` ni o'chira olish. Limit o'tsa ham `start` BAJARILADI.
    if not _spawn_bat(
        "update.bat",
        "@echo off\r\n"
        "set /a n=0\r\n"
        ":kutish\r\n"
        'del "%MBX_OLD%" >nul 2>&1\r\n'
        'if not exist "%MBX_OLD%" goto ishga\r\n'
        "set /a n+=1\r\n"
        "if %n% lss 60 (timeout /t 1 /nobreak >nul & goto kutish)\r\n"
        ":ishga\r\n"
        'start "" "%MBX_EXE%"\r\n'
        'del "%~f0"\r\n',
        {"MBX_EXE": str(exe), "MBX_OLD": str(eski)},
    ):
        # Exe almashdi, bat ketmadi: agent tirik qoladi, yangisi keyingi startda.
        log.warning("Yangilanish qo'llandi, lekin qayta ishga tushirish bat'i ketmadi")
        return
    log.info("Yangilanish qo'llanmoqda — agent qayta ishga tushadi")
    os._exit(0)  # navbat fayli fsync qilingan, tozalash shart emas


async def self_update() -> None:
    """Serverdan versiya so'raydi (qayta ulanishda darhol, zaxira — har 10
    daqiqada); yangi bo'lsa JIM yangilanadi.

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
            http = _http_base()
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
                elif local_drain() or PAIRING.is_set():
                    # ISH PAYTIDA EMAS: navbatda chek turganda os._exit chop
                    # etishni o'rtasida uzib, restartda o'sha chek IKKINCHI
                    # marta chiqishi mumkin edi (fayldan faqat muvaffaqiyatli
                    # chop etishdan KEYIN o'chiriladi). Navbat bo'shaguncha
                    # 30 soniyadan tekshirib turamiz — flusher odatda
                    # soniyalarda bo'shatadi, yangilanish esa shoshmaydi.
                    log.info("Yangilanish tayyor, navbat/pairing tugashini kutmoqda")
                    new_exe.write_bytes(data)
                    # Chegara bilan: tiqilib qolgan bitta chek (masalan printer
                    # buzuq) ilgari yangilanishni MANGU to'xtatardi — aynan
                    # tuzatish kerak bo'lgan mashina tuzatishni olmasdi.
                    kutildi = 0
                    while (local_drain() or PAIRING.is_set()) and kutildi < 3600:
                        await asyncio.sleep(30)
                        kutildi += 30
                    _apply_update(new_exe)
                else:
                    new_exe.write_bytes(data)
                    _apply_update(new_exe)
        except Exception as exc:  # noqa: BLE001 — yangilanish hech qachon agentni yiqitmasin
            log.info("Yangilanish tekshiruvi o'tmadi: %s", exc)
        # 10 daqiqa YOKI qayta ulanish — qaysi biri oldin. Deploy serverni
        # qayta ishga tushiradi -> WS uziladi -> qayta ulanish -> darhol
        # tekshiruv. 10 daqiqalik zaxira avvalgi 6 soat o'rniga: tekshiruv
        # bitta mitti GET, bo'sh turgan agent yangilanishni soatlab kutib
        # o'tirishining hech qanday foydasi yo'q edi.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(CONNECTED_EVENT.wait(), timeout=600)
        CONNECTED_EVENT.clear()


def start_tray() -> None:
    """Tray belgisi: yashil = ulandi, qizil = uzilgan. Yagona ko'rinadigan UI.

    Ilgari agent butunlay ko'rinmas edi — "ishlayaptimi?" savoli exe'ni qayta
    bosish (mutex xabari) yoki admin panelga qarash bilan hal bo'lardi. Menyu
    minimal: holat satri, log papkasi va «Qayta ulash (yangi kod)». "Chiqish" ATAYIN yo'q — tsexda tasodifan
    yopilgan agent = chek chiqmaydi va uzoq qidiruv; kerak bo'lsa Task Manager
    bor. pystray o'rnatilmagan bo'lsa (eski build) jim o'tib ketadi."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        log.info("pystray o'rnatilmagan — tray belgisi yo'q")
        return

    def tinted(color: tuple[int, int, int]) -> "Image.Image":
        """MX logotipi holat rangida: shakl alpha'dan, rang holatdan."""
        import base64
        import io

        src = Image.open(io.BytesIO(base64.b64decode(_LOGO_B64))).convert("RGBA")
        side = max(src.size)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
        out = Image.new("RGBA", sq.size, (*color, 255))
        out.putalpha(sq.getchannel("A"))
        return out.resize((64, 64), Image.LANCZOS)

    try:
        ok_icon, bad_icon = tinted((34, 197, 94)), tinted((220, 38, 38))
    except Exception:  # noqa: BLE001 — logo buzuq bo'lsa oddiy doira
        def dot(color: str) -> "Image.Image":
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=color)
            return img

        ok_icon, bad_icon = dot("#22c55e"), dot("#dc2626")

    def holat(_item: object = None) -> str:
        rejim = PRINTER_NAME or "printer yo'q (skan-forvard)"
        andon = " · Andon: Pico ulandi" if ANDON_CONNECTED else ""
        return f"{'Ulandi' if CONNECTED else 'Uzilgan'} · {rejim}{andon} · v{AGENT_VERSION}"

    def open_logs(_icon: object = None, _item: object = None) -> None:
        with contextlib.suppress(Exception):
            os.startfile(CONFIG_DIR)  # type: ignore[attr-defined]  # noqa: S606

    icon = pystray.Icon(
        "mebelix-agent",
        bad_icon,
        "MebeliX MES agent",
        menu=pystray.Menu(
            pystray.MenuItem(holat, None, enabled=False),
            pystray.MenuItem("Log papkasini ochish", open_logs),
            pystray.MenuItem(
                "Qayta ulash (yangi kod)",
                lambda _i, _m: _repair_from_tray(),
            ),
        ),
    )

    def refresh() -> None:
        import time as _t

        while True:
            _t.sleep(3)
            want = ok_icon if CONNECTED else bad_icon
            if icon.icon is not want:
                icon.icon = want
                icon.title = f"MebeliX MES agent — {'ulandi' if CONNECTED else 'uzilgan'}"

    threading.Thread(target=refresh, daemon=True).start()
    icon.run_detached()


async def main() -> None:
    if not BRIDGE_TOKEN:
        raise SystemExit(
            "Token yo'q — agentni ishga tushirib admin paneldagi ulanish kodini kiriting"
        )
    log.info("MebeliX MES agent v%s", AGENT_VERSION)
    log.info("Printer: %s", PRINTER_NAME or "TOPILMADI — yorliq printeri drayverini o'rnating")
    start_scan_forward()
    start_andon()
    start_tray()
    await asyncio.gather(uplink(), flusher(), log_shipper(), self_update(), andon_shipper())


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
    except Exception as exc:  # noqa: BLE001 — jimgina o'lish o'rniga operatorga ko'rsatamiz
        # log_shipper ham o'lgan bo'ladi: xabar serverga yetmaydi, shuning
        # uchun yagona ko'rinadigan kanal — messagebox va agent.log
        log.exception("Agent kutilmagan xato bilan to'xtadi")
        _alert("MebeliX agenti", f"Agent to'xtadi: {exc}", error=True)
        raise
