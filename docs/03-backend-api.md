# Backend API — Routes, Dependencies va Endpointlar

Bu hujjat MebeliX MES backend'ining HTTP API qatlamini tavsiflaydi: router ierarxiyasi, autentifikatsiya dependency'lari va barcha endpointlar. API FastAPI asosida qurilgan, barcha handler'lar `async`, ma'lumotlar bazasi bilan ishlash SQLAlchemy `AsyncSession` orqali amalga oshiriladi. Foydalanuvchiga qaytariladigan xabarlar o'zbek tilida.

## Umumiy arxitektura

```
/api                        ← backend/app/api/__init__.py (root router)
  └── /v1                   ← backend/app/api/routes/__init__.py (versiya router)
        ├── /health, /ready ← health.py   (auth talab qilinmaydi)
        ├── /login/*        ← login.py    (auth talab qilinmaydi)
        ├── /logout         ← logout.py   (get_current_user)
        └── /users/*        ← users.py    (get_current_user)
```

Autentifikatsiya modeli: JWT access + refresh token juftligi, ikkalasi ham `httpOnly` cookie sifatida o'rnatiladi; qo'shimcha ravishda `Authorization: Bearer` header ham qabul qilinadi (header cookie'dan ustun). Token bekor qilish `token_version` mexanizmi orqali — logout paytida foydalanuvchining `token_version` oshiriladi va barcha eski tokenlar yaroqsiz bo'ladi.

---

## `backend/app/api/__init__.py` — API root router

**Maqsadi:** Butun API uchun eng yuqori darajadagi `APIRouter`ni yaratadi va `/api` prefiksini qo'yadi.

- `router = APIRouter(prefix="/api")` — barcha endpointlar `/api` ostida.
- Ichiga `app.api.routes` dagi `v1_router`ni ulaydi (`router.include_router(v1_router)`).
- Bu router asosiy FastAPI ilovasiga (`app.main` yoki setup modulida) mount qilinadi.

**Bog'lanishlar:** `backend/app/api/routes/__init__.py` (v1 router).

---

## `backend/app/api/deps.py` — Dependency'lar (auth va DB session)

**Maqsadi:** Endpointlarda ishlatiladigan umumiy FastAPI dependency'larni belgilaydi: DB session, joriy foydalanuvchi va superuser tekshiruvi.

Asosiy elementlar:

| Nomi | Turi | Vazifasi |
|---|---|---|
| `SessionDep` | `Annotated[AsyncSession, Depends(async_get_db)]` | Har bir so'rov uchun async DB session |
| `_oauth2_scheme` | `OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token", auto_error=False)` | Bearer token'ni ixtiyoriy o'qiydi; `auto_error=False` — header bo'lmasa 401 bermaydi, cookie fallback ishlaydi |
| `_extract_token(request, bearer_token)` | funksiya | Avval `Authorization` header, keyin `ACCESS_COOKIE_NAME` cookie'dan token oladi |
| `_resolve_user(db, token)` | async funksiya | `verify_token(token, TokenType.ACCESS)` bilan tekshiradi, `crud_users.get(db, id=token_data.user_id)` orqali foydalanuvchini ID bo'yicha topadi; `is_active` va `token_version` mosligini tekshiradi |
| `get_current_user` | async dependency | Token yo'q yoki yaroqsiz bo'lsa `UnauthorizedException("Tizimga kirilmagan.")` |
| `CurrentUser` | `Annotated[User, Depends(get_current_user)]` | Endpoint signaturalarida qulay alias |
| `get_current_superuser` / `SuperUserDep` | dependency / alias | `is_superuser` bo'lmasa `ForbiddenException("Sizda yetarli huquq yo'q.")` |

Muhim xavfsizlik detali: `_resolve_user` da `user.token_version != token_data.token_version` tekshiruvi — logout qilingan (versiyasi oshirilgan) tokenlar rad etiladi.

**Bog'lanishlar:** `backend/app/core/db.py` (`async_get_db`), `backend/app/core/security.py` (`verify_token`, `TokenType`, `ACCESS_COOKIE_NAME`), `backend/app/core/exceptions.py`, `backend/app/crud` (`crud_users`), `backend/app/models/user.py`.

---

## `backend/app/api/routes/__init__.py` — v1 router agregatori

**Maqsadi:** Barcha route modullarini bitta `/v1` prefiksli router'ga birlashtiradi va qaysi router'lar auth talab qilishini belgilaydi.

```python
router = APIRouter(prefix="/v1")
router.include_router(health_router)                                        # ochiq
router.include_router(login_router)                                         # ochiq
router.include_router(logout_router, dependencies=[Depends(get_current_user)])
router.include_router(users_router,  dependencies=[Depends(get_current_user)])
```

Ilgari mavjud bo'lgan demo modullar (`tasks.py`, `items.py`) butunlay olib tashlangan.

Ya'ni auth router darajasida qo'llanadi: `health` va `login` dan tashqari hamma narsa login talab qiladi.

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

Muhim yordamchi: `_issue_token_pair(response, user) -> str` — payload `{"sub": str(user.id), "token_version": user.token_version}` bilan `create_access_token` va `create_refresh_token` chaqiradi (JWT `sub` — foydalanuvchi ID'si, username emas), cookie'larni `ACCESS_MAX_AGE` (daqiqa×60) va `REFRESH_MAX_AGE` (kun×86400) muddat bilan o'rnatadi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/login/access-token` | Yo'q (rate limit: `_LOGIN_RATE_LIMIT`) | `OAuth2PasswordRequestForm` (username — username yoki telefon, password) | `Token` (`access_token`, `token_type: "bearer"`) | `crud_users.authenticate` orqali tekshiradi; noto'g'ri bo'lsa yoki `is_active=False` bo'lsa 401 |
| POST | `/api/v1/login/refresh` | Refresh cookie (`REFRESH_COOKIE_NAME`) | Cookie'dan refresh token | `{"access_token", "token_type"}` | Refresh token'ni `verify_token(TokenType.REFRESH)` bilan tekshiradi, `token_version` mosligini tasdiqlaydi va **ikkala tokenni ham rotatsiya qiladi**; har bir refresh token **one-time-use** (quyida) |

Refresh token one-time-use mexanizmi: har bir muvaffaqiyatli refresh'dan so'ng token'ning `jti`si Redis'da (`auth:refresh:used:<jti>` kaliti, `rate_limiter.client` orqali, TTL = `REFRESH_MAX_AGE`) "ishlatilgan" deb belgilanadi (`_mark_refresh_token_used`). Ishlatilgan `jti` bilan qayta so'rov (replay) kelsa — cookie o'g'irlangan yoki client buzilgan deb hisoblanadi: foydalanuvchining `token_version`i oshiriladi va **butun sessiya bekor qilinadi** (401 "Token bekor qilingan."). Redis o'chirilgan konfiguratsiyada (`rate_limiter.client is None`) bu tekshiruv ataylab o'chiq bo'ladi.

Brute-force himoyasi: `RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)` dependency sifatida `access-token` endpointiga qo'llangan.

**Bog'lanishlar:** `backend/app/core/security.py` (token yaratish/tekshirish, cookie helper'lar), `backend/app/core/utils/rate_limit.py` (`RateLimit`, `rate_limiter`), `backend/app/crud` (`crud_users.authenticate`, `get`, `increment_token_version`), `backend/app/schemas/auth.py` (`Token`), `backend/app/core/config.py`.

---

## `backend/app/api/routes/logout.py` — Tizimdan chiqish

**Maqsadi:** Global logout — foydalanuvchining `token_version`ini oshirish orqali barcha faol access/refresh tokenlarni bekor qiladi va cookie'larni tozalaydi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/logout` | Ha (`CurrentUser`) | — | `{"message": "Tizimdan muvaffaqiyatli chiqildi"}` | `crud_users.increment_token_version` + `clear_auth_cookies(response)` |

**Bog'lanishlar:** `backend/app/api/deps.py`, `backend/app/core/security.py` (`clear_auth_cookies`), `backend/app/crud`.

---

## `backend/app/api/routes/users.py` — Foydalanuvchilarni boshqarish

**Maqsadi:** Foydalanuvchi CRUD: admin (superuser) tomonidan yaratish/tahrirlash hamda foydalanuvchining o'z profilini (`/me`) boshqarishi.

Lokal schema: `PaginatedResponse` (`data: list[UserRead]`, `count: int`).

Yordamchi funksiyalar:
- `_ensure_unique(db, *, phone, username, current)` — telefon/username boshqa foydalanuvchida band bo'lsa `DuplicateValueException`.
- `_derive_username_from_phone(phone)` — `+998901234567` → `998901234567`; username berilmasa telefondan hosil qilinadi, kollisiya bo'lsa `...1`, `...2` suffiks qo'shiladi.
- `_drop_forbidden_nulls(update_data)` — PATCH body'dagi explicit `null` qiymatlarni filtrlaydi: faqat `name` haqiqatan nullable, qolganlari NOT NULL ustunlarga tegib 500 berardi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/users/` | Superuser | `UserCreate` | `UserRead`, 201 | Yangi foydalanuvchi yaratish; telefon uniqueness tekshiruvi; username ixtiyoriy (telefondan derive qilinadi) |
| GET | `/api/v1/users/` | Superuser | Query: `skip>=0`, `limit` (1..`MAX_PAGE_SIZE`, default `DEFAULT_PAGE_SIZE`) | `PaginatedResponse` | Foydalanuvchilar ro'yxati (paginatsiya bilan); faqat superuser — ro'yxat barcha telefon raqamlarni ochib beradi |
| GET | `/api/v1/users/me` | Login | — | `UserRead` | Joriy foydalanuvchi profili |
| PATCH | `/api/v1/users/me` | Login | `UserUpdate` | `UserRead` | O'z profilini yangilash; `UserUpdate` da privilege flaglar yo'q — eskalatsiya mumkin emas; explicit `null`lar `_drop_forbidden_nulls` bilan filtrlanadi |
| PATCH | `/api/v1/users/me/password` | Login | `UpdatePassword` (`current_password`, `new_password`) | `{"message": ...}` | Joriy parolni `verify_password` bilan tekshiradi; yangi parol eskisiga teng bo'lmasligi kerak; yangi hash `await get_password_hash(...)` bilan hisoblanadi |
| DELETE | `/api/v1/users/me` | Login (superuser emas) | — | `{"message": ...}` | O'z hisobini o'chirish; superuser'lar o'zini o'chira olmaydi (403) |
| GET | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `UserRead` | ID bo'yicha foydalanuvchi — faqat o'zi yoki superuser (aks holda 403, telefon raqamlar maxfiy); topilmasa 404 |
| PATCH | `/api/v1/users/{user_id}` | Superuser | `UserAdminUpdate` | `UserRead` | Istalgan foydalanuvchini yangilash (admin schema privilege flaglarni o'z ichiga oladi); explicit `null`lar `_drop_forbidden_nulls` bilan filtrlanadi |
| DELETE | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `{"message": ...}` | Soft-delete; superuser o'z hisobini o'chira olmaydi; oddiy user faqat o'zini o'chira oladi |

**Bog'lanishlar:** `backend/app/api/deps.py` (`CurrentUser`, `SuperUserDep`, `SessionDep`), `backend/app/schemas/users.py` (`UserCreate`, `UserRead`, `UserUpdate`, `UserAdminUpdate`, `UpdatePassword`), `backend/app/core/security.py` (`get_password_hash`, `verify_password`), `backend/app/crud`, `backend/app/core/exceptions.py`, `backend/app/core/config.py`.

---

## Umumiy naqshlar (patterns)

- **Auth ikki kanalda:** `Authorization: Bearer` header (ustuvor) yoki `httpOnly` access cookie — `deps._extract_token`.
- **Token bekor qilish:** `token_version` — DB'dagi qiymat token payload'idagi qiymat bilan mos kelmasa 401; logout versiyani oshiradi.
- **Refresh rotatsiyasi:** har `POST /login/refresh` da access va refresh ikkalasi qayta beriladi; eski refresh token `jti`si Redis'da belgilanadi (one-time-use), replay aniqlansa `token_version` bump bilan butun sessiya bekor qilinadi.
- **Rate limiting:** `RateLimit` dependency — login endpointida (`LOGIN_RATE_LIMIT_*`).
- **Paginatsiya:** `skip`/`limit` query parametrlari, chegaralar `settings.DEFAULT_PAGE_SIZE` / `settings.MAX_PAGE_SIZE` dan.
- **Xatoliklar:** `backend/app/core/exceptions.py` dagi maxsus exception'lar (`UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `DuplicateValueException` 409) — xabarlar o'zbek tilida.
- **OpenAPI barqarorligi:** ko'p endpointlarda aniq `operation_id` berilgan (frontend client generatsiyasi uchun qulay).
