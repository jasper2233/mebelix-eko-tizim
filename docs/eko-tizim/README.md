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
| 2.3b Tablodan material so'rash, qoldiq bo'laklari, TMO | navbatda | |

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

