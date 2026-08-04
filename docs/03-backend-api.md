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
        ├── /posts/*        ← posts.py     │  router darajasida
        ├── /materials/*    ← materials.py │  Depends(get_current_user)
        ├── /orders/*       ← orders.py    │
        ├── /audit-logs/    ← audit.py     │
        ├── /terminal/*     ← terminal.py  │
        ├── /scans/*        ← scans.py     │
        ├── /tablo/*        ← tablo.py     │
        ├── /reports/*      ← reports.py   ┘
        ├── /bridge-agents/*← bridge_agents.py (router darajasida auth YO'Q — /pair ochiq, admin endpointlar o'zini himoyalaydi)
        └── /ws/*           ← ws.py        (router darajasida auth YO'Q — auth endpoint ichida)
```

Jami 17 router: 2 ta ochiq (`health`, `login`), 13 tasi `get_current_user` ortida, `bridge_agents` va `ws` esa router darajasida himoyalanmaydi — autentifikatsiyani endpointlar o'zi bajaradi (WebSocket'da HTTP dependency ishlamaydi, `/bridge-agents/pair` esa sessiyasiz agent uchun ochiq bo'lishi shart).

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
| `ManagerOrTexnolog` | `require_roles(MANAGER, TEXNOLOG)` | manager yoki texnolog |
| `StaffReadUser` | `require_roles(MANAGER, TEXNOLOG, DIRECTOR)` | ofis rollari uchun umumiy read-only ro'yxatlar |
| `AdminUser` | `require_roles()` | hech kim — faqat admin/superuser |

Terminal oqimida esa route fayllar o'zi lokal alias tuzadi: `TerminalUser = require_roles(UserRole.TERMINAL, *POST_ROLES)` (`terminal.py`, `scans.py`) — maxsus terminal akkauntlar va 7 ta operator roli (arrachi, kromkachi, ovalchi, prisadkachi, pazchi, roverchi, stolyar). Chek bekor qilish endpointi kengroq: `LabelCancelUser` = terminal/operator + manager/texnolog.

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
router.include_router(materials_router, dependencies=_protected)
router.include_router(orders_router, dependencies=_protected)
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

Muhim yordamchi: `_issue_token_pair(response, user) -> str` — payload `{"sub": str(user.id), "token_version": user.token_version}` bilan `create_access_token` va `create_refresh_token` chaqiradi (JWT `sub` — foydalanuvchi ID'si, username emas), cookie'larni `ACCESS_MAX_AGE` (daqiqa×60) va `REFRESH_MAX_AGE` (kun×86400) muddat bilan o'rnatadi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/login/access-token` | Yo'q (rate limit: `_LOGIN_RATE_LIMIT`) | `OAuth2PasswordRequestForm` (username — username yoki telefon, password) | `Token` (`access_token`, `token_type: "bearer"`) | `crud_users.authenticate` orqali tekshiradi; noto'g'ri bo'lsa yoki `is_active=False` bo'lsa 401 |
| POST | `/api/v1/login/refresh` | Refresh cookie (`REFRESH_COOKIE_NAME`) | Cookie'dan refresh token | `{"access_token", "token_type"}` | Refresh token'ni `verify_token(TokenType.REFRESH)` bilan tekshiradi, `token_version` mosligini tasdiqlaydi va **ikkala tokenni ham rotatsiya qiladi**; har bir refresh token **one-time-use** (quyida) |

Refresh token one-time-use mexanizmi: har bir muvaffaqiyatli refresh'dan so'ng token'ning `jti`si Redis'da (`auth:refresh:used:<jti>` kaliti, `rate_limiter.client` orqali, TTL = `REFRESH_MAX_AGE`) "ishlatilgan" deb belgilanadi (`_mark_refresh_token_used`). Ishlatilgan `jti` bilan qayta so'rov (replay) kelsa — cookie o'g'irlangan yoki client buzilgan deb hisoblanadi: foydalanuvchining `token_version`i oshiriladi va **butun sessiya bekor qilinadi** (401 "Token bekor qilingan."). Redis pool lifespan'da shartsiz ochiladi (o'chirish sozlamasi yo'q), shuning uchun `rate_limiter.client is None` faqat lifespan'siz kontekstda uchraydi — o'sha holatda tekshiruv o'tkazib yuboriladi.

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

Ro'yxat javobi umumiy `Paginated[UserRead]` sxemasida (`app/schemas/common.py`) — lokal nusxa yo'q.

Yordamchi funksiyalar:
- `_ensure_unique(db, *, phone, username, current)` — telefon/username boshqa foydalanuvchida band bo'lsa `DuplicateValueException`.
- `_derive_username_from_phone(phone)` — `+998901234567` → `998901234567`; username berilmasa telefondan hosil qilinadi, kollisiya bo'lsa `...1`, `...2` suffiks qo'shiladi.
- `_drop_forbidden_nulls(update_data)` — PATCH body'dagi explicit `null` qiymatlarni filtrlaydi: faqat `name` haqiqatan nullable, qolganlari NOT NULL ustunlarga tegib 500 berardi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/users/` | Superuser | `UserCreate` | `UserRead`, 201 | Yangi foydalanuvchi yaratish; telefon uniqueness tekshiruvi; username ixtiyoriy (telefondan derive qilinadi) |
| GET | `/api/v1/users/` | Superuser | Query: `skip>=0`, `limit` (1..`MAX_PAGE_SIZE`, default `DEFAULT_PAGE_SIZE`) | `Paginated[UserRead]` | Foydalanuvchilar ro'yxati (paginatsiya bilan); faqat superuser — ro'yxat barcha telefon raqamlarni ochib beradi |
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

**Maqsadi:** Sex hodimlari CRUD va beyjik (QR badge) boshqaruvi. Hodim — tizimga kirmaydigan shaxs; u terminalda beyjik skan qilib ishlaydi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/employees/` | `StaffReadUser` | Paginatsiya; `search` — ism/beyjik; `status` filtri (`EmployeeStatus`) |
| POST | `/api/v1/employees/` | `AdminUser` | 201; `badge_id` avtomatik `uuid4` sifatida yaratiladi; `assigned_post_ids` mavjudligi tekshiriladi |
| GET | `/api/v1/employees/{id}` | `StaffReadUser` | Topilmasa 404 |
| PATCH | `/api/v1/employees/{id}` | `AdminUser` | `assigned_post_ids` o'zgarsa qayta validatsiya |
| POST | `/api/v1/employees/{id}/badge` | `AdminUser` | Beyjik yo'qolganda (TZ 4.2): yangi `uuid4` beriladi — eskisi darhol ishlamay qoladi, tarix shu hodimda qoladi; eski beyjik audit `meta`sida saqlanadi |
| DELETE | `/api/v1/employees/{id}` | `AdminUser` | Soft-delete |

**Bog'lanishlar:** `backend/app/schemas/employees.py`, `backend/app/crud` (`crud_employees`, `crud_posts`, `log_action`), `backend/app/models/enums.py` (`EmployeeStatus`).

---

## `backend/app/api/routes/machines.py` — Stanoklar

**Maqsadi:** Stanoklar CRUD. Ro'yxat kichik va o'zgarmas bo'lgani uchun paginatsiyasiz; o'qish har qanday login qilgan foydalanuvchiga ochiq (terminal/TABLO kontekstga ham kerak).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/machines/` | login (har qanday) | Barcha stanoklar, `list[MachineRead]` |
| POST | `/api/v1/machines/` | `AdminUser` | 201; `post_id` mavjudligi tekshiriladi |
| GET | `/api/v1/machines/{id}` | login (har qanday) | Topilmasa 404 |
| PATCH | `/api/v1/machines/{id}` | `AdminUser` | `post_id` o'zgarsa qayta tekshiriladi |
| DELETE | `/api/v1/machines/{id}` | `AdminUser` | Soft-delete |

**Bog'lanishlar:** `backend/app/schemas/machines.py`, `backend/app/crud` (`crud_machines`, `crud_posts`, `log_action`).

---

## `backend/app/api/routes/posts.py` — Ishlab chiqarish postlari

**Maqsadi:** 7 ta belgilangan post (ARRA, KROMKA, OVAL, PRISADKA, PAZ, ROVER, STOLYARKA; OVAL `order_index=3`) — ular `seed_defaults` komandasi bilan yaratiladi, shuning uchun API'da create/delete YO'Q, faqat o'qish va sozlash.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/posts/` | login (har qanday) | `order_index` bo'yicha tartiblangan postlar ro'yxati |
| PATCH | `/api/v1/posts/{id}` | `AdminUser` | Post sozlamalarini yangilash (nom, rang, flaglar) |

**Bog'lanishlar:** `backend/app/schemas/posts.py`, `backend/app/crud` (`crud_posts`, `log_action`), `backend/app/commands/seed_defaults.py`.

---

## `backend/app/api/routes/materials.py` — Materiallar katalogi

**Maqsadi:** Material spravochnigi (list/kromka). Katalogni texnolog yuritadi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/materials/` | login (har qanday) | Paginatsiya; `search` — nom/kod; `type` filtri (`MaterialType`) |
| POST | `/api/v1/materials/` | `TexnologUser` | 201; nom+tur dublikati bo'lsa 409 |
| PATCH | `/api/v1/materials/{id}` | `TexnologUser` | Yangilash |
| DELETE | `/api/v1/materials/{id}` | `TexnologUser` | Soft-delete |

**Bog'lanishlar:** `backend/app/schemas/materials.py`, `backend/app/crud` (`crud_materials`, `log_action`), `backend/app/models/enums.py` (`MaterialType`).

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
| POST | `/api/v1/orders/{id}/upload` | `TexnologUser` | `.project` fayl yuklash (TZ 6.3): faqat TECHNICAL_REVIEW holatida; kengaytma va hajm (`MAX_PROJECT_FILE_SIZE`) tekshiriladi; parse xatosi 422; TEMPLATE (GibLab'da optimizatsiya qilinmagan) fayl 422 aniq yo'riqnoma matni bilan rad etiladi (TZ 5.3.3); qayta yuklashda `wipe_previous_parse` oldingi parse natijalarini o'chiradi, `ingest_project` yangisini yozadi |
| GET | `/api/v1/orders/{id}/matrix` | `StaffReadUser` | `OrderMatrix` — detal × bosqich marshrutlar (`RouteCell`) |
| PATCH | `/api/v1/orders/{id}/matrix` | `TexnologUser` | Matritsa tahriri (TZ 6.3.3): bosqich on/off (ARRA'ni o'chirib BO'LMAYDI — 403), izoh, soni o'zgartirish (`_resize_instances` fizik nusxalar va route summalarini moslashtiradi); faqat production'gacha |
| POST | `/api/v1/orders/{id}/machines` | `ManagerUser` | Bir postda bir nechta stanok bo'lsa manager tanlaydi (TZ 6.4.1); post/stanok mosligi tekshiriladi; faqat production'gacha |
| POST | `/api/v1/orders/{id}/start` | `ManagerUser` | Ishlab chiqarishga uzatish (TZ 6.4.2): `TECHNICAL_REVIEW → PRODUCTION`; `.project` yuklangan bo'lishi shart; `requires_assignment_choice` postlarda stanok tanlanmagan bo'lsa 403; tanlangan stanok route yozuvlariga muhrlanadi (terminal filtri uchun); WS `order.started` |
| POST | `/api/v1/orders/{id}/cancel` | `ManagerUser` | Bekor qilish (TZ 6.5): istalgan bosqichda (DELIVERED/CANCELLED dan tashqari); sabab majburiy; skan tarixi audit uchun saqlanadi; WS `order.cancelled` — terminallar vazifalarni DARHOL tashlaydi |
| POST | `/api/v1/orders/{id}/deliver` | `ManagerUser` | TOPSHIRILDI (TZ 10.3): faqat `COMPLETED → DELIVERED`; `delivered_at` avtomatik; WS `order.delivered` |
| GET | `/api/v1/orders/{id}/files/{file_id}` | `StaffReadUser` | Saqlangan faylni yuklab olish (project/SCX/hujjat), `FileResponse`; `media_type`: PROJECT/SCX uchun `application/xml`, qolganlari uchun `meta["content_type"]` (yo'q bo'lsa `application/octet-stream`) — anketa rasmlari `<img>` da ko'rsatilishi uchun shart |
| GET | `/api/v1/orders/{id}/files/scx.zip` | `StaffReadUser` | Barcha SCX fayllar bitta ZIP arxivda (`{number}_scx.zip`) — prisadkachi stanokka bittalab emas, bitta arxiv ko'chiradi; SCX yo'q bo'lsa 404 |
| POST | `/api/v1/orders/{id}/scx/regenerate` | `TexnologUser` | SCX fayllarni saqlangan `.project`dan qayta yaratadi (eski buyurtmani yangi nomlashga o'tkazish: har nusxa = QR nomli fayl); detallar/marshrutlar/skanlarga TEGILMAYDI; `.project` diskda bo'lmasa 404 |
| GET | `/api/v1/orders/{id}/cutmap` | `StaffReadUser` | Kesish xaritasi holati (TZ 10.3) — admin-panel ko'rinishi va brauzer-print; terminal bilan umumiy `build_cutmap_state` (ARRA posti) |

Barcha mutatsiyalar `log_action` bilan audit qilinadi. `.project` parser qoidalari va cutmap tafsilotlari — `docs/09-mes-domain.md`.

### Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i)

Qog'oz forma o'rniga. Menejer to'ldiradi, texnolog o'qib dizayn yasaydi.

**Saqlash:** `Order.survey` — nullable JSONB ustun (`backend/app/models/order.py`, migratsiya `backend/app/migrations/versions/a91c7d34f6e2_order_survey.py`). Butun anketa bir butun sifatida yoziladi: `PUT /survey` mavjud qiymatni to'liq almashtiradi, patch semantikasi yo'q.

**Sxemalar** (`backend/app/schemas/orders.py`) — barcha maydonlar tashqi kirish bo'lgani uchun chegaralangan:

| Sxema | Maydonlar | Chegaralar |
|---|---|---|
| `OrderSurvey` | `version` (default 1), `measured_at` (o'lchov sanasi), `measured_by`, `rooms` | `rooms` ≤ 10; `measured_by` ≤ 120 belgi |
| `SurveyRoom` | `id` (frontend beradigan barqaror kalit), `name`, `furniture_types`/`furniture_other`, `shape` + `room_length`/`room_width`/`room_height`/`furniture_wall_length`, `corpus_materials`/`corpus_color`/`corpus_thickness`/`corpus_note`, `facade_materials`/`facade_color`/`countertop`/`facade_note`, `hardware_level`, `extra_services`, `note`, `walls`, `modules`, `total_running_meters`, `total_height` | `id` ≤ 40; `furniture_types` ≤ 20 element; material/xizmat ro'yxatlari ≤ 10; `note` ≤ 1000; `walls` ≤ 8; `modules` ≤ 40; `total_running_meters` 0..1000 |
| `SurveyWall` | `letter` (A..E), `length`, `height` | o'lchamlar mm da, `_Mm` = 0..50 000 |
| `SurveyModule` | `name`, `wall`, `width` (eni), `depth` (chuqurlik), `height`, `count`, `note` | `count` 1..999; `note` ≤ 200; o'lchamlar `_Mm` |

Variant kodlari (`ldsp`, `mdf`, `akril`…) backend'da qat'iy ro'yxat emas — matnga aylantirish `frontend/src/lib/anketa.ts` da; yangi variant qo'shishda migratsiya kerak emas. Mijoz ma'lumotlari `Client` da, narx/avans/muddat `Order` da — anketada takrorlanmaydi.

**Xona rasmlari** alohida jadval talab qilmaydi: `OrderFile(kind=FileKind.DOCUMENT, meta={"room_id": ..., "content_type": ...})`, disk yo'li `uploads/survey/{order_id}/{uuid4().hex}{ext}`. Shu sabab `OrderFileRead` ga `meta` maydoni qo'shilgan.

Yuklash cheklovlari (`orders.py` dagi konstantalar):

- `_ROOM_PHOTO_TYPES` — faqat `image/jpeg` → `.jpg`, `image/png` → `.png`, `image/webp` → `.webp`; boshqasi 422 "Faqat JPG, PNG yoki WEBP rasm qabul qilinadi."
- `MAX_ROOM_PHOTO_SIZE = 5 MB` — oshsa 422 (telefon surati odatda 2–4 MB).
- `MAX_ROOM_PHOTOS = 6` — bitta `room_id` uchun; oshsa 422.

**Yetim rasm tozalash:** `save_order_survey` anketani yozgach, `room_id`si kelgan `rooms` ro'yxatida yo'q bo'lgan `DOCUMENT` fayllarni topadi (JSONB `meta ? 'room_id'` + `meta->>'room_id' NOT IN (...)`), diskdan `unlink` qiladi (`OSError` yutiladi) va `is_deleted`/`deleted_at` belgilaydi. Ya'ni xona anketadan olib tashlansa uning rasmlari ham yo'qoladi.

**Bog'lanishlar:** `backend/app/schemas/orders.py`, `backend/app/models/order.py` (`Order.survey`), `backend/app/services/giblab` (`parse_project`, `ingest_project`, `wipe_previous_parse`), `backend/app/core/ws.py` (`ws_manager`), `backend/app/api/routes/terminal.py` (`build_cutmap_state`), frontend tomoni: `frontend/src/routes/_layout/anketa.$orderId.tsx`, `frontend/src/lib/anketa.ts`.

---

## `backend/app/api/routes/audit.py` — Audit jurnali

**Maqsadi:** Barcha modullar yozgan audit yozuvlarini o'qish. Yozish API orqali emas — har mutatsion endpoint o'z tranzaksiyasida `crud.log_action` chaqiradi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/audit-logs/` | `AdminUser` | `Paginated[AuditLogRead]`; filtrlar: `module`, `action`, `user_id`, `q` (xabar bo'yicha `ilike` qidiruv), `date_from`/`date_to` — kun chegaralari Asia/Tashkent vaqtida (naive-UTC bo'lsa "bugun" filtri 00:00–05:00 yozuvlarni yo'qotardi) |

`AuditLogRead` shu faylda lokal e'lon qilingan: user/employee, modul, amal, entity, xabar, `meta` (JSON), IP, vaqt, hamda `user_name`/`employee_name` ("kim" ustuni uchun `outerjoin` orqali — alohida so'rovsiz).

**Bog'lanishlar:** `backend/app/models` (`AuditLog`), `backend/app/crud` (`log_action` — yozuvchi tomon).

---

## `backend/app/api/routes/terminal.py` — Operator terminali (TZ 8)

**Maqsadi:** Sexdagi 17" touch-terminal API: kontekst, beyjik-smena, vazifalar navbati, ARRA kesish xaritasi, yorliq chop etish, SCX fayllar. Barcha endpointlar `require_roles(UserRole.TERMINAL, *POST_ROLES)` ortida. Stanok+post konteksti `TerminalCtx` dependency'si orqali keladi (`_terminal_ctx` → `resolve_terminal`, `ScanRejected` → 422 `{code, message}`) — u faqat kontekstga muhtoj route'larga qo'yilgan, yorliq va fayl route'lariga ATAYLAB emas: stanoksiz terminal foydalanuvchisi ham yorliq chop eta olishi kerak. `resolve_terminal` operator rollarida postni rolning o'zidan oladi (stanok — `user.machine_id`, bo'lmasa postning birinchi stanogi), TERMINAL akkauntda esa `user.machine_id`dan.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/terminal/context` | terminal/operator | Stanok+post konteksti. Operator rollarida (POST_ROLES) sessiya birinchi so'rovda AVTOMATIK ochiladi — login = smena, beyjik kerak emas; TERMINAL rolida esa joriy aktiv sessiya (bo'lsa) qaytariladi |
| POST | `/api/v1/terminal/session` | terminal/operator | Beyjik skan smenani ochadi (TZ 8.2.2); xatolar 422 `{code: "E006", message}` — beyjik topilmadi / nofaol / hodim bu postga biriktirilmagan; bitta terminalda bitta aktiv sessiya — yangi beyjik eskisini yopadi; WS `session.started` |
| POST | `/api/v1/terminal/session/end` | terminal/operator | Smenani yakunlaydi; aktiv sessiya bo'lmasa 404; WS `session.ended` |
| GET | `/api/v1/terminal/tasks` | terminal/operator | NAVBATDAGI VAZIFALAR (TZ 8.3.2): faqat shu post/stanok, QOLDIQ > 0, PRODUCTION buyurtmalar, muddat (deadline) tartibida |
| GET | `/api/v1/terminal/orders` | terminal/operator | Shu postga tegishli aktiv buyurtmalar (post sahifalari tanlagichi). Tartib: prioritet (`URGENT→HIGH→MEDIUM→LOW`, `priority_rank` `case()`), keyin deadline (nulls oxirida), keyin id. `/tasks` bilan bir xil stanok filtri. `done`/`total` post semantikasida: ARRA — chek chiqarilgan YOKI skan qilingan nusxalar (hammasi chiqarilgan buyurtma ro'yxatdan TUSHADI); KROMKA — detal bo'yicha (nusxaning hamma tomoni skan bo'lsa "qilingan"); boshqa postlarda skan yig'indisi. Kartada `materials`, `sheets_total`, `has_cutmap` |
| GET | `/api/v1/terminal/orders/{id}/cutmap` | terminal/operator | ARRA kesish xaritasi (TZ 7.1.7); ARRA bo'lmagan postda 403; katak holati serverda — terminal qayta yonganda saqlanib qoladi |
| GET | `/api/v1/terminal/orders/{id}/kromka` | terminal/operator | KROMKA/OVAL sahifasi (boshqa postda 403): shu post marshrutidagi detallar, har nusxada `done` (post skanlari) / `sides` (`per_instance`), `arra_passed` (chek chiqarilgan yoki ARRA skan bor) |
| GET | `/api/v1/terminal/orders/{id}/prisadka` | terminal/operator | PRISADKA sahifasi (boshqa postda 403): detallar + har detalning SCX fayllari (`{id, filename}`), `project_name` (frontend shu nom bilan papka ochadi) |
| GET | `/api/v1/terminal/qr/{qr_text}/order` | terminal/operator | QR qaysi PRODUCTION buyurtmaga tegishligini topadi — `{order_id, order_number}`; picker'da skan qilinsa terminal o'sha proyektni o'zi ochadi |
| POST | `/api/v1/terminal/labels/{instance_id}` | terminal/operator | YORLIQ CHOP ETISH (TZ 7.1.4): ARQ `print_label` navbatiga qo'yiladi (bridge-agent/GoDEX); `label_printed_at` belgilanadi; WS `label.printed`. ARRA UI'da chiqarilgan katak YASHIL = "kesildi"; qayta chop etish frontendda bloklanadi (avval bekor qilish kerak) |
| DELETE | `/api/v1/terminal/labels/{instance_id}` | terminal/operator + manager/texnolog | Chekni bekor qilish: `label_printed_at = None`, WS `label.cancelled`. Terminalda long press (~600ms) + tasdiq dialogi; admin webdagi xaritada detal kartochkasidagi tugma (proyekt ARRA ro'yxatidan tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi). Skan qilingan nusxaga tegmaydi |
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

Agent tomoni (`bridge-agent/agent.py`) — bitta chiqish yo'li: `send_to_printer(png_b64)` → `_print_png_gdi` — PNG Windows drayveri orqali chiziladi (win32ui + PIL, DEVMODE 80×60 mm ga majburlanadi). Printer avtomatik topiladi: `_detect_printer()` nomida "godex" bor lokal Windows printerini qidiradi, `PRINTER_NAME` env faqat qo'lda override uchun. Agent env'lari: `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`. Agent faqat printer ulangan kompyuterga o'rnatiladi — menejer, texnolog va boshqa post terminallariga hech narsa kerak emas.

**Bog'lanishlar:** `backend/app/schemas/terminal.py`, `backend/app/services/scanning.py` (`resolve_terminal`, `active_session`, `latest_active_session`, `ScanRejected`), `backend/app/services/labels.py` (`LabelData`, `load_label_data`, `_n`, `render_label_png` — 80×60 mm, 203 dpi, 1-bit), `backend/app/tasks` (`print_label`, `PRINT_QUEUE_KEY`), `backend/app/core/ws.py`, `bridge-agent/agent.py`.

---

## `backend/app/api/routes/scans.py` — Skan ro'yxatga olish va bekor qilish (TZ 8.4–8.6)

**Maqsadi:** Terminaldagi QR skanlarni qayd etish/bekor qilish. Rol: `require_roles(UserRole.TERMINAL, *POST_ROLES)`. Butun domen logikasi `app/services/scanning.py` da — endpoint yupqa adapter.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/scans/` | terminal/operator | `record_scan` chaqiradi; rad etilsa rollback + 422 `{code, message}` (**E001–E006** xato kodlari); muvaffaqiyatda WS eventlar publish qilinadi; javob `ScanResult`: `scan_id`, `duplicate`, `qoldiq`, `scx_file_ids`, `project_name` (avto-SCX proyekt nomli papkaga tushishi uchun), `order_stage_completed`, `order_completed` va detal ma'lumotlari; har skan (rad etilgani ham) `scan` modulida audit logga yoziladi |
| DELETE | `/api/v1/scans/{scan_id}` | terminal/operator | Skanni bekor qilish (undo) — `cancel_scan`; hisoblagichlar qaytariladi, WS eventlar publish qilinadi |
| GET | `/api/v1/scans/recent` | terminal/operator | TARIX bloki (TZ 8.3.3): faqat JORIY sessiyaning oxirgi 50 ta yozuvi |

Skan qabul qilish qoidalari (marshrut/ketma-ketlik tekshiruvi, dublikat, E001–E006 kodlarining ma'nosi) — `docs/09-mes-domain.md` da batafsil.

**Bog'lanishlar:** `backend/app/services/scanning.py` (`record_scan`, `cancel_scan`, `ScanRejected`), `backend/app/schemas/terminal.py` (`ScanRequest`, `ScanResult`, `ScanHistoryItem`), `backend/app/core/ws.py`.

---

## `backend/app/api/routes/tablo.py` — TABLO (sex televizori, TZ 9)

**Maqsadi:** Buyurtmalar × bosqichlar jonli matritsasi. Read-only, har qanday login qilgan foydalanuvchi/qurilma (TABLO akkaunt ham, ofis ham).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/tablo/matrix` | login (har qanday) | `TabloMatrix`: postlar ro'yxati + PRODUCTION buyurtmalar va oxirgi `COMPLETED_WINDOW` (30 kun) ichida yakunlanganlar; har katak `StageAgg` — done/total va post birligidagi hajm (`part_volume`: m²/metr/dona). **Chegara shart**: COMPLETED holatdan faqat manager qo'lda "topshirildi" bosgandagina chiqiladi, ya'ni chegarasiz har bir unutilgan buyurtma taxtada abadiy qolib, sex ekranini sekinlashtirardi (o'lchov: 100 buyurtmada 28 ms → 1.9 s). Marshrutlar ORM obyekti sifatida emas, faqat kerakli ustunlar bilan o'qiladi |
| GET | `/api/v1/tablo/orders/{id}` | login (har qanday) | Drill-down (TZ 9.5 SONI NAZORATI): har detal × bosqich done/total |

**Bog'lanishlar:** `backend/app/services/metrics.py` (`part_volume`), `backend/app/models` (`Order`, `PartRoute`, `Post`).

---

## `backend/app/api/routes/reports.py` — Hisobotlar (TZ 11) va dashboard statistikasi

**Maqsadi:** Boshqaruv hisobotlari. Rol: `require_roles(MANAGER, DIRECTOR)` (admin/superuser har doim o'tadi). Uch hisobot default JSON qaytaradi, `?format=xlsx` bilan Excel fayl stream qilinadi (TZ 11.4, `services/excel.xlsx_response`). Sana oralig'i berilmasa — oxirgi 30 kun, chegaralar Asia/Tashkent bo'yicha inklyuziv kunlar.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/reports/productivity` | manager/direktor | Hodim mahsuldorligi (TZ 11.1.1): skan soni, faol kunlar, kuniga/soatiga o'rtacha; `?format=xlsx` |
| GET | `/api/v1/reports/orders` | manager/direktor | Buyurtmalar holati (TZ 11.2): holat, muddatlar, `overdue` belgisi (muddat o'tgan tugallanmaganlar), bekor sababi; `?format=xlsx` |
| GET | `/api/v1/reports/materials` | manager/direktor | Material sarfi (TZ 11.3): `Order.material_usage` JSONB'dan agregatsiya (`project_loaded_at` oralig'ida, CANCELLED chiqariladi); `?format=xlsx` |
| GET | `/api/v1/reports/dashboard` | manager/direktor | Dashboard (TZ 10.2.1): har stanok uchun navbat (qolgan skanlar/hajm), quvvat va prognoz soatlar (TZ 4.3: navbat/quvvat), bugungi skanlar; faqat JSON |

**Bog'lanishlar:** `backend/app/services/excel.py` (`xlsx_response`), `backend/app/services/metrics.py` (`part_volume`).

---

## `backend/app/api/routes/bridge_agents.py` — Printer agentlari va pairing (TZ 2.2.2)

**Maqsadi:** Printerli kompyuterdagi bridge-agent'ni serverga ulash (pairing) — podpiska modeli uchun: admin panelda kod beriladi, agent kodni doimiy tokenga almashtiradi. Serverga SSH kirish ham, `.env` tahriri ham kerak emas. Har printerning o'z tokeni bor — birini bekor qilish qolganlariga tegmaydi.

Router `/api/v1/bridge-agents` prefiksi bilan **himoyasiz** ulanadi (`/pair` chaqirilganda agentda sessiya yo'q), shuning uchun admin endpointlarning har biri o'z signaturasida `AdminUser` talab qiladi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/bridge-agents/` | `AdminUser` | Agentlar ro'yxati (`BridgeAgentRead`: `id`, `name`, `paired`, `pair_code`, `pair_expires_at`, `last_seen_at`, `created_at`, `machine_id`, `machine_name`, `version`, `can_print`); `pair_code` faqat muddati o'tmagan bo'lsa qaytariladi, aks holda `null` |
| PATCH | `/api/v1/bridge-agents/{id}` | `AdminUser` | Stanok bog'lash (`machine_id` — skan-forvard uchun) va chek-chiqarish belgisi (`can_print`); maydonlar alohida yuboriladi (`exclude_unset` — berilmagani tegilmaydi); audit `machine_linked` / `can_print_changed` |
| POST | `/api/v1/bridge-agents/` | `AdminUser` | 201; agent yaratiladi va **bir martalik 8 belgili ulanish kodi** beriladi (`PAIR_TTL` = 15 daqiqa); audit `created` |
| POST | `/api/v1/bridge-agents/{id}/code` | `AdminUser` | Yangi ulanish kodi (kod eskirgan yoki kompyuter almashgan holat); `token_hash` tozalanadi — eski kompyuter keyingi ulanishda rad etiladi; audit `code_regenerated` |
| DELETE | `/api/v1/bridge-agents/{id}` | `AdminUser` | Soft-delete; jonli WebSocket ham uziladi (`touch_agent()` 5 daqiqada bir tekshiradi); audit `deleted` |
| POST | `/api/v1/bridge-agents/pair` | **Yo'q (ochiq)** | Agent bir martalik kodni doimiy tokenga almashtiradi; javob `BridgePairResponse` (`token`, `name`); audit `paired` (`user_id=None`); WS `bridge.paired` — admin sahifasi pollingsiz yangilanadi |
| POST | `/api/v1/bridge-agents/scan` | Agent tokeni (`Authorization: Bearer`) | Skan-forvard (TZ 12.5): stanok skaneri o'qigan QR agent orqali MES'ga yoziladi — agentga bog'langan stanokning AKTIV sessiyasi nomidan (`record_scan_at` + `finalize_scan`, odatdagi skan yo'li); stanok bog'lanmagan / sessiya yo'q — 409; rad etilgan skan ham `scan`/`rejected` audit logga tushadi, javob `ScanResult` |

**Ulanish kodi:** `_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"` — I/L/O/0/1 yo'q, telefonda aytganda adashtirmaydi. 31 belgi × 8 uzunlik (`_CODE_LEN = 8`) = 31⁸ ≈ 8.5·10¹¹ kombinatsiya, 15 daqiqalik oynada brute-force amalda imkonsiz.

**Pairing xavfsizligi** (`POST /pair`):

- Atomik `UPDATE ... RETURNING` — bir kodni ikki kompyuter bir vaqtda yuborsa faqat bittasi yutadi (kod shu tranzaksiyada `NULL` ga o'tadi).
- Kod topilmasa ham, muddati o'tgan bo'lsa ham **bitta umumiy xato**: 400 "Ulanish kodi noto'g'ri yoki muddati o'tgan." — kodning bor-yo'qligi oshkor qilinmaydi.
- Kirishda `-` va bo'shliqlar olib tashlanadi, harflar katta registrga o'tkaziladi (qo'lda kiritishga bardosh).
- Token `secrets.token_hex(24)` bilan yaratiladi va **faqat shu javobda** beriladi; bazada `token_hash` sifatida sha256 xeshi qoladi.

Agent exe'ni yuklab olish endpointi YO'Q (2026-08-02 da olib tashlangan — diskdagi eski exe'ni berib adashtirardi): exe qo'lda tarqatiladi (`bridge-agent/README.md`).

**Agent tomoni** (`bridge-agent/agent.py`): PyInstaller onefile `mebelix-agent.exe` — sex kompyuteriga Python o'rnatish shart emas. `_load_dotenv()` config'ni shu tartibda o'qiydi: env var > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`. `_pair()` (import paytida chaqiriladi) birinchi ishga tushishda kichik tkinter oynasi (`_pair_dialog()`) orqali server manzili va ulanish kodini so'raydi, `_exchange()` ularni `POST /pair` ga yuboradi va olingan tokenni `%APPDATA%\MebelixAgent\.env` ga yozadi; kod noto'g'ri bo'lsa oyna xato matni bilan qayta ochiladi. `BRIDGE_TOKEN` allaqachon bor bo'lsa `_pair()` darhol qaytadi — hech narsa so'ralmaydi; aks holda oyna har doim ochiladi, `stdin` tty bo'lishi shart emas (exe `--noconsole` bilan quriladi, konsol umuman yo'q). Faqat tkinter ishlamagan muhitda (dev/Linux) `_pair_console()` zaxira sifatida ishlaydi, u ham kod ololmasa `SystemExit("Ulanish bekor qilindi.")` — agent jim davom etmaydi, xato oynasini ko'rsatib to'xtaydi. Qolgan hammasi o'zgarmagan — printer avto-topiladi, `print-queue.jsonl` durable navbat, `_print_png_gdi` chiqish yo'li.

**Bog'lanishlar:** `backend/app/schemas/bridge_agents.py` (`BridgeAgentCreate`, `BridgeAgentRead`, `BridgePairRequest`, `BridgePairResponse`), `backend/app/models/bridge_agent.py` (`BridgeAgent`), migratsiya `backend/app/migrations/versions/d5e81a24c3b7_bridge_agent_pairing.py`, `backend/app/crud` (`crud_bridge_agents`, `log_action`), `backend/app/api/routes/ws.py` (`/ws/bridge` shu tokenni tanidi), `bridge-agent/agent.py`.

---

## `backend/app/api/routes/ws.py` — WebSocket endpointlari

**Maqsadi:** Ikki WebSocket kanal. Router darajasida auth YO'Q — WebSocket'da HTTP dependency ishlamaydi, autentifikatsiya har endpoint ichida.

| Endpoint | Auth | Izoh |
|---|---|---|
| WS `/api/v1/ws/events` | `?token=` query yoki access cookie | Brauzer klientlari (TZ 2.3). Token HTTP oqimidagi bilan bir xil funksiya — `deps.resolve_user` — orqali tekshiriladi (`verify_token` + `is_active` + `token_version`); muvaffaqiyatsiz bo'lsa **4401** kod bilan yopiladi. Klient scope'i rol bo'yicha: TERMINAL va operator rollar (POST_ROLES)→`terminal`, TABLO→`tablo`, qolganlar→`dashboard`; post/stanok scope `user.machine_id` dan, operator rollarda esa `machine_id` bo'lmasa post rolning o'zidan (`POST_ROLES` → `Post.code`) aniqlanadi — aks holda postga nishonlangan `scan.recorded` eventlari yetib bormasdi. Heartbeat (TZ 2.3.2): klientning har qanday xabariga `{"type": "pong"}` |
| WS `/api/v1/ws/bridge` | `Authorization: Bearer <token>` header (fallback: `?token=` query) → `bridge_agent.token_hash` (sha256) yoki legacy `settings.BRIDGE_TOKEN` (`secrets.compare_digest`) | Sex tarmog'idagi bridge-agent uplink'i (TZ 2.2.2 — USB GoDEX'da chop etadi). Ulanish CHIQUVCHI: agent o'zi ulanadi, sex routerida port ochilmaydi. Token headerda keladi — server access-loglariga tushmasin; `?token=` eski agentlar uchun qoldirilgan. Avval legacy umumiy `BRIDGE_TOKEN` bilan solishtiriladi (bytes'da — non-ASCII tokenda `compare_digest(str)` TypeError beradi), mos kelmasa token sha256 xeshi bo'yicha `bridge_agent` jadvalidan qidiriladi; topilmasa 4401. `BRIDGE_TOKEN` default bo'sh, `bool(settings.BRIDGE_TOKEN)` guard esa shu holda legacy yo'lni butunlay o'chiradi — aks holda bo'sh token bo'sh sozlama bilan mos kelib, hamma ulana olardi. Ulanishda `X-Agent-Version` header `bridge_agent.version` ustuniga yoziladi; ulanish/uzilish `bridge.connected`/`bridge.disconnected` eventlari bilan panelga tarqatiladi (pairing esa `bridge.paired`). Chop etish ishlari faqat `can_print=True` agentga beriladi — `can_print=False` agent ulanib turadi (skan-forvard uchun), lekin print navbatidan ish olmaydi. Ulangandan keyin `touch_agent()` har 300 sekundda `last_seen_at` ni yangilaydi, `can_print`ni qayta o'qiydi va agent hali tirikligini qayta tekshiradi — agent o'chirilgan yoki yangi kod berilgan bo'lsa ulanish 4401 bilan yopiladi, qo'lda turgan ish esa navbatga QAYTARILADI (revoke jonli ulanishni ~5 daqiqa ichida uzadi). DB xatosi ulanishni yiqitmaydi. Redis `mes:print:queue` ro'yxatidan `brpop` (5s timeout) bilan ishlarni oladi va agentga yuboradi (job JSON: `type`, `instance_id`, `png` — base64 PNG); agent ishni lokal `print-queue.jsonl` ga yozgach 15s ichida `{"ok": true}` bilan ack qilishi shart — ack kelmasa yoki uzilsa ish `rpush` bilan navbatga QAYTARILADI (hech bir ish yo'qolmaydi); bo'sh navbatda `{"type": "ping"}` heartbeat va 10s ichida javob kutiladi |

Server → klient eventlarni `app/core/ws.py` dagi `ws_manager` tarqatadi: `order.*`, `session.*`, skan eventlari, `label.printed` — mutatsion HTTP endpointlar publish qiladi.

**Bog'lanishlar:** `backend/app/core/ws.py` (`WsClient`, `ws_manager`), `backend/app/api/deps.py` (`resolve_user`), `backend/app/core/security.py` (`ACCESS_COOKIE_NAME`), `backend/app/models/bridge_agent.py` (`BridgeAgent.token_hash`, `last_seen_at`), `backend/app/api/routes/bridge_agents.py` (pairing — token shu yerda beriladi), `backend/app/tasks` (`PRINT_QUEUE_KEY = "mes:print:queue"`), `backend/app/core/config.py` (`BRIDGE_TOKEN` — legacy, `REDIS_URL`).

---

## Umumiy naqshlar (patterns)

- **Auth ikki kanalda:** `Authorization: Bearer` header (ustuvor) yoki `httpOnly` access cookie — `deps._extract_token`. WebSocket'da esa `?token=` query yoki cookie, xato — 4401.
- **Rol-guruh avtorizatsiyasi:** `require_roles` aliaslari (`ManagerUser`, `TexnologUser`, `StaffReadUser`, `AdminUser`, terminal oqimida `TerminalUser`) — superuser va ADMIN har doim o'tadi; deyarli har MES endpoint shulardan birini ishlatadi.
- **Token bekor qilish:** `token_version` — DB'dagi qiymat token payload'idagi qiymat bilan mos kelmasa 401; logout versiyani oshiradi.
- **Refresh rotatsiyasi:** har `POST /login/refresh` da access va refresh ikkalasi qayta beriladi; eski refresh token `jti`si Redis'da belgilanadi (one-time-use), replay aniqlansa `token_version` bump bilan butun sessiya bekor qilinadi.
- **Rate limiting:** `RateLimit` dependency — login endpointida (`LOGIN_RATE_LIMIT_*`).
- **Paginatsiya:** `skip`/`limit` query parametrlari, chegaralar `settings.DEFAULT_PAGE_SIZE` / `settings.MAX_PAGE_SIZE` dan; ro'yxat javoblari `app/schemas/common.py` dagi generik `Paginated[T]` (`{data, count}`) sxemasida, oddiy tasdiqlar `Message` da.
- **Fayl yuklash:** `UploadFile` qabul qiladigan endpointlar (`/orders/{id}/upload` — `.project`, `/orders/{id}/survey/photos` — xona rasmi) kengaytma/MIME va hajmni endpoint ichida tekshiradi, xato 422; fayl `settings.UPLOAD_DIR` ostiga yoziladi, bazada `OrderFile` qatori qoladi (yo'l — nisbiy).
- **Audit:** deyarli barcha mutatsion endpointlar (clients/employees/machines/posts/materials/orders/terminal) o'z tranzaksiyasida `crud.log_action` chaqiradi — modul, amal, foydalanuvchi, entity, `meta`, IP yoziladi; o'qish `GET /api/v1/audit-logs/` orqali.
- **Real-time eventlar:** mutatsion endpointlar `ws_manager.publish` orqali WS eventlar tarqatadi (`order.*`, `session.*`, skan eventlari, `label.printed`) — terminallar, TABLO va dashboard jonli yangilanadi.
- **Xatoliklar:** `backend/app/core/exceptions.py` dagi maxsus exception'lar (`UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `DuplicateValueException` 409) — xabarlar o'zbek tilida. "Topilmadi" holati odatda qo'lda yozilmaydi: `BaseCRUD.get_or_404(db, "Mijoz topilmadi.", id=...)` o'zi `NotFoundException` ko'taradi. Terminal/skan oqimida esa 422 `{code, message}` formati (E001–E006 kodlari). `E007` ("Aloqa yo'q") server kodi emas — WS uzilganda terminal frontendi lokal hosil qiladi (`frontend/src/routes/terminal.tsx`), so'rov serverga umuman ketmaydi.
- **OpenAPI barqarorligi:** biznes endpointlarning barchasida aniq `operation_id` berilgan (frontend client generatsiyasi uchun qulay); istisno — `health.py` dagi `/health` va `/ready` probalari (FastAPI avtomatik nom beradi).
