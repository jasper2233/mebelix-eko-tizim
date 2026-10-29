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
| 3e MX Kroy: katalog sinxroni (K5), MX bo'lagi ↔ ATX yorlig'i, ortiqchani qaytarish | navbatda | |
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

