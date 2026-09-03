# Backend Data Layer — Models, Schemas, CRUD, Migrations, Tasks

Bu hujjat MebeliX MES backend'ining ma'lumotlar qatlamini qamrab oladi: SQLAlchemy ORM modellari, Pydantic schemalari, generic CRUD qatlami, Alembic migratsiyalari, CLI komandalar va ARQ background tasklari. Qatlam to'liq **async** (SQLAlchemy `AsyncSession`, asyncpg driver) va aniq qatlamlararo yo'nalishga ega:

```
API routes  →  schemas (validation)  →  crud (biznes DB-operatsiyalar)  →  models (ORM)  →  PostgreSQL
```

Domen modeli to'liq MES sohasini qamrab oladi: **19 jadval** — `user` + 18 MES jadvali (`organization`, `client`, `employee`, `post`, `machine`, `audit_log`, `order`, `work_session`, `product`, `part`, `order_file`, `part_instance`, `part_route`, `scan`, `bridge_agent`, `pachka`, `pachka_item`, `waste_item`). Shablondan qolgan demo `Item` moduli to'liq olib tashlangan; GibLab katalogidan avtomat to'ladigan `material` jadvali ham endi yo'q (`d2b71f4c86e9` da drop — 4.4-bo'lim). Materiallar ombori moduli ham olib tashlandi: `stock_item`/`stock_move`/`sale`/`payment` jadvallari bazada bo'sh turadi (migratsiyalari prodga qo'llangan, 4.4-bo'lim), lekin model qatlamida ular YO'Q.

---

## 1. Models — `backend/app/models/`

### 1.1 `backend/app/models/base.py` — Mixinlar va abstract BaseModel

Barcha ORM modellari uchun umumiy ustunlarni beruvchi mixinlar. Hammasi SQLAlchemy 2.0 `MappedAsDataclass` uslubida yozilgan (modellar Python dataclass sifatida ham ishlaydi, `init=False` / `kw_only=True` / `default_factory` shu mexanizm uchun).

| Klass | Beradigan ustunlar | Izoh |
|---|---|---|
| `IDMixin` | `id: int` | PK, autoincrement, `init=False` (constructor'da berilmaydi) |
| `TimestampMixin` | `created_at`, `updated_at` | `DateTime(timezone=True)`; Python tomonda `datetime.now(UTC)`; `created_at` DB tomonda `current_timestamp(0)` server default. `updated_at` da server default YO'Q (`6a5051b7b420`): INSERT'da NULL qoladi, `onupdate` bilan yangilanadi — «hech tahrirlanmagan» = NULL (ilgari DB defaulti har yangi qatorga vaqt qo'yib, belgi hech qachon ishlamasdi; mavjud qatorlar migratsiyada to'ldirilgan) |
| `SoftDeleteMixin` | `deleted_at`, `is_deleted` | Soft delete; `is_deleted` indekslanMAGAN — 19 ta `ix_*_is_deleted` `6a5051b7b420` da o'chirilgan (boolean tanlovsiz, issiq yo'llardagi PARTIAL `WHERE NOT is_deleted` indekslar qoladi) |
| `BaseModel` | yuqoridagilarning hammasi | `__abstract__ = True`; `app.core.db.Base` + 3 mixin kombinatsiyasi |

```python
class BaseModel(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
```

**Bog'lanish:** `Base` deklarativ asosi `backend/app/core/db.py` dan keladi. `BaseCRUD` (`backend/app/crud/base.py`) aynan shu mixinlar mavjudligiga tayanadi (ayniqsa soft-delete ustunlariga).

### 1.2 `backend/app/models/enums.py` — Domen enumlari

`db_enum(enum_cls, length=30)` helper — **VARCHAR-backed** SQLAlchemy `Enum` (`native_enum=False`): yangi a'zo qo'shilganda PG native enum ALTER'i kerak emas (masalan, `UserRole` ga 9 operator roli migratsiyasiz qo'shilgan). Faylda **11 ta StrEnum** (`ClientType` va `ProjectGeneration` o'lik ustunlar bilan birga olib tashlangan — `c7f2d84a91b3`; `MaterialType` esa material katalogi bilan birga ketgan — `d2b71f4c86e9`; `StockCatalog`/`StockMoveKind` — materiallar ombori moduli bilan):

| Enum | A'zolar |
|---|---|
| `UserRole` | 15 ta: 6 xodim/qurilma (`admin`, `director`, `manager`, `texnolog`, `terminal`, `tablo`) + 9 post operatori (`arrachi`, `kromkachi`, `ovalchi`, `prisadkachi`, `roverchi`, `stolyar`, `boyoqchi`, `upakovkachi`, `omborchi`) |
| `PostCode` | 9 ta: `ARRA`, `KROMKA`, `OVAL`, `PRISADKA`, `ROVER`, `STOLYARKA`, `BOYOQ`, `UPAKOVKA` (qadoqlash bo'limi — marshrutga anketadagi `packaging` bayrog'i bo'yicha qo'shiladi), `TMO` (Tayyor Mahsulot Ombori — marshrutning ENG OXIRGI qadami, har detalda). PAZ olib tashlangan — paz ham frezer stanogida, ya'ni ROVER postida kesiladi |
| `PachkaStatus` | `open` (detal qo'shiladi) → `closed` (chek chiqadi) → `shipped` (TMO dan jo'natildi) |
| `PostUnit` | `m2`, `meter`, `piece` |
| `MachineStatus` | `active`, `inactive`, `repair` — **bezak emas, tanlovga ta'sir qiladi** (`scanning.post_machine`): `inactive` avtomatik TANLANMAYDI va unga bog'langan qurilma hisobi skan qila olmaydi (E009); `repair` tanlanadi, lekin oxirgi navbatda va yangi buyurtma biriktirilmaydi (409). Sababi: admin belgini qaytarishni unutsa tsex to'xtab qolmasligi kerak, `inactive` esa ataylab o'chirish. O'zbekcha nomlar — `MACHINE_STATUS_LABELS` |
| `EmployeeStatus` | `active`, `inactive` |
| `OrderStatus` | `draft`, `technical_review`, `production`, `completed`, `delivered`, `cancelled` |
| `OrderPriority` | `low`, `medium`, `high`, `urgent` |
| `RouteSource` | `auto`, `manual` |
| `FileKind` | `project`, `scx`, `label_pdf`, `document` |
| `SessionStatus` | `active`, `ended` |

`POST_ROLES: dict[UserRole, PostCode]` — 9 operator rolini o'z postiga bog'laydi (`ARRACHI→ARRA`, `KROMKACHI→KROMKA`, `OVALCHI→OVAL`, `PRISADKACHI→PRISADKA`, `ROVERCHI→ROVER`, `STOLYAR→STOLYARKA`, `BOYOQCHI→BOYOQ`, `UPAKOVKACHI→UPAKOVKA`, `OMBORCHI→TMO` (rol kodi odamning kasbi; ekran yozuvi "TMO omborchisi")). Operator rollari tsexda odatda **BEYJIK bilan kiradi** (`POST /login/badge`). Parol bilan kirish esa hisobning TURIGA bog'liq, ROLIGA emas: `is_system=True` hisob (seed yaratgani) 401 oladi, odamning SHAXSIY hisobi esa kiradi va smenasi shu zahoti ochiladi (`login._open_shift_for`). Bu skaneri yo'q post uchun: ARRA da monoblok bor, skaner yo'q — u yerda chek chiqarishning o'zi skan hisoblanadi (`cut_by_print`), ya'ni skaner FAQAT kirish uchun kerak bo'lib qolardi. Ilgari butun rol yopiq edi, chunki har postda bitta umumiy hisob bor edi va uning paroli butun smenaga ma'lum bo'lardi; `is_system` o'sha ikki xil hisobni ajratdi (`e7a35c19d840`). Ish markazi binding'i esa talab qilinmaydi (`TERMINAL` qurilma akkauntlaridan farqli): post rolning o'zidan (`POST_ROLES`), ish markazi `scanning.post_machine` dan topiladi. Tafsilot — `docs/03-backend-api.md` (login.py) va `docs/09-mes-domain.md` §3.0.1.

### 1.3 `backend/app/models/user.py` — User modeli

`user` jadvali. Login identifikatori sifatida **username yoki telefon** ishlatiladi; telefon O'zbekiston E.164 formatida kanonik saqlanadi (`+998` + 9 raqam = 13 belgi). `token_version` — barcha chiqarilgan JWT tokenlarni bir zarbda bekor qilish mexanizmi. Uch joyda inkrement qilinadi: parol almashtirish (`PATCH /users/me/password`), admin boshqa hisobning parolini almashtirganda (`PATCH /users/{user_id}` — ikkalasi ham `backend/app/api/routes/users.py`) va o'g'irlangan refresh token qayta ishlatilganda (`login.py`, one-time-use nazorati). **Parol almashtirish tirik sessiyalarni UZADI** — bu ataylab: parol almashtirishning maqsadi aynan eski kirishni bekor qilish. `logout.py` esa versiyani OSHIRMAYDI — "Chiqish" faqat SHU qurilmani uzadi (refresh `jti` tombstone + cookie tozalash), aks holda monoblokdan chiqqan admin noutbukdagi ishidan ham uchib tushardi. `backend/app/crud/users.py` dagi `increment_token_version` ga qarang.

MES uchun ikkita yangi ustun:

- `role: UserRole` — `db_enum(UserRole)` (VARCHAR), NOT NULL, `server_default="admin"`. `admin`/`director`/`manager`/`texnolog` — odamlar; `terminal`/`tablo` — ish markaziga bog'langan qurilma akkauntlari; operator rollari — post terminaliga kiruvchi ishchilar.
- `machine_id: int | None` — FK `machine.id` (`fk_user_machine_id`); `TERMINAL`/`TABLO` qurilma akkauntini konkret ish markaziga bog'laydi.

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
| `name` | `String(100)` | NULL | — | `schemas/users.py:_NAME_FIELD` va `employee.full_name` bilan bir xil (`e5b73c04a19f`) |
| `username` | `String(20)` | NOT NULL | — | PARTIAL UNIQUE `ix_user_username` (`WHERE NOT is_deleted`) |
| `phone` | `String(13)` | NOT NULL | — | PARTIAL UNIQUE `ix_user_phone` (E.164: `+998XXXXXXXXX`) |
| `hashed_password` | `String` | NOT NULL | — | — |
| `is_active` | `Boolean` | NOT NULL | `True` (Python) | — |
| `is_superuser` | `Boolean` | NOT NULL | `False` (Python) | — |
| `token_version` | `Integer` | NOT NULL | `0` (server_default) | JWT'larni ommaviy bekor qilish |
| `role` | `VARCHAR(30)` (`UserRole`) | NOT NULL | `'admin'` (server_default) | — |
| `machine_id` | `Integer` | NULL | — | FK `machine.id` (`fk_user_machine_id`) |
| `is_system` | `Boolean` | NOT NULL | `False` (server_default) | TIZIM hisobi — `seed_defaults` yaratgan post hisobi; u bilan KIRIB bo'lmaydi (`e7a35c19d840`) |

### 1.4 MES modellari

Barcha MES modellari `BaseModel` dan meros oladi (id + timestamp + soft-delete), enumlar `db_enum(...)` bilan VARCHAR sifatida saqlanadi. Ko'p jadvalda `organization_id` FK (`default=1`) — sxema multi-tenant'ga tayyor, hozircha bitta "Mebelix" tashkiloti.

**Registr modellari** (har biri o'z faylida):

| Model / jadval | Fayl | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|---|
| `Organization` | `organization.py` | faqat `name(100)` (profil maydonlari — `logo_url`, `address`, `phones`, `currency`, `timezone`, `settings` — hech qayerda o'qilmasdi, `c7f2d84a91b3` da drop) | — |
| `Client` | `client.py` | `organization_id`, `full_name(150)`, `phone`/`phone_alt(13)`, `address`, `notes` (`client_type`/`inn` — `c7f2d84a91b3` da drop) | — (`orders_count` saqlanmaydi — query'da hisoblanadi) |
| `Employee` | `employee.py` | `organization_id`, `full_name(100)`, `badge_id(36)` (badge QR, HAR DOIM `uuid4()`), `user_id` FK NULL → `user.id` — hodimni kirish hisobiga bog'laydi (`d1c4e7a90b52`). Ikki holatda to'ladi: skaneri yo'q postda ishlaydigan odamning SHAXSIY hisobi (`login._open_shift_for` smenani aynan shu bog'lamdan topadi) va ishchi ayni paytda ofis roli ham bo'lgan holat. Qurilma (TERMINAL/TABLO) va `is_system` texnik hisoblariga bog'lash rad etiladi. Ilgari bu ustun ARXIV edi — eski avtomat mirror yozuvlarini belgilardi (`c7e2b4f81d39` nofaol qildi, `a9e14b7c2d63` o'chirdi), `phone`, `position`, `status` (`EmployeeStatus`), `assigned_post_ids` **JSONB** (int list — join-table o'rniga) (`passport_id`/`photo_url`/`hired_date` — `c7f2d84a91b3` da drop) | PARTIAL UNIQUE `ix_employee_badge_id`, PARTIAL UNIQUE `ix_employee_user_id`. Bog'lam ATAYLAB `badge_id` da EMAS: ilgari `user-{id}` badge orqali edi va hodimga haqiqiy beyjik chiqarish bog'lamni uzib, ikkinchi qator yaratardi (ish haqi ikkiga bo'linardi). Yo'qolgan badge: qator saqlanadi, `badge_id` almashtiriladi — scan tarixi buzilmaydi |
| `Post` | `post.py` | `organization_id`, `code` (`PostCode`), `name(50)`, `order_index`, `unit` (`PostUnit`), `requires_assignment_choice` (`requires_qr_print`/`auto_skip_if_empty` olib tashlangan — hech qayerda o'qilmasdi, `e8b1c6d94f27` da drop; `icon`/`color` esa MODELDAN olib tashlandi — rang TAQDIMOT, domen ma'lumoti emas: backend uni hech qayerda ishlatmaydi (chek 1-bitli, rangsiz), postlarni tahrirlaydigan UI yo'q va frontend baribir o'z `POST_COLORS` konstantasini o'qirdi, ya'ni ikkita haqiqat manbai bor edi va bazadagisi hech qachon g'alaba qozonmasdi. Ustunlar bazada qoldi) | PARTIAL UNIQUE `ix_post_code`. 9 bosqichli ishlab chiqarish zanjiri: `ARRA`…`BOYOQ` + `UPAKOVKA` + `TMO` |
| `Machine` | `machine.py` | `organization_id`, `post_id` FK (index), `name(100)`, `status` (`MachineStatus`) (`mac_address`/`icon_url`/`serial_number`/`installed_date` — `c7f2d84a91b3` da, `ip_address` — `b1f27ce03d94` da drop: ish markazi bilan aloqa `machine_id` orqali, tarmoq manzili orqali emas. `capacity`/`capacity_unit` va OEE ustunlari MODELDAN olib tashlandi, lekin bazada qoldi — migratsiyalar prodga qo'llangan, ularni orqaga qaytarish deployni yiqitardi; hech qayerdan o'qilmaydi) | PARTIAL UNIQUE `ix_machine_name` (`WHERE NOT is_deleted`, `d8f31a05c7e2`) — nom operatorga monoblokda YOLG'IZ ko'rinadi, ikkita "01 ARRA" bo'lsa u qaysi stanokda turganini ajrata olmasdi; dublikat nom 409 beradi. Terminal/TABLO konteksti `user.machine_id` dan. Nom, post va holat `/work-centers` sahifasidan tahrirlanadi. |
| `AuditLog` | `audit.py` | `user_id` FK NULL (index), `employee_id` FK NULL, `module(50)`, `action(50)`, `entity_type`, `entity_id`, `message`, `meta` **JSONB**, `ip(45)` | `ix_audit_log_module_action` (`module`, `action`), `ix_audit_log_created_at`, `user_id` ustun indeksi — loglar sahifasi filtrlari eng tez o'suvchi jadvalda seq scan qilmasin (`e8b1c6d94f27`). `created_at` = hodisa vaqti |
| `BridgeAgent` | `bridge_agent.py` | `organization_id`, `name(100)` (qaysi kompyuter/post — admin panelda ko'rinadi), `token_hash(64)` (doimiy tokenning sha256'si; NULL = hali ulanmagan), `pair_code(16)` (8 belgili bir martalik kod), `pair_expires_at` (kod TTL — 15 daqiqa), `last_seen_at`, `machine_id` FK NULL (skan-forvard: agent skani qaysi ish markazi nomidan yoziladi), `version(20)` (agent exe versiyasi — WS `X-Agent-Version` headeridan), `can_print` (default `True`; `False` = printersiz skan-forvard stansiyasi — chek navbatidan ish olmaydi) | UNIQUE `ix_bridge_agent_token_hash`; `ix_bridge_agent_pair_code`. Har printerli kompyuterga bitta qator; bekor qilish — soft delete (1.4.2-bo'lim) |

**Buyurtma modellari** (`order.py` — 7 klass):

| Model / jadval | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|
| `Order` | `number(20)` (`B-2026-001`, avto), `client_id` FK (index), `status` (`OrderStatus`, default `draft`, index), `priority` (`OrderPriority`), `deadline`, `amount Numeric(14,2)`, `advance_payment Numeric(14,2)` (boshlang'ich to'lov — manager buyurtma ochishda kiritadi), `notes`, `created_by_id` FK user; `.project` metadata: `project_uuid/name/loaded_at` (`project_generation` — `c7f2d84a91b3` da drop); **JSONB**: `cutmap` (kesish xaritasi vizual modeli), `material_usage` (default `[]` — `[{name, code, kind, count, unit}]`), `machine_assignments` (default `{}` — `{"ROVER": 5}`), `survey` (mijoz anketasi + o'lchov varag'i, NULL — sxema `schemas/orders.OrderSurvey`, 2.4.1-bo'lim); lifecycle: `production_started_at`, `completed_at`, `delivered_at`, `cancelled_at`, `cancel_reason`, `cancelled_by_id` | PARTIAL UNIQUE `ix_order_number` |
| `Product` | `order_id` FK (index), `code(50)`, `name(255)`, `count` (`import_source` — `c7f2d84a91b3` da drop) | `<good typeId="product">` |
| `Part` | `order_id`/`product_id` FK (index), `code(50)` (masalan `01_002`), `name`, `count`, o'lchamlar `length/width/thickness` (`saw_length/saw_width` — `c7f2d84a91b3` da drop), `txt` (tekstura qulfi), `material_name(150)`, `label_num`; **JSONB**: `edges` (tomon bo'yicha kromka: `{"l": {"mat": ..., "symbol": "A"}, ...}`), `xnc_summary` (`{"bores", "edge_bores", "grooves", "mills", "sides"}`); `note` (texnolog izohi), `is_custom` (nostandart bayrog'i, index), `assembly_parent_id` FK NULL → `part.id` (index) | Barqaror kalit: `productCode_partCode`. `is_custom=True` — detal fayldan avtomatik marshrut OLMAYDI: texnolog uni "Nostandart detallar" tabida qo'lda chizadi (`e7c4b208af13`). `assembly_parent_id` — YIG'MA BUYUM (`c9d4e2f81a70`): mayda detal stolyarkada asosiy detalga yopishtiriladi, uning marshruti birikish qadamida TUGAYDI (qadoqlash/TMO dumi qo'shilmaydi) va asosiy detal skani uni ham yopadi. Bir pog'ona — biriktirilgan detalning o'zi asosiy bo'la olmaydi |
| `PartInstance` | `order_id`/`part_id` FK (index), `instance_no` (1..count), `qr_text(120)`, `pattern_no`/`cell_index` (kesish xaritasi katagi), `label_printed_at`, `label_post_id` FK NULL → `post.id` (chekni QAYSI post chiqargan — bekor qilishga faqat o'sha postning huquqi bor; marshrutdan taxmin qilib bo'lmaydi, bitta detalning chekini ARRA ham, ROVER ham chiqarishi mumkin, `c5e81b3a97d2`) | **PARTIAL UNIQUE `ix_part_instance_order_qr` (`order_id`, `qr_text`) `WHERE NOT is_deleted`** — QR = `productCode_partCode` (yagona nusxa, suffikssiz) yoki `productCode_partCode_n` (takrorlanganda); PARTIAL `ix_part_instance_qr_text` (unique EMAS, `WHERE NOT is_deleted`) — skan lookup aynan shu ustun bo'yicha ketadi (`e8b1c6d94f27`) |
| `PartRoute` | Marshrutning BITTA qadami: `order_id`/`part_id`/`post_id` FK, `seq` (marshrutdagi o'rni, 1 dan), `process_code` (1..16 — aynan qaysi amal; 15 = Qadoqlash, 16 = TMO qabuli), `machine_id` FK NULL, `source` (`RouteSource`), `is_enabled` (texnolog o'chira oladi), `per_instance` (qadamdagi skan soni: KROMKA birinchi kelganda — tomonlar soni, takror kelganda 1; OVAL va qolgan postlarda doim 1), `total_required` = count × per_instance, `total_done` | **PARTIAL UNIQUE `ix_part_route_part_seq` (`part_id`, `seq`) `WHERE NOT is_deleted`**; `ix_part_route_part_post` (`part_id`, `post_id`) — endi YAGONA EMAS, faqat qidiruv uchun; `ix_part_route_order_post`. Denormalizatsiyalangan hisoblagichlar — tez QOLDIQ |
| `OrderFile` | `order_id` FK (index), `part_id` FK NULL, `kind` (`FileKind`), `path(500)`, `filename(255)`, `size`, `meta` **JSONB** (default `{}`) | Yuklangan `.project`, part-boshiga `.scx`, label PDF, hujjatlar. Anketa xona rasmlari ham shu yerda: `kind=DOCUMENT` + `meta={"room_id": ..., "content_type": ...}` — alohida jadval/migratsiyasiz (1.4.1-bo'lim) |
| `WasteItem` | FOYDALI atxot (`af6809b43a73`): `order_id` FK (index), `material_name(150)`, `sheet_no` (material ichidagi list raqami), `length`/`width` (foydali o'lcham, mm), `qr_text(120)` (`ATX-{buyurtma}-{n}` — prefiks ataylab detal QR'idan farqli: skan dvijoki uni detal deb qidirmasin), `label_printed_at` | PARTIAL UNIQUE `ix_waste_item_qr_text` (`WHERE NOT is_deleted`). Qatorni GibLab optimizatorining `business="true"` bayrog'i yaratadi (`giblab/ingest.py`) — mayda qoldiq jadvalga TUSHMAYDI (o'tinga ketadi, chek ham chiqarilmaydi). Kesish xaritasi katagidagi `atx` raqami shu qatorga bog'laydi; qayta yuklashda `wipe_previous_parse` tozalaydi |

**Qadoq modellari** (`pachka.py`, migratsiya `7e2e0ae9f7f3`):

| Model / jadval | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|
| `Pachka` | `order_id` FK (index), `code(40)` (`PK-B-2026-014-03` — chekdagi QR matni), `status` (`PachkaStatus`: open → closed → shipped), `closed_at`, `shipped_at` (TMO dan chiqarilgan payt), `created_by_id` FK user | PARTIAL UNIQUE `ix_pachka_code`; `ix_pachka_order_id` (kod `status` ni yakka predikat qilmaydi — `ix_pachka_order_status`/`ix_pachka_status` `6a5051b7b420` da o'chirilgan). Kod tartib raqami O'CHIRILGANLARNI ham sanaydi — qayta ishlatilsa eski chek bilan yangi qadoq bir xil QR berardi |
| `PachkaItem` | `pachka_id`/`instance_id` FK | **PARTIAL UNIQUE `ix_pachka_item_instance` `WHERE NOT is_deleted`** — bitta nusxa faqat bitta qadoqda; ikki qadoqqa tushsa TMO hisobi ikki marta chiqarilardi. Ochiq qadoqdan chiqarish — yumshoq o'chirish. `ix_pachka_item_pachka` (`pachka_id`) — qadoq tarkibini o'qish uchun |

**Marshrut = tartibli qadamlar ketma-ketligi** (`d5a1c93b70e2`) — ilgari `part_route` tartibsiz post to'plami edi:

- Yagonalik `(part_id, post_id)` dan `(part_id, seq)` ga ko'chdi — shu sababli bitta post marshrutda **bir necha marta** uchrashi mumkin (kromka → prisadka → yana kromka). `ix_part_route_part_post` qidiruv uchun qoldi, lekin endi unique emas.
- `process_code` kerak, chunki post nomining o'zi yetarli emas: STOLYARKA da 6 xil, KROMKA da 2 xil amal bor — operator qaysi biri kerakligini shu koddan biladi.
- Skan tartibi postlarning global `order_index` idan emas, detalning O'Z `seq` i bo'yicha tekshiriladi (`services/scanning.py`) — nostandart marshrut global tartibni buzadi. Skan shu postdagi eng kichik `seq` li tugallanmagan qadamga yoziladi.
- Standart (`is_custom=False`) detal fayldan faqat ARRA (kod 1) + KROMKA (kod 3, qirralar soni bo'yicha) + PRISADKA (kod 6) oladi; PRISADKA qadami HAR QANDAY ishlovda ochiladi — teshik, qirra teshigi, paz yoki freza (`giblab/models.py: ParsedPart.stage_sides`; ilgari faqat TESHIK sanalardi va paz/freza-only detal marshrutsiz qolardi — `a7c419e0b3d5`, §4.4). Paz/freza uchun alohida ROVER qadami ataylab yaratilmaydi — roverdan chiqqan detal keyin bo'yalishi mumkinligini fayl bilmaydi (geometriya baribir SCX va yorliq eskiziga ketadi).

**Og'ir JSONB'larni defer qilish** — `order.py` da ikkita modul-darajali tuple: `ORDER_FAT_COLUMNS = (Order.cutmap, Order.survey, Order.material_usage, Order.machine_assignments)` va `PART_FAT_COLUMNS = (Part.xnc_summary, Part.note)`. Ro'yxat/hisobot so'rovlari ularni `defer()` bilan tashlab yuboradi — busiz 100 talik buyurtma reestri 2.2 MB kesish xaritasini bazadan tortib parse qilib tashlar edi (o'lchov: 284 ms → 5 ms). `Part.edges` ataylab ro'yxatda YO'Q — hajm hisobida kerak. Kartochka so'rovlarida ustunlar odatdagidek yuklanadi. `/terminal/orders` esa tuple'ning faqat yarmini — `survey` va `machine_assignments` ni — defer qiladi: `cutmap` va `material_usage` terminal kartasining o'zida ishlatiladi.

#### 1.4.1 Anketa xona rasmlari — `OrderFile.meta` orqali

Xona surati uchun yangi jadval qo'shilmagan: `OrderFile` qatori `kind=FileKind.DOCUMENT` va `meta` JSONB'ida `room_id` (`SurveyRoom.id` ga bog'lanish) + `content_type` bilan saqlanadi. Shu sababli:

- Rasm xonaning ro'yxatdagi **o'rniga** emas, barqaror `SurveyRoom.id` ga bog'langan — xonalar qayta tartiblansa ham bog'lanish buzilmaydi.
- Filtr JSONB operatorlari bilan: `OrderFile.meta["room_id"].astext == room_id`, yetimlarni topishda `OrderFile.meta.has_key("room_id")`.
- Disk yo'li: `{UPLOAD_DIR}/survey/{order_id}/{uuid4().hex}{.jpg|.png|.webp}` — absolyut root `app.core.config.upload_root()` helperidan (path traversal tekshiruvlari ham shunga nisbatan).
- Chegaralar route qatlamida (`backend/app/api/routes/orders/survey.py`): `_ROOM_PHOTO_TYPES` = jpeg/png/webp, `MAX_ROOM_PHOTO_SIZE` = 5 MB, `MAX_ROOM_PHOTOS` = 6 (bitta xonaga).
- `PUT /orders/{id}/survey` (`save_order_survey`) saqlashda anketada endi mavjud bo'lmagan `room_id` li rasmlarni topib, diskdan `unlink` qiladi va qatorni soft-delete qiladi (yetim rasm tozalash). `DELETE /orders/{id}/survey/photos/{file_id}` ham diskdagi faylni o'chiradi — anketa rasmlari tarix uchun saqlanmaydi.
- `GET /orders/{id}/files/{file_id}` (`download_order_file`) `kind` `PROJECT`/`SCX` bo'lsa `application/xml`, aks holda `meta["content_type"]` (bo'lmasa `application/octet-stream`) ni `media_type` qilib beradi — brauzer rasmni `<img>` da yuklab olmasdan ko'rsatadi.

**Skan modellari** (`scan.py` — 2 klass):

| Model / jadval | Muhim ustunlar | Unikal/muhim indekslar |
|---|---|---|
| `WorkSession` | `employee_id` FK (index), `user_id` FK NULL (smenani ochgan hisob — ish markazining TERMINAL hisobi, post rolidagi texnik hisob yoki ishchining SHAXSIY hisobi), `machine_id` FK NULL, `post_id` FK, `status` (`SessionStatus`, index), `ended_at` | **Bitta ish markazida BIR NECHTA ochiq smena bo'lishi mumkin — brigada** (`crew_sessions`): ARRA da ikki kishi birga ishlaydi va detalni qaysi biri olganini bilishning iloji yo'q. Ilgari "bitta ish markazi = bitta smena" edi va ikkinchi kirish birinchisini jimgina yopib, undan keyingi hamma skan bitta odamga yozilardi. `Scan.session_id` LANGAR smenaga (brigadaning birinchisi) yoziladi, ish esa skan VAQTIDA ochiq bo'lgan smenalar orasida teng bo'linadi (`reports.py`). Smena terminalda ochiladi (beyjik skani yoki ismni bosish) yoki ishchi parol bilan kirganda avtomatik (`login._open_shift_for`). `SESSION_MAX_HOURS` (12 soat) dan oshgani avtomatik ENDED. `created_at` = boshlanish vaqti |
| `Scan` | `order_id`/`part_id`/`instance_id`/`route_id`/`post_id` FK, `machine_id` FK NULL, `employee_id` FK (index), `session_id` FK (index), `client_event_id(64)`, `is_cancelled`, `cancelled_at`, `parent_scan_id` FK NULL → `scan.id` (index) | `parent_scan_id` — YIG'MA BUYUM: asosiy detal skani biriktirilgan mayda detallarga ham skan yozadi, hosila qatorlar shu ustun orqali bog'lanadi va bekor qilinganda birga bekor bo'ladi (`c9d4e2f81a70`). UNIQUE `ix_scan_client_event_id` (idempotentlik — network replay rad etiladi); `ix_scan_order_post`; PARTIAL `ix_scan_instance_post` (`WHERE NOT is_cancelled`); `ix_scan_instance_route` (`instance_id`, `route_id`) — skan hisobi QADAM bo'yicha sanaladi (`scanning._scans_done`, issiq yo'l, `d5a1c93b70e2`); `ix_scan_created_at` — dashboard "bugungi skanlar" so'rovi uchun (`a7d3f1c48b26`). Bekor qilingan skan auditda qoladi, hisoblagich qayta oshiriladi |

#### 1.4.2 `bridge_agent` — har printerga o'z tokeni (pairing)

Ilgari barcha printerlar server `.env` idagi **bitta** `BRIDGE_TOKEN` bilan ishlar edi: yangi printer qo'shish uchun serverga SSH kirish kerak bo'lar, bitta token sizib chiqsa esa hamma printer ochilib qolar edi. Endi har printerli kompyuter uchun `bridge_agent` da alohida qator (`BaseModel` ustunlari — id/timestamp/soft-delete — odatdagidek):

- Admin panel yangi agent yaratadi → **8 belgili bir martalik kod** (`pair_code` + `pair_expires_at` = 15 daqiqa). Alfavitda `I/L/O/0/1` yo'q — kodni telefonda aytganda adashtirmaydi (`backend/app/api/routes/bridge_agents.py`).
- Agent kodni `POST /api/v1/bridge-agents/pair` orqali doimiy tokenga almashtiradi. Almashtirish **atomik `UPDATE ... RETURNING`** (`pair_code` mos + muddati o'tmagan) — bitta kodni ikki kompyuter yuborsa faqat bittasi yutadi, kod darhol `NULL` ga tushadi.
- Bazada faqat `token_hash` (sha256, UNIQUE) saqlanadi; tokenning o'zi bir marta — pair javobida — beriladi va agent uni `%APPDATA%\MebelixAgent\.env` ga yozadi.
- `last_seen_at` ni `/ws/bridge` har 5 daqiqada yangilaydi (DB'ga ortiqcha yuk bo'lmasin) — panel shundan **Ulandi/Uzilgan** ni ko'rsatadi.
- Bekor qilish — soft delete (`BaseCRUD.delete`): keyingi ulanish 4401 bilan rad etiladi, jonli ulanish esa navbatdagi tekshiruvda (maks. ~5 daqiqa) uziladi va qo'lda turgan job navbatga qaytadi. Yangi kod berish (`POST /bridge-agents/{id}/code`) `token_hash` ni ham tozalaydi — eski kompyuter shu zahoti kesiladi. Bittasini bekor qilish qolgan printerlarga tegmaydi.

### 1.5 `backend/app/models/__init__.py`

`__all__` da 22 nom: 19 model klassi — `AuditLog`, `BridgeAgent`, `Client`, `Employee`, `Machine`, `Order`, `OrderFile`, `Organization`, `Pachka`, `PachkaItem`, `Part`, `PartInstance`, `PartRoute`, `Post`, `Product`, `Scan`, `User`, `WasteItem`, `WorkSession` — hamda `ORDER_FAT_COLUMNS`/`PART_FAT_COLUMNS` defer-tuple'lari (1.4-bo'lim) va `PRIORITY_RANK` — buyurtma navbatining `case()` ifodasi (URGENT→HIGH→MEDIUM→LOW). Oxirgisi modelda turadi, chunki uni TERMINAL ro'yxati ham, TABLO ham ishlatadi va ikki nusxa bo'lsa navbat ikki xil chiqardi. Alembic `env.py` ham endi shu faylga tayanadi: statik `import app.models` metadata'ni to'ldiradi (avvalgi `pkgutil.walk_packages` dinamik importi olib tashlangan) — yangi model fayli qo'shilsa uni `__init__.py` ga import qilish shart.

---

## 2. Schemas — `backend/app/schemas/`

Pydantic v2 schemalari — API request/response validatsiyasi. `backend/app/schemas/__init__.py` bo'sh (re-export yo'q, importlar to'g'ridan-to'g'ri moduldan qilinadi). Umumiy naqshlar: read-schemalar `from_attributes=True`, create/update-schemalar `extra="ignore"`, update'larda hamma maydon optional (partial PATCH).

### 2.1 `backend/app/schemas/users.py` — User schemalari

Umumiy validatsiya elementlari:

- `PHONE_PATTERN = r"^\+998\d{9}$"` — O'zbekiston E.164 telefon regex'i (model'dagi `String(13)` bilan mos); uni hech bir sxema import qilmaydi — faqat shu modulning `validate_phone` funksiyasi ichida ishlatiladi. `clients.py` (`from .users import validate_phone`) ham, `employees.py` (`from app.schemas.users import validate_phone`) ham shu validatorni import qiladi (§2.3).
- `validate_password_strength(v)` — parol kuchi: 8+ belgi, kichik harf, katta harf, raqam, maxsus belgi (ASCII `[^A-Za-z0-9]` — `lib/validation.ts` regexi bilan bir xil). Xato bo'lsa `ValueError`.
- Qayta ishlatiladigan `Field` konstantalar: `_NAME_FIELD` (2–100, `employee.full_name` bilan bir xil — 30 belgi yetmasdi: "Abdurahmonov Abdurahmon Abdurahmonovich" 39 belgi), `_USERNAME_FIELD` (2–20, `^[a-z0-9]+$`), `_PHONE_FIELD`, `_OPTIONAL_PHONE_FIELD`.

| Schema | Vazifasi | Muhim jihatlar |
|---|---|---|
| `UserRead` | Barcha read javoblar | `from_attributes=True`; `id` — `BeforeValidator(str)` bilan **string** ga aylantiriladi; `role: UserRole` va `machine_id` qaytariladi; `hashed_password` chiqarilmaydi |
| `UserCreate` | `POST /users` (faqat superuser) | `password` strength-validatsiya; `is_superuser`/`is_active` flaglar; `role` (default `UserRole.MANAGER`) va `machine_id` (TERMINAL/TABLO rollari uchun amalda majburiy) |
| `UserUpdate` | `PATCH /users/me` (self-update) | Faqat `name`/`username`/`phone`; privilegiya flaglari va parol yo'q |
| `UserAdminUpdate` | `PATCH /users/{user_id}` (superuser) | `UserUpdate` + `password`, `is_active`, `is_superuser`, `role`, `machine_id` (hammasi optional) |
| `UpdatePassword` | `PATCH /users/me/password` | `current_password` + `new_password` (strength check) |

### 2.2 `backend/app/schemas/auth.py`

- `Token` — `access_token`, `token_type` (login javobi).
- `BadgeLoginRequest` / `BadgePostOption` / `BadgeLoginResponse` — beyjik skani bilan kirish: `badge_id` (1–36) + ixtiyoriy `post_id` (hodim bir nechta postga biriktirilgan bo'lsa qaysi biriga kirayotgani; bittasida bo'lsa server o'zi tanlaydi). Javob `Token` ustiga `employee_name`, `machine_name`, `post_name` qo'shadi.
- `TokenData` — JWT payload'dan dekodlangan ma'lumot:
  - `user_id: int` — subject **immutable PK** (username/phone emas: ular o'zgarishi mumkin, bu tirik sessiyalarni uzib qo'yar va qayta ro'yxatdan o'tishda account confusion'ga yo'l ochar edi);
  - `token_version: int = 0` — User modeli bilan solishtiriladi;
  - `jti: str | None = None` — refresh tokenning unikal id'si (one-time-use enforcement uchun); access tokenlarda `None`.

### 2.3 MES registr schemalari

Har bir registr moduli standart uchlik (`*Read` / `*Create` / `*Update`) beradi:

| Fayl | Schemalar | Muhim jihatlar |
|---|---|---|
| `clients.py` | `ClientRead`, `ClientOrderRow`, `ClientDetail`, `ClientCreate`, `ClientUpdate` | `full_name` 2–150; telefonlar `validate_phone` validatoridan o'tadi; `ClientRead` da bazada saqlanmaydigan, route'da hisoblanadigan maydonlar: `orders_count`, `total_amount` (bekor qilinmagan buyurtmalar summasi — mijozning haqiqiy qiymati), `rank`/`share_pct` va `segment` — ABC (Pareto) segmenti (A — aylanmaning birinchi 80%, B — 95% gacha, C — qolgani; yulduzcha reyting ishlamasdi: prodda eng yirik mijoz aylanmaning 81% ini beradi, ya'ni qolgan hamma bir xil past baho olardi). `ClientDetail` = `ClientRead` + `orders: list[ClientOrderRow]` (mijoz kartochkasidagi buyurtmalar ro'yxati) |
| `employees.py` | `EmployeeRead`, `EmployeeCreate`, `EmployeeUpdate` | `badge_id` **faqat server tomonda** generatsiya qilinadi (UUID) va `EmployeeRead` da ham QAYTARILMAYDI — u tsexdagi yagona kirish kaliti, ekrandagi QR ni suratga olgan odam boshqa hodim nomidan smena ocha olardi; `assigned_post_ids: list[int]` (bo'sh bo'lishi mumkin); `user_id: int \| None` — kirish hisobi bog'lami, birlashgan sahifa "Kirish" ustunini shundan hisoblaydi. Telefon `pattern` o'rniga `validate_phone` VALIDATORIDAN o'tadi: Pydantic shablon xatosi ekranga "String should match pattern '^\\+998...'" bo'lib chiqardi |
| `machines.py` | `MachineRead`, `MachineCreate`, `MachineUpdate` | `post_id` majburiy; `status` enum |
| `posts.py` | `PostRead`, `PostUpdate` | Create yo'q — 9 postlik zanjir qat'iy, faqat `name` va `requires_assignment_choice` tahrirlanadi (`order_index` ham olib tashlandi — egasi `seed_defaults.POSTS`, aks holda PATCH tahriri har prestart'da qaytarilardi) (`icon`/`color` olib tashlandi — rang frontend konstantasida) |

### 2.4 `backend/app/schemas/orders.py` — Buyurtma schemalari

| Schema | Vazifasi |
|---|---|
| `OrderRead` | Registr qatori: `number`, `status`, `priority`, `client_id` + route'da join qilinadigan `client_name`, `deadline`, `amount`, `advance_payment`, `notes`, `project_name`, barcha lifecycle timestamplar |
| `MaterialUsageItem` | `material_usage` yozuvi (ingest.py yozadi): `name`, `code` (goods SKU, NULL bo'lishi mumkin), `kind` (`sheet`/`band`/`hardware`), `count`, `unit` — buyurtma kartasining Furnituralar tabi shu ro'yxatni ko'rsatadi |
| `OrderFileRead` | Fayl qatori: `id`, `kind`, `filename`, `size`, `part_id`, `meta: dict[str, Any]` (default `{}` — anketa rasmida `{"room_id", "content_type"}`), `created_at` |
| `OrderDetail` | `OrderRead` + `machine_assignments`, `project_uuid`/`project_loaded_at`/`project_name` (**yuklangan fayl nomi, kengaytmasiz**: `2064 alisher.project` -> `2064 alisher`; ilgari fayl ICHIDAGI `<root name=...>` atributidan olinardi va GibLab eksportlarining bir qismida u yo'q — prodda 39 buyurtmadan 20 tasida nom bo'sh qolgan edi, migratsiya `b8e4a71c92d5` ularni to'ldirdi), `survey: dict \| None` (xom JSONB — texnolog o'qiydi), `material_usage: list[MaterialUsageItem]`, `files: list[OrderFileRead]`, `parts_count`, `instances_count` (buyurtma kartasi), `can_edit` (buyurtma hali tahrirlanadimi — ishlab chiqarishdagisi ham tahrirlanadi, TO birinchi skangacha), `edit_blocked_reason` (tahrirlab bo'lmasa SABABI: "ARRA postida 12 ta skan (26-08 10:15)" — tugmani jimgina o'chirib qo'yish texnologni sababsiz qoldirardi), `cancelled_by_name` (ISM, id emas — kartochkada "Bekor sababi" yonida turadi; `cancelled_by_id` bazada yozilardi-yu hech qayerda o'qilmasdi, ya'ni foydalanuvchi sababni ko'rib kimligini audit logdan qidirishga majbur bo'lardi; ism faqat bekor qilingan buyurtmada so'raladi) |
| `OrderCreate` | Manager DRAFT ochadi: `client_id`, `deadline`, `priority`, `amount`/`advance_payment` (`ge=0`), `notes`; `number` avto (`B-2026-001`) |
| `OrderUpdate` | Hammasi optional (shu jumladan `advance_payment`) |
| `OrderCancel` | `reason` (3–500 belgi, majburiy) |
| `MachineAssignments` | `assignments: dict[PostCode, int]` — ishlab chiqarishdan oldin post-boshiga ish markazi tanlovi |
| `RouteCell` | Marshrutning bitta qadami: `id` (`part_route` qatori id'si), `post_id`, `seq` (marshrutdagi o'rni), `process_code` (1..16 — 15/16 marshrut dumi, `TAIL_CODES`), `source`, `is_enabled`, `per_instance`, `total_required`, `total_done`, `machine_id` |
| `MatrixPart` | Matritsa qatori: part o'lchamlari + `edges` + `note` + `is_custom` + `assembly_parent_id` (qaysi asosiy detalga biriktirilgan) + `assembly_children: list[dict]` (`[{part_id, code, count}]` — UI ro'yxati) + `routes: list[RouteCell]` |
| `OrderMatrix` | `order_id` + `parts: list[MatrixPart]` |
| `MatrixPartEdit` | Texnolog bitta part qatorini tahrirlaydi: `part_id` (majburiy — qaysi matritsa qatori tahrirlanayotgani), `note`, `count` (1–1000), `stages: dict[int, bool]` (post_id → yoqilgan), `is_custom: bool \| None` (nostandart bayrog'i), `route_codes: list[int] \| None` (nostandart marshrut — jarayon kodlari TARTIB bilan, masalan `[7, 11, 8]`; kod takrorlanishi mumkin, bo'sh ro'yxat marshrutni tozalaydi), `assembly_parent_id: int \| None` (YIG'MA BUYUM bog'lami — texnolog aynan shu maydon orqali o'rnatadi: `None` yuborilsa bog'lam uziladi, maydon umuman yuborilmasa tegilmaydi — `model_fields_set`) |
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
| `packaging` | `bool` | default `False` — yetkazishdan oldin qadoqlash |
| `delivery` | `bool` | default `False` — bitta mashina, bitta manzil |
| `installation` | `bool` | default `False` — bitta brigada, bitta tashrif |
| `rooms` | `list[SurveyRoom]` | ≤10 |

`packaging`/`delivery`/`installation` **buyurtma darajasida**, xona ichida emas: tsex va logistikaga xona degan tushuncha yetib bormaydi (bitta `.project` fayl butun buyurtmaga yuklanadi). `survey` — JSONB, shuning uchun migratsiya kerak emas: eski yozuvlarda bu kalitlar umuman yo'q (o'qishda xom dict qaytadi, `OrderSurvey` bo'yicha qayta validatsiya yo'q) va frontend ularni belgilanmagan deb oladi; `delivery`/`installation` esa xonalardagi eski `yetkazish`/`montaj` kodlaridan qayta tiklanadi (`frontend/src/routes/_layout/anketa.$orderId.tsx`).

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

**Variant kodlari** (`ldsp`, `mdf`, `akril`, `led`, `rozetka`, `burchak`, ...) bazaga **kod** sifatida yoziladi; matnga aylantirish faqat `frontend/src/lib/anketa.ts` katalogida (`FURNITURE_TYPES`, `LAYOUT_SHAPES`, `CORPUS_MATERIALS`, `CORPUS_THICKNESS`, `FACADE_MATERIALS`, `COUNTERTOPS`, `HARDWARE_LEVELS`, `EXTRA_SERVICES`, `WALL_LETTERS` + `labelOf`/`labelsOf`). Backend ro'yxatni qat'iy tekshirmaydi — yangi variant qo'shilganda migratsiya ham, backend o'zgarishi ham kerak emas, eski qatorlarda saqlangan kod ham buzilmaydi.

### 2.5 `backend/app/schemas/terminal.py` — Terminal/skan schemalari

| Schema | Vazifasi |
|---|---|
| `ShiftStart` | Smenani boshlash — IKKI yo'l, natijasi bir xil: `badge_id` (8–36 belgi, optional — skaneri bor postda bitta harakat) yoki `employee_id` (ekrandagi ro'yxatdan ismni bosish — ARRA da skaner yo'q). `join: bool = False` — brigadaga QO'SHILISH; sukut `False` almashtiradi (chiqishni unutish xavfsiz tomonga og'sin) |
| `TerminalEmployee` | "Kim ishlayapti?" ro'yxatidagi tugma: `id`, `full_name`, `position` |
| `SessionRead` | Sessiya: `id`, `employee_id` + join qilinadigan `employee_name`, `machine_id`, `post_id`, `status`, `created_at`, `ended_at`, `is_me` — shu smenani KIRGAN odamning o'ziniki: tsex hisobi bilan kirgan operator o'zini brigada chipida ko'rmasligi kerak, chip faqat QO'SHILGAN sherik uchun |
| `TerminalContext` | Terminal konteksti: `machine_id`/`machine_name`, `post_id`/`post_code`/`post_name` + `crew: list[SessionRead]` — ish markazidagi HAMMA ochiq smena (brigada, 1.4-bo'lim); bo'sh ro'yxat = hali hech kim smenani boshlamagan. `agent_online` — `None` = ish markaziga agent biriktirilmagan (chek chiqmaydi), aks holda paneldagi bilan bir xil 6 daqiqalik oyna (skan-forvard-only agent ham qamraladi: u o'lsa skanlar MES'ga jimgina tushmay qolardi; jonli o'zgarish `bridge.connected/disconnected` dan); `agent_prints` — biriktirilgan agent chek chiqaradimi (`can_print`), `agent_online` `None` bo'lsa ma'nosiz |
| `TerminalOrderCard` | Terminal proyekt tanlagichi kartasi (`/terminal/orders`): `done`/`total` post turiga moslangan, `materials` (arrachi partiyalab kesadi), `sheets_total`, `has_cutmap` |
| `QrOrderRef` | QR qaysi aktiv buyurtmaga tegishli (`/terminal/qr/{qr}/order`): `order_id` + `order_number` |
| `KromkaInstance`, `KromkaPartRow`, `KromkaOrderState` | KROMKA post sahifasi: har nusxaning `done` (yopishtirilgan tomonlar) + `arra_passed` flagi; qator darajasida `sides`, `total_done`/`total_required`, `process_code`, `route_id`. Nusxaning `done` hisobi QADAM bo'yicha (`_post_scan_counts` → `{(instance_id, route_id): count}`) — post bo'yicha sanalsa takror kromka o'tishida birinchi o'tishning skanlari ikkinchisini ham "bajarildi" qilib ko'rsatardi |
| `PrisadkaFile`, `PrisadkaInstance`, `PrisadkaPartRow`, `PrisadkaOrderState` | CNC post sahifasi (PRISADKA/ROVER): detallar + SCX fayllar, `arra_route` (marshrutda ARRA yo'q bo'lsa QR chek shu sahifadan), `route_id`, nusxa darajasida `label_printed`/`done` (hisob qadam bo'yicha) |
| `ScanRequest` | `qr_text` + `client_event_id` (klient UUID — idempotentlik) |
| `ScanResult` | `scan_id`, `duplicate` (replay — xato emas), part ma'lumotlari, yangi `qoldiq`, `order_stage_completed`/`order_completed` flaglar |
| `ScanHistoryItem` | Skan tarixi qatori (`is_cancelled` bilan) |
| `CutmapModel` (+ `CutmapMaterial`/`CutmapSheet`/`CutmapCell`/`CutmapDim`/`CutmapCut`/`CutmapHole`/`CutmapBore`/`CutmapEdgeBore`), `CutmapWasteItem`, `CutmapInstanceState`, `CutmapState` | ARRA kesish xaritasi ekrani: TIPLANGAN vizual `model: CutmapModel \| None` (ilgari `dict[str, Any]` edi — generatsiya qilingan klient bo'sh tur berardi va frontend butun xaritani `any` ustida yozardi) + har nusxaning jonli holati (`pattern_no`/`cell_index`/`done`/`label_printed_at`, `custom` — nostandart detal xaritada pushti, `arra_route` — list ARRAniki emas ROVERniki bo'lsa xira ko'rinadi) + `waste_items: list[CutmapWasteItem]` (foydali atxot, katakdagi `atx` raqami orqali bog'lanadi) |
| `PostQueueRow`, `PostQueueState` | Post navbati sahifasi (BOYOQ, STOLYARKA): qator NUSXA darajasida — bo'yoqchi oltita eshikning to'rttasini bo'yab, qolganini ertaga qilishi mumkin. `instance_id`, `qr_text`, `part_code`/`part_name`, o'lchamlar, `material` (bo'yoqchi uchun bu RANG), `note`, `process_code`, `ready` (oldingi bosqichlar tugadimi), `stage` (detal hozir qayerda), `done`, `assembly` (biriktirilgan mayda detallar) |
| `PachkaItemRow`, `PachkaRow`, `UpakovkaPending`, `UpakovkaOrderState` | UPAKOVKA post sahifasi: ochiq/yopiq qadoqlar (`code`, `status`, `items`, taxminiy `weight_kg` — faqat KO'RSATILADI, hech narsani bloklamaydi) va hali qadoqlanmagan tayyor nusxalar (`pending`); `density` (kg/m³) og'irlik hisobi uchun |
| `PachkaScan` | Qadoq QR'i bo'yicha amal: `qr_text` (3–120) |
| `TmoPending`, `TmoDone`, `TmoOrderState` | TMO post sahifasi (qabul + topshirish bitta holatda): `TmoOrderState` da `order_status`, `packaging` (marshrutda UPAKOVKA bormi — topshirish qadoq bo'yichami yoki detal bo'yichami) va `total`/`arrived`/`accepted` (`accepted <= arrived <= total` — "40 dan 20 tasi keldi, 10 tasi qabul qilindi" bir qarashda ko'rinsin). Qabul qilinganlar `done: list[TmoDone]` (`pachka_code`, `accepted_at`) — ilgari ular javobdan butunlay chiqib ketardi va sahifa yangilansa omborchi o'zi qabul qilganlarini boshqa ko'rmasdi. Qolganlar `pending: list[TmoPending]`: `ready` + `pachka_code` (qadoqsiz buyurtmada `None`) va `stage` — tayyor bo'lmasa detal HOZIR qaysi bosqichda ("Kromka", "Prisadka"), omborchiga "tsexda" degan umumiy so'z hech narsa bermaydi |

Umumiy "NAVBATDAGI VAZIFALAR" jadvali (`TaskRow`) va `/terminal/tasks` endpointi olib tashlangan — har post o'z sahifasida ishlaydi (`Kromka*`/`Prisadka*`/`PostQueue*`/`Upakovka*`/`Tmo*`), beyjik body'si esa endi `schemas/auth.py: BadgeLoginRequest` da.

### 2.6 Kichik schemalar

| Fayl | Schema | Vazifasi |
|---|---|---|
| `backend/app/schemas/common.py` | `Message` | Generic `{"message": str}` javob |
| | `Paginated[T]` | Standart sahifalangan ro'yxat javobi: `{data: list[T], count: int}` — registr ro'yxatlarida (users, clients, employees, orders, audit). Postlar/ish markazlari/bridge-agentlar va terminal yordamchi ro'yxatlari (`terminal/employees`, `terminal/orders`) xom `list[...]` qaytaradi — sahifalanmaydi |
| `backend/app/schemas/health.py` | `HealthCheck`, `ReadyCheck` | Liveness/readiness endpointlari; `ReadyCheck` `database` va `redis` holatini ham qaytaradi |
| `backend/app/schemas/bridge_agents.py` | `BridgeAgentRead`, `BridgeAgentCreate`, `BridgeAgentUpdate`, `BridgeScanRequest`, `BridgePairRequest`, `BridgePairResponse`, `AgentRelease` (CI qurgan oxirgi agent exe — `version`, `sha256`; manbasi `agent-dist/version.json`), `BridgeLogPush` (agent log push tanasi — `lines`, ≤200) | MES agentlari (1.4.2-bo'lim): `BridgeAgentRead` `token_hash` o'rniga `paired: bool` beradi, `pair_code` faqat muddati o'tmagan bo'lsa; `BridgeAgentUpdate` — `machine_id`/`can_print` PATCH body; `BridgeScanRequest` — skan-forvard body (`POST /bridge-agents/scan`, javobi `ScanResult`); `BridgePairResponse.token` — tokenning yagona ko'rinishi |
| `backend/app/schemas/tablo.py` | `StageAgg`, `TabloPostCol`, `TabloOrderRow`, `TabloMatrix`, `TabloPartRow`, `TabloOrderDetail` | TABLO javob modellari (avval `tablo.py` route ichida inline edi); `TabloMatrix.posts` endi typed (`TabloPostCol`) |
| `backend/app/schemas/reports.py` | `EmployeeProductivity`, `ProductivityReport`, `OrderReportRow`, `OrdersReport`, `MaterialUsageRow`, `MaterialsReport`, `DashboardToday`, `DashboardOrders`, `ReadyOrder`, `PostLoad`, `TrendDay`, `DashboardMoney`, `DashboardStats` | Hisobot/dashboard javob modellari (avval `reports.py` route ichida inline edi) |
| `backend/app/schemas/audit.py` | `AuditLogRead`, `AuditSummaryRow` | Loglar sahifasi qatori (avval route ichida inline edi) |

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

Tranzaksiya chegarasi: `delete` — sinfdagi **yagona o'zi commit qiladigan** metod. Shu sababli u bilan birga `log_action` stage qilingan bo'lsa, audit qatori ham shu commitda ketadi; qolgan yozuv oqimlarida commit route qatlamining zimmasida.

### 3.2 `backend/app/crud/users.py` — `CRUDUser`

`BaseCRUD[User]` + autentifikatsiya logikasi. Modul oxirida singleton: `crud_users = CRUDUser(User)`.

| Metod | Vazifasi |
|---|---|
| `get_by_login(db, identifier)` | Identifier `+` bilan boshlansa `phone`, aks holda `username` bo'yicha qidiradi |
| `create(db, user_create)` | Parolni `await get_password_hash(...)` (`backend/app/core/security.py`) bilan xeshlab yaratadi; faqat `flush` (INSERT shu yerda ketadi) — **commit route zimmasida**; caller pre-check qilsa ham, race'da yuzaga keladigan `IntegrityError` tutilib `DuplicateValueException` (409) qaytariladi |
| `update(db, db_user, user_update)` | `UserUpdate` yoki `dict`; `exclude_unset=True` (partial); `password` kelsa avtomatik `hashed_password` ga xeshlanadi (`await`); faqat `flush` — commit route zimmasida; `IntegrityError` → `DuplicateValueException` (409) |
| `authenticate(db, username_or_phone, password)` | `get_by_login` + `verify_password`; user **topilmasa ham** modul-darajali `_DUMMY_HASH` ustida `verify_password` bajariladi — javob vaqti user mavjudligini oshkor qilmaydi (timing attack himoyasi); `logger.warning` faqat user TOPILIB paroli noto'g'ri bo'lganda yoziladi — identifikator umuman topilmasa dummy-hash verify bajarilib JIMGINA `None` qaytadi (log yo'q); xatoda `None` |
| `increment_token_version(db, user)` | `token_version += 1` — foydalanuvchining barcha access/refresh tokenlarini bekor qiladi; faqat `flush` — commit route zimmasida |

### 3.3 `backend/app/crud/orders.py` — `CRUDOrder`

`BaseCRUD[Order]` + bitta maxsus metod:

- `next_number(db) -> str` — joriy yil ichida ketma-ket buyurtma raqami: `B-{yil}-` prefiksli qatorlar orasidan raqam suffiksi (`split_part(number, '-', 3)`) **INTEGER ga cast qilinib** `MAX` olinadi, +1, `B-2026-001` formatida (`{seq:03d}`) qaytariladi. **Yil `Asia/Tashkent` bo'yicha** (`TASHKENT_TZ`) — UTC yili 1-yanvar 00:00-05:00 mahalliy oralig'ida hali o'tgan yilni berardi. Cast ataylab: satr (leksikografik) max 999 dan keyin `"B-2026-999" > "B-2026-1000"` bo'lib raqamlashni sindirardi.

Singleton: `crud_orders = CRUDOrder(Order)`.

### 3.4 `backend/app/crud/audit.py` — `log_action`

Singleton emas — oddiy funksiya (sync, `db.add` qiladi, `await` yo'q):

```python
def log_action(db, *, module, action, user_id=None, employee_id=None,
               entity_type=None, entity_id=None, message=None, meta=None, ip=None) -> AuditLog
```

`AuditLog` qatorini **caller tranzaksiyasida** stage qiladi — asosiy o'zgarish bilan birga commit bo'ladi (yoki birga rollback). Routelar `from app.crud import log_action` deb ishlatadi.

### 3.5 `backend/app/crud/__init__.py` — yupqa registrlar + re-export

Paketda `__init__.py` dan tashqari **4 modul** bor: `base.py`, `orders.py`, `users.py`, `audit.py`. O'z metodi yo'q sakkizta registr uchun alohida fayl ham, bo'sh subclass ham yo'q — `BaseCRUD` to'g'ridan-to'g'ri shu yerda instansiyalanadi:

```python
crud_bridge_agents: BaseCRUD[BridgeAgent] = BaseCRUD(BridgeAgent)
crud_clients: BaseCRUD[Client] = BaseCRUD(Client)
crud_employees: BaseCRUD[Employee] = BaseCRUD(Employee)
crud_machines: BaseCRUD[Machine] = BaseCRUD(Machine)
crud_pachkas: BaseCRUD[Pachka] = BaseCRUD(Pachka)
crud_part_instances: BaseCRUD[PartInstance] = BaseCRUD(PartInstance)
crud_posts: BaseCRUD[Post] = BaseCRUD(Post)
crud_waste_items: BaseCRUD[WasteItem] = BaseCRUD(WasteItem)
```

Modelga maxsus metod kerak bo'lsa — `orders.py`/`users.py` kabi alohida subclass qilinadi. Registrlarning maxsus logikasi route qatlamida (masalan, employee badge regeneratsiyasi, client orders_count join'i, agent pairing'ining atomik `UPDATE` i).

Re-export (`__all__`): **10 singleton** — `crud_bridge_agents`, `crud_clients`, `crud_employees`, `crud_machines`, `crud_orders`, `crud_pachkas`, `crud_part_instances`, `crud_posts`, `crud_users`, `crud_waste_items` — hamda `log_action`.

---

## 4. Migrations — Alembic

### 4.1 `backend/alembic.ini`

Standart Alembic konfiguratsiya: `script_location = app/migrations`, `prepend_sys_path = .` (shuning uchun `backend/` katalogidan turib `alembic` ishga tushiriladi). `sqlalchemy.url` kaliti faylda UMUMAN yo'q — o'rnida faqat izoh turibdi: URL'ni runtime'da `env.py` `config.set_main_option("sqlalchemy.url", ...)` bilan `.env` dan **noldan quradi**, ya'ni parol repoga tushmaydi. Logging bo'limi: root/alembic/sqlalchemy loggerlar, console handler. `[post_write_hooks]` — yangi yaratilgan revision fayli ustidan ketma-ket `ruff check --fix` va `ruff format` ishlaydi (`ruff_check`, `ruff_format`), shuning uchun autogenerate natijasini CI lint darvozasi uchun qo'lda tuzatish shart emas.

### 4.2 `backend/app/migrations/env.py`

Async migration environment:

- DB URL `app.core.config.settings` dan dinamik quriladi: `POSTGRES_ASYNC_PREFIX + USER:PASSWORD@SERVER:PORT/DB` — `.env` bilan sinxron, alembic.ini'ga parol yozilmaydi.
- Statik `import app.models` — `app/models/__init__.py` barcha jadval modullarini import qilgani uchun metadata shu bilan to'ladi (avvalgi `pkgutil.walk_packages` dinamik importi olib tashlangan); yangi model fayli `__init__.py` ga qo'shilishi shart, aks holda autogenerate uni ko'rmaydi.
- `target_metadata = Base.metadata` (`backend/app/core/db.py`).
- Online rejim: `async_engine_from_config` (`NullPool`) → `connection.run_sync(do_run_migrations)` → `asyncio.run(...)`. Offline rejim ataylab yo'q (ikki data-migratsiya `op.get_bind()` ishlatadi).
- `include_object` — migratsiyasi prodga QO'LLANGAN, lekin modeli olib tashlangan obyektlarni autogenerate solishtiruvidan chiqaradi: `LEGACY_TABLES` (6 ta: `machine_stop`, `payment`, `sale`, `stock_item`, `stock_move`, `stop_reason`) va `LEGACY_COLUMNS` (7 ta: `machine.capacity`, `machine.capacity_unit`, `machine.ideal_rate`, `machine.planned_minutes_per_day`, `part_instance.cut_meters`, `post.color`, `post.icon`). Usiz `alembic check` har safar soxta drift berardi va haqiqiy drift shovqin ichida ko'rinmay qolardi (4.4-bo'lim). Filtr faqat REFLEKSIYADAN kelgan (bazada bor, modelda yo'q) ustunga tegadi: `type_ == "column" and reflected and compare_to is None`.

### 4.3 `backend/app/migrations/script.py.mako`

Yangi revision fayllari uchun standart shablon (`upgrade()` / `downgrade()` skeleti, `revision`/`down_revision` identifikatorlari). Importlar loyihaning ruff qoidalariga moslangan: `from collections.abc import Sequence` (UP035) va isort tartibi `collections.abc` -> `typing` -> `sqlalchemy` -> `alembic` (I001).

### 4.4 Versiyalar zanjiri — `backend/app/migrations/versions/`

47 ta migratsiya, head: `1cfd3b2182fc`.

**Olib tashlangan ikki modulning migratsiyalari ATAYLAB qoldirilgan** — OEE
(37–39) va materiallar ombori (27–28). Modul kodi butunlay
olib tashlandi (egasi hozircha kerak emas dedi), lekin migratsiyalar prodga
allaqachon qo'llangan. Faylni
o'chirish keyingi deployda `alembic upgrade head` ni "Can't locate revision"
bilan yiqitardi, ya'ni prod deploy butunlay sinardi. OEE jadvallari
(`stop_reason`, `machine_stop` — `defect` esa 40-migratsiyada DROP qilingan) va ustunlari
(`machine.planned_minutes_per_day`, `machine.ideal_rate`,
`part_instance.cut_meters`), shuningdek ombor jadvallari (`stock_item`,
`stock_move`, `sale`, `payment`) bazada bo'sh turadi va hech qayerdan
o'qilmaydi — model qatlamida ular YO'Q. INSERT buzilmaydi:
`planned_minutes_per_day` server default'i (`480`) bilan to'ladi, qolgan
ikkitasi NULL qabul qiladi.

Yetim ustunlar shu uchtasi bilan tugamaydi: MODELDAN olib tashlangani uchun
bazada yolg'iz qolgan yana to'rttasi bor — `machine.capacity`,
`machine.capacity_unit`, `post.color`, `post.icon` (hammasi `1393a241b793` da
tug'ilgan, hech qaysi migratsiya ularni drop qilmagan). Jami **6 yetim jadval
va 7 yetim ustun**; hammasi `migrations/env.py` dagi
`LEGACY_TABLES`/`LEGACY_COLUMNS` da sanab o'tilgan va `include_object` ularni
`alembic check` solishtiruvidan chiqaradi (4.2-bo'lim). Ularning 6 ta `ix_<yetim>_is_deleted` indeksi ham joyida — `6a5051b7b420` faqat jonli modellarning 19 tasini o'chirgan (prodda 25 = 19 + 6).

| # | Revision | Fayl | Nima qiladi |
|---|---|---|---|
| 1 | `e1c262d7e2ae` | `e1c262d7e2ae_init.py` | **Init**: `user` va (o'sha paytdagi demo) `item` jadvallari, to'liq unique indekslar |
| 2 | `b7f3a9c41d02` | `b7f3a9c41d02_drop_items_partial_unique_user.py` | `item` jadvalini drop qiladi; `ix_user_username`/`ix_user_phone` ni **partial unique** ga almashtiradi (`WHERE NOT is_deleted`) |
| 3 | `1393a241b793` | `1393a241b793_mes_domain_org_posts_machines_employees_.py` | **MES domeni**: 15 jadval yaratadi (`organization`, `client`, `employee`, `material`, `post`, `machine`, `audit_log`, `order`, `work_session`, `product`, `part`, `order_file`, `part_instance`, `part_route`, `scan`) + `user` ga `role` (server_default `'admin'`) va `machine_id` (FK `fk_user_machine_id`) qo'shadi. Oxirida **default `organization` qatorini ham qo'yadi**: idempotent `INSERT INTO organization (name, phones, currency, timezone, settings, is_deleted) SELECT 'Mebelix', ... WHERE NOT EXISTS (SELECT 1 FROM organization)`. Sabab — keyingi uchta post migratsiyasi (`b3e9a1d76c42`/BOYOQ, `f1b6d0c73a25`/UPAKOVKA, `a3f8d61c9b04`/OMBOR — bugungi TMO) `post` ga `organization_id = 1` bilan qator qo'yadi, `seed_defaults` esa prestart'da migratsiyalardan KEYIN ishlaydi: busiz toza bazada `alembic upgrade head` FK buzilishi bilan yiqilardi. `phones`/`currency`/`timezone`/`settings` shu nuqtada hali NOT NULL — ular keyinroq `c7f2d84a91b3` da drop qilinadi |
| 4 | `3b4e0b90f440` | `3b4e0b90f440_order_material_usage.py` | `order.material_usage` JSONB NOT NULL (server_default `'[]'`) |
| 5 | `7d2c9f5e1b3a` | `7d2c9f5e1b3a_order_advance_payment.py` | `order.advance_payment Numeric(14,2)` NULL — to'lov oqimi maydoni |
| 6 | `a91c7d34f6e2` | `a91c7d34f6e2_order_survey.py` | `order.survey JSONB` NULL — mijoz anketasi va o'lchov varag'i (xonalar bo'yicha) |
| 7 | `d5e81a24c3b7` | `d5e81a24c3b7_bridge_agent_pairing.py` | **`bridge_agent`** jadvali (printer agentlari: ulanish kodi + token xeshi) + 3 indeks: UNIQUE `ix_bridge_agent_token_hash`, `ix_bridge_agent_pair_code`, `ix_bridge_agent_is_deleted` (1.4.2-bo'lim) |
| 8 | `f4b8c2a91e55` | `f4b8c2a91e55_bridge_agent_machine.py` | `bridge_agent.machine_id` FK NULL — skan-forvard: agent skani qaysi ish markazi nomidan yoziladi |
| 9 | `a7c3e9d12f04` | `a7c3e9d12f04_bridge_agent_version.py` | `bridge_agent.version(20)` NULL — agent exe versiyasi (WS `X-Agent-Version` headeridan) |
| 10 | `c9e5b2a41d78` | `c9e5b2a41d78_single_copy_qr_no_suffix.py` | Data-migratsiya: `count=1` detallarda `qr_text` dagi `_1` suffiksi olib tashlanadi — chek/QR/SCX nomi bir xil (Nanxing mosligi); downgrade yo'q |
| 11 | `d4f7a8c25e91` | `d4f7a8c25e91_bridge_agent_can_print.py` | `bridge_agent.can_print` NOT NULL (server_default `true`) — printersiz agent chek navbatidan ish olmaydi |
| 12 | `e8b1c6d94f27` | `e8b1c6d94f27_hot_path_indexes.py` | Issiq yo'l indekslari: PARTIAL `ix_part_instance_qr_text` (`WHERE NOT is_deleted`), `ix_audit_log_module_action`, `ix_audit_log_created_at`; `post.requires_qr_print`/`auto_skip_if_empty` drop |
| 13 | `a7d3f1c48b26` | `a7d3f1c48b26_scan_created_at_orderfile_part.py` | Yana ikki issiq yo'l indeksi: `ix_scan_created_at` (dashboard "bugungi skanlar" har 60 s da so'raydi), `ix_order_file_part_id` (CNC skanida detalning SCX fayli shu ustun bo'yicha qidiriladi) |
| 14 | `b3e9a1d76c42` | `b3e9a1d76c42_remove_paz_add_boyoq.py` | **PAZ posti olib tashlanadi, `BOYOQ` qo'shiladi.** Sxema o'zgarmaydi (`post.code` — VARCHAR), lekin ma'lumot **HARD DELETE** qilinadi: `select(Post)` filtrsiz chaqiriladi (prestart'dagi `seed_defaults`, orders/reports/tablo/ingest) va enumda yo'q kod bazada qolsa SQLAlchemy `LookupError` beradi — konteyner ko'tarilmay qoladi. Ketma-ketlik: `pazchi` userlar → `roverchi`, `order.machine_assignments` dan `"PAZ"` kaliti olib tashlanadi, PAZ skan/marshrut/smenalari o'chiriladi, PAZ ish markazlariga havolalar `NULL` ga tushiriladi (FK sug'urtasi), ish markazlari va postning o'zi o'chiriladi, `BOYOQ` qatori qo'yiladi. Downgrade qaytarmaydi (faqat `BOYOQ` ni oladi) |
| 15 | `c7f2d84a91b3` | `c7f2d84a91b3_drop_dead_columns.py` | **19 o'lik (faqat yoziladigan, hech qayerda o'qilmaydigan) ustun DROP** (2026-08-05 to'liq audit): `part.saw_length/saw_width`, `product.import_source`, `order.project_generation`, `organization` profil maydonlari (6 ta), `machine.mac_address/icon_url/serial_number/installed_date`, `employee.passport_id/photo_url/hired_date`, `client.client_type/inn`. `client_type`/`project_generation` VARCHAR + CHECK bo'lgani uchun constraint ustun bilan birga o'chadi; mos Pydantic fieldlar va `ClientType`/`ProjectGeneration` enumlari ham olib tashlangan. Downgrade ustunlarni 1393a241b793 dagi tiplar bilan qaytaradi (NOT NULL'larga server_default qo'shib) |
| 16 | `d5a1c93b70e2` | `d5a1c93b70e2_part_route_seq.py` | **Marshrut qadamlari**: `part_route.seq` va `part_route.process_code` NOT NULL (server_default vaqtincha, backfill'dan keyin olib tashlanadi). Backfill: `seq` — har detal ichida `post.order_index` bo'yicha `row_number()`, `process_code` — post uchun odatdagi kod (`giblab/models.py: DEFAULT_PROCESS_CODE`). Indekslar: yagona `ix_part_route_part_post` DROP → yangi PARTIAL UNIQUE `ix_part_route_part_seq` (`part_id`, `seq`) + yagona **emas** `ix_part_route_part_post` qayta yaratiladi; `ix_scan_instance_route` qo'shiladi (skan hisobi endi post emas, qadam bo'yicha — `scanning._scans_done`) |
| 17 | `e7c4b208af13` | `e7c4b208af13_part_is_custom.py` | `part.is_custom` NOT NULL (server_default `false`, keyin olib tashlanadi) + `ix_part_is_custom`. Nostandart detal fayldan avtomatik marshrut olmaydi — texnolog qo'lda chizadi |
| 18 | `f1b6d0c73a25` | `f1b6d0c73a25_upakovka_post.py` | **QADOQLASH posti** (`UPAKOVKA`, `order_index` 9, unit `m2` — ish haqi kvadratura bo'yicha). Sxema o'zgarmaydi (`post.code` VARCHAR), faqat qator qo'shiladi. Marshrutga anketadagi "Upakovka qilish" bayrog'i qo'shadi |
| 19 | `7e2e0ae9f7f3` | `7e2e0ae9f7f3_pachka_va_pachka_item_jadvallari.py` | **`pachka` va `pachka_item`** jadvallari: qadoq kodi (PARTIAL UNIQUE `ix_pachka_code`), holat, yopilgan/jo'natilgan vaqt; tarkib — bitta nusxa faqat bitta qadoqda (PARTIAL UNIQUE `ix_pachka_item_instance`) |
| 20 | `a3f8d61c9b04` | `a3f8d61c9b04_ombor_post.py` | **TMO posti** (`order_index` 10, unit `piece`; `f2a08c47b6d1` da `OMBOR` dan nomlandi) — marshrutning ENG OXIRGI qadami, har detalda. Qadoqsiz buyurtmada omborchi har detalni skanerlab qabul qiladi, qadoqlanganda qadoq QR'i ichidagi hammasini birdan yopadi |
| 21 | `c9d4e2f81a70` | `c9d4e2f81a70_assembly_parent.py` | **Yig'ma buyum**: `part.assembly_parent_id` FK → `part.id` (+ `ix_part_assembly_parent_id`) va `scan.parent_scan_id` FK → `scan.id` (+ `ix_scan_parent_scan_id`). Mayda detal stolyarkada asosiy detalga yopishtiriladi; asosiy detal skani hosila skanlarni yozadi va bekor qilinganda birga qaytaradi (09-mes-domain.md §3.1) |
| 22 | `d5b71c0a9e34` | `d5b71c0a9e34_machine_device_pairing.py` | **Terminal qurilmasini bog'lash** — `machine.pair_code(8)`, `pair_expires_at`, `token_hash(64)`. **BEKOR QILINGAN**: `b83e1f7a25c9` ustunlarni olib tashlaydi. Fayl zanjirda qoladi, chunki u tarqalib bo'lgan — o'chirilsa alembic o'z holatini topa olmasdi ("Can't locate revision") |
| 23 | `f2a08c47b6d1` | `f2a08c47b6d1_ombor_post_tmo_deb_nomlandi.py` | **`OMBOR` → `TMO`** (Tayyor Mahsulot Ombori) — kelishilgan atama. Faqat NOM: `UPDATE post SET code='TMO', name='TMO'`; `post.id` tegilmaydi, marshrut/skan/hisoblagichlar o'z joyida qoladi |
| 24 | `b83e1f7a25c9` | `b83e1f7a25c9_qurilma_boglash_olib_tashlandi.py` | **Qurilma bog'lash olib tashlandi**: `machine` dagi uchta ustun va ikkita indeks `DROP ... IF EXISTS` bilan. Tsexdagi kirish uchun faqat beyjik skani kerak (09-mes-domain.md §3.0.1) |
| 25 | `d1c4e7a90b52` | `d1c4e7a90b52_employee_user_link.py` | **`employee.user_id`** FK + PARTIAL UNIQUE `ix_employee_user_id`; `user-N` beyjiklar `user_id` ga ko'chirilib, `badge_id` `gen_random_uuid()` ga almashtiriladi. Tsexdagi HAR hodimda haqiqiy beyjik bo'lishi uchun (09-mes-domain.md §3.0.1). `employee.id` tegilmaydi — skan va ish haqi tarixi joyida qoladi |
| 26 | `c7e2b4f81d39` | `c7e2b4f81d39_mirror_hodimlar_arxivlandi.py` | **Avtomat mirror hodim yozuvlari arxivlandi**: `user_id IS NOT NULL` bo'lgan hodimlarning ochiq smenalari `ended` ga, hodimlarning o'zi `inactive` ga o'tkaziladi. Yozuvlar O'CHIRILMAYDI — ularda haqiqiy skan tarixi bor, o'chirilsa mahsuldorlik hisoboti buzilardi. Downgrade qaytarmaydi: qaysi biri ilgari nofaol bo'lganini ajratib bo'lmaydi |
| 27 | `b4d1e79c53a8` | `b4d1e79c53a8_materiallar_ombori.py` | **Materiallar ombori katalogi (OLIB TASHLANGAN modul)**: `stock_item` jadvali + PARTIAL UNIQUE `ix_stock_item_code`. Modul kodi olib tashlandi, migratsiya QOLDI — jadval oldidagi izohga qarang |
| 28 | `c9a3e15d84b6` | `c9a3e15d84b6_ombor_harakatlari_sotuv_tolov.py` | **Ombor harakati, sotuv, to'lov (OLIB TASHLANGAN modul)**: `stock_move` / `sale` / `payment` jadvallari — qarz hisobi bilan (2-daraja pul hisobi). Modul kodi olib tashlandi, migratsiya QOLDI |
| 29 | `d2b71f4c86e9` | `d2b71f4c86e9_material_katalogi_olib_tashlandi.py` | **`material` jadvali olib tashlandi** — GibLab katalogi sahifasi bilan birga. Jadvalga birorta FK yo'q edi; material sarfi `Order.material_usage` dan, yorliq/kesish xaritasi `Part.material_name` dan hisoblanadi. Downgrade faqat TUZILMANI tiklaydi (mazmun `.project` qayta yuklanganda o'zi paydo bo'lardi) |
| 30 | `a7c40e29b168` | `a7c40e29b168_tmo_ish_markazi_nomi.py` | TMO ish markazi **`01 OMBOR` → `01 TMO`** — yolg'iz "Ombor" atamasi ishlatilmaydi (09-mes-domain.md §1.1). Faqat NOM: `machine.id` tegilmaydi |
| 31 | `e5b83c04d7a1` | `e5b83c04d7a1_audit_modul_nomlarini_birlashtirish.py` | **Audit modul nomlari birlashtirildi**: `audit_log.module` da `ombor` → `tmo` (174 qator) va `materials` → `stock`. Modul qayta nomlanganda eski qiymat qolib ketgan edi — loglar sahifasidagi filtr eski yozuvlarni umuman ko'rsatmasdi. Faqat TASNIF: `message`/`action`/`meta` tegilmaydi. Downgrade to'liq emas (`materials` dagi `updated` qatorlari ajratilmaydi) |
| 32 | `b1f27ce03d94` | `b1f27ce03d94_machine_ip_address_olib_tashlandi.py` | **`machine.ip_address` DROP** — o'lik ustun: birorta so'rov, biznes-logika yoki hisobot murojaat qilmasdi, 9 qatorning hammasida NULL edi. Ish markazi bilan aloqa `user.machine_id` va `bridge_agent.machine_id` orqali, tarmoq manzili orqali emas. Downgrade faqat TUZILMANI qaytaradi (qiymat bo'lmagan) |
| 33 | `c3d97a1e5b02` | `c3d97a1e5b02_oval_bitta_skan.py` | **OVAL da detal BITTA marta skanlanadi**: mavjud marshrutlarda `per_instance=1`, `total_required=part.count`, `total_done` chegaraga tushiriladi. Kod OVAL ni KROMKA bilan bir qatorga qo'ygan edi (qirralar soni marta skan) — egasi xato ekanini tasdiqladi; kodning o'z izohlari ham "bitta skan" deb turgandi |
| 34 | `a9e14b7c2d63` | `a9e14b7c2d63_mirror_hodimlar_ochirildi.py` | **Mirror hodim yozuvlari HARD DELETE**: 8 hodim, 410 smena, 120 skan; audit yozuvlari saqlanadi (`employee_id` NULL). Skanlar ketgani uchun ta'sirlangan 40 `part_route` ning `total_done` i qolgan skanlar bo'yicha qayta sanaladi. Qaytarilmaydi |
| 35 | `d8f31a05c7e2` | `d8f31a05c7e2_ish_markazi_nomi_unikal.py` | **Ish markazi nomi UNIKAL** — PARTIAL UNIQUE `ix_machine_name`. Ilgari bitta postga ikkita "01 ARRA" qo'shsa bo'lardi: monoblokda operator FAQAT nomni ko'radi, ya'ni qaysi stanokda turganini ajrata olmasdi. Mavjud dublikatlar avval " (2)" bilan ajratiladi |
| 36 | `e7a35c19d840` | `e7a35c19d840_user_is_system.py` | **`user.is_system`** — texnik hisobni odamnikidan ajratadi. Mavjud post rolidagi hisoblarning HAMMASI texnik deb belgilanadi (`WHERE role IN (...)`) — nom/telefon shabloniga qaralmaydi: shaxsiy hisob tushunchasi aynan shu migratsiyadan keyin paydo bo'ladi, ya'ni undan oldingi har bir post hisobi seed yoki sinov qoldig'i; shablonga tayanish esa eski seed boshqacha yaratgan hisoblarni belgilanmay qoldirardi. Shundan keyin post rolidagi SHAXSIY hisob parol bilan kira oladi — skaneri yo'q postda (ARRA) yagona yo'l |
| 37 | `f3fad5351d8a` | `f3fad5351d8a_oee_toxtalishlar_va_ideal_tezlik.py` | **OEE (OLIB TASHLANGAN modul)**: `stop_reason`, `machine_stop` jadvallari va `machine.planned_minutes_per_day`/`machine.ideal_rate` ustunlari. Modul kodi olib tashlandi, migratsiya QOLDI — jadval oldidagi izohga qarang |
| 38 | `b2c7e40f9a13` | `b2c7e40f9a13_part_instance_cut_meters.py` | **OEE (OLIB TASHLANGAN modul)**: `part_instance.cut_meters` — kesim uzunligi, mavjud buyurtmalar migratsiyada to'ldirilgan |
| 39 | `10a4a7945eac` | `10a4a7945eac_brak_defect_jadvali.py` | **OEE (OLIB TASHLANGAN modul)**: `defect` jadvali (brak) |
| 40 | `a1c9d4f2b60e` | `a1c9d4f2b60e_brak_jadvali_olib_tashlandi.py` | **`defect` jadvali DROP** — modul umuman ishlatilmaydi, prodda 0 qator, yetim jadval sxemani chalg'itardi. `10a4a7945eac` o'chirilmaydi (prodda qo'llanib bo'lingan), o'rniga shu migratsiya tushiradi; `downgrade` jadvalni to'liq tiklaydi |
| 41 | `c5e81b3a97d2` | `c5e81b3a97d2_chek_qaysi_postda_chiqarilgani.py` | **`part_instance.label_post_id`** — chekni qaysi post chiqargani (FK `post`) |
| 42 | `a7c419e0b3d5` | `a7c419e0b3d5_paz_freza_detaliga_prisadka_qadami.py` | **Paz/freza bor detalga PRISADKA qadami** — mavjud buyurtmalarga ham qo'llanadi. Ilgari faqat TESHIK hisobga olinardi va paz/freza-only detal marshrutsiz qolardi |
| 43 | `b8e4a71c92d5` | `b8e4a71c92d5_project_name_fayl_nomidan.py` | **`order.project_name` backfill** — bo'sh qolganlari `order_file` dagi `.project` yo'lining fayl nomidan to'ldiriladi. Sabab: nom ilgari fayl ichidagi `<root name=...>` dan olinardi, GibLab eksportlarining bir qismida esa u yo'q |
| 44 | `af6809b43a73` | `af6809b43a73_waste_item_foydali_atxot_jadvali.py` | **`waste_item` jadvali** — foydali atxot (GibLab `business="true"`): `order_id`, `material_name`, `sheet_no`, `length`/`width`, `qr_text` (PARTIAL UNIQUE `ix_waste_item_qr_text`), `label_printed_at`. GibSaw'dagi «Деловой остаток» chekining muqobili; ombor moduli keyin shu jadval ustiga quriladi |
| 45 | `e5b73c04a19f` | `e5b73c04a19f_user_name_100_belgi.py` | **`user.name` VARCHAR(30) → VARCHAR(100)** — `UserCreate`/`UserUpdate` allaqachon 100 belgigacha qabul qilardi (`_NAME_FIELD`, 2.1-bo'lim), ya'ni 31–100 belgili F.I.Sh validatsiyadan o'tib INSERT da yiqilardi; `employee.full_name` bilan tenglashtirildi. Downgrade avval `left(name, 30)` bilan qisqartiradi |
| 46 | `6a5051b7b420` | `6a5051b7b420_drop_redundant_indexes_and_updated_at_.py` | **Ortiqcha indekslar + `updated_at` defaulti** — 19 ta `ix_*_is_deleted` (jonli jadvallar; yetimlar tegilmagan), `ix_pachka_order_status`, `ix_pachka_status` o'chirildi; 19 jadvalda `updated_at` `DROP DEFAULT` + to'ldirish (`updated_at - created_at < 1 s → NULL`). Eski kod bilan mos — rollback `SKIP_MIGRATIONS=1` bilan xavfsiz; downgrade hammasini qaytaradi (NULL → `created_at`). Scratch Postgres'da upgrade/check/downgrade/upgrade sinalgan |
| 47 | `1cfd3b2182fc` | `1cfd3b2182fc_prisadka_one_scan_per_instance.py` | **PRISADKA — bitta skan** (ma'lumot migratsiyasi): ikki yuzli detal (old + orqa `_2` XNC) qadamida `per_instance=2` edi — prisadkachi bitta detalni «0/2» deb ko'rar, bir QR'ni ikki marta skanlardi; SCX ikkala yuzni bitta faylga birlashtirgani uchun skan bitta. `per_instance>1` bo'lgan PRISADKA qadamlari → `per_instance=1, total_required=part.count` (prodda 29 ta; `total_done` tegilmaydi — bir marta skanlangan nusxa tugagan hisoblanadi). Downgrade `xnc_summary.sides=2` bo'yicha qaytaradi. Scratch'da upgrade/check/downgrade sinalgan |

Anketa **xona rasmlari** uchun migratsiya yo'q: mavjud `order_file` jadvali `kind=DOCUMENT` + `meta` JSONB bilan ishlatiladi (1.4.1-bo'lim).

Eslatma: `1393a241b793` dagi `user.role` enum'i 6 qiymat bilan yaratilgan; keyinchalik 9 operator roli faqat Python enum'ga qo'shildi — ustun VARCHAR bo'lgani uchun (`db_enum`, `native_enum=False`) DB migratsiyasi kerak bo'lmadi.

Prestart ketma-ketligi (`scripts/prestart.sh`: `alembic upgrade head` → `create_first_superuser` → `seed_defaults`) endi **toza bazada** ham to'liq o'tadi — default `organization` qatori `1393a241b793` da tug'ilgani uchun keyingi post migratsiyalarining `organization_id = 1` FK'si buzilmaydi. Toza bazadagi natija: 1 tashkilot, 9 post, 1 admin va 9 ta `is_system` post hisobi (`_seed_post_accounts`, 5.2-bo'lim).

---

## 5. Commands — `backend/app/commands/`

### 5.1 `backend/app/commands/create_first_superuser.py`

Idempotent bootstrap skript — birinchi admin foydalanuvchini yaratadi (`python -m app.commands.create_first_superuser` yoki deploy scriptidan chaqiriladi):

- Ma'lumotlar `settings` dan: `ADMIN_NAME`, `ADMIN_PHONE`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (`backend/app/core/config.py`).
- **Tirik** (`is_deleted=False`) qatorlar orasidan TELEFON YOKI USERNAME bo'yicha tekshiradi (`or_(User.phone == phone, User.username == username)`, `scalars().first()`) — soft-o'chirilgan eski admin qatori yangi seed'ni bloklamaydi, `ADMIN_PHONE` rotatsiyasida esa eski `admin` username'i `ix_user_username` ni buzmaydi: mavjud bo'lsa hech narsa qilmaydi (log: "already exists"), bo'lmasa `is_active=True, is_superuser=True` bilan yaratadi (`role` server default bo'yicha `admin`).
- Session `app.core.db.local_session` dan olinadi; parol `await get_password_hash(...)` bilan xeshlanadi (funksiya async).
- E'tibor: `crud_users.create` emas, to'g'ridan-to'g'ri `User(...)` konstruktor ishlatadi (schema-validatsiyasiz bootstrap yo'li).

### 5.2 `backend/app/commands/seed_defaults.py`

Idempotent bootstrap — default tashkilot va 9 ishlab chiqarish postini ta'minlaydi (`python -m app.commands.seed_defaults`, prestart/setup scriptlardan chaqiriladi):

- Tashkilot: `select(Organization).limit(1)` — DB'da **birorta ham** tashkilot bo'lmasa `Organization(name="Mebelix")` yaratadi. Kod o'zgarmagan, lekin bu shox endi **hech qachon ishlamaydi**: org qatorini `1393a241b793` migratsiyasi qo'yadi (4.4-bo'lim), seed uni faqat topib qoldiradi.
- Postlar: mavjud `code` lar to'plami bilan solishtirib, yetishmaganlarini `POSTS` ro'yxatidan qo'shadi — 9 post (`ARRA`…`BOYOQ` + `UPAKOVKA` + `TMO`, `OVAL` 3-o'rinda) `order_index` 1–10, `unit` (m2/meter/piece; `UPAKOVKA` — `m2`, ish haqi qadoqlangan kvadratura bo'yicha, `TMO` — `piece`); faqat `ROVER` — `requires_assignment_choice=True`; BOYOQ'da ish markazi tanlash shart emas — bo'yoq kamerasi bitta. **`order_index` 5 ataylab bo'sh** — olib tashlangan `PAZ` o'rni: tartib faqat nisbiy ishlatiladi, qayta raqamlash esa mavjud bazalarda bekorga siljish beradi. Mavjud postning `order_index` i ro'yxatdan farq qilsa sinxronlanadi (yangi post qo'shilganda tartib siljiydi).

**Post hisoblari** (`_seed_post_accounts`) — har post uchun BITTA texnik hisob (`arrachi`,
`kromkachi`, … `omborchi`), idempotent; mavjudi nofaol bo'lsa qayta faollashtiriladi.
Nega kerak: beyjik bilan kirishda smena kimningdir hisobi nomidan ochiladi
(`login._terminal_user` — avval ish markazining TERMINAL hisobi, bo'lmasa post roli).
Ikkalasi ham bo'lmasa post BUTUNLAY ishlamaydi va operator 401 oladi. Aynan shu holat
BOYOQ postida bor edi: `boyoqchi` hisobi hech qachon yaratilmagan. Parol tasodifiy
(`secrets.token_urlsafe`) va hech kimga aytilmaydi — `login.py` aynan `is_system`
bayrog'iga qarab kirishni 401 bilan rad etadi, ya'ni parol faqat NOT NULL ustunni
to'ldiradi. Cheklov ROLGA emas, hisob TURIGA: post rolidagi SHAXSIY hisob
(`is_system=False`) parol bilan bemalol kiradi va smenasi shu zahoti ochiladi
(1.2-bo'lim). Telefon `+998000000001…09` ajratilgan diapazondan (`+9980000000` +
ikki xonali raqam = 13 belgi, `user.phone` dagi `String(13)` ga aynan mos;
ustunda UNIQUE indeks bor). Raqam `POST_ROLES` tartibidan OLINMAYDI: seed
diapazondagi birinchi bo'sh raqamni beradi va u rolga biriktirilib qoladi —
aks holda ro'yxat o'rtasiga yangi rol qo'shilganda indeks siljib, mavjud
hisobning raqami bilan to'qnashardi (UNIQUE buzilib prestart yiqilardi).

`backend/app/commands/__init__.py` — bo'sh (faqat package marker).

---

## 6. Tasks — ARQ background workers

`backend/app/tasks/__init__.py` — package bitta fayldan iborat, to'rtta registered task:

| Task | Vazifasi |
|---|---|
| `print_label(ctx, instance_id, agent_id=None)` | Bitta fizik nusxa uchun yorliq PNG'ini render qilib chop etish navbatiga qo'yadi |
| `print_pachka_label(ctx, pachka_id, agent_id=None)` | Qadoq chekini (`render_pachka_label_png` — qadoq kodi + buyurtma raqami + proyekt nomi + ichidagi detallar soni) shu navbatga qo'yadi — detal yorlig'i bilan bir xil zanjir |
| `print_waste_label(ctx, waste_id, agent_id=None)` | Foydali atxot chekini (`WasteLabelData` → `render_waste_label_png` — `ATX-...` QR + buyurtma raqami + proyekt nomi + material va foydali o'lcham) shu navbatga qo'yadi; chaqiruvchi — `POST /terminal/waste/{waste_id}/label` (ARRA kesish xaritasi sahifasi). `label_printed_at` ni ENDPOINT yozadi, task emas — aks holda javob bilan yozuv orasida poyga bo'lardi va terminal katagi darhol yangilanmasdi |
| `print_badge(ctx, employee_id, agent_id=None)` | Hodim beyjigini (`render_badge_png` — lavozim + ism + QR, 80×60 mm) shu navbatga qo'yadi. Beyjik brauzerdan chop etilmaydi: agent DEVMODE bilan qog'ozni majburlaydi, drayver sozlamasi ahamiyatsiz |

`print_label` oqimi:

1. `app.services.labels.load_label_data(db, instance_id)` — nusxa/detal/buyurtma ma'lumoti va cutmap teshiklari yig'iladi; topilmasa `skip:{instance_id}`.
2. `render_label_png(data)` → `base64` (`png_b64`). Yagona format — PNG: GoDEX G500-U faqat USB, agent rasmni Windows drayveri (GDI) orqali chizadi, printer dialekti kerak emas.
3. ARQ worker kontekstidagi Redis'ga `LPUSH`: `print_queue_key(agent_id)` ro'yxatiga (`mes:print:queue:{agent_id}`, manzilsiz bo'lsa `mes:print:queue`) JSON job `{"type": "print", "job_id", "instance_id", "png"}` → `queued:{instance_id}`.
4. Worker kontekstida Redis bo'lmasa — `logger.error` + `lost:{instance_id}`.

To'liq zanjir:

```
Terminal "Chop etish"
  -> POST /api/v1/terminal/labels/{instance_id}   (label_printed_at + ws "label.printed")
  -> arq print_label: render_label_png -> LPUSH mes:print:queue:{agent_id}
  -> /ws/bridge (per-agent token -> bridge_agent.token_hash): brpop -> agentga yuboradi, ack kutadi
  -> bridge-agent: print-queue.jsonl (durable) -> Windows GDI -> USB GoDEX
```

`/ws/bridge` (`backend/app/api/routes/ws.py`) jobni ack (`{"ok": true}`) kelmasa `rpush` bilan navbatga qaytaradi — yorliq yo'qolmaydi. Auth **per-agent**: token `Authorization: Bearer` headerda keladi (query param eski agentlar uchun fallback), sha256 xeshi bo'yicha tirik `bridge_agent` qatori qidiriladi — topilmasa 4401 (`WS_CLOSE_UNAUTHORIZED` konstantasi). Serverda sozlama kerak emas, printer admin paneldan ulanadi (1.4.2-bo'lim). `settings.BRIDGE_TOKEN` faqat **legacy** back-compat sifatida qoldi: bo'sh bo'lsa e'tiborga olinmaydi, to'ldirilgan bo'lsa eski umumiy tokenli agent ham o'tadi (bunday ulanishning jadvalda qatori yo'q — `last_seen_at` yangilanmaydi, panelda ham ko'rinmaydi).

Bridge-agent (`bridge-agent/agent.py`) faqat printer ulangan kompyuterga o'rnatiladi — menejer, texnolog va boshqa post terminallariga hech narsa kerak emas. Birinchi ishga tushganda `_pair()` sozlash oynasini ochadi (`_pair_dialog()` — tkinter, server manzili + ulanish kodi; tkinter bo'lmasa `_pair_console()` zaxirasi), `_exchange()` kodni tokenga almashtiradi va `%APPDATA%\MebelixAgent\.env` ga yozadi — token allaqachon bo'lsa oyna umuman ochilmaydi. Ulangandan keyin `_register_autostart()` agentni `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` ga yozadi, exe esa `--noconsole` bilan qurilgan — kompyuter yonganda oynasiz fonda o'zi tushadi. Exe qo'lda tarqatiladi (server download endpointi yo'q). Printerni `_detect_printer()` avtomatik topadi (nomida `godex` bor Windows printeri); env'lari: `MES_URL`, `BRIDGE_TOKEN` (pairing to'ldiradi), `PRINTER_NAME` (ixtiyoriy, qo'lda override), `QUEUE_FILE`, `SCAN_FORWARD` (default yoqilgan; `0` — klaviatura-skaner forvardini o'chiradi). Pairing `.env` ni qayta yozganda faqat `MES_URL`/`BRIDGE_TOKEN` yangilanadi — qo'lda yozilgan qolgan kalitlar saqlanadi.

```python
all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]
```

Worker konfiguratsiyasi (ARQ `WorkerSettings`) ro'yxatni `all_tasks` dan oladi; yangi task qo'shilganda shu ro'yxatga kiritilishi kerak. ARQ konvensiyasi: birinchi argument worker context (`ctx`).

---

## 7. Qatlamlararo bog'lanish xulosasi

| Qatlam | Fayllar | Kimga tayanadi | Kim ishlatadi |
|---|---|---|---|
| Models | `backend/app/models/*` | `app.core.db.Base` | CRUD, Alembic autogenerate, commands, services |
| Schemas | `backend/app/schemas/*` | Pydantic, `app.models.enums` | API routes (request/response), CRUD (create/update input) |
| CRUD | `backend/app/crud/*` | Models, Schemas, `app.core.security` | API routes (7 singleton + `log_action`) |
| Migrations | `backend/app/migrations/*`, `backend/alembic.ini` | `app.core.config.settings`, `Base.metadata` | deploy/`alembic upgrade head` |
| Commands | `backend/app/commands/*` | settings, `local_session`, Models | bootstrap (superuser, organization + postlar) |
| Tasks | `backend/app/tasks/*` | ARQ, `app.services.labels`, Redis | worker process |

Naqshlar: **soft delete hamma joyda default** (BaseCRUD avtomatik filtr), **partial unique indekslar** tirik qatorlar orasida (jami 12 ta: `user.username`, `user.phone`, `order.number`, `employee.badge_id`, `employee.user_id`, `machine.name`, `post.code`, `part_instance`, `part_route`, `pachka.code`, `pachka_item.instance_id`, `waste_item.qr_text`), **VARCHAR-backed enumlar** (`db_enum`, migratsiyasiz yangi a'zo), **JSONB** moslashuvchan maydonlar uchun (cutmap, edges, machine_assignments, assigned_post_ids, survey, order_file.meta — anketa rasmlari jadvalsiz shu orqali bog'lanadi), **token_version** bilan JWT mass-invalidation, **E.164 telefon** username bilan teng huquqli login identifikatori, **MappedAsDataclass** ORM uslubi, **singleton CRUD instancelar**, **partial update** (`exclude_unset=True`), **idempotentlik** (`scan.client_event_id`, seed skriptlar).
