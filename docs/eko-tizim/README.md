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
