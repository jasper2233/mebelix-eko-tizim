# 09 — MES domen qatlami (TT bo'yicha implementatsiya)

Holat: **2026-08-29**. TT (Texnik Topshiriq) repodan tashqarida yuritiladi — quyidagi `TZ x.y` havolalari
uning bo'lim raqamlari. Barcha fazalar implementatsiya qilingan — alohida `TODO.md` yuritilmaydi, holat shu hujjatlar to'plami va git tarixidan o'qiladi.

## 1. Data model (`app/models/`)

19 jadval, hammasi `BaseModel` (ID + timestamps + soft-delete):

| Jadval | Mazmun | TT |
|---|---|---|
| `organization` | Tenant (bitta: Mebelix), sxema multi-tenant tayyor | 4.1 |
| `post` | 9 bosqich: ARRA→KROMKA→OVAL→PRISADKA→ROVER→STOLYARKA→BO'YOQ→**QADOQLASH**→**TMO** (unit, order_index, flaglar; rang MODELDA EMAS — frontend `POST_COLORS` konstantasida), seed `app/commands/seed_defaults.py` — idempotent, order_index'ni mavjud bazalarda ham sinxronlaydi va u tartibning YAGONA egasi (`PostUpdate` da `order_index` yo'q — PATCH tahriri keyingi prestart'da qaytarilardi). `order_index` 5 bo'sh: eski PAZ posti olib tashlangan (paz ham frezer stanogida, ya'ni ROVER da kesiladi), qayta raqamlash mavjud bazalarda bekorga siljish beradi. OVAL fayldan avto-aniqlanmaydi va detallar matritsasida ustuni ham YO'Q (`STANDARD_MATRIX_POSTS` faqat ARRA/KROMKA/PRISADKA): texnolog uni "Nostandart detallar" tabida jarayon kodi 5 bilan marshrutga qo'shadi; `per_instance` HAR DOIM 1 — oval kromkada detal bitta o'tishda ishlanadi (`c3d97a1e5b02`, §2); qirralar soni bo'yicha ko'paytirish (`first_edge_pass`) FAQAT `PostCode.KROMKA` uchun ishlaydi. QADOQLASH (`f1b6d0c73a25`, unit `m2` — ish haqi kvadratura bo'yicha) anketadagi `packaging` bayrog'i bo'yicha qo'shiladi; TMO (`a3f8d61c9b04`, `f2a08c47b6d1` da nomlandi, unit `piece`) esa HAR marshrutning ENG OXIRGI qadami | 4.4 |
| `machine` | Ish markazi (post FK, holat `MachineStatus`); `ip_address` ustuni olib tashlangan — migratsiya `b1f27ce03d94` | 4.3 |
| `employee` | Beyjik egasi (badge_id UUID partial-unique, assigned_post_ids JSONB) | 4.2 |
| `client` | Mijoz (FIO, telefonlar, manzil, izoh; `client_type`/`inn` o'lik ustunlar sifatida olib tashlangan — migratsiya `c7f2d84a91b3`) | 4.6 |
| `order` | B-YYYY-NNN (yil — `Asia/Tashkent` bo'yicha, `crud/orders.next_number`), status DRAFT→…→DELIVERED/CANCELLED; `amount` + `advance_payment` Numeric(14,2) (boshlang'ich to'lov, migratsiya `7d2c9f5e1b3a`); `cutmap` JSONB (5.7.5 modeli), `machine_assignments`, `material_usage`; `survey` JSONB — mijoz anketasi + o'lchov varag'i (migratsiya `a91c7d34f6e2`, §6.2) | 6 |
| `product`/`part`/`part_instance` | Fayl tarkibi; instance QR = `productCode_partCode` (yagona nusxa) / `productCode_partCode_n` (takror), kesish xaritasi katakchasiga bog'langan (pattern_no, cell_index); `part.is_custom` — nostandart detal bayrog'i (marshrutini texnolog qo'lda chizadi, migratsiya `e7c4b208af13`); `part.assembly_parent_id` — yig'ma buyum: mayda detal qaysi ASOSIY detalga yopishtiriladi (`c9d4e2f81a70`, §3.1) | 5.8 |
| `part_route` | Marshrutning BITTA QADAMI: `seq` (tartib, 1 dan) + post + `process_code` (1..16 — aynan qaysi amal: 1..14 texnolog tanlaydigan amallar, 15/16 — tizim qo'shadigan dum, `TAIL_CODES`) + per_instance (KROMKA tomonlar), total_required/done — QOLDIQ shu yerda. Yagonalik `(part_id, seq)` bo'yicha (`ix_part_route_part_seq`), post bo'yicha EMAS: bitta post marshrutda bir necha marta uchrashi mumkin (kromka → prisadka → yana kromka). Migratsiya `d5a1c93b70e2` | 5.4 |
| `scan` | Muvaffaqiyatli ish birligi; `client_event_id` UNIQUE (idempotency), bekor qilish belgisi; `parent_scan_id` — yig'ma buyumda asosiy detal skani yozgan hosila qatorlar (birga bekor bo'ladi, `c9d4e2f81a70`) | 8.4 |
| `pachka`/`pachka_item` | Qadoq va uning tarkibi (`7e2e0ae9f7f3`): `code` = chekdagi QR (`PK-{buyurtma}-{NN}`, PARTIAL UNIQUE), `status` open→closed→shipped, `closed_at`/`shipped_at`. Bitta nusxa faqat bitta qadoqda — `ix_pachka_item_instance` PARTIAL UNIQUE | Upakovka |
| `work_session` | Smena (beyjik → sessiya) | 8.2 |
| `order_file` | project / scx / hujjatlar (diskda `UPLOAD_DIR` ostida); `meta` JSONB — anketa xona rasmlari uchun `{"room_id", "content_type"}` | 2.4.3 |
| `audit_log` | Kim-qachon-nima (`crud/audit.py: log_action`, tranzaksiya ichida) | 10.11 |
| `waste_item` | FOYDALI atxot (GibLab `business="true"`) — saqlashga arziydigan yirik qoldiq: `qr_text` = `ATX-{buyurtma}-{n}` (PARTIAL UNIQUE), material, list raqami, foydali o'lcham va `label_printed_at`. Mayda qoldiq bu jadvalga tushmaydi (GibSaw xulqi bilan bir xil). Marshrutda yurmaydi — vazifasi chek chiqarib ID ni yo'qotmaslik | 5.7.5 |
| `bridge_agent` | Printerli kompyuterdagi chop etish agenti: `name`, `token_hash` (sha256, unique), bir martalik `pair_code` + `pair_expires_at` (15 daqiqa), `last_seen_at` (panelda "Ulandi"/"Uzilgan"); migratsiya `d5e81a24c3b7`. Qo'shimcha: `machine_id` — skan-forvard bog'lash (`f4b8c2a91e55`), `version` — agent exe versiyasi, WS handshake `X-Agent-Version` dan (`a7c3e9d12f04`), `can_print` — False bo'lsa printersiz stansiya chek navbatidan job olmaydi (`d4f7a8c25e91`) | 2.2.2 |

`user` jadvaliga qo'shildi: `role` (`UserRole`, 15 a'zo) + `machine_id`. Rollar ikki guruhga
bo'linadi (`app/models/enums.py`):

- staff/qurilma: admin, director, manager, texnolog, terminal, tablo — terminal/TABLO qurilma
  akkauntlari ish markaziga biriktiriladi (TT 8.1 variant B);
- post-operator: arrachi, kromkachi, ovalchi, prisadkachi, roverchi, stolyar, boyoqchi,
  **upakovkachi**, **omborchi** — `POST_ROLES` mapping orqali postga bog'lanadi (ARRACHI→ARRA …
  OMBORCHI→TMO); odatdagi yo'l — `/login/badge`. Parol bilan kirish ROLGA emas, HISOB TURIGA
  bog'liq: seed yaratgan `is_system=True` hisob 401 oladi, odamning shaxsiy hisobi esa kiradi va
  smenasi avtomat ochiladi (§3.0.1) — skaneri yo'q post uchun (ARRA). Beyjik yo'lida smena
  terminalda ochiladi (§3, §3.0.1). Ish markazi biriktirish shart
  emas: `resolve_terminal` postdan `scanning.post_machine` bilan topadi.
  `omborchi` rol KODI o'zgarmaydi (odamning kasbi), ekranda
  esa "TMO omborchisi" (`ROLE_LABELS`) — u ishlaydigan post nomi bilan.

### 1.1 Atamalar (kelishilgan — kodda ham, ekranda ham shu)

| Atama | Nima | Nima EMAS |
|---|---|---|
| **TMO** | Tayyor Mahsulot Ombori — marshrutning oxirgi posti (`PostCode.TMO`) | "Ombor", "sklad", "tayyor mahsulot skladi" |
| **Ish markazi** | `Machine` modeli / `machine` jadvali — postdagi jismoniy ish nuqtasi: monoblok yoki stanok qayerda tursa, smena shu yerda ochiladi, skan shu yerga yoziladi. UI da "Ish markazi", URL `/work-centers`. Nom SAP `Arbeitsplatz` / 1C «рабочий центр» / APICS *work center* dan; ISA-95 da `Post` = Work Center darajasi, bu esa Work Unit | "Stanok" — ARRA/KROMKA/OVAL/PRISADKA/ROVER da haqiqiy stanok bor, STOLYARKA/BOYOQ/UPAKOVKA/TMO da esa faqat brigada + monoblok. Klass va jadval nomi `machine` qoladi (5 jadval `machine_id` FK bilan bog'langan), lekin FOYDALANUVCHI hech qayerda "stanok" so'zini ko'rmaydi |
| **Qadoqlash bo'limi** | `PostCode.UPAKOVKA` — marshrutning oddiy posti | "Upakovka ombori" — bunday ombor yo'q |

Bu MENYU VA URL ga ham tegishli: ish markazlari sahifasi "Ish markazlari" / `/work-centers` (ilgari "Stanoklar" / `/machines` edi — 9 ta yozuvning 4 tasida stanok yo'q). GibLab material katalogi sahifasi BUTUNLAY OLIB TASHLANDI (`d2b71f4c86e9`): u `.project` fayllaridan avtomat to'lardi va hech kim o'qimasdi. Material sarfi `Order.material_usage` dan hisoblanadi, yorliq va kesish xaritasi `Part.material_name` dan.

Yolg'iz "Ombor" va "sklad" ishlatilmaydi: tsexda tayyor mahsulot omboridan tashqari
xomashyo ombori ham bor (u MESda yuritilmaydi), nomsiz atalganda qaysi biri ekani
yo'qoladi. Boshqa tizimning ombori haqida yozilganda kimniki ekani
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
| `ingest.py` | DBga yozish: products/parts/instances/routes/fayllar/cutmap/material_usage + foydali atxotlar (`WasteItem`, `ATX-{buyurtma}-{n}`; cutmap katagiga `atx` raqami yoziladi — frontend WasteItem'ni shundan topadi) (`material` jadvali `d2b71f4c86e9` da olib tashlangan); qayta yuklash to'liq almashtiradi, LEKIN qo'lda chizilgan marshrutlar `snapshot_custom_routes`/`restore_custom_routes` bilan saqlanib tiklanadi (quyida); SCX fayl yozish+ro'yxatga olish `write_and_register_scx()` helperda; butun qayta yaratish sikli esa `rebuild_order_scx()` + `purge_replaced_scx()` da — `/orders/{id}/scx/regenerate` ham, `PATCH /matrix` da detal soni o'zgarganda ham shu ikkitasi chaqiriladi |

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
PRISADKA (kod 6, XNC operatsiyasida teshik, paz yoki freza bo'lsa — `bf`/`bt`/`bb`/`bl`/`br`,
`gr`/`oq`/`oh`, `ms`/`ml`/`mac`; per_instance = **1** — orqa yuz (`_2`) ham o'sha bitta skan, chunki SCX
ikkala yuzni bitta faylga birlashtiradi va stanok bir yurgizishda ag'darib ishlaydi; ilgari old+orqa = 2
skan talab qilinar, prisadkachi bitta detalni «0/2» deb ko'rardi — eski qadamlarni migratsiya 1 ga tushirgan).
Fayldan boshqa qadam chiqmaydi; ustiga `ingest.py` tizim DUMINI qo'shadi — UPAKOVKA
(kod 15, anketada `packaging` bo'lsa) va TMO (kod 16, DOIM, eng oxirgi qadam).

Paz/freza uchun ROVER bosqichi **ataylab yaratilmaydi** (`ParsedPart.stage_sides()` endi FAQAT
prisadka qaytaradi): roverdan chiqqan detal keyin bo'yalishi ham, stolyarkaga ketishi ham mumkin —
buni fayl bilmaydi, ya'ni taxmin qilingan marshrut noto'g'ri bo'lardi. Paz/freza geometriyasi
baribir SCX ga va yorliq eskiziga ketadi, faqat ROVER qadami bo'lmaydi — pazli/frezali detal
PRISADKA qadamini oladi (aks holda u ARRA→TMO bo'ylab ishlov KO'RMASDAN o'tib ketardi). ROVER, STOLYARKA va
BO'YOQ marshrutga faqat texnolog qo'li bilan tushadi.

**Nostandart detal — marshrutni texnolog chizadi.** Eski "marshrut detal NOMIDA" (`eshik {7;11;8}`)
mexanizmi butunlay olib tashlangan: nom qaytadan shunchaki nom, marshrut esa `part_route` da
tartibli qadamlar. Jarayon kodi → post o'girish `PROCESS_POSTS` (`giblab/models.py`) da qoladi —
to'liq jadval: [10-giblab-reference.md](10-giblab-reference.md) §2.3. Qoidalar:

- Bayroq `Part.is_custom` — texnolog detallar matritsasidagi "Nostandart" checkbox bilan qo'yadi.
  Yoqilganda fayldan kelgan `AUTO` qadamlar YUMSHOQ o'chiriladi, bayroq qaytarilganda AYNAN
  tiklanadi (`orders/matrix.py: edit_order_matrix`) — fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi.
- Marshrutning o'zi alohida **"Nostandart detallar" tabida** chiziladi
  (`Orders/CustomRoutes.tsx`): texnolog jarayonlarni bosadi, ular tanlangan tartibda 1, 2, 3…
  raqamlanadi va bitta kodni **takror tanlash mumkin** ([3, 6, 3] — kromkaga qaytish). Yo'l:
  `PATCH /orders/{id}/matrix` → `MatrixPartEdit.route_codes` → `_set_custom_route()`. Eski
  QO'LDA chizilgan (`MANUAL`) qadamlar BUTUNLAY o'chadi — `delete(PartRoute)`, fayldan
  kelgan `AUTO` qadamlar esa yumshoq o'chadi; ro'yxat qaytadan quriladi. Manual qadam yumshoq
  o'chirilsa avlodlar to'planib, bayroq standartga qaytarilib yana yoqilganda hammasi tiklanib
  (`edit_order_matrix` `MANUAL` ni AYNAN shunday tiklaydi) `(part_id, seq)` yagonaligini
  buzardi. **ISTISNO — skan TEGGAN manual qadam** (`PartRoute.id.in_(select(Scan.route_id))`):
  u ham yumshoq o'chadi, chunki `scan.route_id` NOT NULL FK va `ON DELETE` yo'q — qattiq
  o'chirish 500 (ForeignKeyViolation) berardi; `ix_part_route_part_seq` faqat `NOT is_deleted`
  uchun yagona, ya'ni o'chiq turgan qator to'qnashuv bermaydi.
- **Marshrut faqat ARRA yoki ROVER'dan boshlanadi** (`_ROUTE_START_POSTS`, frontendda
  `ROUTE_START_POSTS`) — QR cheki aynan shu ikki postda chiqadi, boshqasidan boshlansa detal
  yorliqsiz qolardi.
- `per_instance`: KROMKA marshrutda **BIRINCHI** kelganda qirralar soni marta skanlanadi (har qirra alohida yopishtiriladi), takror kelganda 1. OVAL esa HAR DOIM 1 — oval kromkada detal bitta o'tishda ishlanadi (`c3d97a1e5b02`). Qolgan postlarda bitta o'tish = bitta skan. Qoida UCHALA yo'lda bir xil hisoblanadi: fayldan ingest (`ingest.py`), qo'lda marshrut (`_set_custom_route` — `first_edge_pass`) va matritsadagi bosqich katakchasi (`edit_order_matrix` — katakcha yoqilganda qadam hali yo'q, ya'ni bu birinchi o'tish). `total_required = part.count * per_instance`.
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
  STANDART detallar ham olinadi. Qadamlar bilan birga faylda MAVJUD BO'LMAGAN yana ikki narsa
  saqlanadi (`PartSnapshot`): texnolog IZOHI (`part.note`) va O'CHIRIB qo'yilgan qadamlarning
  jarayon kodlari (`is_enabled=False`) — ikkalasi ham qayta yuklashda jimgina yo'qolardi
  (izoh bo'shab qolardi, o'chirilgan amal esa qayta yonardi). O'chirilgan bayroq AUTO qadamda
  ham turishi mumkin, shuning uchun snapshot buyurtmaning hamma tirik qatorini o'qiydi va
  tiklash oxirida detal bo'yicha bitta `UPDATE`ni qaytaradi. `is_custom` va
  `assembly_parent_id` bayroqlari MANUAL qatordan emas, DETALNING O'ZIDAN o'qiladi: "Nostandart" deb belgilangan yoki yig'maga
  biriktirilgan detalda hali bironta ham qo'lda qadam bo'lmasligi mumkin (matritsa bayroqni
  yoqqanda MANUAL qator YOZMAYDI, faqat AUTO qatorlarni yumshoq o'chiradi) — bayroqlar
  qatorlarga bog'lansa qayta yuklashda jimgina yo'qolardi. Ingest'dan keyin
  `restore_custom_routes()` ularni tiklaydi: nostandart detalda marshrut TO'LIQ qo'lda, ya'ni
  fayldan qurilgani o'chadi (kodlar saqlanmagan bo'lsa marshrut bo'sh qoladi — dum ham
  qo'shilmaydi). Qadamlarni qurish qoidasi `_set_custom_route` bilan BITTA:
  ikkalasi ham `giblab/routes.py: build_manual_route()` ni chaqiradi; standart detalda esa qo'lda
  qo'shilgan qadam fayl qadamlariga QO'SHIMCHA edi — fayl qadamlari joyida qoladi,
  saqlanganlari DUMDAN (UPAKOVKA/TMO) OLDIN qo'yiladi va dum ular soniga suriladi
  (`park_tail`/`unpark_tail`, matritsadagi yangi qadam bilan bitta helper). Aks holda
  tiklangan qadam TMO dan keyin tushib, qat'iy tartibda mangu `E004` berardi. Yangi faylda
  topilmagan detallar warning'da sanaladi.
- **Qayta yuklash yiqilsa fayllar joyida qoladi.** `wipe_previous_parse()` eski
  `.project`/SCX qatorlarini yumshoq o'chiradi va fayllarni diskda `<yo'l>.stale` ga qayta
  nomlaydi (yangi ingest aynan o'sha nomlarga yozadi: SCX nomi = QR, project nomi = fayl
  nomi). Ingest har qanday xato bilan yiqilsa `db.rollback()` dan keyin
  `restore_stale_files()` eskilarni asl nomiga qaytaradi (yarim yozilgan yangining
  ustidan), muvaffaqiyatda `db.commit()` dan keyin `drop_stale_files()` `.stale` larni
  o'chiradi. Ilgari unlink tranzaksiya ichida edi — ParseError'da DB orqaga qaytar,
  fayllar esa mangu yo'qolardi.
- **Marshrut birikish qadamida tugaydi**: `_set_custom_route` biriktirilgan detalga qadoqlash/TMO
  dumini QO'SHMAYDI — alohida detal endi mavjud emas, qadoqlovchi uni qidirmaydi.
  `_check_assembly_match` asosiy detal marshrutida o'sha amal borligini talab qiladi — bog'lam
  o'zgarganda ham, biriktirilgan detalning `route_codes` i qayta chizilganda ham.
- **Skan kaskadi** (`scanning._close_assembly_children`): asosiy detal skani biriktirilgan
  detallarning birikish qadamini ham yopadi (`Scan.parent_scan_id` bilan bog'lanadi, bekor
  qilinganda birga qaytadi). Mayda detalning oldingi bosqichi tugamagan bo'lsa BUTUN skan E004
  bilan rad etiladi — chala detaldan yaxlit buyum yig'ilmaydi.
- Nusxalar soni bo'linmasa (5 mayda / 2 asosiy) asosiy detalning shu qadamdagi OXIRGI nusxasi
  qolgan hammasini yopadi.
- Terminal ro'yxatida biriktirilgan detallar alohida vazifa bo'lib chiqmaydi — asosiy detal
  qatorida "+ `01_007 ×2`" bo'lib ko'rinadi.

**Nusxani topish — QR buyurtmaga bog'lanmagan** (`scanning.record_scan_at`). QR satri
`{productCode}_{partCode}[_n]` (`docs/11`), yagona indeks esa faqat `(order_id, qr_text)`
bo'yicha: bir xil GibLab kodlaridan yig'ilgan IKKI jonli buyurtma bitta QR ni ulashishi
mumkin. Dvijok mos keluvchi jonli (PRODUCTION/CANCELLED) qatorlarni oladi; to'qnashuv deb FAQAT
PRODUCTION qatorlar sanaladi (CANCELLED faqat E003 xabari uchun — bekor qilingan buyurtma o'sha
.project dan qayta yaratilsa qr_text bir xil bo'ladi) va PRODUCTION qatorlar birdan
ko'p bo'lsa `E001` — "Bu QR bir nechta buyurtmada uchradi — managerga murojaat qiling" —
beradi. Ilgari `ORDER BY order.id DESC` bilan JIMGINA eng yangi buyurtmaga yozardi, ya'ni
skan boshqa buyurtmaning hisobiga tushib ketardi. Diqqat: bu tekshiruv faqat skan
dvijokida; `terminal.py resolve_terminal_qr` (QR → buyurtma sahifasi) hali ham eng
yangisini tanlaydi.

### 3.2 Nusxa darajasidagi tayyorlik (`scanning.instance_stages`)

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

**WS eventlarini tarqatish — `publish_scan_events(outcomes)`** (`scanning.py`), FAQAT
commitdan keyin chaqiriladi. Bitta skan uchun uni `finalize_scan` chaqiradi; TMO qabuli
(`tmo.accept_into_tmo`) va qadoqqa skan (`pachka.scan_into_pachka`) esa bir nechta skanni
bitta tranzaksiyada yozib o'z javobini qaytargani uchun to'g'ridan-to'g'ri shuni chaqiradi.
Ilgari o'sha ikki yo'l `record_scan_at` qaytargan `ScanOutcome` ni umuman TASHLAB
YUBORARDI: `scan.recorded` boshqa terminallarga bormasdi (terminal ekranidagi jonli lenta
uni tinglaydi), `order.stage_completed`/`order.completed` esa efirga umuman chiqmasdi.
Buyurtma STATUSI baribir to'g'ri yozilardi — yo'qolgani faqat WS xabari edi.

## 4. Real-time (`app/core/ws.py`, `api/routes/ws.py`)

- `/ws/events` — brauzer klientlar: JWT (`Authorization: Bearer` header yoki access cookie; `?token=`
  query ATAYLAB qabul qilinmaydi — access-loglariga sizardi); rol → scope (terminal/tablo/dashboard),
  post/ish markazi bo'yicha filtrlash; `ping`→`pong` heartbeat. Heartbeat'da token har **300 s** da
  qayta tekshiriladi (`_RECHECK_SECONDS`): logout (`token_version` bump) yoki hisobni
  o'chirish/nofaol qilish ochiq soketni ham **4401** bilan yopadi. Tekshiruv BEKOR QILINGANLIK
  bo'yicha (`resolve_user(..., verify_exp=False)`): ulanishdagi access token 30 daqiqada eskiradi,
  tablo/terminal soketi esa kun bo'yi ochiq — muddat bo'yicha uzish har ekranni yarim soatda
  uzib qayta ulardi. DB xatosi ulanishni uzmaydi.
- Fan-out Redis pub/sub (`mes:events`) orqali — gunicorn workerlar orasida; pool lifespan'da doim
  ochiladi (flag yo'q), publish xato bersa lokal yetkazishga tushadi.
- `/ws/bridge` — tsex bridge-agenti (per-agent pairing tokeni: `Authorization: Bearer` header, sha256
  → `bridge_agent.token_hash`; umumiy `BRIDGE_TOKEN` faqat legacy moslik): Redis `mes:print:queue:{agent_id}`
  dan chop etish joblarini oladi, ack qilinmagan job qayta navbatga qaytadi. `can_print=False`
  agent (printersiz skan-forvard stansiyasi) navbatdan job OLMAYDI — brpop o'rniga sleep, aks
  holda u umumiy navbatdan chekni "o'g'irlab" lokalida qoldirardi. `touch_agent()` har
  5 daqiqada `last_seen_at` (va `can_print` ni) yangilaydi — bu ZAXIRA tekshiruv. Token bekor
  qilinganini Redis bayrog'i (`agent_revoked_key` → `mes:agent:revoked:{id}`, TTL 10 daqiqa)
  HAR brpop siklida (~5 s) ushlaydi: jonli ulanish 4401 (`WS_CLOSE_UNAUTHORIZED`) bilan uziladi,
  qo'ldagi job navbatga qaytadi. Ilgari yagona tekshiruv 5 daqiqalik `touch_agent` edi va bekor
  qilingan token yana ~5 daqiqa chek chiqaraverardi (prod-repro bilan o'lchandi: 295 s).
- **Skan-forvard (TZ 12.5)** — ish markazining o'z skaneri o'qigan QR MES'ga ham yoziladi: agent
  klaviatura kiritishini tinglaydi (`pynput`; `SCAN_FORWARD=0` o'chiradi, pynput bo'lmasa jim
  o'chadi) va QR ko'rinishidagi tez terilgan qatorni `POST /bridge-agents/scan` ga agent tokeni
  bilan yuboradi. Skan agentga bog'langan ish markazi (`PATCH /bridge-agents/{id}` — `machine_id`,
  admin panel) AKTIV terminal sessiyasi nomidan yoziladi (`record_scan_at` — hisob-kitob odatdagi
  skan bilan bir xil); sessiya yo'q/ish markazi bog'lanmagan bo'lsa 409, rad etilgan skan audit logga
  tushadi (`log_rejected_scan`) VA `scan.rejected` WS eventi bilan (`post_id` + `machine_id` bo'yicha)
  terminal ekraniga chiqadi — ilgari bu holat faqat agent logiga tushar, stanokda skanerlagan
  operator skanini yo'qotganini bilmasdi. `ATX-`/`PK-` QR bu yo'ldan o'tsa `SKIP` bilan jimgina
  chetlab o'tiladi, beyjik UUID'i esa `BADGE` bilan (§3.0).

## 5. Yorliq chop etish (TT 12.3 / 13.2)

`app/services/labels.py` API — to'rt xil chek, hammasi 80×60 mm va bitta printer zanjiri:
`LabelData` + `load_label_data(db, instance_id)` + `_n` + `render_label_png` (detal),
`PachkaLabelData`/`render_pachka_label_png` (qadoq), `WasteLabelData`/`render_waste_label_png`
(foydali atxot), `BadgeLabelData`/`render_badge_png` (hodim beyjigi). Mos arq tasklari —
`print_label`, `print_pachka_label`, `print_waste_label`, `print_badge`
(`app/tasks/__init__.py: all_tasks`). Yagona chiqish — PNG rasm; `LabelData` maydonlari: qr_text, part_code,
part_name, project_name (`order.project_name or order.number`), order_number, material, l/w/t, count,
instance_no, edges, xnc_summary, label_num, printed_at (Asia/Tashkent — yorliq pastida sana bo'lib
chiqadi), **holes**, **texture**, **route_codes** (marshrut jarayon kodlari `seq` tartibida).
`holes` — `order.cutmap` dan shu detal katakchasi bo'yicha
(`part.label_num` → cutmap `parts[].num` → `cutmap.holes[cell.id]`).

**`render_label_png(d, scale=1)` — asosiy maket** (GibSaw `mebelix.lbl` uslubi). 80×60 mm,
203 dpi (8 dot/mm → 640×480 px), oxirida `point(... , "1")` bilan sof 1-bit; `draw.fontmode = "1"`
— antialiasing yo'q, aks holda termodrayver dither qiladi. Koordinatalar mm da. Tarkibi:

- chap ustun: `assets/label-logo.png` (threshold 160), `Formatka` + product kodi, detal kaliti,
  loyiha nomi (`text(..., max_mm=34)` — `draw.textlength` bo'yicha QR chap chetigacha kesiladi;
  ilgari 26 belgi limiti turardi va u QR'ni hisobga olmagani uchun uzun nomning dumi
  QR ostida ko'rinmay qolardi), kromka materiallari 2×2 (t/l/b/r, tagchiziq bilan), markazda katta `L x W = soni`,
  `N_detal nomi`, teshik bo'lsa `assets/label-icon-drill.png` ikonkasi,
  marshrut ALOHIDA qatorda (`Marshrut: 7/11/8`, y=41.5mm — detal NOMIGA qo'shilmaydi, chunki nom
  24 belgida kesiladi va marshrut jimgina yo'qolardi). Marshrut satri **faqat nostandart detalda**
  (`part.is_custom`) chiqadi: standart detalning yo'li oldindan ma'lum, chekda u joyni behuda band
  qilardi; nostandartda esa operator keyingi postni aynan shundan biladi,
  pastda material + sana + `N{label_num} {instance_no}/{count}`;
- o'ng ustun: QR (`qrcode`, `d.qr_text`) tepada, ostida **vertikal detal eskizi** — ingichka kontur,
  kromka konturdan 1 mm tashqarida qalin chiziq, `texture` bo'lsa `l` O'QI bo'ylab 3 chiziq — yo'nalish eskizga ergashadi (`burilgan` bo'lsa vertikal, aks holda gorizontal; ilgari doim vertikal edi va 250×832 kabi l<w detalda chek teksturani 90° noto'g'ri ko'rsatib, kesish xaritasi bilan mos kelmasdi),
  cutmap'dagi **haqiqiy teshiklar** (`bores` aylana, `edge` qirra shtrixi; burilgan eskizda HAQIQIY 90° burilish `(x,y)→(y, l−x)` — xarita va GibSaw bilan bitta konvensiya, ilgari transpose/oyna edi), o'lchamlar en pastda va
  uzunlik o'ngda 90° aylantirilgan, har biri yoniga o'sha tomonlar kromka simvoli.

Chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qoladi.

Zanjir (terminal → printer) — GoDEX G500-U faqat USB, tarmoq porti yo'q, shuning uchun bitta yo'l:

```
terminal (POST /terminal/labels/{instance_id})   → label_printed_at + ws "label.printed"
  (DELETE o'sha path — chekni bekor qilish: label_printed_at=None + ws "label.cancelled";
   ARRA UI'da chiqarilgan katak yashil="kesildi", qayta chop etish bekor qilishdan keyingina)
  → arq task print_label (app/tasks/__init__.py)
     · render_label_png → LPUSH mes:print:queue:{agent_id} = {type, job_id, instance_id, png(base64)}
  → /ws/bridge (per-agent token auth: Bearer → sha256 bridge_agent.token_hash; Redis brpop + ack;
     ack kelmasa rpush bilan navbatga qaytadi)
  → bridge-agent/agent.py → print-queue.jsonl → Windows GDI → USB GoDEX
```

`GET /terminal/labels/{instance_id}.png` — o'sha `render_label_png()` chiqishi to'g'ridan brauzerga;
worker ham, GoDEX ham, bridge-agent ham shart emas. `load_label_data` nusxa, detal yoki
buyurtmaning biri yumshoq o'chirilgan bo'lsa `None` qaytaradi — PNG 404 beradi (POST/DELETE bilan
bir xil), `print_label` taski esa `skip:{id}` bilan jimgina o'tadi. Nusxalar matritsada count
kamayganda va `.project` qayta import qilinganda yumshoq o'chiriladi.

**Qadoq cheki** — `PachkaLabelData` + `render_pachka_label_png()`, arq task `print_pachka_label`
(qadoq yakunlanganda avtomatik; chek chiqmaydigan bo'lsa qadoq umuman yopilmaydi — pastdagi
"Qadoq cheki chiqmasa" ga qarang). Tarkibi: logo, `QADOQ` + kod (4.6 mm bold), buyurtma raqami,
loyiha nomi, detallar soni, sana-vaqt va 28 mm QR (kod QR ostida ham takrorlanadi). Qadoq QR'i
detal QR'idan ajralib turadi: `PK-` bilan boshlanadi va ostki chiziq umuman yo'q, shuning uchun
`scanning._QR_RE` uni detal deb qabul qilmaydi — terminal skanni qaysi oqimga yuborishni shundan
biladi.

**Qadoq cheki chiqmasa** — `close_pachka` chekni chiqara olishini commitdan OLDIN tekshiradi:
navbat (arq/Redis) o'chgan bo'lsa 503, postga printer biriktirilmagan bo'lsa 422 (`require_printer`
→ `NoPrinterBound`). Ikkalasida ham qadoq OCHIQ qoladi va qadoqlovchi shu tugmani qayta bosadi — aks holda
avval «Qayta ochish» qadamini bosish kerak bo'lardi.

**Yopilgan qadoqni tuzatish** — `POST /pachka/{id}/reopen` (terminalda "Qayta ochish"
tugmasi, yakunlangan qadoqlar ro'yxatida). Status OPEN ga qaytadi, `closed_at` tozalanadi,
audit `reopened` yoziladi; qayta yakunlash chekni navbatga yangidan qo'yadi, ya'ni chekni
qayta chiqarish yo'li ham shu. **Buyurtmada bir vaqtda faqat BITTA ochiq qadoq bo'ladi**
(`_open_of`): `create_pachka` ham, `reopen_pachka` ham ikkinchisini 409 bilan rad etadi —
terminal ekrani faqat bitta ochiq qadoqni ko'rsatadi, skan ham o'shanga tushadi. TMO ga qabul qilingan qadoq (nusxalarida jonli TMO skani bor) qayta OCHILMAYDI — 403; aks holda chiqarilgan detalning UPAKOVKA skani bekor bo'lib TMO skani qolar, marshrut o'rtasi ochilib qolardi.

**Foydali atxot cheki** — `WasteLabelData` + `render_waste_label_png()`, arq task
`print_waste_label`, yo'li `POST /terminal/waste/{waste_id}/label` (bekor qilish — o'sha path
DELETE). Arrachi uni kesish xaritasidagi ATXOT katagidan chiqaradi (§7). Detal chekidan farqi:
marshrut/skan tekshiruvi YO'Q — atxot ish bosqichi emas, saqlanadigan material; shuning uchun
bekor qilishda qaytariladigan skan ham yo'q, faqat `label_printed_at` tozalanadi.
`label_printed_at` ARQ vazifasida emas, ENDPOINTNING o'zida yoziladi — aks holda terminal
darhol qayta so'raganda katak rangi o'zgarmay qolardi. Eskiz yo'q: atxot to'rtburchak, chekda
katta O'LCHAM, material, buyurtma·loyiha·list va QR (`ATX-{buyurtma}-{n}`).

**Hodim beyjigi** — `BadgeLabelData` + `render_badge_png()`, arq task `print_badge`, yo'li
`POST /employees/{employee_id}/print` (`AdminUser`). Maket: lavozim (kichik) → ism (katta) → QR
(`badge_id` UUID), QR o'rni QAT'IY — ism bir yoki ikki qatorga tushishidan qat'i nazar beyjiklar
skaner uchun bir xil. Beyjikda ish markazi YO'Q (ofisdan chiqariladi), shuning uchun printer
ATAYLAB tanlanadi: `agent_id` berilsa o'sha, berilmasa `printing_agents(db)` dagi yagona agent,
bir nechta bo'lsa 422 + ro'yxat. Ilgari job manzilsiz qo'yilardi va uni umumiy navbatdan birinchi
ulgurgan printer olardi.

**KESISH POSTLARIDA CHOP ETISH = BAJARILDI.** ARRA'da arrachi xaritada katakni bosib chek
chiqaradi va alohida skan qilmaydi (xarita ochiqda terminalning skan maydoni yashirin);
ROVER'da esa marshrutida ARRA bo'lmagan detal roverning o'zida kesiladi. Ikkala holatda ham
`POST /terminal/labels/{id}` avto-skan yozadi (`record_scan`,
`client_event_id="cutprint-{instance_id}-{unix_ts}"`). Vaqt tamg'asi ataylab: doimiy kalitda chek
bekor qilinib qayta chiqarilsa idempotentlik tekshiruvi eski (bekor qilingan) qatorni topib
`duplicate` qaytarardi — yangi skan yozilmas, holat "Bajarilmagan" bo'lib qolardi.
Avto-skanning o'zi busiz esa `PartRoute.total_done` hech qachon
o'smasdi: buyurtma COMPLETED bo'lmasdi va qat'iy tartibda KEYINGI postlarning hammasi E004
bilan rad etilardi. Skan rad etilsa (oldingi bosqich tugamagan) chek baribir chiqadi —
operator keyin oddiy skan bilan yakunlaydi.

Chekni bekor qilish (`DELETE /terminal/labels/{id}`) shu avto-skanni ham bekor qiladi va
`total_done` ni qaytaradi; operator qo'lda qilgan skanga tegilmaydi. Qidiruv ikkala shaklni ham
qamraydi — eski doimiy `cutprint-{id}` / `rvprint-{id}` va yangi vaqt tamg'ali `cutprint-{id}-%` /
`rvprint-{id}-%`.

`bridge-agent/agent.py` — tsexdagi mustaqil servis (websockets + pywin32 + Pillow): outbound WS,
lokal JSONL navbat `QUEUE_FILE` (printer/internet uzilganda yo'qotmaydi), flusher **event-driven** —
`FLUSH_EVENT` bilan darhol uyg'onadi, 5 s faqat zaxira timeout. `send_to_printer(png_b64)` bitta
yo'l: `_print_png_gdi()` — jobdagi PNG Windows drayveri orqali, DEVMODE'da qog'oz 80×60 mm ga
majburlanadi. Xatoda `False` qaytadi va job lokal navbatda qoladi.

Printer **avto-topiladi**: `_detect_printer()` nomida tanish yorliq-printer rusumi bo'lgan lokal
Windows printerini qidiradi (`_PRINTER_KEYWORDS`: `godex`, `xprinter`, `gprinter`, `tsc`, `zebra`,
`argox`, `postek`) — GoDEX'dan boshqa rusum o'rnatilgan stansiyada ham `PRINTER_NAME` qo'yish shart
emas; u faqat qo'lda override uchun. Agent faqat printer ulangan kompyuterga o'rnatiladi —
menejer, texnolog va boshqa terminallarga hech narsa kerak emas.

O'rnatish qadamlari: [07-infra-devops.md](07-infra-devops.md) → "Chop etish infratuzilmasi".

## 6. API xaritasi (yangi routerlar)

| Router | Prefix | Kirish |
|---|---|---|
| `clients/employees/machines/posts` | CRUD + qidiruv; `employees` da qo'shimcha ikki amal: `/{id}/badge` POST (yo'qolgan beyjik — yangi `badge_id`, eskisi darhol bloklanadi, tarix o'sha hodimda qoladi) va `/{id}/print` POST (beyjik YORLIG'INI chop etish navbatiga — `print_badge`, printer `agent_id` bilan yoki yagona agent, §5) | rol-based (`api/deps.py: require_roles`); `employees` yozuv amallari `AdminUser` |
| `orders` | lifecycle (`/confirm`, `/start`, …) + `/status-counts` + `/upload` + `/matrix` + `/machines` + `/cutmap` + `/files/{id}` + `/files/scx.zip` (barcha SCX bitta arxivda, `StaffReadUser`) + `/scx/regenerate` (SCX qayta generatsiya, `TexnologUser`; `ingest.rebuild_order_scx` — `PATCH /matrix` bilan umumiy helper) + `/survey` + `/survey/photos[/{file_id}]` | o'qish: manager/texnolog/director (`StaffReadUser`); yozish: manager/texnolog (+admin/superuser); anketa yozuvi: `ManagerUser` |
| `scans` | POST scan, DELETE undo (`/recent` olib tashlangan) | terminal + 9 operator rol |
| `terminal` | `/context`, `/employees` ("Kim ishlayapti?" — shu postdagi faol hodimlar), `/session`, `/session/end`, `/orders` (loyiha kartalari: done/total post semantikasida — ARRA: NUSXA bo'yicha (done = chek∪skan, total = ARRA marshruti bor nusxalar soni; ikkalasi bir o'lchovda, chunki bir detalda ikkita ARRA qadami bo'lishi mumkin), KROMKA: detal bo'yicha, qolganlarida `PartRoute.total_done/total_required` qadam yig'indisi), `/orders/{id}/cutmap`, `/orders/{id}/kromka` (KROMKA/OVAL sahifasi), `/orders/{id}/prisadka` (detallar + SCX fayllar), `/orders/{id}/queue` (post navbati NUSXA darajasida — BOYOQ/STOLYARKA; postga bog'liq emas, kontekstdagi postni oladi), `/qr/{qr}/order` (QR→buyurtma), `/labels/{id}` POST (GoDEX navbat) / DELETE (chekni bekor qilish, manager/texnolog ham), `/waste/{id}/label` POST/DELETE (foydali atxot cheki — arrachi xaritadagi ATX katakdan, §5), `/labels/{id}.png`, `/files/{id}` | terminal + 9 operator rol; ish markazi/post konteksti (`_terminal_ctx` → `TerminalCtx`) har route'ga alohida qo'yiladi — yorliq/fayl route'lariga ataylab emas, ular ish markazisiz ham ishlaydi; javoblar typed (`app/schemas/terminal.py`: `TerminalOrderCard`, `QrOrderRef`, `Kromka*`/`Prisadka*` modellari — `list[dict]` yo'q) |
| `pachka` | `/orders/{id}` GET (qadoqlash holati) / POST (yangi qadoq — buyurtmada bitta ochiq qadoq), `/{id}/scan` (detalni qadoqqa — bu AYNI paytda marshrutning UPAKOVKA qadami), `/{id}/items/{instance_id}` DELETE (xato skanni qaytarish — skan ham bekor bo'ladi), `/{id}/reopen` (yopilganini qayta ochish), `/{id}/close` (yakunlash + chek) | terminal + operator rollar; faqat UPAKOVKA postida (`_pack_ctx`) |
| `tmo` | `/orders/{id}` GET, `/orders/{id}/accept` (QABUL — `PK-...` bo'lsa qadoq ichidagi HAMMA nusxa bitta skanda, aks holda bitta detal), **`/orders/{id}/ship` ham OLIB TASHLANDI** — TMO da qadoq ro'yxati yo'q. **Buyurtmani TOPSHIRISH endpointi ham TMO da YO'Q** — u managerda (`orders.deliver_order`, faqat TAYYOR holatdan); TMO faqat qabul qiladi va hamma detal o'tgach buyurtma o'zi TAYYOR bo'ladi | terminal + operator rollar; faqat TMO postida (`_wh_ctx`) |
| `tablo` | `/matrix`, `/orders/{id}` | istalgan auth |
| `reports` | `/productivity`, `/orders`, `/materials` (+`?format=xlsx`), `/dashboard` | manager/director/admin |
| `audit-logs` | filtrli ro'yxat (13 modul: scan, print, sessions, orders, pachka, tmo, bridge_agents, employees, users, clients, machines, posts, auth — backend `log_action(module=…)` qiymatlari va frontend `logs.tsx: CATEGORIES` bir xil; eski `ombor` nomi `e5b83c04d7a1` da `tmo` ga birlashtirilgan (o'sha migratsiya `materials` ni `stock` ga ham ko'chirgan — stock moduli olib tashlangach o'sha qatorlar bazada filtrsiz tarix bo'lib qoladi); rad etilgan skanlar ham — `module=scan, action=rejected`, §3) | faqat admin (`AdminUser`, TZ 10.11) — butun tizim audit izi; direktor ishlab chiqarish ko'rsatkichlarini `/reports` dan oladi |
| `bridge-agents` | ro'yxat/yaratish, `/{id}` PATCH (ish markazi bog'lash + `can_print`), `/{id}/code` (yangi ulanish kodi), `/{id}` DELETE, `/pair`, `/scan` (skan-forvard, §4), `/logs` POST + `/{id}/logs` GET (agent loglari Redisda — `mes:agent:log:{id}`, oxirgi 200 satr, TTL 7 kun; admin panelda ko'rinadi, tsexdagi kompyuterga masofadan kirish yo'q), `/latest` + `/download` (agent avto-yangilanishi: `agent-dist/version.json` — versiya + sha256 — va `mebelix-agent.exe`; 2026-08-27 dan CI har deploy'da exe quradi, ya'ni eskirishning iloji yo'q) | admin (`AdminUser`); `/pair`, `/latest`, `/download` ochiq (router global auth'siz — agentda sessiya yo'q, exe sir emas), `/scan` va `/logs` agent tokeni bilan (Bearer → sha256) |

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
bo'lib qolardi. Tanlangan ish markazi `PartRoute.machine_id` ga muhrlanadi
(`orders/_common.py: stamp_route_machines`) — terminal ro'yxati va skan tekshiruvi shu ustunga
qaraydi. Ish markazi PRODUCTION holatida `POST /{id}/machines` bilan qayta tanlansa muhr ham
o'sha yerda yangilanadi; aks holda buyurtma eski stanokda qolib, yangisida skan E001 berardi.
PRODUCTION buyurtmaga `.project` QAYTA yuklansa marshrut qatorlari yangidan yaraladi
(`machine_id=None`), shuning uchun `upload_order_project` ham shu muhrni qayta bosadi —
aks holda tanlov joyida tursa ham marshrut o'sha postdagi hamma stanokda ko'rinardi.
`GET /orders/status-counts` — registr tablari uchun har status bo'yicha son. Frontendda
qoldiq to'lov = `amount − advance_payment`, `advance ≤ amount` validatsiyasi bilan.

Texnolog ko'rinishi cheklangan (`orders/_common.py: _hidden_statuses`): DRAFT va CANCELLED buyurtmalar
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
| `SurveyRoom` | `id` (frontend beradigan barqaror kalit) + `name`; 2-bo'lim `furniture_types`/`furniture_other`; 3-bo'lim `shape`, `room_length/width/height`, `furniture_wall_length`; 4-bo'lim `corpus_materials`, `corpus_color`, `corpus_thickness`, `corpus_note`; 5-bo'lim `facade_materials`, `facade_color`, `countertop`, `facade_note`; 6-bo'lim `hardware_level`, `extra_services`; 7-bo'lim `note`; o'lchov varag'i `walls`, `modules`, `total_running_meters`, `total_height` |
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

Endpointlar (`app/api/routes/orders/survey.py`, hammasi `ManagerUser`):

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

- `app/services/metrics.py: part_volume()` — TT 9.3.1 HAJM matematikasi (ARRA va UPAKOVKA m²
  — ikkalasi ham `length × width / 1 000 000 × count`, KROMKA metr, qolganlari dona; OVAL
  birligi metr bo'lsa ham dona bilan approksimatsiya — egri qirraning uzunligi detal
  bo'yicha saqlanmaydi),
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
- Imzo komponent: `Common/StagePipeline` — post zanjiri (dinamik, faqat dashboard'ning "Aktiv buyurtmalar" qatorlarida — `routes/_layout/index.tsx:205`; buyurtmalar reyestrida bosqich ustuni yo'q).
- Routelar: `_layout/*` admin modullar (index — boshqaruv paneli, orders (`index` + `$orderId`),
  clients, employees, work-centers, reports, logs, printers, admin, settings,
  cutmap.$orderId, `anketa.$orderId`), `/terminal`, `/tablo`
  ("Jami" yig'indi qatori + rejimlar + drill-down; sarlavhada brend logo, ish markaziga bog'langan
  tablo akkauntida "JORIY NUQTA" chipi, onlayn indikatori va tablo bo'lmagan rollarga "Boshqaruv
  paneli" havolasi). "Jami" qatori hajmga bog'lanmagan — katakchalari tanlangan rejimga ergashadi:
  hajm — `X / Y` post birligida (m²/m/dona), soni — `done / total`, foiz — `%`. Tanlangan rejim
  `localStorage` da (`tablo-mode`) — TV qayta yoqilganda ham saqlanadi; yangi bundle uchun qayta
  yuklash soatiga bir marta va faqat drill-down yopiq bo'lganda. Katak qiymati OSHGANDA bir marta
  0.9 s yashil uriladi (`animate-cell-flash` / `@keyframes mx-cell-flash`, `src/index.css`) —
  devordagi ekranda o'zgargan raqamni ilib oladigan yagona signal; kamayishda (skan bekor
  qilinganda) urilmaydi. Yon menyu — `Sidebar/AppSidebar.tsx: NAV_ITEMS` (9 band); mobil
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
    kartochkadagi tugma). FOYDALI ATXOT katagi ham xuddi shu ekranda va shu oqimda:
    `POST /terminal/waste/{id}/label` chek chiqaradi, DELETE bekor qiladi, cheki chiqarilgani
    ham YASHIL bo'ladi. Katak↔`WasteItem` bog'lanishi `w.qr_text.endsWith("-{atx}")` +
    `sheet_no` orqali — ya'ni `ingest.py` cutmap katagiga yozgan `atx` raqami bilan.
  · **KROMKA** (`Terminal/KromkaView`) — ikki panel: chapda arradan chiqqan detallar
    (tugaganlari yashil, pastda), o'ngda "Jarayonda" (2+ tomonli, boshlangan, tugamagan).
    Har skan darhol yoziladi (tomon = skan, `per_instance`); bir QR uchun 5 s to'siq;
    picker'da skan qilinsa proyekt o'zi ochiladi (`/qr/{qr}/order`); begona detalga aniq xato.
    Kromka ustunida tomon NOMI emas, qirra simvollari — yorliq eskizi detal o'lchamiga
    qarab buriladi (`labels.py` `burilgan`), shuning uchun qat'iy Chap/Tepa nomi to'g'ri kelmaydi.
  · **OVAL** — o'sha KromkaView `oval` rejimda: bir panel, tomonlar ustuni yo'q va `done/sides` o'rniga faqat tugagan/tugamagan belgisi. Har detal BITTA skan (`per_instance = 1`), shuning uchun hisoblagichning ma'nosi ham yo'q.
  · **PRISADKA** (`Terminal/PrisadkaView`) — detallar + SCX fayllar; "Hammasini yuklab olish"
    File System Access API bilan BIR MARTA tanlangan papkaga (IndexedDB'da saqlanadi,
    `lib/scxDir.ts`) proyekt nomli subpapka ochib yozadi (har skandagi avto-SCX olib tashlangan — faqat shu tugma).
  · **ROVER** — o'sha PrisadkaView, lekin SCX butunlay yashirin (`showScx=false` — roverga SCX
    kerak emas): har jismoniy nusxa ALOHIDA qator, chap ustunda katta
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
    bloklamaydi. Bloklanadigan yagona narsa — marshrut tartibi. O'ng ustundagi
    "Yakunlangan" ro'yxatida har qadoqqa "Qayta ochish" tugmasi (ochiq qadoq turganda
    bloklangan — buyurtmada bir vaqtda bitta ochiq qadoq bo'ladi).
  · **TMO** (`Terminal/TmoView`) — ikki tab. **Qabul**: TMO ga yetib kelganlar (qadoq kodi
    bilan), qadoq QR'i bitta skanda ichidagi hammasini qabul qiladi; pastda "Tsexda" ro'yxati,
    har detalga ishi TUGAGAN post yozilgan (omborchi uni o'sha yerdan topadi). Sarlavhada
    ikki son: `TMO ga keldi: arrived/total` va `Qabul qilindi: accepted/total`.
    **Qabul qilingan**: serverdan kelgan ro'yxat (`done`) — sahifa yangilansa ham qoladi.
    Qadoq alohida tab EMAS, faqat yorliq — chek skanerlansa ichidagi hamma nusxa birdan
    "Qabul qilingan" ga o'tadi. Ekranda TOPSHIRISH rejimi YO'Q: har qanday skan — QABUL.
    Hamma detal qabul qilingach buyurtma o'zi COMPLETED bo'ladi, DELIVERED ni esa manager
    qo'yadi (`POST /orders/{id}/deliver`).
  Qadoqlash va TMO skani ekranning O'ZIDA yoziladi (`viewScanRef` — umumiy skan yo'li
  chetlab o'tiladi): detal qaysi qadoqqa tushishini yoki TMO ga qabul qilinishini faqat
  o'sha ekran biladi, qadoq QR'i esa umumiy yo'lda "QR noto'g'ri formatda" bo'lib rad etilardi.
  Buning EVAZIGA javob xabarini shu ikki ekran O'ZI beradi: skan mutatsiyasining
  `onSuccess` da `playSuccess()` + toast, `onError` da `playError()`, ochiq qadoq yo'q /
  takror qabul holatida `playWarning()` (TT 8.4.3 — tsex shovqinida ovoz majburiy).
  Umumiy: majburiy to'liq ekran overlay, lock overlay, operator logout, 2 s umumiy QR cooldown
  (TT 8.4.4), skan chizig'i 15 s da o'zi yo'qoladi, skan inputi fokussiz ham QR ni tutadi
  (birinchi tugmada fokus), yangi build uchun har 5 daqiqada `/` HEAD ETag tekshiruvi va xavfsiz
  paytda avto-reload.
- WS hook: `hooks/useMesWs.ts` (reconnect + heartbeat + online flag).
- Rol-marshrutlash: `_layout.tsx` beforeLoad (`lib/guards.ts: requireAuth`) — terminal va
  9 operator rol → `/terminal`, tablo → `/tablo` (qurilma/operator akkauntlar admin panelga
  kira olmaydi).

## 8. Sozlamalar (yangi env)

Backend: `UPLOAD_DIR`, `MAX_PROJECT_FILE_SIZE`, `STRICT_STAGE_ORDER`,
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
