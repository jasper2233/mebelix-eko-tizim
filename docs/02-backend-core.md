# Backend Core — konfiguratsiya, DB, xavfsizlik, middleware, worker

Bu hujjat MebeliX MES backend'ining yadro (core) qatlamini tavsiflaydi: ilova qanday quriladi (application factory), sozlamalar qayerdan o'qiladi, ma'lumotlar bazasi va Redis ulanishlari qanday boshqariladi, autentifikatsiya kriptografiyasi, so'rovlarni loglash va fon vazifalar (background jobs) infratuzilmasi.

Umumiy arxitektura oqimi:

```
backend/app/main.py
  └── create_application(router, settings)        # core/setup.py
        ├── Settings (env → pydantic)             # core/config.py
        ├── lifespan: Redis pool'lar + WS pub/sub listener + DB probe   # core/setup.py, core/ws.py
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
| `backend/app/core/config.py` | Barcha sozlamalar (`Settings`) + production xavfsizlik validatori |
| `backend/app/core/db.py` | Async SQLAlchemy engine, session factory, `Base` model |
| `backend/app/core/exceptions.py` | Umumiy HTTP exception klasslari (o'zbekcha xabarlar bilan) |
| `backend/app/core/health.py` | DB va Redis health-check funksiyalari |
| `backend/app/core/logger.py` | JSON formatdagi structured logging (stdout) |
| `backend/app/core/middleware.py` | `X-Request-ID` + so'rov loglash middleware'i |
| `backend/app/core/security.py` | bcrypt parol hash, JWT token, httpOnly cookie'lar |
| `backend/app/core/setup.py` | Application factory, lifespan, probe'lar, metrics, docs |
| `backend/app/core/worker.py` | arq background worker konfiguratsiyasi |
| `backend/app/core/ws.py` | Real-time ko'prik — WebSocket fan-out + Redis pub/sub (`WsManager`) |
| `backend/app/core/utils/__init__.py` | Bo'sh package marker |
| `backend/app/core/utils/queue.py` | arq Redis pool uchun global holder |
| `backend/app/core/utils/rate_limit.py` | Redis asosidagi rate limiting (`RateLimiter`, `RateLimit`) |
| `backend/app/tasks/__init__.py` | arq'ga ro'yxatga olinadigan vazifalar (`ping`, `print_label`) + `PRINT_QUEUE_KEY` |

---

## `backend/app/main.py`

**Maqsadi:** butun backend'ning kirish nuqtasi. Bor-yo'g'i 5 qator: `app.api`dagi yagona `router`ni va `core/config.py`dagi `settings`ni olib, `create_application()` factory'siga uzatadi.

```python
app = create_application(router=router, settings=settings)
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
| Application | `APP_NAME`, `APP_VERSION` (`/health` va `/ready` hisobotida ishlatiladi) — description/license/contact sozlamalari olib tashlangan, metadata `setup.py`da literal yoziladi |
| Crypto / JWT | `SECRET_KEY: SecretStr`, `ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7`, `BCRYPT_ROUNDS=12` |
| PostgreSQL | `POSTGRES_USER/PASSWORD/SERVER/PORT/DB`, `POSTGRES_ASYNC_PREFIX="postgresql+asyncpg://"`, `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20` |
| First admin | `ADMIN_NAME/PHONE/USERNAME/PASSWORD` — startup'da yaratiladigan birinchi admin |
| Redis | `REDIS_HOST/PORT`, `ENABLE_REDIS_QUEUE`, `ENABLE_REDIS_RATE_LIMIT` (ikkalasi default `True`) |
| Rate limit | `DEFAULT_RATE_LIMIT_LIMIT=10`/`PERIOD=3600`, `LOGIN_RATE_LIMIT_ATTEMPTS=5`/`PERIOD=300` |
| Pagination | `DEFAULT_PAGE_SIZE=50`, `MAX_PAGE_SIZE=100` |
| File storage | `UPLOAD_DIR="uploads"` (project/scx/label fayllar ildizi, TZ 2.4.3), `MAX_PROJECT_FILE_SIZE` = 50 MB |
| Production floor | `STRICT_STAGE_ORDER=False` (E004 — oldingi bosqich tugamaguncha skanni bloklash, ixtiyoriy, TZ 7.2.5), `SESSION_MAX_HOURS=12` (operator smenasi timeout'i, TZ 8.5), `SCAN_UNDO_SECONDS=60` (BEKOR QILISH oynasi, TZ 8.6) |
| Printing (TZ 12.3 / 13.2) | `BRIDGE_TOKEN=""` — **legacy**, ixtiyoriy: eski agentlar uchun umumiy token. Printerlar endi per-agent pairing orqali ulanadi (`bridge_agent` jadvali), shuning uchun bu sozlama bo'sh qolganda ham chop etish ishlaydi. Yorliqlar faqat shu navbat orqali USB GoDEX'ga boradi (G500-U'da tarmoq porti yo'q), shuning uchun printer manzili sozlamasi yo'q |
| Startup probes | `STARTUP_RETRY_MAX_ATTEMPTS=5`, `STARTUP_RETRY_DELAY_SECONDS=2` |
| Threadpool | `THREADPOOL_TOKENS=100` (AnyIO sync-bridge slotlari) |
| Reverse-proxy | `FORWARDED_ALLOW_IPS=["*"]` — X-Forwarded-* headerlariga ishoniladigan IP'lar |
| Env / CORS | `ENVIRONMENT`, `CORS_ORIGINS=["http://localhost:5173"]`, `CORS_METHODS`, `CORS_HEADERS` |

- Computed field'lar: `POSTGRES_URI` (`user:pass@host:port/db`) va `REDIS_URL` (`redis://host:port`).
- `_validate_production_settings(s)` — **har qanday non-LOCAL muhitda (STAGING ham, PRODUCTION ham) xavfsiz bo'lmagan default'lar bilan boot qilishni rad etadi** (faqat LOCAL o'tkazib yuboriladi): `SECRET_KEY`, `ADMIN_PASSWORD`, `POSTGRES_PASSWORD`, `ADMIN_PHONE` placeholder qiymatda qolgan bo'lsa `RuntimeError` ko'taradi. Modul import bo'lganda darhol ishlaydi (birinchi so'rovda emas, startup'da).
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

**Bog'lanishlar:** `config.py`dan `settings`; `setup.py` engine'ni startup probe uchun import qiladi; API endpointlari `async_get_db`ni `Depends` orqali oladi; ORM modellar `Base`dan meros oladi.

---

## `backend/app/core/exceptions.py`

**Maqsadi:** loyihada qayta ishlatiladigan HTTP exception klasslari. Barchasi FastAPI `HTTPException`dan meros oladi va default `detail` xabarlari **o'zbek tilida**.

| Klass | Status | Default detail |
|---|---|---|
| `NotFoundException` | 404 | "Topilmadi" |
| `ForbiddenException` | 403 | "Ruxsat berilmagan" |
| `UnauthorizedException` | 401 | "Tizimga kirilmagan" (+ `WWW-Authenticate: Bearer` header) |
| `DuplicateValueException` | 409 | "Takroriy qiymat" |
| `RateLimitException` | 429 | "So'rovlar chegarasidan oshib ketdi" |

**Bog'lanishlar:** `utils/rate_limit.py` (`RateLimitException`), auth dependency'lari va CRUD qatlamlari shu klasslarni ishlatadi.

---

## `backend/app/core/health.py`

**Maqsadi:** health-check endpointlari uchun tekshiruv funksiyalari.

- `check_database_health(db: AsyncSession) -> bool` — `SELECT 1` bajaradi; xato bo'lsa log yozib `False` qaytaradi.
- `check_redis_health() -> bool` — ilova ishlatayotgan **har bir** Redis klientni (`queue.pool` va `rate_limiter.client`) `ping()` qiladi. Hech qanday Redis funksiya yoqilmagan bo'lsa, tekshiruv "vacuously" muvaffaqiyatli hisoblanadi (`True`).

**Bog'lanishlar:** `utils/queue.py`, `utils/rate_limit.py`; API'dagi `/api/v1/health` va `/api/v1/ready` endpointlari shu funksiyalarni chaqiradi (bu pathlar `setup.py`dagi `NON_BUSINESS_PATHS`da ham ro'yxatga olingan).

---

## `backend/app/core/logger.py`

**Maqsadi:** 12-factor uslubidagi structured JSON logging — process o'zi log fayl yozmaydi, hamma narsa stdout'ga bir qatorli JSON sifatida chiqadi.

- `JsonFormatter(logging.Formatter)` — har bir log record'ni `{"timestamp", "level", "logger", "message"}` + mavjud bo'lsa `_EXTRA_FIELDS` (`request_id`, `method`, `path`, `status_code`, `duration_ms`) va `exc_info` bilan JSON'ga aylantiradi.
- `setup_logging(level=logging.INFO)` — root logger'ga stdout handler o'rnatadi. **Modul import bo'lishi bilan avtomatik chaqiriladi** (fayl oxirida `setup_logging()`).

**Bog'lanishlar:** `middleware.py` yozadigan `extra` maydonlar aynan `_EXTRA_FIELDS` bilan mos keladi; `utils/rate_limit.py` bu modul orqali `logging`ni import qiladi (side-effect: JSON logging faollashadi).

---

## `backend/app/core/middleware.py`

**Maqsadi:** har bir so'rovga `X-Request-ID` biriktirish va tugagach structured log yozish.

- `REQUEST_ID_HEADER = "X-Request-ID"`.
- `RequestLoggingMiddleware(BaseHTTPMiddleware)`:
  - Klientdan kelgan `X-Request-ID`ni qabul qiladi, bo'lmasa `uuid4().hex` yaratadi; `request.state.request_id`ga saqlaydi va javob header'iga qo'shadi.
  - `NON_BUSINESS_PATHS`dagi pathlar (`/metrics`, health/ready) **loglanmaydi** — faqat header qo'shiladi. (Circular import oldini olish uchun `NON_BUSINESS_PATHS` `dispatch` ichida local import qilinadi.)
  - Boshqa so'rovlar uchun `time.perf_counter()` bilan davomiylik o'lchanadi va `logger.info("request", extra={request_id, method, path, status_code, duration_ms})` yoziladi — bu `logger.py`dagi `JsonFormatter` orqali JSON bo'lib chiqadi.

**Bog'lanishlar:** `setup.py` (`create_application` uni ro'yxatga oladi, `NON_BUSINESS_PATHS` shu yerdan), `logger.py`.

---

## `backend/app/core/security.py`

**Maqsadi:** autentifikatsiya kriptografiyasi — parol hashlash (bcrypt), JWT token yaratish/tekshirish va httpOnly auth cookie'lar.

**Muhim elementlar:**

- Konstantalar: `ACCESS_COOKIE_NAME = "access_token"`, `REFRESH_COOKIE_NAME = "refresh_token"`; `TokenType` (StrEnum): `ACCESS` / `REFRESH`.
- Parollar:
  - `verify_password(plain, hashed)` — **async**: `bcrypt.checkpw` `run_in_threadpool` orqali bajariladi (bcrypt CPU-bound, event loop'ni bloklamaslik uchun).
  - `get_password_hash(password)` — **async**: hashlash (`_hash_password_sync`, `BCRYPT_ROUNDS`=12) `run_in_threadpool` orqali bajariladi — 12 round ~250ms olgani uchun event loop'ni bloklamasligi kerak.
- JWT:
  - `_create_token(data, token_type, expires_delta)` — payload'ga `exp` va `token_type` qo'shib `HS256` bilan imzolaydi.
  - `create_access_token(data)` (30 daqiqa) va `create_refresh_token(data)` (7 kun). Refresh token payload'iga unikal `jti` (`uuid4().hex`) qo'shiladi — har bir refresh token unikal bo'ladi va bir marta rotation'dan keyin "ishlatilgan" deb belgilash mumkin.
  - `verify_token(token, expected_token_type) -> TokenData | None` — decode qiladi, `sub` mavjudligini va `token_type` mosligini tekshiradi; `sub` **int `user_id`** sifatida parse qilinadi (parse bo'lmasa `None`) va natijada `TokenData(user_id, token_version, jti)` qaytadi — `token_version` (default 0) token bekor qilish (revocation) mexanizmi uchun, `jti` esa refresh tokenning bir martalik (one-time-use) nazorati uchun (access tokenlarda `None`).
- Cookie'lar:
  - `set_auth_cookie(response, key, value, max_age)` — `httponly=True`, `samesite="strict"` (klassik CSRF vektorini neytrallaydi), `secure` faqat non-LOCAL muhitlarda (`_is_secure_environment()`), local'da oddiy HTTP ustida ishlashi uchun o'chirilgan.
  - `clear_auth_cookies(response)` — ikkala cookie'ni o'chiradi (logout).

**Bog'lanishlar:** `config.py` (`settings`, `EnvironmentOption`), `backend/app/schemas/auth.py` (`TokenData`); auth endpointlari va `api/deps.py` shu funksiyalarni ishlatadi.

---

## `backend/app/core/setup.py`

**Maqsadi:** core'ning eng katta fayli — application factory va startup/shutdown hayot sikli. FastAPI ilovasini metadata, middleware, metrics va env-shartli docs bilan yig'adi.

**Muhim funksiyalar:**

- `_retry_async(label, fn)` — startup probe'lar uchun retry helper: `STARTUP_RETRY_MAX_ATTEMPTS` (5) marta urinadi, orasida `STARTUP_RETRY_DELAY_SECONDS` (2s) kutadi; `CancelledError`/`KeyboardInterrupt` darhol yuqoriga uzatiladi.
- `check_database_connection()` — engine orqali `SELECT 1` probe (retry bilan).
- `check_redis_connection()` — faol Redis klientlarni (`queue.pool`, `rate_limiter.client`) ping qiladi; ikkalasi ham o'chiq bo'lsa tekshiruv o'tkazib yuboriladi.
- Redis pool boshqaruvi: `create_redis_queue_pool()` (arq `create_pool` → `queue.pool`), `close_redis_queue_pool()`, `create_redis_rate_limit_pool()` (`rate_limiter.initialize(settings.REDIS_URL)`), `close_redis_rate_limit_pool()`.
- `set_threadpool_tokens()` — AnyIO thread-pool hajmini `THREADPOOL_TOKENS`ga ko'taradi (bloklovchi chaqiriqlar navbatda turib qolmasligi uchun).
- `lifespan_factory(settings)` — `@asynccontextmanager` lifespan quradi: threadpool → (yoqilgan bo'lsa) Redis pool'lar + ping → **WS real-time ko'prik**: alohida Redis klient ochilib `ws_manager.start_listener(...)` ishga tushiriladi (`core/ws.py`; kamida bitta Redis funksiya yoqilgan bo'lsa) → DB probe → `yield` → `finally`da WS listener to'xtatiladi, WS Redis klienti va pool'lar yopiladi.
- `_install_docs_router(application, settings)` — docs siyosati:
  - **production**: docs umuman yo'q;
  - **staging**: `/docs`, `/redoc`, `/openapi.json` faqat superuser uchun (`Depends(get_current_superuser)`);
  - **local**: ochiq.
- `create_application(router, settings, **kwargs) -> FastAPI` — asosiy factory:
  1. FastAPI metadata — `title` `settings.APP_NAME`dan, `description` (`"MebeliX API"`) va `license_info` (MIT) esa literal (settings'dan emas); **built-in docs har doim o'chiriladi** (`docs_url=None` va h.k.) — o'rniga shartli router o'rnatiladi.
  2. `lifespan_factory(settings)` bilan `FastAPI(...)` yaratadi va berilgan `router`ni ulaydi.
  3. Middleware'lar: `RequestLoggingMiddleware`, `CORSMiddleware` (`allow_credentials=True` — cookie-auth uchun zarur), `ProxyHeadersMiddleware` (`FORWARDED_ALLOW_IPS` bilan) — busiz `request.client.host` har doim proxy IP bo'lib, barcha foydalanuvchilar bitta rate-limit bucket'iga tushib qolardi.
  4. `_install_metrics()` va `_install_docs_router()`.
- `NON_BUSINESS_PATHS = ["/metrics", "/api/v1/health", "/api/v1/ready"]` — metrics'dan ham, access-log'dan ham chiqarib tashlanadigan pathlar (yagona manba — single source of truth).
- `_install_metrics(application)` — `prometheus_fastapi_instrumentator` orqali `/metrics` endpoint (gzip, schema'da ko'rinmaydi). Endpoint autentifikatsiyasiz — production'da Caddy darajasida cheklash nazarda tutilgan.

**Bog'lanishlar:** `config.py`, `db.py`, `middleware.py`, `ws.py` (`ws_manager`), `utils/queue.py`, `utils/rate_limit.py`, `backend/app/api/deps.py` (`get_current_superuser`); `main.py` va `worker.py` bu modulni ishlatadi.

---

## `backend/app/core/worker.py`

**Maqsadi:** arq background worker konfiguratsiyasi — fon vazifalarni (background tasks) Redis navbati orqali bajaradigan alohida process. `arq app.core.worker.WorkerSettings` komandasi bilan ishga tushiriladi.

**Muhim elementlar:**

- Modul yuklanishida `uvloop` event loop policy o'rnatiladi (Linux/macOS; Windows'da `ImportError` jim o'tkaziladi).
- `startup(ctx)` — worker startida `check_database_connection()` probe'ni bajaradi (retry bilan).
- `shutdown(ctx)` — log yozadi.
- `WorkerSettings` klassi:

```python
class WorkerSettings:
    functions = all_tasks                      # backend/app/tasks dan
    redis_settings = RedisSettings(host=..., port=...)
    on_startup = startup
    on_shutdown = shutdown
    # handle_signals default (True) — docker stop'da SIGTERM to'g'ri ushlanadi
```

- `handle_signals` endi o'rnatilmaydi (default `True`): `docker stop`da SIGTERM to'g'ri ushlanib, bajarilayotgan joblar tugatiladi yoki qayta navbatga qo'yiladi.

**Bog'lanishlar:** `config.py`, `setup.py` (`check_database_connection`), `backend/app/tasks/__init__.py` (`all_tasks = [ping, print_label]`). Web-process `utils/queue.py`dagi pool orqali vazifalarni shu worker navbatiga qo'yadi.

### `backend/app/tasks/__init__.py` — ro'yxatga olingan vazifalar

- `ping(ctx)` — liveness placeholder (arq kamida bitta funksiya talab qiladi), `"pong"` qaytaradi.
- `PRINT_QUEUE_KEY = "mes:print:queue"` — bridge-agent shu Redis ro'yxatini bo'shatadi (TZ 2.2.2). `backend/app/api/routes/ws.py` ham shu konstantani import qiladi.
- `print_label(ctx, instance_id)` — yorliq chiqarish vazifasi (TZ 7.1.4). Bitta DB sessiyasida (`local_session`) `services/labels.py`dan:
  - `load_label_data(db, instance_id)` — `None` bo'lsa `"skip:{id}"` qaytarib chiqadi;
  - `render_label_png(data)` — o'sha yorliqning 80×60 mm / 203 dpi rasteri; `base64` bilan kodlanadi.

  **Nega PNG:** GoDEX G500-U USB bilan ishlaydi va bridge-agent uni Windows drayveri (GDI) orqali chizadi — PNG printer dialektiga bog'liq emas.

  So'ng arq context'idagi Redis (`ctx["redis"]`) orqali `LPUSH mes:print:queue`, job JSON: `{"type": "print", "instance_id", "png"}` (`png` — base64 PNG). Natija `"queued:{id}"`. Redis mavjud bo'lmasa — xato loglanadi, `"lost:{id}"`.

**To'liq zanjir (TZ 2.2):**

```
terminal → POST /api/v1/terminal/labels/{instance_id}
  → label_printed_at yoziladi + ws_manager.publish("label.printed", ...)
  → queue.pool.enqueue_job("print_label", instance_id)
  → arq worker: render_label_png → LPUSH mes:print:queue
  → /ws/bridge (per-agent token auth; BRPOP + ack talab qiladi, ack kelmasa RPUSH bilan qaytariladi)
  → bridge-agent → print-queue.jsonl (durable) → Windows GDI (_print_png_gdi) → USB GoDEX G500-U
```

Bridge-agent faqat printer ulangan kompyuterga o'rnatiladi va GoDEX printerini nomidan o'zi topadi (`_detect_printer`, nomida "godex" bor Windows printeri); `PRINTER_NAME` env faqat qo'lda override uchun. Sexdagi kompyuterda `mebelix-agent.exe` (PyInstaller onefile) ishlaydi — Python ham, pip ham, serverdagi `.env` tahriri ham kerak emas. Menejer, texnolog va boshqa terminallarga hech narsa o'rnatilmaydi — ular brauzerdan tugmani bosadi.

**`/ws/bridge` autentifikatsiyasi — per-agent pairing.** Admin panel har bir printerli kompyuter uchun 8 belgili bir martalik ulanish kodi beradi (alifboda I/L/O/0/1 yo'q — telefonda aytganda adashtirmaydi; TTL 15 daqiqa). Agent birinchi ishga tushganda kodni ochiq `POST /api/v1/bridge-agents/pair` endpointi orqali doimiy tokenga almashtiradi; bazada tokenning faqat sha256 xeshi qoladi (`bridge_agent.token_hash`, unikal) — token o'zi bir marta, pair javobida beriladi.

Ulanishda token `Authorization: Bearer` headerda keladi (server access-loglariga tushmasligi uchun; `?token=` query eski agentlar uchun fallback). Tekshiruv tartibi: avval legacy `settings.BRIDGE_TOKEN` bilan `secrets.compare_digest` orqali solishtiriladi, mos kelmasa token sha256'si bo'yicha `bridge_agent` jadvalidan qidiriladi; topilmasa socket 4401 bilan yopiladi. Ulanish davomida har 300 soniyada `touch_agent()` ishlaydi — `last_seen_at`ni yangilaydi (paneldagi "Onlayn") va shu bilan birga agent qatori hali borligini tekshiradi: admin bekor qilgan bo'lsa jonli ulanish ham 4401 bilan uziladi, qo'lda turgan job esa `rpush` bilan navbatga qaytariladi — yo'qolmaydi.

**Bog'liq fayllar (core'dan tashqarida):** `backend/app/models/bridge_agent.py` (`bridge_agent` jadvali: `organization_id`, `name`, `token_hash`, `pair_code`, `pair_expires_at`, `last_seen_at`), migratsiya `d5e81a24c3b7`, `backend/app/crud/bridge_agents.py` (`crud_bridge_agents`), `backend/app/schemas/bridge_agents.py`, `backend/app/api/routes/bridge_agents.py`.

---

## `backend/app/core/ws.py`

**Maqsadi:** real-time ko'prik (TZ 2.3) — WebSocket klientlarga event fan-out. Gunicorn worker'lari aro tarqatish Redis pub/sub `mes:events` kanali orqali amalga oshadi (har bir worker faqat o'z lokal socketlarini ko'radi, kanal orqali hammasi bir xil eventni oladi).

**Muhim elementlar:**

- `WsClient` (dataclass) — bitta ulanish: `socket`, `scope` (`"terminal"` / `"tablo"` / `"dashboard"`) va ixtiyoriy `post_id`/`machine_id` filtrlar. `wants(event)` — dashboard hamma eventni oladi; target'siz eventlar broadcast; terminal/tablo faqat o'z `post_id`/`machine_id`siga mos eventlarni oladi (TZ 2.3.2).
- `WsManager` (modul-darajali singleton `ws_manager`):
  - `connect(client)` / `disconnect(client)` — lokal klientlar ro'yxatini boshqaradi (`accept` + qo'shish / olib tashlash).
  - `publish(event_type, payload, **targets)` — event quradi (`{"type", "payload"}` + `post_id`/`machine_id` target'lar) va Redis mavjud bo'lsa `mes:events` kanaliga `PUBLISH` qiladi; Redis yo'q (dev) yoki yiqilgan bo'lsa **lokal yetkazishga degradatsiya** qiladi (`_dispatch`).
  - `_dispatch(event)` — `wants()`ga mos klientlarga `send_json`; yuborishda xato bergan **o'lik socketlar ro'yxatdan tozalanadi**.
  - `start_listener(redis)` / `stop_listener()` — lifespan boshqaradigan pub/sub listener task: `mes:events`ga subscribe bo'lib, kelgan xabarlarni `_dispatch`ga uzatadi; shutdown'da unsubscribe + cancel.

**Bog'lanishlar:** `setup.py` (lifespan listener'ni ishga tushiradi/to'xtatadi), `backend/app/api/routes/ws.py` (WebSocket endpointlar klientlarni ro'yxatga oladi); mutatsiya qiluvchi API endpointlar `ws_manager.publish(...)` orqali event yuboradi.

---

## `backend/app/core/utils/queue.py`

**Maqsadi:** arq Redis pool uchun minimal global holder — 3 qator:

```python
pool: ArqRedis | None = None
```

Pool `setup.py`dagi lifespan'da (`create_redis_queue_pool`) to'ldiriladi va shutdown'da yopiladi. Vazifa qo'ymoqchi bo'lgan kod `queue.pool.enqueue_job(...)`ni shu modul orqali chaqiradi; `health.py` va `setup.py` ping uchun ishlatadi.

---

## `backend/app/core/utils/rate_limit.py`

**Maqsadi:** Redis asosidagi IP-darajali rate limiting — ham client holder, ham FastAPI dependency.

**Muhim elementlar:**

- `RateLimiter` klassi (modul-darajali singleton `rate_limiter`):
  - `initialize(redis_url)` — `ConnectionPool.from_url` + `Redis` klient yaratadi (idempotent: pool bor bo'lsa qayta yaratmaydi).
  - `is_rate_limited(key, limit, period) -> bool` — `INCR` + birinchi urinishda `EXPIRE`; hisob `limit`dan oshsa `True`. **Fail-closed**: Redis xatosi bo'lsa `True` qaytaradi (so'rov 429 oladi, xato loglanadi) — Redis yiqilishi brute-force himoyasini jimgina o'chirib qo'ymasligi uchun. Klient `None` bo'lsa (`ENABLE_REDIS_RATE_LIMIT` orqali ataylab o'chirilgan) avvalgidek ochiq — `False` qaytaradi.
- `RateLimit(limit, period)` — endpoint dependency (callable klass):
  - Kalit: `ratelimit:{ip}:{path}:{window_start}` — fixed-window algoritmi (`window_start = timestamp - timestamp % period`).
  - Limit oshsa `RateLimitException` (429, o'zbekcha xabar) ko'taradi.
  - `ip` `request.client.host`dan olinadi — shuning uchun `setup.py`dagi `ProxyHeadersMiddleware` muhim (aks holda hamma bitta bucket'da bo'lardi).

**Bog'lanishlar:** `exceptions.py` (`RateLimitException`), `logger.py`; `setup.py` lifecycle'ni boshqaradi; login kabi endpointlar `Depends(RateLimit(...))` orqali ishlatadi (`LOGIN_RATE_LIMIT_ATTEMPTS`/`PERIOD` sozlamalari bilan).

---

## `backend/app/core/__init__.py` va `backend/app/core/utils/__init__.py`

Ikkalasi ham bo'sh — faqat Python package marker vazifasini bajaradi, hech qanday re-export yo'q.

---

## Yakuniy kuzatuvlar

- **Yagona konfiguratsiya manbasi:** hamma narsa `Settings` singleton'idan keladi; har qanday non-local (staging/production) muhitda xavfsiz bo'lmagan default'lar bilan boot bloklanadi.
- **Fail-fast startup, fail-closed rate limit:** DB/Redis ulanishi startup'da retry bilan tekshiriladi (ishlamasa ilova ko'tarilmaydi); runtime'da Redis yiqilsa rate limit **fail-closed** ishlaydi — cheklangan endpointlar 429 qaytaradi (brute-force himoyasi jimgina o'chib qolmaydi). Faqat config orqali ataylab o'chirilgan bo'lsa ochiq.
- **Kuzatuvchanlik (observability):** JSON loglar + `X-Request-ID` korrelatsiyasi + Prometheus `/metrics`; health/ready pathlari shovqin qilmasligi uchun `NON_BUSINESS_PATHS` orqali chiqarib tashlangan.
- **Xavfsizlik defaults:** httpOnly + SameSite=Strict cookie'lar, HS256 JWT (access/refresh ajratilgan, `token_version` bilan revocation, refresh'da unikal `jti`), bcrypt (hash ham, verify ham) threadpool'da, docs production'da yopiq.
