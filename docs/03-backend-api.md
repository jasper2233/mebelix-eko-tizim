# Backend API — Routes, Dependencies va Endpointlar

Bu hujjat MebeliX MES backend'ining HTTP API qatlamini tavsiflaydi: router ierarxiyasi, autentifikatsiya dependency'lari va barcha endpointlar. API FastAPI asosida qurilgan, barcha handler'lar `async`, ma'lumotlar bazasi bilan ishlash SQLAlchemy `AsyncSession` orqali amalga oshiriladi. Foydalanuvchiga qaytariladigan xabarlar o'zbek tilida.

## Umumiy arxitektura

```
/api                        ← backend/app/api/__init__.py (root router)
  └── /v1                   ← backend/app/api/routes/__init__.py (versiya router)
        ├── /health, /ready ← health.py    (ochiq — auth yo'q)
        ├── /login/*        ← login.py     (ochiq — auth yo'q)
        ├── /logout         ← logout.py    ┐
        ├── /users/*        ← users.py     │
        ├── /clients/*      ← clients.py   │
        ├── /employees/*    ← employees.py │
        ├── /machines/*     ← machines.py  │
        ├── /posts/*        ← posts.py     │
        ├── /stock/*        ← stock.py     │  router darajasida
        ├── /orders/*       ← orders.py    │  Depends(get_current_user)
        ├── /pachka/*       ← pachka.py    │
        ├── /tmo/*          ← tmo.py       │
        ├── /audit-logs/    ← audit.py     │
        ├── /terminal/*     ← terminal.py  │
        ├── /scans/*        ← scans.py     │
        ├── /tablo/*        ← tablo.py     │
        ├── /reports/*      ← reports.py   ┘
        ├── /bridge-agents/*← bridge_agents.py (router darajasida auth YO'Q — /pair ochiq, admin endpointlar o'zini himoyalaydi)
        └── /ws/*           ← ws.py        (router darajasida auth YO'Q — auth endpoint ichida)
```

Jami 19 router: 2 ta ochiq (`health`, `login`), 15 tasi `get_current_user` ortida, `bridge_agents` va `ws` esa router darajasida himoyalanmaydi — autentifikatsiyani endpointlar o'zi bajaradi (WebSocket'da HTTP dependency ishlamaydi, `/bridge-agents/pair` esa sessiyasiz agent uchun ochiq bo'lishi shart).

Autentifikatsiya modeli: JWT access + refresh token juftligi, ikkalasi ham `httpOnly` cookie sifatida o'rnatiladi; qo'shimcha ravishda `Authorization: Bearer` header ham qabul qilinadi (header cookie'dan ustun). Token bekor qilish `token_version` mexanizmi orqali — logout paytida foydalanuvchining `token_version` oshiriladi va barcha eski tokenlar yaroqsiz bo'ladi.

---

## `backend/app/api/__init__.py` — API root router

**Maqsadi:** Butun API uchun eng yuqori darajadagi `APIRouter`ni yaratadi va `/api` prefiksini qo'yadi.

- `router = APIRouter(prefix="/api")` — barcha endpointlar `/api` ostida.
- Ichiga `app.api.routes` dagi `v1_router`ni ulaydi (`router.include_router(v1_router)`).
- Bu router asosiy FastAPI ilovasiga (`app.main` yoki setup modulida) mount qilinadi.

**Bog'lanishlar:** `backend/app/api/routes/__init__.py` (v1 router).

---

## `backend/app/api/deps.py` — Dependency'lar (auth, rollar va DB session)

**Maqsadi:** Endpointlarda ishlatiladigan umumiy FastAPI dependency'larni belgilaydi: DB session, joriy foydalanuvchi, superuser tekshiruvi va rol-asosli avtorizatsiya.

Asosiy elementlar:

| Nomi | Turi | Vazifasi |
|---|---|---|
| `SessionDep` | `Annotated[AsyncSession, Depends(async_get_db)]` | Har bir so'rov uchun async DB session |
| `client_ip(request)` | funksiya | Audit log uchun mijoz IP'si BITTA joyda (`request.client.host`); kelajakda proxy ortida `X-Forwarded-For` o'qish kerak bo'lsa faqat shu funksiya o'zgaradi — deyarli barcha route modullar import qiladi |
| `_oauth2_scheme` | `OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token", auto_error=False)` | Bearer token'ni ixtiyoriy o'qiydi; `auto_error=False` — header bo'lmasa 401 bermaydi, cookie fallback ishlaydi |
| `_extract_token(request, bearer_token)` | funksiya | Avval `Authorization` header, keyin `ACCESS_COOKIE_NAME` cookie'dan token oladi |
| `resolve_user(db, token)` | async funksiya | `verify_token(token, TokenType.ACCESS)` bilan tekshiradi, `crud_users.get(db, id=token_data.user_id)` orqali foydalanuvchini ID bo'yicha topadi; `is_active` va `token_version` mosligini tekshiradi. Ochiq nom — `ws.py` ham shu funksiyani chaqiradi |
| `get_current_user` | async dependency | Token yo'q yoki yaroqsiz bo'lsa `UnauthorizedException("Tizimga kirilmagan.")` |
| `CurrentUser` | `Annotated[User, Depends(get_current_user)]` | Endpoint signaturalarida qulay alias |
| `get_current_superuser` / `SuperUserDep` | dependency / alias | `is_superuser` bo'lmasa `ForbiddenException("Sizda yetarli huquq yo'q.")` |

Muhim xavfsizlik detali: `resolve_user` da `user.token_version != token_data.token_version` tekshiruvi — logout qilingan (versiyasi oshirilgan) tokenlar rad etiladi.

### Rol-asosli avtorizatsiya (TZ 3.7 rol/modul matritsasi)

`require_roles(*roles)` — dependency factory: joriy foydalanuvchi ruxsat etilgan rollardan birida bo'lishi kerak. **Superuser va `UserRole.ADMIN` HAR DOIM o'tadi**, aks holda `ForbiddenException("Sizda yetarli huquq yo'q.")`. Tayyor aliaslar:

| Alias | Ta'rifi | Kimga ruxsat (admin/superuser'dan tashqari) |
|---|---|---|
| `ManagerUser` | `require_roles(MANAGER)` | manager |
| `TexnologUser` | `require_roles(TEXNOLOG)` | texnolog |
| `StaffReadUser` | `require_roles(MANAGER, TEXNOLOG, DIRECTOR)` | ofis rollari uchun umumiy read-only ro'yxatlar |
| `AdminUser` | `require_roles()` | hech kim — faqat admin/superuser |

Terminal oqimida esa route fayllar o'zi lokal alias tuzadi: `TerminalUser = require_roles(UserRole.TERMINAL, *POST_ROLES)` (`terminal.py`, `scans.py`) — maxsus terminal akkauntlar va 9 ta operator roli (arrachi, kromkachi, ovalchi, prisadkachi, roverchi, stolyar, boyoqchi, upakovkachi, omborchi). Chek bekor qilish endpointi kengroq: `LabelCancelUser` = terminal/operator + manager/texnolog.

**Bog'lanishlar:** `backend/app/core/db.py` (`async_get_db`), `backend/app/core/security.py` (`verify_token`, `TokenType`, `ACCESS_COOKIE_NAME`), `backend/app/core/exceptions.py`, `backend/app/crud` (`crud_users`), `backend/app/models/user.py`, `backend/app/models/enums.py` (`UserRole`).

---

## `backend/app/api/routes/__init__.py` — v1 router agregatori

**Maqsadi:** Barcha route modullarini bitta `/v1` prefiksli router'ga birlashtiradi va qaysi router'lar auth talab qilishini belgilaydi.

```python
router = APIRouter(prefix="/v1")
router.include_router(health_router)   # ochiq
router.include_router(login_router)    # ochiq

_protected = [Depends(get_current_user)]
router.include_router(logout_router, dependencies=_protected)
router.include_router(users_router, dependencies=_protected)
router.include_router(clients_router, dependencies=_protected)
router.include_router(employees_router, dependencies=_protected)
router.include_router(machines_router, dependencies=_protected)
router.include_router(posts_router, dependencies=_protected)
router.include_router(stock_router, dependencies=_protected)    # materiallar ombori
router.include_router(orders_router, dependencies=_protected)
router.include_router(pachka_router, dependencies=_protected)   # qadoqlash
router.include_router(tmo_router, dependencies=_protected)      # TMO — tayyor mahsulot ombori
router.include_router(audit_router, dependencies=_protected)
router.include_router(terminal_router, dependencies=_protected)
router.include_router(scans_router, dependencies=_protected)
router.include_router(tablo_router, dependencies=_protected)
router.include_router(reports_router, dependencies=_protected)
router.include_router(bridge_agents_router)  # /pair ochiq bo'lishi shart
router.include_router(ws_router)  # WebSocket auth endpoint ichida
```

Ya'ni auth ikki qatlamda: router darajasida `get_current_user` (login bo'lganlik), endpoint darajasida esa `deps.py` dagi rol aliaslari (kim nima qila oladi). Ikki istisno: `ws_router` — WebSocket'da HTTP dependency ishlamaydi, shuning uchun autentifikatsiya har endpoint ichida bajariladi (quyida `ws.py` bo'limi); `bridge_agents_router` — `/pair` va `/scan` sessiyasiz kompyuterdan chaqiriladi, shuning uchun butun router himoyasiz ulanadi va admin endpointlarning har biri `AdminUser` bilan o'zini himoyalaydi.

**Bog'lanishlar:** `backend/app/api/deps.py` va barcha route fayllar.

---

## `backend/app/api/routes/health.py` — Health/Readiness problar

**Maqsadi:** Kubernetes/Docker uslubidagi liveness va readiness endpointlari. Auth talab qilinmaydi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| GET | `/api/v1/health` | Yo'q | — | `HealthCheck` (status, environment, version, timestamp), 200 | Liveness — jarayon tirikligini tasdiqlaydi |
| GET | `/api/v1/ready` | Yo'q | — | `ReadyCheck` (status, environment, version, app, database, redis, timestamp), 200 yoki 503 | Readiness — `check_database_health` va `check_redis_health` orqali DB hamda Redis'ni ping qiladi; birortasi ishlamasa 503 |

Yordamchi funksiyalar: `_now()` (UTC ISO timestamp), `_status(ok)` (`"healthy"` / `"unhealthy"`).

**Bog'lanishlar:** `backend/app/core/health.py`, `backend/app/core/config.py` (`settings.ENVIRONMENT`, `APP_VERSION`), `backend/app/schemas/health.py`, `backend/app/api/deps.py` (`SessionDep`).

---

## `backend/app/api/routes/login.py` — Autentifikatsiya (token berish va yangilash)

**Maqsadi:** Login va refresh oqimi. Access+refresh token juftligini yaratadi va ikkalasini `httpOnly` cookie sifatida o'rnatadi (`set_auth_cookie`), shu bilan birga access token'ni response body'da ham qaytaradi (OAuth2 mosligi uchun).

Muhim yordamchi: `_issue_token_pair(response, user) -> str` — payload `{"sub": str(user.id), "token_version": user.token_version}` bilan `create_access_token` va `create_refresh_token` chaqiradi (JWT `sub` — foydalanuvchi ID'si, username emas), cookie'larni muddat bilan o'rnatadi: access — `ACCESS_MAX_AGE` (daqiqa×60); refresh esa ROLGA bog'liq — qurilma hisoblarida (TERMINAL, TABLO) `settings.DEVICE_REFRESH_TOKEN_EXPIRE_DAYS` (default 90 kun; monoblokda klaviatura yo'q, parol faqat o'rnatishda bir marta teriladi), qolganlarida `REFRESH_TOKEN_EXPIRE_DAYS` (default 7 kun — o'g'irlangan cookie oynasi kengaymasin). Refresh token ham AYNAN shu `days` bilan yaratiladi (`create_refresh_token(..., days=days)`), cookie muddati `days × 24×60×60`. `REFRESH_MAX_AGE` konstantasi esa faqat Redis'dagi `jti` tombstone TTL'i uchun ishlatiladi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/login/access-token` | Yo'q (rate limit: `_LOGIN_RATE_LIMIT`) | `OAuth2PasswordRequestForm` (username — username yoki telefon, password) | `Token` (`access_token`, `token_type: "bearer"`) | `crud_users.authenticate` orqali tekshiradi; noto'g'ri bo'lsa yoki `is_active=False` bo'lsa 401. **`is_system=True` hisob YOPIQ** — 401 "Bu texnik hisob — u bilan kirilmaydi.": seed yaratgan post hisobi faqat beyjik bilan ochilgan smena qaysi nomdan yozilishini hal qiladi (`_terminal_user`), odam emas. Post rolidagi SHAXSIY hisob esa kiradi va `_open_shift_for` smenani shu zahoti ochadi (`employee.user_id` bog'lami, post `POST_ROLES` dan, ish markazi `scanning.post_machine` dan; bog'lam yoki ish markazi topilmasa smena ochilmaydi va odam terminalda o'zini tanishtiradi). Bu skaneri yo'q post uchun — ARRA da chek chiqarish skan hisoblanadi, skaner faqat kirishga kerak bo'lardi |
| POST | `/api/v1/login/refresh` | Refresh cookie (`REFRESH_COOKIE_NAME`) | Cookie'dan refresh token | `{"access_token", "token_type"}` | Refresh token'ni `verify_token(TokenType.REFRESH)` bilan tekshiradi, `token_version` mosligini tasdiqlaydi va **ikkala tokenni ham rotatsiya qiladi**; har bir refresh token **one-time-use** (quyida) |
| POST | `/api/v1/login/badge` | Yo'q (rate limit: `_BADGE_RATE_LIMIT`) | `BadgeLoginRequest` (`badge_id`, ixtiyoriy `post_id`) | `BadgeLoginResponse` (`Token` + `employee_name`, `machine_name`, `post_name`) | Tsexdagi kirish: beyjik skani, parolsiz. Post beyjik egasining biriktirilgan postlaridan chiqadi; bir nechtasi bo'lsa **409** + `{"code": "POST_CHOICE", "employee_name", "posts": [...]}` (monoblok tanlash oynasini ko'rsatadi va `post_id` bilan qayta yuboradi). Smenani ochadi (`open_badge_session`) |

### Beyjik bilan kirish (parolsiz tsex terminali)

Operator login/parol termaydi — beyjik skani kirishga aylanadi. **Hech qanday o'rnatish qadami yo'q:** kirish sahifasi ochilib turgan istalgan brauzerda skan ishlaydi.

Beyjik ikkala savolga javob beradi — KIM va QAYERDA:

1. `badge_id` → `employee` (nofaol beyjik va noma'lum beyjik 401).
2. `employee.assigned_post_ids` → post. Bitta bo'lsa so'ralmaydi; bir nechta bo'lsa 409 + ro'yxat, hodim monoblokda tanlaydi (`_badge_post`).
3. Post → ish markazi: `_post_machine` `scanning.post_machine` — BITTA joydagi qoida (ilgari ikki nusxada yozilgan edi): NOAKTIV markaz tanlanmaydi, AKTIV TA'MIRDA dan ustun turadi, ikkalasi ham yo'q bo'lsa admin uchun aniq xato. Beyjik kirishi ham, terminal konteksti ham SHU funksiyani chaqiradi, ya'ni ikkalasi bir xil javob beradi.
4. `_terminal_user(machine, post)` — kirish qaysi hisob nomidan yoziladi: shu ish markaziga biriktirilgan **TERMINAL** hisobi, bo'lmasa post roli hisobi (`POST_ROLES`). Ikkala yo'l ham `resolve_terminal` bilan BIR XIL postga olib keladi (biri ish markazi, ikkinchisi rol orqali) — aks holda operator boshqa postning ekranida paydo bo'lardi. Hisob KIM ishlayotganini bildirmaydi — u beyjik ochgan `work_session` da.

**Xavfsizlik (ataylab tanlangan, 2026-08-12).** Beyjik — yagona omil: QR qog'ozda, nusxa olingan bo'lsa istalgan qurilmadan kirsa bo'ladi. Qurilma bog'lash varianti ko'rib chiqilib rad etildi — tsexda parol/kod terish smena almashuvini sekinlashtiradi va amalda umumiy akkauntga olib keladi, ya'ni ish haqi atributsiyasini butunlay yo'qotadi. O'rniga: hisob imtiyozi tor (terminal ekranlari, admin paneli emas), har kirish audit logga tushadi, beyjik `employee.status` bilan darhol bekor qilinadi. Chegara `30/60s` — 122-bitli UUID'ni brute-force qilib bo'lmaydi, tor chegara esa smena almashuvida butun tsexni (bitta tashqi IP) qulflab qo'yardi.

Refresh token one-time-use mexanizmi: har bir muvaffaqiyatli refresh'dan so'ng token'ning `jti`si Redis'da (`auth:refresh:used:<jti>` kaliti, `rate_limiter.client` orqali, TTL = `REFRESH_MAX_AGE`) "ishlatilgan" deb belgilanadi (`_mark_refresh_token_used`). Ishlatilgan `jti` bilan qayta so'rov (replay) kelsa — cookie o'g'irlangan yoki client buzilgan deb hisoblanadi: foydalanuvchining `token_version`i oshiriladi va **butun sessiya bekor qilinadi** (401 "Token bekor qilingan."). Redis klienti lifespan'da shartsiz ochiladi (`rate_limiter.initialize(settings.REDIS_URL)`, o'chirish sozlamasi yo'q), shuning uchun `rate_limiter.client is None` faqat lifespan'siz kontekstda uchraydi — o'sha holatda tekshiruv o'tkazib yuboriladi.

Brute-force himoyasi: `RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)` dependency sifatida `access-token` endpointiga qo'llangan. Beyjik endpointida alohida `_BADGE_RATE_LIMIT = RateLimit(30, 60)` (kalit `ratelimit:{ip}:{path}:{oyna}` — yo'l bo'yicha ajralgan, parol chegarasini yemaydi).

**Bog'lanishlar:** `backend/app/core/security.py` (token yaratish/tekshirish, cookie helper'lar), `backend/app/core/utils/rate_limit.py` (`RateLimit`, `rate_limiter`), `backend/app/crud` (`crud_users.authenticate`, `get`, `increment_token_version`), `backend/app/schemas/auth.py` (`Token`, `BadgeLogin*`, `BadgePostOption`), `backend/app/services/scanning.py` (`open_badge_session`), `backend/app/core/config.py`.

---

## `backend/app/api/routes/logout.py` — Tizimdan chiqish

**Maqsadi:** Global logout — foydalanuvchining `token_version`ini oshirish orqali barcha faol access/refresh tokenlarni bekor qiladi va cookie'larni tozalaydi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/logout` | Ha (`CurrentUser`) | — | `Message` — "Tizimdan muvaffaqiyatli chiqildi" | `crud_users.increment_token_version` + `clear_auth_cookies(response)` |

**Bog'lanishlar:** `backend/app/api/deps.py`, `backend/app/core/security.py` (`clear_auth_cookies`), `backend/app/crud`.

---

## `backend/app/api/routes/users.py` — Foydalanuvchilarni boshqarish

**Maqsadi:** Foydalanuvchi CRUD: admin (superuser) tomonidan yaratish/tahrirlash hamda foydalanuvchining o'z profilini (`/me`) boshqarishi.

Ro'yxat javobi umumiy `Paginated[UserRead]` sxemasida (`app/schemas/common.py`) — lokal nusxa yo'q.

Yordamchi funksiyalar:
- `_ensure_unique(db, *, phone, username, current)` — telefon/username boshqa foydalanuvchida band bo'lsa `DuplicateValueException`.
- `_derive_username_from_phone(phone)` — `+998901234567` → `998901234567`; username berilmasa telefondan hosil qilinadi, kollisiya bo'lsa `...1`, `...2` suffiks qo'shiladi.
- `_drop_forbidden_nulls(update_data)` — PATCH body'dagi explicit `null` qiymatlarni filtrlaydi: faqat `_NULLABLE_FIELDS = ("name", "machine_id")` null qabul qiladi (`machine_id: null` — ish markazi bog'lamini uzish), qolganlari NOT NULL ustunlarga tegib 500 berardi.

Barcha mutatsiyalar (yaratish, admin-yangilash, parol almashtirish, o'chirish) `log_action` bilan audit qilinadi (`module="users"`); xabar javoblari `Message` sxemasida, "topilmadi" holatlari `crud_users.get_or_404` orqali.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/users/` | Superuser | `UserCreate` | `UserRead`, 201 | Yangi foydalanuvchi yaratish; telefon uniqueness tekshiruvi; username ixtiyoriy (telefondan derive qilinadi) |
| GET | `/api/v1/users/` | `StaffReadUser` | Query: `skip>=0`, `limit` (1..`MAX_PAGE_SIZE`, default `DEFAULT_PAGE_SIZE`) | `Paginated[UserRead]` | Sahifalangan ro'yxat. RO'YXAT boshqaruvga ochiq — birlashgan "Hodimlar" sahifasi har odamning kirish usulini shundan biladi; YOZISH amallari superuser'da qoladi |
| GET | `/api/v1/users/me` | Login | — | `UserRead` | Joriy foydalanuvchi profili |
| PATCH | `/api/v1/users/me` | Login | `UserUpdate` | `UserRead` | O'z profilini yangilash; `UserUpdate` da privilege flaglar yo'q — eskalatsiya mumkin emas; explicit `null`lar `_drop_forbidden_nulls` bilan filtrlanadi |
| PATCH | `/api/v1/users/me/password` | Login | `UpdatePassword` (`current_password`, `new_password`) | `{"message": ...}` | Joriy parolni `verify_password` bilan tekshiradi; yangi parol eskisiga teng bo'lmasligi kerak; yangi hash `await get_password_hash(...)` bilan hisoblanadi |
| DELETE | `/api/v1/users/me` | Login (superuser emas) | — | `{"message": ...}` | O'z hisobini o'chirish; superuser'lar o'zini o'chira olmaydi (403) |
| GET | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `UserRead` | ID bo'yicha foydalanuvchi — faqat o'zi yoki superuser (aks holda 403, telefon raqamlar maxfiy); topilmasa 404 |
| PATCH | `/api/v1/users/{user_id}` | Superuser | `UserAdminUpdate` | `UserRead` | Istalgan foydalanuvchini yangilash (admin schema privilege flaglarni o'z ichiga oladi); explicit `null`lar `_drop_forbidden_nulls` bilan filtrlanadi |
| DELETE | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `{"message": ...}` | Soft-delete; superuser o'z hisobini o'chira olmaydi; oddiy user faqat o'zini o'chira oladi |

**Bog'lanishlar:** `backend/app/api/deps.py` (`CurrentUser`, `SuperUserDep`, `SessionDep`), `backend/app/schemas/users.py` (`UserCreate`, `UserRead`, `UserUpdate`, `UserAdminUpdate`, `UpdatePassword`), `backend/app/schemas/common.py` (`Paginated`), `backend/app/core/security.py` (`get_password_hash`, `verify_password`), `backend/app/crud`, `backend/app/core/exceptions.py`, `backend/app/core/config.py`.

---

## `backend/app/api/routes/clients.py` — Mijozlar

**Maqsadi:** Mijozlar CRUD (buyurtma reestri uchun manba). Ro'yxat javobida har mijozga `orders_count` (tirik buyurtmalar soni, subquery orqali) qo'shiladi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/clients/` | `StaffReadUser` | Paginatsiya (`skip`/`limit`), `search` — ism/telefon bo'yicha `ilike` |
| POST | `/api/v1/clients/` | `ManagerUser` | 201; telefon unikalligi: `phone` va `phone_alt` ustunlari bo'yicha tirik yozuvlarda tekshiriladi, band bo'lsa 409 — xabarda egasining ismi ko'rsatiladi |
| GET | `/api/v1/clients/{id}` | `StaffReadUser` | Bitta mijoz + `orders_count`; topilmasa 404 |
| PATCH | `/api/v1/clients/{id}` | `ManagerUser` | Yangilash; telefon o'zgarsa unikallik qayta tekshiriladi |
| DELETE | `/api/v1/clients/{id}` | `ManagerUser` | Soft-delete, `Message` qaytaradi |

Barcha mutatsiyalar `log_action` bilan audit qilinadi (`module="clients"`).

**Bog'lanishlar:** `backend/app/schemas/clients.py`, `backend/app/crud` (`crud_clients`, `log_action`), `backend/app/schemas/common.py` (`Paginated`, `Message`).

---

## `backend/app/api/routes/employees.py` — Hodimlar va beyjiklar

**Maqsadi:** Tsex hodimlari CRUD va beyjik (QR badge) boshqaruvi. Hodim — tizimga kirmaydigan shaxs; u terminalda beyjik skan qilib ishlaydi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/employees/` | `StaffReadUser` | Paginatsiya; `search` — ism/beyjik; `status` filtri (`EmployeeStatus`) |
| POST | `/api/v1/employees/` | `AdminUser` | 201; `badge_id` avtomatik `uuid4` sifatida yaratiladi va JAVOBDA QAYTARILMAYDI (tsexdagi yagona kirish kaliti — ekranga chiqmaydi); `assigned_post_ids` mavjudligi tekshiriladi, BO'SH bo'lishi mumkin (hamma xodim ish markazida ishlamaydi); `user_id` — ixtiyoriy kirish hisobi bog'lami (`_validate_user_link`: hisob mavjud, qurilma/post hisobi emas, boshqa hodimga band emas) |
| GET | `/api/v1/employees/{id}` | `StaffReadUser` | Topilmasa 404 |
| PATCH | `/api/v1/employees/{id}` | `AdminUser` | `assigned_post_ids` o'zgarsa qayta validatsiya |
| POST | `/api/v1/employees/{id}/badge` | `AdminUser` | Beyjik yo'qolganda (TZ 4.2): yangi `uuid4` beriladi — eskisi darhol ishlamay qoladi, tarix shu hodimda qoladi; eski beyjik audit `meta`sida saqlanadi |
| POST | `/api/v1/employees/{id}/print` | `AdminUser` | Beyjikni chop etish navbatiga qo'yadi (`print_badge` arq task -> Redis `mes:print:queue` -> bridge-agent -> GoDEX). Brauzerdan chop etish TASHLANDI: u drayverdagi saqlangan qog'oz o'lchamiga tayanardi, agent esa DEVMODE bilan 80×60 ni majburlaydi |
| DELETE | `/api/v1/employees/{id}` | `AdminUser` | Soft-delete. Ochiq smenalari shu tranzaksiyada yopiladi (`end_employee_sessions`) — aks holda ular postni E006 bilan tiqilib qoldirardi |

**Hodim nofaol qilinganda yoki o'chirilganda** `end_employee_sessions()` uning OCHIQ smenalarini yopadi. Busiz nofaol hodim brigadaning LANGAR smenasi egasi bo'lib qolsa, o'sha ish markazidagi har skan E006 "Hodim nofaol" bilan rad etilardi (`scanning.active_session`) — brigadaning qolgan a'zolari aybsiz bo'lsa ham post to'liq to'xtardi. Audit xabariga nechta smena yopilgani yoziladi.

**O'chirish to'sig'i OLIB TASHLANDI.** U POST ROLI hisobiga bog'langan yozuvlarni 403 bilan rad etardi — eski avtomat mirror'lar uchun. Mirror'lar `a9e14b7c2d63` da butunlay o'chirilgan, post rolidagi bog'lam esa endi BOSHQA narsani bildiradi: skaneri yo'q postda ishlaydigan odamning shaxsiy hisobi. To'siq qolganda haqiqiy hodimni o'chirib bo'lmasdi.

**Bog'lanishlar:** `backend/app/schemas/employees.py`, `backend/app/crud` (`crud_employees`, `crud_posts`, `crud_users`, `log_action`), `backend/app/services/scanning.py` (`end_employee_sessions`).

---

## `backend/app/api/routes/machines.py` — Ish markazlari

**Maqsadi:** Ish markazlari CRUD. Ro'yxat kichik va o'zgarmas bo'lgani uchun paginatsiyasiz; o'qish har qanday login qilgan foydalanuvchiga ochiq (terminal/TABLO kontekstga ham kerak).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/machines/` | login (har qanday) | Barcha ish markazlari, `list[MachineRead]` |
| POST | `/api/v1/machines/` | `AdminUser` | 201; `post_id` mavjudligi va NOM TAKRORLANMASLIGI tekshiriladi (`_check_name`, registrga sezgir emas) — indeks `ix_machine_name` baribir rad etardi, lekin xabari tushunarsiz bo'lardi |
| GET | `/api/v1/machines/{id}` | login (har qanday) | Topilmasa 404 |
| PATCH | `/api/v1/machines/{id}` | `AdminUser` | nom o'zgarsa takrorlanmasligi tekshiriladi; `post_id` o'zgarsa qayta tekshiriladi; **skan tarixi bor markazning posti o'zgarmaydi** (409) — o'tgan skanlar yangi post nomidan sanalib ketardi |
| DELETE | `/api/v1/machines/{id}` | `AdminUser` | Soft-delete, LEKIN **bog'lam bo'lsa 409** (`_blockers`): biriktirilgan hisob (`user.machine_id`), printer agenti, ochiq smena, tugallanmagan marshrut (`total_done < total_required`). Sabab xabarda nomlanadi |

**O'chirish nega to'sildi:** soft-delete FK'ni buzmaydi, lekin bog'lamni JIMGINA uzadi — qurilma hisobi E009 bilan kirolmaydi, agent skan-forvardi 409 beradi, tugallanmagan marshrutlar terminal ro'yxatidan yo'qoladi (filtr `machine_id` bo'yicha). Vaqtincha to'xtatish uchun o'chirish emas, `status` kerak.

**Bog'lanishlar:** `backend/app/schemas/machines.py`, `backend/app/crud` (`crud_machines`, `crud_posts`, `log_action`).

---

## `backend/app/api/routes/posts.py` — Ishlab chiqarish postlari

**Maqsadi:** 9 ta belgilangan post (ARRA, KROMKA, OVAL, PRISADKA, ROVER, STOLYARKA, BOYOQ, UPAKOVKA, TMO; `order_index` 1–10: OVAL 3, ROVER 6, UPAKOVKA 9, TMO 10 — 5-tartib olib tashlangan PAZ dan bo'sh qolgan) — ular `seed_defaults` komandasi bilan yaratiladi, shuning uchun API'da create/delete YO'Q, faqat o'qish va sozlash.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/posts/` | login (har qanday) | `order_index` bo'yicha tartiblangan postlar ro'yxati |
| PATCH | `/api/v1/posts/{id}` | `AdminUser` | Post sozlamalarini yangilash (nom, rang, flaglar) |

**Bog'lanishlar:** `backend/app/schemas/posts.py`, `backend/app/crud` (`crud_posts`, `log_action`), `backend/app/commands/seed_defaults.py`.

---

### `/api/v1/stock` — Materiallar ombori (`routes/stock.py`)

**Maqsadi:** omborchi yuritadigan katalog: kod, qoldiq, minimal zaxira, narx. `stock_item` — AYRIM jadval: GibLab `.project` dan keladigan plita/kromka sarfi `Order.material_usage` JSONB ustunida turadi va har yuklashda qayta yoziladi, ya'ni qoldiq va narx u yerda tura olmaydi; furnitura esa `.project` da umuman uchramaydi (material katalogi jadvali `d2b71f4c86e9` bilan butunlay olib tashlangan). Huquq: `StockUser` — `material_omborchi` (qoldiqni yuritadigan xodim) + manager/texnolog/direktor (u yo'qligida ish to'xtamasin). `omborchi` bu yerda YO'Q: u TMO ning odami, monoblokda ishlaydi.

| Method | Path | Nima qiladi |
|---|---|---|
| GET | `/api/v1/stock/` | Ro'yxat (`Paginated[StockItemRead]`, `skip`/`limit`): `search` — nom, kod YOKI guruh nomi (`group_name`; jadvalda alohida "Guruh" ustuni yo'q, "petlya" deb yozgan omborchi butun guruhni topsin), `catalog` (F/M), `group_code`, `low=true` (min zaxiradan pastdagilar) |
| GET | `/api/v1/stock/summary` | Sahifa tepasidagi uchta raqam: tovar soni, tugayaptilar, qoldiqning XARID narxidagi qiymati |
| GET | `/api/v1/stock/groups` | Filtr chiplari — guruh, tovar soni, tugayaptilar soni. Alohida jadval yo'q: 28 guruh tovarlarning o'zidan yig'iladi |
| POST | `/api/v1/stock/` | Yangi tovar. **`code` IXTIYORIY**: bo'sh bo'lsa server beradi — guruhdagi eng katta model raqami + 1 (`F-RC-032-01`). Excel katalogida "Keyingi bo'sh model kodi" ustunini odam qo'lda yuritardi, o'sha ish serverga o'tdi va ikki kishi bir vaqtda qo'shsa unique indeks ikkinchisini rad etadi. Mavjud MODELNING yangi varianti kerak bo'lsa (o'sha ruchkaning boshqa rangi) kod qo'lda beriladi — `F-RC-001-04`. Kod band bo'lsa 409 |
| PATCH | `/api/v1/stock/{id}` | Kartochka maydonlari: nom, variant, o'lcham, birlik, izoh, min zaxira, narxlar — va **`qty` ham** (`StockItemUpdate` da bor, endpoint kelgan maydonni to'g'ridan-to'g'ri `setattr` qiladi). PATCH bilan yozilgan qoldiq HARAKAT JURNALIGA (`stock_move`) TUSHMAYDI, shuning uchun frontend bu yerda `qty` yubormaydi — qoldiqning odatdagi yo'li `POST /{id}/move` |
| POST | `/api/v1/stock/{id}/move` | **KIRIM / BUYURTMAGA / HISOBDAN CHIQIM** — `delta` (musbat/manfiy) + `kind`. Qoldiqni to'g'ridan-to'g'ri yozish EMAS: omborchi "20 ta keldi" deb o'ylaydi va delta ikki kishi bir vaqtda yozganda ham yo'qolmaydi. `kind=buyurtma` da `order_id` MAJBURIY va faqat chiqim — tannarx shu buyurtmaga yoziladi. `kind=sotuv` bu yerda RAD ETILADI (422): sotuvda hujjat, mijoz va to'lov bo'ladi. Qoldiq manfiyga tushsa 409 |
| GET | `/api/v1/stock/moves` | Harakatlar: `item_id` (tovar kartochkasi), `order_id` (buyurtmaga berilganlar — buyurtma tannarxi), `kind`, `limit` (1..`settings.MAX_PAGE_SIZE`, sukut `settings.DEFAULT_PAGE_SIZE`) |
| POST | `/api/v1/stock/sales` | **SOTUV**: `lines[]` (tovar, miqdor, narx — bo'sh bo'lsa katalogdagi sotuv narxi), `client_id`, `paid_uzs`, `method`. To'liq to'lanmagan (`paid_uzs = 0`) sotuvda MIJOZ MAJBURIY (kimdan undirishni bilmasak yozuvning ma'nosi yo'q) — 422; naqd sotuvda shart emas, qisman to'lovda (`0 < paid_uzs < jami`) hozircha talab qilinmaydi. Satrlar `stock_move` sifatida yoziladi (`sale_id` bilan) — sotuv satri va ombor harakati bir xil voqea |
| GET | `/api/v1/stock/sales` | Sotuvlar; `debts=true` — faqat to'lanmaganlar (qarzdorlar), `status` (`paid`/`partial`/`debt`), `client_id` (mijozning qarz tarixi), `limit` (1..`settings.MAX_PAGE_SIZE`, sukut `settings.DEFAULT_PAGE_SIZE`) |
| GET | `/api/v1/stock/sales/summary` | Sotuvlar soni, savdo, tushgan pul, qarz |
| GET | `/api/v1/stock/sales/{id}` | Bitta sotuv: satrlar + to'lovlar |
| POST | `/api/v1/stock/sales/{id}/payments` | Qarzni to'lash (to'liq yoki qisman). To'lov AYRIM yozuv — `paid_uzs` ni shunchaki yangilash "qachon va qanday to'ladi" ni yo'qotardi. Qarzdan katta to'lov 422 |
| DELETE | `/api/v1/stock/{id}` | Soft-delete |

**Katalogni yuklash:** `python -m app.commands.import_stock_catalog ["fayl.xlsx"]` — BUYRUQ QATORIDAN. Brauzerdan yuklash endpointi qurildi va OLIB TASHLANDI: katalog bir marta to'ldiriladi, keyin tovarlar bittalab qo'shiladi, ya'ni har kun ko'rinib turadigan tugma keraksiz edi — `uploads/Umumiy maxsulotlar kataligi.xlsx` dan 638 tovar (464 furnitura + 174 material). `Xizmatlar` varag'i OLINMAYDI: xizmatning qoldig'i bo'lmaydi. Idempotent — kod bo'yicha topilsa nom va narx yangilanadi, **`qty` esa faqat yangi tovarda yoziladi**: mavjud qoldiqni omborchi tizimda yuritadi va qayta import uni Excel'dagi eski raqamga qaytarmasligi kerak. Ustunlar tartib raqamiga emas SARLAVHAGA qarab olinadi.


**Bog'lanishlar:** `backend/app/schemas/stock.py` (`StockItemCreate/Read/Update`, `StockMoveRequest/Read`, `SaleCreate/Read/Summary`, `PaymentCreate/Read`, `StockGroup`, `StockSummary`), `backend/app/models/stock.py` (`StockItem`, `StockMove`, `Sale`, `Payment`), `backend/app/crud` (`crud_stock_items`, `log_action`), `backend/app/models/enums.py` (`StockCatalog`, `StockMoveKind`, `SaleStatus`, `PaymentMethod`), `backend/app/commands/import_stock_catalog.py`.

---

## `backend/app/api/routes/orders.py` — Buyurtmalar (hayot sikli, matritsa, fayllar)

**Maqsadi:** Eng katta route moduli (20 endpoint) — buyurtma hayot sikli TZ 6 bo'yicha: `DRAFT → TECHNICAL_REVIEW → PRODUCTION → COMPLETED → DELIVERED` (+ istalgan bosqichda `CANCELLED`). Tahrirlash cheklovlari `_EDITABLE_STATUSES = (DRAFT, TECHNICAL_REVIEW)` atrofida qurilgan.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/orders/` | `ManagerUser` | 201; tartib raqami `crud_orders.next_number` ("B-2026-001" ko'rinishida, yiliga ketma-ket); ikki manager poygasida unique index hakam — `IntegrityError` bo'lsa 3 martagacha qayta uriniladi; WS `order.created` |
| GET | `/api/v1/orders/` | `StaffReadUser` | Paginatsiya; `status` filtri; `search` — raqam/loyiha nomi/loyiha UUID/mijoz ismi; DRAFT va CANCELLED buyurtmalar texnologga (superuser bo'lmasa) KO'RINMAYDI (`_hidden_statuses`) |
| GET | `/api/v1/orders/status-counts` | `StaffReadUser` | Reestr tablari uchun har holatdagi buyurtmalar soni; `_hidden_statuses` filtri bu yerda ham amal qiladi; `/{order_id}` dan OLDIN e'lon qilingan (aks holda "status-counts" order_id deb o'qilardi) |
| GET | `/api/v1/orders/{id}` | `StaffReadUser` | `OrderDetail`: mijoz ismi, biriktirilgan fayllar (`OrderFileRead`, `meta` bilan), `survey` (anketa JSON), `parts_count`, `instances_count`; yashirin holatdagi buyurtma texnologga to'g'ridan ID bilan ham 404 |
| PATCH | `/api/v1/orders/{id}` | `ManagerUser` | DELIVERED/CANCELLED tahrirlanmaydi (403); `client_id` faqat DRAFT holatida almashtiriladi |
| PUT | `/api/v1/orders/{id}/survey` | `ManagerUser` | Mijoz anketasi + o'lchov varag'ini to'liq almashtiradi (`OrderSurvey` → `Order.survey` JSONB); DELIVERED/CANCELLED da 403; saqlashda o'chirilgan xonalarning rasmlari yetim qolmasin deb tozalanadi (quyida); audit `survey_saved` |
| POST | `/api/v1/orders/{id}/survey/photos` | `ManagerUser` | 201, multipart: `room_id` (Form, ≤40 belgi) + `file`; xona uchun namuna rasm; DELIVERED/CANCELLED buyurtmaga rasm qo'shib bo'lmaydi (403); javob `OrderFileRead`; audit `survey_photo_added` |
| DELETE | `/api/v1/orders/{id}/survey/photos/{file_id}` | `ManagerUser` | Rasmni o'chiradi — diskdan ham, bazada `is_deleted=True`; boshqa buyurtmaning yoki `DOCUMENT` bo'lmagan fayl uchun 404; audit `survey_photo_deleted` |
| POST | `/api/v1/orders/{id}/confirm` | `ManagerUser` | Tasdiqlash: `DRAFT → TECHNICAL_REVIEW` — buyurtma texnologga o'tadi; `amount` (narx) kiritilgan bo'lishi shart |
| POST | `/api/v1/orders/{id}/upload` | `TexnologUser` | `.project` fayl yuklash (TZ 6.3): faqat TECHNICAL_REVIEW holatida; kengaytma va hajm (`MAX_PROJECT_FILE_SIZE`) tekshiriladi; parse xatosi 422; TEMPLATE (GibLab'da optimizatsiya qilinmagan) fayl 422 aniq yo'riqnoma matni bilan rad etiladi (TZ 5.3.3); qayta yuklashda `wipe_previous_parse` oldingi parse natijalarini o'chiradi, `ingest_project` yangisini yozadi. Qo'lda chizilgan (nostandart) marshrutlar fayldan kelmaydi, shuning uchun `snapshot_custom_routes` ular fizik o'chirishdan OLDIN (mahsulot kodi, detal kodi) bo'yicha saqlaydi va `restore_custom_routes` yangi detallarga tiklaydi; tiklanganlar soni va yangi faylda topilmagan detallar javob matnidagi ogohlantirishlarga qo'shiladi |
| GET | `/api/v1/orders/{id}/matrix` | `StaffReadUser` | `OrderMatrix` — har detal (`MatrixPart`, `is_custom` bayrog'i bilan) va uning marshrut QADAMLARI (`RouteCell`, javobda `seq` bo'yicha tartiblangan) |
| PATCH | `/api/v1/orders/{id}/matrix` | `TexnologUser` | Matritsa tahriri (TZ 6.3.3): bosqich on/off (ARRA'ni o'chirib BO'LMAYDI — 403, faqat STANDART detalda), izoh, `is_custom` bayrog'i, nostandart marshrut (`route_codes`), soni o'zgartirish (`_resize_instances` fizik nusxalar va route summalarini moslashtiradi); faqat production'gacha — batafsil quyida |
| POST | `/api/v1/orders/{id}/machines` | `ManagerUser` | Bir postda bir nechta ish markazi bo'lsa manager tanlaydi (TZ 6.4.1); post/ish markazi mosligi tekshiriladi; **faqat AKTIV markaz** — TA'MIRDA/NOAKTIV bo'lsa 409 (ish bajariladigan joyi yo'q); faqat production'gacha |
| POST | `/api/v1/orders/{id}/start` | `ManagerUser` | Ishlab chiqarishga uzatish (TZ 6.4.2): `TECHNICAL_REVIEW → PRODUCTION`; `.project` yuklangan bo'lishi shart; **marshrutsiz detal bo'lsa 403** (quyida); `requires_assignment_choice` postlarda ish markazi tanlanmagan bo'lsa 403; tanlangan ish markazi route yozuvlariga muhrlanadi (terminal filtri uchun); WS `order.started` |
| POST | `/api/v1/orders/{id}/cancel` | `ManagerUser` | Bekor qilish (TZ 6.5): istalgan bosqichda (DELIVERED/CANCELLED dan tashqari); sabab majburiy; skan tarixi audit uchun saqlanadi; WS `order.cancelled` — terminallar vazifalarni DARHOL tashlaydi |
| POST | `/api/v1/orders/{id}/deliver` | `ManagerUser` | TOPSHIRILDI (TZ 10.3): faqat `COMPLETED → DELIVERED`; `delivered_at` avtomatik; WS `order.delivered` |
| GET | `/api/v1/orders/{id}/files/{file_id}` | `StaffReadUser` | Saqlangan faylni yuklab olish (project/SCX/hujjat), `FileResponse`; `media_type`: PROJECT/SCX uchun `application/xml`, qolganlari uchun `meta["content_type"]` (yo'q bo'lsa `application/octet-stream`) — anketa rasmlari `<img>` da ko'rsatilishi uchun shart |
| GET | `/api/v1/orders/{id}/files/scx.zip` | `StaffReadUser` | Barcha SCX fayllar bitta ZIP arxivda (`{number}_scx.zip`) — prisadkachi stanokka bittalab emas, bitta arxiv ko'chiradi; SCX yo'q bo'lsa 404 |
| POST | `/api/v1/orders/{id}/scx/regenerate` | `TexnologUser` | SCX fayllarni saqlangan `.project`dan qayta yaratadi (eski buyurtmani yangi nomlashga o'tkazish: har nusxa = QR nomli fayl; yozish `write_and_register_scx` — ingest bilan umumiy helper); detallar/marshrutlar/skanlarga TEGILMAYDI; `.project` diskda bo'lmasa 404 |
| GET | `/api/v1/orders/{id}/cutmap` | `StaffReadUser` | Kesish xaritasi holati (TZ 10.3) — admin-panel ko'rinishi va brauzer-print; terminal bilan umumiy `build_cutmap_state` (ARRA posti) |

Barcha mutatsiyalar `log_action` bilan audit qilinadi. `.project` parser qoidalari va cutmap tafsilotlari — `docs/09-mes-domain.md`.

### Marshrut matritsasi (detal × qadam)

Marshrut endi "qaysi postlar yoqilgan" to'plami emas, TARTIBLI qadamlar ketma-ketligi: `PartRoute` da `seq` (marshrutdagi o'rin, 1 dan) va `process_code` (`PROCESS_POSTS` — 1..16, aynan qaysi amal; bitta postda bir necha amal bor, masalan STOLYARKA da olti xil; 1–14 ni texnolog tanlaydi, 15 (qadoqlash) va 16 (TMO qabuli) — tizim qo'shadigan dum, `TAIL_CODES`). Bitta post marshrutda TAKRORLANISHI mumkin (kromka → prisadka → yana kromka), shuning uchun yagona indeks `(part_id, post_id)` dan `(part_id, seq)` ga ko'chdi (`ix_part_route_part_seq`, migratsiya `d5a1c93b70e2_part_route_seq.py`). Detal NOMI marshrutga umuman ta'sir qilmaydi — nomdagi `{ }` kodlari olib tashlangan.

Sxemalarga qo'shilgan maydonlar (`backend/app/schemas/orders.py`):

| Sxema | Maydon | Ma'nosi |
|---|---|---|
| `RouteCell` | `seq`, `process_code` | Bitta QADAM (avvalgi "katak" emas); `GET /matrix` qadamlarni `seq` bo'yicha tartiblab beradi |
| `MatrixPart` | `is_custom` | Nostandart detal bayrog'i (migratsiya `e7c4b208af13_part_is_custom.py`) — marshrutini texnolog o'zi chizadi |
| `MatrixPart` | `assembly_parent_id`, `assembly_children` | Yig'ma buyum: bu detal biriktirilgan ASOSIY detal va unga biriktirilgan mayda detallar ro'yxati (`[{"part_id", "code", "count"}]`) |
| `MatrixPartEdit` | `is_custom: bool \| None`, `route_codes: list[int] \| None`, `assembly_parent_id: int \| None` | Bayroqni almashtirish, qo'lda marshrut chizish va yig'ma buyumga biriktirish (`None` — bog'lamni uzish; maydon umuman yuborilmasa tegilmaydi — `model_fields_set`) |

`PATCH /matrix` qoidalari (bir so'rovda bir nechta detal tahriri, tartib: `note` → `count` → `is_custom` → `assembly_parent` → `route_codes` → `stages`):

- **`is_custom`** o'zgarsa marshrut manbasi almashadi: `True` da `AUTO` qadamlar YUMSHOQ o'chadi (`is_deleted=True`), `MANUAL` qadamlar tiklanadi; `False` da teskarisi. Qayta hisoblamay AYNAN tiklash sababi — fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi va texnolog qo'shgan qadamlar yo'qolardi.
- **`route_codes`** — jarayon kodlari TARTIB bilan (`[7, 11, 8]`), kod takrorlanishi mumkin (`[3, 6, 3]`), bo'sh ro'yxat marshrutni tozalaydi. Faqat `is_custom=True` detalga ruxsat (aks holda 403 "Marshrutni faqat nostandart detalga qo'lda chizish mumkin."). `PROCESS_POSTS` da yo'q kod → 403. Marshrut faqat ARRA yoki ROVER'dan boshlanadi (`_ROUTE_START_POSTS`) — chek shu ikki postda chiqadi, boshqasidan boshlansa detalda umuman QR bo'lmasdi. Kromka/oval BIRINCHI kelganda `per_instance` = qirralar soni, takror kelganda 1 (qirralar bir marta yopishtiriladi). Texnolog bergan kodlardan keyin marshrut DUMI avtomat qo'shiladi: anketada `packaging` bayrog'i bo'lsa UPAKOVKA (`process_code=15`), so'ng HAR DOIM TMO (16) — biriktirilgan mayda detalga (`assembly_parent_id` bor) dum QO'SHILMAYDI, u asosiy detal bilan birga qadoqlanadi va TMO ga alohida kirmaydi.
- **`assembly_parent_id`** (yig'ma buyum, migratsiya `c9d4e2f81a70`) marshrutdan OLDIN o'rnatiladi — dum shu bayroqqa qarab qo'shiladi yoki qo'shilmaydi; marshrut o'zgarmay faqat bog'lam o'zgarsa marshrut mavjud kodlardan qayta quriladi. `_set_assembly_parent` bir pog'onani majburlaydi (biriktirilgan detal o'zi asosiy bo'la olmaydi va aksincha — 403, o'ziga biriktirish ham 403), `_check_assembly_match` esa mayda detalning OXIRGI amali asosiy detal marshrutida ham borligini talab qiladi (403) — birikish aynan o'sha qadamda ro'y beradi.
- **`stages`** (post on/off) endi shu postdagi HAMMA qadamni birga yoqadi/o'chiradi — qadam-baqadam tahrir `route_codes` orqali. Yangi qadam qo'shilganda `seq` = detalning mavjud maksimumidan keyingisi, `process_code` = `DEFAULT_PROCESS_CODE[post.code]`. ARRA'ni o'chirish taqiqi faqat STANDART detalda: nostandartda ARRA majburiy emas (rover'dan boshlanadigan oqim).

**`POST /{id}/start` ikki tekshiruv bilan to'xtatadi:** (1) yoqilgan birorta qadami yo'q detallar `outerjoin` + `HAVING count = 0` bilan topiladi — 403 "Marshruti berilmagan detallar bor: …"; bunday detal na terminal navbatida, na TABLOda ko'rinadi, ya'ni buyurtma usiz jimgina "tayyor" bo'lardi. (2) marshrutning BIRINCHI qadami (eng kichik `seq`) Arra yoki Rover'da bo'lmasa — 403 "Marshruti Arra yoki Rover'dan boshlanmagan detallar bor: …"; chek faqat shu ikki postda chiqadi, boshqa postdan boshlangan detalga QR umuman bo'lmasdi. Ikkalasida ham birinchi 5 tasi `mahsulot_detal` ko'rinishida, qolgani "va yana N ta".

### Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i)

Qog'oz forma o'rniga. Menejer to'ldiradi, texnolog o'qib dizayn yasaydi.

**Saqlash:** `Order.survey` — nullable JSONB ustun (`backend/app/models/order.py`, migratsiya `backend/app/migrations/versions/a91c7d34f6e2_order_survey.py`). Butun anketa bir butun sifatida yoziladi: `PUT /survey` mavjud qiymatni to'liq almashtiradi, patch semantikasi yo'q.

**Sxemalar** (`backend/app/schemas/orders.py`) — barcha maydonlar tashqi kirish bo'lgani uchun chegaralangan:

| Sxema | Maydonlar | Chegaralar |
|---|---|---|
| `OrderSurvey` | `version` (default 1), `measured_at` (o'lchov sanasi), `measured_by`, `packaging`/`delivery`/`installation` (buyurtma darajasidagi bayroqlar, har biri default `False`), `rooms` | `rooms` ≤ 10; `measured_by` ≤ 120 belgi |
| `SurveyRoom` | `id` (frontend beradigan barqaror kalit), `name`, `furniture_types`/`furniture_other`, `shape` + `room_length`/`room_width`/`room_height`/`furniture_wall_length`, `corpus_materials`/`corpus_color`/`corpus_thickness`/`corpus_note`, `facade_materials`/`facade_color`/`countertop`/`facade_note`, `hardware_level`, `extra_services`, `note`, `walls`, `modules`, `total_running_meters`, `total_height` | `id` ≤ 40; `furniture_types` ≤ 20 element; material/xizmat ro'yxatlari ≤ 10; `note` ≤ 1000; `walls` ≤ 8; `modules` ≤ 40; `total_running_meters` 0..1000 |
| `SurveyWall` | `letter` (A..E), `length`, `height` | o'lchamlar mm da, `_Mm` = 0..50 000 |
| `SurveyModule` | `name`, `wall`, `width` (eni), `depth` (chuqurlik), `height`, `count`, `note` | `count` 1..999; `note` ≤ 200; o'lchamlar `_Mm` |

`packaging`/`delivery`/`installation` xona ichida emas, buyurtma darajasida: tsex va logistika butun buyurtma ustida ishlaydi (bitta mashina, bitta brigada), xona degan tushuncha ularga yetib bormaydi. Migratsiya kerak emas (`survey` — JSONB), lekin eski yozuvda bu kalitlar javobda umuman ko'rinmaydi: o'qish yo'li `OrderDetail.survey` ni xom dict sifatida beradi va `OrderSurvey` orqali qayta validatsiya qilmaydi — default `False` faqat YOZISHDA (yoki frontendda) paydo bo'ladi. `packaging` uchun eski ekvivalent yo'q; `delivery`/`installation` esa ilgari xona ichida, `extra_services` dagi `yetkazish`/`montaj` kodlari edi — anketa sahifasi yuklashda ularni buyurtma bayrog'iga ko'taradi va xona ro'yxatidan olib tashlaydi.

**Diqqat — to'liq almashtirish oqibati:** `OrderSurvey` ning har bir maydonida default bor, shuning uchun body'da tushib qolgan kalit uchun 422 CHIQMAYDI — maydon jimgina defaultiga (bayroqlar uchun `False`) qaytadi; `model_config = ConfigDict(extra="ignore")` esa boshqa narsani qiladi: noto'g'ri nomlangan yoki notanish kalitni indamay tashlab yuboradi. Klient har saqlashda anketaning butun holatini (shu jumladan bu uch bayroqni) qaytarib yuborishi shart.

Variant kodlari (`ldsp`, `mdf`, `akril`…) backend'da qat'iy ro'yxat emas — matnga aylantirish `frontend/src/lib/anketa.ts` da; yangi variant qo'shishda migratsiya kerak emas. Mijoz ma'lumotlari `Client` da, narx/avans/muddat `Order` da — anketada takrorlanmaydi.

**Xona rasmlari** alohida jadval talab qilmaydi: `OrderFile(kind=FileKind.DOCUMENT, meta={"room_id": ..., "content_type": ...})`, disk yo'li `uploads/survey/{order_id}/{uuid4().hex}{ext}`. Shu sabab `OrderFileRead` ga `meta` maydoni qo'shilgan.

Yuklash cheklovlari (`orders.py` dagi konstantalar):

- `_ROOM_PHOTO_TYPES` — faqat `image/jpeg` → `.jpg`, `image/png` → `.png`, `image/webp` → `.webp`; boshqasi 422 "Faqat JPG, PNG yoki WEBP rasm qabul qilinadi."
- `MAX_ROOM_PHOTO_SIZE = 5 MB` — oshsa 422 (telefon surati odatda 2–4 MB).
- `MAX_ROOM_PHOTOS = 6` — bitta `room_id` uchun; oshsa 422.

**Yetim rasm tozalash:** `save_order_survey` anketani yozgach, `room_id`si kelgan `rooms` ro'yxatida yo'q bo'lgan `DOCUMENT` fayllarni topadi (JSONB `meta ? 'room_id'` + `meta->>'room_id' NOT IN (...)`), diskdan `unlink` qiladi (`OSError` yutiladi) va `is_deleted`/`deleted_at` belgilaydi. Ya'ni xona anketadan olib tashlansa uning rasmlari ham yo'qoladi.

**Bog'lanishlar:** `backend/app/schemas/orders.py`, `backend/app/models/order.py` (`Order.survey`), `backend/app/services/giblab` (`ParseError`, `parse_project`; `ingest.py` dan `ingest_project`, `wipe_previous_parse`, `write_and_register_scx`), `backend/app/core/ws.py` (`ws_manager`), `backend/app/api/routes/terminal.py` (`build_cutmap_state`), frontend tomoni: `frontend/src/routes/_layout/anketa.$orderId.tsx`, `frontend/src/lib/anketa.ts`.

---

## `backend/app/api/routes/audit.py` — Audit jurnali

**Maqsadi:** Barcha modullar yozgan audit yozuvlarini o'qish. Yozish API orqali emas — har mutatsion endpoint o'z tranzaksiyasida `crud.log_action` chaqiradi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/audit-logs/` | `AdminUser` | `Paginated[AuditLogRead]`; filtrlar: `module`, `action`, `user_id`, `q` (xabar bo'yicha `ilike` qidiruv), `date_from`/`date_to` — kun chegaralari Asia/Tashkent vaqtida (`TASHKENT_TZ`; naive-UTC bo'lsa "bugun" filtri 00:00–05:00 yozuvlarni yo'qotardi) |

`AuditLogRead` sxemasi `backend/app/schemas/audit.py` da: user/employee, modul, amal, entity, xabar, `meta` (JSON), IP, vaqt, hamda `user_name`/`employee_name` ("kim" ustuni uchun `outerjoin` orqali — alohida so'rovsiz).

**Bog'lanishlar:** `backend/app/schemas/audit.py`, `backend/app/models` (`AuditLog`), `backend/app/crud` (`log_action` — yozuvchi tomon), `backend/app/core/config.py` (`TASHKENT_TZ`).

---

## `backend/app/api/routes/terminal.py` — Operator terminali (TZ 8)

**Maqsadi:** Tsexdagi 17" touch-terminal API: kontekst, beyjik-smena, vazifalar navbati, ARRA/ROVER kesish xaritasi, yorliq chop etish, SCX fayllar. Barcha endpointlar `require_roles(UserRole.TERMINAL, *POST_ROLES)` ortida. Ish markazi+post konteksti `TerminalCtx` dependency'si orqali keladi (`_terminal_ctx` → `resolve_terminal`, `ScanRejected` → 422 `{code, message}` — `_scan_error()` helper) — u faqat kontekstga muhtoj route'larga qo'yilgan, yorliq va fayl route'lariga ATAYLAB emas: ish markazisiz terminal foydalanuvchisi ham yorliq chop eta olishi kerak. `resolve_terminal` operator rollarida postni rolning o'zidan oladi (ish markazi — `user.machine_id`, bo'lmasa postning birinchi ish markazi), TERMINAL akkauntda esa `user.machine_id`dan.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/terminal/context` | terminal/operator | Ish markazi+post konteksti, OCHIQ smenalar ro'yxati (`crew` — brigada) va OCHIQ TO'XTASH (`stop`, bo'lmasa `null` — OEE); muddati o'tganlari shu so'rovda yopiladi (`crew_sessions` → `expire_if_stale`). Rolidan qat'i nazar smena AVTOMATIK ochilmaydi: yagona yo'l — `POST /terminal/session` (beyjik skani yoki ismni bosish) yoxud `/login/badge`. Ilgari operator rollarida "login = smena" shoxi bor edi, u soxta mirror hodim yozuvi bilan birga olib tashlangan (`c7e2b4f81d39`) |
| GET | `/api/v1/terminal/stop-reasons` | terminal/operator | Faol to'xtash sabablari (`is_active`, `order_index` bo'yicha) — monoblokdagi tanlash ro'yxati |
| POST | `/api/v1/terminal/stop` | terminal/operator | To'xtashni boshlaydi (`reason_id`, ixtiyoriy `note`). Ochig'i bo'lsa AVVAL yopiladi — sababni almashtirish odatiy holat ("material yo'q" bilan boshlanib, keyin "nosozlik" bo'lib chiqadi); XUDDI SHU sabab bo'lsa mavjudi qaytariladi, dublikat ochilmaydi. `employee_id` — ish markazidagi langar smena egasi, hech kim bo'lmasa NULL (stanok operatorsiz ham to'xtaydi) |
| POST | `/api/v1/terminal/stop/end` | terminal/operator | Ochiq to'xtashni yopadi; ochig'i bo'lmasa 404 |
| GET | `/api/v1/terminal/employees` | terminal/operator | "Kim ishlayapti?" ro'yxati — shu postga biriktirilgan FAOL hodimlar. Monoblok TERMINAL hisobi bilan allaqachon kirgan, ya'ni ro'yxat ochiq emas. Ismni bosish AUTENTIFIKATSIYA emas, ATRIBUTSIYA: qurilma tanitilgan, endi kim ishlayotgani yoziladi |
| POST | `/api/v1/terminal/session` | terminal/operator | Smenani ochadi (TZ 8.2.2). IKKI yo'l, natijasi bir xil: `badge_id` (skaneri bor post — bitta harakat) yoki `employee_id` (ekrandagi "Kim ishlayapti?" ro'yxatidan ism). `join=true` — BRIGADAGA qo'shiladi (ARRA da ikki kishi birga ishlaydi); sukut bo'yicha ALMASHTIRADI, ya'ni yakunlashni unutish xavfsiz tomonga og'adi. Bir odam ikki marta qo'shilmaydi — mavjud smenasi qaytariladi. Xatolar 422 `{code: "E006", message}` — beyjik topilmadi / nofaol / bu postga biriktirilmagan; WS `session.started` |
| POST | `/api/v1/terminal/session/end` | terminal/operator | Smenani yakunlaydi. `?employee_id=` berilsa FAQAT o'shaniki — brigadaning qolgani ishlayveradi (biri ketib, ikkinchisi qolishi odatiy hol); berilmasa hammasi. Aktiv smena bo'lmasa 404; WS `session.ended` |
| GET | `/api/v1/terminal/orders` | terminal/operator | Shu postga tegishli aktiv buyurtmalar (post sahifalari tanlagichi). Tartib: prioritet (`URGENT→HIGH→MEDIUM→LOW`, `priority_rank` `case()`), keyin deadline (nulls oxirida), keyin id. `done`/`total` post semantikasida: ARRA — chek chiqarilgan YOKI skan qilingan nusxalar, **faqat ARRA marshruti bor detallar bo'yicha** (aks holda arradan o'tmaydigan detalning cheki — masalan roverchi o'zi chiqargani — arra hisobini jamidan oshirib yuborardi va listlar hali kesilmagan proyekt ro'yxatdan yo'qolardi); hammasi chiqarilgan buyurtma ro'yxatdan TUSHADI; KROMKA — detal bo'yicha (nusxaning hamma tomoni skan bo'lsa "qilingan"); boshqa postlarda skan yig'indisi. Kartada (`TerminalOrderCard`) `materials`, `sheets_total`, `has_cutmap` |
| GET | `/api/v1/terminal/orders/{id}/cutmap` | terminal/operator | ARRA/ROVER kesish xaritasi (TZ 7.1.7): ROVER ham ochadi — marshruti arradan boshlanmagan detal butun listi bilan frezerda kesiladi, ya'ni roverchiga ham joylashuv kerak; shu ikkisidan boshqa postda 403 ("Kesish xaritasi faqat arra va rover postida ko'rsatiladi."). Har post O'Z skanlarini ko'radi (`done` — `build_cutmap_state` ga berilgan `post_id` bo'yicha), listlarni esa frontend `arra_route` bilan ajratadi; katak holati serverda — terminal qayta yonganda saqlanib qoladi. `CutmapInstanceState.custom` — detal NOSTANDART (`Part.is_custom`): marshrutini texnolog qo'lda chizgan va u arradan boshlanmasligi mumkin, shuning uchun xaritada binafsha chiqadi (chek chiqarilgach yashil) |
| GET | `/api/v1/terminal/orders/{id}/kromka` | terminal/operator | KROMKA/OVAL sahifasi (boshqa postda 403): shu post marshrutidagi qadamlar, har nusxada `done` (post skanlari) / `sides` (`per_instance` — KROMKA marshrutda birinchi kelganda qirralar soni, takrorida 1; OVAL da doim 1), `process_code` (3 — kromka, 4 — fasat kromka, 5 — oval), `arra_passed` (chek chiqarilgan yoki ARRA skan bor) |
| GET | `/api/v1/terminal/orders/{id}/prisadka` | terminal/operator | CNC sahifasi — PRISADKA va ROVER (boshqa postda 403), javob `PrisadkaOrderState`: detallar + har detalning SCX fayllari (`PrisadkaFile {id, filename}`), `arra_route` (marshrutida yoqilgan ARRA bormi — yo'q bo'lsa QR chek shu sahifadan chiqariladi, roverdan boshlanadigan oqim), `done_qrs` (shu postda to'liq skan qilingan nusxalar QR'lari), `instances` (`PrisadkaInstance`: `instance_id`/`qr_text`/`label_printed`/`done`), `project_name` (frontend shu nom bilan papka ochadi) |
| GET | `/api/v1/terminal/orders/{id}/queue` | terminal/operator | POST NAVBATI nusxa darajasida (BOYOQ, STOLYARKA) — `PostQueueState`. Postga bog'lanmagan: kontekstdagi postni oladi. Har nusxada `ready` (oldingi qadamlar shu NUSXADA tugadimi — `pachka.instance_stages`), `stage` (ishi TUGAGAN post nomi — detal jismonan qayerda turibdi), `done` (shu qadam yopilgan), `material` (bo'yoqchi uchun RANG), `note` (texnolog izohi), `process_code` (stolyarkada olti xil amal) va `assembly` (yig'ma buyumga biriktirilgan mayda detallar). Frontend `ready=false` qatorlarni KO'RSATMAYDI — ularni skanerlab bo'lmaydi (E004) |
| GET | `/api/v1/terminal/qr/{qr_text}/order` | terminal/operator | QR qaysi PRODUCTION buyurtmaga tegishligini topadi — `QrOrderRef` (`order_id`, `order_number`); picker'da skan qilinsa terminal o'sha proyektni o'zi ochadi |
| POST | `/api/v1/terminal/labels/{instance_id}` | terminal/operator | YORLIQ CHOP ETISH (TZ 7.1.4): ARQ `print_label` navbatiga qo'yiladi (bridge-agent/GoDEX); `label_printed_at` belgilanadi; WS `label.printed`. ARRA UI'da chiqarilgan katak YASHIL = "kesildi"; qayta chop etish frontendda bloklanadi (avval bekor qilish kerak). **KESISH POSTLARIDA CHOP ETISH = SKAN**: ARRA'da doim, ROVER'da esa detalning marshrutida ARRA bo'lmasa, shu so'rovda skan ham avto-yoziladi (`record_scan` + `finalize_scan`, `client_event_id="cutprint-<instance_id>-<unix_ts>"`, manba " (chek chiqarish bilan)"). Vaqt tamg'asi ataylab: doimiy `cutprint-<id>` bo'lganda chek bekor qilinib qayta chiqarilsa idempotentlik tekshiruvi eski (bekor qilingan) qatorni topib `duplicate` qaytarardi va `total_done` o'smasdi — eski shakl endi faqat tarixiy yozuvlarda uchraydi. **ARRA terminalida marshrutida yoqilgan ARRA qadami yo'q detalga chek UMUMAN chiqarilmaydi** — 422 `{code: "E001", message: "Bu detal roverda kesiladi — chekni rover terminalidan chiqaring."}` (u rover terminalidan chiqariladi; shu qoida "chek chiqarilgan = kesilgan" degan arra statistikasini saqlaydi). Ish markazi aniqlanmagan terminalda chek chiqadi, lekin avto-skan o'tkazib yuboriladi. Busiz `PartRoute.total_done` o'smasdi: buyurtma COMPLETED bo'lmasdi va qat'iy tartibda keyingi POSTLARNING HAMMASI E004 bilan rad etilardi (arrachi xarita ochiqda alohida skan qilmaydi — skan maydoni yashirin). Skan rad etilsa (`ScanRejected`) jim rollback, chek baribir chiqadi |
| DELETE | `/api/v1/terminal/labels/{instance_id}` | terminal/operator + manager/texnolog | Chekni bekor qilish: `label_printed_at = None`, WS `label.cancelled`. Chop etish YOZGAN skan ham bekor qilinadi (`client_event_id` `cutprint-`/`rvprint-` bo'yicha tanlanadi) va `total_done` qaytariladi — aks holda katak yashil bo'lib qolar, qadam hisobi esa oshgan holida qolardi; operator QO'LDA qilgan skanga tegilmaydi. Terminalda long press (~600ms) + tasdiq dialogi; admin webdagi xaritada detal kartochkasidagi tugma (proyekt ARRA ro'yxatidan tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi). UI sharti faqat `label_printed_at` — chop etish skan yozgani uchun `done` doim true bo'ladi |
| GET | `/api/v1/terminal/labels/{instance_id}.png` | terminal/operator | Yorliqning PNG ko'rinishi (`load_label_data` + `render_label_png`) — brauzerdan istalgan printerga chop etish uchun (GoDEX shart emas); `Response(media_type="image/png")` |
| GET | `/api/v1/terminal/files/{file_id}` | terminal/operator | SCX faylni stanok brauzeriga yuklab olish (TZ 12.5) — har safar yangidan beriladi |

### Yorliq chop etish zanjiri

```
terminal (POST /terminal/labels/{instance_id})
  → arq: app.tasks.print_label(instance_id)
      load_label_data(db, instance_id) → LabelData
      render_label_png(data)   → PNG (80×60 mm, 203 dpi, 1-bit) → base64
  → Redis LPUSH mes:print:queue
      job = {"type": "print", "instance_id": ..., "png": <base64>}
  → WS /api/v1/ws/bridge (brpop + ack)
  → bridge-agent → print-queue.jsonl (durable) → Windows GDI → USB GoDEX
```

GoDEX G500-U faqat USB bilan ulanadi — printerda tarmoq porti yo'q, shuning uchun backend printerga hech qachon to'g'ridan murojaat qilmaydi: `print_label` yagona ish sifatida Redis navbatiga qo'yadi. Job JSON'da faqat uchta maydon: `type`, `instance_id`, `png`. PNG printer dialektiga bog'liq emas (QR kutubxona bilan chiziladi), shuning uchun backend hech qanday printer tili generatsiya qilmaydi.

`print_label` qaytaradigan qiymatlar: `queued:<id>` (Redis navbatiga qo'yildi), `skip:<id>` (nusxa topilmadi), `lost:<id>` (arq kontekstida Redis yo'q).

Agent tomoni (`bridge-agent/agent.py`) — bitta chiqish yo'li: `send_to_printer(png_b64)` → `_print_png_gdi` — PNG Windows drayveri orqali chiziladi (win32ui + PIL, DEVMODE 80×60 mm ga majburlanadi). Printer avtomatik topiladi: `_detect_printer()` nomida "godex" bor lokal Windows printerini qidiradi, `PRINTER_NAME` env faqat qo'lda override uchun. Agent env'lari: `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`, `SCAN_FORWARD` (default `1`; `0` — skan-forvard tinglovchisini o'chiradi). Agent faqat printer ulangan kompyuterga o'rnatiladi — menejer, texnolog va boshqa post terminallariga hech narsa kerak emas.

**Bog'lanishlar:** `backend/app/schemas/terminal.py`, `backend/app/services/scanning.py` (`resolve_terminal`, `crew_sessions`, `badge_employee`, `open_badge_session`, `end_session`, `record_scan`, `finalize_scan`, `ScanRejected`), `backend/app/services/labels.py` (`LabelData`, `load_label_data`, `_n`, `render_label_png` — 80×60 mm, 203 dpi, 1-bit), `backend/app/tasks` (`print_label`, `PRINT_QUEUE_KEY`), `backend/app/core/ws.py`, `bridge-agent/agent.py`.

---

## `backend/app/api/routes/pachka.py` — Qadoqlash (Upakovka)

**Maqsadi:** Qadoq yaratish, detallarni qadoqqa skanerlash, yakunlash. Kontekst `PackCtx`
(`_pack_ctx`) — faqat UPAKOVKA postida ochiladi, boshqa postda 403. Qadoqni ALGORITM emas,
qadoqlovchi yig'adi: tizim taxminiy og'irlikni (`DENSITY = 700.0` kg/m³ × hajm) faqat KO'RSATADI.

| Metod | Path | Izoh |
|---|---|---|
| GET | `/api/v1/pachka/orders/{id}` | Qadoqlash holati: qadoqlar (tarkib + og'irlik) va hali qadoqlanmagan nusxalar (`ready` — `instance_stages` bo'yicha, tayyorlari tepada) |
| POST | `/api/v1/pachka/orders/{id}` | Yangi qadoq. Kod `PK-{buyurtma}-{NN}` — O'CHIRILGANLAR ham sanaladi, aks holda eski chek bilan yangi qadoq bir xil QR berardi |
| POST | `/api/v1/pachka/{id}/scan` | Detalni qadoqqa. Bu AYNI PAYTDA marshrutning UPAKOVKA qadami (`record_scan_at`, `client_event_id="pack-{pachka}-{instance}"`) — qat'iy tartib shu yerda ham ishlaydi, ya'ni yopiq qadoq ichida chala detal bo'lishi mumkin emas. Boshqa buyurtma detali / allaqachon qadoqlangan nusxa 422; WS `pachka.item` |
| DELETE | `/api/v1/pachka/{id}/items/{instance_id}` | Xato skanni qaytarish: nusxa qadoqdan chiqadi VA UPAKOVKA skani bekor bo'ladi (`total_done--`) — aks holda detal boshqa qadoqqa tushib ikki marta sanalardi |
| POST | `/api/v1/pachka/{id}/close` | Yakunlash: status CLOSED + arq `print_pachka_label`. Bo'sh qadoq yakunlanmaydi; WS `pachka.closed` |

`instance_stages(db, order, post)` shu faylda — qadoqlash, TMO va post navbati ekranlari
uchun umumiy (09-mes-domain.md §3.2).

---

## `backend/app/api/routes/tmo.py` — TMO (Tayyor Mahsulot Ombori)

**Maqsadi:** Marshrutning ENG OXIRGI qadami — QABUL va TOPSHIRISH. Kontekst `WhCtx` (`_wh_ctx`),
faqat TMO postida.

| Metod | Path | Izoh |
|---|---|---|
| GET | `/api/v1/tmo/orders/{id}` | Qadoqlar (`accepted_count`/`item_count`, `shipped_at`), qabul qilinmagan nusxalar (`ready` + `stage` — ishi TUGAGAN post, omborchi detalni o'sha yerdan topadi), `packaging`, `total`/`accepted` |
| POST | `/api/v1/tmo/orders/{id}/accept` | QABUL. QR `PK-` bilan boshlansa — qadoq: ichidagi HAMMA nusxa bitta skanda qabul qilinadi (omborchi qadoqni ochmaydi); aks holda bitta detal. Ochiq (yakunlanmagan) qadoq qabul qilinmaydi. `client_event_id="wh-{order}-{qr}"` — idempotent; WS `tmo.accepted` |
| POST | `/api/v1/tmo/orders/{id}/ship` | Qadoqni mijozga topshirish (QR skani yoki ro'yxatdagi tugma — ikkisi ham kod yuboradi). To'liq qabul qilinmagan qadoq topshirilmaydi: aks holda detal TMO ga kirmasdan chiqib ketardi; WS `tmo.shipped` |
| POST | `/api/v1/tmo/orders/{id}/deliver` | Butun buyurtmani topshirish — qadoqsiz buyurtma uchun. Qabul qilinmagan detal yoki topshirilmagan qadoq bo'lsa 403; WS `tmo.delivered` |

Hammasi qabul qilinib topshirilgach buyurtma `DELIVERED` bo'ladi (`_deliver_if_done`).

---

## `backend/app/api/routes/scans.py` — Skan ro'yxatga olish va bekor qilish (TZ 8.4–8.6)

**Maqsadi:** Terminaldagi QR skanlarni qayd etish/bekor qilish. Rol: `require_roles(UserRole.TERMINAL, *POST_ROLES)`. Butun domen logikasi `app/services/scanning.py` da — endpoint yupqa adapter.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/scans/` | terminal/operator | `record_scan` chaqiradi; rad etilsa 422 `{code, message}` (**E001–E009** xato kodlari, §09 §3.0); muvaffaqiyatda WS eventlar publish qilinadi; javob `ScanResult`: `scan_id`, `duplicate`, `qoldiq`, `scx_file_ids`, `project_name` (avto-SCX proyekt nomli papkaga tushishi uchun), `order_stage_completed`, `order_completed` va detal ma'lumotlari; rad etilgan urinish ham `log_rejected_scan` helper (`services/scanning.py`) orqali `scan` modulida audit logga yoziladi |
| DELETE | `/api/v1/scans/{scan_id}` | terminal/operator | Skanni bekor qilish (undo) — `cancel_scan`; hisoblagichlar qaytariladi, WS eventlar publish qilinadi; javob `ScanHistoryItem` |

Skan qabul qilish qoidalari (marshrut/ketma-ketlik tekshiruvi, dublikat) va xato kodlari jadvali — `docs/09-mes-domain.md` §3 va §3.0 da.

**Bog'lanishlar:** `backend/app/services/scanning.py` (`record_scan`, `cancel_scan`, `finalize_scan`, `log_rejected_scan`, `ScanRejected`), `backend/app/schemas/terminal.py` (`ScanRequest`, `ScanResult`, `ScanHistoryItem`), `backend/app/core/ws.py`.

---

## `backend/app/api/routes/tablo.py` — TABLO (tsex televizori, TZ 9)

**Maqsadi:** Buyurtmalar × bosqichlar jonli matritsasi. Read-only, har qanday login qilgan foydalanuvchi/qurilma (TABLO akkaunt ham, ofis ham).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/tablo/matrix` | login (har qanday) | `TabloMatrix`: postlar ro'yxati + PRODUCTION buyurtmalar va oxirgi `COMPLETED_WINDOW` (30 kun) ichida yakunlanganlar; har katak `StageAgg` — done/total va post birligidagi hajm (`part_volume`: m²/metr/dona). **Chegara shart**: COMPLETED holatdan faqat manager qo'lda "topshirildi" bosgandagina chiqiladi, ya'ni chegarasiz har bir unutilgan buyurtma taxtada abadiy qolib, tsex ekranini sekinlashtirardi (o'lchov: 100 buyurtmada 28 ms → 1.9 s). Marshrutlar ORM obyekti sifatida emas, faqat kerakli ustunlar bilan o'qiladi |
| GET | `/api/v1/tablo/orders/{id}` | login (har qanday) | Drill-down (TZ 9.5 SONI NAZORATI): har detal × bosqich done/total. Katakcha post bo'yicha, marshrut esa qadamli — bitta post takrorlansa (kromka → prisadka → kromka) qadamlar QO'SHILADI, aks holda oxirgi qadam oldingisining ustiga yozilib bajarilgan ish yo'qolardi |

Javob sxemalari `backend/app/schemas/tablo.py` da: `TabloMatrix` (`posts` — typed `TabloPostCol` ro'yxati), `TabloOrderRow`, `StageAgg`, `TabloOrderDetail`, `TabloPartRow`.

**Bog'lanishlar:** `backend/app/schemas/tablo.py`, `backend/app/services/metrics.py` (`part_volume`), `backend/app/models` (`Order`, `PartRoute`, `Post`).

---

## `backend/app/api/routes/reports.py` — Hisobotlar (TZ 11) va dashboard statistikasi

**Maqsadi:** Boshqaruv hisobotlari. Rol: `require_roles(MANAGER, DIRECTOR)` (admin/superuser har doim o'tadi). Uch hisobot default JSON qaytaradi, `?format=xlsx` bilan Excel fayl stream qilinadi (TZ 11.4, `services/excel.xlsx_response`). Sana oralig'i berilmasa — oxirgi 30 kun, chegaralar Asia/Tashkent bo'yicha inklyuziv kunlar (`TASHKENT_TZ`, `app/core/config.py`). Javob sxemalari `backend/app/schemas/reports.py` da (8 model: `ProductivityReport`, `OrdersReport`, `MaterialsReport`, `DashboardStats` va ularning qator modellari).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/reports/productivity` | manager/direktor | Hodim mahsuldorligi (TZ 11.1.1): skan soni, faol kunlar, kuniga/soatiga o'rtacha; `?format=xlsx` |
| GET | `/api/v1/reports/orders` | manager/direktor | Buyurtmalar holati (TZ 11.2): holat, muddatlar, `overdue` belgisi (muddat o'tgan tugallanmaganlar), bekor sababi; `?format=xlsx` |
| GET | `/api/v1/reports/materials` | manager/direktor | Material sarfi (TZ 11.3): `Order.material_usage` JSONB'dan agregatsiya (`project_loaded_at` oralig'ida, CANCELLED chiqariladi); `?format=xlsx` |
| GET | `/api/v1/reports/oee` | manager/direktor | Ish markazlari bo'yicha **Availability** va to'xtalishlar tahlili (`?post_id` bilan filtrlanadi). Hisob `services/oee.py: machine_availability` da. NOAKTIV ish markazlari ham ro'yxatda: ta'mirdagi stanok aynan eng katta yo'qotish manbai bo'lishi mumkin. `availability=null` — o'sha davrda reja umuman bo'lmagan, "0%" yolg'on bo'lardi. Excel eksporti YO'Q: hisobot ichma-ich (ish markazi → sabablar) va yassi jadval ma'noni yo'qotardi |
| GET | `/api/v1/reports/dashboard` | manager/direktor | Dashboard (TZ 10.2.1): har ish markazi uchun navbat (qolgan skanlar/hajm), quvvat va prognoz soatlar (TZ 4.3: navbat/quvvat), bugungi skanlar; faqat JSON |

**Bog'lanishlar:** `backend/app/schemas/reports.py`, `backend/app/services/excel.py` (`xlsx_response`), `backend/app/services/metrics.py` (`part_volume`).

---

## `backend/app/api/routes/bridge_agents.py` — Printer agentlari va pairing (TZ 2.2.2)

**Maqsadi:** Printerli kompyuterdagi bridge-agent'ni serverga ulash (pairing) — podpiska modeli uchun: admin panelda kod beriladi, agent kodni doimiy tokenga almashtiradi. Serverga SSH kirish ham, `.env` tahriri ham kerak emas. Har printerning o'z tokeni bor — birini bekor qilish qolganlariga tegmaydi.

Router `/api/v1/bridge-agents` prefiksi bilan **himoyasiz** ulanadi (`/pair` chaqirilganda agentda sessiya yo'q), shuning uchun admin endpointlarning har biri o'z signaturasida `AdminUser` talab qiladi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/bridge-agents/` | `AdminUser` | Agentlar ro'yxati (`BridgeAgentRead`: `id`, `name`, `paired`, `pair_code`, `pair_expires_at`, `last_seen_at`, `created_at`, `machine_id`, `machine_name`, `version`, `can_print`); `pair_code` faqat muddati o'tmagan bo'lsa qaytariladi, aks holda `null` |
| PATCH | `/api/v1/bridge-agents/{id}` | `AdminUser` | Ish markazi bog'lash (`machine_id` — skan-forvard uchun) va chek-chiqarish belgisi (`can_print`); maydonlar alohida yuboriladi (`exclude_unset` — berilmagani tegilmaydi); audit `machine_linked` / `can_print_changed` |
| POST | `/api/v1/bridge-agents/` | `AdminUser` | 201; agent yaratiladi va **bir martalik 8 belgili ulanish kodi** beriladi (`PAIR_TTL` = 15 daqiqa); audit `created` |
| POST | `/api/v1/bridge-agents/{id}/code` | `AdminUser` | Yangi ulanish kodi (kod eskirgan yoki kompyuter almashgan holat); `token_hash` tozalanadi — eski kompyuter keyingi ulanishda rad etiladi; audit `code_regenerated` |
| DELETE | `/api/v1/bridge-agents/{id}` | `AdminUser` | Soft-delete; jonli WebSocket ham uziladi (`touch_agent()` 5 daqiqada bir tekshiradi); audit `deleted` |
| POST | `/api/v1/bridge-agents/pair` | **Yo'q (ochiq)** | Agent bir martalik kodni doimiy tokenga almashtiradi; javob `BridgePairResponse` (`token`, `name`); audit `paired` (`user_id=None`); WS `bridge.paired` — admin sahifasi pollingsiz yangilanadi |
| POST | `/api/v1/bridge-agents/scan` | Agent tokeni (`Authorization: Bearer`) | Skan-forvard (TZ 12.5): stanok skaneri o'qigan QR agent orqali MES'ga yoziladi — agentga bog'langan ish markazining AKTIV sessiyasi nomidan (`record_scan_at` + `finalize_scan`, odatdagi skan yo'li); ish markazi bog'lanmagan / sessiya yo'q — 409; sessiya terminal bilan bir xil `expire_if_stale` tekshiruvidan o'tadi — 12 soatdan (`SESSION_MAX_HOURS`) eskirgan smena yopiladi va 409 qaytadi; rad etilgan skan ham `log_rejected_scan` bilan `scan`/`rejected` audit logga tushadi, javob `ScanResult` |

**Ulanish kodi:** `_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"` — I/L/O/0/1 yo'q, telefonda aytganda adashtirmaydi. 31 belgi × 8 uzunlik (`_CODE_LEN = 8`) = 31⁸ ≈ 8.5·10¹¹ kombinatsiya, 15 daqiqalik oynada brute-force amalda imkonsiz.

**Pairing xavfsizligi** (`POST /pair`):

- Atomik `UPDATE ... RETURNING` — bir kodni ikki kompyuter bir vaqtda yuborsa faqat bittasi yutadi (kod shu tranzaksiyada `NULL` ga o'tadi).
- Kod topilmasa ham, muddati o'tgan bo'lsa ham **bitta umumiy xato**: 400 "Ulanish kodi noto'g'ri yoki muddati o'tgan." — kodning bor-yo'qligi oshkor qilinmaydi.
- Kirishda `-` va bo'shliqlar olib tashlanadi, harflar katta registrga o'tkaziladi (qo'lda kiritishga bardosh).
- Token `secrets.token_hex(24)` bilan yaratiladi va **faqat shu javobda** beriladi; bazada `token_hash` sifatida sha256 xeshi qoladi.

Agent exe'ni yuklab olish endpointi YO'Q (2026-08-02 da olib tashlangan — diskdagi eski exe'ni berib adashtirardi): exe qo'lda tarqatiladi (`bridge-agent/README.md`).

**Agent tomoni** (`bridge-agent/agent.py`): PyInstaller onefile `mebelix-agent.exe` — tsex kompyuteriga Python o'rnatish shart emas. `_load_dotenv()` config'ni shu tartibda o'qiydi: env var > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`. `_pair()` (import paytida chaqiriladi) birinchi ishga tushishda kichik tkinter oynasi (`_pair_dialog()`) orqali server manzili va ulanish kodini so'raydi, `_exchange()` ularni `POST /pair` ga yuboradi va olingan tokenni `%APPDATA%\MebelixAgent\.env` ga yozadi; kod noto'g'ri bo'lsa oyna xato matni bilan qayta ochiladi. `BRIDGE_TOKEN` allaqachon bor bo'lsa `_pair()` darhol qaytadi — hech narsa so'ralmaydi; aks holda oyna har doim ochiladi, `stdin` tty bo'lishi shart emas (exe `--noconsole` bilan quriladi, konsol umuman yo'q). Faqat tkinter ishlamagan muhitda (dev/Linux) `_pair_console()` zaxira sifatida ishlaydi, u ham kod ololmasa `SystemExit("Ulanish bekor qilindi.")` — agent jim davom etmaydi, xato oynasini ko'rsatib to'xtaydi. Qolgan hammasi o'zgarmagan — printer avto-topiladi, `print-queue.jsonl` durable navbat, `_print_png_gdi` chiqish yo'li.

**Skan-forvard klienti ham agentning o'zida** (TZ 12.5 ning ikkinchi yarmi): `pynput` klaviatura tinglovchisi stanok skanerining wedge kiritishini ushlaydi (Enter bilan yakunlangan 6–64 belgili satr, belgi tezligi <50 ms — odam terishi bunday tez emas) va uni agent tokeni bilan `POST /bridge-agents/scan` ga yuboradi. `SCAN_FORWARD=0` env o'chiradi; `pynput` o'rnatilmagan bo'lsa o'zi jim o'chadi.

**Bog'lanishlar:** `backend/app/schemas/bridge_agents.py` (`BridgeAgentCreate`, `BridgeAgentRead`, `BridgePairRequest`, `BridgePairResponse`), `backend/app/models/bridge_agent.py` (`BridgeAgent`), migratsiya `backend/app/migrations/versions/d5e81a24c3b7_bridge_agent_pairing.py`, `backend/app/crud` (`crud_bridge_agents`, `log_action`), `backend/app/api/routes/ws.py` (`/ws/bridge` shu tokenni tanidi), `bridge-agent/agent.py`.

---

## `backend/app/api/routes/ws.py` — WebSocket endpointlari

**Maqsadi:** Ikki WebSocket kanal. Router darajasida auth YO'Q — WebSocket'da HTTP dependency ishlamaydi, autentifikatsiya har endpoint ichida.

| Endpoint | Auth | Izoh |
|---|---|---|
| WS `/api/v1/ws/events` | `?token=` query yoki access cookie | Brauzer klientlari (TZ 2.3). Token HTTP oqimidagi bilan bir xil funksiya — `deps.resolve_user` — orqali tekshiriladi (`verify_token` + `is_active` + `token_version`); muvaffaqiyatsiz bo'lsa **4401** (`WS_CLOSE_UNAUTHORIZED` konstantasi) kod bilan yopiladi. Klient scope'i rol bo'yicha: TERMINAL va operator rollar (POST_ROLES)→`terminal`, TABLO→`tablo`, qolganlar→`dashboard`; post/ish markazi scope `user.machine_id` dan, operator rollarda esa `machine_id` bo'lmasa post rolning o'zidan (`POST_ROLES` → `Post.code`) aniqlanadi — aks holda postga nishonlangan `scan.recorded` eventlari yetib bormasdi. Heartbeat (TZ 2.3.2): klientning har qanday xabariga `{"type": "pong"}` |
| WS `/api/v1/ws/bridge` | `Authorization: Bearer <token>` header (fallback: `?token=` query) → `bridge_agent.token_hash` (sha256) yoki legacy `settings.BRIDGE_TOKEN` (`secrets.compare_digest`) | Tsex tarmog'idagi bridge-agent uplink'i (TZ 2.2.2 — USB GoDEX'da chop etadi). Ulanish CHIQUVCHI: agent o'zi ulanadi, tsex routerida port ochilmaydi. Token headerda keladi — server access-loglariga tushmasin; `?token=` eski agentlar uchun qoldirilgan. Avval legacy umumiy `BRIDGE_TOKEN` bilan solishtiriladi (bytes'da — non-ASCII tokenda `compare_digest(str)` TypeError beradi), mos kelmasa token sha256 xeshi bo'yicha `bridge_agent` jadvalidan qidiriladi; topilmasa 4401. `BRIDGE_TOKEN` default bo'sh, `bool(settings.BRIDGE_TOKEN)` guard esa shu holda legacy yo'lni butunlay o'chiradi — aks holda bo'sh token bo'sh sozlama bilan mos kelib, hamma ulana olardi. Ulanishda `X-Agent-Version` header `bridge_agent.version` ustuniga yoziladi; ulanish/uzilish `bridge.connected`/`bridge.disconnected` eventlari bilan panelga tarqatiladi (pairing esa `bridge.paired`). Chop etish ishlari faqat `can_print=True` agentga beriladi — `can_print=False` agent ulanib turadi (skan-forvard uchun), lekin print navbatidan ish olmaydi. Ulangandan keyin `touch_agent()` har 300 sekundda `last_seen_at` ni yangilaydi, `can_print`ni qayta o'qiydi va agent hali tirikligini qayta tekshiradi — agent o'chirilgan yoki yangi kod berilgan bo'lsa ulanish 4401 bilan yopiladi, qo'lda turgan ish esa navbatga QAYTARILADI (revoke jonli ulanishni ~5 daqiqa ichida uzadi). DB xatosi ulanishni yiqitmaydi. Redis `mes:print:queue` ro'yxatidan `brpop` (5s timeout) bilan ishlarni oladi va agentga yuboradi (job JSON: `type`, `instance_id`, `png` — base64 PNG); agent ishni lokal `print-queue.jsonl` ga yozgach 15s ichida `{"ok": true}` bilan ack qilishi shart — ack kelmasa yoki uzilsa ish `rpush` bilan navbatga QAYTARILADI (hech bir ish yo'qolmaydi); bo'sh navbatda `{"type": "ping"}` heartbeat va 10s ichida javob kutiladi |

Server → klient eventlarni `app/core/ws.py` dagi `ws_manager` tarqatadi — mutatsion HTTP endpointlar publish qiladi. Kodda uchraydigan oilalar: `order.*` (`created`, `started`, `cancelled`, `delivered` — orders.py; `stage_completed`, `completed` — skan yakunida `scanning.py` `outcome.events` orqali), `session.*` (`started`, `ended`), `scan.*` (`recorded`, `cancelled`), `label.*` (`printed`, `cancelled`), `pachka.*` (`item`, `closed`), `tmo.*` (`accepted`, `shipped`, `delivered`), `bridge.*` (`connected`, `disconnected`, `paired`).

**Bog'lanishlar:** `backend/app/core/ws.py` (`WsClient`, `ws_manager`), `backend/app/api/deps.py` (`resolve_user`), `backend/app/core/security.py` (`ACCESS_COOKIE_NAME`), `backend/app/models/bridge_agent.py` (`BridgeAgent.token_hash`, `last_seen_at`), `backend/app/api/routes/bridge_agents.py` (pairing — token shu yerda beriladi), `backend/app/tasks` (`PRINT_QUEUE_KEY = "mes:print:queue"`), `backend/app/core/config.py` (`BRIDGE_TOKEN` — legacy, `REDIS_URL`).

---

## Umumiy naqshlar (patterns)

- **Auth ikki kanalda:** `Authorization: Bearer` header (ustuvor) yoki `httpOnly` access cookie — `deps._extract_token`. WebSocket'da esa `?token=` query yoki cookie, xato — 4401.
- **Rol-guruh avtorizatsiyasi:** `require_roles` aliaslari (`ManagerUser`, `TexnologUser`, `StaffReadUser`, `AdminUser`, terminal oqimida `TerminalUser`) — superuser va ADMIN har doim o'tadi; deyarli har MES endpoint shulardan birini ishlatadi.
- **Token bekor qilish:** `token_version` — DB'dagi qiymat token payload'idagi qiymat bilan mos kelmasa 401; logout versiyani oshiradi.
- **Refresh rotatsiyasi:** har `POST /login/refresh` da access va refresh ikkalasi qayta beriladi; eski refresh token `jti`si Redis'da belgilanadi (one-time-use), replay aniqlansa `token_version` bump bilan butun sessiya bekor qilinadi.
- **Rate limiting:** `RateLimit` dependency — login endpointida (`LOGIN_RATE_LIMIT_*`).
- **Paginatsiya:** `skip`/`limit` query parametrlari, chegaralar `settings.DEFAULT_PAGE_SIZE` / `settings.MAX_PAGE_SIZE` dan; ro'yxat javoblari `app/schemas/common.py` dagi generik `Paginated[T]` (`{data, count}`) sxemasida, oddiy tasdiqlar `Message` da.
- **Fayl yuklash:** `UploadFile` qabul qiladigan endpointlar (`/orders/{id}/upload` — `.project`, `/orders/{id}/survey/photos` — xona rasmi) kengaytma/MIME va hajmni endpoint ichida tekshiradi, xato 422; fayl `settings.UPLOAD_DIR` ostiga yoziladi (absolyut root — `upload_root()`, `app/core/config.py`), bazada `OrderFile` qatori qoladi (yo'l — nisbiy).
- **Audit:** deyarli barcha mutatsion endpointlar o'z tranzaksiyasida `crud.log_action` chaqiradi — modul, amal, foydalanuvchi, entity, `meta`, IP (`deps.client_ip`) yoziladi; o'qish `GET /api/v1/audit-logs/` orqali. Kodda ishlatiladigan 13 modul nomi: `users`, `clients`, `employees`, `machines`, `posts`, `orders`, `stock`, `pachka`, `tmo`, `bridge_agents`, `print`, `sessions`, `scan`. Eski nomlar `e5b83c04d7a1` da birlashtirilgan (`ombor`→`tmo`, `materials`→`stock`), `terminal.py` esa o'z nomidan emas — `print` va `sessions` modullariga yozadi.
- **Real-time eventlar:** mutatsion endpointlar `ws_manager.publish` orqali WS eventlar tarqatadi (`order.*`, `session.*`, `scan.*`, `label.*`, `pachka.*`, `tmo.*`, `bridge.*` — to'liq ro'yxat `ws.py` bo'limida) — terminallar, TABLO va dashboard jonli yangilanadi.
- **Xatoliklar:** `backend/app/core/exceptions.py` dagi maxsus exception'lar (`UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `DuplicateValueException` 409, `RateLimitException` 429) — xabarlar o'zbek tilida. "Topilmadi" holati odatda qo'lda yozilmaydi: `BaseCRUD.get_or_404(db, "Mijoz topilmadi.", id=...)` o'zi `NotFoundException` ko'taradi. Terminal/skan oqimida esa 422 `{code, message}` formati (E001–E009 kodlari — `docs/09-mes-domain.md` §3.0). `E007` ("Aloqa yo'q") server kodi emas — WS uzilganda terminal frontendi lokal hosil qiladi (`frontend/src/routes/terminal.tsx`), so'rov serverga umuman ketmaydi.
- **OpenAPI barqarorligi:** biznes endpointlarning barchasida aniq `operation_id` berilgan (frontend client generatsiyasi uchun qulay); istisno — `health.py` dagi `/health` va `/ready` probalari (FastAPI avtomatik nom beradi).
