# MebeliX bridge-agent

Printerli kompyuterdagi yengil servis (TZ 2.2.2): masofaviy serverdan chop etish
buyruqlarini olib, **GoDEX G500-U (USB)** printerga Windows drayveri orqali
chiqaradi. Internet yoki printer uzilganda buyruqlar `print-queue.jsonl` faylida
saqlanadi va aloqa tiklangach avtomatik bajariladi — yorliq yo'qolmaydi.

Serverga CHIQUVCHI WebSocket bilan ulanadi — sex routerida port ochilmaydi.
Faqat printer ulangan kompyuterga o'rnatiladi; menejer, texnolog va boshqa post
terminallariga hech narsa kerak emas (ular brauzerdan tugmani bosadi).

## O'rnatish

1. GoDEX drayverini o'rnating (printer USB ulangan holda). Agent printerni
   nomidan o'zi topadi ("godex" qidiradi) — sozlash shart emas.
2. Python 3.11+ va kutubxonalar:

```bash
pip install websockets pywin32 pillow
```

3. Ishga tushirish:

```powershell
$env:MES_URL="wss://mes.mebelix.uz"
$env:BRIDGE_TOKEN="<serverdagi BRIDGE_TOKEN>"
python agent.py
```

Log'da `Printer: Godex G500` va `Serverga ulandi` chiqsa — tayyor.

Doimiy ishlashi uchun shu buyruqni Windows Task Scheduler'da "At startup"
trigger bilan ro'yxatdan o'tkazing.

## Env sozlamalari

| Env | Vazifasi |
| --- | --- |
| `MES_URL` | server manzili (`wss://mes.mebelix.uz` yoki `ws://host:8000`) |
| `BRIDGE_TOKEN` | serverdagi `.env` dagi `BRIDGE_TOKEN` bilan bir xil (`openssl rand -hex 24`) |
| `PRINTER_NAME` | printer nomini qo'lda berish (avto-topish o'rniga) |
| `QUEUE_FILE` | lokal navbat fayli (default `./print-queue.jsonl`) |

## Ishlash tartibi

```
Terminal "Chop etish"
  -> POST /api/v1/terminal/labels/{id}   (label_printed_at + TABLO xabari)
  -> arq print_label: render_label_png -> LPUSH mes:print:queue
  -> /ws/bridge: brpop -> agentga yuboradi, agent ack qiladi
  -> agent: print-queue.jsonl ga yozadi -> Windows GDI -> GoDEX
```

Ack kelmasa yoki ulanish uzilsa job navbatga qaytadi — yorliq yo'qolmaydi.

Eslatma: SCX fayllar bridge orqali o'tmaydi — ular stanok kompyuterida brauzer
orqali yuklab olinadi (TZ 12.5).
