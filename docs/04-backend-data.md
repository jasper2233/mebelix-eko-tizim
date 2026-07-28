# Backend Data Layer — Models, Schemas, CRUD, Migrations, Tasks

Bu hujjat MebeliX MES backend'ining ma'lumotlar qatlamini qamrab oladi: SQLAlchemy ORM modellari, Pydantic schemalari, generic CRUD qatlami, Alembic migratsiyalari, CLI komandalar va ARQ background tasklari. Qatlam to'liq **async** (SQLAlchemy `AsyncSession`, asyncpg driver) va aniq qatlamlararo yo'nalishga ega:

```
API routes  →  schemas (validation)  →  crud (biznes DB-operatsiyalar)  →  models (ORM)  →  PostgreSQL
```

Domen modeli to'liq MES sohasini qamrab oladi: **17 jadval** — `user` + 16 MES jadvali (`organization`, `client`, `employee`, `material`, `post`, `machine`, `audit_log`, `order`, `work_session`, `product`, `part`, `order_file`, `part_instance`, `part_route`, `scan`, `bridge_agent`). Shablondan qolgan demo `Item` moduli to'liq olib tashlangan.

---

## 1. Models — `backend/app/models/`

### 1.1 `backend/app/models/base.py` — Mixinlar va abstract BaseModel

Barcha ORM modellari uchun umumiy ustunlarni beruvchi mixinlar. Hammasi SQLAlchemy 2.0 `MappedAsDataclass` uslubida yozilgan (modellar Python dataclass sifatida ham ishlaydi, `init=False` / `kw_only=True` / `default_factory` shu mexanizm uchun).

| Klass | Beradigan ustunlar | Izoh |
|---|---|---|
| `IDMixin` | `id: int` | PK, autoincrement, `init=False` (constructor'da berilmaydi) |
| `TimestampMixin` | `created_at`, `updated_at` | `DateTime(timezone=True)`; Python tomonda `datetime.now(UTC)`, DB tomonda `current_timestamp(0)` server default; `updated_at` — `onupdate` orqali avtomatik yangilanadi |
| `SoftDeleteMixin` | `deleted_at`, `is_deleted` | Soft delete; `is_deleted` indekslangan |
| `BaseModel` | yuqoridagilarning hammasi | `__abstract__ = True`; `app.core.db.Base` + 3 mixin kombinatsiyasi |

```python
class BaseModel(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
```

**Bog'lanish:** `Base` deklarativ asosi `backend/app/core/db.py` dan keladi. `BaseCRUD` (`backend/app/crud/base.py`) aynan shu mixinlar mavjudligiga tayanadi (ayniqsa soft-delete ustunlariga).

### 1.2 `backend/app/models/enums.py` — Domen enumlari

`db_enum(enum_cls, length=30)` helper — **VARCHAR-backed** SQLAlchemy `Enum` (`native_enum=False`): yangi a'zo qo'shilganda PG native enum ALTER'i kerak emas (masalan, `UserRole` ga 6 operator roli migratsiyasiz qo'shilgan). Faylda **14 ta StrEnum**:

| Enum | A'zolar |
|---|---|
| `UserRole` | 12 ta: 6 xodim/qurilma (`admin`, `director`, `manager`, `texnolog`, `terminal`, `tablo`) + 6 operator (`arrachi`, `kromkachi`, `prisadkachi`, `pazchi`, `roverchi`, `stolyar`) |
| `PostCode` | `ARRA`, `KROMKA`, `PRISADKA`, `PAZ`, `ROVER`, `STOLYARKA` |
| `PostUnit` | `m2`, `meter`, `piece` |
| `MachineStatus` | `active`, `inactive`, `repair` |
| `CapacityUnit` | `m2_per_hour`, `meter_per_hour`, `units_per_hour` |
| `EmployeeStatus` | `active`, `inactive` |
| `ClientType` | `individual`, `legal` |
| `MaterialType` | `sheet`, `band`, `hardware` |
| `OrderStatus` | `draft`, `technical_review`, `production`, `completed`, `delivered`, `cancelled` |
| `OrderPriority` | `low`, `medium`, `high`, `urgent` |
| `ProjectGeneration` | `processed`, `template` |
| `RouteSource` | `auto`, `manual` |
| `FileKind` | `project`, `scx`, `label_pdf`, `document` |
| `SessionStatus` | `active`, `ended` |

`POST_ROLES: dict[UserRole, PostCode]` — 6 operator rolini o'z postiga bog'laydi (`ARRACHI→ARRA`, `KROMKACHI→KROMKA`, `PRISADKACHI→PRISADKA`, `PAZCHI→PAZ`, `ROVERCHI→ROVER`, `STOLYAR→STOLYARKA`). Operator rollari o'z akkaunti bilan kiradi va o'z postining terminalini ko'radi — stanok binding'i va badge talab qilinmaydi (`TERMINAL` qurilma akkauntlaridan farqli).

### 1.3 `backend/app/models/user.py` — User modeli

`user` jadvali. Login identifikatori sifatida **username yoki telefon** ishlatiladi; telefon O'zbekiston E.164 formatida kanonik saqlanadi (`+998` + 9 raqam = 13 belgi). `token_version` — barcha chiqarilgan JWT tokenlarni bir zarbda bekor qilish mexanizmi. Faqat ikki joyda inkrement qilinadi: logout (`backend/app/api/routes/logout.py`) va o'g'irlangan refresh token qayta ishlatilganda (`login.py`, one-time-use nazorati). **Parol almashtirish tirik sessiyalarni uzmaydi** — `PATCH /users/me/password` versiyani oshirmaydi. `backend/app/crud/users.py` dagi `increment_token_version` ga qarang.

MES uchun ikkita yangi ustun (TZ 3 / TZ 8.1):

- `role: UserRole` — `db_enum(UserRole)` (VARCHAR), NOT NULL, `server_default="admin"`. `admin`/`director`/`manager`/`texnolog` — odamlar; `terminal`/`tablo` — stanokka bog'langan qurilma akkauntlari; operator rollari — post terminaliga kiruvchi ishchilar.
- `machine_id: int | None` — FK `machine.id` (`fk_user_machine_id`); `TERMINAL`/`TABLO` qurilma akkauntini konkret stanokka bog'laydi.

Uniqueness ustun darajasida emas, `__table_args__` dagi **PARTIAL UNIQUE indexlar** orqali:

```python
__table_args__ = (
    Index("ix_user_username", "username", unique=True, postgresql_where=text("NOT is_deleted")),
    Index("ix_user_phone", "phone", unique=True, postgresql_where=text("NOT is_deleted")),
)
```

Ya'ni uniqueness faqat **tirik** (soft-o'chirilmagan) qatorlar orasida amal qiladi — soft-o'chirilgan userning telefon/username'i IntegrityError'siz qayta ro'yxatdan o'tkazilishi mumkin. Bu naqsh MES jadvallarida ham takrorlanadi (1.5-bo'lim).

**Jadval: `user`** (mixin ustunlari — `id`, `created_at`, `updated_at`, `deleted_at`, `is_deleted` — 1.1-bo'limdagidek, quyida takrorlanmaydi)

| Ustun | Tip | Null | Default | Index/Constraint |
|---|---|---|---|---|
| `name` | `String(30)` | NULL | — | — |
| `username` | `String(20)` | NOT NULL | — | PARTIAL UNIQUE `ix_user_username` (`WHERE NOT is_deleted`) |
| `phone` | `String(13)` | NOT NULL | — | PARTIAL UNIQUE `ix_user_phone` (E.164: `+998XXXXXXXXX`) |
| `hashed_password` | `String` | NOT NULL | — | — |
| `is_active` | `Boolean` | NOT NULL | `True` (Python) | — |
| `is_superuser` | `Boolean` | NOT NULL | `False` (Python) | — |
| `token_version` | `Integer` | NOT NULL | `0` (server_default) | JWT'larni ommaviy bekor qilish |
| `role` | `VARCHAR(30)` (`UserRole`) | NOT NULL | `'admin'` (server_default) | — |
| `machine_id` | `Integer` | NULL | — | FK `machine.id` (`fk_user_machine_id`) |

### 1.4 MES modellari

Barcha MES modellari `BaseModel` dan meros oladi (id + timestamp + soft-delete), enumlar `db_enum(...)` bilan VARCHAR sifatida saqlanadi. Ko'p jadvalda `organization_id` FK (`default=1`) — sxema multi-tenant'ga tayyor (TZ 4.1), hozircha bitta "Mebelix" tashkiloti.

**Registr modellari** (har biri o'z faylida):

| Model / jadval | Fayl | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|---|
| `Organization` | `organization.py` | `name(100)`, `logo_url`, `address`, `phones` **JSONB** (list), `currency` (`"UZS"`), `timezone` (`"Asia/Tashkent"`), `settings` **JSONB** | — |
| `Client` | `client.py` | `organization_id`, `full_name(150)`, `client_type` (`ClientType`, default `individual`), `phone`/`phone_alt(13)`, `address`, `inn(20)`, `notes` | — (`orders_count` saqlanmaydi — query'da hisoblanadi) |
| `Employee` | `employee.py` | `organization_id`, `full_name(100)`, `badge_id(36)` (badge QR — registrda `uuid4()`; operator rolidagi foydalanuvchi birinchi skanida `services/scanning.py: operator_employee` `user-{user_id}` badge bilan ko'zgu qatorni avtomatik yaratadi — `docs/09-mes-domain.md` §3), `phone`, `passport_id`, `position`, `status` (`EmployeeStatus`), `photo_url`, `assigned_post_ids` **JSONB** (int list — join-table o'rniga, maks. 6 post), `hired_date` | PARTIAL UNIQUE `ix_employee_badge_id`. Yo'qolgan badge: qator saqlanadi, `badge_id` almashtiriladi — scan tarixi buzilmaydi |
| `Material` | `material.py` | `organization_id`, `name(150)`, `code`, `type` (`MaterialType`), `thickness`/`width`/`length`, `default_supplier`, `price_per_unit Numeric(14,2)`, `color`, `glossiness` | PARTIAL UNIQUE `ix_material_name_type` (`name`, `type`). `.project` fayllardan avtomatik to'ldiriladi |
| `Post` | `post.py` | `organization_id`, `code` (`PostCode`), `name(50)`, `order_index`, `unit` (`PostUnit`), `requires_qr_print`, `auto_skip_if_empty` (default `True`), `requires_assignment_choice`, `icon`, `color` | PARTIAL UNIQUE `ix_post_code`. 6 bosqichli ishlab chiqarish zanjiri (TZ 4.4) |
| `Machine` | `machine.py` | `organization_id`, `post_id` FK (index), `name(100)`, `ip_address(45)`, `mac_address(17)`, `capacity` + `capacity_unit` (`CapacityUnit`), `status` (`MachineStatus`), `icon_url`, `serial_number`, `installed_date` | IP — terminal/TABLO kontekstini aniqlash uchun (TZ 4.3) |
| `AuditLog` | `audit.py` | `user_id` FK NULL (index), `employee_id` FK NULL, `module(50)`, `action(50)`, `entity_type`, `entity_id`, `message`, `meta` **JSONB**, `ip(45)` | `created_at` = hodisa vaqti (TZ 10.11) |
| `BridgeAgent` | `bridge_agent.py` | `organization_id`, `name(100)` (qaysi kompyuter/post — admin panelda ko'rinadi), `token_hash(64)` (doimiy tokenning sha256'si; NULL = hali ulanmagan), `pair_code(16)` (8 belgili bir martalik kod), `pair_expires_at` (kod TTL — 15 daqiqa), `last_seen_at` | UNIQUE `ix_bridge_agent_token_hash`; `ix_bridge_agent_pair_code`. Har printerli kompyuterga bitta qator; bekor qilish — soft delete (1.4.2-bo'lim) |

**Buyurtma modellari** (`order.py` — 6 klass):

| Model / jadval | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|
| `Order` | `number(20)` (`B-2026-001`, avto), `client_id` FK (index), `status` (`OrderStatus`, default `draft`, index), `priority` (`OrderPriority`), `deadline`, `amount Numeric(14,2)`, `advance_payment Numeric(14,2)` (boshlang'ich to'lov — manager buyurtma ochishda kiritadi), `notes`, `created_by_id` FK user; `.project` metadata: `project_uuid/name/generation/loaded_at`; **JSONB**: `cutmap` (kesish xaritasi vizual modeli, TZ 5.7.5), `material_usage` (default `[]` — `[{name, kind, count, unit}]`, TZ 11.3), `machine_assignments` (default `{}` — `{"PAZ": 3, "ROVER": 5}`, TZ 6.4.1), `survey` (mijoz anketasi + o'lchov varag'i, NULL — sxema `schemas/orders.OrderSurvey`, 2.4.1-bo'lim); lifecycle: `production_started_at`, `completed_at`, `delivered_at`, `cancelled_at`, `cancel_reason`, `cancelled_by_id` | PARTIAL UNIQUE `ix_order_number` |
| `Product` | `order_id` FK (index), `code(50)`, `name(255)`, `count`, `import_source` | `<good typeId="product">` (TZ 5.2.2) |
| `Part` | `order_id`/`product_id` FK (index), `code(50)` (masalan `01_002`), `name`, `count`, o'lchamlar `length/width/thickness` + `saw_length/saw_width` (jl/jw), `txt` (tekstura qulfi), `material_name(150)`, `label_num`; **JSONB**: `edges` (tomon bo'yicha kromka: `{"l": {"mat": ..., "symbol": "A"}, ...}`), `xnc_summary` (`{"bores", "edge_bores", "grooves", "mills", "sides"}`); `note` (texnolog izohi) | Barqaror kalit: `productCode_partCode` (TZ 5.8) |
| `PartInstance` | `order_id`/`part_id` FK (index), `instance_no` (1..count), `qr_text(120)`, `pattern_no`/`cell_index` (kesish xaritasi katagi, TZ 7.1.4), `label_printed_at` | **PARTIAL UNIQUE `ix_part_instance_order_qr` (`order_id`, `qr_text`) `WHERE NOT is_deleted`** — QR = `productCode_partCode_n` |
| `PartRoute` | `order_id`/`part_id`/`post_id` FK, `machine_id` FK NULL, `source` (`RouteSource`), `is_enabled` (texnolog o'chira oladi), `per_instance` (post'dagi skan soni: KROMKA — tomonlar, PRISADKA `_2` — 2), `total_required` = count × per_instance, `total_done` | PARTIAL UNIQUE `ix_part_route_part_post` (`part_id`, `post_id`); `ix_part_route_order_post`. Denormalizatsiyalangan hisoblagichlar — tez QOLDIQ (TZ 5.4) |
| `OrderFile` | `order_id` FK (index), `part_id` FK NULL, `kind` (`FileKind`), `path(500)`, `filename(255)`, `size`, `meta` **JSONB** (default `{}`) | Yuklangan `.project`, part-boshiga `.scx`, label PDF, hujjatlar. Anketa xona rasmlari ham shu yerda: `kind=DOCUMENT` + `meta={"room_id": ..., "content_type": ...}` — alohida jadval/migratsiyasiz (1.4.1-bo'lim) |

#### 1.4.1 Anketa xona rasmlari — `OrderFile.meta` orqali

Xona surati uchun yangi jadval qo'shilmagan: `OrderFile` qatori `kind=FileKind.DOCUMENT` va `meta` JSONB'ida `room_id` (`SurveyRoom.id` ga bog'lanish) + `content_type` bilan saqlanadi. Shu sababli:

- Rasm xonaning ro'yxatdagi **o'rniga** emas, barqaror `SurveyRoom.id` ga bog'langan — xonalar qayta tartiblansa ham bog'lanish buzilmaydi.
- Filtr JSONB operatorlari bilan: `OrderFile.meta["room_id"].astext == room_id`, yetimlarni topishda `OrderFile.meta.has_key("room_id")`.
- Disk yo'li: `{UPLOAD_DIR}/survey/{order_id}/{uuid4().hex}{.jpg|.png|.webp}`.
- Chegaralar route qatlamida (`backend/app/api/routes/orders.py`): `_ROOM_PHOTO_TYPES` = jpeg/png/webp, `MAX_ROOM_PHOTO_SIZE` = 5 MB, `MAX_ROOM_PHOTOS` = 6 (bitta xonaga).
- `PUT /orders/{id}/survey` (`save_order_survey`) saqlashda anketada endi mavjud bo'lmagan `room_id` li rasmlarni topib, diskdan `unlink` qiladi va qatorni soft-delete qiladi (yetim rasm tozalash). `DELETE /orders/{id}/survey/photos/{file_id}` ham diskdagi faylni o'chiradi — anketa rasmlari tarix uchun saqlanmaydi.
- `GET /orders/{id}/files/{file_id}` (`download_order_file`) `kind` `PROJECT`/`SCX` bo'lsa `application/xml`, aks holda `meta["content_type"]` (bo'lmasa `application/octet-stream`) ni `media_type` qilib beradi — brauzer rasmni `<img>` da yuklab olmasdan ko'rsatadi.

**Skan modellari** (`scan.py` — 2 klass):

| Model / jadval | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|
| `WorkSession` | `employee_id` FK (index), `user_id` FK NULL (sessiyani ochgan akkaunt — TERMINAL qurilmasi yoki operator), `machine_id` FK NULL, `post_id` FK, `status` (`SessionStatus`, index), `ended_at` | TERMINAL qurilma akkauntida smena badge skani bilan ochiladi (TZ 8.2); operator rolida (`POST_ROLES`) login-ning o'zi smena — `services/scanning.py: active_session` sessiyani avtomatik ochadi/egallaydi va `user_id` ga operator user'ini yozadi. `SESSION_MAX_HOURS` (12 soat) dan oshgan smena avtomatik ENDED bo'ladi. `created_at` = boshlanish vaqti |
| `Scan` | `order_id`/`part_id`/`instance_id`/`route_id`/`post_id` FK, `machine_id` FK NULL, `employee_id` FK (index), `session_id` FK (index), `client_event_id(64)`, `is_cancelled`, `cancelled_at` | UNIQUE `ix_scan_client_event_id` (idempotentlik — network replay rad etiladi, TZ 8.4.4); `ix_scan_order_post`; PARTIAL `ix_scan_instance_post` (`WHERE NOT is_cancelled`). Bekor qilingan skan auditda qoladi, hisoblagich qayta oshiriladi |

#### 1.4.2 `bridge_agent` — har printerga o'z tokeni (pairing)

Ilgari barcha printerlar server `.env` idagi **bitta** `BRIDGE_TOKEN` bilan ishlar edi: yangi printer qo'shish uchun serverga SSH kirish kerak bo'lar, bitta token sizib chiqsa esa hamma printer ochilib qolar edi. Endi har printerli kompyuter uchun `bridge_agent` da alohida qator (`BaseModel` ustunlari — id/timestamp/soft-delete — odatdagidek):

- Admin panel yangi agent yaratadi → **8 belgili bir martalik kod** (`pair_code` + `pair_expires_at` = 15 daqiqa). Alfavitda `I/L/O/0/1` yo'q — kodni telefonda aytganda adashtirmaydi (`backend/app/api/routes/bridge_agents.py`).
- Agent kodni `POST /api/v1/bridge-agents/pair` orqali doimiy tokenga almashtiradi. Almashtirish **atomik `UPDATE ... RETURNING`** (`pair_code` mos + muddati o'tmagan) — bitta kodni ikki kompyuter yuborsa faqat bittasi yutadi, kod darhol `NULL` ga tushadi.
- Bazada faqat `token_hash` (sha256, UNIQUE) saqlanadi; tokenning o'zi bir marta — pair javobida — beriladi va agent uni `%APPDATA%\MebelixAgent\.env` ga yozadi.
- `last_seen_at` ni `/ws/bridge` har 5 daqiqada yangilaydi (DB'ga ortiqcha yuk bo'lmasin) — panel shundan **Onlayn/Oflayn** ni ko'rsatadi.
- Bekor qilish — soft delete (`BaseCRUD.delete`): keyingi ulanish 4401 bilan rad etiladi, jonli ulanish esa navbatdagi tekshiruvda (maks. ~5 daqiqa) uziladi va qo'lda turgan job navbatga qaytadi. Yangi kod berish (`POST /bridge-agents/{id}/code`) `token_hash` ni ham tozalaydi — eski kompyuter shu zahoti kesiladi. Bittasini bekor qilish qolgan printerlarga tegmaydi.

### 1.5 `backend/app/models/__init__.py`

17 model klassini re-export qiladi (`__all__`): `AuditLog`, `BridgeAgent`, `Client`, `Employee`, `Machine`, `Material`, `Order`, `OrderFile`, `Organization`, `Part`, `PartInstance`, `PartRoute`, `Post`, `Product`, `Scan`, `User`, `WorkSession`. Alembic `env.py` esa modellarni bu faylga tayanmasdan `pkgutil.walk_packages` bilan dinamik import qiladi.

---

## 2. Schemas — `backend/app/schemas/`

Pydantic v2 schemalari — API request/response validatsiyasi. `backend/app/schemas/__init__.py` bo'sh (re-export yo'q, importlar to'g'ridan-to'g'ri moduldan qilinadi). Umumiy naqshlar: read-schemalar `from_attributes=True`, create/update-schemalar `extra="ignore"`, update'larda hamma maydon optional (partial PATCH).

### 2.1 `backend/app/schemas/users.py` — User schemalari

Umumiy validatsiya elementlari:

- `PHONE_PATTERN = r"^\+998\d{9}$"` — O'zbekiston E.164 telefon regex'i (model'dagi `String(13)` bilan mos); clients/employees schemalari ham shu konstantani import qiladi.
- `validate_password_strength(v)` — parol kuchi: 8+ belgi, kichik harf, katta harf, raqam, maxsus belgi. Xato bo'lsa `ValueError`.
- Qayta ishlatiladigan `Field` konstantalar: `_NAME_FIELD` (2–30), `_USERNAME_FIELD` (2–20, `^[a-z0-9]+$`), `_PHONE_FIELD`, `_OPTIONAL_PHONE_FIELD`.

| Schema | Vazifasi | Muhim jihatlar |
|---|---|---|
| `UserRead` | Barcha read javoblar | `from_attributes=True`; `id` — `BeforeValidator(str)` bilan **string** ga aylantiriladi; `role: UserRole` va `machine_id` qaytariladi; `hashed_password` chiqarilmaydi |
| `UserCreate` | `POST /users` (faqat superuser) | `password` strength-validatsiya; `is_superuser`/`is_active` flaglar; `role` (default `UserRole.MANAGER`) va `machine_id` (TERMINAL/TABLO rollari uchun amalda majburiy) |
| `UserUpdate` | `PATCH /users/me` (self-update) | Faqat `name`/`username`/`phone`; privilegiya flaglari va parol yo'q |
| `UserAdminUpdate` | `PATCH /users/{user_id}` (superuser) | `UserUpdate` + `password`, `is_active`, `is_superuser`, `role`, `machine_id` (hammasi optional) |
| `UpdatePassword` | `PATCH /users/me/password` | `current_password` + `new_password` (strength check) |

### 2.2 `backend/app/schemas/auth.py`

- `Token` — `access_token`, `token_type` (login javobi).
- `TokenData` — JWT payload'dan dekodlangan ma'lumot:
  - `user_id: int` — subject **immutable PK** (username/phone emas: ular o'zgarishi mumkin, bu tirik sessiyalarni uzib qo'yar va qayta ro'yxatdan o'tishda account confusion'ga yo'l ochar edi);
  - `token_version: int = 0` — User modeli bilan solishtiriladi;
  - `jti: str | None = None` — refresh tokenning unikal id'si (one-time-use enforcement uchun); access tokenlarda `None`.

### 2.3 MES registr schemalari

Har bir registr moduli standart uchlik (`*Read` / `*Create` / `*Update`) beradi:

| Fayl | Schemalar | Muhim jihatlar |
|---|---|---|
| `clients.py` | `ClientRead`, `ClientCreate`, `ClientUpdate` | `full_name` 2–150; telefonlar `PHONE_PATTERN`; `ClientRead.orders_count` — route'da hisoblanadi (default 0) |
| `employees.py` | `EmployeeRead`, `EmployeeCreate`, `EmployeeUpdate` | `badge_id` **faqat server tomonda** generatsiya qilinadi (UUID) — `EmployeeCreate` da yo'q; `assigned_post_ids: list[int]` |
| `machines.py` | `MachineRead`, `MachineCreate`, `MachineUpdate` | `post_id` majburiy; `capacity` `gt=0`; `capacity_unit`/`status` enumlar |
| `materials.py` | `MaterialRead`, `MaterialCreate`, `MaterialUpdate` | `type: MaterialType` faqat create'da (update'da o'zgartirilmaydi); o'lchamlar `gt=0`, `price_per_unit ge=0` |
| `posts.py` | `PostRead`, `PostUpdate` | Create yo'q — 6 postlik zanjir qat'iy (TZ 4.4), faqat prezentatsion/xulq maydonlari tahrirlanadi (`name`, `order_index`, `auto_skip_if_empty`, `requires_assignment_choice`, `icon`, `color`) |

### 2.4 `backend/app/schemas/orders.py` — Buyurtma schemalari

| Schema | Vazifasi |
|---|---|
| `OrderRead` | Registr qatori (TZ 10.3.1): `number`, `status`, `priority`, `client_id` + route'da join qilinadigan `client_name`, `deadline`, `amount`, `advance_payment`, `notes`, project metadata, barcha lifecycle timestamplar |
| `OrderFileRead` | Fayl qatori: `id`, `kind`, `filename`, `size`, `part_id`, `meta: dict[str, Any]` (default `{}` — anketa rasmida `{"room_id", "content_type"}`), `created_at` |
| `OrderDetail` | `OrderRead` + `machine_assignments`, `project_uuid`/`project_loaded_at`, `survey: dict \| None` (xom JSONB — texnolog o'qiydi), `files: list[OrderFileRead]`, `parts_count`, `instances_count` (buyurtma kartasi, TZ 10.3.3) |
| `OrderCreate` | Manager DRAFT ochadi (TZ 6.2): `client_id`, `deadline`, `priority`, `amount`/`advance_payment` (`ge=0`), `notes`; `number` avto (`B-2026-001`) |
| `OrderUpdate` | Hammasi optional (shu jumladan `advance_payment`) |
| `OrderCancel` | `reason` (3–500 belgi, majburiy) |
| `MachineAssignments` | `assignments: dict[PostCode, int]` — ishlab chiqarishdan oldin post-boshiga stanok tanlovi (TZ 6.4) |
| `RouteCell` | Matritsa katagi (part × post): `post_id`, `source`, `is_enabled`, `per_instance`, `total_required`, `total_done`, `machine_id` |
| `MatrixPart` | Matritsa qatori: part o'lchamlari + `edges`/`xnc_summary` + `routes: list[RouteCell]` |
| `OrderMatrix` | `order_id` + `parts: list[MatrixPart]` |
| `MatrixPartEdit` | Texnolog bitta part qatorini tahrirlaydi (TZ 6.3.3): `note`, `count` (1–1000), `stages: dict[int, bool]` (post_id → yoqilgan) |
| `MatrixEdit` | `edits: list[MatrixPartEdit]` — batch wrapper |
| `OrderSurvey`, `SurveyRoom`, `SurveyWall`, `SurveyModule` | Mijoz anketasi + o'lchov varag'i — 2.4.1-bo'lim |

#### 2.4.1 Anketa schemalari — `Order.survey` JSONB sxemasi

Qog'oz formaning o'rnini bosadi: menejer to'ldiradi, texnolog o'qib dizayn yasaydi. `PUT /orders/{id}/survey` butun anketani **bir butun sifatida** yozadi (partial patch yo'q) — `order.survey = body.model_dump(mode="json")`. O'qishda `OrderDetail.survey` xom dict qaytaradi (qayta validatsiya qilinmaydi — eski versiyadagi qatorlar javobni yiqitmasin).

Mijoz ismi/telefoni `Client` da, narx/avans/muddat `Order` da — anketada takrorlanmaydi.

**`OrderSurvey`** (`extra="ignore"`):

| Maydon | Tip | Chegara |
|---|---|---|
| `version` | `int` | default `1` — sxema evolyutsiyasi uchun |
| `measured_at` | `date \| None` | o'lchov sanasi |
| `measured_by` | `str` | ≤120 — o'lchagan usta |
| `rooms` | `list[SurveyRoom]` | ≤10 |

**`SurveyRoom`** — har xona alohida to'ldiriladi (`extra="ignore"`). `id` — frontend beradigan barqaror kalit (≤40), xona rasmlari shu `id` ga bog'lanadi (1.4.1-bo'lim).

| Bo'lim | Maydonlar |
|---|---|
| Kimlik | `id` (≤40, majburiy), `name` (≤60 — "Oshxona", "Yotoqxona 1") |
| 2. Mebel turi | `furniture_types: list[str]` (≤20), `furniture_other` (≤120) |
| 3. Shakl/o'lcham | `shape` (≤20), `room_length`, `room_width`, `room_height`, `furniture_wall_length` |
| 4. Korpus | `corpus_materials: list[str]` (≤10), `corpus_color` (≤120), `corpus_thickness` (≤20), `corpus_note` (≤300) |
| 5. Fasad | `facade_materials: list[str]` (≤10), `facade_color` (≤120), `countertop` (≤20), `facade_note` (≤300) |
| 6-7. Furnitura/xizmat | `hardware_level` (≤20), `extra_services: list[str]` (≤10) |
| 8. Izoh | `note` (≤1000) |
| O'lchov varag'i | `walls: list[SurveyWall]` (≤8), `modules: list[SurveyModule]` (≤40), `total_running_meters` (0–1000 pm), `total_height` |

**`SurveyWall`** (A bo'limi): `letter` (≤2 — A..E), `length`, `height`.
**`SurveyModule`** (B bo'limi, yasaladigan modul qatori): `name` (≤120), `wall` (≤2), `width` (eni), `depth` (chuqurlik), `height` (balandlik), `count` (1–999), `note` (≤200).

Barcha mm-o'lchamlar umumiy alias orqali: `_Mm = Annotated[float | None, Field(default=None, ge=0, le=50_000)]` — anketa tashqi kirish, chegarasiz bitta so'rov JSONB'ni to'ldirib yuborardi. Ro'yxat maydonlarida `Field(max_length=...)` element sonini cheklaydi.

**Variant kodlari** (`ldsp`, `mdf`, `akril`, `led`, `montaj`, `burchak`, ...) bazaga **kod** sifatida yoziladi; matnga aylantirish faqat `frontend/src/lib/anketa.ts` katalogida (`FURNITURE_TYPES`, `LAYOUT_SHAPES`, `CORPUS_MATERIALS`, `CORPUS_THICKNESS`, `FACADE_MATERIALS`, `COUNTERTOPS`, `HARDWARE_LEVELS`, `EXTRA_SERVICES`, `WALL_LETTERS` + `labelOf`/`labelsOf`). Backend ro'yxatni qat'iy tekshirmaydi — yangi variant qo'shilganda migratsiya ham, backend o'zgarishi ham kerak emas, eski qatorlarda saqlangan kod ham buzilmaydi.

### 2.5 `backend/app/schemas/terminal.py` — Terminal/skan schemalari

| Schema | Vazifasi |
|---|---|
| `BadgeStart` | `badge_id` (8–36 belgi) — badge skani bilan smena ochish |
| `SessionRead` | Sessiya: `employee_id` + join qilinadigan `employee_name`, `machine_id`, `post_id`, `status`, `ended_at` |
| `TerminalContext` | Terminal konteksti: stanok + post ma'lumotlari + aktiv `session` |
| `TaskRow` | NAVBATDAGI VAZIFALAR qatori (TZ 8.3.2): part o'lchamlari, `qoldiq` (shu postdagi qolgan skanlar), `total`, `edges` |
| `ScanRequest` | `qr_text` + `client_event_id` (klient UUID — idempotentlik, TZ 8.4.4) |
| `ScanResult` | `scan_id`, `duplicate` (replay — xato emas), part ma'lumotlari, yangi `qoldiq`, `scx_file_ids` (CNC postlar uchun har skanda, TZ 12.5), `order_stage_completed`/`order_completed` flaglar |
| `ScanHistoryItem` | Skan tarixi qatori (`is_cancelled` bilan) |
| `CutmapInstanceState`, `CutmapState` | ARRA kesish xaritasi ekrani (TZ 7.1.7): vizual `model` (JSONB) + har nusxaning jonli holati (`pattern_no`/`cell_index`/`done`/`label_printed_at`) |

### 2.6 Kichik schemalar

| Fayl | Schema | Vazifasi |
|---|---|---|
| `backend/app/schemas/common.py` | `Message` | Generic `{"message": str}` javob |
| | `Paginated[T]` | Standart sahifalangan ro'yxat javobi: `{data: list[T], count: int}` — barcha list endpointlarda ishlatiladi |
| `backend/app/schemas/health.py` | `HealthCheck`, `ReadyCheck` | Liveness/readiness endpointlari; `ReadyCheck` `database` va `redis` holatini ham qaytaradi |
| `backend/app/schemas/bridge_agents.py` | `BridgeAgentRead`, `BridgeAgentCreate`, `BridgePairRequest`, `BridgePairResponse` | Printer agentlari (1.4.2-bo'lim): `BridgeAgentRead` `token_hash` o'rniga `paired: bool` beradi, `pair_code` faqat muddati o'tmagan bo'lsa; `BridgePairResponse.token` — tokenning yagona ko'rinishi |

---

## 3. CRUD — `backend/app/crud/`

### 3.1 `backend/app/crud/base.py` — Generic `BaseCRUD[ModelType]`

Barcha model-CRUD klasslarning asosi. `ModelType` `app.models.base.BaseModel` bilan chegaralangan — soft-delete/timestamp ustunlarining mavjudligini kafolatlaydi.

```python
class BaseCRUD(Generic[ModelType]):
    exclude_deleted: bool = True
    def __init__(self, model: type[ModelType]): ...
```

Asosiy metodlar (hammasi async, `AsyncSession` qabul qiladi):

| Metod | Signatura (qisqartirilgan) | Vazifasi |
|---|---|---|
| `_build_query` | `(**kwargs) -> Select` | `**kwargs` — equality filterlar; `exclude_deleted=True` bo'lsa va caller `is_deleted` bermagan bo'lsa avtomatik `is_deleted == False` qo'shadi |
| `get` | `(db, **kwargs) -> ModelType \| None` | Istalgan field bo'yicha bitta yozuv (`scalar_one_or_none`) |
| `get_or_404` | `(db, detail, **kwargs) -> ModelType` | `get` kabi, topilmasa (yoki soft-delete bo'lsa) `NotFoundException(detail)` (`app.core.exceptions`) — routelardagi qo'lda yozilgan get-or-404 bloklari o'rniga |
| `get_multi` | `(db, offset=0, limit=100, **kwargs) -> (list, int)` | Sahifa + jami count (count subquery orqali, paginatsiyasiz); sahifa `ORDER BY id` bilan — barqaror tartib bo'lmasa Postgres sahifalarda qatorlarni takrorlashi/tushirib qoldirishi mumkin |
| `exists` | `(db, **kwargs) -> bool` | Yozuv borligini tekshirish (count > 0) |
| `delete` | `(db, **kwargs) -> bool` | **Soft delete**: `is_deleted=True`, `deleted_at=now(UTC)`; topilmasa `False` |

Muhim xulq: qidiruvlar default holda o'chirilgan yozuvlarni **ko'rmaydi**; o'chirilganlarni ham olish uchun `is_deleted=True/False` ni explicit berish yoki `exclude_deleted` ni override qilish kerak.

### 3.2 `backend/app/crud/users.py` — `CRUDUser`

`BaseCRUD[User]` + autentifikatsiya logikasi. Modul oxirida singleton: `crud_users = CRUDUser(User)`.

| Metod | Vazifasi |
|---|---|
| `get_by_login(db, identifier)` | Identifier `+` bilan boshlansa `phone`, aks holda `username` bo'yicha qidiradi |
| `create(db, user_create)` | Parolni `await get_password_hash(...)` (`backend/app/core/security.py`) bilan xeshlab yaratadi; caller pre-check qilsa ham, race'da yuzaga keladigan `IntegrityError` tutilib `DuplicateValueException` (409) qaytariladi |
| `update(db, db_user, user_update)` | `UserUpdate` yoki `dict`; `exclude_unset=True` (partial); `password` kelsa avtomatik `hashed_password` ga xeshlanadi (`await`); `IntegrityError` → `DuplicateValueException` (409) |
| `authenticate(db, username_or_phone, password)` | `get_by_login` + `verify_password`; user **topilmasa ham** modul-darajali `_DUMMY_HASH` ustida `verify_password` bajariladi — javob vaqti user mavjudligini oshkor qilmaydi (timing attack himoyasi); muvaffaqiyatsiz urinish `logger.warning` bilan loglanadi; xatoda `None` |
| `increment_token_version(db, user)` | `token_version += 1` — foydalanuvchining barcha access/refresh tokenlarini bekor qiladi |

### 3.3 `backend/app/crud/orders.py` — `CRUDOrder`

`BaseCRUD[Order]` + bitta maxsus metod:

- `next_number(db) -> str` — joriy yil ichida ketma-ket buyurtma raqami (TZ 6.2.2): `B-{yil}-` prefiksli maksimal `Order.number` topiladi, suffiks +1, `B-2026-001` formatida (`{seq:03d}`) qaytariladi.

Singleton: `crud_orders = CRUDOrder(Order)`.

### 3.4 `backend/app/crud/audit.py` — `log_action`

Singleton emas — oddiy funksiya (sync, `db.add` qiladi, `await` yo'q):

```python
def log_action(db, *, module, action, user_id=None, employee_id=None,
               entity_type=None, entity_id=None, message=None, meta=None, ip=None) -> AuditLog
```

`AuditLog` qatorini **caller tranzaksiyasida** stage qiladi — asosiy o'zgarish bilan birga commit bo'ladi (yoki birga rollback). Routelar `from app.crud import log_action` deb ishlatadi.

### 3.5 `backend/app/crud/__init__.py` — yupqa registrlar + re-export

Paketda `__init__.py` dan tashqari **4 modul** bor: `base.py`, `orders.py`, `users.py`, `audit.py`. O'z metodi yo'q oltita registr uchun alohida fayl ham, bo'sh subclass ham yo'q — `BaseCRUD` to'g'ridan-to'g'ri shu yerda instansiyalanadi:

```python
crud_bridge_agents: BaseCRUD[BridgeAgent] = BaseCRUD(BridgeAgent)
crud_clients: BaseCRUD[Client] = BaseCRUD(Client)
crud_employees: BaseCRUD[Employee] = BaseCRUD(Employee)
crud_machines: BaseCRUD[Machine] = BaseCRUD(Machine)
crud_materials: BaseCRUD[Material] = BaseCRUD(Material)
crud_posts: BaseCRUD[Post] = BaseCRUD(Post)
```

Modelga maxsus metod kerak bo'lsa — `orders.py`/`users.py` kabi alohida subclass qilinadi. Registrlarning maxsus logikasi route qatlamida (masalan, employee badge regeneratsiyasi, client orders_count join'i, agent pairing'ining atomik `UPDATE` i).

Re-export (`__all__`): **8 singleton** — `crud_bridge_agents`, `crud_clients`, `crud_employees`, `crud_machines`, `crud_materials`, `crud_orders`, `crud_posts`, `crud_users` — hamda `log_action`.

---

## 4. Migrations — Alembic

### 4.1 `backend/alembic.ini`

Standart Alembic konfiguratsiya: `script_location = app/migrations`, `prepend_sys_path = .` (shuning uchun `backend/` katalogidan turib `alembic` ishga tushiriladi). `sqlalchemy.url` bu yerda placeholder (`driver://user:pass@localhost/dbname`) — real URL runtime'da `env.py` tomonidan **override** qilinadi. Logging bo'limi: root/alembic/sqlalchemy loggerlar, console handler.

### 4.2 `backend/app/migrations/env.py`

Async migration environment:

- DB URL `app.core.config.settings` dan dinamik quriladi: `POSTGRES_ASYNC_PREFIX + USER:PASSWORD@SERVER:PORT/DB` — `.env` bilan sinxron, alembic.ini'ga parol yozilmaydi.
- `import_models("app.models")` — `pkgutil.walk_packages` bilan `app.models` ichidagi **barcha** modullarni avtomatik import qiladi; yangi model fayli qo'shilsa autogenerate uni `__init__.py` ga qo'lda yozmasdan ham ko'radi.
- `target_metadata = Base.metadata` (`backend/app/core/db.py`).
- Online rejim: `async_engine_from_config` (`NullPool`) → `connection.run_sync(do_run_migrations)` → `asyncio.run(...)`. Offline rejim: `literal_binds` bilan SQL chiqaradi.

### 4.3 `backend/app/migrations/script.py.mako`

Yangi revision fayllari uchun standart shablon (`upgrade()` / `downgrade()` skeleti, `revision`/`down_revision` identifikatorlari).

### 4.4 Versiyalar zanjiri — `backend/app/migrations/versions/`

7 ta migratsiya, head: `d5e81a24c3b7`.

| # | Revision | Fayl | Nima qiladi |
|---|---|---|---|
| 1 | `e1c262d7e2ae` | `e1c262d7e2ae_init.py` | **Init**: `user` va (o'sha paytdagi demo) `item` jadvallari, to'liq unique indekslar |
| 2 | `b7f3a9c41d02` | `b7f3a9c41d02_drop_items_partial_unique_user.py` | `item` jadvalini drop qiladi; `ix_user_username`/`ix_user_phone` ni **partial unique** ga almashtiradi (`WHERE NOT is_deleted`) |
| 3 | `1393a241b793` | `1393a241b793_mes_domain_org_posts_machines_employees_.py` | **MES domeni**: 15 jadval yaratadi (`organization`, `client`, `employee`, `material`, `post`, `machine`, `audit_log`, `order`, `work_session`, `product`, `part`, `order_file`, `part_instance`, `part_route`, `scan`) + `user` ga `role` (server_default `'admin'`) va `machine_id` (FK `fk_user_machine_id`) qo'shadi |
| 4 | `3b4e0b90f440` | `3b4e0b90f440_order_material_usage.py` | `order.material_usage` JSONB NOT NULL (server_default `'[]'`) |
| 5 | `7d2c9f5e1b3a` | `7d2c9f5e1b3a_order_advance_payment.py` | `order.advance_payment Numeric(14,2)` NULL — to'lov oqimi maydoni |
| 6 | `a91c7d34f6e2` | `a91c7d34f6e2_order_survey.py` | `order.survey JSONB` NULL — mijoz anketasi va o'lchov varag'i (xonalar bo'yicha) |
| 7 | `d5e81a24c3b7` | `d5e81a24c3b7_bridge_agent_pairing.py` | **`bridge_agent`** jadvali (printer agentlari: ulanish kodi + token xeshi) + 3 indeks: UNIQUE `ix_bridge_agent_token_hash`, `ix_bridge_agent_pair_code`, `ix_bridge_agent_is_deleted` (1.4.2-bo'lim) |

Anketa **xona rasmlari** uchun migratsiya yo'q: mavjud `order_file` jadvali `kind=DOCUMENT` + `meta` JSONB bilan ishlatiladi (1.4.1-bo'lim).

Eslatma: `1393a241b793` dagi `user.role` enum'i 6 qiymat bilan yaratilgan; keyinchalik 6 operator roli faqat Python enum'ga qo'shildi — ustun VARCHAR bo'lgani uchun (`db_enum`, `native_enum=False`) DB migratsiyasi kerak bo'lmadi.

---

## 5. Commands — `backend/app/commands/`

### 5.1 `backend/app/commands/create_first_superuser.py`

Idempotent bootstrap skript — birinchi admin foydalanuvchini yaratadi (`python -m app.commands.create_first_superuser` yoki deploy scriptidan chaqiriladi):

- Ma'lumotlar `settings` dan: `ADMIN_NAME`, `ADMIN_PHONE`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (`backend/app/core/config.py`).
- `phone` bo'yicha tekshiradi: mavjud bo'lsa hech narsa qilmaydi (log: "already exists"), bo'lmasa `is_active=True, is_superuser=True` bilan yaratadi (`role` server default bo'yicha `admin`).
- Session `app.core.db.local_session` dan olinadi; parol `await get_password_hash(...)` bilan xeshlanadi (funksiya async).
- E'tibor: `crud_users.create` emas, to'g'ridan-to'g'ri `User(...)` konstruktor ishlatadi (schema-validatsiyasiz bootstrap yo'li).

### 5.2 `backend/app/commands/seed_defaults.py`

Idempotent bootstrap — default tashkilot va 6 ishlab chiqarish postini yaratadi (`python -m app.commands.seed_defaults`, prestart/setup scriptlardan chaqiriladi):

- Tashkilot: `select(Organization).limit(1)` — DB'da **birorta ham** tashkilot bo'lmasa `Organization(name="Mebelix")` yaratadi.
- Postlar: mavjud `code` lar to'plami bilan solishtirib, yetishmaganlarini `POSTS` ro'yxatidan qo'shadi — 6 post (`ARRA`…`STOLYARKA`) `order_index` 1–6, `unit` (m2/meter/piece), `color`/`icon` va xulq flaglari bilan: `ARRA` — `requires_qr_print=True`, `PAZ` va `ROVER` — `requires_assignment_choice=True`.

`backend/app/commands/__init__.py` — bo'sh (faqat package marker).

---

## 6. Tasks — ARQ background workers

`backend/app/tasks/__init__.py` — package bitta fayldan iborat, bitta registered task:

| Task | Vazifasi |
|---|---|
| `print_label(ctx, instance_id)` | Bitta fizik nusxa uchun yorliq PNG'ini render qilib chop etish navbatiga qo'yadi (TZ 7.1.4) |

`print_label` oqimi:

1. `app.services.labels.load_label_data(db, instance_id)` — nusxa/detal/buyurtma ma'lumoti va cutmap teshiklari yig'iladi; topilmasa `skip:{instance_id}`.
2. `render_label_png(data)` → `base64` (`png_b64`). Yagona format — PNG: GoDEX G500-U faqat USB, agent rasmni Windows drayveri (GDI) orqali chizadi, printer dialekti kerak emas.
3. ARQ worker kontekstidagi Redis'ga `LPUSH`: `PRINT_QUEUE_KEY = "mes:print:queue"` ro'yxatiga JSON job `{"type": "print", "instance_id", "png"}` → `queued:{instance_id}` (TZ 2.2.2).
4. Worker kontekstida Redis bo'lmasa — `logger.error` + `lost:{instance_id}`.

To'liq zanjir:

```
Terminal "Chop etish"
  -> POST /api/v1/terminal/labels/{instance_id}   (label_printed_at + ws "label.printed")
  -> arq print_label: render_label_png -> LPUSH mes:print:queue
  -> /ws/bridge (per-agent token -> bridge_agent.token_hash): brpop -> agentga yuboradi, ack kutadi
  -> bridge-agent: print-queue.jsonl (durable) -> Windows GDI -> USB GoDEX
```

`/ws/bridge` (`backend/app/api/routes/ws.py`) jobni ack (`{"ok": true}`) kelmasa `rpush` bilan navbatga qaytaradi — yorliq yo'qolmaydi. Auth **per-agent**: token `Authorization: Bearer` headerda keladi (query param eski agentlar uchun fallback), sha256 xeshi bo'yicha tirik `bridge_agent` qatori qidiriladi — topilmasa 4401. Serverda sozlama kerak emas, printer admin paneldan ulanadi (1.4.2-bo'lim). `settings.BRIDGE_TOKEN` faqat **legacy** back-compat sifatida qoldi: bo'sh bo'lsa e'tiborga olinmaydi, to'ldirilgan bo'lsa eski umumiy tokenli agent ham o'tadi (bunday ulanishning jadvalda qatori yo'q — `last_seen_at` yangilanmaydi, panelda ham ko'rinmaydi).

Bridge-agent (`bridge-agent/agent.py`) faqat printer ulangan kompyuterga o'rnatiladi — menejer, texnolog va boshqa post terminallariga hech narsa kerak emas. Birinchi ishga tushganda `_pair()` sozlash oynasini ochadi (`_pair_dialog()` — tkinter, server manzili + ulanish kodi; tkinter bo'lmasa `_pair_console()` zaxirasi), `_exchange()` kodni tokenga almashtiradi va `%APPDATA%\MebelixAgent\.env` ga yozadi — token allaqachon bo'lsa oyna umuman ochilmaydi. Ulangandan keyin `_register_autostart()` agentni `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` ga yozadi, exe esa `--noconsole` bilan qurilgan — kompyuter yonganda oynasiz fonda o'zi tushadi. Exe'ning o'zi `GET /api/v1/bridge-agents/download` dan olinadi. Printerni `_detect_printer()` avtomatik topadi (nomida `godex` bor Windows printeri); env'lari: `MES_URL`, `BRIDGE_TOKEN` (pairing to'ldiradi), `PRINTER_NAME` (ixtiyoriy, qo'lda override), `QUEUE_FILE`.

```python
all_tasks = [print_label]
```

Worker konfiguratsiyasi (ARQ `WorkerSettings`) ro'yxatni `all_tasks` dan oladi; yangi task qo'shilganda shu ro'yxatga kiritilishi kerak. ARQ konvensiyasi: birinchi argument worker context (`ctx`).

---

## 7. Qatlamlararo bog'lanish xulosasi

| Qatlam | Fayllar | Kimga tayanadi | Kim ishlatadi |
|---|---|---|---|
| Models | `backend/app/models/*` | `app.core.db.Base` | CRUD, Alembic autogenerate, commands, services |
| Schemas | `backend/app/schemas/*` | Pydantic, `app.models.enums` | API routes (request/response), CRUD (create/update input) |
| CRUD | `backend/app/crud/*` | Models, Schemas, `app.core.security` | API routes (8 singleton + `log_action`) |
| Migrations | `backend/app/migrations/*`, `backend/alembic.ini` | `app.core.config.settings`, `Base.metadata` | deploy/`alembic upgrade head` |
| Commands | `backend/app/commands/*` | settings, `local_session`, Models | bootstrap (superuser, organization + postlar) |
| Tasks | `backend/app/tasks/*` | ARQ, `app.services.labels`, Redis | worker process |

Naqshlar: **soft delete hamma joyda default** (BaseCRUD avtomatik filtr), **partial unique indekslar** tirik qatorlar orasida (`user`, `order.number`, `employee.badge_id`, `material`, `post.code`, `part_instance`, `part_route`), **VARCHAR-backed enumlar** (`db_enum`, migratsiyasiz yangi a'zo), **JSONB** moslashuvchan maydonlar uchun (cutmap, edges, machine_assignments, assigned_post_ids, survey, order_file.meta — anketa rasmlari jadvalsiz shu orqali bog'lanadi), **token_version** bilan JWT mass-invalidation, **E.164 telefon** username bilan teng huquqli login identifikatori, **MappedAsDataclass** ORM uslubi, **singleton CRUD instancelar**, **partial update** (`exclude_unset=True`), **idempotentlik** (`scan.client_event_id`, seed skriptlar).
