# 09 — MES domen qatlami (TT bo'yicha implementatsiya)

Holat: **2026-07-27**. TT manba: `Mebelix_MES_TZ_v2.2.docx`. Fazalar holati: repo ildizidagi `TODO.md`.

## 1. Data model (`app/models/`)

17 jadval, hammasi `BaseModel` (ID + timestamps + soft-delete):

| Jadval | Mazmun | TT |
|---|---|---|
| `organization` | Tenant (bitta: Mebelix), sxema multi-tenant tayyor | 4.1 |
| `post` | 6 bosqich: ARRA→STOLYARKA (unit, order_index, flaglar), seed `app/commands/seed_defaults.py` | 4.4 |
| `machine` | Stanok (post FK, IP, capacity, holat) | 4.3 |
| `employee` | Beyjik egasi (badge_id UUID partial-unique, assigned_post_ids JSONB) | 4.2 |
| `client` | Mijoz (jismoniy/yuridik, INN) | 4.6 |
| `material` | Katalog — .project fayldan avtomatik to'ladi | 4.5 |
| `order` | B-YYYY-NNN, status DRAFT→…→DELIVERED/CANCELLED; `amount` + `advance_payment` Numeric(14,2) (boshlang'ich to'lov, migratsiya `7d2c9f5e1b3a`); `cutmap` JSONB (5.7.5 modeli), `machine_assignments`, `material_usage`; `survey` JSONB — mijoz anketasi + o'lchov varag'i (migratsiya `a91c7d34f6e2`, §6.2) | 6 |
| `product`/`part`/`part_instance` | Fayl tarkibi; instance QR = `productCode_partCode_n`, kesish xaritasi katakchasiga bog'langan (pattern_no, cell_index) | 5.8 |
| `part_route` | Detal × post: per_instance (KROMKA tomonlar), total_required/done — QOLDIQ shu yerda | 5.4 |
| `scan` | Muvaffaqiyatli ish birligi; `client_event_id` UNIQUE (idempotency), bekor qilish belgisi | 8.4 |
| `work_session` | Smena (beyjik → sessiya) | 8.2 |
| `order_file` | project / scx / hujjatlar (diskda `UPLOAD_DIR` ostida); `meta` JSONB — anketa xona rasmlari uchun `{"room_id", "content_type"}` | 2.4.3 |
| `audit_log` | Kim-qachon-nima (`crud/audit.py: log_action`, tranzaksiya ichida) | 10.11 |
| `bridge_agent` | Printerli kompyuterdagi chop etish agenti: `name`, `token_hash` (sha256, unique), bir martalik `pair_code` + `pair_expires_at` (15 daqiqa), `last_seen_at` (panelda Onlayn/Oflayn); migratsiya `d5e81a24c3b7` | 2.2.2 |

`user` jadvaliga qo'shildi: `role` (`UserRole`, 12 a'zo) + `machine_id`. Rollar ikki guruh
(`app/models/enums.py`):

- staff/qurilma: admin, director, manager, texnolog, terminal, tablo — terminal/TABLO qurilma
  akkauntlari stanokka biriktiriladi (TT 8.1 variant B);
- post-operator: arrachi, kromkachi, prisadkachi, pazchi, roverchi, stolyar — `POST_ROLES`
  mapping orqali postga bog'lanadi (ARRACHI→ARRA … STOLYAR→STOLYARKA); o'z akkaunti bilan kiradi,
  **stanok biriktirish ham, beyjik ham shart emas** (login = smena, §3 ga qarang).

## 2. GibLab parser (`app/services/giblab/`)

| Fayl | Vazifa |
|---|---|
| `models.py` | Parse natijasi dataclasslari (ORM emas): `ParsedProject/Product/Part`, `XncOp`, `ParsedMaterial`, `CutOperation` + `ParseError` (matni to'g'ridan texnologga ko'rsatiladi) |
| `parser.py` | .project XML (to'la parser, regex YO'Q; cp1251/UTF-8; PROCESSED/TEMPLATE avlodlar; kontekstli id qidiruv); takror detal kodlari deterministik rename (`code`, `code-2`, …) + o'zbekcha warning — QR/SCX kaliti unikal qoladi |
| `xnc.py` | XNC program parse (atribut yoki bola element), xavfsiz ifoda hisoblash (`dz+3`), max 2 op merge |
| `csblob.py` | CS `data` blob dekoderi: big-endian, 15B yozuvlar, guillotine daraxt, dims+117 root-o'q sloti, 5.7.4 self-check |
| `cutmap.py` | Vizual model (5.7.5): sheets/parts/cuts + holes overlay, rot/eW/eH, atxot foydali o'lcham, instance↔katakcha binding; har list uchun root-strip o'lcham zanjiri `dims` (ax/a/b/v, ≥10mm poloslar, GibSaw uslubi) — cutmap JSONida saqlanadi, terminal SVG chizadi |
| `scx.py` | SCX generatsiya: **Y_scx = Width − y_program**; `_2` ikkinchi tomon; Face kodlari qisman kalibr talab (`ponytail:`) |
| `ingest.py` | DBga yozish: products/parts/instances/routes/materials/fayllar/cutmap/material_usage; qayta yuklash to'liq almashtiradi |

Marshrut qoidalari (5.4): ARRA har doim (per_instance=1); KROMKA = ell/elr/elt/elb soni;
PRISADKA = bf/bt/bb/bl/br; PAZ = gr; ROVER = ms/ml/mac — XNC bosqichlarda per_instance = shu
element bor op soni (`_2` → 2). STOLYARKA — texnolog qo'lda (matrix PATCH).

Test: `uv run python -m tests.test_giblab` — sintetik blob enkoderi bilan assert-based.

## 3. Scan engine (`app/services/scanning.py`)

Instance-level nazorat: QR → aktiv PRODUCTION buyurtma → route (post+stanok mosligi) →
per-instance limit → yozish + `total_done++`. Xatolar TT 8.5 kodlari bilan (`{"code": "E00x",
"message": ...}` 422 detail). Idempotency: `client_event_id` UNIQUE — takror so'rov `duplicate:true`
bilan muvaffaqiyat. `STRICT_STAGE_ORDER=true` bo'lsa E004 (oldingi bosqich shu nusxada tugamagan).
60s ichida bekor qilish; COMPLETED regress. Bosqich tugashi → `order.stage_completed`, hammasi →
`COMPLETED` + `order.completed`.

Operator-rol oqimi (`resolve_terminal` / `operator_employee` / `active_session`): arrachi…stolyar
uchun post roldan aniqlanadi (`POST_ROLES`); stanok — `user.machine_id`, bo'lmasa postning birinchi
o'chirilmagan stanogi (faqat soft-delete tekshiriladi, holat emas — NOAKTIV/TA'MIRDA stanok ham
tushishi mumkin). Employee mirror avto-yaratiladi (`badge_id = "user-<id>"`) — scan/mahsuldorlik
attributsiyasi beyjiksiz saqlanadi. **Login = smena**: sessiya avtomatik ochiladi/qayta ochiladi
(beyjik scan talab qilinmaydi); TERMINAL qurilma akkauntida esa avvalgidek beyjik shart (E005/E006).

## 4. Real-time (`app/core/ws.py`, `api/routes/ws.py`)

- `/ws/events` — brauzer klientlar: JWT (cookie yoki `?token=`); rol → scope (terminal/tablo/dashboard),
  post/stanok bo'yicha filtrlash; `ping`→`pong` heartbeat.
- Fan-out Redis pub/sub (`mes:events`) orqali — gunicorn workerlar orasida; pool lifespan'da doim
  ochiladi (flag yo'q), publish xato bersa lokal yetkazishga tushadi.
- `/ws/bridge` — sex bridge-agenti (per-agent pairing tokeni: `Authorization: Bearer` header, sha256
  → `bridge_agent.token_hash`; umumiy `BRIDGE_TOKEN` faqat legacy moslik): Redis `mes:print:queue`
  dan chop etish joblarini oladi, ack qilinmagan job qayta navbatga qaytadi. `touch_agent()` har
  5 daqiqada `last_seen_at` ni yangilaydi — token bekor qilingan bo'lsa jonli ulanish 4401 bilan
  uziladi, qo'ldagi job navbatga qaytadi.

## 5. Yorliq chop etish (TT 12.3 / 13.2)

`app/services/labels.py` API: `LabelData`, `load_label_data(db, instance_id)`, `_n`,
`render_label_png`. Yagona chiqish — PNG rasm; `LabelData` maydonlari: qr_text, part_code,
part_name, project_name, material, l/w/t, count, instance_no, edges, xnc_summary, label_num,
**holes**, **texture**. `holes` — `order.cutmap` dan shu detal katakchasi bo'yicha
(`part.label_num` → cutmap `parts[].num` → `cutmap.holes[cell.id]`).

**`render_label_png(d, scale=1)` — asosiy maket** (GibSaw `mebelix.lbl` uslubi). 80×60 mm,
203 dpi (8 dot/mm → 640×480 px), oxirida `point(... , "1")` bilan sof 1-bit; `draw.fontmode = "1"`
— antialiasing yo'q, aks holda termodrayver dither qiladi. Koordinatalar mm da. Tarkibi:

- chap ustun: `assets/label-logo.png` (threshold 160), `Formatka` + product kodi, detal kaliti,
  loyiha nomi, kromka materiallari 2×2 (t/l/b/r, tagchiziq bilan), markazda katta `L x W = soni`,
  `N_detal nomi`, П/Ф belgilari (paz/freza), teshik bo'lsa `assets/label-icon-drill.png` ikonkasi,
  pastda material + sana + `N{label_num} {instance_no}/{count}`;
- o'ng ustun: QR (`qrcode`, `d.qr_text`) tepada, ostida **vertikal detal eskizi** — ingichka kontur,
  kromka konturdan 1 mm tashqarida qalin chiziq, `texture` bo'lsa uzunlik bo'ylab 3 chiziq,
  cutmap'dagi **haqiqiy teshiklar** (`bores` aylana, `edge` qirra shtrixi), o'lchamlar en pastda va
  uzunlik o'ngda 90° aylantirilgan, har biri yoniga o'sha tomonlar kromka simvoli.

Chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qoladi.

Zanjir (terminal → printer) — GoDEX G500-U faqat USB, tarmoq porti yo'q, shuning uchun bitta yo'l:

```
terminal (POST /terminal/labels/{instance_id})   → label_printed_at + ws "label.printed"
  → arq task print_label (app/tasks/__init__.py)
     · render_label_png → LPUSH mes:print:queue = {type, instance_id, png(base64)}
  → /ws/bridge (per-agent token auth: Bearer → sha256 bridge_agent.token_hash; Redis brpop + ack;
     ack kelmasa rpush bilan navbatga qaytadi)
  → bridge-agent/agent.py → print-queue.jsonl → Windows GDI → USB GoDEX
```

`GET /terminal/labels/{instance_id}.png` — o'sha `render_label_png()` chiqishi to'g'ridan brauzerga;
worker ham, GoDEX ham, bridge-agent ham shart emas.

`bridge-agent/agent.py` — sexdagi mustaqil servis (websockets + pywin32 + Pillow): outbound WS,
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
| `orders` | lifecycle (`/confirm`, `/start`, …) + `/status-counts` + `/upload` + `/matrix` + `/machines` + `/cutmap` + `/files/{id}` + `/survey` + `/survey/photos[/{file_id}]` | o'qish: manager/texnolog/director (`StaffReadUser`); yozish: manager/texnolog (+admin/superuser); anketa yozuvi: `ManagerUser` |
| `scans` | POST scan, DELETE undo, `/recent` | terminal + 6 operator rol |
| `terminal` | `/context`, `/session`, `/session/end`, `/tasks`, `/orders` (loyiha kartalari: done/total agregat), `/orders/{id}/cutmap`, `/labels/{id}` (GoDEX navbat), `/labels/{id}.png`, `/files/{id}` | terminal + 6 operator rol; stanok/post konteksti (`_terminal_ctx` → `TerminalCtx`) har route'ga alohida qo'yiladi — yorliq/fayl route'lariga ataylab emas, ular stanoksiz ham ishlaydi |
| `tablo` | `/matrix`, `/orders/{id}` | istalgan auth |
| `reports` | `/productivity`, `/orders`, `/materials` (+`?format=xlsx`), `/dashboard` | manager/director/admin |
| `audit-logs` | filtrli ro'yxat | staff |
| `bridge-agents` | ro'yxat/yaratish, `/{id}/code` (yangi ulanish kodi), `/{id}` DELETE, `/pair`, `/download` | admin (`AdminUser`); `/pair` va `/download` ochiq — router global auth'siz ulanadi |

### Buyurtma lifecycle va to'lovlar

Manager buyurtmani narx (`amount`, ixtiyoriy `advance_payment`) kiritib yaratadi, so'ng
`POST /orders/{id}/confirm` — DRAFT → TECHNICAL_REVIEW (`amount` bo'lmasa rad etiladi). Texnolog
`.project` faylni **faqat tasdiqdan keyin** (TECHNICAL_REVIEW holatida) yuklay oladi;
`POST /{id}/start` (TECHNICAL_REVIEW → PRODUCTION) `.project` biriktirilgan bo'lishini va
`requires_assignment_choice` postlar uchun `machine_assignments` ni talab qiladi.
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
| `OrderSurvey` | `version`, `measured_at` (o'lchov sanasi), `measured_by` (o'lchagan usta), `rooms` (max 10) |
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
`order` da — anketada takrorlanmaydi.

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
  qolganlari dona; PAZ metrlari hozircha dona bilan approksimatsiya — paz uzunligi saqlanmaydi),
  reports va tablo uchun umumiy.
- `app/services/excel.py: xlsx_response()` — openpyxl bilan bitta varaqli .xlsx stream
  (reports `?format=xlsx` orqasida).

## 7. Frontend tuzilishi

- Dizayn tokenlar: `src/index.css` (post/status ranglari, `.num`, print CSS); domen konstantalar `src/lib/mes.ts`.
- Imzo komponent: `Common/StagePipeline` — 6 bosqich zanjiri (dashboard, buyurtma qatorlari).
- Routelar: `_layout/*` admin modullar (orders, clients, employees, machines, materials, reports,
  transactions, printers, admin, settings, cutmap.$orderId, `anketa.$orderId`), `/terminal`, `/tablo`
  (JAMI HAJM + rejimlar + drill-down). Yon menyu sarlavhalari (`_layout.tsx: sectionTitles`) — 10 ta.
- Anketa UI: `_layout/anketa.$orderId.tsx` — xonalar tab bilan almashadi, 7 ta bo'lim + yopiladigan
  "O'lchov varag'i". Yozish huquqi `is_superuser || admin || manager`; boshqa rollarga forma emas,
  `RoomSummary` — o'qish uchun jamlanma (matn nusxa olinadi). Avtosaqlash: har tahrirdan 1.5 s
  keyin `PUT /survey` (alohida "saqlash" bosqichi yo'q), `beforeunload` ogohlantirish +
  unmount'da fire-and-forget saqlash. Server javobi formaga **bir marta** yuklanadi
  (`loaded` ref) — aks holda refetch menejer yozayotgan matn ustiga tushadi.
- Buyurtma kartasi (`orders/$orderId.tsx`): `.project` uchun drag&drop zona (kengaytma tekshiriladi,
  boshqasiga xato toast) va anketaga o'tish tugmasi.
- `/terminal` (17" touch UX) drill-down: loyiha kartalari (`GET /terminal/orders` — priority badge,
  ARRA progress, deadline) → materiallar ro'yxati (har material bo'yicha bajarilgan list soni) →
  listlar → to'liq ekran xarita. Chizish `Terminal/CutmapView` + `Terminal/SheetSvg` (detallar,
  teshiklar, o'lcham zanjirlari, zoom/swipe); `printAllMaps` — har list A4 landscape. Qo'shimcha:
  majburiy to'liq ekran overlay, lock overlay (tasodifiy touch himoyasi, scan to'xtaydi), operator
  logout, jonli soat.
- WS hook: `hooks/useMesWs.ts` (reconnect + heartbeat + online flag).
- Rol-marshrutlash: `_layout.tsx` beforeLoad — terminal va 6 operator rol → `/terminal`,
  tablo → `/tablo` (qurilma/operator akkauntlar admin panelga kira olmaydi).

## 8. Sozlamalar (yangi env)

Backend: `UPLOAD_DIR`, `MAX_PROJECT_FILE_SIZE`, `STRICT_STAGE_ORDER`, `SESSION_MAX_HOURS`,
`SCAN_UNDO_SECONDS`, `BRIDGE_TOKEN` — ixtiyoriy **legacy** moslik: bo'sh bo'lsa ham `/ws/bridge`
ishlaydi (agentlar admin paneldagi pairing tokeni bilan ulanadi), faqat eski umumiy tokenli
agentlar uchun to'ldiriladi.

Bridge-agent (`bridge-agent/agent.py`, backend settings'ida emas — o'z env'i): `MES_URL`
(default `ws://localhost:8000`), `BRIDGE_TOKEN` (pairing bergan per-agent token — birinchi ishga
tushishda `%APPDATA%\MebelixAgent\.env` ga o'zi yoziladi; qo'lda berish faqat legacy holat), `PRINTER_NAME`
(ixtiyoriy — avto-topish o'rniga qo'lda), `QUEUE_FILE` (default `print-queue.jsonl`).
