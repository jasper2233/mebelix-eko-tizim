# MebeliX bridge-agent

Printerli kompyuterdagi yengil servis (TZ 2.2.2): masofaviy serverdan chop etish
buyruqlarini olib, **GoDEX G500-U (USB)** printerga Windows drayveri orqali
chiqaradi. Internet yoki printer uzilganda buyruqlar `print-queue.jsonl` faylida
saqlanadi va aloqa tiklangach avtomatik bajariladi — yorliq yo'qolmaydi.

Serverga CHIQUVCHI WebSocket bilan ulanadi — tsex routerida port ochilmaydi.
Faqat printer ulangan kompyuterga o'rnatiladi; menejer, texnolog va boshqa post
terminallariga hech narsa kerak emas (ular brauzerdan tugmani bosadi).

## O'rnatish

1. GoDEX drayverini o'rnating (printer USB ulangan holda). Agent printerni
   nomidan o'zi topadi ("godex" qidiradi) — sozlash shart emas.
2. `mebelix-agent.exe` ni printerli kompyuterga ko'chiring (qo'lda tarqatiladi —
   flashka yoki lokal tarmoq; panel ichidagi yuklab olish tugmasi olib tashlangan,
   chunki serverda eski nusxa qolib adashtirardi). Python ham, `pip` ham kerak emas.
3. O'sha sahifada "Yangi agent" 8 belgili bir martalik kod beradi (masalan
   `P7HJ-N46U`) — 15 daqiqa amal qiladi.
4. Exe'ni ishga tushiring — kichik oyna chiqadi, ikkita maydon: server manzili
   (default `wss://mes.mebelix.uz`) va ulanish kodi. "Ulash" bosilgach kod
   `POST /api/v1/bridge-agents/pair` orqali doimiy tokenga almashtiriladi va
   `%APPDATA%\MebelixAgent\.env` ga saqlanadi. Kod noto'g'ri bo'lsa oyna xato
   bilan qayta ochiladi — dasturni qayta ishga tushirish shart emas.

Shundan keyin **oyna umuman ko'rinmaydi**: agent fonda ishlaydi va kompyuter
yonganda o'zi tushadi (birinchi ulanishda `HKCU\...\Run` ga yoziladi, admin
huquqi kerak emas). Ishlayotganini admin paneldagi **Ulandi** belgisi bildiradi;
tafsilotlar `%APPDATA%\MebelixAgent\agent.log` da (1 MB x 3 rotatsiya).

Kod muddati o'tishi ulangan agentga ta'sir qilmaydi — token muddatsiz.

Agentni ikki marta ishga tushirib bo'lmaydi: mutex ikkinchi nusxani to'xtatib,
"allaqachon ishlab turibdi" deydi. Oyna ko'rinmagani uchun bu tez-tez uchraydi.

## Env sozlamalari

O'qish tartibi: env o'zgaruvchi > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`.
Odatda qo'lda hech narsa yozilmaydi — birinchi ulanish ikkalasini ham to'ldiradi.

| Env | Vazifasi |
| --- | --- |
| `MES_URL` | server manzili (`wss://mes.mebelix.uz` yoki `ws://host:8000`) |
| `BRIDGE_TOKEN` | ulanishda olingan doimiy token (har agentda o'ziniki) |
| `PRINTER_NAME` | printer nomini qo'lda berish (avto-topish o'rniga) |
| `QUEUE_FILE` | lokal navbat fayli (default `%APPDATA%\MebelixAgent\print-queue.jsonl` — avtostartda ishchi papka System32 bo'lgani uchun nisbiy yo'l ishlamaydi) |

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

Admin panelda "yangi kod" yoki "bekor qilish" bosilsa server ulanishni **HTTP
401/403** bilan rad etadi. Agent buni o'zi payqaydi: 401/403 KETMA-KET 3 marta
kelgandagina (~15 soniya) saqlangan tokenni o'chirib, sozlash oynasini qayta
ochadi — yangi kodni kiritsangiz ishlashda davom etadi. Oyna bekor qilinsa agent
to'xtaydi. Boshqa har qanday xato (deploy paytidagi 502, kompyuter yonganda
tarmoq hali tik turmagani, server qayta yonayotgani) tokenni O'CHIRMAYDI —
agent 5 soniyalik interval bilan jimgina qayta ulanadi, dialog ochilmaydi.

Chek chiqmasa birinchi qaraydigan joy — admin paneldagi holat. **Uzilgan** bo'lsa
agent ishlamayapti: `agent.log` ni oching. Muhimi, bu paytda ham hech narsa
yo'qolmaydi — yorliqlar Redis navbatida turadi va agent qaytishi bilan chiqadi.

## Dasturchi uchun: exe yig'ish

```bash
pip install "websockets>=14" pywin32 pillow pynput pyinstaller
pyinstaller --onefile --noconsole --name mebelix-agent agent.py
```

`websockets>=14` majburiy: agent kodi v14+ API'siga yozilgan
(`additional_headers=`, `InvalidStatus.response.status_code`) — eski v13 bilan
yig'ilgan exe serverga ulanolmaydi. `pyinstaller` faqat build-time asbob,
runtime'da kerak emas.

`--noconsole` muhim: usiz qora konsol oynasi ochiq turadi va uni kimdir yopib
qo'ysa chek chiqmay qoladi. Oynasiz rejimda `sys.stdout` yo'q — shuning uchun
hamma narsa `agent.log` ga yoziladi, foydalanuvchiga esa faqat messagebox orqali
gapiriladi.

Eslatma: SCX fayllar bridge orqali o'tmaydi — ular stanok kompyuterida brauzer
orqali yuklab olinadi (TZ 12.5).

## Skan-forvard (TZ 12.5) — bitta skan, ikkala tizim

Stanok (Nanxing) kompyuterida agent o'rnatilgan bo'lsa, skaner o'qigan QR:

1. odatdagidek Nanxing dasturining Scan maydoniga tushadi (fayl ochiladi);
2. agent buni PASSIV kuzatib, nusxasini `POST /api/v1/bridge-agents/scan` ga
   yuboradi — MES'da prisadka skani yoziladi, panel jonli yangilanadi.

Ishlashi uchun:

- admin panel > Printer agentlar > agentga **stanok bog'lanadi** (skan shu
  stanokning aktiv sessiyasi nomidan yoziladi — operator monoblokda kirgan
  bo'lishi shart);
- `pip install pynput` (exe yig'ilganda kiritiladi); `SCAN_FORWARD=0` o'chiradi;
- skaner-klaviatura aniqlanishi: 6+ belgi, har belgi <50ms, Enter bilan
  tugaydi — odam terishi bu tezlikka tushmaydi.

**MUHIM — klaviatura layouti:** skaner HID-klaviatura, `_` belgisi layoutga
bog'liq. Stanok kompyuterida faqat **ENG (US)** layout qoldiring (Win+Space
bilan tekshiring), aks holda `100701_02_003_1` o'rniga buzilgan matn tushadi —
ham Nanxing, ham MES topa olmaydi.
