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
2. Admin panel > **Printer agentlar** > "Agentni yuklab olish" — `mebelix-agent.exe`
   yuklanadi (`GET /api/v1/bridge-agents/download`). Python ham, `pip` ham kerak emas.
3. O'sha sahifada "Yangi agent" 8 belgili bir martalik kod beradi (masalan
   `P7HJ-N46U`) — 15 daqiqa amal qiladi.
4. Exe'ni ishga tushiring: server manzilini (Enter = `wss://mes.mebelix.uz`) va
   kodni so'raydi, kodni `POST /api/v1/bridge-agents/pair` orqali doimiy tokenga
   almashtiradi va `%APPDATA%\MebelixAgent\.env` ga saqlaydi — keyingi safar
   so'ramaydi. Kod muddati o'tishi ulangan agentga ta'sir qilmaydi.

Log'da `Printer: Godex G500` va `Serverga ulandi` chiqsa — tayyor.

Doimiy ishlashi uchun exe'ni Windows Task Scheduler'da "At startup" trigger
bilan ro'yxatdan o'tkazing — headless ishga tushganda kod so'ralmaydi, saqlangan
token ishlatiladi.

## Env sozlamalari

O'qish tartibi: env o'zgaruvchi > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`.
Odatda qo'lda hech narsa yozilmaydi — birinchi ulanish ikkalasini ham to'ldiradi.

| Env | Vazifasi |
| --- | --- |
| `MES_URL` | server manzili (`wss://mes.mebelix.uz` yoki `ws://host:8000`) |
| `BRIDGE_TOKEN` | ulanishda olingan doimiy token (har agentda o'ziniki) |
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

## Muammolar

Admin panelda "yangi kod" yoki "bekor qilish" bosilgan bo'lsa agent log'da server
ulanishni rad etganini yozadi. Yechim: `%APPDATA%\MebelixAgent\.env` faylini
o'chirib, exe'ni yangi kod bilan qaytadan ishga tushiring.

## Dasturchi uchun: exe yig'ish

```bash
pyinstaller --onefile --console --name mebelix-agent agent.py
```

So'ng `dist/mebelix-agent.exe` ni serverdagi `backend/uploads/agent/` ga
ko'chiring — "Agentni yuklab olish" o'sha fayldan beradi. Binar repo'da yo'q
(gitignore).

Eslatma: SCX fayllar bridge orqali o'tmaydi — ular stanok kompyuterida brauzer
orqali yuklab olinadi (TZ 12.5).
