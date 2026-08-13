# 09 — MES domen qatlami (TT bo'yicha implementatsiya)

Holat: **2026-08-10**. TT (Texnik Topshiriq) repodan tashqarida yuritiladi — quyidagi `TZ x.y` havolalari
uning bo'lim raqamlari. Barcha fazalar implementatsiya qilingan — alohida `TODO.md` yuritilmaydi, holat shu hujjatlar to'plami va git tarixidan o'qiladi.

## 1. Data model (`app/models/`)

19 jadval, hammasi `BaseModel` (ID + timestamps + soft-delete):

| Jadval | Mazmun | TT |
|---|---|---|
| `organization` | Tenant (bitta: Mebelix), sxema multi-tenant tayyor | 4.1 |
| `post` | 9 bosqich: ARRA→KROMKA→OVAL→PRISADKA→ROVER→STOLYARKA→BO'YOQ→**QADOQLASH**→**TMO** (unit, order_index, flaglar), seed `app/commands/seed_defaults.py` — idempotent, order_index'ni mavjud bazalarda ham sinxronlaydi. `order_index` 5 bo'sh: eski PAZ posti olib tashlangan (paz ham frezer stanogida, ya'ni ROVER da kesiladi), qayta raqamlash mavjud bazalarda bekorga siljish beradi. OVAL fayldan avto-aniqlanmaydi: texnolog matritsada belgilaydi (route `per_instance=1`). QADOQLASH (`f1b6d0c73a25`, unit `m2` — ish haqi kvadratura bo'yicha) anketadagi `packaging` bayrog'i bo'yicha qo'shiladi; TMO (`a3f8d61c9b04`, `f2a08c47b6d1` da nomlandi, unit `piece`) esa HAR marshrutning ENG OXIRGI qadami | 4.4 |
| `machine` | Stanok (post FK, IP, capacity, holat) | 4.3 |
| `employee` | Beyjik egasi (badge_id UUID partial-unique, assigned_post_ids JSONB) | 4.2 |
| `client` | Mijoz (FIO, telefonlar, manzil, izoh; `client_type`/`inn` o'lik ustunlar sifatida olib tashlangan — migratsiya `c7f2d84a91b3`) | 4.6 |
| `material` | Katalog — .project fayldan avtomatik to'ladi | 4.5 |
| `order` | B-YYYY-NNN, status DRAFT→…→DELIVERED/CANCELLED; `amount` + `advance_payment` Numeric(14,2) (boshlang'ich to'lov, migratsiya `7d2c9f5e1b3a`); `cutmap` JSONB (5.7.5 modeli), `machine_assignments`, `material_usage`; `survey` JSONB — mijoz anketasi + o'lchov varag'i (migratsiya `a91c7d34f6e2`, §6.2) | 6 |
| `product`/`part`/`part_instance` | Fayl tarkibi; instance QR = `productCode_partCode` (yagona nusxa) / `productCode_partCode_n` (takror), kesish xaritasi katakchasiga bog'langan (pattern_no, cell_index); `part.is_custom` — nostandart detal bayrog'i (marshrutini texnolog qo'lda chizadi, migratsiya `e7c4b208af13`); `part.assembly_parent_id` — yig'ma buyum: mayda detal qaysi ASOSIY detalga yopishtiriladi (`c9d4e2f81a70`, §3.1) | 5.8 |
| `part_route` | Marshrutning BITTA QADAMI: `seq` (tartib, 1 dan) + post + `process_code` (1..14 — aynan qaysi amal) + per_instance (KROMKA tomonlar), total_required/done — QOLDIQ shu yerda. Yagonalik `(part_id, seq)` bo'yicha (`ix_part_route_part_seq`), post bo'yicha EMAS: bitta post marshrutda bir necha marta uchrashi mumkin (kromka → prisadka → yana kromka). Migratsiya `d5a1c93b70e2` | 5.4 |
| `scan` | Muvaffaqiyatli ish birligi; `client_event_id` UNIQUE (idempotency), bekor qilish belgisi; `parent_scan_id` — yig'ma buyumda asosiy detal skani yozgan hosila qatorlar (birga bekor bo'ladi, `c9d4e2f81a70`) | 8.4 |
| `pachka`/`pachka_item` | Qadoq va uning tarkibi (`7e2e0ae9f7f3`): `code` = chekdagi QR (`PK-{buyurtma}-{NN}`, PARTIAL UNIQUE), `status` open→closed→shipped, `closed_at`/`shipped_at`. Bitta nusxa faqat bitta qadoqda — `ix_pachka_item_instance` PARTIAL UNIQUE | Upakovka |
| `work_session` | Smena (beyjik → sessiya) | 8.2 |
| `order_file` | project / scx / hujjatlar (diskda `UPLOAD_DIR` ostida); `meta` JSONB — anketa xona rasmlari uchun `{"room_id", "content_type"}` | 2.4.3 |
| `audit_log` | Kim-qachon-nima (`crud/audit.py: log_action`, tranzaksiya ichida) | 10.11 |
| `bridge_agent` | Printerli kompyuterdagi chop etish agenti: `name`, `token_hash` (sha256, unique), bir martalik `pair_code` + `pair_expires_at` (15 daqiqa), `last_seen_at` (panelda "Ulandi"/"Uzilgan"); migratsiya `d5e81a24c3b7`. Qo'shimcha: `machine_id` — skan-forvard bog'lash (`f4b8c2a91e55`), `version` — agent exe versiyasi, WS handshake `X-Agent-Version` dan (`a7c3e9d12f04`), `can_print` — False bo'lsa printersiz stansiya chek navbatidan job olmaydi (`d4f7a8c25e91`) | 2.2.2 |

`user` jadvaliga qo'shildi: `role` (`UserRole`, 15 a'zo) + `machine_id`. Rollar ikki guruh
(`app/models/enums.py`):

- staff/qurilma: admin, director, manager, texnolog, terminal, tablo — terminal/TABLO qurilma
  akkauntlari stanokka biriktiriladi (TT 8.1 variant B);
- post-operator: arrachi, kromkachi, ovalchi, prisadkachi, roverchi, stolyar, boyoqchi,
  **upakovkachi**, **omborchi** — `POST_ROLES` mapping orqali postga bog'lanadi (ARRACHI→ARRA …
  OMBORCHI→TMO); o'z akkaunti bilan kiradi, **stanok biriktirish ham, beyjik ham shart emas**
  (login = smena, §3 ga qarang). `omborchi` rol KODI o'zgarmaydi (odamning kasbi), ekranda
  esa "TMO omborchisi" — materiallar ombori omborchisidan farqi ko'rinib tursin.

### 1.1 Atamalar (kelishilgan — kodda ham, ekranda ham shu)

| Atama | Nima | Nima EMAS |
|---|---|---|
| **TMO** | Tayyor Mahsulot Ombori — marshrutning oxirgi posti (`PostCode.TMO`) | "Ombor", "sklad", "tayyor mahsulot skladi" |
| **Materiallar ombori** | Xomashyo va qoldiqlar ombori (hozircha alohida modul yo'q — `/materials` bu KATALOG, qoldiq hisobi emas) | "Ombor", "sklad" |
| **Qadoqlash bo'limi** | `PostCode.UPAKOVKA` — marshrutning oddiy posti | "Upakovka ombori" — bunday ombor yo'q |

Yolg'iz "Ombor" va "sklad" ishlatilmaydi: tsexda ikkita ombor bor, nomsiz atalganda
qaysi biri ekani yo'qoladi. Boshqa tizimning ombori haqida yozilganda kimniki ekani
aytiladi ("GibLab ombori") — 10-giblab-reference.md dagidek.

## 2. GibLab parser (`app/services/giblab/`)

| Fayl | Vazifa |
|---|---|
| `models.py` | Parse natijasi dataclasslari (ORM emas): `ParsedProject/Product/Part`, `XncOp`, `ParsedMaterial`, `CutOperation` + `ParseError` (matni to'g'ridan texnologga ko'rsatiladi); `PROCESS_POSTS` — tsexning "Jarayon uchun kodlar" jadvali (jarayon kodi → post kodi, quyida) |
| `parser.py` | .project XML (to'la parser, regex YO'Q; cp1251/UTF-8; PROCESSED/TEMPLATE avlodlar; kontekstli id qidiruv); takror detal kodlari deterministik rename (`code`, `code-2`, …) + o'zbekcha warning — QR/SCX kaliti unikal qoladi. Detal NOMI marshrutga umuman ta'sir qilmaydi: eski `{7;11;8}` figurali qavs kodlari butunlay olib tashlangan, marshrut endi bazadagi tartibli qadamlar (quyida) |
| `xnc.py` | XNC program parse (atribut yoki bola element), xavfsiz ifoda hisoblash (`dz+3`), `merge_xnc_ops` — BARCHA operatsiyalar saqlanadi, (`side2`, `code`) bo'yicha tartiblanadi, soni cheklanmaydi (`parser.py` 2 tadan ko'pi uchun faqat ogohlantiradi) |
| `csblob.py` | CS `data` blob dekoderi: big-endian, 15B yozuvlar, guillotine daraxt, dims+117 root-o'q sloti, 5.7.4 self-check |
| `cutmap.py` | Vizual model (5.7.5): sheets/parts/cuts + holes overlay, rot/eW/eH, atxot foydali o'lcham, instance↔katakcha binding; har list uchun root-strip o'lcham zanjiri `dims` (ax/a/b/v, ≥10mm poloslar, GibSaw uslubi) — cutmap JSONida saqlanadi, terminal SVG chizadi |
| `scx.py` | SCX generatsiya — Nanxing haqiqiy konvensiyasi (Scx-korpusdan, 87 proyekt): Y=Width−y; qirra Face l4/r3/t1/b2; orqa dastur Face=6 bilan bitta faylda; 32mm qo'shqavat 16/Z÷2; freza kompensatsiyalangan yo'l. To'liq jadval: [10-giblab-reference.md](10-giblab-reference.md) §7.2 |
| `ingest.py` | DBga yozish: products/parts/instances/routes/materials/fayllar/cutmap/material_usage; qayta yuklash to'liq almashtiradi, LEKIN qo'lda chizilgan marshrutlar `snapshot_custom_routes`/`restore_custom_routes` bilan saqlanib tiklanadi (quyida); SCX fayl yozish+ro'yxatga olish `write_and_register_scx()` helperda — `/orders/{id}/scx/regenerate` ham shundan foydalanadi |

**O'lcham juftliklari (GibLab veb-ilovasida tekshirilgan).** Faylda har detalning
uch juft o'lchami bo'ladi: `dl/dw` — tayyor detal (kromka bilan), `jl/jw` — zagotovka
(kromkalanadigan tomonda tasma qalinligicha kichik), `cl/cw` — korpusda `dl/dw` bilan
bir xil. GibLab'ning **o'z kesish xaritasi ham `dl/dw` ni joylashtiradi**, shuning uchun
bizning xarita va yorlig'imiz ham shu o'lchamni ko'rsatadi — manba tizim bilan mos.
`jl/jw` bazada saqlanmaydi (o'lik `part.saw_length/saw_width` ustunlari `c7f2d84a91b3`
migratsiyasida olib tashlangan); parser o'lchamni `l → dl → cl → jl` zanjiri bilan
oladi (`cSizeMode` qaysi juft majburiyligini belgilaydi). GibLab'da o'lcham
kiritish rejimi ("Режимы ввода деталей") uchta: zagotovka, tayyor detal (kromka bilan),
prifugovkadan keyin (kromkasiz) — shu sozlama `dl/dw` ma'nosini belgilaydi.

**Standart marshrut (5.4) — fayldan chiqadigan uchta qadam, shu TARTIBDA:** ARRA (kod 1, listda
joyi bor detalga, per_instance=1) → KROMKA (kod 3, per_instance = ell/elr/elt/elb soni) →
PRISADKA (kod 6, bf/bt/bb/bl/br bo'lsa; per_instance = shu element bor XNC op soni, `_2` → 2).
Boshqa hech narsa avtomatik chiqmaydi.

Paz/freza uchun ROVER bosqichi **ataylab yaratilmaydi** (`ParsedPart.stage_sides()` endi FAQAT
prisadka qaytaradi): roverdan chiqqan detal keyin bo'yalishi ham, stolyarkaga ketishi ham mumkin —
buni fayl bilmaydi, ya'ni taxmin qilingan marshrut noto'g'ri bo'lardi. Paz/freza geometriyasi
baribir SCX ga va yorliq eskiziga ketadi, faqat marshrut qadami bo'lmaydi. ROVER, STOLYARKA va
BO'YOQ marshrutga faqat texnolog qo'li bilan tushadi.

**Nostandart detal — marshrutni texnolog chizadi.** Eski "marshrut detal NOMIDA" (`eshik {7;11;8}`)
mexanizmi butunlay olib tashlangan: nom qaytadan shunchaki nom, marshrut esa `part_route` da
tartibli qadamlar. Jarayon kodi → post o'girish `PROCESS_POSTS` (`giblab/models.py`) da qoladi —
to'liq jadval: [10-giblab-reference.md](10-giblab-reference.md) §2.3. Qoidalar:

- Bayroq `Part.is_custom` — texnolog detallar matritsasidagi "Nostandart" checkbox bilan qo'yadi.
  Yoqilganda fayldan kelgan `AUTO` qadamlar YUMSHOQ o'chiriladi, bayroq qaytarilganda AYNAN
  tiklanadi (`orders.py: edit_order_matrix`) — fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi.
- Marshrutning o'zi alohida **"Nostandart detallar" tabida** chiziladi
  (`Orders/CustomRoutes.tsx`): texnolog jarayonlarni bosadi, ular tanlangan tartibda 1, 2, 3…
  raqamlanadi va bitta kodni **takror tanlash mumkin** ([3, 6, 3] — kromkaga qaytish). Yo'l:
  `PATCH /orders/{id}/matrix` → `MatrixPartEdit.route_codes` → `_set_custom_route()` (eski
  qadamlar yumshoq o'chadi, ro'yxat qaytadan quriladi).
- **Marshrut faqat ARRA yoki ROVER'dan boshlanadi** (`_ROUTE_START_POSTS`, frontendda
  `ROUTE_START_POSTS`) — QR cheki aynan shu ikki postda chiqadi, boshqasidan boshlansa detal
  yorliqsiz qolardi.
- `per_instance`: KROMKA/OVAL marshrutda **BIRINCHI** kelganda qirralar soni marta skanlanadi
  (skan qirra bo'yicha sanaladi), TAKROR kelganda bitta. Qolgan postlarda bitta o'tish = bitta skan.
- Qaysi amal ekanini endi nom emas, qadamning **`process_code`** i saqlaydi (kodlar postga
  ko'p-birga tushadi: 1 va 2 → ARRA, 3 va 4 → KROMKA, 9..14 → STOLYARKA). Terminal amal NOMINI
  chip bilan ko'rsatadi (`Common/OperationChips.tsx` — `processCode` + `postCode` qabul qiladi,
  `lib/mes.ts: PROCESS_OPS`; bitta amalli postda — rover, bo'yoq, prisadka — chip chizilmaydi,
  post nomi sarlavhada turibdi).
- Sozlanmagan post uchrasa `ingest.py` toza `ParseError` (422) beradi: `posts` lug'ati post kodi
  bo'yicha tuziladi va `posts.get()` topmasa `None` qaytaradi — `PostCode(...)` chaqirilsa
  `ValueError` → 500 bo'lardi. `PROCESS_POSTS` qiymatlari `PostCode` enum'i (StrEnum, ya'ni
  qiymat baribir o'sha satr) — post lug'atlari ham shu kalit bilan tuziladi.
- **Qayta yuklash marshrutni yo'qotmaydi.** `.project` qayta yuklanishidan oldin
  `snapshot_custom_routes()` qo'lda kiritilgan (`MANUAL`) qadamlarni `(mahsulot kodi, detal kodi)`
  kaliti bilan eslab qoladi — detal kodi fayl ichidagi `part@id` dan farqli o'laroq qayta
  eksportda ham o'zgarmaydi. Nostandart detallar ham, matritsadan qo'lda qadam qo'shilgan
  STANDART detallar ham olinadi (`is_custom` bayrog'i bilan birga). Ingest'dan keyin
  `restore_custom_routes()` ularni tiklaydi: nostandart detalda marshrut TO'LIQ qo'lda, ya'ni
  fayldan qurilgani o'chadi; standart detalda esa qo'lda qo'shilgan qadam fayl qadamlariga
  QO'SHIMCHA edi — fayl qadamlari joyida qoladi, saqlanganlari ketidan tushadi. Yangi faylda
  topilmagan detallar warning'da sanaladi.


## 3. Scan engine (`app/services/scanning.py`)

Instance-level nazorat: QR → aktiv PRODUCTION buyurtma → shu postdagi marshrut QADAMLARI (`seq`
bo'yicha) → eng kichik `seq` li TUGALLANMAGAN qadam + stanok mosligi → per-instance limit →
yozish + `total_done++`. Hisob POST emas, QADAM bo'yicha: `_scans_done(db, instance_id, route_id)`
kaliti `route_id` — bitta post marshrutda ikki marta bo'lsa (kromka → prisadka → kromka) post
bo'yicha sanash hisobni aralashtirib yuborardi. `total_done` SQL tomonda oshiriladi/kamaytiriladi
(`UPDATE ... SET total_done = total_done ± 1`): Python tomondagi o'qib-yozish ikki terminal bir
vaqtda skanlaganda bitta inkrementni yo'qotardi va qadam `total_required` ga hech qachon
yetmasdi — buyurtmani faqat bazani qo'lda tuzatib yopish mumkin bo'lardi. Xatolar TT 8.5 kodlari bilan (`{"code": "E00x",
"message": ...}` 422 detail). Idempotency: `client_event_id` UNIQUE — takror so'rov `duplicate:true`
bilan muvaffaqiyat. `STRICT_STAGE_ORDER` (endi default **yoqiq**) — E004: tekshiruv postlarning
global tartibidan emas, detalning O'Z marshruti bo'yicha: `seq` i kichik qadamlar shu nusxada
tugamaguncha keyingisi rad etiladi, xabar navbatdagi post nomini aytadi.
60s ichida bekor qilish; COMPLETED regress. Bosqich tugashi → `order.stage_completed`, hammasi →
`COMPLETED` + `order.completed`.

### 3.0 Xato kodlari (TT 8.5)

Rad etilgan skan `422 {"code": "E00x", "message": "..."}` qaytaradi. **Kod kim
harakat qilishini aytadi, matn esa nima qilishini** — matn tahrirlanadi, kod
barqaror qoladi, shuning uchun mantiq (terminal ovozi, hisobot guruhlashi)
faqat kodga tayanadi. Ilgari terminal o'zbekcha xabardan "yakunlangan" bo'lagini
qidirardi — matn tahrirlanishi bilan jimgina buziladigan bog'lanish.

| Kod | Ma'nosi | Kim tuzatadi |
|---|---|---|
| `E001` | Detal/plan mos kelmadi: bu QR bo'yicha tugallanmagan plan yo'q, bu post detal marshrutida yo'q, detal boshqa stanokka biriktirilgan, detal roverda kesiladi | Operator — chekni va postni tekshiradi |
| `E002` | QR formati buzuq (`_` yo'q) | Operator — chekni qayta chop etadi |
| `E003` | Buyurtma bekor qilingan | Manager |
| `E004` | Navbat buzildi: shu NUSXAda oldingi qadam tugamagan (`STRICT_STAGE_ORDER`); xabar navbatdagi post nomini aytadi | Operator — oldingi postni kutadi |
| `E005` | Aktiv sessiya yo'q yoki `SESSION_MAX_HOURS` (12 soat) o'tgan | Operator — beyjikni skanerlaydi |
| `E006` | Beyjik: topilmadi / nofaol / hodim bu postga biriktirilmagan | Admin yoki hodim |
| `E007` | Aloqa yo'q — **server kodi emas**, WS uzilganda terminal frontendi o'zi hosil qiladi, so'rov serverga umuman ketmaydi | — |
| `E008` | Ish allaqachon bajarilgan (shu nusxaning shu postdagi qadamlari to'lgan). Xato emas — terminal neytral ogohlantirish ovozini beradi | Hech kim — takror skan |
| `E009` | SOZLAMA xatosi: post topilmadi, postda stanok yo'q, terminalga stanok biriktirilmagan | **Admin** — operator hech narsa qila olmaydi |

`E008` va `E009` 2026-08-12 da `E001` dan ajratildi: u 12 xil sababni qamrab
olgani uchun kod amalda hech narsa bildirmasdi va mijoz matn qidirishga majbur
edi. `E001`–`E006` raqamlari TT dan kelgan, tegilmagan.

Rad etilgan urinish `log_rejected_scan()` orqali audit logga yoziladi
(`module=scan, action=rejected`, `meta={"code": ...}`) — hisobotda kod bo'yicha
guruhlash shundan ishlaydi.

Operator-rol oqimi (`resolve_terminal` / `active_session`): arrachi…omborchi uchun post roldan
aniqlanadi (`POST_ROLES`); stanok — `user.machine_id`, bo'lmasa postning birinchi o'chirilmagan
stanogi (faqat soft-delete tekshiriladi, holat emas — NOAKTIV/TA'MIRDA stanok ham tushishi mumkin).

**Smena YAGONA joyda ochiladi — terminalda** (`open_badge_session`): beyjik skani yoki ekrandagi
"Kim ishlayapti?" ro'yxatidan ismni bosish. `active_session` hech qachon smena ochmaydi: brigada
bo'sh bo'lsa E005, smena egasi nofaol bo'lsa E006.

**QURILMA ≠ ODAM.** Monoblok TERMINAL hisobi bilan BIR MARTA, o'rnatishda kiradi va boshqa hech
qachon parol termaydi — tsexda klaviatura yo'q, qurilma tokeni 90 kunlik va har ishlatilganda
yangilanadi (`DEVICE_REFRESH_TOKEN_EXPIRE_DAYS`). Kim ishlayotgani esa HAR smenada yoziladi. Bu
ikkisini bir narsa deb qarash eng qimmat xato bo'lardi: "bir marta kirib eslab qolsin" degan yechim
qurilmani tanitadi, lekin ertaga boshqa odam kelganda hamma skan kechagi odamga yozilib ketardi.

Ismni bosish AUTENTIFIKATSIYA emas, **ATRIBUTSIYA**: qurilma allaqachon tanitilgan va ekran tsex
ichida, stanok yonida turibdi, ya'ni sir so'rashning ma'nosi yo'q — uzoqdan hech kim tegolmaydi.
Shu sabab PIN kodi qurilib, keyin OLIB TASHLANDI: u 4 raqamni hamma oldida terishni talab qilardi,
ya'ni kuzatib turgan odamdan himoya qilmasdi — himoya qilmaydigan narsani himoya qilardi.

Ilgari post rollari uchun "login = smena" shoxi bor edi: `operator_employee` hisobga soxta hodim
yozuvi yaratib ("Arrachi", "Omborchi" — ismi rol nomi) smenani o'sha nomdan ochardi. Post rollari
parol bilan kira olmagach (§3.0.2) u shox smena ocholmay qoldi va butunlay olib tashlandi.
`c7e2b4f81d39` mavjud mirror yozuvlarni NOFAOL qiladi va ularning ochiq smenalarini yopadi;
yozuvlar O'CHIRILMAYDI — ularda haqiqiy skan tarixi bor. Natijada **`Hodimlar` = odamlar,
`Foydalanuvchilar` = loginlar** va ular kesishmaydi.

#### Brigada — bitta stanokda ikki kishi

ARRA da ikki kishi birga ishlaydi: biri varaqni beradi, ikkinchisi detalni oladi va taxlaydi.
Detalni qaysi biri olganini bilishning **iloji yo'q** — ish qo'shma, ya'ni har skanda operator
tanlashni so'rash soxta ma'lumot berardi.

Shuning uchun stanokda bir nechta ochiq smena bo'lishi mumkin (`crew_sessions`):

| Amal | Natija |
|---|---|
| beyjik / ism (sukut) | brigadani ALMASHTIRADI — ochiq smenalar yopiladi |
| `join=true` ("+ Qo'shish") | brigadaga QO'SHILADI |
| `/session/end?employee_id=` | FAQAT o'sha odamniki yopiladi, qolgani ishlayveradi |

Almashtirish ATAYLAB sukut: ketayotgan odam yakunlashni unutsa, keyingi kirish eski smenani yopadi
— unutish xavfsiz tomonga og'adi. Qo'shilish esa ataylab so'raladi, aks holda ikkalasiga ham jimgina
ish yozilib ketardi.

Ish haqi va mahsuldorlik: skan qatorida bitta `employee_id` bor (LANGAR smena egasi), shuning uchun
hisobot uni SANAMAYDI — har skan o'z VAQTIDA ochiq bo'lgan smenalar orasida teng bo'linadi
(`reports.py`, `count() OVER (PARTITION BY scan.id)`). Ikki kishi birga ishlagan skan har biriga
0.5 yoziladi: zavod bir ishga bir marta to'laydi. `scan.machine_id` NULL bo'lsa (stanoksiz yozuv)
`COALESCE` uni eski yo'l bilan `scan.employee_id` ga yozadi — skan hisobdan tushib qolmasin.

### 3.0.1 Beyjik bilan kirish (tsexda parol yo'q)

Operator login/parol termaydi va **hech qanday o'rnatish qadami yo'q**: kirish sahifasi ochilib
turgan istalgan brauzerda beyjik skani kirishga aylanadi.

Beyjik ikkala savolga javob beradi — KIM va QAYERDA (`login.py`):

| Qadam | Nima |
|---|---|
| 1 | `badge_id` → `employee`. Noma'lum yoki nofaol beyjik — 401 |
| 2 | `employee.assigned_post_ids` → post (`_badge_post`). Bitta bo'lsa so'ralmaydi; bir nechta bo'lsa **409 + ro'yxat**, hodim monoblokda tanlaydi |
| 3 | Post → stanok (`_post_machine`): postning birinchi o'chirilmagan stanogi — `resolve_terminal` ham operator rolida aynan shunday tanlaydi |
| 4 | `_terminal_user`: shu stanokka biriktirilgan TERMINAL hisobi, bo'lmasa post roli hisobi. **Hisob KIM ishlayotganini bildirmaydi** — u beyjik ochgan `work_session` da |

3- va 4-qadam ataylab `resolve_terminal` bilan bir xil javob berishi kerak: aks holda operator
kirgandan keyin BOSHQA postning ekranida paydo bo'lardi.

**SEXDAGI HAR HODIMDA BEYJIK BOR.** Admin beyjiksiz — u mes.mebelix.uz ga login/parol bilan
kiradi; beyjik faqat tsexda ishlaydiganlarga. Shuning uchun `Hodimlar` ro'yxatidagi HAR bir yozuvga
beyjik chiqariladi.

`employee.user_id` ustuni (`d1c4e7a90b52`) endi ARXIV: u eski mirror yozuvlarni belgilaydi
(o'chirish taqiqlanadi — skan tarixi ularda) va kelajakda ishchi ayni paytda menejer ham bo'lsa
ishlatiladi. Yangi hodim qo'shganda foydalanuvchi tanlanmaydi: tsexdagi ishchi login qilmaydi.

**Xavfsizlik — ataylab qilingan tanlov (2026-08-12).** Beyjik yagona omil: QR qog'ozda va nusxa
olingan bo'lsa istalgan qurilmadan kirsa bo'ladi. Qurilma bog'lash (monoblokni stanokka bir
martalik kod bilan bog'lash) qurilib, keyin OLIB TASHLANDI — tsexda kod/parol terish smena
almashuvini sekinlashtiradi va amalda umumiy akkauntga olib keladi, ya'ni ish haqi atributsiyasini
butunlay yo'qotadi. Buning o'rniga:

- hisob imtiyozi tor — terminal ekranlari, admin paneli emas;
- har kirish audit logga tushadi (`module=sessions, action=started`);
- beyjik `employee.status` bilan darhol bekor qilinadi;
- chegara `30/60s` (`_BADGE_RATE_LIMIT`) — 122-bitli UUID brute-force qilinmaydi, tor chegara esa
  smena almashuvida butun tsexni (bitta tashqi IP) qulflab qo'yardi.

Frontendda skan **fokusni tortmaydi** (`hooks/useBadgeScan`): login sahifasida ofis xodimi ayni
paytda parol terayotgan bo'lishi mumkin. Skanerni odamdan tezlik ajratadi — belgilar orasi
120 ms dan oshsa bufer tozalanadi.

### 3.1 Yig'ma buyum (stolyarkada bir nechta detal birikadi)

Stolyarkada mayda detallar asosiy detalga yopishtirilib **yaxlit buyum** bo'ladi. Texnolog
"Nostandart detallar" tabida MAYDA detalda "Asosiy detal" ni tanlaydi — alohida "asosiy" bayrog'i
yo'q, detal unga kimdir biriktirilgani uchun asosiy bo'lib qoladi. Bir pog'ona: biriktirilgan
detalning o'zi asosiy bo'la olmaydi (`orders._set_assembly_parent` tekshiradi).

- **Marshrut birikish qadamida tugaydi**: `_set_custom_route` biriktirilgan detalga qadoqlash/TMO
  dumini QO'SHMAYDI — alohida detal endi mavjud emas, qadoqlovchi uni qidirmaydi.
  `_check_assembly_match` asosiy detal marshrutida o'sha amal borligini talab qiladi.
- **Skan kaskadi** (`scanning._close_assembly_children`): asosiy detal skani biriktirilgan
  detallarning birikish qadamini ham yopadi (`Scan.parent_scan_id` bilan bog'lanadi, bekor
  qilinganda birga qaytadi). Mayda detalning oldingi bosqichi tugamagan bo'lsa BUTUN skan E004
  bilan rad etiladi — chala detaldan yaxlit buyum yig'ilmaydi.
- Nusxalar soni bo'linmasa (5 mayda / 2 asosiy) asosiy detalning shu qadamdagi OXIRGI nusxasi
  qolgan hammasini yopadi.
- Terminal ro'yxatida biriktirilgan detallar alohida vazifa bo'lib chiqmaydi — asosiy detal
  qatorida "+ `01_007 ×2`" bo'lib ko'rinadi.

### 3.2 Nusxa darajasidagi tayyorlik (`pachka.instance_stages`)

`instance_stages(db, order, post)` → `instance_id -> (shu postga tayyormi, OXIRGI bajarilgan post
nomi)`. Bitta agregat so'rov (`Scan` bo'yicha `(instance_id, route_id)` guruhlash), N+1 yo'q.

Hisob NUSXA bo'yicha, detal bo'yicha EMAS: 4 nusxali detalning bittasi qadoqlansa,
`total_done >= total_required` hali bajarilmaydi — lekin o'sha bitta nusxa TMO ga tayyor. Detal
darajasida sanaganda qadoqlangan buyum TMO ro'yxatida "tsexda" bo'lib qolar va omborchi uni topa
olmasdi. Bosqich nomi sifatida **ishi TUGAGAN** post beriladi (kutilayotgani emas): detal jismonan
o'sha postdan keyin turadi va aynan o'sha yerdan olinadi.

Qadoqlash, TMO va post navbati (BOYOQ/STOLYARKA) ekranlari shu yagona funksiyadan foydalanadi.

Rad etilgan skan yakuni umumiy helperda — `log_rejected_scan()` (rollback + audit-log
`module=scan, action=rejected` + commit): terminal (`scans.py`) ham, stanok skan-forvardi
(`bridge_agents.py`) ham shu yo'ldan o'tadi, ya'ni operator ko'rmagan rad ham Loglar
sahifasida qoladi. `GET /scans/recent` endpointi olib tashlangan.

## 4. Real-time (`app/core/ws.py`, `api/routes/ws.py`)

- `/ws/events` — brauzer klientlar: JWT (cookie yoki `?token=`); rol → scope (terminal/tablo/dashboard),
  post/stanok bo'yicha filtrlash; `ping`→`pong` heartbeat.
- Fan-out Redis pub/sub (`mes:events`) orqali — gunicorn workerlar orasida; pool lifespan'da doim
  ochiladi (flag yo'q), publish xato bersa lokal yetkazishga tushadi.
- `/ws/bridge` — tsex bridge-agenti (per-agent pairing tokeni: `Authorization: Bearer` header, sha256
  → `bridge_agent.token_hash`; umumiy `BRIDGE_TOKEN` faqat legacy moslik): Redis `mes:print:queue`
  dan chop etish joblarini oladi, ack qilinmagan job qayta navbatga qaytadi. `can_print=False`
  agent (printersiz skan-forvard stansiyasi) navbatdan job OLMAYDI — brpop o'rniga sleep, aks
  holda u umumiy navbatdan chekni "o'g'irlab" lokalida qoldirardi. `touch_agent()` har
  5 daqiqada `last_seen_at` (va `can_print` ni) yangilaydi — token bekor qilingan bo'lsa jonli
  ulanish 4401 (`WS_CLOSE_UNAUTHORIZED`) bilan uziladi, qo'ldagi job navbatga qaytadi.
- **Skan-forvard (TZ 12.5)** — stanokning o'z skaneri o'qigan QR MES'ga ham yoziladi: agent
  klaviatura kiritishini tinglaydi (`pynput`; `SCAN_FORWARD=0` o'chiradi, pynput bo'lmasa jim
  o'chadi) va QR ko'rinishidagi tez terilgan qatorni `POST /bridge-agents/scan` ga agent tokeni
  bilan yuboradi. Skan agentga bog'langan stanok (`PATCH /bridge-agents/{id}` — `machine_id`,
  admin panel) AKTIV terminal sessiyasi nomidan yoziladi (`record_scan_at` — hisob-kitob odatdagi
  skan bilan bir xil); sessiya yo'q/stanok bog'lanmagan bo'lsa 409, rad etilgan skan audit logga
  tushadi (`log_rejected_scan`).

## 5. Yorliq chop etish (TT 12.3 / 13.2)

`app/services/labels.py` API: `LabelData`, `load_label_data(db, instance_id)`, `_n`,
`render_label_png`. Yagona chiqish — PNG rasm; `LabelData` maydonlari: qr_text, part_code,
part_name, project_name (`order.project_name or order.number`), order_number, material, l/w/t, count,
instance_no, edges, xnc_summary, label_num, printed_at (Asia/Tashkent — yorliq pastida sana bo'lib
chiqadi), **holes**, **texture**, **route_codes** (marshrut jarayon kodlari `seq` tartibida).
`holes` — `order.cutmap` dan shu detal katakchasi bo'yicha
(`part.label_num` → cutmap `parts[].num` → `cutmap.holes[cell.id]`).

**`render_label_png(d, scale=1)` — asosiy maket** (GibSaw `mebelix.lbl` uslubi). 80×60 mm,
203 dpi (8 dot/mm → 640×480 px), oxirida `point(... , "1")` bilan sof 1-bit; `draw.fontmode = "1"`
— antialiasing yo'q, aks holda termodrayver dither qiladi. Koordinatalar mm da. Tarkibi:

- chap ustun: `assets/label-logo.png` (threshold 160), `Formatka` + product kodi, detal kaliti,
  loyiha nomi, kromka materiallari 2×2 (t/l/b/r, tagchiziq bilan), markazda katta `L x W = soni`,
  `N_detal nomi`, teshik bo'lsa `assets/label-icon-drill.png` ikonkasi,
  marshrut ALOHIDA qatorda (`Marshrut: 7/11/8`, y=41.5mm — detal NOMIGA qo'shilmaydi, chunki nom
  24 belgida kesiladi va marshrut jimgina yo'qolardi). Marshrut satri **faqat nostandart detalda**
  (`part.is_custom`) chiqadi: standart detalning yo'li oldindan ma'lum, chekda u joyni behuda band
  qilardi; nostandartda esa operator keyingi postni aynan shundan biladi,
  pastda material + sana + `N{label_num} {instance_no}/{count}`;
- o'ng ustun: QR (`qrcode`, `d.qr_text`) tepada, ostida **vertikal detal eskizi** — ingichka kontur,
  kromka konturdan 1 mm tashqarida qalin chiziq, `texture` bo'lsa uzunlik bo'ylab 3 chiziq,
  cutmap'dagi **haqiqiy teshiklar** (`bores` aylana, `edge` qirra shtrixi), o'lchamlar en pastda va
  uzunlik o'ngda 90° aylantirilgan, har biri yoniga o'sha tomonlar kromka simvoli.

Chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qoladi.

Zanjir (terminal → printer) — GoDEX G500-U faqat USB, tarmoq porti yo'q, shuning uchun bitta yo'l:

```
terminal (POST /terminal/labels/{instance_id})   → label_printed_at + ws "label.printed"
  (DELETE o'sha path — chekni bekor qilish: label_printed_at=None + ws "label.cancelled";
   ARRA UI'da chiqarilgan katak yashil="kesildi", qayta chop etish bekor qilishdan keyingina)
  → arq task print_label (app/tasks/__init__.py)
     · render_label_png → LPUSH mes:print:queue = {type, instance_id, png(base64)}
  → /ws/bridge (per-agent token auth: Bearer → sha256 bridge_agent.token_hash; Redis brpop + ack;
     ack kelmasa rpush bilan navbatga qaytadi)
  → bridge-agent/agent.py → print-queue.jsonl → Windows GDI → USB GoDEX
```

`GET /terminal/labels/{instance_id}.png` — o'sha `render_label_png()` chiqishi to'g'ridan brauzerga;
worker ham, GoDEX ham, bridge-agent ham shart emas.

**Qadoq cheki** — `PachkaLabelData` + `render_pachka_label_png()`, arq task `print_pachka_label`
(qadoq yakunlanganda avtomatik). Tarkibi: logo, `QADOQ` + kod (4.6 mm bold), buyurtma raqami,
loyiha nomi, detallar soni, sana-vaqt va 28 mm QR (kod QR ostida ham takrorlanadi). Qadoq QR'i
detal QR'idan ajralib turadi: `PK-` bilan boshlanadi va ostki chiziq umuman yo'q, shuning uchun
`scanning._QR_RE` uni detal deb qabul qilmaydi — terminal skanni qaysi oqimga yuborishni shundan
biladi.

**KESISH POSTLARIDA CHOP ETISH = BAJARILDI.** ARRA'da arrachi xaritada katakni bosib chek
chiqaradi va alohida skan qilmaydi (xarita ochiqda terminalning skan maydoni yashirin);
ROVER'da esa marshrutida ARRA bo'lmagan detal roverning o'zida kesiladi. Ikkala holatda ham
`POST /terminal/labels/{id}` avto-skan yozadi (`record_scan`,
`client_event_id="cutprint-{instance_id}"`). Busiz `PartRoute.total_done` hech qachon
o'smasdi: buyurtma COMPLETED bo'lmasdi va qat'iy tartibda KEYINGI postlarning hammasi E004
bilan rad etilardi. Skan rad etilsa (oldingi bosqich tugamagan) chek baribir chiqadi —
operator keyin oddiy skan bilan yakunlaydi.

Chekni bekor qilish (`DELETE /terminal/labels/{id}`) shu avto-skanni ham bekor qiladi va
`total_done` ni qaytaradi; operator qo'lda qilgan skanga tegilmaydi.

`bridge-agent/agent.py` — tsexdagi mustaqil servis (websockets + pywin32 + Pillow): outbound WS,
lokal JSONL navbat `QUEUE_FILE` (printer/internet uzilganda yo'qotmaydi), flusher **event-driven** —
`FLUSH_EVENT` bilan darhol uyg'onadi, 5 s faqat zaxira timeout. `send_to_printer(png_b64)` bitta
yo'l: `_print_png_gdi()` — jobdagi PNG Windows drayveri orqali, DEVMODE'da qog'oz 80×60 mm ga
majburlanadi. Xatoda `False` qaytadi va job lokal navbatda qoladi.

Printer **avto-topiladi**: `_detect_printer()` nomida "godex" bor lokal Windows printerini qidiradi,
`PRINTER_NAME` faqat qo'lda override uchun. Agent faqat printer ulangan kompyuterga o'rnatiladi —
menejer, texnolog va boshqa terminallarga hech narsa kerak emas.

O'rnatish qadamlari: [07-infra-devops.md](07-infra-devops.md) → "Chop etish infratuzilmasi".

## 6. API xaritasi (yangi routerlar)

| Router | Prefix | Kirish |
|---|---|---|
| `clients/employees/machines/posts/materials` | CRUD + qidiruv | rol-based (`api/deps.py: require_roles`) |
| `orders` | lifecycle (`/confirm`, `/start`, …) + `/status-counts` + `/upload` + `/matrix` + `/machines` + `/cutmap` + `/files/{id}` + `/files/scx.zip` (barcha SCX bitta arxivda, `StaffReadUser`) + `/scx/regenerate` (SCX qayta generatsiya, `TexnologUser`; `write_and_register_scx` — ingest bilan umumiy helper) + `/survey` + `/survey/photos[/{file_id}]` | o'qish: manager/texnolog/director (`StaffReadUser`); yozish: manager/texnolog (+admin/superuser); anketa yozuvi: `ManagerUser` |
| `scans` | POST scan, DELETE undo (`/recent` olib tashlangan) | terminal + 9 operator rol |
| `terminal` | `/context`, `/session`, `/session/end`, `/orders` (loyiha kartalari: done/total post semantikasida — ARRA: chek∪skan, KROMKA: detal bo'yicha), `/orders/{id}/cutmap`, `/orders/{id}/kromka` (KROMKA/OVAL sahifasi), `/orders/{id}/prisadka` (detallar + SCX fayllar), `/orders/{id}/queue` (post navbati NUSXA darajasida — BOYOQ/STOLYARKA; postga bog'liq emas, kontekstdagi postni oladi), `/qr/{qr}/order` (QR→buyurtma), `/labels/{id}` POST (GoDEX navbat) / DELETE (chekni bekor qilish, manager/texnolog ham), `/labels/{id}.png`, `/files/{id}` | terminal + 9 operator rol; stanok/post konteksti (`_terminal_ctx` → `TerminalCtx`) har route'ga alohida qo'yiladi — yorliq/fayl route'lariga ataylab emas, ular stanoksiz ham ishlaydi; javoblar typed (`app/schemas/terminal.py`: `TerminalOrderCard`, `QrOrderRef`, `Kromka*`/`Prisadka*` modellari — `list[dict]` yo'q) |
| `pachka` | `/orders/{id}` GET (qadoqlash holati) / POST (yangi qadoq), `/{id}/scan` (detalni qadoqqa — bu AYNI paytda marshrutning UPAKOVKA qadami), `/{id}/items/{instance_id}` DELETE (xato skanni qaytarish — skan ham bekor bo'ladi), `/{id}/close` (yakunlash + chek) | terminal + operator rollar; faqat UPAKOVKA postida (`_pack_ctx`) |
| `tmo` | `/orders/{id}` GET, `/orders/{id}/accept` (QABUL — `PK-...` bo'lsa qadoq ichidagi HAMMA nusxa bitta skanda, aks holda bitta detal), `/orders/{id}/ship` (qadoqni topshirish), `/orders/{id}/deliver` (qadoqsiz buyurtmani butunligicha topshirish) | terminal + operator rollar; faqat TMO postida (`_wh_ctx`) |
| `tablo` | `/matrix`, `/orders/{id}` | istalgan auth |
| `reports` | `/productivity`, `/orders`, `/materials` (+`?format=xlsx`), `/dashboard` | manager/director/admin |
| `audit-logs` | filtrli ro'yxat (11 modul: users/orders/scan/print/sessions/bridge_agents/…; rad etilgan skanlar ham — `module=scan, action=rejected`, §3) | faqat admin (`AdminUser`, TZ 10.11) — butun tizim audit izi; direktor ishlab chiqarish ko'rsatkichlarini `/reports` dan oladi |
| `bridge-agents` | ro'yxat/yaratish, `/{id}` PATCH (stanok bog'lash + `can_print`), `/{id}/code` (yangi ulanish kodi), `/{id}` DELETE, `/pair`, `/scan` (skan-forvard, §4) | admin (`AdminUser`); `/pair` ochiq (router global auth'siz), `/scan` agent tokeni bilan. `/download` olib tashlangan (2026-08-02) — exe qo'lda tarqatiladi (`bridge-agent/README.md`) |

### Buyurtma lifecycle va to'lovlar

Manager buyurtmani narx (`amount`, ixtiyoriy `advance_payment`) kiritib yaratadi, so'ng
`POST /orders/{id}/confirm` — DRAFT → TECHNICAL_REVIEW (`amount` bo'lmasa rad etiladi). Texnolog
`.project` faylni **faqat tasdiqdan keyin** (TECHNICAL_REVIEW holatida) yuklay oladi. Fayl PROCESSED
bo'lishi ham shart: `parse_project` avlodni aniqlaydi (`processed` = CS `data` blob ham, `project.uuid`
ham bor; aks holda `template`), va `upload_order_project` TEMPLATE faylni **422** bilan rad etadi —
"Bu fayl GibLabda hali optimizatsiya qilinmagan…". Bundan oldin kengaytma (`.project`) va hajm
(`MAX_PROJECT_FILE_SIZE`) tekshiriladi.
`POST /{id}/start` (TECHNICAL_REVIEW → PRODUCTION) `.project` biriktirilgan bo'lishini va
`requires_assignment_choice` postlar uchun `machine_assignments` ni talab qiladi; **marshrutsiz
detal qolgan bo'lsa rad etadi** — u terminalda ham, TABLOda ham ko'rinmay, buyurtma usiz "tayyor"
bo'lib qolardi.
`GET /orders/status-counts` — registr tablari uchun har status bo'yicha son. Frontendda
qoldiq to'lov = `amount − advance_payment`, `advance ≤ amount` validatsiyasi bilan.

Texnolog ko'rinishi cheklangan (`orders.py: _hidden_statuses`): DRAFT va CANCELLED buyurtmalar
ro'yxatdan va `/status-counts` dan yashirin, to'g'ridan ID bilan GET ham 404 — buyurtma
texnologga confirm'dan keyin ko'rinadi.

### Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i)

Qog'oz forma o'rniga. Menejer to'ldiradi, texnolog
o'qiydi va shunga qarab dizayn yasaydi — ya'ni `.project` fayldan **oldingi** bosqich.

Saqlash joyi: `order.survey` JSONB, butun anketa bir butun sifatida yoziladi (qism-qism PATCH yo'q).
Sxema `app/schemas/orders.py`:

| Model | Mazmun |
|---|---|
| `OrderSurvey` | `version`, `measured_at` (o'lchov sanasi), `measured_by` (o'lchagan usta), `packaging`/`delivery`/`installation` — buyurtma darajasidagi bayroqlar (tsex bitta `.project` fayl ustida ishlaydi, logistika butun buyurtmani bitta mashinada olib ketadi: xona degan tushuncha ularga yetib bormaydi), `rooms` (max 10) |
| `SurveyRoom` | `id` (frontend beradigan barqaror kalit) + `name`; 2-bo'lim `furniture_types`/`furniture_other`; 3-bo'lim `shape`, `room_length/width/height`, `furniture_wall_length`; 4-bo'lim `corpus_materials`, `corpus_color`, `corpus_thickness`, `corpus_note`; 5-bo'lim `facade_materials`, `facade_color`, `countertop`, `facade_note`; 6-7 `hardware_level`, `extra_services`; 8 `note`; o'lchov varag'i `walls`, `modules`, `total_running_meters`, `total_height` |
| `SurveyWall` | A bo'limi: `letter` (A..E), `length`, `height` — max 8 ta |
| `SurveyModule` | B bo'limi: `name`, `wall`, `width`/`depth`/`height`, `count`, `note` — max 40 ta |

Barcha mm maydonlari `ge=0, le=50_000`, matnlar `max_length` bilan, ro'yxatlar cheklangan —
chegaralar tashqi kirish nuqtasida, aks holda bitta so'rov bazani to'ldirib yuboradi.
`model_config = extra="ignore"`. Variant **kodlari** (`ldsp`, `akril`, `burchak`, …) bazada,
matnga aylantirish faqat `frontend/src/lib/anketa.ts` da (`FURNITURE_TYPES`, `LAYOUT_SHAPES`,
`CORPUS_MATERIALS`, `CORPUS_THICKNESS`, `FACADE_MATERIALS`, `COUNTERTOPS`, `HARDWARE_LEVELS`,
`EXTRA_SERVICES`, `WALL_LETTERS` + `labelOf`/`labelsOf`) — yangi variant qo'shilganda migratsiya
kerak emas, saqlangan tarix ham buzilmaydi. Mijoz ma'lumotlari `client` da, narx/avans/muddat
`order` da — anketada takrorlanmaydi. Eski anketalarda `yetkazish`/`montaj` xona
`extra_services` ida edi: forma ochilganda ular buyurtma bayroqlariga ko'chiriladi va xona
ro'yxatidan olib tashlanadi (`_layout/anketa.$orderId.tsx`), keyingi avtosaqlash yangi
shaklni yozadi — migratsiya kerak emas.

Endpointlar (`app/api/routes/orders.py`, hammasi `ManagerUser`):

- `PUT /orders/{id}/survey` → `save_order_survey`. DELIVERED/CANCELLED buyurtmada 403. Saqlashda
  **yetim rasm tozalash**: `body.rooms` da yo'q `room_id` li `OrderFile` lar diskdan `unlink`,
  bazada soft-delete. Audit: `survey_saved`.
- `POST /orders/{id}/survey/photos` → `upload_room_photo`. `room_id` (Form) + `file`. Faqat
  `image/jpeg|png|webp` (`_ROOM_PHOTO_TYPES`), `MAX_ROOM_PHOTO_SIZE` 5 MB, xonaga
  `MAX_ROOM_PHOTOS` = 6 ta. Diskda `UPLOAD_DIR/survey/{order_id}/{uuid4().hex}{ext}`. Audit:
  `survey_photo_added`.
- `DELETE /orders/{id}/survey/photos/{file_id}` → `delete_room_photo`: diskdan ham o'chadi
  (anketa rasmlari tarix uchun saqlanmaydi). Audit: `survey_photo_deleted`.

Rasmlar **alohida jadval yaratmasdan** `OrderFile(kind=DOCUMENT, meta={"room_id", "content_type"})`
da — migratsiyasiz, anketa JSON'iga tegmaydi (avtosaqlash bilan poyga yo'q). Rasm `SurveyRoom.id`
ga bog'lanadi, xona ro'yxatdagi o'rni o'zgarsa ham yo'qolmaydi. `OrderFileRead.meta` shu sababli
qo'shilgan; `download_order_file` PROJECT/SCX uchun `application/xml`, qolganiga
`meta.content_type` beradi — aks holda brauzer `<img>` o'rniga faylni yuklab oladi.

O'qish: `GET /orders/{id}` javobida `OrderDetail.survey` — `StaffReadUser`, ya'ni texnolog va
direktor ham ko'radi.

### Hisobot yordamchilari

- `app/services/metrics.py: part_volume()` — TT 9.3.1 HAJM matematikasi (ARRA m², KROMKA metr,
  qolganlari dona; OVAL birligi metr bo'lsa ham dona bilan approksimatsiya — egri qirraning
  uzunligi detal bo'yicha saqlanmaydi),
  reports va tablo uchun umumiy. `Part` obyektini emas, `length`/`width`/`count`/`edges`
  qiymatlarini oladi — TABLO o'n minglab marshrutni ORM obyekti sifatida qurmay,
  faqat shu to'rt ustunni tanlab olishi uchun (o'lchov: 669 ms → 175 ms).
- `app/services/excel.py: xlsx_response()` — openpyxl bilan bitta varaqli .xlsx stream
  (reports `?format=xlsx` orqasida).
- Og'ir JSONB ustunlar ro'yxat so'rovlarida `defer()` bilan qoldiriladi:
  `ORDER_FAT_COLUMNS` (cutmap/survey/material_usage/machine_assignments) va
  `PART_FAT_COLUMNS` (xnc_summary/note) — `app/models/order.py` (o'lchov: reestr
  284 ms → 5 ms). Skan issiq yo'li uchun `qr_text` partial indeksi
  (`ix_part_instance_qr_text`, migratsiya `e8b1c6d94f27`).

## 7. Frontend tuzilishi

- Dizayn tokenlar: `src/index.css` (post/status ranglari, `.num`, print CSS); domen konstantalar `src/lib/mes.ts`.
- Imzo komponent: `Common/StagePipeline` — post zanjiri (dinamik, dashboard va buyurtma qatorlari).
- Routelar: `_layout/*` admin modullar (orders, clients, employees, machines, materials, reports,
  logs, printers, admin, settings, cutmap.$orderId, `anketa.$orderId`), `/terminal`, `/tablo`
  ("Jami" yig'indi qatori + rejimlar + drill-down; sarlavhada brend logo, stanokka bog'langan
  tablo akkauntida "JORIY NUQTA" chipi, onlayn indikatori va tablo bo'lmagan rollarga "Boshqaruv
  paneli" havolasi). "Jami" qatori hajmga bog'lanmagan — katakchalari tanlangan rejimga ergashadi:
  hajm — `X / Y` post birligida (m²/m/dona), soni — `done / total`, foiz — `%`. Tanlangan rejim
  `localStorage` da (`tablo-mode`) — TV qayta yoqilganda ham saqlanadi; yangi bundle uchun qayta
  yuklash soatiga bir marta va faqat drill-down yopiq bo'lganda. Katak qiymati OSHGANDA bir marta
  0.9 s yashil uriladi (`animate-cell-flash` / `@keyframes mx-cell-flash`, `src/index.css`) —
  devordagi ekranda o'zgargan raqamni ilib oladigan yagona signal; kamayishda (skan bekor
  qilinganda) urilmaydi. Yon menyu — `Sidebar/AppSidebar.tsx: NAV_ITEMS` (11 band); mobil
  sarlavhalar (`_layout.tsx: sectionTitles`) shu ro'yxatdan + `/settings`.
- Anketa UI: `_layout/anketa.$orderId.tsx` — xonalar pill bilan almashadi, 7 ta bo'lim + yopiladigan
  "O'lchov varag'i". Xona pillidagi × uni o'chiradi (tasdiq dialogi bilan; bitta xona qolganda ×
  yo'q). Xona pillari bilan raqamlangan bo'limlar orasida — bo'limlardan TASHQARIDA — "Butun
  buyurtma uchun" bloki (butun karta `canEdit` ostida: o'qish huquqidagi rollar uni ko'rmaydi):
  `ORDER_SERVICES` belgilari (Upakovka qilish / Yetkazib berish / O'rnatish (montaj)) va o'lchov
  sanasi + o'lchagan usta; xona almashganda o'zgarmaydi. `RoomSummary` da ikki alohida qator:
  "O'lchov" (sana — usta) va "Buyurtma bo'yicha" (tanlangan xizmatlar). Yozish huquqi
  `is_superuser || admin || manager`; boshqa rollarga forma emas,
  `RoomSummary` — o'qish uchun jamlanma (matn nusxa olinadi). Avtosaqlash: har tahrirdan 1.5 s
  keyin `PUT /survey` (qo'lda saqlash shart emas — pastdagi yopishqoq panelda holat va ixtiyoriy
  "Saqlash" tugmasi), `beforeunload` ogohlantirish + unmount'da fire-and-forget saqlash. Server
  javobi formaga **bir marta** yuklanadi (`loaded` ref) — aks holda refetch menejer yozayotgan
  matn ustiga tushadi.
- Buyurtma kartasi (`orders/$orderId.tsx`): `.project` uchun drag&drop zona (kengaytma tekshiriladi,
  boshqasiga xato toast) va anketaga o'tish tugmasi. Texnolog uchun DOIM tablar: "Detallar
  matritsasi" / "Nostandart detallar (N)" / "Furnituralar" (agar bor bo'lsa). Matritsa ustunlari
  faqat ARRA/KROMKA/PRISADKA (`STANDARD_MATRIX_POSTS`) + "Nostandart" checkbox ustuni; nostandart
  qatorda "Nostandart · N qadam" belgisi (marshrut yo'q bo'lsa — "Nostandart · marshrut yo'q").
  Katakcha shu postdagi HAMMA qadamni birga yoqadi/o'chiradi — qadam-baqadam tahrir nostandart
  tabda (`Orders/CustomRoutes.tsx`).
- `/terminal` post bo'yicha sahifalar (hammasi picker: `GET /terminal/orders` kartalari):
  · **ARRA** — materiallar → listlar → to'liq ekran xarita (`Terminal/CutmapView` +
    `Terminal/SheetSvg`; `printAllMaps` — har list A4 landscape). NOSTANDART detal xaritada
    BINAFSHA (`CutmapInstanceState.custom` ← `Part.is_custom`, `PART_CUSTOM`) — marshrutini
    texnolog qo'lda chizgan, u arradan boshlanmasligi ham mumkin. Chek chiqarilgan katak YASHIL
    ("kesildi") — nostandart detal ham; qayta chop etish bloklanadi; long press (~600ms) + tasdiq
    dialogi chekni bekor qiladi va katak o'z rangiga qaytadi (admin webdagi xaritada —
    kartochkadagi tugma).
  · **KROMKA** (`Terminal/KromkaView`) — ikki panel: chapda arradan chiqqan detallar
    (tugaganlari yashil, pastda), o'ngda "Jarayonda" (2+ tomonli, boshlangan, tugamagan).
    Har skan darhol yoziladi (tomon = skan, `per_instance`); bir QR uchun 5 s to'siq;
    picker'da skan qilinsa proyekt o'zi ochiladi (`/qr/{qr}/order`); begona detalga aniq xato.
  · **OVAL** — o'sha KromkaView `oval` rejimda: bir panel, har detal BITTA skan.
  · **PRISADKA** (`Terminal/PrisadkaView`) — detallar + SCX fayllar; "Hammasini yuklab olish"
    File System Access API bilan BIR MARTA tanlangan papkaga (IndexedDB'da saqlanadi,
    `lib/scxDir.ts`) proyekt nomli subpapka ochib yozadi; har skandagi avto-SCX ham o'sha yerga.
  · **ROVER** — o'sha PrisadkaView, lekin SCX butunlay yashirin (`showScx=false`, avto-yuklash
    ham o'chiq — roverga SCX kerak emas): har jismoniy nusxa ALOHIDA qator, chap ustunda katta
    "Chop etish" tugmasi (`Terminal/usePrintLabel.ts`); marshrutida ARRA bo'lmagan detalda chek
    chiqarish avto-skan yozadi (§5 "ROVER'da chop etish = bajarildi").
  · **BO'YOQ / STOLYARKA** (`Terminal/PostQueueView`, `GET /orders/{id}/queue`) — NUSXA
    darajasidagi navbat: "kelgan" (oldingi bosqichi tugagan) → skan → "bajarilgan". Yetib
    KELMAGAN detal ro'yxatda ko'rsatilmaydi (uni skanerlab bo'lmaydi, E004 chiqadi) — faqat
    "yana N detal tsexda" satri. Qatorda material (bo'yoqchi uchun bu RANG), texnolog izohi,
    amal chipi (stolyarkada olti xil amal) va yig'ma buyum bo'lsa biriktirilgan mayda detallar.
    Sarlavhalar postga moslanadi (`LABELS`).
  · **QADOQLASH** (`Terminal/UpakovkaView`) — "Qadoq yaratish" → detallarni birma-bir
    skanerlash → "Yakunlash" (chek QR bilan chiqadi). Tarkibni algoritm emas, qadoqlovchi
    belgilaydi; tizim faqat taxminiy og'irlikni KO'RSATADI (hajm × 700 kg/m³) va hech narsani
    bloklamaydi. Bloklanadigan yagona narsa — marshrut tartibi.
  · **TMO** (`Terminal/TmoView`) — ikki tab. **Qabul**: TMO ga yetib kelganlar (qadoq kodi
    bilan), qadoq QR'i bitta skanda ichidagi hammasini qabul qiladi; pastda "Tsexda" ro'yxati,
    har detalga ishi TUGAGAN post yozilgan (omborchi uni o'sha yerdan topadi). **Topshirish**:
    qadoqlangan buyurtmada har qadoq alohida (to'liq qabul qilinmagani topshirilmaydi),
    qadoqsizda butun buyurtma; hammasi topshirilgach buyurtma DELIVERED.
  Qadoqlash va TMO skani ekranning O'ZIDA yoziladi (`viewScanRef` — umumiy skan yo'li
  chetlab o'tiladi): detal qaysi qadoqqa tushishini yoki qabulmi/topshirishmi ekanini faqat
  o'sha ekran biladi, qadoq QR'i esa umumiy yo'lda "QR noto'g'ri formatda" bo'lib rad etilardi.
  Umumiy: majburiy to'liq ekran overlay, lock overlay, operator logout, 2 s umumiy QR cooldown
  (TT 8.4.4), skan chizig'i 15 s da o'zi yo'qoladi, skan inputi fokussiz ham QR ni tutadi
  (birinchi tugmada fokus), yangi build uchun har 5 daqiqada `/` HEAD ETag tekshiruvi va xavfsiz
  paytda avto-reload.
- WS hook: `hooks/useMesWs.ts` (reconnect + heartbeat + online flag).
- Rol-marshrutlash: `_layout.tsx` beforeLoad (`lib/guards.ts: requireAuth`) — terminal va
  9 operator rol → `/terminal`, tablo → `/tablo` (qurilma/operator akkauntlar admin panelga
  kira olmaydi).

## 8. Sozlamalar (yangi env)

Backend: `UPLOAD_DIR`, `MAX_PROJECT_FILE_SIZE`, `STRICT_STAGE_ORDER`, `SESSION_MAX_HOURS`,
`SCAN_UNDO_SECONDS`, `BRIDGE_TOKEN` — ixtiyoriy **legacy** moslik: bo'sh bo'lsa ham `/ws/bridge`
ishlaydi (agentlar admin paneldagi pairing tokeni bilan ulanadi), faqat eski umumiy tokenli
agentlar uchun to'ldiriladi.

Bridge-agent (`bridge-agent/agent.py`, backend settings'ida emas — o'z env'i): `MES_URL`
(default `ws://localhost:8000`), `BRIDGE_TOKEN` (pairing bergan per-agent token — birinchi ishga
tushishda `%APPDATA%\MebelixAgent\.env` ga o'zi yoziladi; qo'lda berish faqat legacy holat), `PRINTER_NAME`
(ixtiyoriy — avto-topish o'rniga qo'lda), `QUEUE_FILE` (default
`%APPDATA%\MebelixAgent\print-queue.jsonl` — avtostartda ishchi papka System32 bo'lgani uchun;
exe yonidagi eski fayl birinchi ishga tushishda bir marta ko'chiriladi), `SCAN_FORWARD`
(default yoqiq; `0` — stanok skanerini MES'ga forvard qilish o'chadi, §4).
