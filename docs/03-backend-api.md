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
        ├── /orders/*       ← orders/      │  Depends(get_current_user)
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

Jami 18 router: 2 ta ochiq (`health`, `login`), 14 tasi `get_current_user` ortida, `bridge_agents` va `ws` esa router darajasida himoyalanmaydi — autentifikatsiyani endpointlar o'zi bajaradi (WebSocket'da HTTP dependency ishlamaydi, `/bridge-agents/pair` esa sessiyasiz agent uchun ochiq bo'lishi shart).

Autentifikatsiya modeli: JWT access + refresh token juftligi, ikkalasi ham `httpOnly` cookie sifatida o'rnatiladi; qo'shimcha ravishda `Authorization: Bearer` header ham qabul qilinadi (header cookie'dan ustun). Token bekor qilishning IKKI darajasi bor. (1) **Chiqish — faqat shu qurilma**: `logout` joriy refresh tokenning `jti` sini Redis'dagi `auth:refresh:used:` tombstone'iga qo'yadi va cookie'larni tozalaydi; boshqa qurilmalardagi sessiyalarga tegilmaydi (ilgari bu yerda ham `token_version` oshirilardi — monoblokdan chiqqan admin noutbukdagi ishidan ham uchib tushardi; sanoat amaliyotida chiqish joriy sessiyani yopadi). (2) **Global bekor qilish** — `token_version` oshirilishi, u BARCHA qurilmadagi access va refresh tokenlarni birdan o'ldiradi va faqat jiddiy holatlarda ishlatiladi: parol almashtirilganda (`users.py`, o'z paroli ham, admin boshqasinikini almashtirganda ham) va refresh token qayta ishlatilganda (o'g'irlanish belgisi, `login.py`). Alohida «hamma qurilmadan chiqish» tugmasi ATAYLAB yo'q: u kerak bo'ladigan yagona jiddiy holat — token o'g'irlangani — parolni almashtirish bilan yopiladi.

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
| `client_ip(request)` | funksiya | Audit log uchun mijoz IP'si BITTA joyda (`request.client.host`); `X-Forwarded-For` allaqachon `ProxyHeadersMiddleware` orqali qo'llanadi (`core/setup.py`) — funksiya faqat `request.client` ni o'qiydi. 22 route moduldan 12 tasi import qiladi |
| `_oauth2_scheme` | `OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token", auto_error=False)` | Bearer token'ni ixtiyoriy o'qiydi; `auto_error=False` — header bo'lmasa 401 bermaydi, cookie fallback ishlaydi |
| (token manbasi) | `get_current_user` ichida | Avval `Authorization` header, keyin `ACCESS_COOKIE_NAME` cookie — alohida helper YO'Q, uch qator `get_current_user` ichida |
| `resolve_user(db, token)` | async funksiya | `verify_token(token, TokenType.ACCESS)` bilan tekshiradi, `crud_users.get(db, id=token_data.user_id)` orqali foydalanuvchini ID bo'yicha topadi; `is_active` va `token_version` mosligini tekshiradi. Ochiq nom — `ws.py` ham shu funksiyani chaqiradi |
| `get_current_user` | async dependency | Token yo'q yoki yaroqsiz bo'lsa `UnauthorizedException("Tizimga kirilmagan.")` |
| `CurrentUser` | `Annotated[User, Depends(get_current_user)]` | Endpoint signaturalarida qulay alias |
| `get_current_superuser` / `SuperUserDep` | dependency / alias | `is_superuser` bo'lmasa `ForbiddenException("Sizda yetarli huquq yo'q.")` |

Muhim xavfsizlik detali: `resolve_user` da `user.token_version != token_data.token_version` tekshiruvi — versiyasi oshirilgan (parol almashtirilgan yoki refresh replay aniqlangan) tokenlar rad etiladi. Oddiy chiqish bu versiyani OSHIRMAYDI — u faqat shu qurilmani uzadi.

### Rol-asosli avtorizatsiya (rol/modul matritsasi)

`require_roles(*roles)` — dependency factory: joriy foydalanuvchi ruxsat etilgan rollardan birida bo'lishi kerak. **Superuser va `UserRole.ADMIN` HAR DOIM o'tadi**, aks holda `ForbiddenException("Sizda yetarli huquq yo'q.")`. Tayyor aliaslar:

| Alias | Ta'rifi | Kimga ruxsat (admin/superuser'dan tashqari) |
|---|---|---|
| `ManagerUser` | `require_roles(MANAGER)` | manager |
| `TexnologUser` | `require_roles(TEXNOLOG)` | texnolog |
| `ManagerOrTexnologUser` | `require_roles(MANAGER, TEXNOLOG)` | manager yoki texnolog — `orders/{id}/machines` va `orders/{id}/start` |
| `StaffReadUser` | `require_roles(MANAGER, TEXNOLOG, DIRECTOR)` | ofis rollari uchun umumiy read-only ro'yxatlar |
| `AdminUser` | `require_roles(ADMIN)` | faqat admin/superuser |

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

Muhim yordamchilar: `refresh_days(user) -> int` (refresh umri — qurilma hisobi 90 kun, odam 7; ochiq nom — `logout.py` ham shuni import qiladi) va `_issue_token_pair(response, user) -> str` — payload `{"sub": str(user.id), "token_version": user.token_version}` bilan `create_access_token` va `create_refresh_token` chaqiradi (JWT `sub` — foydalanuvchi ID'si, username emas), cookie'larni muddat bilan o'rnatadi: access — `ACCESS_MAX_AGE` (daqiqa×60); refresh esa ROLGA bog'liq — qurilma hisoblarida (TERMINAL, TABLO) `settings.DEVICE_REFRESH_TOKEN_EXPIRE_DAYS` (default 90 kun; monoblokda klaviatura yo'q, parol faqat o'rnatishda bir marta teriladi), qolganlarida `REFRESH_TOKEN_EXPIRE_DAYS` (default 7 kun — o'g'irlangan cookie oynasi kengaymasin). Refresh token ham AYNAN shu `days` bilan yaratiladi (`create_refresh_token(..., days=days)`), cookie muddati `days × 24×60×60`. Tombstone TTL'i ham `refresh_days(user)` dan kelib chiqadi — ya'ni token qancha yashasa, bir martalik belgisi ham shuncha turadi (qotirilgan `REFRESH_MAX_AGE` OLIB TASHLANDI: u 7 kun edi, qurilma tokeni esa 90 kun yashardi va 83 kunlik replay oynasi qolardi).

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/login/access-token` | Yo'q (rate limit: `_LOGIN_RATE_LIMIT`) | `OAuth2PasswordRequestForm` (username — username yoki telefon, password) | `Token` (`access_token`, `token_type: "bearer"`) | `crud_users.authenticate` orqali tekshiradi; noto'g'ri bo'lsa yoki `is_active=False` bo'lsa 401. **`is_system=True` hisob YOPIQ** — 401 "Bu texnik hisob — u bilan kirilmaydi.": seed yaratgan post hisobi faqat beyjik bilan ochilgan smena qaysi nomdan yozilishini hal qiladi (`_terminal_user`), odam emas. Post rolidagi SHAXSIY hisob esa kiradi va `_open_shift_for` smenani shu zahoti ochadi (`employee.user_id` bog'lami, post `POST_ROLES` dan, ish markazi `scanning.post_machine` dan). Smena JIMGINA ochilmaydi (xato chiqmaydi, odam terminalda o'zini tanishtiradi) BESH holatda: hodim yozuvi yo'q, hodim `EmployeeStatus.ACTIVE` emas, rolga mos post bazada topilmadi, post shu hodimning `assigned_post_ids` ichida emas, yoki postga ishga yaroqli ish markazi topilmadi (`post_machine` `None`). Smena ochilsa audit logga `sessions/started` yoziladi (`entity_type="session"`, `employee_id`, `ip` — beyjik yo'li bilan bir xil, matni «Parol bilan kirish: …»); ilgari bu yo'l JIMGINA ochardi va parol bilan ochilgan smena izsiz qolardi. Bu skaneri yo'q post uchun — ARRA da chek chiqarish skan hisoblanadi, skaner faqat kirishga kerak bo'lardi. Kirishning O'ZI ham audit logga tushadi (`_audit_auth`, modul `auth`): muvaffaqiyatda `login` (`user_id`), har uchala rad etishda esa `login_failed` — parol/username noto'g'ri (`user_id=None`, xabarda urinilgan identifikator), nofaol hisob va texnik hisob (ikkalasida `user_id` ma'lum). Yozuv SHU YERDA commit qilinadi, chunki keyin 401 ko'tariladi va sessiya rollback bo'lardi — aynan brute-force izi yo'qolardi |
| POST | `/api/v1/login/refresh` | Refresh cookie (`REFRESH_COOKIE_NAME`) | Cookie'dan refresh token | `{"access_token", "token_type"}` | Refresh token'ni `verify_token(TokenType.REFRESH)` bilan tekshiradi, `token_version` mosligini tasdiqlaydi va **ikkala tokenni ham rotatsiya qiladi**; har bir refresh token **one-time-use** (quyida) |
| POST | `/api/v1/login/badge` | Yo'q (rate limit: `_BADGE_RATE_LIMIT`) | `BadgeLoginRequest` (`badge_id`, ixtiyoriy `post_id`) | `BadgeLoginResponse` (`Token` + `employee_name`, `machine_name`, `post_name`) | Tsexdagi kirish: beyjik skani, parolsiz. Post beyjik egasining biriktirilgan postlaridan chiqadi; bir nechtasi bo'lsa **409** + `{"code": "POST_CHOICE", "employee_name", "posts": [...]}` (monoblok tanlash oynasini ko'rsatadi va `post_id` bilan qayta yuboradi). Smenani ochadi (`open_badge_session`) |

### Beyjik bilan kirish (parolsiz tsex terminali)

Operator login/parol termaydi — beyjik skani kirishga aylanadi. **Hech qanday o'rnatish qadami yo'q:** kirish sahifasi ochilib turgan istalgan brauzerda skan ishlaydi.

Beyjik ikkala savolga javob beradi — KIM va QAYERDA:

1. `badge_id` → `employee` (nofaol beyjik va noma'lum beyjik 401).
2. `employee.assigned_post_ids` → post. Bitta bo'lsa so'ralmaydi; bir nechta bo'lsa 409 + ro'yxat, hodim monoblokda tanlaydi (`_badge_post`).
3. Post → ish markazi: `scanning.post_machine` — BITTA joydagi qoida (ilgari ikki nusxada yozilgan edi): NOAKTIV markaz tanlanmaydi, AKTIV TA'MIRDA dan ustun turadi, ikkalasi ham yo'q bo'lsa admin uchun aniq xato. Beyjik kirishi ham, terminal konteksti ham SHU funksiyani chaqiradi, ya'ni ikkalasi bir xil javob beradi.
4. `_terminal_user(machine, post)` — kirish qaysi hisob nomidan yoziladi: shu ish markaziga biriktirilgan **TERMINAL** hisobi, bo'lmasa post rolidagi (`POST_ROLES`) **TEXNIK** (`is_system=True`) hisob. `is_system` sharti MAJBURIY: o'sha rolda odamning SHAXSIY hisobi ham bo'ladi va usiz eng kichik ID olinib, beyjik ochgan smena BOSHQA ishchining hisobi nomidan yozilardi. Oqibati: postda seed texnik hisobi yaratilmagan yoki nofaol qilingan bo'lsa (faqat shaxsiy post-rolli hisob qolsa) beyjik bilan kirish 401 «{post} uchun terminal hisobi yo'q. Admin hisob yaratishi kerak.» bilan yiqiladi — admin aynan TEXNIK hisobni tiklashi kerak. Ikkala yo'l ham `resolve_terminal` bilan BIR XIL postga olib keladi (biri ish markazi, ikkinchisi rol orqali) — aks holda operator boshqa postning ekranida paydo bo'lardi. Hisob KIM ishlayotganini bildirmaydi — u beyjik ochgan `work_session` da.

**Xavfsizlik (ataylab tanlangan, 2026-08-12).** Beyjik — yagona omil: QR qog'ozda, nusxa olingan bo'lsa istalgan qurilmadan kirsa bo'ladi. Qurilma bog'lash varianti ko'rib chiqilib rad etildi — tsexda parol/kod terish smena almashuvini sekinlashtiradi va amalda umumiy akkauntga olib keladi, ya'ni ish haqi atributsiyasini butunlay yo'qotadi. O'rniga: hisob imtiyozi tor (terminal ekranlari, admin paneli emas), har kirish audit logga tushadi, beyjik `employee.status` bilan darhol bekor qilinadi. Chegara `30/60s` — 122-bitli UUID'ni brute-force qilib bo'lmaydi, tor chegara esa smena almashuvida butun tsexni (bitta tashqi IP) qulflab qo'yardi.

Refresh token one-time-use mexanizmi: `jti` Redis'da (`auth:refresh:used:<jti>` kaliti, `rate_limiter.client` orqali, TTL = tokenning O'Z umri (`refresh_days(user)` — odam hisobida 7 kun, qurilma hisobida 90 kun)) "ishlatilgan" deb belgilanadi. Belgilash ATOMIK: `_claim_refresh_jti` bitta `SET … NX EX` yuboradi va falsy natija “jti allaqachon ishlatilgan” degani. Ilgari bu EXISTS bilan tekshirilib, keyin alohida SET qilinardi — ikkisi orasidagi oynada bir tokenning IKKI parallel replayi ham o'tib ketardi va bir martalik kafolat jimgina yo'qolardi. Shu sababli tartib ham shunday: avval foydalanuvchi va `token_version` tekshiriladi (TTL uchun `refresh_days(user)` kerak), keyin claim qilinadi. `logout.py` esa shartsiz belgilaydi — `mark_refresh_token_used` (oddiy `SET … EX`, NX'siz). Ishlatilgan `jti` bilan qayta so'rov (replay) kelsa — cookie o'g'irlangan yoki client buzilgan deb hisoblanadi: foydalanuvchining `token_version`i oshiriladi va **butun sessiya bekor qilinadi** (401 "Token bekor qilingan."). Redis klienti lifespan'da shartsiz ochiladi (`rate_limiter.initialize(settings.REDIS_URL)`, o'chirish sozlamasi yo'q), shuning uchun `rate_limiter.client is None` faqat lifespan'siz kontekstda uchraydi — o'sha holatda tekshiruv o'tkazib yuboriladi.

Brute-force himoyasi: `RateLimit(limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS, period=settings.LOGIN_RATE_LIMIT_PERIOD)` dependency sifatida `access-token` endpointiga qo'llangan. Beyjik endpointida alohida `_BADGE_RATE_LIMIT = RateLimit(30, 60)` (kalit `ratelimit:{ip}:{path}:{oyna}` — yo'l bo'yicha ajralgan, parol chegarasini yemaydi).

**Chegara FAQAT MUVAFFAQIYATSIZ urinishlarni sanaydi.** Dependency (`RateLimit.__call__`) hech narsa hisoblamaydi — u faqat `rate_limiter.over_limit` bilan Redis'dan O'QIYDI va oshgan bo'lsa 429 beradi; hisobni chaqiruvchi XATO yo'lda `hit()` bilan oshiradi: parolda uch joyda (parol noto'g'ri, `is_active=False`, `is_system=True`) va beyjikda ikki joyda (beyjik topilmadi, beyjik nofaol). Sabab o'lchangan: tsex bitta tashqi IP orqali chiqadi (NAT) va har so'rov hisoblanganda smena boshida navbatma-navbat kirgan operatorlar byudjetni yeb qo'yardi — keyingi odam, odatda admin, parolni to'g'ri tersa ham 429 olardi (prodda: 30 daqiqada 9 ta muvaffaqiyatli kirish va 8 ta 429). Redis o'qishda xato bersa `over_limit` **fail-closed** — 429 qaytadi, ya'ni Redis uzilishi brute-force himoyasini jimgina o'chirmaydi.

**Bog'lanishlar:** `backend/app/core/security.py` (token yaratish/tekshirish, cookie helper'lar), `backend/app/core/utils/rate_limit.py` (`RateLimit`, `rate_limiter`), `backend/app/crud` (`crud_users.authenticate`, `get`, `increment_token_version`), `backend/app/schemas/auth.py` (`Token`, `BadgeLogin*`, `BadgePostOption`), `backend/app/services/scanning.py` (`open_badge_session`), `backend/app/core/config.py`.

---

## `backend/app/api/routes/logout.py` — Tizimdan chiqish

**Maqsadi:** Chiqish — FAQAT SHU QURILMA: joriy refresh tokenning `jti` si Redis tombstone'iga qo'yiladi, cookie'lar tozalanadi va shu foydalanuvchining ochiq smenalari yopiladi. `token_version` OSHIRILMAYDI — boshqa qurilmalardagi sessiyalar tirik qoladi (monoblokdan chiqqan admin noutbukdagi ishidan uchib tushmasin). Access token texnik jihatdan yana 30 daqiqa amal qiladi, lekin u ham shu qurilmadan o'chiriladi.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/logout` | Ha (`CurrentUser`) | — | `Message` — "Tizimdan muvaffaqiyatli chiqildi" | `end_session` (faqat O'Z ochiq smenalari) + audit `auth/logout` + `mark_refresh_token_used(jti)` + `clear_auth_cookies(response)` |

**Smena ham yopiladi:** kirish uni ochgan (`login._open_shift_for`), shuning uchun chiqish uni yopmasa hisob yopilib smena ochiq qolardi — terminal "Kim ishlayapti?" da ketgan odamni ko'rsatar, ish haqi esa unga yozilib turaverardi. Faqat O'Z smenasi yopiladi: beyjik bilan qo'shilgan sherigining smenasiga tegilmaydi, u boshqa odam va o'zi chiqadi. Cookie'dagi refresh token buzuq yoki eskirgan bo'lsa xato yutiladi — chiqish baribir bajariladi. Chiqish audit logga `auth/logout` bo'lib yoziladi (`user_id`, IP) — smenalarni yopish bilan BIR tranzaksiyada.

**Bog'lanishlar:** `backend/app/api/deps.py`, `backend/app/core/security.py` (`clear_auth_cookies`, `verify_token`, `REFRESH_COOKIE_NAME`), `backend/app/api/routes/login.py` (`mark_refresh_token_used`, `refresh_days`), `backend/app/services/scanning.py` (`end_session`), `backend/app/models` (`Employee`, `WorkSession`).

---

## `backend/app/api/routes/users.py` — Foydalanuvchilarni boshqarish

**Maqsadi:** Foydalanuvchi CRUD: admin (superuser) tomonidan yaratish/tahrirlash hamda foydalanuvchining o'z profilini (`/me`) boshqarishi.

Ro'yxat javobi umumiy `Paginated[UserRead]` sxemasida (`app/schemas/common.py`) — lokal nusxa yo'q.

Yordamchi funksiyalar:
- `_ensure_unique(db, *, phone, username, current)` — telefon/username boshqa foydalanuvchida band bo'lsa `DuplicateValueException`.
- `_derive_username_from_phone(phone)` — `+998901234567` → `998901234567`; username berilmasa telefondan hosil qilinadi, kollisiya bo'lsa `...1`, `...2` suffiks qo'shiladi.
- `drop_forbidden_nulls(update_data, nullable)` (`routes/_shared.py` — routerlar orasida umumiy) — PATCH body'dagi explicit `null` qiymatlarni filtrlaydi. Har modul o'z `_NULLABLE_FIELDS` ini uzatadi: `users.py` — `("name", "machine_id")` (`machine_id: null` — ish markazi bog'lamini uzish), `employees.py` — `("phone", "position", "user_id")`, `clients.py` — `("phone", "phone_alt", "address", "notes")`; qolganlari NOT NULL ustunlarga tegib 500 berardi. `machines.py` va `posts.py` esa nullable ustunsiz chaqiradi (hamma ustuni NOT NULL). Beshala PATCH route'i shu filtrdan o'tadi.

Barcha mutatsiyalar (yaratish, admin-yangilash, parol almashtirish, o'chirish) `log_action` bilan audit qilinadi (`module="users"`); xabar javoblari `Message` sxemasida, "topilmadi" holatlari `crud_users.get_or_404` orqali.

| Method | Path | Auth | Request | Response | Tavsif |
|---|---|---|---|---|---|
| POST | `/api/v1/users/` | Superuser | `UserCreate` | `UserRead`, 201 | Yangi foydalanuvchi yaratish; telefon uniqueness tekshiruvi; username ixtiyoriy (telefondan derive qilinadi); `_check_machine` — TERMINAL/TABLO hisobiga ish markazi SHART (409), boshqa rolga esa biriktirilmaydi (409), noma'lum `machine_id` 404 |
| GET | `/api/v1/users/` | `StaffReadUser` | Query: `skip>=0`, `limit` (1..`MAX_PAGE_SIZE`, default `DEFAULT_PAGE_SIZE`) | `Paginated[UserRead]` | Sahifalangan ro'yxat. RO'YXAT boshqaruvga ochiq — birlashgan "Hodimlar" sahifasi har odamning kirish usulini shundan biladi; YOZISH amallari superuser'da qoladi |
| GET | `/api/v1/users/me` | Login | — | `UserRead` | Joriy foydalanuvchi profili |
| PATCH | `/api/v1/users/me` | Login | `UserUpdate` | `UserRead` | O'z profilini yangilash; `UserUpdate` da privilege flaglar yo'q — eskalatsiya mumkin emas; explicit `null`lar `drop_forbidden_nulls` bilan filtrlanadi |
| PATCH | `/api/v1/users/me/password` | Login | `UpdatePassword` (`current_password`, `new_password`) | `{"message": ...}` | Joriy parolni `verify_password` bilan tekshiradi; yangi parol eskisiga teng bo'lmasligi kerak; yangi hash `await get_password_hash(...)` bilan hisoblanadi |
| DELETE | `/api/v1/users/me` | Login (superuser/qurilma/post roli emas) | — | `{"message": ...}` | O'z hisobini o'chirish — `delete_user(current_user.id, ...)` ga uzatadi, ya'ni qoidalar BITTA joyda: superuser o'zini o'chira olmaydi (403), qurilma (`TERMINAL`/`TABLO`) va post roli hisobi ham o'chirilmaydi (403) |
| GET | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `UserRead` | ID bo'yicha foydalanuvchi — faqat o'zi yoki superuser (aks holda 403, telefon raqamlar maxfiy); topilmasa 404 |
| PATCH | `/api/v1/users/{user_id}` | Superuser | `UserAdminUpdate` | `UserRead` | Istalgan foydalanuvchini yangilash (admin schema privilege flaglarni o'z ichiga oladi); explicit `null`lar `drop_forbidden_nulls` bilan filtrlanadi; rol yoki `machine_id` o'zgarsa `_check_machine` qayta tekshiradi; **o'zini nofaol qilish va o'zidan superuser huquqini olish — 403** (aks holda bitta superuserli o'rnatishda tizimga kirishning yagona yo'li yopilardi); parol almashtirilsa `token_version` oshadi — egasining TIRIK sessiyalari uziladi |
| DELETE | `/api/v1/users/{user_id}` | Login (o'zi yoki superuser) | path: `user_id: int` | `{"message": ...}` | Soft-delete; qurilma hisoblari (TERMINAL/TABLO) va seed yaratgan POST hisoblari (`username == str(role)` — `login._terminal_user` beyjik smenasini shu hisob nomidan yozadi) 403 «qurilma yoki post hisobi, odam emas»; tsex xodimining SHAXSIY logini post rolida bo'lsa ham o'chiriladi (PersonDialog «loginni olib tashlash» yo'li); superuser o'z hisobini o'chira olmaydi; oddiy user faqat o'zini o'chira oladi — begona `user_id` uchun tekshiruv bazaga borishdan OLDIN ishlaydi, ya'ni javob mavjud va mavjud bo'lmagan id uchun bir xil 403 (`"Sizda yetarli huquq yo'q."`), id bor-yo'qligi sizib chiqmaydi. **Qurilma (`TERMINAL`/`TABLO`) va post roli hisoblari umuman o'chirilmaydi — 403**: ular odam emas, o'chirilsa o'sha postda beyjik bilan kirish o'ladi (`login._terminal_user`). Kerak bo'lsa nofaol qilinadi |

**Bog'lanishlar:** `backend/app/api/deps.py` (`CurrentUser`, `SuperUserDep`, `SessionDep`), `backend/app/schemas/users.py` (`UserCreate`, `UserRead`, `UserUpdate`, `UserAdminUpdate`, `UpdatePassword`), `backend/app/schemas/common.py` (`Paginated`), `backend/app/core/security.py` (`get_password_hash`, `verify_password`), `backend/app/crud`, `backend/app/core/exceptions.py`, `backend/app/core/config.py`.

---

## `backend/app/api/routes/clients.py` — Mijozlar

**Maqsadi:** Mijozlar CRUD (buyurtma reestri uchun manba). Ro'yxat javobida har mijozga `orders_count` (tirik buyurtmalar soni, subquery orqali) qo'shiladi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/clients/` | `StaffReadUser` | Paginatsiya (`skip`/`limit`), `search` — `full_name`, `phone` va `phone_alt` bo'yicha `ilike` (unikallik ham ikkala telefon ustunini qamragani uchun ikkinchi raqam bo'yicha ham topiladi) |
| POST | `/api/v1/clients/` | `ManagerUser` | 201; telefon unikalligi: `phone` va `phone_alt` ustunlari bo'yicha tirik yozuvlarda tekshiriladi, band bo'lsa 409 — xabarda egasining ismi ko'rsatiladi |
| GET | `/api/v1/clients/{id}` | `StaffReadUser` | Bitta mijoz + `orders_count`; topilmasa 404 |
| PATCH | `/api/v1/clients/{id}` | `ManagerUser` | Yangilash; telefon o'zgarsa unikallik qayta tekshiriladi; explicit `null` faqat `phone`, `phone_alt`, `address`, `notes` ga o'tadi (`drop_forbidden_nulls`) — ilgari `full_name: null` NOT NULL ustunga tushib 500 berardi |
| GET | `/api/v1/clients/{id}/detail` | `StaffReadUser` | `ClientDetail` — mijoz + uning BARCHA buyurtmalari (`ClientOrderRow`: raqam, loyiha nomi, holat, boshlang'ich to'lov (`advance_payment` — kartochkada qoldiq/qarz uchun), prioritet, muddat, summa), yangi buyurtma birinchi. Ro'yxatdagi qator ustiga bosilganda ochiladi |
| DELETE | `/api/v1/clients/{id}` | `ManagerUser` | **Buyurtmasi bor mijoz o'chirilmaydi — 409**, xabar nechta buyurtma borligini aytadi. `order.client_id` majburiy FK: yumshoq o'chirilgan mijozning buyurtmalari reestrda egasiz qatorga aylanardi. Yumshoq o'chirilgan buyurtma to'siq emas. Ish markazi o'chirishidagi qoida bilan bir xil (`machines._blockers`) |

**Mijoz REYTINGI** (`clients._reyting`): `total_amount` (bekor qilinmagan buyurtmalar summasi), `rank`, `share_pct` va ABC segmenti. HAMMA mijoz bo'yicha hisoblanadi, sahifa bo'yicha emas — o'rin va segment populyatsiya xossasi, aks holda ikkinchi sahifada "1-o'rin" chiqib qolardi. Ro'yxat ham SUMMA bo'yicha tartiblanadi (`id desc` emas). "Daromad" ta'rifi (`_DAROMAD`) bitta joyda — saralash va reyting ajralib ketmasin.

ABC (Pareto): A — aylanmaning birinchi 80%, B — 95% gacha, C — qolgani; chegarani KESIB o'tgan mijoz yuqori sinfda qoladi. Yulduzcha reyting bu ma'lumotda ishlamaydi — prodda o'lchandi: eng yirik mijoz aylanmaning **81%** ini beradi, ya'ni qolgan yigirmatasi bir xil past bahoni olardi (A: 1 mijoz, B: 6, C: 14).

Barcha mutatsiyalar `log_action` bilan audit qilinadi (`module="clients"`).

**Bog'lanishlar:** `backend/app/schemas/clients.py`, `backend/app/crud` (`crud_clients`, `log_action`), `backend/app/schemas/common.py` (`Paginated`, `Message`).

---

## `backend/app/api/routes/employees.py` — Hodimlar va beyjiklar

**Maqsadi:** Tsex hodimlari CRUD va beyjik (QR badge) boshqaruvi. Hodim — tizimga kirmaydigan shaxs; u terminalda beyjik skan qilib ishlaydi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/employees/` | `StaffReadUser` | Paginatsiya; `search` — ism bo'yicha QISMIY (`ilike`), beyjik bo'yicha esa ANIQ moslik (`badge_id == search`): skaner har doim to'liq UUID beradi, qismiy beyjik qidiruvi esa javobda ataylab yashirilgan `badge_id` ni prefiks-prefiks tiklab olish kanali edi (~400 GET bilan to'liq UUID chiqardi); `status` filtri (`EmployeeStatus`) |
| POST | `/api/v1/employees/` | `AdminUser` | 201; `badge_id` avtomatik `uuid4` sifatida yaratiladi va JAVOBDA QAYTARILMAYDI (tsexdagi yagona kirish kaliti — ekranga chiqmaydi); `assigned_post_ids` mavjudligi tekshiriladi, BO'SH bo'lishi mumkin (hamma xodim ish markazida ishlamaydi); `user_id` — ixtiyoriy kirish hisobi bog'lami (`_validate_user_link`: hisob mavjud (404), qurilma (TERMINAL/TABLO) yoki `is_system` texnik hisob emas (409), boshqa hodimga band emas (409)). Post rolidagi SHAXSIY hisobga ATAYLAB ruxsat — skanersiz postda (ARRA) xodim aynan shu hisob bilan kiradi |
| PATCH | `/api/v1/employees/{id}` | `AdminUser` | `assigned_post_ids` o'zgarsa qayta validatsiya; explicit `null` faqat `phone`, `position`, `user_id` ga o'tadi (`drop_forbidden_nulls`) — ilgari `full_name: null` NOT NULL ustunga tushib 500 berardi |
| POST | `/api/v1/employees/{id}/badge` | `AdminUser` | Beyjik yo'qolganda: yangi `uuid4` beriladi — eskisi darhol ishlamay qoladi, tarix shu hodimda qoladi; eski beyjik audit `meta`sida saqlanadi |
| POST | `/api/v1/employees/{id}/print` | `AdminUser` | Beyjikni chop etish navbatiga qo'yadi (`print_badge` arq task -> `mes:print:queue:{agent_id}` -> bridge-agent -> GoDEX). Printer ATAYLAB tanlanadi: `?agent_id=` berilsa o'sha, berilmasa yagona chop etuvchi agent, bir nechta bo'lsa **422** va ro'yxat. UI tomonda tanlov DIALOGDA (`employees.tsx` beyjik oynasi): bir nechta printer bo'lsa select chiqadi va `agent_id` yuboriladi, bitta bo'lsa tanlov ko'rsatilmaydi. Ilgari UI `agent_id` ni UMUMAN yubormasdi — ikkinchi printer paydo bo'lgan zahoti beyjik chop etish faqat xato toast berardi. Ish markazi shart emas: `printing_agents` agentni faqat `can_print` bo'yicha tanlaydi, shuning uchun ofisdagi beyjik printeri ish markazisiz ham ishlaydi. Printer umuman yo'q bo'lsa ham 422. Navbat (arq/Redis) ishlamayotgan bo'lsa **503** — bu infratuzilma nosozligi, huquq xatosi emas (ilgari 403 qaytardi va operatorga "ruxsat yo'q" bo'lib ko'rinardi). Brauzerdan chop etish TASHLANDI: u drayverdagi saqlangan qog'oz o'lchamiga tayanardi, agent esa DEVMODE bilan 80×60 ni majburlaydi |
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
| GET | `/api/v1/machines/overview` | `StaffReadUser` | `list[MachineOverview]` — Ish markazlari sahifasining jonli ustunlari: `accounts` (`user.machine_id` bilan biriktirilgan hisoblar), `agents` + `agent_online` (faol MES agentlari, 6 daqiqa qoidasi), `on_shift` (bugun ochilgan, yopilmagan smenalardagi hodimlar soni), `today_scans`, `last_scan_at`, `unfinished_routes` (BIRIKTIRILGAN, tugallanmagan qadamlar — CANCELLED/DELIVERED chiqariladi, `_blockers` bilan bir xil filtr; UI'da faqat o'chirish to'sig'i), `queue_scans` (terminal navbati qoidasi — `machine_id == men YOKI null` shu postda, PRODUCTION, yoqilgan qadamlar — qolgan skan yig'indisi; boshqaruv paneli «navbatda» bilan bir birlik; 2+ faol markazli postda biriktirilmagan ish ikkalasida ko'rinadi, terminalda ham shunday). `MachineRead` ro'yxatiga qo'shilmagan ataylab — u har select'da ishlatiladi; bu faqat sahifada 60s poll |
| POST | `/api/v1/machines/` | `AdminUser` | 201; `post_id` mavjudligi va NOM TAKRORLANMASLIGI tekshiriladi (`_check_name`, registrga sezgir emas) — indeks `ix_machine_name` baribir rad etardi, lekin xabari tushunarsiz bo'lardi |
| PATCH | `/api/v1/machines/{id}` | `AdminUser` | nom o'zgarsa takrorlanmasligi tekshiriladi; `post_id` o'zgarsa qayta tekshiriladi; **skan tarixi bor markazning posti o'zgarmaydi** (409) — o'tgan skanlar yangi post nomidan sanalib ketardi. `Machine` ning uchala ustuni ham NOT NULL, shuning uchun body'dagi explicit `null` `drop_forbidden_nulls` bilan tashlanadi (no-op) — ilgari `name: null` NOT NULL ustunga tushib 500 berardi |
| DELETE | `/api/v1/machines/{id}` | `AdminUser` | Soft-delete, LEKIN **bog'lam bo'lsa 409** (`_blockers`): biriktirilgan hisob (`user.machine_id`), printer agenti, ochiq smena (`crew_sessions` — YOSHIDAN qat'i nazar HAMMA aktiv smena sanaladi va bu yerda hech narsa yopilmaydi: smena muddati yo'q, uni terminalda «Chiqish»/logout yopadi), tugallanmagan marshrut (`total_done < total_required`, LEKIN faqat ochiq buyurtmaniki — `order.status` `cancelled`/`delivered` bo'lganlari va o'chirilgan buyurtmalar sanalmaydi, aks holda bekor qilingan buyurtma markazni abadiy o'chirilmas qilardi). Sabab xabarda nomlanadi |

**O'chirish nega to'sildi:** soft-delete FK'ni buzmaydi, lekin bog'lamni JIMGINA uzadi — qurilma hisobi E009 bilan kirolmaydi, agent skan-forvardi 409 beradi, tugallanmagan marshrutlar terminal ro'yxatidan yo'qoladi (filtr `machine_id` bo'yicha). Vaqtincha to'xtatish uchun o'chirish emas, `status` kerak.

**Bog'lanishlar:** `backend/app/schemas/machines.py`, `backend/app/crud` (`crud_machines`, `crud_posts`, `log_action`).

---

## `backend/app/api/routes/posts.py` — Ishlab chiqarish postlari

**Maqsadi:** 9 ta belgilangan post (ARRA, KROMKA, OVAL, PRISADKA, ROVER, STOLYARKA, BOYOQ, UPAKOVKA, TMO; `order_index` 1–10: OVAL 3, ROVER 6, UPAKOVKA 9, TMO 10 — 5-tartib olib tashlangan PAZ dan bo'sh qolgan) — ular `seed_defaults` komandasi bilan yaratiladi, shuning uchun API'da create/delete YO'Q, faqat o'qish va sozlash.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/posts/` | login (har qanday) | `order_index` bo'yicha tartiblangan postlar ro'yxati |
| PATCH | `/api/v1/posts/{id}` | `AdminUser` | Post sozlamalarini yangilash — `PostUpdate`: `name`, `requires_assignment_choice`. `order_index` ataylab TAHRIRLANMAYDI — uning yagona egasi `seed_defaults.POSTS`, u har prestart'da tartibni sinxronlaydi, ya'ni PATCH tahriri keyingi deploy'da jimgina yo'qolardi (`extra="ignore"`: eski klient yuborsa e'tiborsiz qoladi). `Post` ning uchala ustuni ham NOT NULL, shuning uchun body'dagi explicit `null` `drop_forbidden_nulls` bilan tashlanadi (no-op) — ilgari `name: null` NOT NULL ustunga tushib 500 berardi. Frontendda chaqiruvchi YO'Q (faqat generatsiya qilingan `src/client/sdk.gen.ts`) — endpoint qo'lda/admin so'rov uchun qolgan |

**Bog'lanishlar:** `backend/app/schemas/posts.py`, `backend/app/crud` (`crud_posts`, `log_action`), `backend/app/commands/seed_defaults.py`.

---

## `backend/app/api/routes/orders/` — Buyurtmalar (hayot sikli, matritsa, fayllar, anketa)

**Maqsadi:** Eng katta route moduli (21 endpoint) — MAVZU bo'yicha beshga bo'lingan paket: `lifecycle.py` (hayot sikli), `matrix.py` (marshrut matritsasi), `files.py` (`.project`/SCX/cutmap), `survey.py` (anketa) va `_common.py` (ko'rinish + tahrirlash qoidalari). `__init__.py` prefiks, tag va ro'yxatga olish TARTIBINI beradi; sub-routerlar yalang'och `APIRouter()` — tag ularda takrorlansa `include_router` uni qo'shib yuboradi va generatsiya qilingan klientda metod ikki klassga tushadi. Endpoint yo'llari, `operation_id` lari va marshrut tartibi bo'lishdan oldingi holat bilan AYNAN bir xil — buyurtma hayot sikli: `DRAFT → TECHNICAL_REVIEW → PRODUCTION → COMPLETED → DELIVERED` (+ istalgan bosqichda `CANCELLED`). Tahrirlash cheklovlari `_edit_block_reason` atrofida qurilgan: `_EDITABLE_STATUSES = (DRAFT, TECHNICAL_REVIEW)` va ularga qo'shimcha `PRODUCTION` — tsexda tirik skan bo'lmasa (quyida «Qachon tahrirlash mumkin»).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/orders/` | `ManagerUser` | 201; tartib raqami `crud_orders.next_number` ("B-2026-001" ko'rinishida, yiliga ketma-ket); ikki manager poygasida unique index hakam — `IntegrityError` bo'lsa 3 martagacha qayta uriniladi; WS `order.created` |
| GET | `/api/v1/orders/` | `StaffReadUser` | Paginatsiya; `status` filtri; `search` — raqam/loyiha nomi/loyiha UUID/mijoz ismi; DRAFT va CANCELLED buyurtmalar texnologga (superuser bo'lmasa) KO'RINMAYDI (`_hidden_statuses`) |
| GET | `/api/v1/orders/status-counts` | `StaffReadUser` | Reestr tablari uchun har holatdagi buyurtmalar soni; `_hidden_statuses` filtri bu yerda ham amal qiladi; `/{order_id}` dan OLDIN e'lon qilingan (aks holda "status-counts" order_id deb o'qilardi) |
| GET | `/api/v1/orders/{id}` | `StaffReadUser` | `OrderDetail`: mijoz ismi, biriktirilgan fayllar (`OrderFileRead`, `meta` bilan), `survey` (anketa JSON), `parts_count`, `instances_count`; yashirin holatdagi buyurtma texnologga to'g'ridan ID bilan ham 404 | `OrderDetail` da qo'shimcha: `last_action` / `last_action_at` / `last_action_by_name` — audit logning (`module=orders`, `entity_id`) eng yangi yozuvi (kim, nima, qachon), log bo'lmasa `null`; `cancelled_by_name` — bekor qilgan foydalanuvchi ismi.
| PATCH | `/api/v1/orders/{id}` | `ManagerUser` | DELIVERED/CANCELLED tahrirlanmaydi (403); `client_id` faqat DRAFT holatida almashtiriladi |
| PUT | `/api/v1/orders/{id}/survey` | `ManagerUser` | Mijoz anketasi + o'lchov varag'ini to'liq almashtiradi (`OrderSurvey` → `Order.survey` JSONB); DELIVERED/CANCELLED da 403; saqlashda o'chirilgan xonalarning rasmlari yetim qolmasin deb tozalanadi (quyida); audit `survey_saved` |
| POST | `/api/v1/orders/{id}/survey/photos` | `ManagerUser` | 201, multipart: `room_id` (Form, ≤40 belgi) + `file`; xona uchun namuna rasm; DELIVERED/CANCELLED buyurtmaga rasm qo'shib bo'lmaydi (403); javob `OrderFileRead`; audit `survey_photo_added` |
| DELETE | `/api/v1/orders/{id}/survey/photos/{file_id}` | `ManagerUser` | Rasmni o'chiradi — diskdan ham, bazada `is_deleted=True`; boshqa buyurtmaning yoki `DOCUMENT` bo'lmagan fayl uchun 404; audit `survey_photo_deleted` |
| POST | `/api/v1/orders/{id}/confirm` | `ManagerUser` | Tasdiqlash: `DRAFT → TECHNICAL_REVIEW` — buyurtma texnologga o'tadi; `amount` (narx) kiritilgan bo'lishi shart |
| POST | `/api/v1/orders/{id}/upload` | `TexnologUser` | `.project` fayl yuklash: DRAFT'da rad etiladi (avval tasdiqlansin); TECHNICAL_REVIEW va **hali ishlanmagan** PRODUCTION buyurtmada ruxsat (`_require_editable`, quyida); kengaytma va hajm (`MAX_PROJECT_FILE_SIZE`) tekshiriladi; parse xatosi 422; TEMPLATE (GibLab'da optimizatsiya qilinmagan) fayl 422 aniq yo'riqnoma matni bilan rad etiladi; qayta yuklashda `wipe_previous_parse` oldingi parse natijalarining DB qatorlarini yumshoq o'chiradi va eski fayllar YO'LINI qaytaradi (diskka tegmaydi), `ingest_project` yangisini yozadi; eski fayllar `db.commit()` dan KEYIN `drop_stale_files` da (`.stale` ga qayta nomlangan nusxalar) o'chiriladi, ingest yiqilsa `restore_stale_files` ularni qaytaradi, aks holda `ParseError` da DB orqaga qaytib, fayllar mangu yo'qolardi. Og'ir bosqichlar (XML parse, kesish xaritasi, SCX qurish va diskka yozish) `run_in_threadpool` da bajariladi — inline bo'lsa yuklash davomida hamma terminal, TABLO va WebSocket muzlab turardi. Qo'lda chizilgan (nostandart) marshrutlar fayldan kelmaydi, shuning uchun `snapshot_custom_routes` ular fizik o'chirishdan OLDIN (mahsulot kodi, detal kodi) bo'yicha saqlaydi va `restore_custom_routes` yangi detallarga tiklaydi; tiklanganlar soni va yangi faylda topilmagan detallar javob matnidagi ogohlantirishlarga qo'shiladi. Faylda mavjud bo'lmagan yana ikki narsa shu snapshot bilan qaytadi: detal IZOHI (`part.note`) va texnolog O'CHIRIB qo'ygan qadamlar (`is_enabled=False`) — aks holda izoh bo'shab, o'chirilgan amal esa qayta yonib qolardi (batafsil `docs/10` §7). PRODUCTION buyurtmada commit'dan oldin `stamp_route_machines` QAYTA chaqiriladi: ingest yangi `PartRoute` qatorlarini `machine_id=None` bilan yaratadi, muhr esa ilgari faqat `POST /{id}/start` da bosilardi — ya'ni `machine_assignments` joyida tursa ham marshrut o'sha postdagi HAMMA stanokda ko'rinardi |
| GET | `/api/v1/orders/{id}/matrix` | `StaffReadUser` | `OrderMatrix` (`_get_visible_order` — texnologga DRAFT/CANCELLED 404) — har detal (`MatrixPart`, `is_custom` bayrog'i bilan) va uning marshrut QADAMLARI (`RouteCell`, javobda `seq` bo'yicha tartiblangan) |
| PATCH | `/api/v1/orders/{id}/matrix` | `TexnologUser` | Matritsa tahriri: bosqich on/off (ARRA'ni o'chirib BO'LMAYDI — 403, faqat STANDART detalda), izoh, `is_custom` bayrog'i, nostandart marshrut (`route_codes`), soni o'zgartirish (`_resize_instances` fizik nusxalar va route summalarini moslashtiradi); tahrir shartlari — `_require_editable` (quyida); batafsil quyida |
| POST | `/api/v1/orders/{id}/machines` | `ManagerOrTexnologUser` | Bir postda bir nechta ish markazi bo'lsa manager tanlaydi; post/ish markazi mosligi tekshiriladi; **faqat AKTIV markaz** — TA'MIRDA/NOAKTIV bo'lsa 409 (ish bajariladigan joyi yo'q); tahrir shartlari — `_require_editable` (quyida). Buyurtma ALLAQACHON PRODUCTION bo'lsa (hali skansiz — `_require_editable` shunga ruxsat beradi) tanlov `PartRoute.machine_id` ga ham qayta muhrlanadi (`_common.stamp_route_machines`, `/start` bilan UMUMIY helper): ilgari faqat `order.machine_assignments` yangilanardi, marshrut esa eski stanokda qolib buyurtma yangi terminalda ko'rinmasdi va skan E001 berardi |
| POST | `/api/v1/orders/{id}/start` | `ManagerOrTexnologUser` | Ishlab chiqarishga uzatish (texnolog ham: faylni va marshrutni u tayyorlaydi): `TECHNICAL_REVIEW → PRODUCTION`; `.project` yuklangan bo'lishi shart; **marshrutsiz detal bo'lsa 403** (quyida); `requires_assignment_choice` postlarda ish markazi tanlanmagan bo'lsa 403; tanlangan ish markazi route yozuvlariga muhrlanadi (`_common.stamp_route_machines` — terminal filtri uchun); WS `order.started` Tanlov talab qiladigan postda aktiv stanok BITTA bo'lsa uzatishda o'zi biriktiriladi (`machine_assignments` ga yoziladi); 403 «Ish markazi tanlanmagan postlar» faqat 2+ aktiv variant bo'lib odam tanlamaganda yoki aktiv stanok umuman yo'qligida. |
| POST | `/api/v1/orders/{id}/cancel` | `ManagerUser` | Bekor qilish: TECHNICAL_REVIEW/PRODUCTION/COMPLETED da (DELIVERED/CANCELLED — 403; **DRAFT — 403 «Qoralama bekor qilinmaydi — uni o'chiring»**: qoralamada tijoriy ahamiyat yo'q, xato ochilganlar «Bekor qilingan» ro'yxatini to'ldirardi); sabab majburiy; skan tarixi audit uchun saqlanadi; WS `order.cancelled` — terminallar vazifalarni DARHOL tashlaydi |
| DELETE | `/api/v1/orders/{id}` | `ManagerUser` | Ikki yo'l, ikkalasida buyurtma qatori TOSHBITIK (`is_deleted=True`, `deleted_at`; ro'yxatlarda yo'q, raqam qayta berilmaydi — `next_number` `is_deleted` ni filtrlamaydi, `audit_log.entity_id` yetim qolmaydi): (1) **DRAFT** — menejer, sababsiz, bolalar yo'q; audit `deleted` «Qoralama o'chirildi», WS `order.deleted`; (2) **CANCELLED** — faqat superuser (aks holda 403): `product`/`part`/`part_instance`/`part_route`/`scan`/`waste_item`/`pachka`/`order_file` qatorlari va diskdagi fayllar (`.project`, SCX, anketa rasmlari) butunlay o'chadi, bekor qilinmagan skani bo'lsa 403 (skan = ish haqi); boshqa holatlar — 403 «avval bekor qiling». Audit yozuvi qoladi |
| POST | `/api/v1/orders/{id}/deliver` | `ManagerUser` | TOPSHIRILDI: faqat `COMPLETED → DELIVERED`; `delivered_at` avtomatik; WS `order.delivered` |
| GET | `/api/v1/orders/{id}/files/{file_id}` | `StaffReadUser` | Saqlangan faylni yuklab olish (`_get_visible_order`) (project/SCX/hujjat), `FileResponse`; `media_type`: PROJECT/SCX uchun `application/xml`, qolganlari uchun `meta["content_type"]` (yo'q bo'lsa `application/octet-stream`) — anketa rasmlari `<img>` da ko'rsatilishi uchun shart |
| GET | `/api/v1/orders/{id}/files/scx.zip` | `StaffReadUser` | Barcha SCX fayllar (`_get_visible_order`) bitta ZIP arxivda (`{number}_scx.zip`) — prisadkachi stanokka bittalab emas, bitta arxiv ko'chiradi; DB'da SCX qatori yo'q bo'lsa 404, qatorlardan BIRORTASINING fayli diskda topilmasa ham 404 — yetishmayotgan nomlar (birinchi 5 tasi) xato matnida sanaladi va KAMCHIL arxiv berilmaydi: prisadkachi uni to'liq deb olib detalni teshmay qoldirardi; bittalab yuklashdagi `download_order_file` ham xuddi shu holatda 404 |
| POST | `/api/v1/orders/{id}/scx/regenerate` | `TexnologUser` | SCX fayllarni saqlangan `.project`dan qayta yaratadi (eski buyurtmani yangi nomlashga o'tkazish: har nusxa = QR nomli fayl). Butun ish `ingest.rebuild_order_scx` da — `PATCH /matrix` soni o'zgarganda AYNAN shu helperni chaqiradi, ya'ni endpoint yupqa qobiq; detallar/marshrutlar/skanlarga TEGILMAYDI; eski SCX qatorlari `is_deleted` bilan belgilanadi, fayllar esa diskdan faqat `commit`dan KEYIN (`ingest.purge_replaced_scx`) va faqat hech bir tirik qator ularga ishora qilmasa o'chiriladi (generatsiya yiqilsa DB rollback qatorlarni tiriltiradi — fayl diskda qolishi shart; nom = nusxa QR'i, ya'ni yangi fayl eskisi bilan ustma-ust tushishi mumkin); `.project` diskda bo'lmasa 404 |
| GET | `/api/v1/orders/{id}/cutmap` | `StaffReadUser` | Kesish xaritasi holati (`_get_visible_order`) — admin-panel ko'rinishi va brauzer-print; terminal bilan umumiy `build_cutmap_state` (ARRA posti) |

**Yashirin holat qorovuli:** texnolog (superuser bo'lmagan) uchun DRAFT va CANCELLED buyurtmalar ro'yxatdan tushadi (`_hidden_statuses`) va to'g'ridan ID bilan ham ochilmaydi — `_get_visible_order` oltita o'qish yo'lida: `GET /{id}`, `/matrix`, `/files/{file_id}`, `/files/scx.zip`, `/cutmap`, hamda TABLO drill-down `GET /tablo/orders/{id}`. Mutatsiyalarga ATAYLAB tarqatilmagan: bekor qilingan buyurtmaga fayl yuklashga urinish "topilmadi" emas, sababni aytadigan xato berishi kerak.

Barcha mutatsiyalar `log_action` bilan audit qilinadi. `.project` parser qoidalari va cutmap tafsilotlari — `docs/09-mes-domain.md`.

### Qachon tahrirlash mumkin (`_require_editable`)

Fayl qayta yuklash, matritsa tahriri va ish markazi tanlovi — uchalasi BITTA
qoidadan o'tadi (`orders/_common.py: _edit_block_reason`):

| Holat | Tahrirlash |
|---|---|
| `DRAFT` | Faqat matritsa/markaz (fayl yuklash alohida 403 — avval tasdiqlash kerak) |
| `TECHNICAL_REVIEW` | Ha |
| `PRODUCTION` | **Faqat tsexda hech qanday ish qilinmagan bo'lsa** |
| `COMPLETED`, `DELIVERED`, `CANCELLED` | Yo'q |

"Ish qilingan" = shu buyurtmada BEKOR QILINMAGAN va o'chirilmagan skan bor
(`scan.is_cancelled = false AND scan.is_deleted = false`). Ya'ni ARRAda 2 detal
kesilib chek chiqarilsa-yu, keyin o'sha skanlar bekor qilinsa — buyurtma yana
tahrirlanadi. Bu ataylab: bekor qilingan skan hisoblagichni ham qaytaradi, ya'ni
tsexda haqiqatan hech narsa qilinmagan holatga tenglashadi.

403 xabari qaysi postda nechta skan borligini va birinchi skan vaqtini aytadi:
«tsexda ish allaqachon boshlangan — Arra postida 2 ta skan (26-08 14:10)».

`GET /api/v1/orders/{id}` javobida shu qoida `can_edit: bool` va
`edit_blocked_reason: str | None` bo'lib qaytadi — frontend tugmani shu bo'yicha
ko'rsatadi, ya'ni tugma ko'rinishi bilan server javobi hech qachon ajralmaydi.

### Marshrut matritsasi (detal × qadam)

Marshrut endi "qaysi postlar yoqilgan" to'plami emas, TARTIBLI qadamlar ketma-ketligi: `PartRoute` da `seq` (marshrutdagi o'rin, 1 dan) va `process_code` (`PROCESS_POSTS` — 1..16, aynan qaysi amal; bitta postda bir necha amal bor, masalan STOLYARKA da olti xil; 1–14 ni texnolog tanlaydi, 15 (qadoqlash) va 16 (TMO qabuli) — tizim qo'shadigan dum, `TAIL_CODES`). Bitta post marshrutda TAKRORLANISHI mumkin (kromka → prisadka → yana kromka), shuning uchun yagona indeks `(part_id, post_id)` dan `(part_id, seq)` ga ko'chdi (`ix_part_route_part_seq`, migratsiya `d5a1c93b70e2_part_route_seq.py`). Detal NOMI marshrutga umuman ta'sir qilmaydi — nomdagi `{ }` kodlari olib tashlangan.

Sxemalarga qo'shilgan maydonlar (`backend/app/schemas/orders.py`):

| Sxema | Maydon | Ma'nosi |
|---|---|---|
| `RouteCell` | `seq`, `process_code` | Bitta QADAM (avvalgi "katak" emas); `GET /matrix` qadamlarni `seq` bo'yicha tartiblab beradi |
| `MatrixPart` | `is_custom` | Nostandart detal bayrog'i (migratsiya `e7c4b208af13_part_is_custom.py`) — marshrutini texnolog o'zi chizadi |
| `MatrixPart` | `assembly_parent_id`, `assembly_children` | Yig'ma buyum: bu detal biriktirilgan ASOSIY detal va unga biriktirilgan mayda detallar ro'yxati (`[{"part_id", "code", "count"}]`) |
| `MatrixPartEdit` | `is_custom: bool \| None`, `route_codes: list[int] \| None`, `assembly_parent_id: int \| None` | Bayroqni almashtirish, qo'lda marshrut chizish va yig'ma buyumga biriktirish (`None` — bog'lamni uzish; maydon umuman yuborilmasa tegilmaydi — `model_fields_set`) |

`PATCH /matrix` qoidalari (bir so'rovda bir nechta detal tahriri, tartib: `note` → `count` → `is_custom` → `assembly_parent_id` → `route_codes` → `stages`):

- **`is_custom`** o'zgarsa marshrut manbasi almashadi: `True` da `AUTO` qadamlar YUMSHOQ o'chadi (`is_deleted=True`), `MANUAL` qadamlar tiklanadi; `False` da teskarisi. Qayta hisoblamay AYNAN tiklash sababi — fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi va texnolog qo'shgan qadamlar yo'qolardi.
- **`route_codes`** — jarayon kodlari TARTIB bilan (`[7, 11, 8]`), kod takrorlanishi mumkin (`[3, 6, 3]`), bo'sh ro'yxat marshrutni tozalaydi. Faqat `is_custom=True` detalga ruxsat (aks holda 403 "Marshrutni faqat nostandart detalga qo'lda chizish mumkin."). `PROCESS_POSTS` da yo'q kod → 403. Marshrut faqat ARRA yoki ROVER'dan boshlanadi (`_ROUTE_START_POSTS`) — chek shu ikki postda chiqadi, boshqasidan boshlansa detalda umuman QR bo'lmasdi. KROMKA marshrutda BIRINCHI kelganda `per_instance` = qirralar soni, takror kelganda 1 (qirralar bir marta yopishtiriladi); OVAL bu qoidaga KIRMAYDI — unda `per_instance` doim 1, chunki oval kromkada detal bitta o'tishda ishlanadi. Texnolog bergan kodlardan keyin marshrut DUMI avtomat qo'shiladi: anketada `packaging` bayrog'i bo'lsa UPAKOVKA (`process_code=15`), so'ng HAR DOIM TMO (16) — biriktirilgan mayda detalga (`assembly_parent_id` bor) dum QO'SHILMAYDI, u asosiy detal bilan birga qadoqlanadi va TMO ga alohida kirmaydi. Qatorlarni qurishning O'ZI `services/giblab/routes.py: build_manual_route()` da — `_set_custom_route` eski qadamlarni o'chirib va kodlarni tekshirib shu helperni chaqiradi, qayta yuklashdagi `restore_custom_routes` ham AYNAN shuni chaqiradi: qoida (KROMKA birinchi o'tishi, dum) ikki nusxada turganda bittasiga tegilishi bilan skan/ish haqi sonlari jimgina ajralib ketardi. Sozlanmagan post helperdan `ParseError` bilan chiqadi, endpoint uni 404 ga o'raydi (matn o'sha: «Post sozlanmagan: ...»).
- **`count`** (`_resize_instances`) fizik nusxalar va `PartRoute.total_required` ni moslashtiradi, ortiqcha nusxalarni YUMSHOQ o'chiradi va TIRIK nusxalarning QR'ini konvensiyaga qayta normallaydi (1 nusxa — suffikssiz, N nusxa — `_1.._n`). QR o'zgargani uchun SCX fayllari ham commit'dan OLDIN qayta yaratiladi (`ingest.rebuild_order_scx`, eski fayllar commit'dan keyin `purge_replaced_scx` da o'chadi) — fayl nomi = QR (`docs/11`), aks holda Nanxing yorliqdagi QR bo'yicha dasturni topolmasdi. `.project` diskda bo'lmasa (eski buyurtma) qayta yaratish JIM o'tkazib yuboriladi — matritsa tahriri shu sababdan yiqilmasin. Yozishdan OLDIN buyurtmadagi BOSHQA detallarning tirik `qr_text` lari o'qiladi: yangi QR band bo'lsa (masalan `010` ni 2 nusxaga chiqarish `010_2` kodli detalning ID siga urilsa) 422 "Detal ID to'qnashuvi: … bu buyurtmada boshqa detalga tegishli." — `ix_part_instance_qr_serial` unique indeksi xom 500 bermasin (ingest'dagi `qr_owner` tekshiruvining juftligi, `docs/11`).
- **`assembly_parent_id`** (yig'ma buyum, migratsiya `c9d4e2f81a70`) marshrutdan OLDIN o'rnatiladi — dum shu bayroqqa qarab qo'shiladi yoki qo'shilmaydi; marshrut o'zgarmay faqat bog'lam o'zgarsa marshrut mavjud kodlardan qayta quriladi. `_set_assembly_parent` bir pog'onani majburlaydi (biriktirilgan detal o'zi asosiy bo'la olmaydi va aksincha — 403, o'ziga biriktirish ham 403), `_check_assembly_match` esa mayda detalning OXIRGI amali asosiy detal marshrutida ham borligini talab qiladi (403) — birikish aynan o'sha qadamda ro'y beradi. Tekshiruv bog'lam o'zgarganda VA `route_codes` yuborilganda ishlaydi, ya'ni allaqachon biriktirilgan detalning marshrutini qayta chizish ham tekshiriladi. Tekshiruv BATCH OXIRIDA (hamma `edits` qo'llangach) yuritiladi — bitta PATCH'da ota marshrutiga amal qo'shilib bola o'sha amalda tugatilsa, edit tartibidan qat'i nazar yakuniy holat tekshiriladi.
- **`stages`** (post on/off) endi shu postdagi HAMMA qadamni birga yoqadi/o'chiradi — qadam-baqadam tahrir `route_codes` orqali. Yangi qadam qo'shilganda `seq` = DUMDAN TASHQARI qadamlarning maksimumidan keyingisi, dum (`TAIL_CODES` — UPAKOVKA/TMO) esa bir pog'ona yuqoriga suriladi; `process_code` = `DEFAULT_PROCESS_CODE[post.code]`. Dum hisobga olinsa yangi qadam TMO dan KEYIN tushib, qat'iy tartibda mangu E004 berardi. Surish ikki qadamda (`ingest.park_tail`/`unpark_tail` — qayta yuklashdagi marshrut tiklash bilan umumiy helper): `(part_id, seq)` qisman UNIQUE indeks dublikatni satr-ma-satr tekshiradi. ARRA'ni o'chirish taqiqi faqat STANDART detalda: nostandartda ARRA majburiy emas (rover'dan boshlanadigan oqim).

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

Yuklash cheklovlari (`orders/survey.py` dagi konstantalar):

- `_ROOM_PHOTO_TYPES` — faqat `image/jpeg` → `.jpg`, `image/png` → `.png`, `image/webp` → `.webp`; boshqasi 422 "Faqat JPG, PNG yoki WEBP rasm qabul qilinadi."
- `MAX_ROOM_PHOTO_SIZE = 5 MB` — oshsa 422 (telefon surati odatda 2–4 MB).
- `MAX_ROOM_PHOTOS = 6` — bitta `room_id` uchun; oshsa 422.

**Yetim rasm tozalash:** `save_order_survey` anketani yozgach, `room_id`si kelgan `rooms` ro'yxatida yo'q bo'lgan `DOCUMENT` fayllarni topadi (JSONB `meta ? 'room_id'` + `meta->>'room_id' NOT IN (...)`), diskdan `unlink` qiladi (`OSError` yutiladi) va `is_deleted`/`deleted_at` belgilaydi. Ya'ni xona anketadan olib tashlansa uning rasmlari ham yo'qoladi.

**Bog'lanishlar:** `backend/app/schemas/orders.py`, `backend/app/models/order.py` (`Order.survey`), `backend/app/services/giblab` (`ParseError`, `parse_project`; `ingest.py` dan `ingest_project`, `wipe_previous_parse`, `write_and_register_scx`), `backend/app/core/ws.py` (`ws_manager`), `backend/app/services/giblab/cutmap.py` (`build_cutmap_state`), `backend/app/services/giblab/routes.py` (`build_manual_route` — matritsa va qayta yuklash uchun umumiy), frontend tomoni: `frontend/src/routes/_layout/anketa.$orderId.tsx`, `frontend/src/lib/anketa.ts`.

---

## `backend/app/api/routes/audit.py` — Audit jurnali

**Maqsadi:** Barcha modullar yozgan audit yozuvlarini o'qish. Yozish API orqali emas — har mutatsion endpoint o'z tranzaksiyasida `crud.log_action` chaqiradi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/audit-logs/` | `AdminUser` | `Paginated[AuditLogRead]`; filtrlar: `module` (alias: `scan` so'rovi `scan` VA `scans` yozuvlarini oladi — prodda 19 ta qo'lda yozilgan `scans` yozuvi bor, kod doim `scan` yozadi; `_MODULE_ALIASES`), `action`, `user_id`, `q` (xabar bo'yicha `ilike` qidiruv), `date_from`/`date_to` — kun chegaralari Asia/Tashkent vaqtida (`_day_bounds`; naive-UTC bo'lsa "bugun" filtri 00:00–05:00 yozuvlarni yo'qotardi) |
| GET | `/api/v1/audit-logs/summary` | `AdminUser` | `list[AuditSummaryRow]` — modul × amal bo'yicha sonlar (`date_from`/`date_to` bilan, ro'yxat filtri bilan bir xil); Loglar sahifasi tab'lari va amal chiplari shundan quriladi — qo'lda yuritiladigan kategoriya ro'yxati yo'q, bo'sh modul tab bo'lmaydi, yangi `log_action(module=…)` o'zi chiqadi. Alias'lar birlashtirilgan holda qaytadi |

`AuditLogRead` sxemasi `backend/app/schemas/audit.py` da: user/employee, modul, amal, entity, xabar, `meta` (JSON), IP, vaqt, hamda `user_name`/`employee_name` ("kim" ustuni uchun `outerjoin` orqali — alohida so'rovsiz).

**Bog'lanishlar:** `backend/app/schemas/audit.py`, `backend/app/models` (`AuditLog`), `backend/app/crud` (`log_action` — yozuvchi tomon), `backend/app/core/config.py` (`TASHKENT_TZ`).

---

## `backend/app/api/routes/terminal.py` — Operator terminali

**Maqsadi:** Tsexdagi 17" touch-terminal API: kontekst, beyjik-smena, vazifalar navbati, ARRA/ROVER kesish xaritasi, yorliq chop etish, SCX fayllar. Endpointlar `require_roles(UserRole.TERMINAL, *POST_ROLES)` (`TerminalUser`) ortida; ikkita BEKOR QILISH endpointi — `DELETE /labels/{instance_id}` va `DELETE /waste/{waste_id}/label` — kengroq `LabelCancelUser` (terminal/operator + manager/texnolog) ostida. Ish markazi+post konteksti `TerminalCtx` dependency'si orqali keladi (`_terminal_ctx` → `resolve_terminal`, `ScanRejected` → 422 `{code, message}` — `scan_error()` helperi, `services/scanning.py` da: skan xatosini HTTP ga o'girishning YAGONA joyi, `terminal.py`, `pachka.py`, `tmo.py` va `scans.py` shuni chaqiradi) — u faqat kontekstga muhtoj route'larga qo'yilgan, yorliq, fayl va QR resolver (`GET /qr/{qr_text}/order`) route'lariga ATAYLAB emas: ish markazisiz terminal foydalanuvchisi ham yorliq chop eta olishi va QR skan qilib proyekt sahifasini ocha olishi kerak. `resolve_terminal` operator rollarida postni rolning o'zidan oladi (ish markazi — `user.machine_id`, u yo'q yoki o'chirilgan/NOAKTIV bo'lsa `post_machine` qoidasi: NOAKTIV markaz tanlanmaydi, AKTIV TA'MIRDA dan ustun turadi), TERMINAL akkauntda esa `user.machine_id`dan.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/terminal/context` | terminal/operator | Ish markazi+post konteksti va shu ish markazidagi OCHIQ smenalar ro'yxati (`crew` — brigada); smena muddati yo'q — u faqat «Chiqish», logout yoki keyingi kirish bilan yopiladi. Smenani `GET /terminal/context` o'zi ochmaydi: uch yo'l bor — `POST /terminal/session` (beyjik skani yoki ismni bosish), `/login/badge`, yoxud post rolidagi shaxsiy hisobning `/login/access-token` orqali parol bilan kirishi (`_open_shift_for` — `POST /login/access-token` qatoridagi besh istisno bilan). Post bo'lmagan rollarda smena umuman ochilmaydi. Ilgari operator rollarida "login = smena" shoxi bor edi, u soxta mirror hodim yozuvi bilan birga olib tashlangan (`c7e2b4f81d39`). `agent_online: bool \| null` + `agent_prints` — shu ish markazidagi MES agent holati (panel/chop etishdagi 6 daqiqalik oyna bilan bir ta'rif; null = agent biriktirilmagan; can_print'siz faqat-skan agent HAM qamraladi — u o'lsa skanlar jimgina yo'qolardi). Terminal headeri FAQAT uzilganda qizil «AGENT UZILGAN» chipini ko'rsatadi (onlaynda hech narsa — tray dublikati bo'lmasin; ikonka rolga qarab printer/skaner), jonli o'zgarish `bridge.connected/disconnected` WS eventlaridan (endi `machine_id` ham bor) |
| GET | `/api/v1/terminal/employees` | terminal/operator | "Kim ishlayapti?" ro'yxati — shu postga biriktirilgan FAOL hodimlar. Monoblok TERMINAL hisobi bilan allaqachon kirgan, ya'ni ro'yxat ochiq emas. Ismni bosish AUTENTIFIKATSIYA emas, ATRIBUTSIYA: qurilma tanitilgan, endi kim ishlayotgani yoziladi |
| POST | `/api/v1/terminal/session` | terminal/operator | Smenani ochadi. IKKI yo'l, natijasi bir xil: `badge_id` (skaneri bor post — bitta harakat) yoki `employee_id` (ekrandagi "Kim ishlayapti?" ro'yxatidan ism). `join=true` — BRIGADAGA qo'shiladi (ARRA da ikki kishi birga ishlaydi); sukut bo'yicha ALMASHTIRADI, ya'ni yakunlashni unutish xavfsiz tomonga og'adi. Bir odam ikki marta qo'shilmaydi — mavjud smenasi qaytariladi. Xatolar 422 `{code: "E006", message}` — beyjik topilmadi / nofaol / bu postga biriktirilmagan; WS `session.started` |
| POST | `/api/v1/terminal/session/end` | terminal/operator | Smenani yakunlaydi. `?employee_id=` berilsa FAQAT o'shaniki — brigadaning qolgani ishlayveradi (biri ketib, ikkinchisi qolishi odatiy hol); berilmasa hammasi. Aktiv smena bo'lmasa 404; WS `session.ended` |
| GET | `/api/v1/terminal/orders` | terminal/operator | Shu postga tegishli aktiv buyurtmalar (post sahifalari tanlagichi). Tartib: prioritet (`URGENT→HIGH→MEDIUM→LOW`), keyin deadline (nulls oxirida), keyin id — ifoda `models/order.py: PRIORITY_RANK` da, TABLO bilan UMUMIY (ikki joyda yozilsa ular ajralib ketardi va ishchi terminalda ko'rgan navbat devordagi taxtaga mos kelmasdi). `done`/`total` post semantikasida: ARRA — chek chiqarilgan YOKI skan qilingan nusxalar, **faqat ARRA marshruti bor detallar bo'yicha** (aks holda arradan o'tmaydigan detalning cheki — masalan roverchi o'zi chiqargani — arra hisobini jamidan oshirib yuborardi va listlar hali kesilmagan proyekt ro'yxatdan yo'qolardi); KROMKA — detal bo'yicha (nusxaning hamma tomoni skan bo'lsa "qilingan"); boshqa postlarda skan yig'indisi. Ishi TUGAGAN (`done >= total`) buyurtma HAR POSTDA ro'yxatdan tushadi — ilgari bu qoida faqat ARRA'da ishlar, boshqa postlarda tugagan proyektlar ro'yxatda abadiy turaverardi. Kartada (`TerminalOrderCard`) `materials`, `sheets_total`, `has_cutmap`. `sheets_total` kesish postlarida (ARRA/ROVER) faqat SHU postniki: buyurtmada bu postga bog'langan list bo'lmasa — 0 (ilgari `None` "kesish posti emas" deb tushunilib jami list ko'rsatilardi); boshqa postlarda buyurtmaning hamma listi. So'rov `survey` va `machine_assignments` JSONB'larini `defer()` qiladi — kartada `cutmap` va `material_usage` kerak, qolgan ikkitasi bu yerda o'qilmaydi |
| GET | `/api/v1/terminal/orders/{id}/cutmap` | terminal/operator | ARRA/ROVER kesish xaritasi: ROVER ham ochadi — marshruti arradan boshlanmagan detal butun listi bilan frezerda kesiladi, ya'ni roverchiga ham joylashuv kerak; shu ikkisidan boshqa postda 403 ("Kesish xaritasi faqat arra va rover postida ko'rsatiladi."). Har post O'Z skanlarini ko'radi (`done` — `build_cutmap_state` ga berilgan `post_id` bo'yicha), listlarni esa frontend `arra_route` bilan ajratadi; katak holati serverda — terminal qayta yonganda saqlanib qoladi. `CutmapInstanceState.custom` — detal NOSTANDART (`Part.is_custom`): marshrutini texnolog qo'lda chizgan va u arradan boshlanmasligi mumkin, shuning uchun xaritada binafsha chiqadi (chek chiqarilgach yashil) |
| GET | `/api/v1/terminal/orders/{id}/kromka` | terminal/operator | KROMKA/OVAL sahifasi (boshqa postda 403): shu post marshrutidagi qadamlar, har nusxada `done` (post skanlari) / `sides` (`per_instance` — KROMKA marshrutda birinchi kelganda qirralar soni, takrorida 1; OVAL da doim 1), `process_code` (3 — kromka, 4 — fasat kromka, 5 — oval), `arra_passed` (chek chiqarilgan yoki ARRA skan bor) |
| GET | `/api/v1/terminal/orders/{id}/prisadka` | terminal/operator | CNC sahifasi — PRISADKA va ROVER (boshqa postda 403), javob `PrisadkaOrderState`: detallar + har detalning SCX fayllari (`PrisadkaFile {id, filename}`), `arra_route` (marshrutida yoqilgan ARRA bormi — yo'q bo'lsa QR chek shu sahifadan chiqariladi, roverdan boshlanadigan oqim), `instances` (`PrisadkaInstance`: `instance_id`/`qr_text`/`label_printed`/`done`), `project_name` (frontend shu nom bilan papka ochadi) | `PrisadkaInstance.scans`/`need` (2026-09-03): nusxa bo'yicha skan soni va `per_instance` — terminal chipi yarim yo'lni ko'rsatadi.
| GET | `/api/v1/terminal/orders/{id}/queue` | terminal/operator | POST NAVBATI nusxa darajasida (BOYOQ, STOLYARKA) — `PostQueueState`. Postga bog'lanmagan: kontekstdagi postni oladi. Har nusxada `ready` (oldingi qadamlar shu NUSXADA tugadimi — `scanning.instance_stages`), `stage` (ishi TUGAGAN post nomi — detal jismonan qayerda turibdi), `done` (shu qadam yopilgan), `material` (bo'yoqchi uchun RANG), `note` (texnolog izohi), `process_code` (stolyarkada olti xil amal) va `assembly` (yig'ma buyumga biriktirilgan mayda detallar, `kod ×N` — HAR BIR ota nusxaga N dona: `child.count // parent.count`; bo'linmasa `×N jami`). Frontend `ready=false` qatorlarni KO'RSATMAYDI — ularni skanerlab bo'lmaydi (E004) |
| GET | `/api/v1/terminal/qr/{qr_text}/order` | terminal/operator | QR qaysi PRODUCTION buyurtmaga tegishligini topadi — `QrOrderRef` (`order_id`, `order_number`); picker'da skan qilinsa terminal o'sha proyektni o'zi ochadi |
| POST | `/api/v1/terminal/labels/{instance_id}` | terminal/operator | YORLIQ CHOP ETISH: ARQ `print_label` navbatiga qo'yiladi (bridge-agent/GoDEX); `label_printed_at` belgilanadi; WS `label.printed`. ARRA UI'da chiqarilgan katak YASHIL = "kesildi"; qayta chop etish frontendda bloklanadi (avval bekor qilish kerak). **KESISH POSTLARIDA CHOP ETISH = SKAN**: ARRA'da doim, ROVER'da esa detalning marshrutida ARRA bo'lmasa, shu so'rovda skan ham avto-yoziladi (`record_scan` + `finalize_scan`, `client_event_id="cutprint-<instance_id>-<unix_ts>"`, manba " (chek chiqarish bilan)"). Vaqt tamg'asi ataylab: doimiy `cutprint-<id>` bo'lganda chek bekor qilinib qayta chiqarilsa idempotentlik tekshiruvi eski (bekor qilingan) qatorni topib `duplicate` qaytarardi va `total_done` o'smasdi — eski shakl endi faqat tarixiy yozuvlarda uchraydi. **ARRA terminalida marshrutida yoqilgan ARRA qadami yo'q detalga chek UMUMAN chiqarilmaydi** — 422 `{code: "E001", message: "Bu detal roverda kesiladi — chekni rover terminalidan chiqaring."}` (u rover terminalidan chiqariladi; shu qoida "chek chiqarilgan = kesilgan" degan arra statistikasini saqlaydi). **Ish markazi aniqlanmagan terminalda chek UMUMAN chiqmaydi** — 422 «… ish markaziga printer biriktirilmagan — chek yuborilmadi»: `require_printer(None)` `NoPrinterBound` ko'taradi va u `db.commit()` dan OLDIN uchraydi, ya'ni `label_printed_at` ham saqlanmaydi (bajarilib tasdiqlangan). Shu yo'lga admin/superuser ham tushadi: `require_roles` ularni o'tkazadi, `resolve_terminal` esa E009 beradi. Avto-skansiz `PartRoute.total_done` o'smasdi: buyurtma COMPLETED bo'lmasdi va qat'iy tartibda keyingi POSTLARNING HAMMASI E004 bilan rad etilardi (arrachi xarita ochiqda alohida skan qilmaydi — skan maydoni yashirin). Skan rad etilsa (`ScanRejected`) chek baribir chiqadi, LEKIN rad jim ketmaydi: `print`/`rejected` audit yozuvi tushadi va javob matniga «DIQQAT: bosqich yopilmadi — …» qo'shiladi (`9179738`; `user_id` rollbackdan OLDIN olinadi) |
| DELETE | `/api/v1/terminal/labels/{instance_id}` | terminal/operator + manager/texnolog | Chekni bekor qilish: `label_printed_at = None`, WS `label.cancelled`. Chop etish YOZGAN skan ham bekor qilinadi (`client_event_id` `cutprint-`/`rvprint-` bo'yicha tanlanadi) va `total_done` qaytariladi — aks holda katak yashil bo'lib qolar, qadam hisobi esa oshgan holida qolardi; operator QO'LDA qilgan skanga tegilmaydi. **Bekor qilish huquqi POSTGA bog'langan** (manager/texnolog/admin/superuser — ataylab istisno): boshqasi kesish postida (ARRA yoki ROVER) turishi shart, aks holda 403 «Chekni faqat kesish posti (ARRA yoki ROVER) bekor qila oladi.»; avto-skanni boshqa post yozgan bo'lsa 403 (skandagi `post_id` dalil — marshrutdan taxmin qilinmaydi); chek chiqib skan yozilmagan holat uchun esa nusxadagi `instance.label_post_id` ustuni himoya qiladi — u boshqa post bo'lsa ham 403. Ya'ni chekni chiqargan post o'zi bekor qiladi. Terminalda long press (~600ms) + tasdiq dialogi; admin webdagi xaritada detal kartochkasidagi tugma (proyekt ARRA ro'yxatidan tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi). UI sharti faqat `label_printed_at` — chop etish skan yozgani uchun `done` doim true bo'ladi |
| GET | `/api/v1/terminal/labels/{instance_id}.png` | terminal/operator | Yorliqning PNG ko'rinishi (`load_label_data` + `render_label_png`) — brauzerdan istalgan printerga chop etish uchun (GoDEX shart emas); `Response(media_type="image/png")` |
| POST | `/api/v1/terminal/waste/{waste_id}/label` | terminal/operator | **FOYDALI ATXOT cheki** (GibLab `business` qoldig'i; GibSaw'dagi «Деловой остаток» muqobili): ARQ `print_waste_label`, o'sha GoDEX zanjiri. Sarlavhada «QOLDIQ» (tsex tili; «foydali atxot» — GibLab termini, chekda ishlatilmaydi), eng katta raqam — O'LCHAM, material, buyurtma·loyiha·list, `ATX-{buyurtma}-{n}` QR (prefiks skan dvijoki uni detal deb qidirmasligi uchun). Marshrut/skan tekshiruvi YO'Q — atxot ish bosqichi emas, material; printer biriktirilmagan bo'lsa 422; `label_printed_at` ENDPOINTDA yoziladi (detal cheki bilan bir xil — ilgari uni ARQ vazifasi yozardi va javobdan keyingi darhol qayta so'rov hali bo'sh qiymatni olib, katak rangi faqat keyingi yangilashda o'zgarardi), audit `waste_label_sent`. Kesish xaritasida `business` atxot katagi BITTA bosishda dialog ochadi (o'lcham + chek tugmasi); `CutmapState.waste_items` va katakdagi `atx` raqami bog'laydi |
| DELETE | `/api/v1/terminal/waste/{waste_id}/label` | terminal/operator | Qoldiq chekini BEKOR QILISH: `label_printed_at=None` (katak yashildan oqqa qaytadi), audit `waste_label_cancelled`. Detal skanidagi 60 s oynasi YO'Q — qoldiqda hech qanday bosqich yopilmaydi, bekor qilish istalgan vaqtda xavfsiz (rol `LabelCancelUser` — terminal/operator + manager/texnolog: proyekt ro'yxatdan tushgach xato chekni texnolog tuzatadi, detal cheki bilan bir xil qoida). CHEK CHIQARISH esa faqat terminaldan: admin ko'rinishida printer konteksti yo'q, shuning uchun panelda tugma ko'rsatilmaydi |
| GET | `/api/v1/terminal/files/{file_id}` | terminal/operator | SCX faylni stanok brauzeriga yuklab olish — har safar yangidan beriladi |

### Yorliq chop etish zanjiri

```
terminal (POST /terminal/labels/{instance_id})
  → arq: app.tasks.print_label(instance_id)
      load_label_data(db, instance_id) → LabelData
      render_label_png(data)   → PNG (80×60 mm, 203 dpi, 1-bit) → base64
  → Redis LPUSH mes:print:queue:{agent_id}  (manzilsiz job YARATILMAYDI — 422)
      job = {"type": "print", "job_id": <uuid4hex>, "instance_id": ..., "png": <base64>}
  → WS /api/v1/ws/bridge (brpop + ack)
  → bridge-agent → print-queue.jsonl (durable) → Windows GDI → USB GoDEX
```

GoDEX G500-U faqat USB bilan ulanadi — printerda tarmoq porti yo'q, shuning uchun backend printerga hech qachon to'g'ridan murojaat qilmaydi: `print_label` yagona ish sifatida Redis navbatiga qo'yadi. Job JSON'da to'rtta maydon: `type`, `job_id` (har yuborishda yangi `uuid4().hex` — agent takrorni shu bo'yicha tashlaydi; `instance_id` bu vazifani bajara olmaydi, chunki bekor qilib qayta chiqarishda u bir xil keladi), `instance_id`, `png`. PNG printer dialektiga bog'liq emas (QR kutubxona bilan chiziladi), shuning uchun backend hech qanday printer tili generatsiya qilmaydi.

`print_label` qaytaradigan qiymatlar: `queued:<id>` (Redis navbatiga qo'yildi), `skip:<id>` (nusxa topilmadi), `lost:<id>` (arq kontekstida Redis yo'q).

Agent tomoni (`bridge-agent/agent.py`) — bitta chiqish yo'li: `send_to_printer(png_b64)` → `_print_png_gdi` — PNG Windows drayveri orqali chiziladi (win32ui + PIL, DEVMODE 80×60 mm ga majburlanadi). Printer avtomatik topiladi: `_detect_printer()` nomida "godex" bor lokal Windows printerini qidiradi, `PRINTER_NAME` env faqat qo'lda override uchun. Agent env'lari: `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`, `SCAN_FORWARD` (default `1`; `0` — skan-forvard tinglovchisini o'chiradi). Agent faqat printer ulangan kompyuterga o'rnatiladi — menejer, texnolog va boshqa post terminallariga hech narsa kerak emas.

**Bog'lanishlar:** `backend/app/schemas/terminal.py`, `backend/app/services/scanning.py` (`resolve_terminal`, `crew_sessions`, `badge_employee`, `open_badge_session`, `end_session`, `record_scan`, `finalize_scan`, `instance_stages`, `scan_error`, `ScanRejected`), `backend/app/services/giblab/cutmap.py` (`build_cutmap_state`, `arra_parts_query`), `backend/app/services/labels.py` (`LabelData`, `load_label_data`, `_n`, `render_label_png` — 80×60 mm, 203 dpi, 1-bit; eskizda kromka konturdan TASHQARIDA tutash chiziq, paz/freza esa ICHKARIDA uzuq chiziq + «- - PAZ/OVAL» izohi, manba `xnc_summary["mill_sides"]`), `backend/app/tasks` (`print_label`, `PRINT_QUEUE_KEY`), `backend/app/core/ws.py`, `bridge-agent/agent.py`.

---

## `backend/app/api/routes/pachka.py` — Qadoqlash (Upakovka)

**Maqsadi:** Qadoq yaratish, detallarni qadoqqa skanerlash, yakunlash. Kontekst `PackCtx`
(`_pack_ctx`) — faqat UPAKOVKA postida ochiladi, boshqa postda 403. Qadoqni ALGORITM emas,
qadoqlovchi yig'adi: tizim taxminiy og'irlikni (`DENSITY = 700.0` kg/m³ × hajm) faqat KO'RSATADI.

| Metod | Path | Izoh |
|---|---|---|
| GET | `/api/v1/pachka/orders/{id}` | Qadoqlash holati: qadoqlar (tarkib + og'irlik) va hali qadoqlanmagan nusxalar (`ready` — `instance_stages` bo'yicha, tayyorlari tepada) |
| POST | `/api/v1/pachka/orders/{id}` | Yangi qadoq. Kod `PK-{buyurtma}-{NN}` — O'CHIRILGANLAR ham sanaladi, aks holda eski chek bilan yangi qadoq bir xil QR berardi. Buyurtmada ochiq qadoq turgan bo'lsa 409 (`_open_of`): terminal ekrani bir vaqtda faqat BITTA ochiq qadoqni ko'rsatadi, ikkinchisi ochilsa u ko'rinmay ham, yakunlanmay ham qolardi 2026-09-04: ochiq qadoq BO'SH bo'lsa 409 emas — u tashlanadi (`_discard_if_empty`, audit `discarded`) va yangi ochiladi: bo'sh qadoq tuzoq edi (yopib bo'lmaydi, yonida ochib bo'lmaydi, o'chirish yo'li yo'q). |
| POST | `/api/v1/pachka/{id}/scan` | Detalni qadoqqa. Bu AYNI PAYTDA marshrutning UPAKOVKA qadami (`record_scan_at`, `client_event_id="pack-{pachka}-{instance}"`) — qat'iy tartib shu yerda ham ishlaydi, ya'ni yopiq qadoq ichida chala detal bo'lishi mumkin emas. Boshqa buyurtma detali / allaqachon qadoqlangan nusxa 422; WS `pachka.item` 2026-09-04: `PK-`/`ATX-` chek → 422 E001 «Bu qadoq/qoldiq cheki — detal chekini skanerlang» (ilgari «Bunday QR topilmadi»); allaqachon qadoqda → E008 (ogohlantirish, E001 emas); rad etilgan skan `log_rejected_scan` bilan logga (/scans kabi). |
| DELETE | `/api/v1/pachka/{id}/items/{instance_id}` | Xato skanni qaytarish: nusxa qadoqdan chiqadi VA UPAKOVKA skani bekor bo'ladi (`total_done--`) — aks holda detal boshqa qadoqqa tushib ikki marta sanalardi |
| POST | `/api/v1/pachka/{id}/reopen` | Yopilgan qadoqni qayta ochish (status OPEN, `closed_at=None`, audit `reopened`); TMO ga qabul qilingan qadoq (jonli TMO skani bor) 403 — qayta ochib bo'lmaydi — `_open_pachka` xatosidagi «avval qayta oching» va'dasining bajarilishi. Allaqachon ochiq bo'lsa yoki buyurtmada boshqa ochiq qadoq bo'lsa 409. Qayta yakunlash chekni navbatga YANGIDAN qo'yadi, ya'ni chekni qayta chiqarish yo'li ham shu Ochiq BO'SH qadoq bo'lsa u tashlanadi va qayta ochiladi (`_discard_if_empty`). |
| POST | `/api/v1/pachka/{id}/close` | Yakunlash: status CLOSED + arq `print_pachka_label`. Bo'sh qadoq yakunlanmaydi (403). Chek chiqara olmasak qadoq YOPILMAYDI — tekshiruvlar commitdan OLDIN: navbat (arq/Redis) o'chgan bo'lsa 503, ish markaziga printer biriktirilmagan bo'lsa 422, ikkalasida ham «… qadoq yopilmadi … qayta urinib ko'ring» va qadoq OCHIQ qoladi (avval «Qayta ochish» kerak bo'lmasin uchun); WS `pachka.closed` `enqueue_job` o'zi yiqilsa (navbat tekshiruv bilan commit orasida o'chgan) qadoq OPEN ga qaytariladi va 503 — «yopiq-u cheksiz» holat bo'lmaydi. |

`instance_stages(db, order, post)` — `backend/app/services/scanning.py` da; qadoqlash,
TMO va post navbati ekranlari uchun umumiy (09-mes-domain.md §3.2).

---

## `backend/app/api/routes/tmo.py` — TMO (Tayyor Mahsulot Ombori)

**Maqsadi:** Marshrutning ENG OXIRGI qadami — QABUL va TOPSHIRISH. Kontekst `WhCtx` (`_wh_ctx`),
faqat TMO postida.

| Metod | Path | Izoh |
|---|---|---|
| GET | `/api/v1/tmo/orders/{id}` | (frontend 2026-09-04 dan chaqirmaydi — TMO ro'yxati umumiy `/terminal/orders/{id}/queue` dan; sxema `accept` javobi uchun qoladi) |
| POST | `/api/v1/tmo/orders/{id}/accept` | QABUL. QR `PK-` bilan boshlansa — qadoq: ichidagi HAMMA nusxa bitta skanda qabul qilinadi (omborchi qadoqni ochmaydi); aks holda bitta detal. Ochiq (yakunlanmagan) qadoq qabul qilinmaydi. `client_event_id="wh-{order}-{qr}"` — idempotent; rad etilgan skan `log_rejected_scan` bilan `scan`/`rejected` audit logga tushadi (/scans va /pachka kabi) — qadoq QR'ida bitta nusxa rad etilsa BUTUN qabul orqaga qaytadi; WS `tmo.accepted` |

TMO buyurtmani TOPSHIRMAYDI. Hamma detal TMO dan o'tgach buyurtma o'zi `COMPLETED` (tayyor) bo'ladi — statusni oxirgi marshrut qadami yopilganda `scanning.record_scan_at` qo'yadi. `DELIVERED` esa managerning alohida amali: `POST /api/v1/orders/{id}/deliver`, faqat `COMPLETED` holatdan.

---

## `backend/app/api/routes/scans.py` — Skan ro'yxatga olish va bekor qilish

**Maqsadi:** Terminaldagi QR skanlarni qayd etish/bekor qilish. Rol: `require_roles(UserRole.TERMINAL, *POST_ROLES)`. Butun domen logikasi `app/services/scanning.py` da — endpoint yupqa adapter.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| POST | `/api/v1/scans/` | terminal/operator | `record_scan` chaqiradi; rad etilsa 422 `{code, message}` (**E001–E010** xato kodlari, §09 §3.0). `ATX-` prefiksli QR (qoldiq cheki) `record_scan` gacha yetmaydi: endpoint boshida ushlanib 422 `{code: "ATX", ...}` bilan TO'LIQ MA'LUMOT qaytariladi (o'lcham, material, buyurtma·loyiha·list, chek holati) — xato emas, terminal ko'k info chiziq ko'rsatadi; qoldiq marshrutda yurmagani uchun hech narsa yopilmaydi; muvaffaqiyatda WS eventlar publish qilinadi; javob `ScanResult`: `scan_id`, `duplicate`, `qoldiq` (`scx_file_ids`/`project_name` olib tashlangan — hech bir klient o'qimasdi; PRISADKA sahifasidagi "Hammasini yuklab olish" papka nomini `PrisadkaOrderState.project_name` dan oladi), `order_stage_completed`, `order_completed` va detal ma'lumotlari; rad etilgan urinish ham `log_rejected_scan` helper (`services/scanning.py`) orqali `scan` modulida audit logga yoziladi UPAKOVKA postida umumiy skan 422 E001 rad etiladi (2026-09-04): qadoqsiz UPAKOVKA skani qadamni yopib detalni qadoqlab bo'lmaydigan qilardi — qadoq skani faqat `/pachka/{id}/scan`. |
| DELETE | `/api/v1/scans/{scan_id}` | terminal/operator | Skanni bekor qilish (undo) — `cancel_scan`; hisoblagichlar qaytariladi, WS eventlar publish qilinadi; javob `ScanHistoryItem` 2026-09-04: qadoq skani (`pack-…`) bekor qilinsa detal OCHIQ qadoqdan ham chiqariladi (ilgari qadoqda qolib, qadami ochiq — qayta skanerlab ham, TMO ga topshirib ham bo'lmasdi; lokalda bajarilib tasdiqlangan), yopiq qadoqda E001 «avval qadoqni qayta oching». |

Skan qabul qilish qoidalari (marshrut/ketma-ketlik tekshiruvi, dublikat) va xato kodlari jadvali — `docs/09-mes-domain.md` §3 va §3.0 da.

**Bog'lanishlar:** `backend/app/services/scanning.py` (`record_scan`, `cancel_scan`, `finalize_scan`, `log_rejected_scan`, `ScanRejected`), `backend/app/schemas/terminal.py` (`ScanRequest`, `ScanResult`, `ScanHistoryItem`), `backend/app/core/ws.py`.

---

## `backend/app/api/routes/tablo.py` — TABLO (tsex televizori)

**Maqsadi:** Buyurtmalar × bosqichlar jonli matritsasi. Read-only, har qanday login qilgan foydalanuvchi/qurilma (TABLO akkaunt ham, ofis ham).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/tablo/matrix` | login (har qanday) | `TabloMatrix`: postlar ro'yxati + **faqat PRODUCTION** buyurtmalar; tartib — `PRIORITY_RANK` (URGENT→HIGH→MEDIUM→LOW), keyin `deadline` (nulls oxirida), keyin `id` — terminal ro'yxati bilan AYNAN bir xil. Har qatorda `idle_days` — buyurtma oxirgi qimirlaganidan beri TSEX NECHA KUN ishlagani (`None` — hech qachon skan qilinmagan). Kalendar kuni ATAYLAB emas: dam olish/bayramdan keyin butun taxta "to'xtagan" bo'lib yonardi. "Tsex ishlagan kun" = o'sha kuni bironta skan bo'lgan kun, ya'ni ta'til ro'yxatini yuritish shart emas. Buyurtma taxtadan hamma detali TMO dan o'tgan zahoti tushadi — bu COMPLETED holatining o'zi (oxirgi marshrut qadami TMO qabuli, `scanning.record_scan_at` statusni qo'yadi), ya'ni alohida filtr shart emas. Managerning "TOPSHIRILDI" tugmasi taxtaga ta'sir qilmaydi: u DELIVERED ni yozadi, taxta esa undan oldin tozalangan bo'ladi. Devordagi ekran TSEX ishi uchun — TMO dan o'tgan buyurtmada tsex ishi qolmaydi. (`COMPLETED_WINDOW` 30 kunlik oyna olib tashlangan: endi ro'yxatni TMO ning o'zi cheklaydi.) `idle_days` bazasi — oxirgi skan kuni, skan bo'lmasa ishlab chiqarishga uzatilgan kun (`production_started_at`, Toshkent); shundan keyingi TSEX ISHLAGAN kunlar soni. `null` faqat bazasi yo'q buyurtmada. |
| GET | `/api/v1/tablo/orders/{id}` | login (har qanday) | Drill-down (SONI NAZORATI): har detal × bosqich done/total. Katakcha post bo'yicha, marshrut esa qadamli — bitta post takrorlansa (kromka → prisadka → kromka) qadamlar QO'SHILADI, aks holda oxirgi qadam oldingisining ustiga yozilib bajarilgan ish yo'qolardi. Ko'rinuvchanlik reestrdagi `GET /orders/{id}` bilan bir xil: `_get_visible_order` orqali texnologdan yashiringan holatlar (DRAFT, CANCELLED) bu yerdan ham 404 «Buyurtma topilmadi.» beradi — aks holda taxta drill-down'i tasdiqlanmagan/bekor qilingan buyurtmaning raqami va loyiha nomini ochib qo'yardi |

Javob sxemalari `backend/app/schemas/tablo.py` da: `TabloMatrix` (`posts` — typed `TabloPostCol` ro'yxati), `TabloOrderRow`, `StageAgg`, `TabloOrderDetail`, `TabloPartRow`.

**Bog'lanishlar:** `backend/app/schemas/tablo.py`, `backend/app/services/metrics.py` (`part_volume`), `backend/app/models` (`Order`, `PartRoute`, `Post`).

---

## `backend/app/api/routes/reports.py` — Hisobotlar va dashboard statistikasi

**Maqsadi:** Boshqaruv hisobotlari. Rol: `require_roles(MANAGER, DIRECTOR)` (admin/superuser har doim o'tadi). Uch hisobot default JSON qaytaradi, `?format=xlsx` bilan Excel fayl stream qilinadi (`services/excel.xlsx_response`). Sana oralig'i berilmasa — oxirgi 30 kun (bugun bilan birga, ya'ni `bugun-29 … bugun`), chegaralar Asia/Tashkent bo'yicha inklyuziv kunlar (`TASHKENT_TZ`, `app/core/config.py`). `.xlsx` katakchalarida aware (UTC) `datetime` ham `TASHKENT_TZ` ga o'tkazib formatlanadi (`_cell`), ya'ni fayldagi soatlar UI bilan bir xil. Javob sxemalari `backend/app/schemas/reports.py` da (8 model: `ProductivityReport`, `OrdersReport`, `MaterialsReport`, `DashboardStats` va ularning qator modellari).

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/reports/productivity` | manager/direktor | Hodim mahsuldorligi: skan soni (skan uni urgan — langar smena egasiga to'liq; smena vaqti bo'yicha brigada bo'linishi yo'q), faol kunlar, kuniga/soatiga o'rtacha; `?format=xlsx` |
| GET | `/api/v1/reports/orders` | manager/direktor | Buyurtmalar holati: holat, muddatlar, `overdue` belgisi (muddat o'tgan tugallanmaganlar), bekor sababi; `?format=xlsx` |
| GET | `/api/v1/reports/materials` | manager/direktor | Material sarfi: `Order.material_usage` JSONB'dan agregatsiya (`project_loaded_at` oralig'ida, CANCELLED chiqariladi); `?format=xlsx`. Guruhlash kaliti — `(code or name, kind)` (qatorda `code` ham qaytadi — UI kaliti va nom yonida ko'rsatiladi): katalog SKU kodi barqaror, nom emas (bir xil nomli ikki SKU ilgari bitta qatorga qo'shilib ketardi; eski, `code` siz eksportlarda nomga qaytadi). `orders` ustuni BUYURTMALARNI sanaydi, JSONB yozuvlarni emas — bir buyurtmada takrorlangan material bir marta hisoblanadi |
| GET | `/api/v1/reports/dashboard` | manager/direktor/**texnolog** | Boshqaruv paneli — BITTA so'rov, faqat JSON (`DashboardStats`): `today` (bugungi va kechagi skanlar, `on_shift` — bugun ochilgan va yopilmagan smenalardagi hodimlar soni, bugun ishga tushgan/tayyor/topshirilgan buyurtmalar), `orders` (jarayonda / muddati o'tgan / bugun muddati / muddatsiz / tayyor-topshirilmagan sonlari), `ready` (COMPLETED buyurtmalar, eng uzoq kutayotgani birinchi, `waiting_days`, ≤50), `posts` (har post: qolgan skanlar va hajm — Tablo bilan bir xil `part_volume` hisobi, ishi qolgan buyurtmalar soni, bugungi skanlar, `down` — ACTIVE bo'lmagan ish markazlari nomlari), `trend` (oxirgi 14 lokal kun, bo'sh kun 0), `money` (narx − boshlang'ich to'lov qoldig'i musbat buyurtmalar: summa, soni, topshirilganlari; DRAFT/CANCELLED chiqariladi) — `money` FAQAT boshqaruvga (`is_superuser` yoki admin/manager/direktor), texnologga `null`. Ilgari faqat ish markazi navbatini qaytarardi (`MachineStat`), post-darajaga o'tdi: prodda har postda bitta ish markazi, panel esa post tilida o'qiladi |

**Bog'lanishlar:** `backend/app/schemas/reports.py`, `backend/app/services/excel.py` (`xlsx_response`), `backend/app/services/metrics.py` (`part_volume`).

---

## `backend/app/api/routes/bridge_agents.py` — MES agentlari va pairing

**Maqsadi:** Printerli kompyuterdagi bridge-agent'ni serverga ulash (pairing) — podpiska modeli uchun: admin panelda kod beriladi, agent kodni doimiy tokenga almashtiradi. Serverga SSH kirish ham, `.env` tahriri ham kerak emas. Har printerning o'z tokeni bor — birini bekor qilish qolganlariga tegmaydi.

Router `/api/v1/bridge-agents` prefiksi bilan **himoyasiz** ulanadi (`/pair` chaqirilganda agentda sessiya yo'q), shuning uchun admin endpointlarning har biri o'z signaturasida `AdminUser` talab qiladi.

| Metod | Path | Rol | Izoh |
|---|---|---|---|
| GET | `/api/v1/bridge-agents/` | `AdminUser` | Agentlar ro'yxati (`BridgeAgentRead`: `id`, `name`, `paired`, `pair_code`, `pair_expires_at`, `last_seen_at`, `created_at`, `machine_id`, `machine_name`, `version`, `can_print`); `pair_code` faqat muddati o'tmagan bo'lsa qaytariladi, aks holda `null` |
| PATCH | `/api/v1/bridge-agents/{id}` | `AdminUser` | Ish markazi bog'lash (`machine_id` — skan-forvard uchun) va chek-chiqarish belgisi (`can_print`); maydonlar alohida yuboriladi (`exclude_unset` — berilmagani tegilmaydi); audit `machine_linked` (bog'lashda) / `machine_unlinked` (`machine_id: null` — uzishda) / `can_print_changed` |
| POST | `/api/v1/bridge-agents/` | `AdminUser` | 201; agent yaratiladi va **bir martalik 8 belgili ulanish kodi** beriladi (`PAIR_TTL` = 15 daqiqa); audit `created`; `machine_id` kod berilishidan OLDIN so'raladi (ilgari alohida qadam edi va esdan chiqib qolardi), lekin MAJBURIY EMAS: chek chiqarish (`require_printer` -> 422) va skan-forvard (`bridge_scan` -> 409) uchun shart, OFISDAGI beyjik printeriga esa ish markazi kerak emas — `printing_agents` agentni faqat `can_print` bo'yicha tanlaydi. Band ish markazi 409 |
| POST | `/api/v1/bridge-agents/{id}/code` | `AdminUser` | Yangi ulanish kodi (kod eskirgan yoki kompyuter almashgan holat); `token_hash` tozalanadi — eski kompyuter keyingi ulanishda rad etiladi; audit `code_regenerated` |
| DELETE | `/api/v1/bridge-agents/{id}` | `AdminUser` | Soft-delete; jonli WebSocket ham uziladi (`_revoke_live_connection` Redisga `mes:agent:revoked:{id}` bayrog'ini qo'yadi, TTL 10 daqiqa — `/ws/bridge` sikli uni HAR iteratsiyada ~5 s da o'qiydi); navbatda qolgan cheklar ham o'chiriladi va nechtasi bekor qilingani javob xabarida aytiladi (aks holda operator "chek yuborildi" ni ko'rib qog'oz kutib qolardi); audit `deleted` |
| POST | `/api/v1/bridge-agents/pair` | **Yo'q (ochiq)** | Agent bir martalik kodni doimiy tokenga almashtiradi; javob `BridgePairResponse` (`token`, `name`); audit `paired` (`user_id=None`); WS `bridge.paired` — admin sahifasi pollingsiz yangilanadi; javobda `machine_name` ham (bog'langan stanok — agent ulanish xabarida «skan-forvard shu stanok nomidan yoziladi» deb ko'rsatadi) |
| GET | `/api/v1/bridge-agents/latest` | ochiq | Oxirgi agent exe versiyasi+sha256 (`agent-dist/version.json`, CI yozadi) — agent har qayta ulanishda va zaxira sifatida har 10 daqiqada (v1.4.3) tekshirib O'ZI yangilanadi (v1.4.0+); fayl yo'q bo'lsa 404 |
| GET | `/api/v1/bridge-agents/download` | ochiq | `mebelix-agent.exe` (FileResponse) — CI har deploy'da qurib `agent-dist/` ga qo'yadi, panel havolasi va agent self-update shu yerdan tortadi |
| POST | `/api/v1/bridge-agents/logs` | Agent tokeni (`Authorization: Bearer`) | Agent o'z log satrlarini yuboradi (`BridgeLogPush`: `lines`, ≤200 satr). Redis `mes:agent:log:{agent_id}` ro'yxatida saqlanadi — oxirgi `AGENT_LOG_KEEP = 200` satr, TTL 7 kun. Tsexdagi kompyuterga masofadan kirish yo'q, shuning uchun diagnostika shu yo'l bilan chiqadi |
| GET | `/api/v1/bridge-agents/{id}/logs` | `AdminUser` | O'sha agentning oxirgi log satrlari (eng yangisi birinchi), `list[str]`. Agent topilmasa 404 |
| POST | `/api/v1/bridge-agents/scan` | Agent tokeni (`Authorization: Bearer`) | Skan-forvard: stanok skaneri o'qigan QR agent orqali MES'ga yoziladi — agentga bog'langan ish markazining AKTIV sessiyasi nomidan (`record_scan_at` + `finalize_scan`, odatdagi skan yo'li); ish markazi bog'lanmagan / sessiya yo'q — 409; sessiya terminal bilan AYNAN bir xil `active_session` qoidasidan o'tadi — langar smena egasi nofaol bo'lsa ham 409 (smenaning MUDDATI esa yo'q); rad etilgan skan ham `log_rejected_scan` bilan `scan`/`rejected` audit logga tushadi, javob `ScanResult`. **STANOK FORVARDI QOROVULI (2026-09-12):** shu nusxa oxirgi 10 soniyada BOSHQA postda skan qilingan bo'lsa forvard yozilmaydi — `E010`, `record_scan_at(from_agent=True)`. Agent o'z kompyuteridagi HAR QANDAY skanni eshitadi, brauzerda esa boshqa postning terminali ochiq bo'lishi mumkin (monoblok ishlamay qolganda tsex shunday qiladi): bitta fizik skan ikki postga tushardi. `E010` da WS `scan.rejected` YUBORILMAYDI — ish to'g'ri bajarilgan, terminal ekraniga yolg'on qizil banner chiqmasin; audit yozuvi qoladi. **QOLDIQ (`ATX-`) va QADOQ (`PK-`) QR'lari skan yo'liga umuman qo'yilmaydi** — 422 `{code: "SKIP", message: "Bu QR detal skani emas — terminalda skanerlang."}`: ularning o'z oqimi bor (ATX terminal `/scans` da to'liq ma'lumot beradi, PK esa TMO qabulida ishlatiladi), stanok skaneridan o'tsa esa `_QR_RE` dan yiqilib E002 "QR formati buzuq" degan qizil xato berardi. **BEYJIK (UUID) esa jimgina chetlab o'tiladi** (`_BADGE_RE` — yuqoridagi `ATX-`/`PK-` tekshiruvidan KEYIN, ish markazi va sessiya qorovullaridan OLDIN, 422 `{code: "BADGE"}`): operator smena ochish uchun beyjigini skanerlaganda agentning global klaviatura kuzatuvchisi uni ham ilib olardi va odatdagi yo'ldan o'tib E002 bilan rad etilardi — audit shovqini + terminal ekranida QIZIL banner va xato ovozi (prodda 9 marta o'lchandi). Endi log ham, WS xabari ham yo'q; yangi agent (v1.4.4+) buni umuman jo'natmaydi, serverdagi tekshiruv eski agentlar uchun; **BEKOR QILINGAN AGENT DARHOL UZILADI**: `regenerate`/`delete` Redisga `mes:agent:revoked:{id}` bayrog'ini qo'yadi (TTL 10 daq) va `last_seen_at` ni tozalaydi — `/ws/bridge` sikli bayroqni HAR iteratsiyada (~5 s) o'qiydi, panel esa darhol "Uzilgan" ko'rsatadi (ilgari revoke faqat 5 daqiqalik `touch_agent` da sezilardi: bekor qilingan token shu vaqt davomida chek olib chop etaverardi — 295 s repro bilan o'lchangan). `delete` navbatdagi cheklarni ham o'chiradi va nechtasi bekor qilinganini javobda aytadi; `pair` bayroqni tozalaydi. Bir ish markaziga ikkinchi agentni bog'lash 409 |

**Ulanish kodi:** `_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"` — I/L/O/0/1 yo'q, telefonda aytganda adashtirmaydi. 31 belgi × 8 uzunlik (`_CODE_LEN = 8`) = 31⁸ ≈ 8.5·10¹¹ kombinatsiya, 15 daqiqalik oynada brute-force amalda imkonsiz.

**Pairing xavfsizligi** (`POST /pair`):

- Atomik `UPDATE ... RETURNING` — bir kodni ikki kompyuter bir vaqtda yuborsa faqat bittasi yutadi (kod shu tranzaksiyada `NULL` ga o'tadi).
- Kod topilmasa ham, muddati o'tgan bo'lsa ham **bitta umumiy xato**: 400 "Ulanish kodi noto'g'ri yoki muddati o'tgan." — kodning bor-yo'qligi oshkor qilinmaydi.
- Kirishda `-` va bo'shliqlar olib tashlanadi, harflar katta registrga o'tkaziladi (qo'lda kiritishga bardosh).
- Token `secrets.token_hex(24)` bilan yaratiladi va **faqat shu javobda** beriladi; bazada `token_hash` sifatida sha256 xeshi qoladi.

Agent exe'ni yuklab olish endpointi 2026-08-27 da QAYTA qo'shildi (`GET /bridge-agents/download`, yuqoridagi jadval) — flashka bilan tarqatish o'rniga. U 2026-08-02 da aynan "diskdagi eski exe'ni berib adashtiradi" degan sabab bilan olib tashlangan edi; endi manba yagona: CI har deploy'da windows-runner'da exe'ni qurib, `version.json` (versiya + sha256) bilan `agent-dist/` ga qo'yadi, ya'ni eskirishning iloji yo'q. Ikkala endpoint ham OCHIQ: agentda sessiya yo'q, exe sir emas, `/pair` ham ochiq.

**Agent tomoni** (`bridge-agent/agent.py`): PyInstaller onefile `mebelix-agent.exe` — tsex kompyuteriga Python o'rnatish shart emas. `_load_dotenv()` config'ni shu tartibda o'qiydi: env var > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`. `_pair()` (import paytida chaqiriladi) birinchi ishga tushishda kichik tkinter oynasi (`_pair_dialog()`) orqali server manzili va ulanish kodini so'raydi, `_exchange()` ularni `POST /pair` ga yuboradi va olingan tokenni `%APPDATA%\MebelixAgent\.env` ga yozadi; kod noto'g'ri bo'lsa oyna xato matni bilan qayta ochiladi. `BRIDGE_TOKEN` allaqachon bor bo'lsa `_pair()` darhol qaytadi — hech narsa so'ralmaydi; aks holda oyna har doim ochiladi, `stdin` tty bo'lishi shart emas (exe `--noconsole` bilan quriladi, konsol umuman yo'q). Faqat tkinter ishlamagan muhitda (dev/Linux) `_pair_console()` zaxira sifatida ishlaydi, u ham kod ololmasa `SystemExit("Ulanish bekor qilindi.")` — agent jim davom etmaydi, xato oynasini ko'rsatib to'xtaydi. Qolgan hammasi o'zgarmagan — printer avto-topiladi, `print-queue.jsonl` durable navbat, `_print_png_gdi` chiqish yo'li.

**Skan-forvard klienti ham agentning o'zida**: `pynput` klaviatura tinglovchisi stanok skanerining wedge kiritishini ushlaydi (Enter bilan yakunlangan 6–64 belgili satr, belgi tezligi <50 ms — odam terishi bunday tez emas) va uni agent tokeni bilan `POST /bridge-agents/scan` ga yuboradi. `SCAN_FORWARD=0` env o'chiradi; `pynput` o'rnatilmagan bo'lsa o'zi jim o'chadi. Beyjik (UUID shaklidagi kod) YUBORILMAYDI — u terminalning o'z smena oqimiga tegishli (v1.4.4+). **MES TERMINALI FOKUSDA BO'LSA HAM YUBORILMAYDI (v1.4.8):** fokusdagi oyna sarlavhasi `ctypes.windll.user32.GetForegroundWindow`/`GetWindowTextW` bilan o'qiladi va «Terminal | MebeliX» qism-satri qidiriladi (brauzer sarlavhaga « - Google Chrome» quyrug'ini qo'shadi; TABLO va kirish ekrani ataylab mos kelmaydi). Sabab: forvard Nanxing dasturiga ketayotgan skanning NUSXASI — terminal fokusda bo'lsa skanni brauzerning O'ZI yozadi va nusxa ikkinchi yozuvga aylanadi (2026-09-12, docs/09). Windows API xatosida qoida fail-open: forvard yuboriladi, skan yo'qolmaydi. Serverdagi qorovul (E010) eski agentlarni ham qamraydi.

**Bog'lanishlar:** `backend/app/schemas/bridge_agents.py` (`BridgeAgentCreate`, `BridgeAgentRead`, `BridgeAgentUpdate`, `BridgeScanRequest`, `BridgeLogPush`, `BridgePairRequest`, `BridgePairResponse`, `AgentRelease`), `backend/app/models/bridge_agent.py` (`BridgeAgent`), migratsiya `backend/app/migrations/versions/d5e81a24c3b7_bridge_agent_pairing.py`, `backend/app/crud` (`crud_bridge_agents`, `log_action`), `backend/app/api/routes/ws.py` (`/ws/bridge` shu tokenni tanidi), `bridge-agent/agent.py`.

---

## `backend/app/api/routes/ws.py` — WebSocket endpointlari

**Maqsadi:** Ikki WebSocket kanal. Router darajasida auth YO'Q — WebSocket'da HTTP dependency ishlamaydi, autentifikatsiya har endpoint ichida.

| Endpoint | Auth | Izoh |
|---|---|---|
| WS `/api/v1/ws/events` | `Authorization: Bearer <token>` header yoki access cookie | Brauzer klientlari. Token HTTP oqimidagi bilan bir xil funksiya — `deps.resolve_user` — orqali tekshiriladi (`verify_token` + `is_active` + `token_version`); muvaffaqiyatsiz bo'lsa **4401** (`WS_CLOSE_UNAUTHORIZED` konstantasi) kod bilan yopiladi. Ochiq soketda har 300 s da qayta tekshiruv — `verify_exp=False` bilan: muddat emas, bekor qilinganlik (`token_version`/`is_active`). `?token=` query param ATAYLAB qabul qilinmaydi — token server access-loglariga tushib sizardi (`/ws/bridge` ham shu sababdan headerga o'tgan); frontend `useMesWs.ts` cookie'ga tayanadi. Klient scope'i rol bo'yicha: TERMINAL va operator rollar (POST_ROLES)→`terminal`, TABLO→`tablo`, qolganlar→`dashboard`; post/ish markazi scope `user.machine_id` dan, operator rollarda esa `machine_id` bo'lmasa post rolning o'zidan (`POST_ROLES` → `Post.code`) aniqlanadi — aks holda postga nishonlangan `scan.recorded` eventlari yetib bormasdi. Heartbeat: klientning har qanday xabariga `{"type": "pong"}`; o'sha heartbeat'da token har **300 s** da qayta tekshiriladi (`_RECHECK_SECONDS`) — logout/muddat tugashi ochiq soketni ham **4401** bilan yopadi, DB xatosi esa ulanishni uzmaydi (`/ws/bridge` dagi `touch_agent` uslubi) |
| WS `/api/v1/ws/bridge` | `Authorization: Bearer <token>` header (fallback: `?token=` query) → `bridge_agent.token_hash` (sha256) yoki legacy `settings.BRIDGE_TOKEN` (`secrets.compare_digest`) | Tsex tarmog'idagi bridge-agent uplink'i (USB GoDEX'da chop etadi). Ulanish CHIQUVCHI: agent o'zi ulanadi, tsex routerida port ochilmaydi. Token headerda keladi — server access-loglariga tushmasin; `?token=` eski agentlar uchun qoldirilgan. Avval legacy umumiy `BRIDGE_TOKEN` bilan solishtiriladi (bytes'da — non-ASCII tokenda `compare_digest(str)` TypeError beradi), mos kelmasa token sha256 xeshi bo'yicha `bridge_agent` jadvalidan qidiriladi; topilmasa 4401. `BRIDGE_TOKEN` default bo'sh, `bool(settings.BRIDGE_TOKEN)` guard esa shu holda legacy yo'lni butunlay o'chiradi — aks holda bo'sh token bo'sh sozlama bilan mos kelib, hamma ulana olardi. Ulanishda `X-Agent-Version` header `bridge_agent.version` ustuniga yoziladi; ulanish/uzilish `bridge.connected`/`bridge.disconnected` eventlari bilan panelga tarqatiladi (pairing esa `bridge.paired`). Chop etish ishlari faqat `can_print=True` agentga beriladi — `can_print=False` agent ulanib turadi (skan-forvard uchun), lekin print navbatidan ish olmaydi. Ulangandan keyin `touch_agent()` har 300 sekundda `last_seen_at` ni yangilaydi, `can_print`ni qayta o'qiydi va agent hali tirikligini qayta tekshiradi — agent o'chirilgan yoki yangi kod berilgan bo'lsa ulanish 4401 bilan yopiladi, qo'lda turgan ish esa navbatga QAYTARILADI. Bu 300 sekundlik `touch_agent` — ZAXIRA tekshiruv: revoke bayrog'i (`mes:agent:revoked:{id}`) HAR `brpop` iteratsiyasida o'qiladi, ya'ni bekor qilingan ulanish ~5 soniyada uziladi. DB xatosi ulanishni yiqitmaydi. Redis'dagi O'Z navbatidan (`mes:print:queue:{agent_id}`) `brpop` (5s timeout) bilan ishlarni oladi va agentga yuboradi (job JSON: `type`, `job_id`, `instance_id`, `png` — base64 PNG); umumiy `mes:print:queue` ATAYLAB o'qilmaydi — aynan u "ofisdagi test printeri tsexdagi chekni tortib oldi" nuqsonining mexanizmi edi, endi manzilsiz job umuman yaratilmaydi va kalit bo'sh turadi; tanitilmagan legacy tokenli agent (`agent_id is None`) ham hech qanday chek olmaydi — qaysi ish markazi ekani noma'lum; agent ishni lokal `print-queue.jsonl` ga yozgach 15s ichida `{"ok": true}` bilan ack qilishi shart — ack kelmasa yoki uzilsa ish `rpush` bilan navbatga QAYTARILADI (hech bir ish yo'qolmaydi); bo'sh navbatda `{"type": "ping"}` heartbeat va 10s ichida javob kutiladi |

Server → klient eventlarni `app/core/ws.py` dagi `ws_manager` tarqatadi — mutatsion HTTP endpointlar publish qiladi. Kodda uchraydigan oilalar: `order.*` (`created`, `started`, `cancelled`, `delivered` — orders.py; `stage_completed`, `completed` — skan yakunida `scanning.py` `outcome.events` orqali), `session.*` (`started`, `ended`), `scan.*` (`recorded`, `cancelled`, `rejected` — oxirgisini `bridge_agents.py` stanok skani rad etilganda postga nishonlab yuboradi), `label.*` (`printed`, `cancelled`), `pachka.*` (`item`, `closed`), `tmo.*` (`accepted`), `bridge.*` (`connected`, `disconnected`, `paired`).

**Bog'lanishlar:** `backend/app/core/ws.py` (`WsClient`, `ws_manager`), `backend/app/api/deps.py` (`resolve_user`), `backend/app/core/security.py` (`ACCESS_COOKIE_NAME`), `backend/app/models/bridge_agent.py` (`BridgeAgent.token_hash`, `last_seen_at`), `backend/app/api/routes/bridge_agents.py` (pairing — token shu yerda beriladi), `backend/app/tasks` (`PRINT_QUEUE_KEY = "mes:print:queue"`), `backend/app/core/config.py` (`BRIDGE_TOKEN` — legacy, `REDIS_URL`).

---

## Umumiy naqshlar (patterns)

- **Auth ikki kanalda:** `Authorization: Bearer` header (ustuvor) yoki `httpOnly` access cookie — `deps.get_current_user` ichidagi header→cookie tanlovi. `/ws/events` ham aynan shu ikki kanalni ishlatadi (`?token=` query QABUL QILINMAYDI — access-loglariga sizardi), xato — 4401.
- **Rol-guruh avtorizatsiyasi:** `require_roles` aliaslari (`ManagerUser`, `TexnologUser`, `ManagerOrTexnologUser`, `StaffReadUser`, `AdminUser`, terminal oqimida `TerminalUser`) — superuser va ADMIN har doim o'tadi; deyarli har MES endpoint shulardan birini ishlatadi.
- **Token bekor qilish:** `token_version` — DB'dagi qiymat token payload'idagi qiymat bilan mos kelmasa 401; logout esa versiyani OSHIRMAYDI — u faqat joriy qurilmani uzadi (refresh `jti` tombstone + cookie tozalash). Versiya faqat ikki holatda oshadi: parol almashtirilganda (`users.py`) va refresh token replay aniqlanganda (`login.py`).
- **Refresh rotatsiyasi:** har `POST /login/refresh` da access va refresh ikkalasi qayta beriladi; eski refresh token `jti`si Redis'da belgilanadi (one-time-use), replay aniqlansa `token_version` bump bilan butun sessiya bekor qilinadi.
- **Rate limiting:** `RateLimit` dependency — login (`LOGIN_RATE_LIMIT_*`) va beyjik endpointlarida. Dependency faqat TEKSHIRADI (Redis GET, fail-closed); hisobni chaqiruvchi `hit()` bilan FAQAT muvaffaqiyatsiz urinishda oshiradi.
- **Paginatsiya:** `skip`/`limit` query parametrlari, chegaralar `settings.DEFAULT_PAGE_SIZE` / `settings.MAX_PAGE_SIZE` dan; ro'yxat javoblari `app/schemas/common.py` dagi generik `Paginated[T]` (`{data, count}`) sxemasida, oddiy tasdiqlar `Message` da.
- **Fayl yuklash:** `UploadFile` qabul qiladigan endpointlar (`/orders/{id}/upload` — `.project`, `/orders/{id}/survey/photos` — xona rasmi) kengaytma/MIME va hajmni endpoint ichida tekshiradi, xato 422; fayl `settings.UPLOAD_DIR` ostiga yoziladi (absolyut root — `upload_root()`, `app/core/config.py`), bazada `OrderFile` qatori qoladi (yo'l — nisbiy).
- **Audit:** deyarli barcha mutatsion endpointlar o'z tranzaksiyasida `crud.log_action` chaqiradi — modul, amal, foydalanuvchi, entity, `meta`, IP (`deps.client_ip`) yoziladi; o'qish `GET /api/v1/audit-logs/` orqali. IP HAMMA joyda emas: 54 ta `log_action` chaqiruvidan 12 tasi `ip=` bermaydi va `audit_log.ip` NULL qoladi — `pachka`, `tmo`, `scan` (`scans.py` + `services/scanning.py`) hamda terminal `print` chaqiruvlari. Sabab: skan dvijoki servis qatlamida `Request` obyektisiz ishlaydi. Kodda ishlatiladigan 13 modul nomi: `auth`, `users`, `clients`, `employees`, `machines`, `posts`, `orders`, `pachka`, `tmo`, `bridge_agents`, `print`, `sessions`, `scan`. `auth` — admin paneliga kirish/chiqish (`login`, `login_failed`, `logout`; `login.py` + `logout.py`); u qo'shilgunga qadar parol bilan kirish va chiqish Loglar sahifasida umuman ko'rinmasdi. Eski nomlar `e5b83c04d7a1` da birlashtirilgan (`ombor`→`tmo`), `terminal.py` esa o'z nomidan emas — `print` va `sessions` modullariga yozadi.
- **Real-time eventlar:** mutatsion endpointlar `ws_manager.publish` orqali WS eventlar tarqatadi (`order.*`, `session.*`, `scan.*`, `label.*`, `pachka.*`, `tmo.*`, `bridge.*` — to'liq ro'yxat `ws.py` bo'limida) — terminallar, TABLO va dashboard jonli yangilanadi; terminal `pachka.item`/`pachka.closed` da ham ish so'rovlarini yangilaydi (2026-09-04, boshqa qadoqlash terminali uchun).
- **Xatoliklar:** `backend/app/core/exceptions.py` dagi maxsus exception'lar (`UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `DuplicateValueException` 409, `RateLimitException` 429) — xabarlar o'zbek tilida. "Topilmadi" holati odatda qo'lda yozilmaydi: `BaseCRUD.get_or_404(db, "Mijoz topilmadi.", id=...)` o'zi `NotFoundException` ko'taradi. Terminal/skan oqimida esa 422 `{code, message}` formati (E001–E009 kodlari — `docs/09-mes-domain.md` §3.0). `E007` ("Aloqa yo'q") server kodi emas — WS uzilganda terminal frontendi lokal hosil qiladi (`frontend/src/routes/terminal.tsx`), so'rov serverga umuman ketmaydi.
- **OpenAPI barqarorligi:** biznes endpointlarning barchasida aniq `operation_id` berilgan (frontend client generatsiyasi uchun qulay); istisno — `health.py` dagi `/health` va `/ready` probalari (FastAPI avtomatik nom beradi).
