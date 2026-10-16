# MebeliX bridge-agent

Printerli kompyuterdagi yengil servis: masofaviy serverdan chop etish
buyruqlarini olib, **USB yorliq printeriga** (GoDEX, Xprinter va b.) Windows drayveri orqali
chiqaradi. Internet yoki printer uzilganda buyruqlar `print-queue.jsonl` faylida
saqlanadi va aloqa tiklangach avtomatik bajariladi — yorliq yo'qolmaydi.

Serverga CHIQUVCHI WebSocket bilan ulanadi — tsex routerida port ochilmaydi.
Faqat printer ulangan kompyuterga o'rnatiladi; menejer, texnolog va boshqa post
terminallariga hech narsa kerak emas (ular brauzerdan tugmani bosadi).

## O'rnatish

1. Printer drayverini o'rnating (USB ulangan holda). Agent printerni nomidan
   o'zi topadi (tanish rusumlar: godex, xprinter, gprinter, tsc, zebra, argox,
   postek) — sozlash shart emas; boshqa rusum `PRINTER_NAME` bilan ko'rsatiladi.
   Chop etish Windows GDI orqali — har qanday drayver ishlaydi.
2. `mebelix-agent.exe` ni admin panel > MES agentlar sahifasidagi havoladan
   yuklab oling (`/api/v1/bridge-agents/download` — CI har deploy'da windows
   runner'da qurib serverga qo'yadi, eskirgan nusxa bo'lishi mumkin emas; 2026-08-02
   da olib tashlangan tugma shu kafolat bilan qaytdi). Python ham, `pip` ham kerak emas.
3. O'sha sahifada "Yangi agent" 8 belgili bir martalik kod beradi (masalan
   `P7HJ-N46U`) — 15 daqiqa amal qiladi.
4. Exe'ni ishga tushiring — kichik oyna chiqadi, ikkita maydon: server manzili
   (default `wss://mes.mebelix.uz`) va ulanish kodi. "Ulash" bosilgach kod
   `POST /api/v1/bridge-agents/pair` orqali doimiy tokenga almashtiriladi va
   `%APPDATA%\MebelixAgent\.env` ga saqlanadi. Kod noto'g'ri bo'lsa oyna xato
   bilan qayta ochiladi — dasturni qayta ishga tushirish shart emas.

Shundan keyin oyna yopiladi: agent fonda ishlaydi va kompyuter yonganda o'zi
tushadi (`HKCU\...\Run` — HAR startda qayta yoziladi, ya'ni exe ko'chirilsa
ham keyingi qo'lda ishga tushirishdan boshlab avtostart o'zini tuzatadi; admin
huquqi kerak emas). Eslatma: HKCU foydalanuvchiga bog'liq — kompyuter boshqa
Windows akkaunti bilan yonsa agent tushmaydi; stanok/monoblokda avto-login
o'sha bitta akkauntda bo'lishi kerak. Holat **tray belgisida** (v1.4.0+): yashil nuqta = ulandi, qizil =
uzilgan; menyuda rejim (printer nomi yoki skan-forvard), versiya va log papkasi.
"Chiqish" ATAYIN yo'q — tasodifan yopilgan agent chek chiqarmay qo'yardi.
Admin paneldagi **Ulandi** belgisi ham ishlaydi; tafsilotlar
`%APPDATA%\MebelixAgent\agent.log` da (1 MB x 3 rotatsiya).

Kod muddati o'tishi ulangan agentga ta'sir qilmaydi — token muddatsiz.

## Avto-yangilanish (v1.4.0+)

Agent `GET /api/v1/bridge-agents/latest` dan versiyani so'raydi: startdan ~1 daqiqada, har QAYTA ULANISHDA (deploy = darhol trigger) va zaxira sifatida har 10 daqiqada — bo'sh agent yangilanishni soatlab kutmaydi.
Yangisi bo'lsa JIM yangilanadi: exe'ni yuklab oladi, sha256 tekshiradi,
o'zini almashtirib qayta ishga tushadi (~10 soniya).

**Almashtirish agent HALI TIRIK ekan bo'ladi.** Windows ishlab turgan exe'ni
o'chirishga ruxsat bermaydi, lekin qayta nomlashga beradi (o'lchangan) —
shuning uchun eski exe `mebelix-agent.exe.old` ga suriladi va yangisi uning
o'rniga qo'yiladi. Bu ikkalasi ham xatosi tekshirilgan holda bajariladi:
almashtirib bo'lmasa agent O'LMAYDI, sabab `agent.log` ga yoziladi va keyingi
siklda qayta uriniladi. `update.bat` endi faqat eski jarayon o'lishini kutib
yangi exe'ni ishga tushiradi, kutish esa CHEGARALANGAN (60 urinish) va chegara
o'tsa ham `start` baribir bajariladi.

> **2026-09-21 gacha bo'lgan xato.** Ilgari almashtirish agent `os._exit(0)`
> qilgandan KEYIN, bat ichida bo'lardi va bat eski exe o'chguncha CHEKSIZ
> kutardi. Exe'ni o'chirib bo'lmaydigan mashinada (`Program Files` — pastga
> qara) bu abadiy tsiklga aylanardi: monoblok qayta yuklangunicha AGENTSIZ
> qolardi, keyin esa avtostart ESKI exe'ni ko'tarardi, ya'ni yangilanish
> jimgina yo'qolardi. Bir xil yangilanish bir monoblokda o'tib, boshqasida
> o'tmasligining sababi shu edi. Tsiklni operator qora konsol oynasi sifatida
> ko'rardi — u ham xato: `_spawn_bat` `DETACHED_PROCESS | CREATE_NO_WINDOW`
> uzatardi, Microsoft esa bu ikkisini bir-birini istisno qiladi deb yozadi va
> konsolsiz qolgan cmd o'ziga yangi konsol ajratardi. Endi faqat
> `CREATE_NO_WINDOW`. Lokal navbatda chek turganda darhol ALMASHMAYDI — bo'shashini kutadi, ko'pi bilan 1 soat (chop etish o'rtasida uzilsa bitta chek ikki marta chiqishi mumkin edi; chegara esa tiqilib qolgan navbat yangilanishni mangu to'xtatmasligi uchun).
Token va sozlamalar `%APPDATA%` da — ulanish saqlanadi; exe yo'li o'zgarmagani
uchun avtostart ham amal qilaveradi. Flashka bilan tarqatish endi faqat BIRINCHI
o'rnatishda kerak (yoki paneldagi havoladan). Panelda eski versiyali agent sariq
`v1.3.0 → v1.4.0` belgisi bilan ko'rinadi; 6+ soat o'tsa ham yangilanmasa —
`agent.log` da "Yangilanish tekshiruvi o'tmadi" qatorini qidiring.
sha256 mos kelmasa (yarim yuklangan fayl) o'tkazib yuboriladi va keyingi siklda
qayta urinadi. Dev-skript (exe emas) o'zini yangilamaydi.

**v1.4.7 tuzatishi — «Security validation failure: failed to obtain executable
path for parent process!»** Yangilanish/qayta ulash `.bat` orqali yangi exe'ni
ishga tushiradi. PyInstaller 6.22+ bootloader'i bola jarayonga `_PYI_*` env
o'zgaruvchilarini meros qoldiradi va ular bor bo'lsa OTA jarayon exe'sini
tekshiradi — otasi `cmd.exe` bo'lgani uchun tekshiruv yiqilib, yangilangan
agent turmasdi (faqat qo'lda/reboot'da ochilardi). Endi `_spawn_bat` shu
o'zgaruvchilarni tozalab uzatadi. CI'da `pyinstaller` versiyasi qotirilgan.

**Exe qayerda turishi kerak?** Istalgan LOKAL diskda, yozish huquqi bor
papkada (`C:` shart emas — `D:\MebelixAgent\` ham bo'ladi): yangilanish exe'ni
o'z joyida almashtiradi — `Program Files` ga admin kerak, ya'ni u yerga
o'rnatilgan agent O'ZINI YANGILAY OLMAYDI (yangilanish har siklda jim
o'tkazib yuboriladi, `agent.log` da "exe qayta nomlanmadi" qatori chiqadi),
avtostart yo'li har startda qayta yoziladi, sozlama esa `%APPDATA%\MebelixAgent` da. Tarmoq
diski, flashka yoki «Yuklanmalar» ichidagi tasodifiy nusxa — yo'q: yuklanish
paytida yo'q bo'lsa avtostart yiqiladi.

Agentni ikki marta ishga tushirib bo'lmaydi: mutex ikkinchi nusxani to'xtatadi
va xabar tray'ga yo'naltiradi. **Yangi kod bilan qayta ulash** — exe'ni qayta
bosish EMAS (eski token amalda qolaveradi): tray menyusidan **"Qayta ulash
(yangi kod)"** tanlanadi — dialog ochiladi, kod kiritilsa agent yangi ulanish
bilan qayta ishga tushadi; bekor qilinsa eski ulanish saqlanib qoladi.

## Env sozlamalari

O'qish tartibi: env o'zgaruvchi > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`.
Odatda qo'lda hech narsa yozilmaydi — birinchi ulanish ikkalasini ham to'ldiradi.

| Env | Vazifasi |
| --- | --- |
| `MES_URL` | server manzili (`wss://mes.mebelix.uz` yoki `ws://host:8000`) |
| `BRIDGE_TOKEN` | ulanishda olingan doimiy token (har agentda o'ziniki) |
| `PRINTER_NAME` | printer nomini qo'lda berish (avto-topish o'rniga) |
| `QUEUE_FILE` | lokal navbat fayli (default `%APPDATA%\MebelixAgent\print-queue.jsonl` — avtostartda ishchi papka System32 bo'lgani uchun nisbiy yo'l ishlamaydi) |
| `ANDON` | stanok signal ustunini (Pico, USB) o'qish; default yoniq, `0` o'chiradi. Pico topilmagan kompyuterda o'zi jim turadi |
| `ANDON_PORT` | Pico COM porti (bo'sh — Raspberry Pi VID `2E8A` bo'yicha o'zi topadi) |
| `ANDON_TUR` | Pico turining boshlang'ich taxmini: `prisadka` (signal ustuni), `kromka` (o'lchash stansiyasi) yoki `rover` (CNC 2130) — qurilma hali jim turganda HB/PING/vaqt yuborish oralig'ini belgilaydi. Tur baribir har tushunarli qatordan qayta aniqlanadi |
| `ROVER_T_REASON` | Rover Pico'siga yuboriladigan chegara, soniya (default `300`): shundan uzun to'xtash hodisa bo'lib yoziladi |
| `ROVER_AUTO_SHUTDOWN` | `1` bo'lsa rover Pico'si taymer bo'yicha stanokni o'chiradi (default `0` — kuzatuv) |
| `ANDON_TAKEOVER` | `0` — port band bo'lsa eski `PrisadkaMES.exe` ni to'xtatmaslik |
| `ANDON_QUEUE_FILE` | andon navbati (default `%APPDATA%\MebelixAgent\andon-queue.jsonl`) |

## Ishlash tartibi

```
Terminal "Chop etish"
  -> POST /api/v1/terminal/labels/{id}   (label_printed_at + TABLO xabari)
  -> arq print_label: render_label_png -> LPUSH mes:print:queue:{agent_id}
  -> /ws/bridge: brpop -> agentga yuboradi, agent ack qiladi
  -> agent: print-queue.jsonl ga yozadi -> Windows GDI -> GoDEX
```

Ack kelmasa yoki ulanish uzilsa job navbatga qaytadi — yorliq yo'qolmaydi.

## Muammolar

Admin panelda "yangi kod" yoki "bekor qilish" bosilsa server jonli ulanishni **~5 soniyada** uzadi
(Redis revoke bayrog'i) va keyingi ulanishni **HTTP 401/403** bilan rad etadi. Agent buni o'zi payqaydi: 401/403 KETMA-KET 2 marta
kelgandagina (~3 soniya; transport xatosi endi hisobni NOLLAMAYDI — ilgari notekis
tarmoqda ketma-ketlik hech yig'ilmasdi) saqlangan tokenni o'chirib, sozlash oynasini qayta
ochadi — yangi kodni kiritsangiz ishlashda davom etadi. Oyna bekor qilinsa agent
to'xtamaydi: 30 soniyadan keyin qayta urinadi va oyna yana ochiladi. Boshqa har qanday xato (deploy paytidagi 502, kompyuter yonganda
tarmoq hali tik turmagani, server qayta yonayotgani) tokenni O'CHIRMAYDI —
agent 5 soniyalik interval bilan jimgina qayta ulanadi, dialog ochilmaydi.

Chek chiqmasa birinchi qaraydigan joy — admin paneldagi holat. **Uzilgan** bo'lsa
agent ishlamayapti: `agent.log` ni oching. Muhimi, bu paytda ham hech narsa
yo'qolmaydi — yorliqlar Redis navbatida turadi va agent qaytishi bilan chiqadi.

## Dasturchi uchun: exe yig'ish

```bash
pip install "websockets>=14" pywin32 pillow pynput pystray pyserial "pyinstaller==6.22.2"
pyinstaller --onefile --noconsole --icon mebelix.ico --name mebelix-agent agent.py
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
orqali yuklab olinadi.

## Skan-forvard — bitta skan, ikkala tizim

Stanok (Nanxing) kompyuterida agent o'rnatilgan bo'lsa, skaner o'qigan QR:

1. odatdagidek Nanxing dasturining Scan maydoniga tushadi (fayl ochiladi);
2. agent buni PASSIV kuzatib, nusxasini `POST /api/v1/bridge-agents/scan` ga
   yuboradi — MES'da prisadka skani yoziladi, panel jonli yangilanadi.

Ishlashi uchun:

- admin panel > MES agentlar > agentga **stanok bog'lanadi** (skan shu
  stanokning aktiv sessiyasi nomidan yoziladi — operator monoblokda kirgan
  bo'lishi shart);
- `pip install pynput` (exe yig'ilganda kiritiladi); `SCAN_FORWARD=0` o'chiradi;
- beyjik (UUID) yuborilmaydi — u smena oqimiga tegishli, detal skani emas;
- skaner-klaviatura aniqlanishi: 6+ belgi, har belgi <50ms, Enter bilan
  tugaydi — odam terishi bu tezlikka tushmaydi.

**MUHIM — klaviatura layouti:** skaner HID-klaviatura, `_` belgisi layoutga
bog'liq. Stanok kompyuterida faqat **ENG (US)** layout qoldiring (Win+Space
bilan tekshiring), aks holda `100701_02_003_1` o'rniga buzilgan matn tushadi —
ham Nanxing, ham MES topa olmaydi.

## Andon — stanok signal ustuni (v1.5.0+)

Prisadka stanogining qizil/sariq/yashil chiroqlarini Raspberry Pi Pico o'qiydi
(optopara orqali, firmware — `prisadka-mes-nanxing` repozitoriysi) va USB kabel
orqali shu agentga beradi. Agent hodisalarni serverga yuboradi, stanok holati
MebeliX'da jonli ko'rinadi.

```
signal ustuni ─optopara─► Pico ─USB─► agent: andon oqimi ─► andon-queue.jsonl
                                                                   │ har 3 s
                                              POST /api/v1/bridge-agents/andon
```

- Pico USB porti Raspberry Pi VID (`2E8A`) bo'yicha o'zi topiladi. Pico
  bo'lmagan kompyuterda (arra, kromka...) andon qismi hech narsa qilmaydi.
- Agent Pico'ga har 5 soniyada `PING` yuboradi — Pico uni 15 soniya eshitmasa
  o'zini oflayn deb hisoblab, hodisalarni o'z buferiga yig'adi.
- Hodisa avval diskdagi navbatga (fsync) yoziladi, server qabul qilgachgina
  o'chadi — internet uzilsa ham yo'qolmaydi (20 000 tagacha, keyin eng eskisi).
- Ish markazi Pico'dagi `MACHINE_ID` dan emas, agentning **ish markazi
  bog'lanishidan** olinadi — agentga prisadka stanogi bog'langan bo'lishi shart
  (usiz server `409` qaytaradi, hodisalar navbatda kutib turadi).
- **Eski `PrisadkaMES.exe`:** bitta COM portni ikki dastur ocha olmaydi. Port
  band bo'lsa va band qilgan `PrisadkaMES.exe` bo'lsa, agent uni **bir marta**
  to'xtatadi va avtozapuskdan oladi (`andon-takeover.done` belgisi qo'yiladi,
  keyin qayta tegmaydi). Uning `mes-data.db` bazasi o'chirilmaydi.
  `ANDON_TAKEOVER=0` bu xatti-harakatni o'chiradi.
- Andon qismi chek chop etish va skan-forvarddan to'liq ajralgan: alohida oqim,
  alohida navbat fayli, alohida endpoint. Uning xatosi logga yoziladi, xolos.
- Tray menyusida Pico ulangani ko'rinadi: `... · Andon: Pico ulandi · v1.6.0`.

## Kromka stansiyasi Pico'si (v1.6.0+)

Ikkinchi xil Pico: kromka uskunasida detal uzunligini ikkita to'siq datchigi bilan
o'lchaydi (firmware alohida repoda). Agent ikkalasini ham o'qiydi:

| | Prisadka (signal ustuni) | Kromka (o'lchash) |
|---|---|---|
| Qator | `MES event {...}` | yalang'och `{"ev":"olchov",...}` |
| Yurak urishi | `PING` har 5 s | **`HB` har 1 s** — Pico 3 s buyruq ko'rmasa hodisalarni RAM ga yig'adi |
| Kalit | firmware `session`/`seq` beradi | **v1.22+**: Pico'ning `xb` (yonish belgisi) → `session`, `xq` → `seq`. Eskisida — agent beradi (har ulanishda yangi sessiya) |
| Buferdan kelgani | `age_ms` | `eski_ms` — ikkalasida ham vaqt shundan tiklanadi |
| Tasdiq | yo'q | **v1.22+**: `ACK <xb> <xq…>` — server YOZGANDAN keyin |

Tur birinchi tushunarli qatordan aniqlanadi va har tushunarli qator uni qayta
belgilaydi — `ANDON_TUR` uni majburlamaydi, faqat boshlang'ich taxmin (qurilma hali
jim turganda HB/PING/vaqt yuborish oralig'ini belgilaydi). Agent bitta portni o'qiydi:
bitta kompyuterda ikki Pico bo'lsa port `ANDON_PORT` bilan tanlanadi.

**Firmware v1.16 (2026-09-21):** yangi hodisa `tiqilish` — detallar birga o'tgan yoki
biri datchik ostida turib qolgan, ya'ni o'lchov chiqmagan (soxta uzunlik o'rniga hodisa
va avariya). Agent uni ham uzatadi. Yana: stansiya 3 soniya jim qolsa Pico USB ga umuman
yozmaydi va hodisalarni RAM ga yig'adi — agent har soniyada `HB` yuborgani uchun bizda
o'zgarish kerak emas. Avariya xabarida (`{"ev":"holat","alarm":1}`) `uskuna` maydoni
bo'lmaydi va agent uni holat sifatida O'QIMAYDI — aks holda avariya «stanok to'xtadi»
bo'lib yozilardi.

**Firmware v1.19–v1.22 (2026-09-22…24), agent 1.8.0:**

- **v1.22 — tasdiq (ACK).** Muhim hodisa (`olchov`, `ogoh`, `avariya_toxtash`,
  `tiqilish`, `uskuna`, `boot`) `xb` (yonish belgisi, 8 hex) va `xq` (raqam) bilan
  keladi va Pico RAM ida (300 tagacha) `ACK <xb> <xq…>` kelmaguncha qoladi — har
  5 soniyada 40 tagacha qayta yuboriladi. Agent `xb`/`xq` ni to'g'ridan-to'g'ri
  `session`/`seq` qilib oladi (`_kromka_xbxq`), takrorni navbatga umuman qo'ymaydi
  va tasdiqni FAQAT server 200 qaytargandan keyin yozadi (`_kromka_acked` →
  `_kromka_ack`). Aks holda uzilgan internetdagi o'lchov Pico'da ham o'chib,
  bizda ham yozilmay yo'qolardi — rover bilan bir xil qoida.
  ⚠️ **Agent 1.8.0 dan pastini v1.22 Pico bilan ishlatib bo'lmaydi**: tasdiq
  bo'lmagach Pico qayta yuboraveradi, agent esa har takrorni yangi hodisa deb yozadi.
  **Agent 1.10.0 — tartibsiz kelish.** Agent uzilgan paytda yig'ilgan zaxirani Pico
  40 talab qayta yuboradi va orasiga jonli o'lchov tushadi (1..40, 61, 41..60).
  1.10.0 gacha takror «eng katta `xq`» bilan aniqlanardi va 41..60 tashlanardi: ular
  MES ga yetmas, tasdiqlanmay Pico RAM ida abadiy aylanardi. Endi `xq` TO'PLAMI
  saqlanadi; server yozgan `xq` Pico'dan qayta kelsa (bizning ACK yetib bormagan) —
  tasdiq qayta yuboriladi.
- **v1.21 — qayta yuklanish sababi.** `boot` da `sabab` (`tok` | `wdt`), `HOLAT`
  javobida `sabab` va `up` (ms). Xom holida `payload` ga tushadi, kod o'zgarmadi.
- **v1.20 — ovoz Pico'dan MES tomoniga o'tdi.** Rele almashganda `{"ev":"sig",...}`
  keladi. Agent uni UZATMAYDI: lampa fazasi bizda ishlatilmaydi va har miltillash
  `andon_event` ga bitta yozuv bo'lardi. `yigilgan` (xotira hisoboti) ham shunday.
- **v1.19 — navbat sig'imi va juftlash chegarasi** — Pico ichida, agentga tegmaydi.

## Rover Pico'si — CNC 2130 (v1.7.0+)

Uchinchi xil Pico (firmware alohida repoda: `jasper2233/cnc2130-oyy-mes`). Oldingi
ikkitasidan farqi — **ikki tomonlama** aloqa: bu Pico gapirish uchun kompyuterni
eshitishi SHART.

| | Kromka | Rover (CNC 2130) |
|---|---|---|
| Qator | `{"ev": ...}` | `{"t": ...}` (`hello`/`state`/`event`/`log`) |
| Yurak urishi | agent `HB` yuboradi | agent **kompyuter VAQTINI** yuboradi (har 10 s). 30 s jim qolsa Pico «kompyuter yo'q» deb hodisalarni fleshga yig'a boshlaydi |
| Soat | Pico'da yo'q, vaqt agentdan | xuddi shunday (DS3231 ulanmagan) |
| Tasdiq | yo'q | **bor**: hodisa `ack` kelmaguncha Pico'da qoladi va har 10 s qayta keladi |
| Kalit | agent beradi | hodisaniki — Pico'ning `seq` i (fleshda saqlanadi, takrorlanmaydi) |

**Tasdiq qoidasi:** agent `{"t":"ack","seq":N}` ni FAQAT server hodisani yozgandan
keyin yuboradi (`andon_shipper` → `_rover_acked`). Erta tasdiqlansa, internet
uzilgan paytdagi hodisa Pico'da o'chib, bizda ham yozilmay yo'qolardi.

Tasdiq UMUMIY — Pico N gacha hammasini o'chiradi. Shuning uchun 1.10.0 dan N —
server yozgan **uzilishsiz** qatorning oxiri: 21, 22, 24 yozilgan-u 23 hali yo'lda
bo'lsa tasdiq 22. 1.10.0 gacha partiyadagi eng katta seq (24) tasdiqlanardi, takror
esa «eng katta seq» bilan tashlanardi — zaxira bilan jonli hodisa aralashganda (21,
22, 24, 23) 23 navbatga tushmay Pico'da ham o'chib, BUTUNLAY yo'qolardi. Takror
endi seq TO'PLAMI bilan aniqlanadi; Pico allaqachon tasdiqlangan seq ni qayta
yuborsa (tasdiq yetib bormagan) — tasdiq qayta aytiladi. Server partiyani 422 bilan
rad etsa, u Pico'ga ham tasdiqlanadi: qayta yuborish tuzatmaydi, tasdiqsiz esa
uzluksiz tasdiq o'sha joyda abadiy to'xtab, Pico jurnali to'lib qolardi.

**Nima yoziladi:**
- `state` (har 10 s) — jonli holat; holat (shpindel aylanyapti / stanok yoqiq,
  shpindel to'xtagan / o'chiq) o'zgarganda kromkadagi bilan BIR XIL `uskuna`
  hodisasi (`holat` 1/0, yonida `pwr`). Server `pwr=1, holat=0` ni bo'sh turish
  (IDLE), `pwr=0` ni o'chiq (OFF) deb hisoblaydi (`docs/12` §4.15). v1.9.0 gacha
  hodisa faqat `holat` o'zgarganda yozilardi — bo'sh turgan stanok o'chirilsa
  bu bilinmasdi. Bir xil holat qayta yozilmaydi.
- `event` — Pico o'zi o'lchab tugatgan davr (`POWER_ON`, `SPINDLE_IDLE`,
  `UNPLANNED_STOP`, `AUTO_SHUTDOWN`, `SHUTDOWN_FAILED`, `POWER_CYCLE`,
  `PLANNED_STOP`, `LOG_FULL`). Serverga `kind="rover"` bo'lib boradi, asl turi
  `payload.rover_type` da (`type` ni server sxemasi o'zi uchun band qilgan).

**Sozlama** har ulanishda bir marta yuboriladi: `t_reason` (default 300 s — MES
dagi umumiy chegara bilan bir xil) va `auto_shutdown` (default **o'chiq**:
avtomatik o'chirishga tsexda kuzatuvdan keyin o'tiladi).

Portni faqat BITTA dastur ocha oladi: agent ochgach ularning `usb_panel.html`
sahifasi va `tools/stanok.py` ishlamaydi. Windows'da *USB selective suspend*
o'chirilgan bo'lsin, aks holda port uxlab qoladi.
