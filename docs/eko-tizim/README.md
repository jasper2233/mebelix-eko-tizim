# MebeliX EKO — MES nusxasi ustidagi ish

Mahsulot nomi — **MebeliX EKO** (ichki/papka nomi `eko-tizim`).

Bu repo — MebeliX MES (`94a2f9e`) ning **nusxasi**. Asl MES ga tegilmaydi:

- remote `mes-asl` — faqat o'qish uchun, push manzili ataylab buzilgan;
- ish `eko-tizim` branchida; `main` ga push = prodga deploy, shuning uchun bu nusxadan hech qachon push qilinmaydi.

Texnik topshiriq (birlamchi manba): https://claude.ai/artifact/UENWqnKyfxz1E6jdoL422u

Qisqacha: Ombor, Kassa, Moliya, Soliq — MES ichida modulli monolit (`app/modules/*`,
alohida Postgres sxemalari, `api-sex` / `api-ofis` jarayonlari); MX Kroy — alohida servis,
ikki rejimda (mustaqil / ekotizim), API va webhook orqali ulanadi. Tizim tijorat mahsuloti:
obuna (ko'p ijarachi, har obunachi alohida baza) va mijoz serverida o'rnatish.

## Bosqichlar holati

| Bosqich | Holat | Nima qilindi |
| --- | --- | --- |
| 0. Nusxa | tayyor | `9a9264c` |
| 1a. Poydevor | tayyor, lokal Postgres/Redis/Caddy bilan sinalgan | pastda |
| 1b. Ko'p ijarachi | tayyor, lokal sinalgan | pastda |
| 2.1 Ombor moduli | tayyor (kod ko'chirildi, xulq o'zgarmadi) | pastda |
| 2.2 Rezerv (backend) | tayyor, lokal sinalgan | pastda |
| 2.2b Rezerv (interfeys) | tayyor, brauzerda sinalgan | pastda |
| 2.3a Barkodlar, sexga berish, sexdagi rulonlar | tayyor, brauzerda sinalgan | pastda |
| 2.3b Sexdan so'rov, rulon tugadi (terminal), qoldiq bo'laklari | tayyor, lokal sinalgan | pastda |
| 3a MX Kroy: qoldiq ombori API (K3), webhook inbox (K4) | tayyor, HTTP bilan sinalgan | pastda |
| 3b MX Kroy: buyurtma → loyiha, «Kroy» tugmasi, SSO (K1, K6) | tayyor, MX klon bilan sinalgan | pastda |
| 3c MX Kroy: kroy paketi qabul (K2) | tayyor, MX klon bilan sinalgan | pastda |
| 3d MX Kroy: arra «list chiqdi» → MX va qoldiq bo'laklari, outbox | tayyor, MX klon bilan sinalgan | pastda |
| 3e MX Kroy: katalog sinxroni (K5), MX bo'lagi ↔ ATX yorlig'i | tayyor, MX klon bilan sinalgan | pastda |
| 3f Ortiqcha berilgan materialni sexdan qaytarish | tayyor, brauzerda sinalgan | pastda |
| 4a Kassa (backend): smena, PKO/RKO, aralash to'lov, qarz, qaytarish, o'tkazma, storno, rezerv | tayyor, lokal sinalgan | pastda |
| 4b Kassa (kassir ekrani) | tayyor, Chrome'da ko'rsatilgan | pastda |
| 5a Moliya (backend): P&L, pul oqimi, debitor/kreditor, kalendar, byudjet, balans, akt sverki, davr yopish | tayyor, lokal sinalgan | pastda |
| 5b Moliya (ekran) | tayyor, Chrome'da ko'rsatilgan | pastda |
| 6.0 Tarif darvozasi (obuna): ombor/kassa/moliya/kroy/soliq yo'llari `require_module`, menyu tarifdan | tayyor | pastda |
| 6a Soliq (backend): rejim tarixi (QQS / aylanma), rekvizitlar, MXIK, ESF + navbat + sinov operatori, QQS kitobi, P&L | tayyor, lokal sinalgan | pastda |
| 6b Soliq (ekran) | tayyor, Chrome'da ko'rsatilgan | pastda |
| 7a Buxgalteriya (backend): schyotlar rejasi, avtomatik provodkalar, aylanma-saldo, nazorat | tayyor, lokal sinalgan | pastda |
| 7b Buxgalteriya (ekran) | tayyor, Chrome'da ko'rsatilgan | pastda |
| 8a Ishga tushirish (backend): ochilish qoldiqlari, qo'lda avans qulfi, tayyorlik tekshiruvi | tayyor, lokal sinalgan | pastda |
| 8b Ishga tushirish (ekran) | tayyor, Chrome'da ko'rsatilgan | pastda |
| 9 Yo'riqnomalar: kassir, omborchi, moliyachi, direktor (dasturda `/yoriqnoma`) | tayyor | pastda |
| 2.4 Mustahkamlik (prototip darajasi: baza cheklovlari, o'zgarmas jurnal, solishtirish, storno, ikki kalit, qulf chegarasi) | tayyor, lokal sinalgan | pastda |

### 1a — nima qo'shildi

- `core/config.py`: `ProcessRole` (`all`/`sex`/`ofis`/`worker`), `API_ROLE`, rol bo'yicha `STATEMENT_TIMEOUT_MS`
  (3 s / 30 s / 300 s; `all` = cheklovsiz), `DB_STATEMENT_TIMEOUT_MS` bilan qo'lda berish.
- `core/db.py`: timeout asyncpg `server_settings` bilan ulanishga qo'yiladi.
- `core/utils/queue.py` + `core/worker.py`: `QUEUE_TEZ` / `QUEUE_SEKIN`, `WorkerSekinSettings`.
- `docker-compose.prod.yml`: `api` = ofis, yangi `api-sex`, `worker-sekin`; `caddy/Caddyfile` — sex yo'llari `api-sex` ga.
- `models/enums.py`: `UserLevel` (1 jarayon, 2 o'rta, 3 ofis), `ROLE_LEVEL`; `api/deps.py`: `require_level`;
  frontend `lib/mes.ts`: `LEVEL`, `ROLE_LEVEL`, `hasLevel` (qo'lda oyna).
- `app/modules/{ombor,kassa,moliya,soliq,integratsiya,platforma}` skeleti va
  `scripts/check_module_boundaries.py` (`make lint` va CI da).

Tekshirildi (lokal PostgreSQL 17, Redis, Caddy 2.10 — Docker'siz):
- Caddy orqali 9 ta yo'l: 6 ta sex yo'li `api-sex` ga, qolgani `api` ga tushdi; `caddy adapt` tartibi ham shunday.
- `statement_timeout`: sex jarayonida `pg_sleep(5)` 3,0 s da uzildi; ofis va `all` da oxirigacha bajarildi.
- Ikkala arq ishchisi `--check` dan o'tdi (alohida health kalitlari). Topilgan xato: `WorkerSekinSettings`
  meros olganda arq maydonlarni ko'rmasdi — tuzatildi (`5fc5950`).
- ruff, mypy, biome, frontend build, modul chegarasi skripti.
- **Sinalmagan:** `docker compose` ning o'zi (bu kompyuterda Docker/WSL yo'q). Compose YAML o'qildi va
  servislar/rollar/bog'liqliklar tekshirildi.

### 1b — obuna (ko'p ijarachi)

Qaror: **har obunachi — alohida baza** (`t_<kod>`), platforma bazasida faqat ro'yxat va tarif. Mavjud MES
kodiga `company_id` filtri qo'shilmaydi; izolyatsiya bazaning o'zida. `TENANCY_MODE=single` (sukut) da
xulq avvalgidek — hozirgi MES va mijoz serveridagi o'rnatma ko'chirishsiz ishlaydi.

| Qism | Fayl | Nima |
| --- | --- | --- |
| Kontekst | `core/tenancy.py` | `current_tenant` ContextVar, `use_tenant`, `tkey` (Redis prefiksi `t:<kod>:`), host → kod |
| Aniqlash | `core/tenancy_middleware.py` | `Host: <kod>.BASE_DOMAIN` → obunachi; yo'q 404, to'xtatilgan 403; health ochiq |
| Baza | `core/db.py` | `local_session()` joriy obunachi bazasiga; engine'lar keshlanadi, kichik pul |
| Platforma | `modules/platforma/` | `tenant` jadvali (alohida metadata va migratsiyalar), `resolve` (kesh), `module_enabled` |
| Buyruq | `commands/platforma.py` | `init`, `create`, `migrate-all`, `list`, `status` |
| Token | `core/security.py` | `tid` claim; boshqa subdomenda 401. `tid` siz eski token faqat `single` da o'tadi |
| Redis | tasks, activity, andon, bridge | kalitlar `tkey(...)` bilan |
| WS | `core/ws.py` | hodisada `tenant`, mijoz faqat o'z obunachisinikini oladi |
| arq | `core/utils/queue.py`, `tasks` | `queue.enqueue(...)` obunachini uzatadi; cron'lar har faol obunachi uchun |
| Fayllar | `config.upload_root` | `uploads/t/<kod>/` |
| Tarif | `api/deps.py: require_module` | o'chiq modul — 403 |
| Prestart | `scripts/prestart.sh` | `multi`: `platforma init` + `migrate-all` |

Tekshirildi (bir martalik skriptlar va curl, ikki obunachi `alfa`, `beta`):
- Har obunachi o'z admini bilan kiradi. Alfa tokeni beta subdomenida 401 qaytaradi, alfa paroli betada o'tmaydi.
  Noma'lum obunachi va asosiy domen 404, to'xtatilgan obuna 403 qaytaradi; qayta yoqilgach yana 200.
- Noto'g'ri kod rad etiladi. Yarim yo'lda yiqilgan `create` o'z bazasini o'chiradi.
- arq: alfa vazifasi `t_alfa` da ishladi va chekni `t:alfa:...` navbatiga qo'ydi. Beta vazifasi `t_beta` da ishladi.
  Cron ikkala obunachini aylanib chiqdi.
- WS hodisasi boshqa obunachi mijoziga o'tmaydi. Yuklangan fayllar `uploads/t/alfa`; `tkey` prefiksi to'g'ri.
- `single` regressiyasi: login va `/users/me` 200; eski (`tid` siz) token o'tadi.
- `alembic check`: platforma, obunachi va single bazalarida farq yo'q.

**Prodga chiqishdan oldin (multi):** wildcard DNS (`*.BASE_DOMAIN`) va wildcard TLS — Caddy'da DNS-provayder
moduli yoki on-demand TLS kerak; PgBouncer; obunachilar soni oshganda engine keshiga chegara.
`core/perf.py` metrikalari va valyuta kursi keshi ataylab umumiy (platforma darajasi).

> **2026-10-28 qarori (TZ Q21):** obuna hozir qurilmaydi. 1b kodi «fortochka» bo'lib `single` rejimda uxlaydi.
> Yangi kod faqat: baza — `local_session`, Redis kaliti — `tkey`, fon vazifasi — `queue.enqueue`.

### 2.1 — ombor moduli

`catalog`/`stock` modellari, servislari, sxemalari va yo'llari `app/modules/ombor/` ga ko'chdi (`git mv`, jadval va
endpointlar o'zgarmagan, `from app.models import CatalogItem` ishlayveradi). Router ro'yxati
`app/api/router.py` ga ko'chdi: `app.api.deps` ni import qilgan modul butun router daraxtini tortib aylana importga
tushmasin. Beshala ombor orakli toza bazada o'tadi (36, 37, 21, 16, 22). `ombor_hujjat_oracle` dagi qattiq
sana (2026-10-16) bugungi kunga almashtirildi — sana o'tgach FIFO tekshiruvi soxta yiqilardi (asl MES da ham 19/21 edi).

### 2.2 — rezerv va to'lov muddati (backend)

| Qism | Joy |
| --- | --- |
| Jadvallar | `material_map` (fayl materiali → katalog, `koef`), `rezerv` (buyurtma sarlavhasi: holat, muddat, direktor ruxsati), `rezerv_line`; `client.doimiy`, `client.kredit_limit` — migratsiya `d5b092eb17e0` |
| Qoidalar | `modules/ombor/services/rezerv.py` |
| Ochiq interfeys | `modules/ombor/service.py`: `on_project_loaded`, `on_payment_changed`, `production_block_reason`, `on_order_cancelled`, `expire_reservations` |
| Ishlab chiqarishdagi ulanishlar | `orders/files.py` (yuklash → rezerv), `orders/lifecycle.py` (summa/avans → yechish; `/start` darvozasi; bekor) |
| Ombor hujjatlari | sotuv va sexga berish faqat **bo'sh** qoldiqdan; kirim yetmagan rezervlarni qoplaydi (avval yechilganlar) |
| Cron | har 5 daqiqada muddati o'tganlar bo'shatiladi |
| API | `GET /ombor/rezerv/{id}`, `POST .../qayta`, `POST .../tasdiq` (direktor), `GET /ombor/taminot`, `POST /ombor/moslash` |
| Sozlamalar | `rezerv_muddat_kun`=3, `eng_kam_avans_foiz`=50, `rezerv_darvoza`=1 |

Kroy tayyor = texnolog `.project` yuklagan payt (MX Kroy ulanguncha). To'langan summa — `order.advance_payment`,
buyurtma summasi — `order.amount` (kassagacha, Q24; faqat `paid_and_required` o'qiydi).

Tekshirildi: `rezerv_oracle.py` 23/23 (qoplash, band qoldiq sotilmasligi, moslash, kirim qoplashi, 50 % chegara,
muddat o'tishi, kredit limiti, direktor ruxsati, bekor, ta'minot ro'yxati); HTTP: rezerv yo'llari, avans
999 999 → `faol`, 1 000 000 → `yechildi`, bekor → `bekor`; migratsiya upgrade/downgrade/upgrade, `alembic check` toza.

### 2.2b — interfeys va o'tish

| Qism | Joy | Kim |
| --- | --- | --- |
| Buyurtma kartasida «Material rezervi» | `components/Orders/RezervPanel.tsx` | ofis va skladchi ko'radi; «Qayta hisoblash» — menejer/texnolog; «To'lovsiz ruxsat berish» — direktor |
| «Ta'minot ehtiyoji» sahifasi + moslash oynasi | `routes/_layout/warehouse/taminot.tsx` (skladchi menyusida) | ko'rish — ombor xodimlari; moslash — skladchi, menejer |
| Mijoz kartasida doimiy/kredit | `components/Clients/ClientCredit.tsx`, `PATCH /clients/{id}/kredit` | hamma ko'radi, faqat direktor o'zgartiradi |
| O'tish kuni | `python -m app.commands.rezerv_otish [--apply]` | texnologdagi buyurtmalarga rezerv + tizim ruxsati; PRODUCTION ga tegilmaydi |

Kromka katalogda **metr**da (moslashda koef 1). Rulon butunligicha, ortig'i bilan beriladi — rulon hisobi 2.3 da (sexga berish).

Brauzerda tekshirildi (lokal backend + vite): panel to'langan va to'lanmagan buyurtmada, to'siq matni, direktor tugmasi,
ta'minot ro'yxati, moslash oynasi (qidiruv → tanlash → saqlash → ro'yxat yangilandi); konsolda xato yo'q.

### 2.3a — barkodli birliklar va materialni sexga berish

Foydalanuvchi qarorlari (2026-10-29): rulon qoldig'i **sexda qoladi** va tizim uni eslaydi — keyingi
buyurtma avval o'shandan oladi; har tovar zavod kodi + tizimning **o'z barkodi** bilan; arrachi/kromkachi
tablodan so'raydi **yoki** omborchi oldindan yetkazadi (ikkalasi ham).

- `material_birlik` (`modules/ombor/models/birlik.py`): har list (1 dona) va har rulon (metri bilan) —
  `EK0000123` barkod, zavod kodi, joy `ombor` | `sex` | `tugadi`. Furnitura birliksiz: katalog kodi
  yoki zavod shtrix-kodi (`catalog_item.ishlab_barkod`) + son.
- Kirim: list soni butun bo'lishi shart; metrdagi pozitsiyada rulon uzunligi (`stock_doc_line.hajm`
  yoki katalogdagi `birlik_hajm`) — miqdor rulonlarga bo'linadi. Eski qoldiq kartochkada bir marta
  yorliqlanadi (`POST /ombor/birlik/yorliq`). Yorliqlar: `/warehouse/yorliq?doc=` yoki `?item=` (QR, 58×40 mm).
- `catalog_item.quantity` — korxonaning JAMI miqdori, sexdagi rulon qoldiqlari ham kiradi. Rulon sexga
  o'tganda kamaymaydi; kamayish faqat sarf (`stock_movement.kind='sarf'`, `order_id` bilan — buyurtma
  tannarxi) yoki «rulon tugadi» (`sex_farq`). Birliklar yig'indisi hech qachon qoldiqdan oshmaydi
  (`services/birlik.py: sync_down` — sotuv, inventarizatsiya, tuzatishdan keyin).
- Berish (`services/berish.py`, sahifa `/warehouse/berish`): faqat darvoza ochiq buyurtmaga; rezervdan
  tashqari qism faqat erkin qoldiqdan — rulondan esa band + erkin qismi olinadi, qolgani ogohlantirish.
  Ombordagi rulon skanerlanganda sexda shu kromkadan ochiq rulon bo'lsa — ogohlantirish.
  `rezerv_line.berilgan_qty`; band = qoplangan − berilgan; hamma qator berilsa rezerv `sarflandi`;
  rezerv qayta qurilsa berilgani saqlanadi.
- Orakl: `scripts/oracles/berish_oracle.py` 39/39; boshqa ombor orakllari o'zgarmay o'tadi.

### 2.3b — sexdan so'rov va qoldiq bo'laklari

- `material_sorov`: arra/kromka/oval terminali «Material so'rash» (`MaterialButton`, buyurtma ochiq
  bo'lganda o'ng pastda). Buyurtma+post bo'yicha bitta ochiq so'rov; post materiali to'liq berilsa o'zi
  yopiladi, omborchi qo'lda ham yopadi. Omborchi «Material berish» sahifasida ko'radi (15 s yangilanadi).
  So'rov majburiy emas — omborchi oldindan berishi ham bir xil yo'l.
- Kromkachi terminaldan «Rulon tugadi» (ikki bosqichli tasdiq) — `POST /ombor/sex/rulon/{barkod}/tugadi`.
- `ombor_bolak`: MES `waste_item` (`ATX-…` yorlig'i) omborga qabul qilinadi (`/warehouse/bolaklar`),
  katalogga moslash jadvali yoki manba buyurtma rezervi orqali o'zi bog'lanadi; boshqa buyurtmaga
  «Material berish» skaneri bilan beriladi; chiqitga chiqariladi. Qoldiqqa (`quantity`) kirmaydi —
  tannarxi asl buyurtmaga butun list bilan yozilgan. Kroyda bo'lakdan foydalanish — MX Kroy (3-bosqich).
- Rezerv qayta qurilganda direktor ruxsati saqlanadi (to'lov haqida, material ro'yxati haqida emas).
- TMO (tayyor mahsulot) jismoniy hisobi MES da allaqachon bor (`/tmo`); uning QIYMAT hisobi
  (tugallanmagan ishlab chiqarish → tayyor mahsulot) Moliya bosqichiga (5) o'tkazildi.

### 2.4 — mustahkamlik (mebel-erp-prototip qoidalari)

Foydalanuvchi talabi (2026-10-29): `mebel-erp-prototip.zip` dagi ishonchlilik darajasi. Kod ko'chirilmadi —
qoidalari olindi:

- **Baza cheklovlari** (`e24a0c1b7f31`): `catalog_item.quantity >= 0`, `stock_lot 0 <= qty_left <= qty`,
  `material_birlik 0 <= qoldiq <= hajm`, `rezerv_line` miqdorlari `>= 0`. `NOT VALID` qo'shilib keyin
  tekshiriladi — prodda eski buzuq qator bo'lsa deploy yiqilmaydi, WARNING beradi.
- **O'zgarmas jurnal**: `stock_movement` va `audit_log` — UPDATE/DELETE trigger bilan taqiqlangan
  (`eko_jurnal_ozgarmaydi`). Xato faqat teskari yozuv bilan tuzatiladi.
- **Jurnal = qoldiq**: boshlang'ich qoldiqlar `boshlangich` harakatlari bilan jurnalga o'tkazildi; pozitsiya
  yaratish va `ombor_seed` endi harakat yozadi. `python -m app.commands.ombor_solishtirish` va worker cron
  (har kecha 02:30 Toshkent): qoldiq = jurnal, partiyalar = qoldiq, barkodlar ≤ qoldiq, berilgan = sarf.
  Farq bo'lsa chiqish kodi 1 / ERROR logi; hech narsani o'zi tuzatmaydi.
- **Storno** (`services/storno.py`, `POST /stock/docs/{id}/storno`, faqat direktor, sabab majburiy):
  `STR-…` hujjati teskari harakatlar bilan; asl hujjat `storno` holatida. Kirim — faqat partiyasi tegilmagan,
  barkodlari omborda butun va material band bo'lmasa. Inventarizatsiya storno qilinmaydi.
- **Ikki kalit** (`ombor_ikki_kalit`, sukut 0; «Tizim sozlamalari → Ombor va rezerv qoidalari»): hujjatni
  yozgan xodim uni o'zi tasdiqlay olmaydi.
- **Parallel ishlash**: hujjat raqami `pg_advisory_xact_lock` bilan (parallel sinov bir xil raqam
  berilishini topdi), raqam son sifatida solishtiriladi; `lock_timeout` 5 s va
  `idle_in_transaction_session_timeout` 60 s (`DB_LOCK_TIMEOUT_MS`, `DB_IDLE_TX_TIMEOUT_MS`); qulf/deadlock —
  503 «Tizim hozir band» + `Retry-After`, baza qoidasi buzilishi — 409 (500 emas).
- Orakl `mustahkamlik_oracle.py` 28/28: jurnalni o'zgartirish rad, manfiy rad, 10 parallel sotuv (qoldiq 5) —
  aniq 5 tasi, bitta barkodni ikki joyda skan — bittasi, storno, ikki kalit, buzilgan qoldiq ushlanadi.

Ochiq (keyingi bosqichlar): MXIK va shtrix-kod katalogda (Soliq, 6), kompaniya → filial → ombor tuzilmasi,
idempotent inbox/outbox (MX Kroy integratsiyasi, 3), so'rovni avtomatik qayta urinish (hozir 503 + qayta bosish).

### 3a — MX Kroy: qoldiq ombori (K3) va webhook inbox (K4)

MX tomoni tayyor edi (`MebeliX_Kroy/MES_INTEGRATSIYA.md`, `docs/mebelix/MES_QOLDIQ_V1.md`); MES tomoni:

- `ombor_bolak` — YAGONA qoldiq registri, ikki manba: `mes` (MES `ATX-` yorlig'i) va `mx` (MX kirim hujjati).
  MX bo'lagi `kutish` (qty 0, `qty_pending`) holatida yaratiladi, karta listi arradan chiqqach (`map.done`)
  ulushi `ombor` ga o'tadi: `jami × done / nusxa`. Karta raqami har MX OPERATSIYASIDA 1 dan boshlanadi —
  bog'lash `mx_loyiha + mx_op + karta` bo'yicha (faqat loyiha + karta bo'lsa boshqa materialning bo'laklari ochilardi).
- API `{MES}/api/v1/ombor/kroy` (MX: «Источник склада: База MES», `mes_url` shu): `GET /remnants`
  (kod, kod bo'lmasa nom — harf/bo'shliqsiz), `POST /remnants/reservations` (`add|remove|set`, boshqa loyiha
  bandi va `kutish` — 409 `conflicts`), `POST /remnants/intake` (`IN-2026-0001`), `POST /remnants/intake/{id}/cancel`
  (takror — xavfsiz). Kirish — xizmat tokeni `KROY_API_TOKEN` (MX da `MES_API_TOKEN`/`MES_WEBHOOK_TOKEN`).
- Webhook `POST /api/v1/integ/kroy/webhook` → `integ_inbox`: MX xabarlarida `event_id` YO'Q — kalit
  `event_id` yoki `{event}:{sha256(yuklama)}`; takror — `duplicate`, xuddi shu kalit boshqa mazmun — 409;
  ishlovda xato — 500, hech narsa yozilmaydi (MX navbatida qoladi). Hozir ishlovi: `map.done`;
  `project.status`, `remnant.move` saqlanadi (K1 da ulanadi).
- MES ichida bo'lak skaner bilan berilganda MX bandi hurmat qilinadi.
- Orakl `kroy_http_oracle.py` 20/20 — ishlab turgan serverga MX so'rovlari aynan o'z shaklida.

Ochiq: MX bo'lagining jismoniy yorlig'i — K2 paketidagi qoldiq (`waste_item`, `ATX-`) bilan bog'lanadi.

### 3b — buyurtma → MX loyiha (K1) va yagona kirish (K6)

- Buyurtma sahifasida «Kroy (MX)» (admin, direktor, texnolog, menejer): `POST /integ/kroy/orders/{id}/ochish`
  MX `POST /api/mes/orders` ga sarlavha yuboradi (`mes_order_ref` = buyurtma raqami, mijoz, sanalar), `kroy_loyiha`
  ga bog'laydi va brauzerni `{MX_PUBLIC_URL}/?token=…#/p/{pid}` ga ochadi. Bog'langan loyiha QAYTA YUBORILMAYDI —
  faqat ochiladi (MX `merge_order` detalsiz sarlavhani olib kroychining detallarini va CS operatsiyasini o'chirib
  yuborardi — brauzerda ko'rilgan xato); MX da o'chirilgan bo'lsa (404) — qaytadan yaratiladi. Detallarni kroychi MX da `.project` dan yuklaydi.
- SSO: MES RS256 bilan imzolaydi (`MX_SSO_PRIVATE_KEY`), MX faqat ochiq kalitni biladi (`MEBELIX_JWT_PUBLIC_KEY`).
  Kalit jufti: `python -m app.commands.kroy_kalit`. Rollar: admin/direktor → `admin`, texnolog → `texnolog`+`kroychi`,
  menejer/skladchi → `ko'ruvchi` (MX da faqat o'qish, tahrir 403), sex rollari — ochilmaydi. Sessiya 8 soat
  (`MX_SSO_TTL_MIN`): kroychi MX da smena davomida ishlaydi — TZ dagi «≤ 15 daq» o'rniga, chunki MX tokenni
  sessiya sifatida saqlaydi va muddati o'tsa ish uziladi. Server → server — 5 daqiqalik xizmat tokeni.
- `project.status` webhook → `kroy_loyiha.holat` (0–3).
- MX da topilgan xato (MX klonida tuzatildi, `D:\EKO TIZIM\mx-kroy` `eko-integratsiya` tarmog'i): `requirements.txt`
  da `cryptography` yo'q edi — `MEBELIX_JWT_PUBLIC_KEY` bilan HAR qanday RS256 token «Algorithm not supported»;
  ochiq kalit endi bir qatorda (`\n` bilan) ham qabul qilinadi.
- Sinov: MX klon (8010, o'z SQLite bazasi) ↔ MES (8005): loyiha yaratildi, SSO bilan 200, tokensiz/soxta 401,
  ko'ruvchi tahriri 403, `project.created/updated/status` webhooklari inboxda; brauzerda tugma MX ni kirgan holda ochdi.

Ulash (prod): MES `.env` — `MX_URL`, `MX_PUBLIC_URL`, `MX_SSO_PRIVATE_KEY`, `KROY_API_TOKEN`; MX `.env` —
`MEBELIX_JWT_PUBLIC_KEY`, `MEBELIX_AUTH_REQUIRED=1`, `MES_WEBHOOK_URL={MES}/api/v1/integ/kroy/webhook`,
`MES_WEBHOOK_TOKEN`=`MES_API_TOKEN`=`KROY_API_TOKEN`; MX sozlamasi «Источник склада: База MES», `{MES}/api/v1/ombor/kroy`.

### 3c — MX Kroy paketi (K2)

- Paket `.project` faylining o'rnini bosadi va AYNAN o'sha yo'ldan o'tadi (`orders/files.py: load_project`):
  qayta yuklash qoidasi (postda skan bo'lsa rad), qo'lda marshrutlar saqlanadi, eski natija `.stale`, rezerv.
  `services/giblab/mx_paket.py` paketni `ParsedProject` + `CutmapResult` + `WasteItem` ro'yxatiga o'giradi;
  `ingest_project` ga tayyor xarita, qoldiqlar, `raw_kind=KROY_PAKET`, `write_scx=False` beriladi. Ikkinchi ingest yo'q.
- Qat'iy tekshiruv: format/versiya, `source.mes_order_number` = buyurtma raqami, har nusxa QR MES qoidasiga
  (`instance_qr`) aynan mos, stanok fayli sha256. Nusxa ↔ katak — paketdagi `instance_no` bo'yicha.
- Marshrut MES qoidasi bilan: ARRA (xaritada joyi bor), KROMKA (qirralar soni), PRISADKA — XNC dasturi VA
  CNC stanok fayli kelgan detalga (`forced_passes`, shartnomaning «machining» qoidasi). Stanok fayllari
  `uploads/projects/{id}/stanok/{stanok}/` (`FileKind.STANOK`, meta: format, stanok, sha256, detallar).
- Sarf (`consumption`) → `order.material_usage` (CS/CN → list, EL → kromka, CL → `linear` metr, boshqasi → dona).
  Rezerv: fayldagi kod katalog kodiga AYNAN teng bo'lsa moslash avtomatik (koef 1, bir marta yoziladi).
- Ikki yo'l: «Kroyni olish» (buyurtma sahifasi; MES `GET {MX}/projects/{pid}/mes-package?pp=enabled`) va MX
  yuboradi `POST /api/v1/integ/kroy/orders/{id}/kroy-package` (xizmat tokeni; 201 `{order_id, order_number, redirect_url}`).
- Yo'l-yo'lakay topilgan xatolar: (1) rezerv qayta qurilganda berilgan miqdor yangi ehtiyojgacha KESILARDI va
  kroydan chiqib ketgan material yo'qolardi — endi to'liq ko'chadi, «kerak 0, berilgan N» qatori, berish
  varaqasida «ortiqcha» (kechki solishtirish ushlagan); (2) to'liq berilgan (`sarflandi`) rezervli buyurtmaga kroy
  qayta yuklansa berilgan hammasi yo'qolardi (orakl ushlagan). MX klonida: `pp=all` nesting stanoklarida 422.
- Sinov: MX klonidagi haqiqiy paket (2 list, 3 detal × 2 shkaf = 12 nusxa) → MES: QR, katak, marshrut, sarf,
  kromka rezervi; MES xarita sahifasi paket xaritasini chizdi (konsol xatosiz); orakllar berish 53/53.

Ochiq: qaytarish oqimi (ortiqcha berilgan materialni sexdan omborga skan bilan); MX bo'lagi (`kroy_intake`) ↔
paketdagi `ATX-` qoldiq bog'lanishi; MX da «MES» tugmasi (push) — hozir MES o'zi oladi.

### 3d — arra «list chiqdi» va outbox

- `scanning.finalize_scan`: ARRA skanidan keyin (commit'dan oldin) `integratsiya.arra_skan` — andozaning har
  katagida nechta nusxa kesilgani, kesilgan list soni = eng kami (`mult` gacha). Son o'sganda MX qoldiq
  bo'laklari ulushi `kutish` → `ombor` (MX ni kutmasdan) va MX ga `PATCH /projects/{pid}/operations/{op}/maps/{n}`
  `{done_count}` outbox orqali. Faqat MX paketi bilan yuklangan buyurtmada (`order.cutmap` varag'ida `mx_op`, `mx_index`).
- `integ_outbox`: xabar biznes tranzaksiyasi bilan birga yoziladi; worker har daqiqa (`cron second=15`) tartib
  bilan yuboradi; ulanish/5xx — to'xtaydi, 1/5/30/120/360 daqiqadan keyin qayta; 4xx — `rad`, navbatni to'smaydi;
  kalit bo'yicha takror yozilmaydi; MX ga `Idempotency-Key`.
- Topilgan va tuzatilgan: «Kroy (MX)» ni qayta bosish MX loyihasini detalsiz sarlavha bilan qayta yuborib
  kroychining detallarini o'chirardi (Chrome'da ko'rilgan) — bog'langan loyiha endi faqat ochiladi.
- Sinov (MX klon ↔ MES): MX ning O'Z kodi «MES ombori» rejimida kirim yubordi (`IN-2026-0003`, 3 bo'lak `kutish`);
  2-list 7 nusxasi arra skanidan (`finalize_scan` orqali) o'tgach 2-kartaning bo'lagi `ombor` ga, outbox xabari
  MX da 2-karta `done_count=1`, MX `map.done` qaytardi (inbox: takror qo'llanmadi). `kroy_outbox_oracle.py` 9/9.

### 3e — katalog sinxroni (K5) va MX bo'lagi ↔ ATX yorlig'i

- K5: `ombor/services/mx_katalog.py` MES katalogini MX `CatalogIn` shakliga o'giradi (`M` → `sheet`, `F-KM` → `edge`,
  guruhlar `folder`, ID = MES kodi; o'lcham `2750x1830x16` → length/width/thickness; narx — sotuv narxi).
  `integratsiya/katalog.py` faqat O'ZGARGANLARINI (`kroy_katalog` dagi xesh) 500 tadan outbox orqali yuboradi;
  worker har 10 daqiqada, birinchi to'liq yuborish — `python -m app.commands.kroy_katalog`. Sinov: 2189 yozuv
  12 s da, qayta ishga tushirish — 0, bitta narx o'zgarsa — faqat o'sha (MX da yangi narx).
- MX bo'lagi ↔ ATX: paket qabul qilinganda (`paket._yorliqla`) paketdagi qoldiqlar (`waste_item`, `ATX-…`) shu
  loyihaning MX bo'laklariga `sheet_no → (mx_op, karta)` va o'lcham (±1 mm) bo'yicha `ombor_bolak_yorliq` orqali
  bog'lanadi (bo'lakda bir necha dona bo'lsa — har donaga yorliq). `ATX` skanerlansa bo'lak shu orqali topiladi;
  listi kesilmagan bo'lak — «hali arradan chiqmagan». Xarita katagiga `atx` raqami qo'yiladi — arra terminali chek
  chiqaradi. Bo'laklar sahifasida yorliqlar ko'rinadi.
- MX da topilgan va klonda tuzatilgan: paket `remnants[]` faqat «деловой» belgisiga qarardi, MES ga kirim esa foiz
  qoidasi bilan ketardi — foiz bilan olib qolingan bo'lak paketda yo'q, yorlig'i chiqmasdi. Endi ikkalasi bitta
  qoida (`remnant_rules.classify`); MX testlari 167/167.

### 3f — ortiqcha berilgan materialni qaytarish

- Kroy material berilgandan keyin o'zgarsa `berilgan > kerak` (3c). «Material berish» → «Ortiqchani qaytarish»
  rejimi (`POST /ombor/berish/{id}/qaytar`): list — o'z barkodi (shu buyurtmaga berilgan bo'lsa) omborga qaytadi;
  rulon — barkod + metr, rulon qoldig'iga qo'shiladi (sig'imidan oshmaydi); furnitura — kod + son. Faqat ortiqcha
  miqdorgacha. Qoldiq `qaytish` harakati bilan, shu buyurtma sarfining o'rtacha tannarxida yangi partiya bo'lib
  kiradi; rezerv `berilgan` kamayadi. Kechki solishtirish: berilgan = sarf − qaytish.
- Orakl `berish_oracle` 60/60 (15-bosqich); brauzerda: akril listi va 10 m kromka qaytdi, rulon sig'imidan
  oshirish rad etildi; solishtirish farqsiz.

### 3g — MX «Раскроечные станки»: stanok standarti MES paroli bilan (2026-10-30)

- MX `4f94fd3`: stanok standarti (pila, torsovka, burilishlar…) faqat login paroli bilan o'zgaradi. MES SSO
  rejimida (ochiq kalit) MX da parol yo'q — tekshiruv o'chib, texnolog va direktor standartni parolsiz yozardi.
- Endi MX parolni MES dan so'raydi: `POST /api/v1/integ/kroy/parol-tekshir` (xizmat tokeni `KROY_API_TOKEN`)
  `{login, password}` → `{ok}`. Login — SSO tokendagi `sub` (foydalanuvchi nomi; telefon qabul qilinmaydi), nofaol va
  texnik hisob — `ok: false`. Xato urinishlar LOGIN bo'yicha cheklanadi (`LOGIN_RATE_LIMIT_*`, keyin 429): hamma
  so'rov bitta MX serveridan keladi. Har urinish audit logda (`kroy/mx_parol`, `mx_parol_xato`).
- MX tomoni (klon `eko-integratsiya`, asl MX ga o'tkaziladi): manzil `MES_PASSWORD_URL`, bo'lmasa
  `MES_WEBHOOK_URL` dagi `/webhook` → `/parol-tekshir`; MES javob bermasa yoki sozlanmagan bo'lsa — 503, standart
  o'zgarmaydi (parolsiz o'tkazilmaydi).
- Orakl `mx_parol_oracle` 10/10 (jonli MES + MX klon); MX testi `test_password_checked_by_mes_in_sso_mode`.
- Shu yangilanishdagi `3982f3d` (detal soni oshsa kroy saqlanadi): «До кроить» qilinmagan nusxalar paketda
  «Kesish xaritasida joyi yo'q nusxalar» ogohlantirishi bilan keladi — MES tomonida o'zgarish kerak emas.

### 4a — Kassa (backend)

`app/modules/kassa` (TZ §7; prototip `Kassa.dc.html` / `kassa-core.js` qoidalari):
- Hisoblar (`kassa_hisob`: naqd, karta, bank; komissiya %), smena (`kassa_smena`: kupyura bo'yicha ochish/yopish,
  birinchi smenada sanalgan naqd — boshlang'ich qoldiq; yopishda kutilgan bilan farq → `farq` orderi; karta terminali
  Z va tizim karta tushumi), orderlar (`kassa_order`: PKO/RKO, `kassa_taqsimot` — buyurtmalarga taqsimot).
- Order va taqsimot — JURNAL: UPDATE/DELETE trigger bilan taqiqlangan; summa > 0 (storno — manfiy, `storno_of_id`);
  hisob qoldig'i ustun emas, jurnal yig'indisi. Storno — faqat direktor va ikki kalit (yozgan xodim emas),
  o'tkazma oyoqlari va komissiya birga; aralash to'lov qismlari alohida.
- Qoidalar: naqd — faqat ochiq smenada; chiqim qoldiqdan (bankda komissiya bilan); buyurtma to'lovi qolganidan
  oshmaydi; qarz — mijoz qarzidan, eng eski buyurtmadan; qaytarish — kassadan to'langanidan; mijoz bergan pul va qaytim.
- Rezerv: `paid_and_required` va `client_debt` endi kassadan (+ kassagacha `advance_payment`, o'tish davri). To'lovdan
  keyin shu tranzaksiyada B2 — kassirga «material biriktirildi» / «chegaraga yana N so'm kerak».
- Rol `kassir` (o'rta daraja). API `/api/v1/kassa/...`. Orakl `kassa_oracle.py` 27/27.

Ochiq: `advance_payment` maydonini kassa yoqilgach tahrirlashni yopish (hozir ikkalasi qo'shiladi); fiskal chek (9-bo'lim).

### 4b — Kassir ekrani `/kassa`

Prototip `Kassa.dc.html` tuzilishi: tepada smena, kassir, naqd qoldiq, smenadagi kirim/chiqim/karta; chapda to'lov
navbati (qolgani bor buyurtmalar, qidiruv, «avans: N so'm» — rezerv chegarasigacha); o'rtada Kirim (avans, to'lov,
qarz, boshqa; naqd/karta/bank/naqd+karta; «Eng kam avans» va «Hammasi» tugmalari; mijoz bergan pul → qaytim) va
Chiqim (xarajat turkumlari, ta'minotchi, qaytarish, inkassatsiya); o'ngda smena orderlari. Smena ochish/yopish —
kupyura bo'yicha sanash, kitob/kutilgan bilan farq, karta terminali Z. Rad xabarlari backenddan, o'zbekcha.
Kassir (`kassir` roli) kirgach to'g'ri `/kassa` ga tushadi; sidebar «Kassa» — kassir va direktor.
Demo: smena 2 500 000 → B-2026-101 avans 2 500 000 (berdi 2 600 000, qaytim 100 000) → «material biriktirildi»
→ turkumsiz xarajat rad → 150 000 xarajat → yopishda 10 000 kam sanaldi → «Smena farqi» RKO avtomatik.

### 5a — Moliya (backend)

`app/modules/moliya` (TZ §8; prototip `Moliya.dc.html`). Moliya o'zi pul yozmaydi: hamma raqam jurnallardan
yig'iladi — kassa orderlari, ombor hujjatlari va sarf harakatlari, buyurtmalar (`delivered_at`). O'zining jadvallari:
`moliya_reja` (rejali to'lovlar: oylik / bir marta), `moliya_mijoz_shart` (shartnoma №, to'lov muddati),
`moliya_davr` (yopilgan oylar). Xarajat moddalari va oylik limit — `kassa_modda` (xarajat orderi faqat faol moddaga).
- **P&L** (oy): sotuv = shu oy yetkazilgan buyurtmalar + do'kon chiqim hujjatlari (storno ayirilgan); tannarx =
  buyurtmaga sarf − qaytish (FIFO) + chiqim hujjati `cogs`; xarajat = xarajat va komissiya orderlari moddalar
  bo'yicha + smena kamomadi; buyurtma rentabelligi.
- **Pul oqimi**: o'tkazmalarsiz kirim/chiqim moddalar, hisoblar, kassirlar bo'yicha va 12 oy.
- **Debitorlik**: yetkazilgan va to'lanmagan — qarz, yetkazilmaganga olingan — avans; muddat (shartnoma yoki
  sozlama `tolov_muddat_kun`, standart 10), kredit limiti (`client.kredit_limit`). **Akt sverki**: debet — yetkazilgan
  buyurtma va qaytarilgan pul, kredit — to'lov, boshlang'ich va yakuniy saldo.
- **Kreditorlik**: ombor kirimlari (`head.supplier`, `head.due`) − kassa «ta'minotchi» orderlari (kontragent nomi,
  harf farqsiz), to'lov eng eski hujjatdan yopiladi.
- **To'lov kalendari** (45 kun), **byudjet** (limit va fakt), **balans** (pul, debitorlik, ombor qiymati FIFO,
  kreditorlik, olingan avans), **bosh sahifa** vazifalari (yopilmagan smena, muddati o'tgan qarz, 3 kun ichidagi
  to'lov, byudjetdan oshish, o'tgan oy yopilmagan), orderlar jurnali CSV.
- **Davr yopish**: faqat tugagan oy, ochiq smena va qoralama hujjat bo'lmasa; P&L nusxasi qotadi; o'sha sanali
  ombor hujjati tasdiqlanmaydi; qayta ochish — ikki kalit (so'rov va boshqa xodim tasdig'i).
- Rol `moliyachi` (ofis darajasi); Moliya API va kassa stornosi — direktor va moliyachi. Orakl `moliya_oracle.py` 32/32.

Ochiq: dollar kursi tarixi (TZ §8 «Kurs») — hozir ombor kirimidagi kurs ishlatiladi; ta'minotchi alohida
ma'lumotnoma emas (nom bo'yicha), og'ir hisobotlarni fonga o'tkazish (TZ §10) — hajm o'sganda.

### 5b — Moliya ekrani `/moliya`

Bo'limlar (`?b=`): Bosh sahifa (pul hisoblar bo'yicha, mijozlar qarzi va muddati o'tgan qismi, bizning qarz,
rejali to'lovlar, vazifalar — bosilsa bo'limga o'tadi, 30 kunlik pul oqimi grafigi, oy P&L), Mijozlar qarzi
(shartnoma, muddat, limit; akt sverki A4 chop), Bizning qarz, To'lov kalendari (45 kun + rejali to'lovlar),
Orderlar jurnali (sana oralig'i, qidiruv, CSV, storno — sabab bilan, ikki kalit backendda), Smenalar (sanash
farqlari), Hisobotlar (P&L, byudjet, pul oqimi moddalar bo'yicha, 12 oy grafigi, hisoblar va kassirlar, balans),
Davr yopish (yopish, qayta ochish so'rovi va tasdig'i), Sozlamalar (hisob boshlang'ichi va komissiya, eng kam avans,
to'lov muddati, xarajat moddalari va oylik limit). Sidebar «Moliya» — direktor va moliyachi.
Grafik ranglari — dataviz palitrasi (kirim ko'k, chiqim to'q sariq), legenda va hover.
Storno qatori pulga ta'siri bilan ko'rsatiladi (chiqim stornosi «+»). Muddati o'tgan qarz — buyurtma bo'yicha
(faqat muddatdan o'tgan buyurtmalar summasi), mijozning butun qarzi emas.
Demo: debitor muddati 10 → 30 kun (qizil belgi yo'qoladi), akt sverki, xarajat stornosi (P&L dan chiqadi),
sentyabrni yopish, o'sha xodim qayta ochishni tasdiqlay olmaydi.

### 6.0 — Obuna rejimi: tarif darvozasi

1b dagi `require_module` endi ombor, kassa, moliya, soliq va kroy yo'llariga ulangan: obunachi tarifida yo'q modul —
403 «Bu modul tarifingizga kirmaydi.». `GET /users/me/modullar` — obunachi modullari; menyu yoqilmagan modul bandini
ko'rsatmaydi. Har obunachining bazasi alohida, shuning uchun soliq rejimi, rekvizitlar va stavkalar ham obunachiniki.

### 6a — Soliq (backend)

`app/modules/soliq` (TZ §9). Stavka va rejim kodga yozilmaydi:
- **Rejim tarixi** `soliq_rejim` (amal_boshi, `qqs` | `aylanma`, QQS %, aylanma %): hujjat sanasidagi rejim olinadi —
  yil o'rtasida QQS ga o'tilsa ham o'tgan oylar eski rejimda qoladi; yuborilgan ESF bor sanaga orqaga yozilmaydi.
- **Rekvizitlar**: korxona (`soliq_korxona`: nomi, STIR, bank, MFO, hisob raqami, QQS kodi, ESF operatori, buyurtma
  MXIK i), mijoz (`soliq_mijoz`: yuridik — STIR 9, jismoniy — JShShIR 14), katalogda `mxik` (17), `birlik_kod`,
  `qqs_turi` (standart / nol / ozod).
- **ESF** (`soliq_esf`): yetkazilgan buyurtmadan yoki tasdiqlangan ombor sotuvidan, faqat yuridik mijozga; narx QQS
  bilan, QQS = jami × f/(100+f); MXIK siz pozitsiya — rad. Holatlar: qoralama → navbatda → yuborildi →
  qabul_qilindi / rad_etildi, bekor; operator ishlamasa qayta urinish 1/5/30/120/360 daqiqa, keyin `xato`.
  Fon ishi `soliq_esf_all` (har daqiqa, tarifida soliq yo'q obunachini o'tkazadi). Kiruvchi ESF — operatordan,
  ombor kirimi bilan sotuvchi nomi va summa bo'yicha bog'lanadi; qabul / rad (sabab bilan).
- **Operator adapteri** (`operator.py`): yuborish, holat, kiruvchilar, javob, bekor. Hozir faqat **`sinov`** — LOKAL
  sinov operatori (STIR/MXIK/summalarni tekshiradi, qabul yoki rad qiladi; soliq tizimiga hech narsa ketmaydi).
- **Oylik soliq**: aylanma = yetkazilgan buyurtmalar + do'kon sotuvi; QQS rejimida sotuv QQS − qabul qilingan
  kiruvchi ESF QQS; aylanma rejimida aylanma × stavka. **QQS kitobi** (sotuv/xarid, CSV) + ESF siz (jismoniy shaxs)
  sotuvdagi QQS. **P&L**: QQS to'lovchida sof tushum = sotuv − sotuvdagi QQS, aylanma to'lovchida aylanma soliq xarajat.
- Orakl `soliq_oracle.py` 28/28 (ikki rejim, operator uzilishi, kiruvchi ESF, qo'lda hisob).

Ochiq: haqiqiy ESF operatori (Didox / Faktura.uz va h.k.) — API kaliti, hujjat formati va E-IMZO imzosi kerak;
fiskal chek (S5); xarid QQS i tannarxdan ayirilmaydi (kirim narxi QQS bilan); stavkalarni buxgalter tasdiqlaydi.

### 6b — Soliq ekrani `/soliq`

Bo'limlar (`?b=`): ESF — sotuv (ESF yozilmagan yetkazilgan buyurtma va ombor sotuvlari; rekvizit yo'q bo'lsa avval
mijoz rekvizitlari oynasi, keyin ESF; ombor sotuvida xaridor mijoz tanlanadi; ESF varag'i — hisob-faktura shakli,
chop etiladi; yuborish, bekor, «navbatni hozir yuborish»), Kiruvchi ESF (operatordan olish, ombor kirimi bilan
bog'lanish, qabul / rad sabab bilan; sinov operatorida «yetkazib beruvchi ESF yuboradi» formasi), Soliq va QQS kitobi
(oy: aylanma, sotuv/xarid QQS, to'lanadigan yoki keyingi oyga o'tadigan ortiqcha xarid QQS, aylanma soliq; sotuv va
xarid kitobi, CSV, A4), Sozlamalar (rejim tarixi, korxona rekvizitlari, buyurtma MXIK i, katalogda MXIK / birlik /
QQS turi). Tepada doim «ESF operatori: lokal SINOV — soliq tizimiga hech narsa yuborilmaydi». Sidebar «Soliq» —
direktor va moliyachi, tarifida `soliq` bo'lsa. Moliya P&L jadvalida «Sotuvdagi QQS», «Sof tushum» va «Aylanmadan
soliq» qatorlari.

### 7a — Buxgalteriya (backend), 1C siz

`app/modules/buxgalteriya`, tarif moduli `buxgalteriya`. Jadvallar: `bux_schyot` (BHMS 21 asosida 30 ta asosiy schyot —
buxgalter to'ldiradi/tasdiqlaydi), `bux_qoida` (kalit → schyot: `hisob:naqd` 5010, `xarajat:*` 9420, `xarajat:<modda>`…),
`bux_yozuv` (provodka; jurnal — UPDATE/DELETE trigger bilan taqiqlangan).
- **Avtomatik provodkalar manba jurnallaridan**: kassa orderlari (storno ham, o'tkazma juftligi), ombor harakatlari
  qiymati (1010 ↔ 6010 / 9120 / 2010 / 2510 / 9390–9430), yetkazilgan buyurtma (4010–9010, tannarx 9110–2010),
  do'kon sotuvi (4010–9020), oy soliqi (9010/9020–6410 QQS, 9810–6410 aylanma), boshlang'ich qoldiqlar (… –8710).
- **Sinxron = farq**: har manba guruhi va subkonto bo'yicha «bo'lishi kerak − yozilgan» yoziladi. Takror sinxron
  hech narsa yozmaydi; manba o'zgarsa (summa, bekor, qoida) — tuzatish provodkasi; yopilgan oyga — bugungi sana.
  Fon ishi har 5 daqiqada, hisobot oldidan ham.
- Hisobotlar: aylanma-saldo vedomosti (4010/6010 — mijoz/kontragent bo'yicha kengaytirilgan saldo, CSV), schyot
  kartochkasi, provodkalar jurnali. Qo'lda provodka (ish haqi, asosiy vosita) va uning stornosi (ikki kalit).
- **Nazorat**: 5010/5710/5110 = kassa qoldiqlari, 1010 = ombor qiymati, 4010 = Moliya debitor (qarz − avans),
  6010 = Moliya kreditor; oy natijasi (9xxx) = Moliya P&L sof foydasi (ombor tuzatishlari P&L da yo'q).
- Tuzatildi: «ombor qiymati» endi partiyasi hali ochilmagan qoldiqni ham xarid narxida hisoblaydi (ombor hisoboti
  kabi) — ilgari Moliya balansida kam chiqardi.
- Orakl `bux_oracle.py` 23/23 (seed ombor ma'lumotlari bilan: 1010 = 116 524 210 = ombor qiymati).

Ochiq: xarid QQS i (4410) tannarxdan ajratilmaydi; ish haqi va asosiy vositalar — hozircha qo'lda provodka;
schyot nomlari va qoidalarni buxgalter tasdiqlaydi; hisoblash hajm o'sganda faqat ochiq oylar bo'yicha qilinadi.

### 7b — Buxgalteriya ekrani `/buxgalteriya`

Bo'limlar: Aylanma-saldo (davr, 4010/6010 kengaytirilgan, «Balans: debet = kredit», CSV, A4; schyot bosilsa
kartochka), Schyot kartochkasi (qarshi schyotga o'tish, oraliq saldo; bir kunda boshlang'ich qoldiq birinchi),
Provodkalar (jurnal, «faqat qo'lda», qo'lda provodka va uning stornosi — ikki kalit), Nazorat (buxgalteriya ↔ kassa,
ombor, Moliya; 1 so'mdan kam farq — «yaxlitlash», sariq), Schyotlar va qoidalar (qoida tahriri qayta tasniflaydi).

Nazorat demo bazada ikki narsani topdi va tuzatildi:
- **Kod xatosi (5a dan beri):** storno qilingan ombor hujjatining asl holati `storno` — Moliya va buxgalteriya faqat
  `confirmed` ni o'qirdi: kreditorlikdan storno bir tomonlama ayirilardi, storno harakati 9430 ga tushardi.
  Endi `confirmed` va `storno` ikkalasi o'qiladi; `moliya_oracle` ga regressiya tekshiruvi qo'shildi.
- **Demo ma'lumot:** 5-bosqich demosidagi `KIR-DEMO-1` harakatsiz yozilgan edi — partiya va harakat qo'shildi.
Birinchi noto'g'ri tasnif keyingi sinxronda tuzatish provodkasi bilan qaytarildi (jurnal o'chirilmaydi — bu tarix).

### 8a — Ishga tushirish (backend; TZ §11, 7-bosqich)

Tashqi xizmatlarsiz (haqiqiy ESF operatori, E-IMZO, fiskal chek — keyin ulanadi; adapter va navbat tayyor).
- **Qo'lda avans qulfi**: kassada birinchi order yozilgach buyurtmadagi `advance_payment` yaratib/o'zgartirib
  bo'lmaydi (403 «avans endi Kassa orqali») — ilgari ikkalasi qo'shilib pul ikki marta sanalishi mumkin edi.
- **Boshqaruv paneli** «qoldiq to'lovlar»: endi kassa to'lovlarini ham ayiradi (ilgari faqat qo'lda avans).
- **Ochilish qoldiqlari** `kassa_ochilish` (jurnal): mijoz qarzi / avansi, ta'minotchiga qarz / avans, sanasi bilan.
  `POST /moliya/ochilish` — bitta yoki CSV dan ko'p qator (mijoz: id, telefon yoki aniq nomi); bitta qator xato
  bo'lsa hech biri yozilmaydi. Tuzatish — teskari ishorali qator; to'langan qismdan pastga kamaytirilmaydi.
  Mijozning «Qarzni to'lash»i avval ochilish qarzini yopadi (`kassa_taqsimot.ochilish_client_id`), storno qaytaradi;
  kassa navbatida «Ochilish qarzi» qatori. Moliya debitor/kalendar/akt, kreditor (eng eski «hujjat»), rezerv kredit
  limiti va buxgalteriya (4010–8710, 8710–6010) uni ko'radi.
- **Tayyorlik** `GET /tayyorlik`: kassir bor, karta/bank boshlang'ichi, birinchi smena, ikki kalit uchun ≥ 2 moliya
  xodimi, ochilish qoldiqlari, korxona rekvizitlari, soliq rejimi, ESF operatori (sinov — ogohlantirish), MXIK
  qamrovi, inventarizatsiya, buxgalteriya nazorati. Tarifda yo'q modul tekshirilmaydi.
- Orakl `ishga_tushirish_oracle.py` 16/16 (yo'l funksiyasi commit qiladi — har safar toza baza).

### 8b — «Ishga tushirish» ekrani `/ishga-tushirish`

Tayyorlik ro'yxati (qizil — to'siq, sariq — e'tibor; har band tuzatish joyiga olib boradi) va ochilish qoldiqlari:
bitta qator (mijoz qidiruvi yoki ta'minotchi nomi) yoki CSV / Excel dan (`tur;telefon yoki nom;summa;sana;izoh`,
DD.MM.YYYY ham) — xato qator raqami bilan ko'rsatiladi, hech biri yozilmaydi. Kassa navbatida «Ochilish qarzi»
tanlansa maqsad o'zi «Qarzni to'lash» (natija xabari saqlanadi). Buyurtma formasida kassa moduli yoqilgan bo'lsa
«Boshlang'ich to'lov» yopiq («Kassa orqali»).

Ko'rsatish paytida topilib tuzatildi:
- buyurtma sahifasi va mijoz kartasidagi «Qoldiq to'lov» faqat qo'lda avansdan hisoblanardi — endi buyurtma
  javoblarida `kassa_tolangan`, sahifada «To'langan» = avans + kassa (`lib/mes.ts: paidTotal`);
- tayyorlikdagi «ikki kalit» admin va superuser ni sanamasdi (ular ham storno qila oladi).

### 9 — Yo'riqnomalar (xodimlarni o'qitish, TZ §11 7-bosqich)

Matn manbasi — `frontend/src/yoriqnoma/` (frontend image faqat `frontend/` papkasidan quriladi, shuning uchun
`docs/` da emas): [kassir](../../frontend/src/yoriqnoma/kassir.md),
[omborchi](../../frontend/src/yoriqnoma/omborchi.md), [moliyachi](../../frontend/src/yoriqnoma/moliyachi.md),
[direktor](../../frontend/src/yoriqnoma/direktor.md). Dasturda — menyu **Yo'riqnoma** (`/yoriqnoma`, har xodimga o'z
roli birinchi ochiladi, chop etiladi). Ekrandagi nom yoki qoida o'zgarsa — yo'riqnomani ham yangilang.


### 10a — Ishbay ish haqi va mehnat tannarxi (`modules/tannarx`)

MES da OEE, ideal sikl va hodim mahsuldorligi bor edi, lekin pul yo'q edi: stavka, ish haqi va buyurtmaning
mehnat tannarxi yo'q. Endi:

- **Stavka** (`ish_stavka`) — post birligi uchun so'm (arra/qadoqlash — m², kromka — metr, qolgani — dona), kerak
  bo'lsa aniq amal (`process_code`) uchun alohida; sanadan boshlab tarix bilan. Tasdiqlangan vedomost davriga
  orqaga yozilmaydi.
- **Hisob** — bekor qilinmagan skanlardan: bitta skan hajmi = detalning shu postdagi hajmi ÷ marshrut
  `total_required` (TABLO bilan bir xil, `services/metrics.part_volume`). Skan sanasidagi stavka olinadi. Brak
  tasdiqlanib bekor qilingan skan haqi to'lanmaydi.
- **Vedomost** (`ish_haqi_vedomost` + qatorlar hodim × post) — davr kechagi kun bilan tugaydi, ustma-ust davr
  yo'q, stavkasi yo'q postdagi ish bo'lsa yaratilmaydi. Tasdiqlash — ikki kalit; tasdiqlashda skanlar qayta
  hisoblanadi, o'zgargan bo'lsa rad (bekor qilib qaytadan).
- **Buxgalteriya**: tasdiqlangan vedomost — D 2010 — K 6710 (hodim bo'yicha); buyurtma yetkazilganda tannarx
  (D 9110 — K 2010) material + mehnat. Kassadan to'lov — modda **«Ish haqi (ishbay)»** (`kassa_modda.pnl_emas`,
  qoida → 6710): P&L xarajati emas, qarzni yopadi. Nazoratda yangi qator: 6710 = vedomost − kassa to'lovi.
- **Moliya P&L**: buyurtma tannarxida mehnat bor; ish haqi to'lovi xarajatga ikkinchi marta kirmaydi.
- API `/tannarx/...` (direktor, moliyachi; tarif — `moliya` moduli), ekran — Moliya → **Ish haqi**.
- Orakl: `scripts/oracles/tannarx_oracle.py` (19).


### 10b–10d — To'liq tannarx, stanok soati, asbob (tig'), kromka, OEE yo'qotishi pulda

Moliya → **Tannarx** (`/tannarx/buyurtmalar`, `/tannarx/oee-yoqotish`, normalar — `stanok_narx`, `asbob_stavka`):

- **To'liq (boshqaruv) tannarx** = material (FIFO sarf) + kromka + mehnat + stanok + asbob; summa, foyda, marja.
  Narxi yozilmagan stanok/amal — qatorda «narxi yo'q», tannarxi umuman yo'q buyurtmada marja ko'rsatilmaydi.
- **Kromka** sexga rulonda beriladi (2510) va buyurtma tannarxida yo'q edi: endi rezervdagi kromka
  `kerak − berilgan` × oxirgi partiya narxi (`ombor.service.kromka_normasi`).
- **Stanok** — Prisadka/Rover skanlarining IDEAL sikl vaqti (OEE Performance formulasi) × soat narxi. Buyurtmaga
  faqat ideal vaqt; yo'qotilgan vaqt — OEE yo'qotishida.
- **Asbob (tig')** — norma × amal: teshik, qirra teshigi, paz, freza (`xnc_summary`), Rover kontur metri, kromka
  metri, arra m². Brak tasdiqlab bekor qilingan skan ham sanaladi (stanok va asbob baribir ishlagan).
- **OEE yo'qotishi pulda** — har stanok: to'xtash (reja − ishladi), sekin (ishladi − ideal), brak
  (ideal × brak/detal) × soat narxi; asosiy rejasiz to'xtash sabablari pulda.
- Stanok va asbob normasi **buxgalteriyaga yozilmaydi**: haqiqiy puli (asbob xaridi, elektr) allaqachon
  xarajat/2510 da — normani provodka qilish ikki marta sanash bo'lardi. Narxlar o'tgan sanaga ham yoziladi.
- «Jarayonda» — yetkazilmagan, lekin skani bor buyurtmalarning yig'ilib borayotgan tannarxi.
- OEE yo'qotishi faqat stanokdan ma'lumot kelgan kunlar bo'yicha: MES hisobotida ma'lumotsiz vaqt «o'chiq»
  sanaladi, lekin stanok o'rnatilmagan / Pico ulanmagan kunlar pulli yo'qotish emas (necha kun chiqarilgani
  ko'rsatiladi). MES ning o'z OEE hisobotida bunday kunlar uchun `oee_start_date` sozlamasi bor.
- Orakllar: `tannarx_oracle.py` (26), `oee_pul_oracle.py` (4, `oee_oracle` ssenariysi ustida).

Ochiq: kromka mashina vaqti (lenta tezligi skanda yo'q — hozir kromka metri normasi bilan), asbob resursini
haqiqiy almashtirishlardan hisoblash, ikkinchi Prisadka uchun alohida ideal sikl.

### 11 — Interfeys: dunyo ERP'lari bilan solishtirish (2026-10-30)

G2, Capterra, TrustRadius, Software Advice sharhlari (SAP B1/Fiori, NetSuite, Business Central, Odoo, Acumatica,
Zoho, 1C, Katana, MRPeasy) bo'yicha eng ko'p shikoyat: kerakli joyni topib bo'lmaydi (chuqur menyu, ko'p klik,
yomon qidiruv), ortiqcha to'la ekranlar, tushunarsiz xatolar; maqtov: rolga moslangan ekran, sodda va bir xil
interfeys. Bizda bajarilgani:
- **Ctrl+K umumiy qidiruv** (`components/Common/CommandPalette.tsx`, sidebar'da «Qidirish… Ctrl K»): sahifalar,
  Moliya / Soliq / Buxgalteriya bo'limlari (`lib/bolimlar.ts` — tablar bilan bir manba), buyurtma raqami yoki mijoz,
  ombor tovari (kod/nom). Ro'yxat rolga qarab — menyuda yo'q sahifa qidiruvda ham yo'q (`NAV_ITEMS`).
- **Rolga moslangan menyu:** kassir va moliyachida tsex TV ekranlari (LIVE Tablo, Stanoklar) yo'q.
- **Qaytarib bo'lmaydigan amaldan oldin bir xil savol** (`components/Common/useTasdiq.tsx` → `ConfirmDialog`): oy yopish,
  vedomost tasdiqlash / bekor, ESF yuborish / bekor, kiruvchi ESF qabul, provodka storno — oqibati matnda yoziladi.
- **Ikki kalit ekranda ham:** vedomost muallifiga «Tasdiqlash» o'rniga «boshqa xodim tasdiqlaydi» (`yaratgan_id`).
Keyingi navbat (qilinmadi): ro'yxatlarda saqlanadigan filtrlar, kassir uchun planshet ko'rinishi.

### 11c — Jadval va pul formati (butun tizim)

- **Jadval — Excel kabi to'r** (`components/ui/table.tsx`, hamma jadval shu komponentdan): har katak vertikal chiziq
  bilan ajraladi; o'ngga tekislangan (pul, son) ustunlar kontent kengligida (`w-px` + `nowrap`), bo'sh joyni matn
  ustuni oladi; raqamlar `tabular-nums` — ustun bo'ylab bir tekis.
- **Pul tiyingacha:** `formatSum` / `formatMoney` (`lib/mes.ts`) → `1 234 567,89 so'm` (minglik — bo'shliq, kasr —
  vergul). Ilgari butunga yaxlitlanardi — hisobotlar yig'indisi qatorlardan farq qilishi mumkin edi. Omborda pul
  uchun `fmtSum` (`lib/warehouse.ts`), `fmt` faqat son/dona uchun qoldi. Backend xabarlari (`kassa._som`,
  `rezerv._som`) ham tiyingacha.

### 11b — Hisobot qatoridan buyurtmaga o'tish (moliya buyurtma kartasi)

Moliyachi ishlab chiqarish sahifasini (`/orders`) ko'rmaydi, shuning uchun buyurtma pul tomonidan ochiladi:
`GET /moliya/buyurtma/{order_id}` (direktor, moliyachi; faqat o'qish) → summa, to'langan (kassagacha + kassa orderlari
taqsimot bo'yicha), qarz, ESF lar (bekor qilinganlari ham), material (FIFO) + mehnat = tannarx, foyda. Raqamlar
P&L, `kassa.jami_tolangan` va soliq ro'yxati bilan bir manbadan (`kassa.buyurtma_tolovlari`, `soliq.buyurtma_esflari`).
Ekranda: `components/Moliya/BuyurtmaKarta.tsx` — o'ng panel, `_layout` da bitta; `BuyurtmaHavola` bosilsa ochiladi.
Havola bor joylar: Moliya → Orderlar jurnali, Tannarx, Soliq → Chiquvchi ESF (manba ustuni). Foyda faqat topshirilgan
buyurtmada ko'rsatiladi (P&L kabi). Ishlab chiqarish rollari (direktor) uchun panelda buyurtma sahifasiga havola bor.
ESF holat belgisi `components/Common/EsfHolat.tsx` ga ko'chdi (Soliq sahifasi bilan bir manba).
Orakl: `scripts/oracles/buyurtma_karta_oracle.py` — ruxsat (kassir 403), 404, P&L tannarx/foyda, to'lovlar yig'indisi,
qarz, ESF bog'lanishi.
