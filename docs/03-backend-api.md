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
        └── /ws/*           ← ws.py        (router darajasida auth YO'Q — auth endpoint ichida)
```

Jami 16 router: 2 ta ochiq (`health`, `login`), 13 tasi `get_current_user` ortida, `ws` esa WebSocket bo'lgani uchun autentifikatsiyani endpoint ichida o'zi bajaradi.

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
| `_resolve_user(db, token)` | async funksiya | `verify_token(token, TokenType.ACCESS)` bilan tekshiradi, `crud_users.get(db, id=token_data.user_id)` orqali foydalanuvchini ID bo'yicha topadi; `is_active` va `token_version` mosligini tekshiradi |
| `get_current_user` | async dependency | Token yo'q yoki yaroqsiz bo'lsa `UnauthorizedException("Tizimga kirilmagan.")` |
| `CurrentUser` | `Annotated[User, Depends(get_current_user)]` | Endpoint signaturalarida qulay alias |
| `get_current_superuser` / `SuperUserDep` | dependency / alias | `is_superuser` bo'lmasa `ForbiddenException("Sizda yetarli huquq yo'q.")` |

Muhim xavfsizlik detali: `_resolve_user` da `user.token_version != token_data.token_version` tekshiruvi — logout qilingan (versiyasi oshirilgan) tokenlar rad etiladi.

### Rol-asosli avtorizatsiya (TZ 3.7 rol/modul matritsasi)

`require_roles(*roles)` — dependency factory: joriy foydalanuvchi ruxsat etilgan rollardan birida bo'lishi kerak. **Superuser va `UserRole.ADMIN` HAR DOIM o'tadi**, aks holda `ForbiddenException("Sizda yetarli huquq yo'q.")`. Tayyor aliaslar:

| Alias | Ta'rifi | Kimga ruxsat (admin/superuser'dan tashqari) |
|---|---|---|
| `ManagerUser` | `require_roles(MANAGER)` | manager |
| `TexnologUser` | `require_roles(TEXNOLOG)` | texnolog |
| `ManagerOrTexnolog` | `require_roles(MANAGER, TEXNOLOG)` | manager yoki texnolog |
| `StaffReadUser` | `require_roles(MANAGER, TEXNOLOG, DIRECTOR)` | ofis rollari uchun umumiy read-only ro'yxatlar |
| `AdminUser` | `require_roles()` | hech kim — faqat admin/superuser |

Terminal oqimida esa route fayllar o'zi lokal alias tuzadi: `TerminalUser = require_roles(UserRole.TERMINAL, *POST_ROLES)` (`terminal.py`, `scans.py`) — maxsus terminal akkauntlar va 6 ta operator roli (arrachi, kromkachi, prisadkachi, pazchi, roverchi, stolyar).

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
router.include_router(ws_router)  # WebSocket auth endpoint ichida
```

Ya'ni auth ikki qatlamda: router darajasida `get_current_user` (login bo'lganlik), endpoint darajasida esa `deps.py` dagi rol aliaslari (kim nima qila oladi). `ws_router` istisno — WebSocket'da HTTP dependency ishlamaydi, shuning uchun autentifikatsiya har endpoint ichida bajariladi (quyida `ws.py` bo'limi).

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

**Maqsadi:** 6 ta belgilangan post (ARRA…STOLYARKA) — ular `seed_defaults` komandasi bilan yaratiladi, shuning uchun API'da create/delete YO'Q, faqat o'qish va sozlash.

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

**Maqsadi:** Eng katta route moduli (18 endpoint) — buyurtma hayot sikli TZ 6 bo'yicha: `DRAFT → TECHNICAL_REVIEW → PRODUCTION → COMPLETED → DELIVERED` (+ istalgan bosqichda `CANCELLED`). Tahrirlash cheklovlari `_EDITABLE_STATUSES = (DRAFT, TECHNICAL_REVIEW)` atrofida qurilgan.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/orders/` | `ManagerUser` | 201; tartib raqami `crud_orders.next_number` ("B-2026-001" ko'rinishida, yiliga ketma-ket); ikki manager poygasida unique index hakam — `IntegrityError` bo'lsa 3 martagacha qayta uriniladi; WS `order.created` |
| GET | `/api/v1/orders/` | `StaffReadUser` | Paginatsiya; `status` filtri; `search` — raqam/loyiha nomi/loyiha UUID/mijoz ismi; DRAFT va CANCELLED buyurtmalar texnologga (superuser bo'lmasa) KO'RINMAYDI (`_hidden_statuses`) |
| GET | `/api/v1/orders/status-counts` | `StaffReadUser` | Reestr tablari uchun har holatdagi buyurtmalar soni; `_hidden_statuses` filtri bu yerda ham amal qiladi; `/{order_id}` dan OLDIN e'lon qilingan (aks holda "status-counts" order_id deb o'qilardi) |
| GET | `/api/v1/orders/{id}` | `StaffReadUser` | `OrderDetail`: mijoz ismi, biriktirilgan fayllar (`OrderFileRead`, `meta` bilan), `survey` (anketa JSON), `parts_count`, `instances_count`; yashirin holatdagi buyurtma texnologga to'g'ridan ID bilan ham 404 |
| PATCH | `/api/v1/orders/{id}` | `ManagerUser` | DELIVERED/CANCELLED tahrirlanmaydi (403); `client_id` faqat DRAFT holatida almashtiriladi |
| PUT | `/api/v1/orders/{id}/survey` | `ManagerUser` | Mijoz anketasi + o'lchov varag'ini to'liq almashtiradi (`OrderSurvey` → `Order.survey` JSONB); DELIVERED/CANCELLED da 403; saqlashda o'chirilgan xonalarning rasmlari yetim qolmasin deb tozalanadi (quyida); audit `survey_saved` |
| POST | `/api/v1/orders/{id}/survey/photos` | `ManagerUser` | 201, multipart: `room_id` (Form, ≤40 belgi) + `file`; xona uchun namuna rasm; javob `OrderFileRead`; audit `survey_photo_added` |
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
| GET | `/api/v1/orders/{id}/cutmap` | `StaffReadUser` | Kesish xaritasi holati (TZ 10.3) — admin-panel ko'rinishi va brauzer-print; terminal bilan umumiy `build_cutmap_state` (ARRA posti) |

Barcha mutatsiyalar `log_action` bilan audit qilinadi. `.project` parser qoidalari va cutmap tafsilotlari — `docs/09-mes-domain.md`.

### Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i)

Qog'oz forma (`uploads/forma/mebel_buyurtma_anketa.html`) o'rniga. Menejer to'ldiradi, texnolog o'qib dizayn yasaydi.

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
| GET | `/api/v1/audit-logs/` | `StaffReadUser` | `Paginated[AuditLogRead]`; filtrlar: `module`, `action`, `user_id`, `date_from`, `date_to` |

`AuditLogRead` shu faylda lokal e'lon qilingan: user/employee, modul, amal, entity, xabar, `meta` (JSON), IP, vaqt.

**Bog'lanishlar:** `backend/app/models` (`AuditLog`), `backend/app/crud` (`log_action` — yozuvchi tomon).

---

## `backend/app/api/routes/terminal.py` — Operator terminali (TZ 8)

**Maqsadi:** Sexdagi 17" touch-terminal API: kontekst, beyjik-smena, vazifalar navbati, ARRA kesish xaritasi, yorliq chop etish, SCX fayllar. Barcha endpointlar `require_roles(UserRole.TERMINAL, *POST_ROLES)` ortida. Terminal→stanok bog'lanishi `resolve_terminal` orqali (`user.machine_id`dan).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/terminal/context` | terminal/operator | Stanok+post konteksti. Operator rollarida (POST_ROLES) sessiya birinchi so'rovda AVTOMATIK ochiladi — login = smena, beyjik kerak emas; TERMINAL rolida esa joriy aktiv sessiya (bo'lsa) qaytariladi |
| POST | `/api/v1/terminal/session` | terminal/operator | Beyjik skan smenani ochadi (TZ 8.2.2); xatolar 422 `{code: "E006", message}` — beyjik topilmadi / nofaol / hodim bu postga biriktirilmagan; bitta terminalda bitta aktiv sessiya — yangi beyjik eskisini yopadi; WS `session.started` |
| POST | `/api/v1/terminal/session/end` | terminal/operator | Smenani yakunlaydi; aktiv sessiya bo'lmasa 404; WS `session.ended` |
| GET | `/api/v1/terminal/tasks` | terminal/operator | NAVBATDAGI VAZIFALAR (TZ 8.3.2): faqat shu post/stanok, QOLDIQ > 0, PRODUCTION buyurtmalar, muddat (deadline) tartibida |
| GET | `/api/v1/terminal/orders` | terminal/operator | Shu postga tegishli aktiv buyurtmalar (ARRA xarita tanlagichi uchun). Tartib: prioritet (`URGENT→HIGH→MEDIUM→LOW`, `priority_rank` `case()`), keyin deadline (nulls oxirida), keyin id. `/tasks` bilan bir xil stanok filtri: boshqa stanokka muhrlangan route'lar ko'rinmaydi. Har kartada `done`/`total`, `materials` (`material_usage` dagi `kind == "sheet"` nomlari), `sheets_total` (cutmap listlari `mult` bilan), `has_cutmap` |
| GET | `/api/v1/terminal/orders/{id}/cutmap` | terminal/operator | ARRA kesish xaritasi (TZ 7.1.7); ARRA bo'lmagan postda 403; katak holati serverda — terminal qayta yonganda saqlanib qoladi |
| POST | `/api/v1/terminal/labels/{instance_id}` | terminal/operator | YORLIQ CHOP ETISH (TZ 7.1.4): ARQ `print_label` navbatiga qo'yiladi (bridge-agent/GoDEX); `label_printed_at` belgilanadi; WS `label.printed` |
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

**Bog'lanishlar:** `backend/app/schemas/terminal.py`, `backend/app/services/scanning.py` (`resolve_terminal`, `active_session`, `ScanRejected`), `backend/app/services/labels.py` (`LabelData`, `load_label_data`, `_n`, `render_label_png` — 80×60 mm, 203 dpi, 1-bit), `backend/app/tasks` (`print_label`, `PRINT_QUEUE_KEY`), `backend/app/core/ws.py`, `bridge-agent/agent.py`.

---

## `backend/app/api/routes/scans.py` — Skan ro'yxatga olish va bekor qilish (TZ 8.4–8.6)

**Maqsadi:** Terminaldagi QR skanlarni qayd etish/bekor qilish. Rol: `require_roles(UserRole.TERMINAL, *POST_ROLES)`. Butun domen logikasi `app/services/scanning.py` da — endpoint yupqa adapter.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/scans/` | terminal/operator | `record_scan` chaqiradi; rad etilsa rollback + 422 `{code, message}` (**E001–E007** xato kodlari); muvaffaqiyatda WS eventlar publish qilinadi; javob `ScanResult`: `scan_id`, `duplicate`, `qoldiq`, `scx_file_ids`, `order_stage_completed`, `order_completed` va detal ma'lumotlari |
| DELETE | `/api/v1/scans/{scan_id}` | terminal/operator | Skanni bekor qilish (undo) — `cancel_scan`; hisoblagichlar qaytariladi, WS eventlar publish qilinadi |
| GET | `/api/v1/scans/recent` | terminal/operator | TARIX bloki (TZ 8.3.3): faqat JORIY sessiyaning oxirgi 50 ta yozuvi |

Skan qabul qilish qoidalari (marshrut/ketma-ketlik tekshiruvi, dublikat, E001–E007 kodlarining ma'nosi) — `docs/09-mes-domain.md` da batafsil.

**Bog'lanishlar:** `backend/app/services/scanning.py` (`record_scan`, `cancel_scan`, `ScanRejected`), `backend/app/schemas/terminal.py` (`ScanRequest`, `ScanResult`, `ScanHistoryItem`), `backend/app/core/ws.py`.

---

## `backend/app/api/routes/tablo.py` — TABLO (sex televizori, TZ 9)

**Maqsadi:** Buyurtmalar × bosqichlar jonli matritsasi. Read-only, har qanday login qilgan foydalanuvchi/qurilma (TABLO akkaunt ham, ofis ham).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/tablo/matrix` | login (har qanday) | `TabloMatrix`: postlar ro'yxati + PRODUCTION va COMPLETED buyurtmalar; har katak `StageAgg` — done/total va post birligidagi hajm (`part_volume`: m²/metr/dona) |
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

## `backend/app/api/routes/ws.py` — WebSocket endpointlari

**Maqsadi:** Ikki WebSocket kanal. Router darajasida auth YO'Q — WebSocket'da HTTP dependency ishlamaydi, autentifikatsiya har endpoint ichida.

| Endpoint | Auth | Izoh |
|---|---|---|
| WS `/api/v1/ws/events` | `?token=` query yoki access cookie | Brauzer klientlari (TZ 2.3). Token `verify_token` + `is_active` + `token_version` bilan tekshiriladi; muvaffaqiyatsiz bo'lsa **4401** kod bilan yopiladi. Klient scope'i rol bo'yicha: TERMINAL→`terminal`, TABLO→`tablo`, qolganlar→`dashboard`; `user.machine_id` dan post/stanok scope aniqlanadi. Heartbeat (TZ 2.3.2): klientning har qanday xabariga `{"type": "pong"}` |
| WS `/api/v1/ws/bridge` | `?token=` ↔ `settings.BRIDGE_TOKEN` (`secrets.compare_digest`) | Sex tarmog'idagi bridge-agent uplink'i (TZ 2.2.2 — USB GoDEX'da chop etadi). Ulanish CHIQUVCHI: agent o'zi ulanadi, sex routerida port ochilmaydi. Token noto'g'ri yoki `BRIDGE_TOKEN` sozlanmagan bo'lsa 4401. Redis `mes:print:queue` ro'yxatidan `brpop` (5s timeout) bilan ishlarni oladi va agentga yuboradi (job JSON: `type`, `instance_id`, `png` — base64 PNG); agent ishni lokal `print-queue.jsonl` ga yozgach 15s ichida `{"ok": true}` bilan ack qilishi shart — ack kelmasa yoki uzilsa ish `rpush` bilan navbatga QAYTARILADI (hech bir ish yo'qolmaydi); bo'sh navbatda `{"type": "ping"}` heartbeat va 10s ichida javob kutiladi |

Server → klient eventlarni `app/core/ws.py` dagi `ws_manager` tarqatadi: `order.*`, `session.*`, skan eventlari, `label.printed` — mutatsion HTTP endpointlar publish qiladi.

**Bog'lanishlar:** `backend/app/core/ws.py` (`WsClient`, `ws_manager`), `backend/app/core/security.py`, `backend/app/tasks` (`PRINT_QUEUE_KEY = "mes:print:queue"`), `backend/app/core/config.py` (`BRIDGE_TOKEN`, `REDIS_URL`).

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
- **Xatoliklar:** `backend/app/core/exceptions.py` dagi maxsus exception'lar (`UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `DuplicateValueException` 409) — xabarlar o'zbek tilida. Terminal/skan oqimida esa 422 `{code, message}` formati (E001–E007 kodlari).
- **OpenAPI barqarorligi:** endpointlarda aniq `operation_id` berilgan (frontend client generatsiyasi uchun qulay).
