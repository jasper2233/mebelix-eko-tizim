#!/usr/bin/env python3
"""MebeliX bridge-agent (TZ 2.2.2) — sex ichidagi yengil servis.

Masofaviy serverga CHIQUVCHI (outbound) WebSocket bilan ulanadi, chop etish
buyruqlarini qabul qiladi va GoDEX printerga lokal TCP (9100) orqali yuboradi.
Internet yoki printer uzilganda buyruqlar lokal diskda (JSONL) saqlanadi va
aloqa tiklangach bajariladi — hech bir yorliq yo'qolmaydi.

O'rnatish (sexdagi istalgan kompyuter / mini-PC):
    pip install websockets
    MES_URL=wss://app.mebelix.uz BRIDGE_TOKEN=... PRINTER_IP=192.168.1.90 python3 agent.py

Env sozlamalari:
    MES_URL       — server manzili (wss://... yoki ws://host:8000)
    BRIDGE_TOKEN  — serverdagi BRIDGE_TOKEN bilan bir xil
    PRINTER_IP    — GoDEX IP (Ethernet, TZ 12.3)
    PRINTER_PORT  — default 9100
    QUEUE_FILE    — lokal navbat fayli (default ./print-queue.jsonl)
"""

import asyncio
import json
import logging
import os
import socket
from pathlib import Path

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge-agent")

MES_URL = os.environ.get("MES_URL", "ws://localhost:8000")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PRINTER_IP = os.environ.get("PRINTER_IP", "")
PRINTER_PORT = int(os.environ.get("PRINTER_PORT", "9100"))
QUEUE_FILE = Path(os.environ.get("QUEUE_FILE", "print-queue.jsonl"))


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


def send_to_printer(ezpl: str) -> bool:
    if not PRINTER_IP:
        log.error("PRINTER_IP sozlanmagan — yorliq lokal navbatda qoladi")
        return False
    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=10) as sock:
            sock.sendall(ezpl.encode("cp1251", errors="replace"))
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
                if send_to_printer(job.get("ezpl", "")):
                    log.info("Yorliq chop etildi: instance %s", job.get("instance_id"))
                else:
                    remaining = jobs[i:]
                    break
            local_rewrite(remaining)
            if remaining:
                log.info("Printer kutilmoqda — navbatda %d ta yorliq", len(remaining))
        await asyncio.sleep(5)


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
