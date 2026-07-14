#!/usr/bin/env python3
r"""MebeliX bridge-agent (TZ 2.2.2) — sex ichidagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX printerga lokal TCP (9100) orqali yuboradi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (sexdagi istalgan kompyuter / mini-PC):
    pip install websockets pywin32 pillow
    MES_URL=wss://mes.mebelix.uz BRIDGE_TOKEN=... PRINTER_IP=192.168.1.90 python3 agent.py

Env sozlamalari:
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN  — serverdagi BRIDGE_TOKEN bilan bir xil
    PRINTER_IP    — GoDEX IP (Ethernet, TZ 12.3)
    PRINTER_PORT  — default 9100
    PRINTER_NAME  — Windows'dagi printer nomi (masalan "Godex G500") — USB uchun
                    eng qulay yo'l, admin/share talab qilmaydi (pip install pywin32)
    PRINTER_SHARE — USB printer uchun Windows share UNC yo'li, masalan
                    \\localhost\GODEX — PRINTER_NAME imkoni bo'lmasa
    QUEUE_FILE    — lokal navbat fayli (default ./print-queue.jsonl)
"""

import asyncio
import contextlib
import json
import logging
import os
import socket
import subprocess
import tempfile
from pathlib import Path

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge-agent")

MES_URL = os.environ.get("MES_URL", "ws://localhost:8000")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PRINTER_IP = os.environ.get("PRINTER_IP", "")
PRINTER_PORT = int(os.environ.get("PRINTER_PORT", "9100"))
PRINTER_NAME = os.environ.get("PRINTER_NAME", "")  # Windows printer nomi (win32print RAW)
PRINTER_SHARE = os.environ.get("PRINTER_SHARE", "")  # USB GoDEX: r"\\host\sharename"
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
        win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH | win32con.DM_ORIENTATION
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


def send_to_printer(ezpl: str, png_b64: str = "") -> bool:
    data = ezpl.encode("cp1251", errors="replace")
    if PRINTER_NAME:
        # USB GoDEX: PNG bo'lsa drayver orqali rasm (QR kafolatlangan),
        # bo'lmasa xom EZPL spooler'ga RAW
        try:
            if png_b64:
                _print_png_gdi(png_b64)
                return True
            import win32print

            h = win32print.OpenPrinter(PRINTER_NAME)
            try:
                win32print.StartDocPrinter(h, 1, ("MebeliX yorliq", None, "RAW"))
                win32print.StartPagePrinter(h)
                win32print.WritePrinter(h, data)
                win32print.EndPagePrinter(h)
                win32print.EndDocPrinter(h)
            finally:
                win32print.ClosePrinter(h)
            return True
        except Exception as exc:  # noqa: BLE001 — printer xatosi navbatda qolsin
            log.warning("Printer xatosi (%s): %s", PRINTER_NAME, exc)
            return False
    if PRINTER_SHARE:
        # USB GoDEX (G500-U): Windows'da printer share qilinadi, xom EZPL
        # spooler orqali RAW yuboriladi — copy /b <fayl> \host\share
        try:
            with tempfile.NamedTemporaryFile(suffix=".prn", delete=False) as f:
                f.write(data)
                tmp = f.name
            try:
                r = subprocess.run(
                    ["cmd", "/c", "copy", "/b", tmp, PRINTER_SHARE],
                    capture_output=True,
                    timeout=30,
                )
                if r.returncode != 0:
                    log.warning("Printer share xatosi (%s): %s", PRINTER_SHARE, r.stderr.decode(errors="replace").strip())
                return r.returncode == 0
            finally:
                os.unlink(tmp)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Printer share xatosi (%s): %s", PRINTER_SHARE, exc)
            return False
    if not PRINTER_IP:
        log.error("PRINTER_IP yoki PRINTER_SHARE sozlanmagan — yorliq lokal navbatda qoladi")
        return False
    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=10) as sock:
            sock.sendall(data)
        return True
    except OSError as exc:
        log.warning("Printer xatosi (%s:%s): %s", PRINTER_IP, PRINTER_PORT, exc)
        return False


async def flusher() -> None:
    """Lokal navbatni printerga oqizadi — printer qaytganda o'zi davom etadi."""
    while True:
        jobs = local_drain()
        if jobs:
            remaining = []
            for i, job in enumerate(jobs):
                if send_to_printer(job.get("ezpl", ""), job.get("png", "")):
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


async def uplink() -> None:
    """Serverga doimiy outbound ulanish; uzilsa 5s backoff bilan qayta ulanadi."""
    url = f"{MES_URL.rstrip('/')}/api/v1/ws/bridge?token={BRIDGE_TOKEN}"
    while True:
        try:
            async with websockets.connect(url, ping_interval=30) as ws:
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
                        log.info("Print job qabul qilindi: instance %s", msg.get("instance_id"))
        except Exception as exc:
            log.warning("Ulanish uzildi (%s) — 5s dan keyin qayta urinish", exc)
            await asyncio.sleep(5)


async def main() -> None:
    if not BRIDGE_TOKEN:
        raise SystemExit("BRIDGE_TOKEN env sozlanmagan")
    await asyncio.gather(uplink(), flusher())


if __name__ == "__main__":
    asyncio.run(main())
