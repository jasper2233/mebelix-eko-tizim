# 09 — MES domen qatlami (TT bo'yicha implementatsiya)

Holat: **2026-07-10**. TT manba: `Mebelix_MES_TZ_v2.2.docx`. Fazalar holati: repo ildizidagi `TODO.md`.

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
| `order` | B-YYYY-NNN, status DRAFT→…→DELIVERED/CANCELLED; `cutmap` JSONB (5.7.5 modeli), `machine_assignments`, `material_usage` | 6 |
| `product`/`part`/`part_instance` | Fayl tarkibi; instance QR = `productCode_partCode_n`, kesish xaritasi katakchasiga bog'langan (pattern_no, cell_index) | 5.8 |
| `part_route` | Detal × post: per_instance (KROMKA tomonlar), total_required/done — QOLDIQ shu yerda | 5.4 |
| `scan` | Muvaffaqiyatli ish birligi; `client_event_id` UNIQUE (idempotency), bekor qilish belgisi | 8.4 |
| `work_session` | Smena (beyjik → sessiya) | 8.2 |
| `order_file` | project / scx / hujjatlar (diskda `UPLOAD_DIR` ostida) | 2.4.3 |
| `audit_log` | Kim-qachon-nima (`crud/audit.py: log_action`, tranzaksiya ichida) | 10.11 |

`user` jadvaliga qo'shildi: `role` (admin/director/manager/texnolog/terminal/tablo) + `machine_id`
(terminal/TABLO qurilma akkauntlari stanokka biriktiriladi, TT 8.1 variant B).

## 2. GibLab parser (`app/services/giblab/`)

| Fayl | Vazifa |
|---|---|
| `parser.py` | .project XML (to'la parser, regex YO'Q; cp1251/UTF-8; PROCESSED/TEMPLATE avlodlar; kontekstli id qidiruv) |
| `xnc.py` | XNC program parse (atribut yoki bola element), xavfsiz ifoda hisoblash (`dz+3`), max 2 op merge |
| `csblob.py` | CS `data` blob dekoderi: big-endian, 15B yozuvlar, guillotine daraxt, dims+117 root-o'q sloti, 5.7.4 self-check |
| `cutmap.py` | Vizual model (5.7.5): sheets/parts/cuts + holes overlay, rot/eW/eH, atxot foydali o'lcham, instance↔katakcha binding |
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

## 4. Real-time (`app/core/ws.py`, `api/routes/ws.py`)

- `/ws/events` — brauzer klientlar: JWT (cookie yoki `?token=`); rol → scope (terminal/tablo/dashboard),
  post/stanok bo'yicha filtrlash; `ping`→`pong` heartbeat.
- Fan-out Redis pub/sub (`mes:events`) orqali — gunicorn workerlar orasida; Redis o'chiq bo'lsa lokal.
- `/ws/bridge` — sex bridge-agenti (`BRIDGE_TOKEN` bilan): Redis `mes:print:queue` dan chop etish
  joblarini oladi, ack qilinmagan job qayta navbatga qaytadi.

## 5. Chop etish (TT 12.3 / 13.2)

`app/services/labels.py` — EZPL 80×60 (QR + kod + material + o'lcham + kromka qatori + P/S/F
ikonkalar + sana/№). ARQ task `print_label` (`app/tasks/`): `PRINTER_IP` sozlangan bo'lsa to'g'ridan
TCP 9100; aks holda Redis navbatga (bridge-agent oladi). **Worker shart**: `make worker`.

`bridge-agent/agent.py` — sexdagi mustaqil servis (websockets + stdlib): outbound WS, lokal JSONL
navbat (printer/internet uzilganda yo'qotmaydi), 5s flusher. O'rnatish: `bridge-agent/README.md`.

## 6. API xaritasi (yangi routerlar)

| Router | Prefix | Kirish |
|---|---|---|
| `clients/employees/machines/posts/materials` | CRUD + qidiruv | rol-based (`api/deps.py: require_roles`) |
| `orders` | lifecycle + `/upload` + `/matrix` + `/machines` + `/start` + `/cutmap` + `/files/{id}` | manager/texnolog/admin |
| `scans` | POST scan, DELETE undo, `/recent` | terminal |
| `terminal` | `/context`, `/session`, `/tasks`, `/orders/{id}/cutmap`, `/labels/{id}`, `/files/{id}` | terminal |
| `tablo` | `/matrix`, `/orders/{id}` | istalgan auth |
| `reports` | `/productivity`, `/orders`, `/materials` (+`?format=xlsx`), `/dashboard` | manager/director/admin |
| `audit-logs` | filtrli ro'yxat | staff |

## 7. Frontend tuzilishi

- Dizayn tokenlar: `src/index.css` (post/status ranglari, `.num`, print CSS); domen konstantalar `src/lib/mes.ts`.
- Imzo komponent: `Common/StagePipeline` — 6 bosqich zanjiri (dashboard, buyurtma qatorlari).
- Routelar: `_layout/*` admin modullar (orders, clients, employees, machines, materials, reports,
  transactions, logs, cutmap.$orderId), `/terminal` (ARRA SVG xarita `Terminal/CutmapView`),
  `/tablo` (JAMI HAJM + rejimlar + drill-down).
- WS hook: `hooks/useMesWs.ts` (reconnect + heartbeat + online flag).
- Rol-marshrutlash: `_layout.tsx` beforeLoad — terminal/tablo o'z ekraniga.

## 8. Sozlamalar (yangi env)

`UPLOAD_DIR`, `MAX_PROJECT_FILE_SIZE`, `STRICT_STAGE_ORDER`, `SESSION_MAX_HOURS`,
`SCAN_UNDO_SECONDS`, `PRINTER_IP`/`PRINTER_PORT` (faqat lokal rejim), `BRIDGE_TOKEN`.
