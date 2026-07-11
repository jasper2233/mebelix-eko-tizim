# MebeliX MES — Backend

FastAPI asosidagi MES (ishlab chiqarish boshqaruvi) backend: buyurtmalar hayot sikli, GibLab `.project` parser (CUTMAP/SCX), scan engine, operator terminali, TABLO, hisobotlar, EZPL yorliq chop etish va WebSocket real-time (`/api/v1/*`, jami ~70 endpoint).

Texnologiyalar: Python 3.11+, FastAPI, SQLAlchemy 2 (async) + Alembic, PostgreSQL, Redis (pub/sub + navbatlar), ARQ worker, Pillow/qrcode (yorliq PNG), openpyxl (Excel).

## Talablar

- [uv](https://github.com/astral-sh/uv) (paket menejeri)
- PostgreSQL va Redis (lokal yoki Docker orqali)
- Docker + docker compose (konteynerda ishlatish uchun)

## Setup

Repo ildizidan bir martalik to'liq setup (`.env` nusxalash, `uv sync`, migratsiyalar, superuser, seed, pre-commit):

```bash
make setup
```

Yoki qo'lda, `backend/` ichida:

```bash
uv sync                                            # bog'liqliklarni o'rnatish
cp ../.env.example ../.env                         # so'ng .env ni tahrirlang (SECRET_KEY, POSTGRES_*, ADMIN_*)
uv run alembic upgrade head                        # migratsiyalar
uv run python -m app.commands.create_first_superuser  # birinchi admin (ADMIN_PHONE/ADMIN_PASSWORD dan)
uv run python -m app.commands.seed_defaults        # default tashkilot + 6 post (ARRA..STOLYARKA)
```

## Ishga tushirish

```bash
make run-backend    # lokal: uvicorn app.main:app --reload (http://localhost:8000)
make docker-local   # yoki: db + redis + api konteynerlarda (prestart.sh migratsiya+seed ni o'zi bajaradi)
```

Swagger UI: http://localhost:8000/docs (faqat non-production; `ENVIRONMENT=local` da ochiq, staging da superuser talab qilinadi).

## ARQ worker (yorliq chop etish navbati)

```bash
make worker         # uv --project backend run arq app.core.worker.WorkerSettings
```

## Test, lint, migratsiya

```bash
cd backend && uv run python -m tests.test_giblab   # GibLab parser test to'plami (CI dagi bilan bir xil)
make lint                                          # ruff check + mypy app
make format                                        # ruff format + ruff check --fix
make migrate                                       # alembic upgrade head
make makemigrations m="izoh"                       # alembic revision --autogenerate -m "izoh"
```

Boshqa buyruqlar: `make help`. Infra tafsilotlari: `docs/07-infra-devops.md`, domen qatlami: `docs/09-mes-domain.md`.
