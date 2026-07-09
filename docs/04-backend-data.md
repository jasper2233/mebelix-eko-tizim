# Backend Data Layer — Models, Schemas, CRUD, Migrations, Tasks

Bu hujjat MebeliX MES backend'ining ma'lumotlar qatlamini qamrab oladi: SQLAlchemy ORM modellari, Pydantic schemalari, generic CRUD qatlami, Alembic migratsiyalari, CLI komandalar va ARQ background tasklari. Qatlam to'liq **async** (SQLAlchemy `AsyncSession`, asyncpg driver) va aniq qatlamlararo yo'nalishga ega:

```
API routes  →  schemas (validation)  →  crud (biznes DB-operatsiyalar)  →  models (ORM)  →  PostgreSQL
```

Hozircha domen modeli minimal: faqat `User` (shablondan qolgan demo `Item` moduli to'liq olib tashlangan). MES-ga xos jadvallar hali qo'shilmagan — bu qatlam kelajakdagi entitylar uchun tayyor skelet vazifasini bajaradi.

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

### 1.2 `backend/app/models/user.py` — User modeli

`user` jadvali. Login identifikatori sifatida **username yoki telefon** ishlatiladi; telefon O'zbekiston E.164 formatida kanonik saqlanadi (`+998` + 9 raqam = 13 belgi). `token_version` — barcha chiqarilgan JWT tokenlarni bir zarbda bekor qilish mexanizmi (parol o'zgarganda/logout-all da inkrement qilinadi, `backend/app/crud/users.py` dagi `increment_token_version` ga qarang).

Uniqueness endi ustun darajasida emas (`unique=True`/`index=True` yo'q), balki `__table_args__` dagi **PARTIAL UNIQUE indexlar** orqali:

```python
__table_args__ = (
    Index("ix_user_username", "username", unique=True, postgresql_where=text("NOT is_deleted")),
    Index("ix_user_phone", "phone", unique=True, postgresql_where=text("NOT is_deleted")),
)
```

Ya'ni uniqueness faqat **tirik** (soft-o'chirilmagan) qatorlar orasida amal qiladi — soft-o'chirilgan userning telefon/username'i IntegrityError'siz qayta ro'yxatdan o'tkazilishi mumkin.

Relationlar yo'q (demo `Item` moduli bilan birga `items` relation ham olib tashlangan).

### 1.3 `backend/app/models/item.py` — olib tashlangan (demo)

Shablondan qolgan demo `Item` modeli o'chirildi; `item` jadvali `b7f3a9c41d02` migratsiyasida drop qilinadi (4.5-bo'limga qarang).

### 1.4 `backend/app/models/__init__.py`

Faqat re-export: `from .user import User`. Alembic `env.py` esa modellarni bu faylga tayanmasdan `pkgutil.walk_packages` bilan dinamik import qiladi.

### 1.5 DB jadvallar strukturasi

Manba: modellar + migratsiyalar (`e1c262d7e2ae_init.py` → `b7f3a9c41d02_drop_items_partial_unique_user.py`).

**Jadval: `user`**

| Ustun | Tip | Null | Default | Index/Constraint |
|---|---|---|---|---|
| `id` | `Integer` | NOT NULL | autoincrement | **PK** |
| `name` | `String(30)` | NULL | — | — |
| `username` | `String(20)` | NOT NULL | — | **PARTIAL UNIQUE index** `ix_user_username` (`WHERE NOT is_deleted`) |
| `phone` | `String(13)` | NOT NULL | — | **PARTIAL UNIQUE index** `ix_user_phone` (`WHERE NOT is_deleted`; E.164: `+998XXXXXXXXX`) |
| `hashed_password` | `String` | NOT NULL | — | — |
| `is_active` | `Boolean` | NOT NULL | `True` (Python) | — |
| `is_superuser` | `Boolean` | NOT NULL | `False` (Python) | — |
| `token_version` | `Integer` | NOT NULL | `0` (server_default) | JWT'larni ommaviy bekor qilish uchun |
| `created_at` | `DateTime(tz)` | NOT NULL | `current_timestamp(0)` | — |
| `updated_at` | `DateTime(tz)` | NULL | `current_timestamp(0)`, `onupdate=now(UTC)` | — |
| `deleted_at` | `DateTime(tz)` | NULL | — | — |
| `is_deleted` | `Boolean` | NOT NULL | `False` (Python) | index `ix_user_is_deleted` |

`item` jadvali olib tashlangan (demo); relationlar yo'q.

---

## 2. Schemas — `backend/app/schemas/`

Pydantic v2 schemalari — API request/response validatsiyasi. `backend/app/schemas/__init__.py` bo'sh (re-export yo'q, importlar to'g'ridan-to'g'ri moduldan qilinadi).

### 2.1 `backend/app/schemas/base.py`

`TimestampSchema` — `created_at: datetime`, `updated_at: datetime | None`. Kelajakdagi read-schemalar meros olishi uchun (hozircha ishlatuvchisi yo'q — demo Item schemalari bilan birga foydalanish joyi ham ketdi).

### 2.2 `backend/app/schemas/users.py` — User schemalari

Eng boy schema fayli. Umumiy validatsiya elementlari:

- `PHONE_PATTERN = r"^\+998\d{9}$"` — O'zbekiston E.164 telefon regex'i (model'dagi `String(13)` bilan mos).
- `validate_password_strength(v)` — parol kuchi: 8+ belgi, kichik harf, katta harf, raqam, maxsus belgi. Xato bo'lsa `ValueError`.
- Qayta ishlatiladigan `Field` konstantalar: `_NAME_FIELD` (2–30), `_USERNAME_FIELD` (2–20, `^[a-z0-9]+$`), `_PHONE_FIELD`, `_OPTIONAL_PHONE_FIELD`.

| Schema | Vazifasi | Muhim jihatlar |
|---|---|---|
| `UserRead` | Barcha read javoblar | `from_attributes=True`; `id` — `BeforeValidator(str)` bilan **string** ga aylantiriladi; `hashed_password` chiqarilmaydi |
| `UserCreate` | `POST /users` (faqat superuser) | `password` strength-validatsiya; `is_superuser`/`is_active` flaglar shu yerda (endpoint superuser-only bo'lgani uchun) |
| `UserUpdate` | `PATCH /users/me` (self-update) | Faqat `name`/`username`/`phone`; privilegiya flaglari va parol yo'q |
| `UserAdminUpdate` | `PATCH /users/{user_id}` (superuser) | `UserUpdate` + `password`, `is_active`, `is_superuser` (hammasi optional) |
| `UpdatePassword` | `PATCH /users/me/password` | `current_password` + `new_password` (strength check) |

### 2.3 `backend/app/schemas/auth.py`

- `Token` — `access_token`, `token_type` (login javobi).
- `TokenData` — JWT payload'dan dekodlangan ma'lumot:
  - `user_id: int` — subject endi **immutable PK** (username/phone emas: ular o'zgarishi mumkin, bu tirik sessiyalarni uzib qo'yar va qayta ro'yxatdan o'tishda account confusion'ga yo'l ochar edi);
  - `token_version: int = 0` — User modeli bilan solishtiriladi;
  - `jti: str | None = None` — refresh tokenning unikal id'si (one-time-use enforcement uchun); access tokenlarda `None`.

### 2.4 `backend/app/schemas/items.py` — olib tashlangan (demo)

Demo Item CRUD schemalari (`ItemBase`/`ItemCreate`/`ItemUpdate`/`ItemPublic`/`ItemsPublic`) Item moduli bilan birga o'chirildi.

### 2.5 Kichik schemalar

| Fayl | Schema | Vazifasi |
|---|---|---|
| `backend/app/schemas/common.py` | `Message` | Generic `{"message": str}` javob |
| `backend/app/schemas/health.py` | `HealthCheck`, `ReadyCheck` | Liveness/readiness endpointlari; `ReadyCheck` `database` va `redis` holatini ham qaytaradi |

`backend/app/schemas/job.py` (`Job` — ARQ job javobi) demo task API bilan birga olib tashlangan.

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
| `get_multi` | `(db, offset=0, limit=100, **kwargs) -> (list, int)` | Sahifa + jami count (count subquery orqali, paginatsiyasiz); sahifa `ORDER BY id` bilan — barqaror tartib bo'lmasa Postgres sahifalarda qatorlarni takrorlashi/tushirib qoldirishi mumkin |
| `exists` | `(db, **kwargs) -> bool` | Yozuv borligini tekshirish (count > 0) |
| `delete` | `(db, **kwargs) -> bool` | **Soft delete**: `is_deleted=True`, `deleted_at=now(UTC)`; topilmasa `False` |

Muhim xulq: qidiruvlar default holda o'chirilgan yozuvlarni **ko'rmaydi**; o'chirilganlarni ham olish uchun `is_deleted=True/False` ni explicit berish yoki `exclude_deleted` ni override qilish kerak. Ilgari `get`/`get_multi` da bo'lgan `options` (eager-loading) parametri ishlatilmagani uchun olib tashlandi.

### 3.2 `backend/app/crud/users.py` — `CRUDUser`

`BaseCRUD[User]` + autentifikatsiya logikasi. Modul oxirida singleton: `crud_users = CRUDUser(User)`.

| Metod | Vazifasi |
|---|---|
| `get_by_login(db, identifier)` | Identifier `+` bilan boshlansa `phone`, aks holda `username` bo'yicha qidiradi |
| `create(db, user_create)` | Parolni `await get_password_hash(...)` (`backend/app/core/security.py`) bilan xeshlab yaratadi; caller pre-check qilsa ham, race'da yuzaga keladigan `IntegrityError` tutilib `DuplicateValueException` (409) qaytariladi |
| `update(db, db_user, user_update)` | `UserUpdate` yoki `dict`; `exclude_unset=True` (partial); `password` kelsa avtomatik `hashed_password` ga xeshlanadi (`await`); `IntegrityError` → `DuplicateValueException` (409) |
| `authenticate(db, username_or_phone, password)` | `get_by_login` + `verify_password`; user **topilmasa ham** modul-darajali `_DUMMY_HASH` ustida `verify_password` bajariladi — javob vaqti user mavjudligini oshkor qilmaydi (timing attack himoyasi); muvaffaqiyatsiz urinish `logger.warning` bilan loglanadi; xatoda `None` |
| `increment_token_version(db, user)` | `token_version += 1` — foydalanuvchining barcha access/refresh tokenlarini bekor qiladi |

### 3.3 `backend/app/crud/items.py` — olib tashlangan (demo)

`CRUDItem` / `crud_items` demo Item moduli bilan birga o'chirildi.

### 3.4 `backend/app/crud/__init__.py`

Re-export: faqat `crud_users` (`__all__` da). API routelar odatda `from app.crud import crud_users` deb ishlatadi.

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

### 4.4 `backend/app/migrations/versions/e1c262d7e2ae_init.py`

Birinchi migratsiya — **init** (revision `e1c262d7e2ae`, `down_revision=None`). `user` va (o'sha paytdagi demo) `item` jadvallarini hamda to'liq unique indekslarni yaratadi. `downgrade()` hammasini teskari tartibda o'chiradi. Yakuniy struktura keyingi migratsiya bilan birga o'qilishi kerak (1.5-bo'lim jadvali — ikkalasining natijasi).

### 4.5 `backend/app/migrations/versions/b7f3a9c41d02_drop_items_partial_unique_user.py`

Ikkinchi migratsiya (revision `b7f3a9c41d02`, `down_revision=e1c262d7e2ae`):

- `item` jadvalini (va `ix_item_is_deleted` indeksini) **drop** qiladi — demo modul olib tashlangani uchun.
- `ix_user_username` / `ix_user_phone` to'liq unique indekslarni **partial unique** ga almashtiradi (`postgresql_where=NOT is_deleted`) — soft-o'chirilgan user telefon/username'i qayta ishlatilishi mumkin bo'ladi.
- `downgrade()` indekslarni to'liq unique holiga qaytaradi va `item` jadvalini qayta yaratadi.

---

## 5. Commands — `backend/app/commands/`

### 5.1 `backend/app/commands/create_first_superuser.py`

Idempotent bootstrap skript — birinchi admin foydalanuvchini yaratadi (`python -m app.commands.create_first_superuser` yoki deploy scriptidan chaqiriladi):

- Ma'lumotlar `settings` dan: `ADMIN_NAME`, `ADMIN_PHONE`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (`backend/app/core/config.py`).
- `phone` bo'yicha tekshiradi: mavjud bo'lsa hech narsa qilmaydi (log: "already exists"), bo'lmasa `is_active=True, is_superuser=True` bilan yaratadi.
- Session `app.core.db.local_session` dan olinadi; parol `await get_password_hash(...)` bilan xeshlanadi (funksiya async).
- E'tibor: `crud_users.create` emas, to'g'ridan-to'g'ri `User(...)` konstruktor ishlatadi (schema-validatsiyasiz bootstrap yo'li).

`backend/app/commands/__init__.py` — bo'sh (faqat package marker).

---

## 6. Tasks — ARQ background workers

`backend/app/tasks/sample_tasks.py` (demo `sample_background_task`) olib tashlangan. Hozir package bitta fayldan iborat:

### 6.1 `backend/app/tasks/__init__.py`

```python
async def ping(ctx: dict[str, Any]) -> str:
    """Liveness probe task. ARQ requires at least one registered function; real MES tasks replace this."""
    return "pong"

all_tasks = [ping]
```

`ping` — placeholder: ARQ worker kamida bitta registered funksiya talab qiladi; real MES tasklari qo'shilganda uning o'rnini egallaydi. Worker konfiguratsiyasi (ARQ `WorkerSettings`) ro'yxatni `all_tasks` dan oladi; yangi task qo'shilganda shu ro'yxatga kiritilishi kerak. ARQ konvensiyasi: birinchi argument worker context (`ctx`).

---

## 7. Qatlamlararo bog'lanish xulosasi

| Qatlam | Fayllar | Kimga tayanadi | Kim ishlatadi |
|---|---|---|---|
| Models | `backend/app/models/*` | `app.core.db.Base` | CRUD, Alembic autogenerate, commands |
| Schemas | `backend/app/schemas/*` | Pydantic | API routes (request/response), CRUD (create/update input) |
| CRUD | `backend/app/crud/*` | Models, Schemas, `app.core.security` | API routes (`crud_users` singletoni) |
| Migrations | `backend/app/migrations/*`, `backend/alembic.ini` | `app.core.config.settings`, `Base.metadata` | deploy/`alembic upgrade head` |
| Commands | `backend/app/commands/*` | settings, `local_session`, Models | bootstrap (birinchi superuser) |
| Tasks | `backend/app/tasks/*` | ARQ | worker process |

Naqshlar: **soft delete hamma joyda default** (BaseCRUD avtomatik filtr), **token_version** bilan JWT mass-invalidation, **E.164 telefon** username bilan teng huquqli login identifikatori, **MappedAsDataclass** ORM uslubi, **singleton CRUD instancelar**, **partial update** (`exclude_unset=True`).
