# Backend Core — konfiguratsiya, DB, xavfsizlik, middleware, worker

Bu hujjat MebeliX MES backend'ining yadro (core) qatlamini tavsiflaydi: ilova qanday quriladi (application factory), sozlamalar qayerdan o'qiladi, ma'lumotlar bazasi va Redis ulanishlari qanday boshqariladi, autentifikatsiya kriptografiyasi, so'rovlarni loglash va fon vazifalar (background jobs) infratuzilmasi.

Umumiy arxitektura oqimi:

```
backend/app/main.py
  └── create_application(router)                  # core/setup.py
        ├── Settings (env → pydantic)             # core/config.py
        ├── lifespan: gc.freeze + perf.lag_monitor + perf.flush_loop + Redis pool'lar + WS pub/sub listener + DB probe   # core/setup.py, core/ws.py, core/perf.py, core/health.py
        ├── RequestLoggingMiddleware              # core/middleware.py
        ├── CORSMiddleware, ProxyHeadersMiddleware
        ├── Prometheus /metrics
        └── env-shartli /docs, /redoc, /openapi.json
```

## Fayllar ro'yxati

| Fayl | Vazifasi |
|---|---|
| `backend/app/main.py` | Ilova kirish nuqtasi — `app` obyektini yaratadi |
| `backend/app/core/__init__.py` | Bo'sh package marker |
| `backend/app/core/coalesce.py` | `Coalesced` — hamma uchun bir xil og'ir o'qishni ishchida bir vaqtda BITTA hisoblash; hisob davomida kelganlar keyingisini birga kutadi, javob so'rov kelganidan eski bo'lmaydi (`GET /tablo/matrix`) |
| `backend/app/core/config.py` | Barcha sozlamalar (`Settings`) + production xavfsizlik validatori |
| `backend/app/core/db.py` | Async SQLAlchemy engine, session factory, `Base` model |
| `backend/app/core/exceptions.py` | Umumiy HTTP exception klasslari (o'zbekcha xabarlar bilan) |
| `backend/app/core/health.py` | DB va Redis health-check funksiyalari (`/ready`) va startup probe'lari (lifespan, arq worker) |
| `backend/app/core/logger.py` | JSON formatdagi structured logging (stdout) |
| `backend/app/core/middleware.py` | `X-Request-ID` + so'rov loglash middleware'i; «Tizim holati» uchun so'rov davomiyligini route shabloni bilan yozadi va ishlayotgan so'rovlarni ro'yxatga oladi (`core/perf.py`) |
| `backend/app/core/perf.py` | «Tizim holati» o'lchovlari Redis'da, ikkala gunicorn ishchisidan umumiy: `mes:perf:req` (so'rovlar, 100 000 ≈ 12 soat), `mes:perf:lag` (event loop bloklari, 2 000), `mes:perf:print` (chek kechikishi, 10 000) — LTRIM bilan cheklangan; yozuv xotiradagi buferga, `flush_loop` soniyada bir paket; `record_request`, `record_delivered`, `finish`, `lag_monitor` (muzlash yozuvida shundan GC vaqti — `gc_ms`), `read_window` |
| `backend/app/services/system_health.py` | «Tizim holati» tahlili: oyna o'qish (qamrov bilan), endpoint guruhlari, sekin so'rovning muzlashga to'g'ri kelgan ulushi (pid + vaqt), chek navbatlari, TOPILMALAR (tayyor o'zbekcha jumlalar) va chegaralar — sahifa ham, yon menyu belgisi ham shu yagona manbadan |
| `backend/app/core/security.py` | bcrypt parol hash, JWT token, httpOnly cookie'lar |
| `backend/app/core/setup.py` | Application factory, lifespan, metrics, docs |
| `backend/app/core/worker.py` | arq background worker konfiguratsiyasi |
| `backend/app/core/ws.py` | Real-time ko'prik — WebSocket fan-out + Redis pub/sub (`WsManager`) |
| `backend/app/core/utils/__init__.py` | Bo'sh package marker |
| `backend/app/core/utils/queue.py` | arq Redis pool uchun global holder |
| `backend/app/core/utils/rate_limit.py` | Redis asosidagi rate limiting (`RateLimiter`, `RateLimit`) |
| `backend/app/tasks/__init__.py` | arq'ga ro'yxatga olinadigan vazifalar (`print_label`, `print_pachka_label`, `print_waste_label`, `print_badge`) + `PRINT_QUEUE_KEY`, `print_queue_key()`, `agent_revoked_key()`, `bridge_conn_key()`, `AGENT_ONLINE_WINDOW`/`agent_online()`, `printer_agent()`, `require_printer()`/`NoPrinterBound`, `printing_agents()` |

---

## `backend/app/main.py`

**Maqsadi:** butun backend'ning kirish nuqtasi. Bor-yo'g'i 4 qator: `app.api`dagi yagona `router`ni olib `create_application()` factory'siga uzatadi (`settings` factory ichida modul darajasida import qilinadi).

```python
app = create_application(router=router)
```

**Bog'lanishlar:** `backend/app/api/__init__.py` (router), `backend/app/core/config.py`, `backend/app/core/setup.py`. Uvicorn shu `app` obyektini ishga tushiradi.

---

## `backend/app/core/config.py`

**Maqsadi:** ilovaning barcha sozlamalari — bitta yassi (flat) `Settings` klass (`pydantic_settings.BaseSettings`). Qiymatlar repo ildizidagi `.env` fayldan yoki environment variable'lardan o'qiladi (`case_sensitive=True`, `extra="ignore"`).

**Muhim elementlar:**

- `EnvironmentOption` (StrEnum): `LOCAL` / `STAGING` / `PRODUCTION` — docs ko'rinishi, cookie `secure` flag va production validatsiya shu qiymatga bog'liq.
- `Settings` — bo'limlarga `# === Section ===` kommentlar bilan ajratilgan sozlamalar guruhi:

| Guruh | Asosiy maydonlar |
|---|---|
| Application | `APP_NAME` (FastAPI `title`), `APP_VERSION` (FastAPI `version` + `/health` va `/ready` hisobotida) — description/license/contact sozlamalari olib tashlangan, metadata `setup.py`da literal yoziladi |
| Crypto / JWT | `SECRET_KEY: SecretStr`, `ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7`, `DEVICE_REFRESH_TOKEN_EXPIRE_DAYS=90` (qurilma sessiyasi — monoblok/TABLO tsexda klaviatura yo'q, qayta parol termaydi; token har ishlatilganda yangilanadi, uzun muddat esa uzoq to'xtashdan keyin ham qayta kirish kerak bo'lmasligi uchun), `BCRYPT_ROUNDS=12` |
| PostgreSQL | `POSTGRES_USER/PASSWORD/SERVER/PORT/DB`, `POSTGRES_ASYNC_PREFIX="postgresql+asyncpg://"`, `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20` |
| First admin | `ADMIN_NAME/PHONE/USERNAME/PASSWORD` — startup'da yaratiladigan birinchi admin |
| Redis | `REDIS_HOST`, `REDIS_PORT` — navbat ham, rate limit ham, WS pub/sub ham, «Tizim holati» ro'yxatlari (`mes:perf:*`, `core/perf.py` o'z klienti bilan) ham shu bitta Redis'ga boradi (yoqish/o'chirish bayroqlari yo'q) |
| Rate limit | `LOGIN_RATE_LIMIT_ATTEMPTS=5`/`LOGIN_RATE_LIMIT_PERIOD=300` — faqat parol bilan kirish uchun sozlanadi; boshqa cheklovlar kodda qat'iy (beyjik bilan kirish 30/60 s, ochiq `/public` 3D havola 60/300 s), umumiy default'lar yo'q |
| Pagination | `DEFAULT_PAGE_SIZE=50`, `MAX_PAGE_SIZE=100` |
| File storage | `UPLOAD_DIR="uploads"` (project/scx/label fayllar ildizi,; nisbiy yo'l `backend/` paket ildiziga nisbatan), `MAX_PROJECT_FILE_SIZE` = 50 MB |
| Production floor | `STRICT_STAGE_ORDER=True` (E004 — oldingi qadam tugamaguncha skanni bloklash,; tartib postlarning global ketma-ketligidan emas, detalning O'Z marshrutidagi `seq` bo'yicha, chunki nostandart marshrut roverdan ham boshlanishi mumkin), `SCAN_UNDO_SECONDS=60` (BEKOR QILISH oynasi) |
| Printing | `BRIDGE_TOKEN=""` — **legacy**, ixtiyoriy: eski agentlar uchun umumiy token, u faqat `/ws/bridge` handshake'idan o'tkazadi (bunday agent chek OLMAYDI). Printerlar endi per-agent pairing orqali ulanadi (`bridge_agent` jadvali), shuning uchun bu sozlama bo'sh qolganda ham chop etish ishlaydi. Yorliqlar faqat shu navbat orqali USB GoDEX'ga boradi (G500-U'da tarmoq porti yo'q), shuning uchun printer manzili sozlamasi yo'q |
| Startup probes | `STARTUP_RETRY_MAX_ATTEMPTS=5`, `STARTUP_RETRY_DELAY_SECONDS=2` |
| Threadpool | `THREADPOOL_TOKENS=100` (AnyIO sync-bridge slotlari) |
| Reverse-proxy | `FORWARDED_ALLOW_IPS=["172.16.0.0/12"]` — X-Forwarded-* ga ishoniladigan upstream (compose tarmog'i). **`*` QO'YILMAYDI**: unda uvicorn XFF'ning eng CHAP, ya'ni mijoz bergan qiymatini oladi va login rate-limiti header almashtirish bilan aylanib o'tiladi (o'lchandi: 12 urinishdan 0 tasi bloklandi) |
| Env / CORS | `ENVIRONMENT`, `CORS_ORIGINS=["http://localhost:5173"]`, `CORS_METHODS`, `CORS_HEADERS` |

- Computed field'lar: `POSTGRES_URI` (`user:pass@host:port/db`) va `REDIS_URL` (`redis://host:port`). `POSTGRES_URI` da `POSTGRES_USER` va `POSTGRES_PASSWORD` `urllib.parse.quote(..., safe="")` bilan percent-encode qilinadi (band belgili parol DSN'ni buzmasin); `POSTGRES_DB` xom qoladi — SQLAlchemy baza komponentini unquote qilmaydi. Shu sababli `migrations/env.py` `set_main_option` ga berishdan oldin `%` ni ikkilantiradi (configparser uni interpolatsiya deb o'qiydi).
- Modul darajasidagi eksportlar: `TASHKENT_TZ = ZoneInfo("Asia/Tashkent")` — tsex mahalliy vaqti, hisobot/audit kunlari va chek timestamp'lari shu zonada (`audit.py`, `machines.py`, `reports.py`, `scans.py`, `tablo.py`, `terminal.py` (E012 xabaridagi chek vaqti), `orders/_common.py` route'lari, `crud/orders.py`, `services/andon.py`, `services/availability.py`, `services/excel.py`, `services/labels.py`, `services/scanning.py`, `services/system_health.py` va `tasks/__init__.py` ishlatadi); `upload_root()` — `UPLOAD_DIR`ning absolyut `Path` ildizi. Nisbiy `UPLOAD_DIR` jarayon CWD'siga emas, `backend/` paket ildiziga (`Path(__file__).resolve().parents[2]`) bog'lanadi — ombor xizmat qayerdan ishga tushirilganiga qarab surilmasligi uchun; absolyut qiymat o'zgarishsiz ishlatiladi. Uni yettita route moduli import qiladi: `orders/files.py`, `orders/survey.py`, `orders/lifecycle.py` (o'chirishda fayllarni unlink qiladi), `orders/bazis.py`, `orders/matrix.py`, `public.py`, `terminal.py`; hamda `commands/rebuild_bazis_models.py`. `services/giblab/ingest.py` esa `config`dan import qilmaydi — ildizni `upload_root: Path` PARAMETRI sifatida oladi, qiymatni `orders/files.py` va `orders/matrix.py` (`root = upload_root()`; matritsa tahririda `rebuild_order_scx`/`purge_replaced_scx` ga) uzatadi.
- `_validate_production_settings(s)` — **har qanday non-LOCAL muhitda (STAGING ham, PRODUCTION ham) xavfsiz bo'lmagan default'lar bilan boot qilishni rad etadi** (faqat LOCAL o'tkazib yuboriladi): `SECRET_KEY`, `ADMIN_PASSWORD`, `POSTGRES_PASSWORD`, `ADMIN_PHONE` placeholder qiymatda qolgan bo'lsa YOKI `FORWARDED_ALLOW_IPS` ichida `*` bo'lsa `RuntimeError` ko'taradi (`*` app-level `ProxyHeadersMiddleware` orqali gunicorn'ning qat'iy `--forwarded-allow-ips` flagini bekor qiladi va rate-limit bypass'ini qaytarib ochadi). Modul import bo'lganda darhol ishlaydi (birinchi so'rovda emas, startup'da).
- Modul oxirida global singleton: `settings = Settings()`.

**Bog'lanishlar:** deyarli barcha core modullar (`db.py`, `security.py`, `setup.py`, `worker.py`) va API qatlami shu `settings` obyektini import qiladi.

---

## `backend/app/core/db.py`

**Maqsadi:** async SQLAlchemy infratuzilmasi — engine, session factory va ORM base klass.

**Muhim elementlar:**

- `Base(DeclarativeBase, MappedAsDataclass)` — barcha ORM modellar uchun ota klass; `MappedAsDataclass` modellarni dataclass qiladi.
- `DATABASE_URL = POSTGRES_ASYNC_PREFIX + POSTGRES_URI` — asyncpg driver bilan to'liq URL.
- `async_engine = create_async_engine(...)` — `pool_size`/`max_overflow` `settings`dan, `pool_pre_ping=True` (uzilgan ulanishlarni avtomatik aniqlaydi), `echo=False`.
- `local_session = async_sessionmaker(..., expire_on_commit=False)`.
- `async_get_db()` — FastAPI dependency sifatida ishlatiladigan async generator:

```python
async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with local_session() as db:
        yield db
```

**Bog'lanishlar:** `config.py`dan `settings`; `health.py` engine'ni startup probe (`check_database_connection`) uchun import qiladi; API endpointlari `async_get_db`ni `Depends` orqali oladi; ORM modellar `Base`dan meros oladi.

---

## `backend/app/core/exceptions.py`

**Maqsadi:** loyihada qayta ishlatiladigan HTTP exception klasslari. Barchasi FastAPI `HTTPException`dan meros oladi va default `detail` xabarlari **o'zbek tilida**.

| Klass | Status | Default detail |
|---|---|---|
| `NotFoundException` | 404 | "Topilmadi" |
| `ForbiddenException` | 403 | "Ruxsat berilmagan" |
| `UnauthorizedException` | 401 | "Tizimga kirilmagan" (+ `WWW-Authenticate: Bearer` header) |
| `DuplicateValueException` | 409 | "Takroriy qiymat" |
| `RateLimitException` | 429 | "So'rovlar chegarasidan oshib ketdi." |

**Bog'lanishlar:** `utils/rate_limit.py` (`RateLimitException`), auth dependency'lari va CRUD qatlamlari shu klasslarni ishlatadi.

---

## `backend/app/core/health.py`

**Maqsadi:** DB va Redis tirikligini tekshiruvchi funksiyalar — `/ready` endpointi uchun ham, lifespan va arq worker startup probe'lari uchun ham. Probe'lar ilgari `setup.py`da edi — arq worker bitta `SELECT 1` uchun butun ilova-fabrikasini (prometheus, uvicorn middleware, `app.api.deps`) import qilishga majbur bo'lardi, shuning uchun shu yerga ko'chirildi.

- `check_database_health(db: AsyncSession) -> bool` — `SELECT 1` bajaradi; xato bo'lsa log yozib `False` qaytaradi.
- `check_redis_health() -> bool` — lifespan ochadigan **ikkita** Redis klientni (`queue.pool` va `rate_limiter.client`) `ping()` qiladi; ro'yxat bo'sh bo'lsa (masalan lifespan'gacha) tekshiruv "vacuously" muvaffaqiyatli hisoblanadi (`True`). WS pub/sub klienti (lifespan'da alohida ochiladigan `ws_redis`) va `/ws/bridge` ichidagi per-ulanish klienti bu tekshiruvga kirmaydi — ya'ni `/ready` real-time kanal holatini qamramaydi.
- `redis_clients()` — lifespan egalik qiladigan Redis klientlar ro'yxati (`queue.pool`, `rate_limiter.client`; `None` bo'lganlari tashlab ketiladi); startup probe ham, `/ready` ham shundan o'qiydi.
- `_retry_async(label, fn)` — startup probe'lar uchun retry helper: `STARTUP_RETRY_MAX_ATTEMPTS` (5) marta urinadi, orasida `STARTUP_RETRY_DELAY_SECONDS` (2s) kutadi; `CancelledError`/`KeyboardInterrupt` darhol yuqoriga uzatiladi.
- `check_database_connection()` — engine orqali `SELECT 1` probe (retry bilan); `setup.py` lifespan'i va arq worker (`worker.py`, `startup`) chaqiradi.
- `check_redis_connection()` — `redis_clients()`ni ping qiladi (retry bilan) va qaysilari tekshirilganini logga yozadi; lifespan chaqiradi.

**Bog'lanishlar:** `config.py` (`settings`), `db.py` (`async_engine`), `utils/queue.py`, `utils/rate_limit.py`; `check_database_health`/`check_redis_health`ni faqat `/api/v1/ready` endpointi chaqiradi (`routes/health.py`) — `/api/v1/health` esa sof liveness probe: hech qanday bog'liqlikni tekshirmaydi, doim 200 va statik payload qaytaradi (prod'dagi konteyner healthcheck'i aynan shu pathga uradi). Ikkala path `setup.py`dagi `NON_BUSINESS_PATHS`da ham ro'yxatga olingan.

---

## `backend/app/core/logger.py`

**Maqsadi:** 12-factor uslubidagi structured JSON logging — process o'zi log fayl yozmaydi, hamma narsa stdout'ga bir qatorli JSON sifatida chiqadi.

- `JsonFormatter(logging.Formatter)` — har bir log record'ni `{"timestamp", "level", "logger", "message"}` + mavjud bo'lsa `_EXTRA_FIELDS` (`request_id`, `method`, `path`, `status_code`, `duration_ms`) va `exc_info` bilan JSON'ga aylantiradi.
- `setup_logging()` — argumentsiz, daraja qat'iy INFO; root logger handlerlarini stdout JSON handler bilan **almashtiradi** (`root.handlers = [handler]`). Import-time side-effect yo'q — har bir uzoq yashovchi entrypoint uni **explicit** chaqiradi: `create_application()` (`setup.py`) va arq worker (`core/worker.py`, modul yuklanishida). `app/commands/` dagi uchala CLI komanda (`seed_defaults.py`, `create_first_superuser.py`, `rebuild_bazis_models.py`) esa oddiy `logging.basicConfig(level=INFO)` bilan kifoyalanadi.

- `ARQ_LOG_DICT` — arq CLI'ga `--custom-log-dict app.core.logger.ARQ_LOG_DICT` orqali uzatiladigan dictConfig: `arq` loggerini handlersiz qoldirib `propagate: True` qiladi. arq o'z dictConfig'ini `setup_logging()`dan **keyin** qo'llagani uchun (CLI avval `WorkerSettings`ni import qiladi), busiz har bir `arq.*` yozuvi ikki marta chiqadi — o'zining plain-matn handleri va root JSON handleri orqali.

**Bog'lanishlar:** `middleware.py` yozadigan `extra` maydonlar aynan `_EXTRA_FIELDS` bilan mos keladi; `setup.py` va `worker.py` `setup_logging`ni chaqiradi; `ARQ_LOG_DICT`ni ikkala compose faylidagi worker komandasi ishlatadi.

---

## `backend/app/core/middleware.py`

**Maqsadi:** har bir so'rovga `X-Request-ID` biriktirish, tugagach structured log yozish va «Tizim holati» o'lchovini (`core/perf.py`) berish.

- `REQUEST_ID_HEADER = "X-Request-ID"`.
- `RequestLoggingMiddleware(BaseHTTPMiddleware)`:
  - Klientdan kelgan `X-Request-ID`ni qabul qiladi, bo'lmasa `uuid4().hex` yaratadi va javob header'iga qo'shadi.
  - `NON_BUSINESS_PATHS`dagi pathlar (`/metrics`, health/ready) **loglanmaydi** — faqat header qo'shiladi. (Circular import oldini olish uchun `NON_BUSINESS_PATHS` `dispatch` ichida local import qilinadi.)
  - Boshqa so'rovlar uchun `time.perf_counter()` bilan davomiylik o'lchanadi va `logger.info("request", extra={request_id, method, path, status_code, duration_ms})` yoziladi — bu `logger.py`dagi `JsonFormatter` orqali JSON bo'lib chiqadi.
  - **«Tizim holati»:** `call_next` dan oldin so'rov `perf.inflight` ga yoziladi (NOM FUNKSIYASI va boshlanish; nom — "METOD /yo'l", aks holda bir yo'ldagi GET va PATCH bitta endpoint bo'lib ko'rinardi), `finally` da `perf.finish` uni olib «yaqinda tugaganlar» ga (`perf.recent`) qo'yadi — event loop bloki so'rov OXIRIDA bo'lsa ham aybdor topilsin. Nom muzlash paytida hisoblanadi: routingdan keyin — route shabloni (`/orders/{order_id}`), undan oldin — xom yo'l. Ilgari xom yo'l yozilardi va u endpoint jadvalidagi shablonga mos kelmasdi (bitta endpoint id'lar bo'yicha bo'linib sanalardi). Javobdan keyin `perf.record_request(method, route shabloni, ms, status)`. Shablon (`_route_template`): `scope["route"].path` ichki routerning o'z yo'li, ota prefikslarsiz (`/{order_id}/matrix`) — u haqiqiy yo'lning OXIRI, prefiks haqiqiy yo'ldan olinadi; qiymat bo'yicha almashtirilmaydi (`/orders/5/files/5`). Route topilmasa (404) — `(topilmadi)`.
  - Handler ushlanmagan istisno tashlasa, `call_next` `try/except BaseException` ichida: xuddi shu `extra` (lekin `status_code=500`) bilan `logger.exception("request")` yoziladi, «Tizim holati» ga ham 500 bo'lib yoziladi va istisno yuqoriga qayta uzatiladi. Ya'ni 500'lar ham `request_id` va `duration_ms` bilan strukturali logda ko'rinadi (javob header'ini Starlette'ning xato ishlovchisi shakllantirgani uchun unda `X-Request-ID` bo'lmaydi; korrelatsiya log orqali).

**Bog'lanishlar:** `setup.py` (`create_application` uni ro'yxatga oladi, `NON_BUSINESS_PATHS` shu yerdan), `logger.py`, `perf.py` (`inflight`, `finish`, `record_request`).

## `backend/app/core/perf.py`

**Maqsadi:** «Tizim holati» sahifasining (`GET /system/perf`, `docs/03`) manbasi — server tezligini o'zi o'lchab boradi. 2026-09-26 da tsexdagi 5–10 soniyalik kutish sababi (bitta so'rov ishchining event loop'ini ~7 s CPU bilan band qilib, o'sha ishchidagi HAMMA so'rovni kuttirgan) loglardan qo'lda qidirilgan edi.

- Yozuvlar Redis ro'yxatlarida, ikkala gunicorn ishchisidan umumiy, `LPUSH` + `LTRIM`: `mes:perf:req` (`vaqt|METHOD|route|ms|status|pid`, 100 000 — 2026-09-26 dagi eng band soat 6 456 so'rov, shu sur'atda 12 soat 77 ming; ~7 MB), `mes:perf:lag` (JSON, 2 000), `mes:perf:print` (`vaqt|agent|soniya`, 10 000). pid — muzlashni aynan O'SHA ishchidagi so'rovlar bilan solishtirish uchun; pid qo'shilgan deploydan oldin yozilgan qatorlarda yo'q (o'qish 5 va 6 maydonni qabul qiladi, bunday qatorlar muzlash bilan solishtirilmaydi va sahifa buni aytadi). Klient modul darajasida, birinchi ishlatilganda ochiladi (`client()`, timeout 2 s — Redis javob bermasa flush osilib qolmaydi).
- Yozish so'rovni kuttirmaydi va yiqitmaydi: qator xotiradagi buferga qo'shiladi (`_add`, bufer ham `*_KEEP` bilan cheklangan), `flush_loop` soniyasiga bir marta HAMMA buferni bitta Redis paketida yozadi; lifespan to'xtaganda oxirgi `flush()`. Ilgari har so'rov o'z fon vazifasi va Redis round-trip'ini ochardi. A/B o'lchov (haqiqiy middleware, 9 000 so'rov, lokal Redis): eski usul har so'rovga +295 µs, bufer +3,7 µs; yozuvlar soni to'liq mos (hech biri yo'qolmagan). Evaziga ishchi qulasa oxirgi ≤1 s o'lchov yo'qoladi.
- `read_window(key, since, ts_of)` — ro'yxatni 2 000 lik bo'laklab o'qiydi va oyna boshidan eski yozuvga yetganda to'xtaydi (narxi oynaga bog'liq, ro'yxat hajmiga emas); vaqtni faqat bo'lak chegarasida tekshiradi. Ikki ishchi paketlarini alohida yozgani uchun ro'yxat vaqt bo'yicha qat'iy tartibda emas — `ORDER_SLACK_S` (60 s) ortig'i bilan o'qiladi, aniq kesishni `services/system_health.py` qiladi. Natija `Slice(items, exhausted, trimmed)`: ro'yxat oyna boshiga yetmay tugadimi va LTRIM kesganmi — sahifa qisman qamrovni shundan aytadi.
- `lag_monitor()` — har ishchida lifespan boshlaydi: har 50 ms uyg'onadi, 200 ms dan kech uyg'onsa «muzlash» deb yozadi. Bu event loop KECHIKISHI: bitta uzun hisob ham, ketma-ket ko'p qisqa ishlar ham beradi (sinov: 12 ta 30 ms lik vazifa bitta 310 ms yozuv berdi) — sahifa ham shunday ta'riflaydi. Yozuv o'sha oraliqda kamida bir qadam (50 ms) ishlagan so'rovlar bilan (hali ishlayotganlar va shu oraliqda tugaganlar; kechikish ichida boshlangani ham kiradi, monitor uyg'onishidan bir zum oldin kelgan «0 ms» so'rov kirmaydi — u kechikishni kutmagan) (eng uzoq ishlayotgani birinchi — EHTIMOLIY aybdor: blok paytida qaysi vazifa CPU'da bo'lganini monitor bilmaydi; lokal sinovda yagona CPU-og'ir so'rov katta JSON'li POST edi, lekin 8 muzlashdan bittasida birinchi bo'lib boshqa so'rov (`/tablo/matrix`) turgan). Prod uvloop ishlatadi, ya'ni asyncio callback'larini o'lchab aniq aybdorni topish usuli u yerda ishlamaydi. Qadam — o'lchov xatosi: 0,5 s qadamda 0,6 s blok 204 ms deb yozilgani sinovda ushlangan.
- Har muzlash yozuvida `gc_ms` — shu oynada Python GC yig'imlariga ketgan vaqt. `lag_monitor` ishlab turganda `gc.callbacks` kumulyativ hisoblagichni oshirib boradi, monitor uyqudan oldingi va keyingi farqni oladi (har yig'imni ro'yxatda saqlamaydi — xotira O(1), uzun muzlashda ham tushib qolmaydi). Oyna uyquni ham o'z ichiga oladi, shuning uchun qiymat kechikishdan oshmaydigan qilib kesiladi; xatosi kechikishning o'zi kabi ±50 ms. GC GIL ostida ishlaydi — qaysi oqimda bo'lmasin loop'ni to'xtatadi, hammasi sanaladi. Nega kerak: 2026-09-27 da qolgan qisqa muzlashlarning bir qismi GC ekani faqat alohida probe'da ko'rindi, jonli ishchida ko'rinmasdi. 2026-09-27 dan oldingi yozuvlarda maydon yo'q (`None`, sahifada «—»). Lokal tekshiruv: `gc.collect()` 155 ms bo'lgan 300 ms blokda `gc_ms` 155, GC'siz 313 ms blokda 0.
- `record_delivered(agent_id, job)` — `/ws/bridge` ack'dan keyin chaqiradi: job'dagi `queued_at` dan hozirgacha (`tasks._print_job`); `queued_at` siz eski job va tanitilmagan agent o'lchanmaydi.
- Narxi (lokal o'lchov): `lag_monitor` — 30 s da 31 ms CPU (bitta yadroning 0,1% i); «Tizim holati» o'qish+tahlili 60 ming yozuvli 12 soatlik oynada ~0,2 s devor vaqti, loop'ni bir yo'la ≤47 ms band qiladi (qatorlar 5 000 lik bo'laklarda parse qilinib, orasida loop'ga navbat beriladi; Windows taymeri ~15,6 ms qadamli — bu yuqori chegara). Sekin so'rov ↔ muzlash ustma-ustligi pid bo'yicha saralangan ro'yxatda `bisect` bilan topiladi: ilgari har so'rov har muzlash bilan solishtirilardi va yomon kunda tahlilning o'zi bloklardi (4 000 sekin so'rov × 1 000 muzlash — 749 ms), endi 11 ms (10 000 × 2 000 — 15 ms).

**Bog'lanishlar:** `middleware.py`, `setup.py` (lifespan), `api/routes/ws.py`, `services/system_health.py`, `config.py`.

## `backend/app/core/coalesce.py`

**Maqsadi:** foydalanuvchiga bog'liq bo'lmagan va ko'p mijoz bir paytda so'raydigan og'ir o'qishni ishchida bir vaqtda BITTA hisoblash. Hozir yagona ishlatuvchi — `GET /tablo/matrix` (`docs/03`).

- `Coalesced(fn)` — `await coalesced()` `fn()` natijasini qaytaradi. Birinchi chaqiruv hisobni boshlaydi; hisob ketayotganda kelganlar o'sha hisobga QO'SHILMAYDI — keyingi bitta hisobni birga kutadi, u ular kelgandan KEYIN boshlanadi. Demak javob hech qachon so'rov kelishidan oldingi holatni ko'rsatmaydi: skandan keyin so'ragan ekran o'sha skanni ko'radi. Oddiy «tayyor natijani ulash» yoki TTL kesh buni kafolatlamaydi — ekran skandan oldingi matritsani olib, keyingi pollgacha (60 s) eski qolardi.
- Xato o'sha hisobni kutganlarning hammasiga boradi, keyingi chaqiruv yangidan hisoblaydi; kutuvchi bekor qilinsa (mijoz uzildi) hisob va boshqa kutuvchilar davom etadi (`asyncio.shield`); ishchi to'xtab runner bekor qilinsa joriy VA keyingi hisobni kutayotganlarning hammasi bekor bo'ladi — osilib qolmaydi (keyingisini birinchi versiya unutgan edi, bajarib tekshirilganda ushlandi).
- Faqat ishchi ICHIDA. Ikki ishchi uchun umumiy (Redis) hisob ATAYLAB yo'q: prodda ikki jarayon aynan bir soniyada hisoblaganda muzlash yakka hisobdagidek chiqdi (loop max: ikki jarayonda 195 va 195 ms, yakka 187 ms; ≥200 ms — hech birida), ya'ni ular bir-birini sekinlatmaydi (15 tadan hisob — kichik tanlama).
- O'lchov (2026-09-27, prod API konteynerida ishchiga o'xshash jarayon — uvloop, haqiqiy lag monitori, FastAPI javob serializatsiyasi; 3 takror × 55 so'rov, bir ishchida 1/2/4 talik to'dalar, to'da ichida 4 ms oraliq): ≥200 ms muzlash 20 → 7, `gc.freeze` bilan birga 2; javob p95 ~800 → ~500 ms (~430 ms); eski javob — 0. Lokal tekshiruv haqiqiy ilova orqali: 8 ta bir vaqtdagi so'rov → 2 hisob, javob to'g'ridan-to'g'ri hisob bilan bir xil; hisob paytida commit qilingan yozuvni keyin kelgan so'rov ko'rdi.

**Bog'lanishlar:** `api/routes/tablo.py`.

---

## `backend/app/core/security.py`

**Maqsadi:** autentifikatsiya kriptografiyasi — parol hashlash (bcrypt), JWT token yaratish/tekshirish va httpOnly auth cookie'lar.

**Muhim elementlar:**

- Konstantalar: `ACCESS_COOKIE_NAME = "access_token"`, `REFRESH_COOKIE_NAME = "refresh_token"`; `TokenType` (StrEnum): `ACCESS` / `REFRESH`.
- Parollar:
  - `_bcrypt_bytes(password)` — parolni UTF-8'ga o'girib `BCRYPT_MAX_BYTES = 72` baytga kesadi. bcrypt algoritmi 72 baytdan keyingi qismni baribir hisobga olmaydi, bcrypt 5.0.0 esa uzun parolni jimgina kesmasdan `ValueError` otadi (`hashpw` ham, `checkpw` ham). Kesish **bitta joyda** — hash yo'li ham, verify yo'li ham shu helperdan o'tadi; sxemaga `max_length` qo'yish yetmasdi, chunki login `OAuth2PasswordRequestForm`dan o'tadi (unda sxema yo'q, ya'ni uzun parol autentifikatsiyasiz 500 berardi). Bu chekka holat emas: kirill harflari 2 bayt bo'lgani uchun 40 belgili parol ham chegaradan oshadi. Mavjud hash'lar ≤72 baytdan yasalgani uchun kesish eski parollarni buzmaydi.
  - `verify_password(plain, hashed)` — **async**: `bcrypt.checkpw` `run_in_threadpool` orqali bajariladi (bcrypt CPU-bound, event loop'ni bloklamaslik uchun).
  - `get_password_hash(password)` — **async**: hashlash (`_hash_password_sync`, `BCRYPT_ROUNDS`=12) `run_in_threadpool` orqali bajariladi — 12 round ~250ms olgani uchun event loop'ni bloklamasligi kerak.
- JWT:
  - `_create_token(data, token_type, expires_delta)` — payload'ga `exp` va `token_type` qo'shib `HS256` bilan imzolaydi.
  - `create_access_token(data)` — `ACCESS_TOKEN_EXPIRE_MINUTES` (30 daqiqa); `create_refresh_token(data, days=None)` — `days` berilmasa `REFRESH_TOKEN_EXPIRE_DAYS` (7 kun), berilsa o'sha muddat: `routes/login.py` qurilma akkauntlariga (`UserRole.TERMINAL` / `UserRole.TABLO`) `days=settings.DEVICE_REFRESH_TOKEN_EXPIRE_DAYS` (90 kun) uzatadi. Refresh token payload'iga unikal `jti` (`uuid4().hex`) qo'shiladi — har bir refresh token unikal bo'ladi va bir marta rotation'dan keyin "ishlatilgan" deb belgilash mumkin.
  - `verify_token(token, expected_token_type, *, verify_exp=True) -> TokenData | None` — decode qiladi, `sub` mavjudligini va `token_type` mosligini tekshiradi; `sub` **int `user_id`** sifatida parse qilinadi (parse bo'lmasa `None`) va natijada `TokenData(user_id, token_version, jti)` qaytadi — `token_version` (default 0) token bekor qilish (revocation) mexanizmi uchun, `jti` esa refresh tokenning bir martalik (one-time-use) nazorati uchun (access tokenlarda `None`). `verify_exp=False` — faqat imzo/tur tekshiriladi, muddat emas; `routes/ws.py` ochiq soketni bekor qilinganlik (`token_version`, `is_active`) bo'yicha qayta tekshirishda (`deps.resolve_user(..., verify_exp=False)` orqali) ishlatadi — kun bo'yi ochiq tablo/terminal soketi 30 daqiqalik access muddati bilan uzilmasin.
- Cookie'lar:
  - `set_auth_cookie(response, key, value, max_age)` — `httponly=True`, `samesite="strict"` (klassik CSRF vektorini neytrallaydi), `secure` faqat non-LOCAL muhitlarda (muhit solishtiruvi `set_auth_cookie` ichida, alohida helper yo'q), local'da oddiy HTTP ustida ishlashi uchun o'chirilgan.
  - `clear_auth_cookies(response)` — ikkala cookie'ni o'chiradi (logout).
  - **Uchinchi httpOnly cookie — `terminal_device` (chek qurilmasi) — bu modulda EMAS.** Uni `services/terminal_device.py: set_device_cookie(response, token)` yozadi. Bayroqlar auth cookie'lari bilan bir xil (`httponly=True`, `samesite="strict"`, `secure` faqat non-LOCAL'da — solishtiruv o'sha funksiya ichida takrorlangan), muddati esa `DEVICE_COOKIE_MAX_AGE` = 400 kun (Chrome cookie muddatini 400 kun bilan cheklaydi). Ikki joyda yoziladi: `POST /api/v1/terminal-devices/pair` (bir martalik kod tokenga almashganda) va `GET /api/v1/terminal/context` (cookie ish markazining ulangan qurilmasiga mos kelsa har ochilishda qayta yoziladi — ishlab turgan monoblokda muddati tugamaydi). Bazada faqat sha256 xeshi (`terminal_device.token_hash`). `clear_auth_cookies` uni o'chirmaydi: logout'dan keyin ham monoblok "ulangan qurilma" bo'lib qoladi; ulanishni admin "yangi kod" yoki "o'chirish" bilan bekor qiladi (tasks bo'limidagi «Chek qurilmasi» bandi).

**Bog'lanishlar:** `config.py` (`settings`, `EnvironmentOption`), `backend/app/schemas/auth.py` (`TokenData`); auth endpointlari va `api/deps.py` shu funksiyalarni ishlatadi.

---

## `backend/app/core/setup.py`

**Maqsadi:** application factory va startup/shutdown hayot sikli. FastAPI ilovasini metadata, middleware, metrics va env-shartli docs bilan yig'adi.

**Muhim funksiyalar:**

- `set_threadpool_tokens()` — AnyIO thread-pool hajmini `THREADPOOL_TOKENS`ga ko'taradi (bloklovchi chaqiriqlar navbatda turib qolmasligi uchun).
- `lifespan(app)` — modul darajasidagi `@asynccontextmanager` (pool ochish/yopish alohida wrapper funksiyalarsiz, shu yerda inline): threadpool → `gc.collect()` + `gc.freeze()` (import paytidagi ~216 ming doimiy obyekt GC'ning to'liq yig'imidan chiqadi: prodda har yig'im ~120 ms loop to'xtashi edi, keyin 3–18 ms; monitor'dan OLDIN — bir martalik yig'im muzlash bo'lib yozilmasin) → `perf_tasks` = `perf.lag_monitor()` + `perf.flush_loop()` (har gunicorn ishchisi o'z loop'ini o'lchaydi va o'lchovni soniyada bir Redis'ga yozadi, «Tizim holati») → arq navbat pool (`queue.pool = await create_pool(...)`) + `rate_limiter.initialize(settings.REDIS_URL)` + ping → **WS real-time ko'prik**: alohida Redis klient ochilib `ws_manager.start_listener(...)` ishga tushiriladi (`core/ws.py`) → DB probe → `yield` → `finally`da `perf_tasks` bekor qilinib oxirgi `perf.flush()` yoziladi, WS listener to'xtatiladi, WS Redis klienti, `queue.pool` va `rate_limiter.client` yopiladi. Hech qanday shart yo'q — Redis ilovaning majburiy bog'liqligi, ko'tarilmasa startup probe'da yiqiladi.
- `_install_docs_router(application)` — docs siyosati:
  - **production**: docs umuman yo'q;
  - **staging**: `/docs`, `/redoc`, `/openapi.json` faqat superuser uchun (`Depends(get_current_superuser)`);
  - **local**: ochiq.
  - `/openapi.json` handleri `application.openapi()` qaytaradi — title/description/version metadata'dan tushadi va sxema birinchi so'rovdan keyin keshlanadi.
- `create_application(router) -> FastAPI` — asosiy factory:
  1. `setup_logging()` — JSON logging shu yerda faollashadi (import side-effect emas).
  2. FastAPI metadata — `title` `settings.APP_NAME`dan, `version` `settings.APP_VERSION`dan, `description` (`"MebeliX API"`) esa literal (settings'dan emas; `license_info` yo'q — repo litsenziyasiz); **built-in docs har doim o'chiriladi** (`docs_url=None` va h.k.) — o'rniga shartli router o'rnatiladi.
  3. Modul darajasidagi `lifespan` bilan `FastAPI(...)` yaratadi va berilgan `router`ni ulaydi.
  4. Middleware'lar: `RequestLoggingMiddleware`, `CORSMiddleware` (`allow_credentials=True` — cookie-auth uchun zarur; `expose_headers=["Content-Disposition"]` — cross-origin dev'da Excel eksporti fayl nomini o'qiy olsin), `ProxyHeadersMiddleware` (`FORWARDED_ALLOW_IPS` bilan) — busiz `request.client.host` har doim proxy IP bo'lib, barcha foydalanuvchilar bitta rate-limit bucket'iga tushib qolardi.
  5. `_install_metrics()` va `_install_docs_router()`.
- `NON_BUSINESS_PATHS = ["/metrics", "/api/v1/health", "/api/v1/ready"]` — metrics'dan ham, access-log'dan ham chiqarib tashlanadigan pathlar (yagona manba — single source of truth).
- `_install_metrics(application)` — `prometheus_fastapi_instrumentator` orqali `/metrics` endpoint (gzip, schema'da ko'rinmaydi). Endpoint autentifikatsiyasiz, shuning uchun prod'da Caddy uni tashqariga UMUMAN chiqarmaydi: `handle /metrics` har doim 403 qaytaradi (`caddy/Caddyfile`) — ilgarigi `remote_ip private_ranges` matcher olib tashlangan, chunki Caddy host-nginx ortida turgani uchun har bir tashqi so'rov ham private range'dan kelgandek ko'rinardi. Metrikalarga faqat compose tarmog'i ichidan, to'g'ridan-to'g'ri `api:8000/metrics` orqali borish mumkin; repoda scraper (Prometheus/Grafana) xizmatining o'zi yo'q.

**Bog'lanishlar:** `config.py`, `health.py` (`check_database_connection`, `check_redis_connection`), `logger.py` (`setup_logging`), `middleware.py`, `ws.py` (`ws_manager`), `utils/queue.py`, `utils/rate_limit.py`, `perf.py` (`lag_monitor`, `flush_loop`, `flush`), `backend/app/api/deps.py` (`get_current_superuser`); bu modulni `main.py` ishlatadi (`middleware.py` esa `NON_BUSINESS_PATHS`ni local import qiladi).

---

## `backend/app/core/worker.py`

**Maqsadi:** arq background worker konfiguratsiyasi — fon vazifalarni (background tasks) Redis navbati orqali bajaradigan alohida process. `arq app.core.worker.WorkerSettings --custom-log-dict app.core.logger.ARQ_LOG_DICT` komandasi bilan ishga tushiriladi (bayroq haqida: `logger.py` → `ARQ_LOG_DICT`).

**Muhim elementlar:**

- Modul yuklanishida `uvloop` event loop policy o'rnatiladi (Linux/macOS; Windows'da `ImportError` jim o'tkaziladi) va `setup_logging()` chaqiriladi — worker protsessi ham app protsessidagidek JSON log yozadi.
- `startup(ctx)` — worker startida `check_database_connection()` probe'ni bajaradi (retry bilan).
- `shutdown(ctx)` — log yozadi.
- `WorkerSettings` klassi:

```python
class WorkerSettings:
    functions = all_tasks                      # backend/app/tasks dan
    # harakatsiz smenalarni yopish (10 daq) va Pico to'xtashlarini yozish (5 daq) — 04-backend-data.md §6
    cron_jobs = [
        cron(close_idle_sessions, minute=set(range(0, 60, IDLE_SWEEP_MINUTES))),
        cron(sync_downtimes, minute=set(range(0, 60, DOWNTIME_SWEEP_MINUTES))),
    ]
    redis_settings = RedisSettings(host=..., port=...)
    on_startup = startup
    on_shutdown = shutdown
    # arq defaulti 3600s: yangi ko'tarilgan worker soat davomida "sog'lom" yozuvini
    # yangilamasdi va `arq ... --check` healthcheck'i yiqilardi
    health_check_interval = 30
    # handle_signals default (True) — docker stop'da SIGTERM to'g'ri ushlanadi
```

- `handle_signals` endi o'rnatilmaydi (default `True`): `docker stop`da SIGTERM to'g'ri ushlanib, bajarilayotgan joblar tugatiladi yoki qayta navbatga qo'yiladi.

**Bog'lanishlar:** `config.py`, `health.py` (`check_database_connection`), `logger.py` (`setup_logging`), `backend/app/tasks/__init__.py` (`all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`, cron `close_idle_sessions`, `sync_downtimes`). Web-process `utils/queue.py`dagi pool orqali vazifalarni shu worker navbatiga qo'yadi.

### `backend/app/tasks/__init__.py` — ro'yxatga olingan vazifalar

- `PRINT_QUEUE_KEY = "mes:print:queue"` — kalit prefiksi; manzilsiz kalitning o'zi endi o'qilmaydi. `print_queue_key(agent_id)` esa
  manzilli kalitni beradi: doim `mes:print:queue:{agent_id}` (`agent_id` majburiy; ilgari `None` berilsa umumiy
  kalitga tushardi, uni hech kim o'qimagani uchun job "queued" deb jimgina yo'qolardi).
  Chek SO'RAGAN ish markazining printeriga borishi uchun shunday: `ws.py` ulangan agent uchun
  `brpop([o'z kaliti], timeout=5)` qiladi — FAQAT o'ziga atalgan kalitdan oladi, umumiy
  `PRINT_QUEUE_KEY` ATAYLAB o'qilmaydi. Ack kelmasa job AYNAN kelgan kalitiga (`src_key`) qaytariladi.
- `agent_revoked_key(agent_id)` — `mes:agent:revoked:{agent_id}`, bekor qilingan agent bayrog'i
  (TTL 10 daqiqa). `bridge_agents.py` uni qo'yadi, `/ws/bridge` har brpop iteratsiyasida o'qiydi.
- `bridge_conn_key(agent_id)` — `mes:bridge:conn:{agent_id}`, agentning ENG OXIRGI `/ws/bridge` ulanishi
  id'si (TTL 10 daqiqa). `/ws/bridge` uni ulanishda yozadi, yopilishda o'qiydi — «uzildi» hodisasi (pastda).
- `require_printer(db, machine_id)` — chek qaysi agentga ketishini ANIQ aytadi, agent biriktirilmagan bo'lsa `NoPrinterBound` (chaqiruvchi 422 beradi, chek YUBORILMAYDI); `terminal.py` va `pachka.py`
  navbatga qo'yishdan OLDIN aynan shuni chaqiradi. `printing_agents(db)` — beyjik uchun tanlov ro'yxati.
  `printer_agent(db, machine_id)` — shu ish markaziga bog'langan, `can_print=True`, juftlangan
  (`token_hash` bor) va o'chirilmagan agentni topadi (`require_printer` ichida ishlatiladi;
  xato bilan ikkita agent bog'langan bo'lsa tanlov DETERMINISTIK: eng yangi `last_seen_at`, so'ng eng katta `id`).
  **Onlaynlik tanlashda TEKSHIRILMAYDI** — offline agent ham qaytadi va chek uning navbatida kutadi
  (bu xato emas). `AGENT_ONLINE_WINDOW` (6 daqiqa) / `agent_online(last_seen_at)` faqat CHAQIRUVCHIDA:
  «Printer ulanmagan. Chek saqlandi — printer ulanganda o'zi chiqadi: {qr_text}» xabarini (atxot chekida —
  «Printer ulanmagan. Atxot cheki saqlandi — printer ulanganda chiqadi: {qr_text}») va terminal
  header'idagi agent holatini shu chegara hal qiladi (frontend `agents.tsx` bilan aynan bir xil oyna).
  `employees.py` dagi beyjik chop etishda ish markazi yo'q, shuning uchun printer
  ATAYLAB tanlanadi: `agent_id` query parametri, berilmasa — chop eta oladigan
  yagona agent, bir nechta bo'lsa 422 va ro'yxat.

  **Umumiy `PRINT_QUEUE_KEY` endi ISHLATILMAYDI.** Har chek aniq agentga
  manzillanadi, `ws.py` esa faqat o'z kalitini o'qiydi. Aynan umumiy navbat
  "ofisdagi test printeri tsexdagi chekni tortib oldi" nuqsonini bergan edi:
  kim birinchi `BRPOP` qilsa, chek o'shanikiga chiqardi.
- **Navbatga qo'yishdan OLDINGI yana ikki to'siq (endpoint'da, vazifada emas).**
  1. *Chek qurilmasi (E011).* `print_instance_label`, `print_waste_item_label` (`terminal.py`) va
     `close_pachka` (`pachka.py`) `require_printer`dan oldin, hech narsa yozilmasdan
     `services/terminal_device.py: require_print_device(db, request, user, machine)` ni chaqiradi.
     Ish markazida kamida bitta ULANGAN (`token_hash` bor, o'chirilmagan) `terminal_device` bo'lsa,
     so'rov shulardan birining `terminal_device` cookie'sini olib kelishi SHART. Aks holda: rollback,
     audit-log (`module="print"`, `action="device_rejected"`, `meta` da user-agent), commit,
     so'ng E011 (`scan_error` → 422 `{code, message}`), chek YUBORILMAYDI. Ulangan qurilmasi yo'q ish
     markazida cheklov yo'q; kodi berilgan, lekin hali kiritilmagan qurilma ham cheklovni yoqmaydi.
     Ish markazi aniqlanmasa (`machine is None`) tekshiruv o'tkazib yuboriladi — `require_printer(None)`
     baribir 422 beradi. Chekni BEKOR QILISH (`cancel_instance_label`, `cancel_waste_item_label`) ham
     tsex hisobida shu tekshiruvdan o'tadi (ofis — menejer/texnolog/admin — `_is_office` bilan chetlab
     o'tadi): aks holda telefon chekni bekor qilar, monoblok esa o'sha nusxaga ikkinchi, bir xil chek chiqarardi (E012 faqat BEKOR QILINMAGAN chekni himoya qiladi). Faqat chek chiqarish va bekor qilish to'siladi: skan, xarita, smena
     telefondan ham ishlaydi.
  2. *Bir nusxa — bir chek (E012).* Detal va atxot chekida `terminal.py: _claim_label` `label_printed_at` ni
     atomik `UPDATE ... WHERE id=? AND label_printed_at IS NULL RETURNING id` bilan band qiladi.
     0 qator qaytsa E012 («Bu chek allaqachon chiqarilgan (dd-mm HH:MM)…», vaqt `TASHKENT_TZ` da)
     va job navbatga QO'YILMAYDI. Ikki parallel so'rovda ikkinchisining UPDATE'i birinchisining commit'ini
     kutadi va 0 qator oladi. Qayta chiqarish faqat `label_printed_at` tozalangandan keyin: bekor
     qilish (`DELETE /terminal/labels/{instance_id}`, `DELETE /terminal/waste/{waste_id}/label`) yoki
     menejer tasdiqlagan, kesish postidan qayta ochilgan brak (`services/defects.py: reopen_from_step`).
  Beyjik (`employees.py` → `print_badge`) ikkala to'siqdan ham o'tmaydi.
- `print_label(ctx, instance_id, agent_id)` — yorliq chiqarish vazifasi (`agent_id` majburiy, standart qiymati yo'q — agentni unutgan chaqiruvchi `TypeError` oladi).
  Bitta DB sessiyasida (`local_session`) `services/labels.py`dan:
  - `load_label_data(db, instance_id)` — `None` bo'lsa `"skip:{id}"` qaytarib chiqadi;
  - `render_label_png(data)` — o'sha yorliqning 80×60 mm / 203 dpi rasteri; `base64` bilan kodlanadi.

  **Nega PNG:** GoDEX G500-U USB bilan ishlaydi va bridge-agent uni Windows drayveri (GDI) orqali chizadi — PNG printer dialektiga bog'liq emas.

  So'ng arq context'idagi Redis (`ctx["redis"]`) orqali `LPUSH print_queue_key(agent_id)`, job JSON:
  `{"type": "print", "job_id", "instance_id", "png"[, "queued_at"]}` (`png` — base64 PNG; `queued_at` — arq
  `ctx["enqueue_time"]` unix soniyada, bo'lsa qo'shiladi; `/ws/bridge` ack'da chek kechikishini o'lchaydi,
  agent noma'lum maydonni e'tiborsiz qoldiradi). `job_id` — har
  yuborishda yangi `uuid4().hex`: agent takror yetkazilgan jobni aynan shu kalit bo'yicha tashlaydi
  (`SEEN_JOBS`). Natija `"queued:{id}"`. Redis mavjud bo'lmasa — xato loglanadi, `"lost:{id}"`.
- Qolgan uchta vazifa AYNAN shu zanjirdan o'tadi (`_print_job` + `LPUSH print_queue_key(agent_id)`,
  `skip:`/`queued:`/`lost:` natijalari) — faqat render qilinadigan ma'lumot boshqacha:
  - `print_pachka_label(ctx, pachka_id, agent_id)` — qadoq cheki (`render_pachka_label_png`;
    buyurtma raqami, loyiha nomi, qadoqdagi detallar soni). `pachka.py` qadoq yopilganda qo'yadi
    (`close_pachka` eng avval `require_print_device` ni chaqiradi — E011 bo'lsa qadoq yopilmaydi, ochiq qoladi).
  - `print_waste_label(ctx, waste_id, agent_id)` — FOYDALI ATXOT cheki (`render_waste_label_png`;
    `ATX-` prefiksli QR, material, o'lcham, list raqami). `terminal.py` dagi
    `POST /terminal/waste/{waste_id}/label` qo'yadi (avval `require_print_device` — E011); `label_printed_at` ni
    ENDPOINT yozadi (`_claim_label` — band bo'lsa E012 va job qo'yilmaydi), vazifa emas —
    aks holda javob bilan yozuv orasida poyga bo'lib, kesish xaritasidagi katak darhol yangilanmasdi.
  - `print_badge(ctx, employee_id, agent_id)` — hodim beyjigi (`render_badge_png`). `employees.py`
    qo'yadi; brauzerdan chop etish o'rniga shu yo'l, chunki brauzer drayverdagi saqlangan qog'oz
    o'lchamiga tayanardi va 80×60 bo'lmasa kontent yorliqqa sig'masdi.

  `_print_job(ref_id, png_b64, queued_at)` ni `_enqueue` `ctx.get("enqueue_time")` bilan chaqiradi — to'rttala
  chop etish vazifasi `queued_at` bilan ketadi.
  Job JSON'dagi maydon nomi hamma vazifada `instance_id` (`_print_job` umumiy) — qadoq, atxot va
  beyjikda u mos ravishda `pachka_id`, `waste_id`, `employee_id` qiymatini olib yuradi; agent uni
  faqat log uchun ishlatadi, chop etish `png` bilan bo'ladi.

**To'liq zanjir:**

```
terminal → POST /api/v1/terminal/labels/{instance_id}
  → require_print_device(db, request, user, machine)            ← holat o'zgarishidan OLDIN
     (ish markazida ulangan terminal_device bor-u, cookie mos kelmasa: rollback +
     audit-log print/device_rejected + commit → E011 → 422, chek YUBORILMAYDI)
  → _claim_label: UPDATE part_instance SET label_printed_at, label_post_id
     WHERE id=? AND label_printed_at IS NULL RETURNING id (hali commit qilinmagan;
     0 qator → E012 → 422, chek YUBORILMAYDI)
  → require_printer(db, machine_id) → shu ish markazining printeri
     (biriktirilmagan bo'lsa NoPrinterBound → 422, chek YUBORILMAYDI)
  → queue.pool.enqueue_job("print_label", instance_id, agent_id)   ← commit'dan OLDIN
  → db.commit() → ws_manager.publish("label.printed", ...)         ← eng oxirida
  → arq worker: render_label_png → LPUSH mes:print:queue:{agent_id}
  → /ws/bridge (per-agent token auth; faqat juftlangan (agent_id bor) va can_print=True
     agent BRPOP qiladi; brpop([o'z kaliti]); ack talab qilinadi, ack kelmasa src_key ga
     RPUSH bilan qaytariladi; ack kelgach perf.record_delivered → mes:perf:print — chek kechikishi)
  → bridge-agent → print-queue.jsonl (durable) → Windows GDI (_print_png_gdi) → USB GoDEX G500-U
```

Bridge-agent faqat printer ulangan kompyuterga o'rnatiladi va yorliq printerini nomidan o'zi topadi (`_detect_printer` — nomida `godex`/`xprinter`/`gprinter`/`tsc`/`zebra`/`argox`/`postek` bor birinchi Windows printeri; tsexda GoDEX ham, Xprinter ham bor); `PRINTER_NAME` env faqat qo'lda override uchun. Tsexdagi kompyuterda `mebelix-agent.exe` (PyInstaller onefile) ishlaydi — Python ham, pip ham, serverdagi `.env` tahriri ham kerak emas. Menejer, texnolog va boshqa terminallarga hech narsa o'rnatilmaydi — ular brauzerdan tugmani bosadi. Istisno: ish markaziga chek qurilmasi (`terminal_device`) ULANGAN bo'lsa, o'sha ish markazining cheki faqat ulangan brauzerdan (postning monoblokidan) chiqadi — boshqa qurilmadan, masalan shaxsiy hisob bilan kirilgan telefondan, bosilgan tugma E011 oladi (quyida «Chek qurilmasi» bandi). Chekning PNG rasmi (`GET /terminal/labels/{instance_id}.png`) ham faqat ofisga: `require_roles(MANAGER, TEXNOLOG)` (admin/superuser o'zi o'tadi), terminal va post hisoblari 403 oladi — aks holda telefondagi rasm istalgan printerdan chiqarilib, E011 va E012 aylanib o'tilardi.

**`/ws/bridge` autentifikatsiyasi — per-agent pairing.** Admin panel har bir printerli kompyuter uchun 8 belgili bir martalik ulanish kodi beradi (alifboda I/L/O/0/1 yo'q — telefonda aytganda adashtirmaydi; TTL 15 daqiqa; generator — `bridge_agents.py: new_pair_code()` + `PAIR_TTL`, chek qurilmalari (`terminal_devices.py`) ham aynan shularni import qiladi). Agent birinchi ishga tushganda kodni ochiq `POST /api/v1/bridge-agents/pair` endpointi orqali doimiy tokenga almashtiradi; bazada tokenning faqat sha256 xeshi qoladi (`bridge_agent.token_hash`, unikal) — token o'zi bir marta, pair javobida beriladi.

Ulanishda token `Authorization: Bearer` headerda keladi (server access-loglariga tushmasligi uchun; `?token=` query eski agentlar uchun fallback). Tekshiruv tartibi: avval legacy `settings.BRIDGE_TOKEN` bilan `secrets.compare_digest` orqali solishtiriladi, mos kelmasa token sha256'si bo'yicha `bridge_agent` jadvalidan qidiriladi; topilmasa socket `WS_CLOSE_UNAUTHORIZED` (4401) bilan yopiladi. Handshake'dagi `X-Agent-Version` header agent exe versiyasi sifatida saqlanadi. Ulanish davomida har 300 soniyada `touch_agent()` ishlaydi — `last_seen_at`ni yangilaydi (paneldagi "Ulandi"), `version`ni yozadi va `can_print`ni qayta o'qiydi (admin belgini o'zgartirsa ~5 daqiqada kuchga kiradi). **Bekor qilish esa deyarli DARHOL kuchga kiradi:** `bridge_agents.py` "yangi kod"/"o'chirish"da `agent_revoked_key(agent_id)` Redis bayrog'ini 10 daqiqaga qo'yadi, `/ws/bridge` esa uni HAR brpop iteratsiyasida o'qiydi — kechikish ≤ ~5 s. Ilgari yagona tekshiruv o'sha 300 soniyalik `touch_agent()` edi va bekor qilingan token shu vaqt davomida chek olib chop etaverardi (prod-repro bilan o'lchangan: 295 s); endi `touch_agent()` — zaxira tekshiruv: agent qatori yo'q bo'lsa yoki `token_hash` almashgan bo'lsa u ham 4401 bilan uzadi. Ikkala yo'lda ham qo'lda turgan job `rpush` bilan AYNAN kelgan kalitiga qaytariladi — yo'qolmaydi.

**Istisno — agentni O'CHIRISH.** `DELETE /api/v1/bridge-agents/{agent_id}` `_revoke_live_connection(..., purge_queue=True)` chaqiradi: bayroqdan tashqari u `llen` bilan sanab `print_queue_key(agent_id)` kalitini butunlay `delete` qiladi, ya'ni o'sha agentning navbatidagi HAMMA chek ATAYLAB bekor qilinadi va javobda «Navbatdagi N ta chek bekor qilindi» deb aytiladi. Sabab: har chek aniq agentga manzillangan — o'chirilgan agentning navbatini endi hech kim o'qimaydi va kalit jimgina abadiy qolardi.

Ulanish/uzilish/pairing panelga `bridge.connected` / `bridge.disconnected` / `bridge.paired` eventlari bilan (`ws_manager.publish`) tarqatiladi — admin "MES agentlar" sahifasi pollingsiz yangilanadi. **`bridge.disconnected` ni faqat agentning ENG OXIRGI ulanishi chiqaradi** (`ws.py: _bridge_gone`): har ulanish `bridge.connected` dan oldin o'z id'sini `bridge_conn_key` ga yozadi; yopilganda kalitda boshqa id tursa (agent allaqachon qayta ulangan) hodisa yuborilmaydi. Sabab (prod 2026-10-03): qayta ulangan agentning eski yarim-ochiq soketini server 20–40 s kech yopadi (uvicorn ping'i), terminal esa oxirgi kelgan hodisaga ishonadi — eski soketning «uzildi» si yangi ulanishning «ulandi» sidan keyin kelib, «MES agent uzilgan» chipi qizilda qotib qolardi, agent esa ishlab turardi. Tekshiruv bilan e'lon orasiga yangi ulanish kirib ulgursa, «uzildi» dan keyin «ulandi» takrorlanadi (nazariy istisno: yangi ulanish ham o'sha oynada — ikki Redis so'rovi oralig'i, ~1–2 ms — yopilib ulgursa, takror noto'g'ri bo'ladi). Legacy umumiy token va Redis xatosida hodisa avvalgidek chiqadi. Logdagi iz: `Bridge ulandi: agent=… conn=…`, `Bridge ulanishi yopildi: agent=… conn=… sabab=…`, `… yangiroq ulanish bor, «uzildi» hodisasi yuborilmadi`.

**Skan-forvard va printersiz stansiyalar.** `bridge_agent.machine_id` agentni ish markaziga bog'laydi: stanok skaneri o'qigan QR agent orqali `POST /api/v1/bridge-agents/scan` endpointiga (agent tokeni bilan) yuboriladi va bog'langan ish markazining terminalidagi AKTIV sessiya nomidan odatdagi skan yo'li bilan yoziladi. `can_print=False` agent (masalan, Nanxing skan-forvard stansiyasi — printeri yo'q) ulanib turadi, lekin chek OLMAYDI: BRPOP o'rniga 5s uxlaydi — aks holda chekni "o'g'irlab" lokalida qoldirardi. Shart aslida IKKITA (`if can_print and own_keys`): `own_keys` bo'sh bo'lgani uchun legacy umumiy `BRIDGE_TOKEN` bilan ulangan agent (`agent_id is None`) ham HECH QACHON chek olmaydi — u qaysi ish markazi ekani noma'lum, unga chek berish yana o'sha tasodif bo'lardi. Ya'ni legacy token faqat WS handshake'dan o'tkazadi: chop etish uchun ham, skan-forvard uchun ham (`/bridge-agents/scan` juftlangan tokenni talab qiladi) yaroqsiz. Ikkala maydonni admin `PATCH /api/v1/bridge-agents/{agent_id}` bilan boshqaradi (endpoint tafsilotlari: `docs/03-backend-api.md`).

**Bog'liq fayllar (core'dan tashqarida):** `backend/app/models/bridge_agent.py` (`bridge_agent` jadvali: `organization_id`, `name`, `token_hash`, `pair_code`, `pair_expires_at`, `last_seen_at`, `machine_id` (FK `machine.id`, skan-forvard), `version` (agent exe versiyasi), `can_print` (default `True`)), migratsiyalar `d5e81a24c3b7` (pairing), `f4b8c2a91e55` (machine), `a7c3e9d12f04` (version), `d4f7a8c25e91` (can_print), `backend/app/crud/__init__.py` (`crud_bridge_agents` — `BaseCRUD[BridgeAgent]`, o'z moduli yo'q), `backend/app/schemas/bridge_agents.py`, `backend/app/api/routes/bridge_agents.py`.

**Chek qurilmasi (`terminal_device`) — chek chiqarishni post monoblokiga bog'lash.** Terminal hisobi odamga bog'langan: `resolve_terminal` postni roldan, ish markazini hisobdan oladi. Shuning uchun arrachi shaxsiy hisobi bilan telefondan kirganda ham chek ARRA printeridan chiqardi — 2026-09-24 da bitta nusxaning ikki bir xil cheki ikki xil detalga yopishtirilgan. Ulanish `bridge_agent` naqshida:
1. Admin `/agents` sahifasining ikkinchi bo'limida qurilma yaratadi (`POST /api/v1/terminal-devices/`, `machine_id` majburiy) va 8 belgili bir martalik kod oladi (`new_pair_code()`, 15 daqiqa).
2. Postning monoblokida terminal header'ida «Qurilmani ulash» tugmasi chiqadi (`TerminalContext.print_pairing` — ish markazida kodi amal qilayotgan qurilma bor). Kod `POST /api/v1/terminal-devices/pair` ga yuboriladi: endpoint `TerminalUser` + `TerminalCtx` talab qiladi, ya'ni kod faqat chaqiruvchining O'Z ish markazidagi qurilmada ishlaydi (atomik `UPDATE ... WHERE machine_id=? ... RETURNING`; aks holda 400, kod boshqa ish markaziniki bo'lsa o'sha ish markazi nomi aytiladi). `paired_at` va `paired_user_agent` saqlanadi — admin panelda qurilma turi (telefon/kompyuter) shundan ko'rinadi.
3. Javobda token YO'Q — u faqat httpOnly `terminal_device` cookie'sida (yuqorida `core/security.py` bandi).

Tekshiruv `services/terminal_device.py: print_device()` da. Cheklov yoqilgan = ish markazida kamida bitta ulangan, o'chirilmagan qurilma bor; cookie xeshi `hmac.compare_digest` bilan solishtiriladi. Qurilmaning `last_seen_at` i daqiqasiga ko'pi bilan bir marta yangilanadi (`touch_device`, `_SEEN_EVERY`). Kodni qayta berish (`POST /terminal-devices/{device_id}/code`) eski tokenni darhol bekor qiladi (`token_hash`, `last_seen_at`, `paired_at`, `paired_user_agent` tozalanadi); o'chirish (`DELETE /terminal-devices/{device_id}`, soft delete) ham. Ish markazining yagona ulangan qurilmasi shunday ketsa cheklov qayta ulanguncha o'chadi — `DELETE` javobi buni aytadi. Terminal kontekstida `print_lock` / `print_allowed` / `print_device_name` / `print_pairing` maydonlari bor: `print_lock && !print_allowed` bo'lsa header qizil «Chek chiqmaydi» belgisini ko'rsatadi, chek tugmalari esa yashirilmaydi — to'siq serverda (E011). Admin paneli va terminal pollingni kutmasdan darhol yangilanadi (`terminal_device.code` / `terminal_device.paired` / `terminal_device.deleted` eventlari, `machine_id` bilan; admin ro'yxatida 30 s polling faqat zaxira).

**Bog'liq fayllar:** `backend/app/models/terminal_device.py` (`terminal_device` jadvali: `organization_id`, `name`, `machine_id` (FK `machine.id`, NOT NULL), `token_hash` (unikal), `pair_code`, `pair_expires_at`, `last_seen_at`, `paired_at`, `paired_user_agent`), migratsiya `b3e7c5a90d14`, `backend/app/crud/__init__.py` (`crud_terminal_devices`), `backend/app/schemas/terminal_devices.py`, `backend/app/api/routes/terminal_devices.py` (5 ta endpoint: 4 tasi admin, `pair` — terminal), `backend/app/services/terminal_device.py`.

---

## `backend/app/core/ws.py`

**Maqsadi:** real-time ko'prik — WebSocket klientlarga event fan-out. Gunicorn worker'lari aro tarqatish Redis pub/sub `mes:events` kanali orqali amalga oshadi (har bir worker faqat o'z lokal socketlarini ko'radi, kanal orqali hammasi bir xil eventni oladi).

**Muhim elementlar:**

- `WsClient` (dataclass) — bitta ulanish: `socket`, `scope` (`"terminal"` / `"tablo"` / `"dashboard"`) va ixtiyoriy `post_id`/`machine_id` filtrlar. `wants(event)` — dashboard VA TABLO hamma eventni oladi; target'siz eventlar broadcast; terminal faqat o'z `post_id`/`machine_id`siga mos eventlarni oladi. TABLO ataylab filtrsiz: u devor ekrani va BUTUN tsex matritsasini ko'rsatadi, qurilma hisobi esa majburan bitta ish markaziga bog'langan — filtr qolsa taxta faqat o'z postining skanlarini jonli ko'rardi.
- `WsManager` (modul-darajali singleton `ws_manager`):
  - `connect(client)` / `disconnect(client)` — lokal klientlar ro'yxatini boshqaradi (`accept` + qo'shish / olib tashlash).
  - `publish(event_type, payload, **targets)` — event quradi (`{"type", "payload"}` + `post_id`/`machine_id` target'lar) va Redis mavjud bo'lsa `mes:events` kanaliga `PUBLISH` qiladi; Redis yo'q (dev) yoki yiqilgan bo'lsa **lokal yetkazishga degradatsiya** qiladi (`_dispatch`).
  - `_dispatch(event)` — `wants()`ga mos klientlar ro'yxatning **snapshot'idan** (`list(self.clients)`) yig'iladi (jonli ro'yxat ustida yurish xavfli: `send_json` await'i paytida uzilgan mijoz `disconnect()` bilan ro'yxatni siljitar va keyingi ulangan mijoz event'ni jimgina olmay qolardi), so'ng ularga `asyncio.gather(..., return_exceptions=True)` bilan **parallel** `send_json` qilinadi; xato qaytargan **o'lik socketlar ro'yxatdan tozalanadi**. Fan-out ataylab parallel: ketma-ket await'da bitta qotib qolgan mijoz qolgan hamma mijozni ham, pub/sub tinglovchi siklini ham to'sib qo'yardi.
  - `start_listener(redis)` / `stop_listener()` — lifespan boshqaradigan pub/sub listener task: `mes:events`ga subscribe bo'lib, kelgan xabarlarni `_dispatch`ga uzatadi; shutdown'da unsubscribe + cancel. Redis uzilishi task'ni O'LDIRMAYDI: xato logga yozilib, `_RESUBSCRIBE_SECONDS` (2 s) dan keyin qayta obuna bo'ladi — ilgari faqat `CancelledError` ushlanardi va bitta tarmoq uzilishi workerlar aro fan-out'ni jimgina to'xtatardi.

**Bog'lanishlar:** `setup.py` (lifespan listener'ni ishga tushiradi/to'xtatadi), `backend/app/api/routes/ws.py` (WebSocket endpointlar klientlarni ro'yxatga oladi); mutatsiya qiluvchi API endpointlar `ws_manager.publish(...)` orqali event yuboradi.

---

## `backend/app/core/utils/queue.py`

**Maqsadi:** arq Redis pool uchun minimal global holder — 3 qator:

```python
pool: ArqRedis | None = None
```

Pool `setup.py`dagi lifespan'da (`queue.pool = await create_pool(ArqRedisSettings(...))`) to'ldiriladi va shutdown'da `aclose()` bilan yopiladi. Vazifa qo'ymoqchi bo'lgan kod `queue.pool.enqueue_job(...)`ni shu modul orqali chaqiradi; `health.py` (`redis_clients()`) ping uchun ishlatadi.

---

## `backend/app/core/utils/rate_limit.py`

**Maqsadi:** Redis asosidagi IP-darajali rate limiting — ham client holder, ham FastAPI dependency.

**Muhim elementlar:**

- `RateLimiter` klassi (modul-darajali singleton `rate_limiter`):
  - `initialize(redis_url)` — `Redis.from_url(redis_url)` bilan klient yaratadi (idempotent: klient bor bo'lsa qayta yaratmaydi).
  - `over_limit(key, limit) -> bool` — faqat `GET` bilan o'qiydi, hisobni OSHIRMAYDI; hisob `limit`dan katta yoki teng bo'lsa `True`. **Fail-closed**: Redis xatosi bo'lsa ham, klient `None` bo'lsa ham `True` qaytaradi (so'rov 429 oladi, xato loglanadi) — Redis yiqilishi brute-force himoyasini jimgina o'chirib qo'ymasligi uchun. Klient `None` bo'lishi normal holat emas: lifespan doim `initialize()` qiladi.
  - `bump(key, period)` — `INCR` + birinchi urinishda `EXPIRE`; bitta MUVAFFAQIYATSIZ urinishni hisobga oladi. Bu yerda xato **fail-open**: Redis yiqilsa faqat loglanadi (hisob oshmaydi), so'rovning o'zi to'silmaydi.
- `RateLimit(limit, period)` — endpoint dependency (callable klass):
  - Kalit: `ratelimit:{ip}:{route shabloni}:{window_start}` (ichki router shabloni, masalan `/public/3d/{token}` — real yo'l emas, aks holda parametrli marshrutda har token alohida kalit bo'lib cheklov ishlamasdi) — fixed-window algoritmi (`window_start = timestamp - timestamp % period`).
  - Limit oshsa `RateLimitException` (429, o'zbekcha xabar) ko'taradi.
  - **Faqat MUVAFFAQIYATSIZ urinishlar sanaladi:** dependency (`__call__`) faqat TEKSHIRADI (`over_limit`), hisobni esa chaqiruvchi xato yo'lda `await _LOGIN_RATE_LIMIT.hit(request)` bilan oshiradi (`routes/login.py`). Sabab: tsex bitta tashqi IP orqali chiqadi (NAT), ya'ni har so'rovni sanaganda smena boshida navbatma-navbat kirgan operatorlar butun zavod uchun umumiy byudjetni tugatar va keyingi odam — odatda admin — parolni xato termasa ham 429 olardi (prodda o'lchangan: 30 daqiqada 9 muvaffaqiyatli kirish va 8 ta 429).
  - `ip` `request.client.host`dan olinadi — shuning uchun `setup.py`dagi `ProxyHeadersMiddleware` muhim (aks holda hamma bitta bucket'da bo'lardi).

**Bog'lanishlar:** `exceptions.py` (`RateLimitException`); `setup.py` lifecycle'ni boshqaradi; `routes/login.py` ikkita instansiyani ishlatadi: `_LOGIN_RATE_LIMIT` (`LOGIN_RATE_LIMIT_ATTEMPTS`/`PERIOD` sozlamalaridan — parol bilan kirish) va `_BADGE_RATE_LIMIT` (30/60 s, kodda qat'iy — beyjik bilan kirish: 122-bitli UUID topib bo'lmaydi, tor chegara esa smena almashuvida butun tsexni qulflardi). `routes/public.py` esa `_SHARE_RATE_LIMIT` (60/300 s, kodda qat'iy — 3D havola tokenini taxmin qilishga qarshi, faqat topilmagan token sanaladi) ni butun `/public` routeriga qo'yadi. Logging oddiy `import logging` orqali — `logger.py`ga bog'liq emas.

---

## `backend/app/core/__init__.py` va `backend/app/core/utils/__init__.py`

Ikkalasi ham bo'sh — faqat Python package marker vazifasini bajaradi, hech qanday re-export yo'q.

---

## Yakuniy kuzatuvlar

- **Yagona konfiguratsiya manbasi:** hamma narsa `Settings` singleton'idan keladi; har qanday non-local (staging/production) muhitda xavfsiz bo'lmagan default'lar bilan boot bloklanadi.
- **Fail-fast startup, fail-closed rate limit:** DB/Redis ulanishi startup'da retry bilan tekshiriladi (ishlamasa ilova ko'tarilmaydi); runtime'da Redis yiqilsa rate limit **fail-closed** ishlaydi — cheklangan endpointlar 429 qaytaradi (brute-force himoyasi jimgina o'chib qolmaydi). Uni o'chiradigan sozlama yo'q.
- **Kuzatuvchanlik (observability):** JSON loglar + `X-Request-ID` korrelatsiyasi + Prometheus `/metrics` + «Tizim holati» (`core/perf.py` → `services/system_health.py` → `GET /system/*`, admin: endpoint vaqtlari route shabloni bo'yicha va har endpoint tafsiloti, event loop bloklari ehtimoliy aybdori bilan, chek kechikishi va navbati, `pg_stat_statements` dan og'ir SQL; yon menyuda holat belgisi); health/ready pathlari shovqin qilmasligi uchun `NON_BUSINESS_PATHS` orqali chiqarib tashlangan.
- **Xavfsizlik defaults:** httpOnly + SameSite=Strict cookie'lar (auth juftligi — `core/security.py`, chek qurilmasining `terminal_device` cookie'si — `services/terminal_device.py`, bayroqlari bir xil), HS256 JWT (access/refresh ajratilgan, `token_version` bilan revocation, refresh'da unikal `jti`), bcrypt (hash ham, verify ham) threadpool'da, docs production'da yopiq.
