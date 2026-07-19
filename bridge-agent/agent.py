#!/usr/bin/env python3
r"""MebeliX bridge-agent (TZ 2.2.2) — printerli kompyuterdagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX G500-U (USB) printerga Windows drayveri
orqali chiqaradi. Chiquvchi ulanish — sex routerida hech narsa ochilmaydi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (faqat printer ulangan kompyuterda):
    pip install websockets pywin32 pillow
    MES_URL=wss://mes.mebelix.uz BRIDGE_TOKEN=... python agent.py

Printer avto-topiladi (nomida "godex" bor Windows printeri) — sozlash shart emas.

Env sozlamalari:
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN  — serverdagi BRIDGE_TOKEN bilan bir xil
    PRINTER_NAME  — printer nomini qo'lda berish (avto-topish o'rniga)
    QUEUE_FILE    — lokal navbat fayli (default ./print-queue.jsonl)
"""

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge-agent")

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


def send_to_printer(png_b64: str) -> bool:
    """PNG yorliqni USB GoDEX'ga chiqaradi. False = printer band/yo'q — job navbatda qoladi."""
    if not PRINTER_NAME:
        log.error("GoDEX printer topilmadi — drayver o'rnatilganini tekshiring")
        return False
    if not png_b64:
        log.warning("PNG'siz job tashlab yuborildi")  # eski formatdagi yozuv navbatni to'smasin
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
    log.info("Printer: %s", PRINTER_NAME or "TOPILMADI — GoDEX drayverini o'rnating")
    await asyncio.gather(uplink(), flusher())


if __name__ == "__main__":
    asyncio.run(main())
