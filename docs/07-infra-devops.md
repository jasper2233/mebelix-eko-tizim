# 07 — Infra & DevOps (Docker, Caddy, Makefile, scripts, chop etish, CI hooks)

Bu hujjat MebeliX MES loyihasining infratuzilma va DevOps qatlamini tavsiflaydi: Docker Compose stacklari (lokal va production), backend/frontend Dockerfile'lar, Caddy reverse proxy, nginx static server, `Makefile` buyruqlari, yordamchi scriptlar, sexdagi chop etish infratuzilmasi (bridge-agent + GoDEX), pre-commit hooklar, CI/CD va environment konfiguratsiyasi.

## Umumiy arxitektura

Stack ikki rejimda ishlaydi:

| Rejim | Compose fayl | Kirish nuqtasi | App server | TLS |
|---|---|---|---|---|
| Lokal (dev) | `docker-compose.local.yml` | portlar to'g'ridan-to'g'ri hostga ochiq (`8000`, `3000`, `5432`, `6379`) | `uvicorn --reload` | yo'q |
| Production | `docker-compose.prod.yml` | faqat Caddy (default `:80`/`:443`; `CADDY_HTTP_BIND`/`CADDY_HTTPS_BIND` bilan o'zgartiriladi); `api`/`frontend` faqat `expose`, `db`/`redis` umuman port ochmaydi | `gunicorn` + `UvicornWorker` | Caddy auto-HTTPS (Let's Encrypt) |

Servislar: `db` (PostgreSQL 15), `redis` (Redis 7, ARQ queue + rate limit), `api` (FastAPI), `worker` (ARQ background worker), `frontend` (Vite build + nginx), production'da qo'shimcha `caddy` (reverse proxy + TLS).

So'rov oqimi (production):

```
Client → Caddy (:80/:443)
           ├── /api*, /docs*, /redoc*, /openapi.json → api:8000 (FastAPI)
           ├── /metrics → api:8000 (faqat private IP'lardan; boshqalarga 403)
           └── boshqa hamma narsa → frontend:80 (nginx, SPA)
```

---

## Lokal development flow

Lokal ishlashning ikki yo'li bor: **to'liq lokal** (uv + npm hostda) va **konteynerlashgan** (`make docker-local`).

### 1-yo'l: to'liq lokal (tavsiya etilgan dev workflow)

```bash
make setup          # bir martalik: .env, deps, migratsiya, superuser, pre-commit
make run-backend    # uvicorn app.main:app --reload  (http://localhost:8000)
make run-frontend   # vite dev server                (http://localhost:5173)
make worker         # ARQ background worker
```

Bu rejimda `POSTGRES_SERVER=localhost` va `REDIS_HOST=localhost` bo'lishi kerak (`.env.example` dagi default). DB/Redis'ni konteynerdan olish mumkin: `docker-compose.local.yml` ular portlarini hostga ochadi (`5432`, `6379`). `frontend/README.md` ham aynan shu workflow'ni tavsiya qiladi — Docker image'ni har o'zgarishda qayta build qilish samarasiz, live reload bilan lokal server yaxshiroq.

### 2-yo'l: konteynerlashgan dev — `docker-compose.local.yml`

`make docker-local` → `docker compose -f docker-compose.local.yml up -d`. Xususiyatlari:

- **`db`** — `postgres:15-alpine`, `postgres_data` named volume, `pg_isready` healthcheck, port `5432:5432` hostga ochiq. Credentiallar defaultli: `${POSTGRES_USER:-postgres}` va h.k.
- **`redis`** — `redis:7-alpine`, `redis_data` volume, `redis-cli ping` healthcheck, port `6379:6379`.
- **`api`** — `backend/Dockerfile` dan build (context = repo root). Command:
  ```
  bash -c "/app/scripts/prestart.sh && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
  ```
  Ya'ni avval migratsiya + superuser + default seedlar (`scripts/prestart.sh`), keyin hot-reload uvicorn. **Bind-mountlar** hot-reload uchun: `./backend/app`, `./scripts`. `.env` esa bind-mount emas, `env_file: .env` orqali yuklanadi — fayl yo'q bo'lsa compose aniq xato beradi (bind-mount holatida Docker jimgina bo'sh katalog yaratardi). `POSTGRES_SERVER=db`, `REDIS_HOST=redis` environment orqali override qilinadi (`.env` dagi `localhost` ni yengadi). Healthcheck: `curl -f http://localhost:8000/api/v1/health`, `start_period: 40s`. `db` va `redis` `service_healthy` bo'lgandan keyingina start oladi.
- **`worker`** — xuddi shu image, command: `arq app.core.worker.WorkerSettings`, xuddi shu mountlar va env.
- **`frontend`** — `frontend/Dockerfile` dan build, build-arglar: `VITE_API_URL` (default `http://localhost:8000` — brauzer API'ga to'g'ridan-to'g'ri boradi) va `VITE_API_TIMEOUT_MS` (default `30000`), port `3000:80`.

Lokal composeda Caddy yo'q — frontend nginx'i to'g'ridan-to'g'ri `3000` portda, API `8000` da.

### Kundalik dev buyruqlari (`Makefile`)

`Makefile` (root) `PYTHONPATH := backend` ni export qiladi va `uv --project backend` orqali backend virtualenv'idan foydalanadi. `make help` — barcha targetlar ro'yxati (`##` izohlaridan avtogeneratsiya).

| Target | Vazifasi |
|---|---|
| `setup` | `scripts/setup.sh` + `install-hooks` |
| `install` / `frontend-install` | `uv sync` / `npm install` |
| `run-backend` / `run-frontend` / `worker` | dev serverlar va ARQ worker |
| `lint` / `format` | `ruff check` + `mypy app` / `ruff format` + `ruff check --fix` |
| `frontend-lint` / `frontend-build` | `npm run lint` (biome) / `npm run build` |
| `frontend-gen` | `scripts/generate-client.sh` — OpenAPI → TS client |
| `migrate` / `makemigrations m="msg"` | `alembic upgrade head` / `alembic revision --autogenerate` |
| `cmd n="name"` | `python -m app.commands.<name>` — custom CLI commandlar |
| `docker-local` / `docker-prod` / `docker-down` / `docker-logs` | compose lifecycle (`docker-prod` endi `pull` + `up -d` — prod image'lar CI'da quriladi, serverda build yo'q) |
| `clean` | `__pycache__`, `.mypy_cache`, `.ruff_cache` tozalash |

---

## Production flow

### `docker-compose.prod.yml`

Lokaldan asosiy farqlar:

- **Hech qanday servis DB/Redis/API portini hostga ochmaydi** — `api` va `frontend` faqat `expose` qiladi; tashqi dunyoga faqat `caddy` port ochadi, host binding parametrlangan: `${CADDY_HTTP_BIND:-80}:80` va `${CADDY_HTTPS_BIND:-443}:443` (default — to'g'ridan-to'g'ri `80`/`443`).
- **Prod composeda `build:` bo'limlari yo'q — image'lar tayyor holda registrydan olinadi.** `${REGISTRY:-ghcr.io/dshukriddinov}/mebelix-mes-backend:${TAG:-latest}` (`api` va `worker` bittasini bo'lishadi) va `${REGISTRY:-ghcr.io/dshukriddinov}/mebelix-mes-frontend:${TAG:-latest}`. CI ikkala qiymatni ham beradi — `REGISTRY=ghcr.io/<owner>` va `TAG=<git sha>` (git sha rollback uchun, pastda `scripts/deploy.sh`); defaultlar lokal qo'lda ishga tushirishga. Image'larni GitHub Actions quradi va ghcr.io ga yuboradi (`images` job, pastda CI bo'limi), server faqat `pull` qiladi. Lokal build `docker-compose.local.yml` da qoladi — u o'z `build:` bo'limlarini saqlab qolgan.
- **`api`** production serverda ishlaydi:
  ```
  bash -c "/app/scripts/prestart.sh && gunicorn app.main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --forwarded-allow-ips '*'"
  ```
  `--forwarded-allow-ips` flag sifatida beriladi, chunki gunicorn `FORWARDED_ALLOW_IPS` env'ini ham o'qiydi va pydantic'ning JSON list formati (`'["*"]'`) uni yiqitadi. `env_file: .env` orqali to'liq konfiguratsiya, `POSTGRES_SERVER=db` / `REDIS_HOST=redis` override. `restart: always`. Healthcheck: `curl -f http://localhost:8000/api/v1/health` (`start_period: 40s`) — `caddy` shu healthcheck'ka tayanadi.
- **`db` / `redis`** credentiallari defaultsiz — `.env` da majburiy (`${POSTGRES_USER}` va h.k.).
- **`frontend`** `VITE_API_URL=""` (bo'sh string) bilan build qilinadi — generatsiyalangan SDK yo'llari allaqachon `/api/v1` bilan boshlanadi, shuning uchun bo'sh base same-origin so'rovlar beradi va ularni Caddy backendga proxy qiladi (avvalgi `/api` qiymati so'rovlarni `/api/api/v1` ga aylantirib 404 berardi). `VITE_*` build-arglar (`VITE_API_URL=` va `VITE_API_TIMEOUT_MS=30000`) endi compose faylida emas, CI'ning `images` job'ida beriladi — prod uchun ular belgilanadigan yagona joy. Healthcheck `wget --spider http://127.0.0.1/` ga qadalgan — konteyner ichida `localhost` `::1` ga ketadi, nginx esa faqat IPv4 tinglaydi.
- **`caddy`** — `caddy:2-alpine`, `./caddy/Caddyfile` read-only mount, `caddy_data` (TLS sertifikatlar) va `caddy_config` volumelari. `SITE_ADDRESS` env (default `:80`). `depends_on`: `api` `service_healthy`, `frontend` `service_started` — Caddy backend tayyor bo'lgandan keyingina start oladi. Healthcheck `http://localhost:8080/healthz` orqali — Caddyfile'dagi alohida `:8080` health blokiga (asosiy `:80` emas, chunki `SITE_ADDRESS` domen bo'lganda `:80` HTTPS'ga avto-redirect qiladi).

Ishga tushirish: `.env` ni production qiymatlar bilan to'ldirish (ayniqsa `SECRET_KEY`, `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SITE_ADDRESS`, `ENVIRONMENT=production`), so'ng `make docker-prod`. Image'lar ghcr.io dan tortilgani uchun (paketlar private) server oldindan `docker login ghcr.io` qilgan bo'lishi kerak — CI buni deploy oldidan avtomatik bajaradi.

**Mavjud nginx ortida (ISPmanager) ishga tushirish.** Hostda `80`/`443` allaqachon band bo'lsa, Caddy'ni loopback'ka bog'lab TLS'ni host nginx'iga qoldirish mumkin — `.env` ga:

```
CADDY_HTTP_BIND=127.0.0.1:8200
CADDY_HTTPS_BIND=127.0.0.1:8443
SITE_ADDRESS=:80
```

Bunda Caddy oddiy HTTP'da qoladi (sertifikatni nginx tugatadi), host nginx esa saytni `127.0.0.1:8200` ga proxy qiladi. Shu retsept `docker-compose.prod.yml` dagi `ports` izohida ham yozilgan.

### Disk gigiyenasi — nima o'sadi va nima cheklangan

Serverda cheksiz o'sishi mumkin bo'lgan uch narsa bor edi; hammasi yopilgan:

| Nima | Holat |
|---|---|
| Docker **build keshi** | Endi umuman paydo bo'lmaydi: server build qilmaydi, `deploy.sh` faqat `pull` qiladi. Ghcr o'tishidan oldin 11.6 GB yig'ilgan edi — bir marta tozalandi (`docker builder prune -af`). |
| Konteyner **loglari** | `docker-compose.prod.yml` dagi `x-logging` anchor: `json-file`, `max-size 20m` × `max-file 3` — har xizmatga maksimum 60 MB. Sozlama **repoda**, serverdagi `/etc/docker/daemon.json` da emas: yangi o'rnatishda o'zi qo'llanadi va yagona manba bo'lib qoladi. |
| **journald** | `/etc/systemd/journald.conf.d/99-mebelix.conf`: `SystemMaxUse=300M`, `MaxRetentionSec=1month`. Default cheklov diskning 10% i (bu serverda ~4.8 GB) — 3 GB gacha o'sgan edi. |

Image'lar tomonida: `deploy.sh` har muvaffaqiyatli deploydan keyin eskilarini o'chiradi (joriy + oldingi stable qoladi), CI esa ghcr'da oxirgi 10 versiyani saqlab qolganini tozalaydi (`actions/delete-package-versions`) — har deploy registrga ~620 MB qo'yadi va private repo paket xotirasi cheklangan.

Backuplar `/var/backups/mebelix` da (deploy daraxtidan tashqarida), `BACKUP_KEEP_DAYS` bo'yicha 14 kun.

### Yuklangan fayllar (`UPLOAD_DIR`) va `uploads_data` volume

Backend yuklangan fayllarni diskka yozadi (`backend/app/core/config.py`: `UPLOAD_DIR: str = "uploads"` — **nisbiy** yo'l, image ichidagi CWD `/app/backend` dan hisoblanadi, ya'ni `/app/backend/uploads`). Katalog tarkibi:

| Kichik katalog | Nima | Yozuvchi |
|---|---|---|
| `projects/` | yuklangan GibLab `.project` fayllari | `upload_order_project` |
| `scx/` | SCX/CNC fayllari | orders route'lari |
| `survey/{order_id}/` | anketa xona rasmlari, nomi `{uuid4().hex}{ext}` | `upload_room_photo` (`POST /orders/{id}/survey/photos`) |
| `agent/mebelix-agent.exe` | printer agentining Windows build'i | qo'lda qo'yiladi (deploy emas); `download_bridge_agent` tarqatadi |

DB'da faqat nisbiy yo'l saqlanadi (`OrderFile.path`), o'qishda `Path(settings.UPLOAD_DIR).resolve() / row.path` bilan qayta yig'iladi.

**Prod'da doimiylik:** `docker-compose.prod.yml` da `api` xizmati `uploads_data` named volume'ini `/app/backend/uploads` ga mount qiladi. Volume bo'lmaganda fayllar konteyner qatlamida qolar va **har deploy'da (yangi image + konteyner almashishi) yo'qolar edi** — DB'dagi `OrderFile` yozuvlari qolib, fayl yo'q bo'lardi (`download_order_file` "Fayl diskda topilmadi" beradi). `worker` ga mount berilmagan: arq tasklari (`print_label`) faylga tegmaydi, yorliq DB ma'lumotidan chiziladi — `UPLOAD_DIR` ni faqat `api` route'lari o'qiydi.

`docker-compose.local.yml` faqat `./backend/app` va `./scripts` ni mount qiladi — lokal ishda fayllar repo ichidagi `backend/uploads/` ga tushadi (`.gitignore` da). CI `rsync` ham `uploads` ni exclude qiladi, ya'ni deploy serverdagi fayllarga tegmaydi.

### `caddy/Caddyfile` — reverse proxy va TLS

Site bloki `{$SITE_ADDRESS::80}` — env-driven listener:

- `:80` (default) → oddiy HTTP (boshqa proxy ortida yoki lokal sinov uchun);
- `your-domain.com` → Caddy **avtomatik Let's Encrypt sertifikat** oladi va `:443` da tinglaydi;
- `your-domain.com:8443` → custom port, TLS baribir provision qilinadi.

Blok ichida: security headerlar (`X-Frame-Options SAMEORIGIN`, `X-Content-Type-Options nosniff`, `X-XSS-Protection`), `encode gzip`, so'ng routing:

| Handle | Upstream | Izoh |
|---|---|---|
| `/api*` | `api:8000` | `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` headerlar bilan |
| `/docs*`, `/redoc*`, `/openapi.json` | `api:8000` | API hujjatlari |
| `/metrics` | `api:8000` yoki `403` | Prometheus — `remote_ip private_ranges` matcher: faqat private tarmoq IP'laridan proxy qilinadi, boshqa hammaga `403 Forbidden` |
| qolgani (`handle {}`) | `frontend:80` | SPA, forwarded headerlar bilan |

Asosiy site blokidan tashqari alohida **`:8080` bloki** bor — `respond /healthz "OK" 200`. Bu Docker healthcheck uchun doimiy plain-HTTP endpoint: `SITE_ADDRESS` domenga o'tib asosiy blok TLS'ga ko'chganda ham ishlayveradi.

Backend `X-Forwarded-*` headerlariga ishonishi ikki qatlamli: app-level `ProxyHeadersMiddleware` haliyam `.env` dagi `FORWARDED_ALLOW_IPS` dan oladi, lekin prod'da gunicorn darajasi `--forwarded-allow-ips '*'` flagi bilan qattiq belgilangan (yuqoridagi `api` command).

### `frontend/nginx/index.conf` — konteyner ichidagi static server

Frontend konteyneri ichida nginx `:80` da:

- gzip (`text/*`, `application/json`, `application/javascript` va h.k., `gzip_min_length 1024`);
- `location = /index.html` — `Cache-Control: no-cache`: `index.html` hech qachon keshlanmaydi, aks holda deploy'dan keyin brauzer eski hash'li assetlarga ishora qiluvchi eski SPA'ni ushlab qolib oq ekran berardi;
- `location /` — `/usr/share/nginx/html` dan static, `try_files $uri $uri/ /index.html =404` (SPA fallback);
- static assetlar (`js/css/img/font`) uchun `expires 1y` + `Cache-Control: public, immutable`;
- `/api`, `/docs`, `/redoc` → **404** — bu pathlar reverse proxy (Caddy) tomonidan xizmat qilinadi, frontend konteyneriga tushib qolsa xato ekanini aniq bildiradi.

---

## Dockerfile'lar

### `backend/Dockerfile` — multi-stage, uv asosida

1. **Builder stage** — `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`. `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`. Layer caching uchun avval faqat `uv.lock` + `pyproject.toml` bind-mount bilan `uv sync --frozen --no-install-project` (cache mount `/root/.cache/uv`), keyin faqat kerakli kod — `COPY backend /app/backend` + `COPY scripts /app/scripts` (avvalgi `COPY . /app` o'rniga: frontend/docs o'zgarishlari backend layer cache'ini bekorga buzmasligi uchun) — va `uv sync --frozen --no-editable`.
2. **Final stage** — `python:3.13-slim-bookworm`. Healthcheck uchun `curl`, yorliq PNG'si TTF shriftda chiqishi uchun `fonts-liberation` o'rnatiladi. Xavfsizlik uchun **non-root `app` user** (uid/gid 1000). Builderdan `/app/backend/.venv`, `/app/backend`, `/app/scripts` ko'chiriladi. `PATH` ga venv qo'shiladi, `PYTHONPATH=/app/backend`. Default `CMD` — `uvicorn app.main:app --host 0.0.0.0 --port 8000`, lekin ikkala compose ham buni override qiladi (dev: reload'li uvicorn; prod: gunicorn; worker: arq).

Muhim: build context — **repo root** (`context: .`), chunki image'ga `scripts/` ham kiradi (`prestart.sh` shu yerdan ishlaydi).

### `frontend/Dockerfile` — multi-stage, Node → nginx

1. **build-stage** — `node:24-alpine` (versiya `frontend/.nvmrc` dagi `24` bilan mos). `package*.json` avval ko'chiriladi → `npm ci` (layer caching), keyin kod. `ARG VITE_API_URL` va `ARG VITE_API_TIMEOUT_MS` (default `30000`) build vaqtida env'ga aylanadi — Vite build'ga statik ravishda "pishiriladi" (shuning uchun lokal compose va CI'ning `images` job'i turli `VITE_API_URL` bilan alohida build qiladi). `npm run build` → `tsc && vite build` → `dist/`.
2. **Runtime** — `nginx:1.29-alpine`. Default config o'chiriladi, `dist/` → `/usr/share/nginx/html`, `nginx/index.conf` → `default.conf`. `HEALTHCHECK` — `wget --spider http://localhost/` (prod compose buni `http://127.0.0.1/` bilan override qiladi — nginx faqat IPv4 tinglaydi).

---

## Scriptlar

Barcha `scripts/*.sh` fayllar git'da **executable (mode 100755)** saqlanadi. Bu muhim: avval ular 644 bo'lib, image ichida `/app/scripts/prestart.sh` ishga tushmasdi va `api` konteynerlar umuman start bo'lmasdi.

### `scripts/setup.sh` — bir martalik lokal setup

`make setup` chaqiradi. `set -e` bilan: (1) `uv` o'rnatilganini tekshiradi, yo'q bo'lsa xato bilan chiqadi; (2) `.env` bo'lmasa `.env.example` dan nusxa oladi; (3) `uv --project backend sync`; (4) `alembic upgrade head`; (5) `python -m app.commands.create_first_superuser` (`.env` dagi `ADMIN_*` qiymatlaridan); (6) `python -m app.commands.seed_defaults` — default organizatsiya va 6 ta ishlab chiqarish posti. `Makefile` dagi `setup` targeti bundan keyin `install-hooks` (pre-commit) ni ham bajaradi.

### `scripts/prestart.sh` — konteyner startidan oldingi bosqich

Ikkala composeda ham `api` command zanjirining birinchi qismi. Uch qadam: `alembic.ini` mavjud bo'lsa `python -m alembic upgrade head`, so'ng `python -m app.commands.create_first_superuser`, oxirida `python -m app.commands.seed_defaults` (default organizatsiya va 6 ta ishlab chiqarish postini idempotent seed qiladi). Shu tufayli konteyner har startda schema'ni head'ga keltiradi, admin user va default org/postlar mavjudligini kafolatlaydi. `worker` servisi buni ishlatmaydi (migratsiyani `api` ga qoldiradi).

### `scripts/generate-client.sh` — OpenAPI → TypeScript client

`make frontend-gen` chaqiradi. Oqim: `backend/` da `app.main.app.openapi()` ni Python orqali JSON'ga dump → `frontend/openapi.json`; keyin `npm run generate-client` (`@hey-api/openapi-ts`, `frontend/package.json` dagi `generate-client: openapi-ts` script) → `frontend/src/client/`; oxirida `npx biome format --write ./src/client`. Backend endpoint/schema o'zgarganda shu buyruqni qayta ishlatish kerak (`frontend/README.md` da ham qo'lda variant tasvirlangan).

### `scripts/deploy.sh` — prod deploy avto-rollback bilan

CI chaqiradi: `TAG=<git sha> REGISTRY=ghcr.io/<owner> bash scripts/deploy.sh`. Oqim: `docker compose pull` — serverda build yo'q, tayyor image ghcr.io dan tortiladi (yiqilsa eski stack joyida qoladi) → yangi `TAG` ga switch (`docker compose up -d`) → smoke. Smoke `SMOKE_URL` ga uradi (default `http://127.0.0.1:8200/api/v1/ready`) — `/api/v1/ready` DB+Redis'ni tekshiruvchi readiness probe (`/api/v1/health` dan farqli, u faqat process tirikligini aytadi); CI'ning public smoke'i ham shu endpointga uradi. Smoke o'tsa `TAG` `.stable_tag` fayliga yoziladi va eski image'lar tozalanadi (joriy + oldingi stable qoladi); yiqilsa `.stable_tag` dagi oxirgi barqaror tag'ga avto-rollback qilinadi. Rollback **serverda oldingi image hali turganiga** tayanadi — aynan shu tozalash qadami buni kafolatlaydi (joriy tag va oldingi stable tag hech qachon o'chirilmaydi).

Tozalash `docker images --format '{{.Repository}}:{{.Tag}}' | grep 'mebelix-mes-'` bilan ishlaydi, `--filter=reference='mebelix-mes-*'` bilan emas: docker glob'i `/` dan o'tmaydi, ya'ni `ghcr.io/<owner>/mebelix-mes-*` nomlariga u hech qachon mos kelmasdi va eski image'lar to'planib qolardi. Natija o'sha `grep -vE ":(TAG|STABLE)$"` filtridan o'tkaziladi. **Muhim qoida: rollback DB'ni pastga tushirmaydi — migratsiyalar additive bo'lishi shart** (ustun/jadval qo'shish; eski kod yangi ustunlarga chidashi kerak).

### `scripts/backup.sh` — kunlik shifrlangan DB backup

Server cron'ida kunlik ishlaydi (`0 2 * * *`). Oqim: `pg_dump` (prod composedagi `db` konteyneri ichida) | `gzip` | `openssl aes-256-cbc -pbkdf2` (parol — `.env` dagi `ADMIN_PASSWORD`) → natija **serverdagi `backups/mebelix-YYYY-MM-DD.sql.gz.enc`** fayliga yoziladi. So'ng ikkita nazorat: fayl 1000 baytdan kichik bo'lsa dump yiqilgan deb hisoblanadi (fayl o'chiriladi, script `exit 1`), va `BACKUP_KEEP_DAYS` (default `14`) kundan eski nusxalar `find … -delete` bilan tozalanadi. Katalogni `BACKUP_DIR` (default `backups`), saqlash muddatini `BACKUP_KEEP_DAYS` o'zgartiradi — ikkalasi ham `.env.example` da yo'q, kerak bo'lsa `.env` ga qo'lda qo'shiladi. `backups/` `.gitignore` da.

Telegram — **ixtiyoriy tashqi nusxa**: `.backup.env` da `TG_BOT_TOKEN` va `TG_CHAT_ID` bo'lsa fayl document sifatida ham yuboriladi, bo'lmasa script "Telegram sozlanmagan" deb yozib normal tugaydi; yuborish yiqilsa ogohlantirish chiqadi, lekin lokal backup joyida. Diskka yozish asosiy yo'l ekani ataylab: Telegram yagona yo'l bo'lganda `.backup.env` yo'qligi butun scriptni yiqitib, 15 kecha davomida birorta backup olinmagan edi.

Ochish: `openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc | gunzip > dump.sql`.

---

## Chop etish infratuzilmasi — bridge-agent va GoDEX G500-U

Printer sexda, server esa masofada (`mes.mebelix.uz`) turadi. GoDEX G500-U **faqat USB** — unda tarmoq porti umuman yo'q, ya'ni printerga IP orqali murojaat qilish imkoni yo'q. Shuning uchun oraliqda **bridge-agent** — printer ulangan kompyuterda ishlaydigan, serverga **chiquvchi** (outbound) WebSocket ochadigan servis. Manbasi bitta Python fayl (`bridge-agent/agent.py`), sexga esa u **Windows exe** (`mebelix-agent.exe`) sifatida boradi — o'rnatiladigan mashinada Python ham, kutubxona ham kerak emas. Sex tarmog'ida hech qanday port ochilmaydi, oq IP kerak emas.

Agent faqat **printer ulangan bitta kompyuterga** o'rnatiladi; menejer, texnolog va boshqa post terminallariga hech narsa kerak emas — ular brauzerdan tugmani bosadi.

### Zanjir (uchdan-uchgacha)

```
Terminal (arrachi)
  POST /api/v1/terminal/labels/{instance_id}          (backend/app/api/routes/terminal.py)
    ├── instance.label_printed_at = now()
    ├── ws_manager.publish("label.printed", …)         → brauzerlarga live yangilanish
    └── arq enqueue_job("print_label", instance_id)
          ↓
  print_label task                                     (backend/app/tasks/__init__.py)
    ├── load_label_data(db, instance_id)               (backend/app/services/labels.py)
    ├── render_label_png(data)      → PNG, base64
    └── redis.lpush("mes:print:queue", job)            → job = {type, instance_id, png}
          ↓
  GET /api/v1/ws/bridge  (Authorization: Bearer …)     (backend/app/api/routes/ws.py)
    brpop("mes:print:queue", 5) → send → ack kutish → yo'q bo'lsa rpush (qaytarib qo'yish)
          ↓
  bridge-agent (sex)                                   (bridge-agent/agent.py)
    uplink() → local_enqueue(job) → ack → FLUSH_EVENT.set()
    flusher() → send_to_printer(png)                   → Windows GDI → USB GoDEX
```

Job'ning Redis'dagi kaliti — `PRINT_QUEUE_KEY = "mes:print:queue"` (`backend/app/tasks/__init__.py`).

### Ishonchlilik: hech bir yorliq yo'qolmaydi

Zanjirning har bo'g'inida jobni yo'qotmaslik choralari bor:

- **Server → agent.** `ws_bridge` jobni `brpop` bilan Redis'dan **oladi** (ya'ni navbatdan chiqadi), keyin yuboradi va `{"ok": true}` ack kutadi (`asyncio.wait_for`, 15s). Ack kelmasa yoki `ok` false bo'lsa — `rpush` bilan navbatga **qaytariladi**, ulanish esa uziladi.
- **Agent tomonda.** `uplink()` jobni avval `local_enqueue()` bilan diskka yozadi (`print-queue.jsonl`, JSONL append), **keyin** ack yuboradi. Ya'ni server jobni faqat u sexdagi diskda turgani aniq bo'lgach unutadi — agent yoki kompyuter o'chsa ham job saqlanadi.
- **Printer o'chiq bo'lsa.** `flusher()` navbatni ketma-ket chiqaradi; birinchi muvaffaqiyatsiz jobda to'xtaydi va **qolgan barchasini** `local_rewrite()` bilan faylga qaytarib yozadi (tartib buzilmaydi), keyin `"Printer kutilmoqda — navbatda N ta yorliq"` deb log yozadi.
- **Bo'sh vaqtda.** Agent oddiy holatda 5 sekundda bir sikl uradi, lekin yangi job kelganda `FLUSH_EVENT.set()` flusher'ni **darhol** uyg'otadi — kutish yo'q.
- **Yarim-ochiq TCP.** Server jobsiz 5 sekunddan keyin `{"type": "ping"}` yuboradi va javob kutadi; agent unga `{"ok": true}` bilan javob beradi. Sex tarmog'ida "o'lgan" ulanish tez aniqlanadi. Agent tomonda `websockets.connect(..., ping_interval=30)`, uzilganda 5s backoff bilan qayta ulanish.

### Autentifikatsiya — har agent uchun alohida token (pairing)

Avval serverda bitta umumiy `BRIDGE_TOKEN` bo'lardi va uni har printerli mashinaga qo'lda ko'chirish kerak edi. Endi **har agent o'z tokeni bilan** ishlaydi, tokenni esa admin panel beradi — serverga SSH ham, `.env` tahriri ham kerak emas (`backend/app/api/routes/bridge_agents.py`).

Oqim:

1. **Kod.** Admin panelda "Yangi agent" → `bridge_agent` qatori yaratiladi va 8 belgili **bir martalik kod** beriladi (`P7HJ-N46U` ko'rinishida ko'rsatiladi), muddati **15 daqiqa** (`PAIR_TTL`). Alifboda `I/L/O/0/1` yo'q — kodni telefonda aytganda adashilmaydi; 31⁸ ≈ 8.5e11 kombinatsiya 15 daqiqalik oynada brute-force'ni ma'nosiz qiladi.
2. **Almashtirish.** Agent kodni `POST /api/v1/bridge-agents/pair` ga yuboradi va **muddatsiz token** oladi (`secrets.token_hex(24)`). Bazada faqat `sha256` xesh saqlanadi, kod esa o'chiriladi. UPDATE atomik — bitta kodni ikki kompyuter bir vaqtda yuborsa faqat bittasi yutadi. Kod noto'g'ri yoki eskirgan bo'lsa bitta umumiy xato qaytadi (kod umuman bor-yo'qligi oshkor qilinmaydi). `/pair` — ochiq endpoint, chunki agentda sessiya yo'q; `GET /download` ham ataylab ochiq (exe hamma uchun bir xil fayl, sir saqlamaydi, monoblok brauzerida esa sessiya bo'lmasligi mumkin). Qolgan `bridge-agents` endpointlari (`GET /`, `POST /`, `POST /{id}/code`, `DELETE /{id}`) `AdminUser` bilan yopiq.
3. **Ulanish.** `/ws/bridge` tokenni **`Authorization: Bearer`** headeridan oladi (URL query'da emas — server access-loglariga tushmasin); `?token=` query eski agentlar uchun fallback bo'lib qolgan. Token avval legacy `settings.BRIDGE_TOKEN` bilan `secrets.compare_digest` orqali solishtiriladi (bytes'da — non-ASCII tokenda `str` solishtirish `TypeError` beradi), mos kelmasa `sha256` bo'yicha `bridge_agent` jadvalidan qidiriladi. Ikkovi ham topilmasa WebSocket `code=4401` bilan yopiladi.

`settings.BRIDGE_TOKEN` endi **ixtiyoriy legacy back-compat** — bo'sh bo'lsa ham chop etish to'liq ishlaydi. Yangi o'rnatishlarda uni umuman to'ldirmaslik kerak.

**Bekor qilish (revoke) darhol emas, lekin kafolatli.** Ulanish davomida `touch_agent()` har **300 sekundda** `last_seen_at` ni yangilaydi (paneldagi "Onlayn" indikatorining manbai) va shu UPDATE'ning o'zi agent hali mavjudligini qayta tekshiradi: `token_hash` mos kelmasa yoki qator o'chirilgan bo'lsa `RETURNING` bo'sh qaytadi. Ya'ni bekor qilingan agentning **jonli** ulanishi ham 5 daqiqa ichida `4401` bilan uziladi, qo'lida turgan job esa Redis navbatiga `rpush` bilan qaytariladi — yo'qolmaydi. DB xatosi ulanishni **yiqitmaydi** (jobni saqlab qolish ustuvor).

### Admin panel — "Printer agentlar"

`frontend/src/routes/_layout/printers.tsx`, faqat admin. Sahifada: exe yuklab olish tugmasi, uch qatorli o'rnatish yo'riqnomasi va agentlar jadvali — nomi, holati, joriy ulanish kodi, oxirgi ulanish vaqti, amallar.

| Holat | Qachon |
|---|---|
| `Onlayn` | `last_seen_at` 6 daqiqadan yangi (server 5 daqiqada bir yangilaydi — bitta sikl zaxira) |
| `Oflayn` | ulangan (token bor), lekin oxirgi 6 daqiqada ko'rinmadi |
| `Kod kutilmoqda` | kod berilgan, agent hali ulanmagan |
| `Kod muddati o'tgan` | 15 daqiqa o'tdi, agent ulanmadi — "yangi kod" kerak |

Amallar: **yangi kod** (`POST /{id}/code` — eski tokenni ham bekor qiladi, kompyuter almashganda) va **bekor qilish** (`DELETE /{id}` — soft delete, ulanish endi rad etiladi). Ikkalasi ham `audit_log` ga yozadi.

### Yorliq PNG — bitta format

`backend/app/services/labels.py` da yorliqning yagona chiqish formati bor:

| Funksiya | Chiqish | Kim ishlatadi |
|---|---|---|
| `load_label_data(db, instance_id)` | `LabelData` (DB'dan yig'iladi, cutmap'dagi haqiqiy teshiklar bilan) | `print_label` task va PNG endpoint uchun umumiy manba |
| `render_label_png(d, scale=1)` | 80×60 mm, 203 dpi (8 dot/mm → 640×480 px), **1-bit** PNG | agent'ning Windows GDI yo'li; `GET /api/v1/terminal/labels/{id}.png` (brauzerdan istalgan printerga) |

`print_label` task jobga faqat base64 `png` soladi — job JSON: `{"type": "print", "instance_id", "png"}`. PNG printer dialektiga bog'liq emas — server hech qanday xom printer formatini generatsiya qilmaydi, chizishni Windows drayveri bajaradi.

PNG maketi GibSaw `mebelix.lbl` ga taqlid qiladi: chap ustun — logo, `Formatka` + zakaz kodi, detal kodi, loyiha nomi, 2×2 kromka jadvali (tagchiziq bilan), katta `L x W = count`, `N_detal` nomi, XNC belgilari (`П`=paz, `Ф`=freza), material va sana; o'ng ustun — QR (tepada, `qrcode` kutubxonasi bilan chiziladi) va vertikal detal eskizi. Eskizda kromka konturdan 1 mm tashqarida qalin chiziq bilan, `d.texture` bo'lsa uzunlik bo'ylab 3 ta chiziq, `d.holes` (cutmap'dan olingan haqiqiy teshiklar) aylana/qirra tikkalari bilan chiziladi.

Termoprinter uchun ikki qat'iy qoida kodga o'rnatilgan: `draw.fontmode = "1"` (antialiasing o'chiq) va yakuniy `img.convert("L").point(… , "1")` — har piksel sof qora yoki oq. Aks holda drayver dither qiladi va QR skanerlanmay qoladi. Shuningdek barcha chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qolib ketadi.

**Assetlar** (`backend/app/assets/`, image ichiga `COPY backend /app/backend` bilan tushadi):

| Fayl | Qayerda |
|---|---|
| `label-logo.png` | yorliq tepa-chapida, 160 threshold bilan 1-bit qilinadi; ochib bo'lmasa `MEBELIX` matni fallback |
| `label-icon-drill.png` | teshik bor detallarda sverlo ikonkasi (alpha oq fonga flatten qilinadi); ochib bo'lmasa `С` harfi fallback |

**Shrift eslatmasi.** `_FONT_REGULAR` / `_FONT_BOLD` ro'yxatlari tartib bilan sinaladi: Windows (`C:/Windows/Fonts/arial.ttf`, `arialbd.ttf`) → Debian Liberation Sans (`/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf` / `-Bold.ttf`) → zaxira DejaVu; hech biri topilmasa `ImageFont.load_default()` ga tushadi. `backend/Dockerfile` final stage'i `curl` bilan birga `fonts-liberation` ni ham o'rnatadi, shuning uchun server tomonda PNG (`/labels/{id}.png` endpointi va `print_label` task'idagi `render_label_png`) ham TTF shriftda chiqadi — qo'shimcha paket kerak emas. Liberation Sans Arial bilan metrik mos, ya'ni Windowsda sozlangan maket serverda ham aynan shunday joylashadi (DejaVu kengroq va maketni siljitgani uchun faqat zaxira).

### Chiqish yo'li — bitta: Windows GDI

`send_to_printer(png_b64)` da bitta yo'l bor: `_print_png_gdi()` — win32ui/PIL orqali Windows drayveriga rasm chizish. Bu GibSaw'ning "Used the printer driver" rejimi bilan bir xil; admin huquqi ham, printer share ham kerak emas.

Printer **avtomatik topiladi**: `_detect_printer()` `win32print.EnumPrinters(PRINTER_ENUM_LOCAL)` bo'yicha yuradi va nomida `godex` bo'lgan birinchi lokal printerni oladi. Shuning uchun odatdagi o'rnatishda hech qanday printer sozlamasi yozilmaydi — GoDEX drayveri o'rnatilgan bo'lsa bas, printer almashsa ham config o'zgarmaydi. `PRINTER_NAME` env'i faqat qo'lda override uchun (avto-topish o'rniga).

Printer topilmasa job navbatda qoladi va log'da `GoDEX printer topilmadi — drayver o'rnatilganini tekshiring` xatosi chiqadi. `png` maydonisiz job (eski format yozuvi) navbatni to'smasligi uchun tashlab yuboriladi.

**`_print_png_gdi()` nima qiladi.** Windows printer drayveri default qog'oz o'lchamiga (ko'pincha A4 yoki roll default'i) qarab yorliqni noto'g'ri joylashtiradi, shuning uchun DEVMODE qo'lda majburlanadi:

1. `win32print.GetPrinter(h, 2)["pDevMode"]` — drayverning joriy DEVMODE'i olinadi;
2. `PaperSize = 256` (`DMPAPER_USER`), `PaperWidth = 800`, `PaperLength = 600` — birlik **0.1 mm**, ya'ni 80×60 mm; `Orientation = 1` (portret);
3. `dm.Fields |= DM_PAPERSIZE | DM_PAPERWIDTH | DM_PAPERLENGTH | DM_ORIENTATION` — drayverga bu maydonlar haqiqiy ekani bildiriladi;
4. `win32gui.CreateDC("WINSPOOL", PRINTER_NAME, dm)` bilan shu DEVMODE'li DC ochiladi;
5. rasm `HORZRES`/`VERTRES` ga proporsional (`min` scale) sig'diriladi va `ImageWin.Dib(img).draw(...)` bilan `StartDoc`/`StartPage` ichida chiziladi.

Printer xatosi ushlanadi va `False` qaytariladi — job navbatda qoladi, yo'qolmaydi.

### Agent o'rnatish

Faqat printer USB bilan ulangan Windows kompyuterga (sexdagi terminal monoblokning o'zi ham bo'ladi). Hammasi brauzerdan bajariladi — serverga SSH kirish, server `.env` ini tahrirlash yoki sex routerida biror port ochish **kerak emas** (ulanish baribir chiquvchi). Qadamlar (`bridge-agent/README.md`):

1. **GoDEX drayverini o'rnatish** — printer USB'ga ulangan holda. Agent printerni nomidan o'zi topadi, boshqa sozlash yo'q.
2. **Agentni yuklab olish** — admin panel > "Printer agentlar" > "Agentni yuklab olish": `mebelix-agent.exe` tushadi (`GET /api/v1/bridge-agents/download`). Python, `pip`, kutubxonalar — hech biri kerak emas, hammasi exe ichida.
3. **Ulanish kodini olish** — o'sha sahifada "Yangi agent", kompyuterga nom beriladi va 8 belgili bir martalik kod chiqadi (masalan `P7HJ-N46U`), 15 daqiqa amal qiladi.
4. **Exe'ni ishga tushirish** — kichik oyna chiqadi: server manzili (default `wss://mes.mebelix.uz`) va ulanish kodi. "Ulash" bosilgach kod doimiy tokenga almashtiriladi va `%APPDATA%\MebelixAgent\.env` ga saqlanadi. Kod noto'g'ri bo'lsa oyna xato matni bilan qayta ochiladi — dasturni qayta ishga tushirish shart emas. Kod muddati o'tishi allaqachon ulangan agentga ta'sir qilmaydi.

Beshinchi qadam yo'q: agent birinchi ulanishda o'zini `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` ga yozadi, ya'ni kompyuter yonganda o'zi tushadi (admin huquqi kerak emas, faqat shu foydalanuvchi uchun). Exe `--noconsole` bilan qurilgani uchun **hech qanday oyna ko'rinmaydi** — yopib qo'yish mumkin bo'lgan konsol yo'q.

Ishlayotganini admin paneldagi **Onlayn** belgisi bildiradi. Diagnostika `%APPDATA%\MebelixAgent\agent.log` da (`RotatingFileHandler`, 1 MB x 3): `Printer: Godex G500` va `Serverga ulandi` — tayyor; `Printer: TOPILMADI` — GoDEX drayveri yo'q.

Ikkinchi nusxa ishga tushmaydi — `win32event.CreateMutex` bilan singleton. Oyna ko'rinmagani uchun foydalanuvchi "ishlayaptimi?" deb exe'ni qayta bosishi tabiiy; ikki agent bir printerga ulansa navbat ular orasida bo'linib ketardi.

Token bekor qilinganda (admin "yangi kod" yoki "o'chirish" bosgan) handshake `403`/`4401` bilan rad etiladi. Agent buni payqab saqlangan `.env` ni o'chiradi va sozlash oynasini qayta ochadi — yangi kod kiritilsa ishlashda davom etadi, bekor qilinsa to'xtaydi. Aks holda foydalanuvchi `.env` ni qo'lda o'chirib, avval fon jarayonini Task Manager'dan yopishga majbur bo'lardi.

Agent sozlamalari (bular **server `.env`** ida emas — printerli mashinada, `%APPDATA%\MebelixAgent\.env` da). O'qish tartibi: **env o'zgaruvchi > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`**. Odatda qo'lda hech narsa yozilmaydi — birinchi ulanish `MES_URL` va `BRIDGE_TOKEN` ni o'zi to'ldiradi.

| Env | Default | Tavsif |
|---|---|---|
| `MES_URL` | `ws://localhost:8000` | server manzili; agent oxiriga `/api/v1/ws/bridge` qo'shadi. Pairing paytida `https://`/`http://`/sxemasiz manzil ham qabul qilinadi va `wss://`/`ws://` ga normallashtiriladi (TLS'siz manzilga ogohlantirish chiqadi) |
| `BRIDGE_TOKEN` | — | pairing bergan doimiy token; bo'sh bo'lsa agent `SystemExit` bilan to'xtaydi ("ulanish kodini kiriting") |
| `PRINTER_NAME` | avto-topish (`godex`) | printer nomini qo'lda berish — faqat avto-topish mos kelmaganda |
| `QUEUE_FILE` | `./print-queue.jsonl` | lokal durable navbat fayli |

Navbat fayli `.gitignore` da (`bridge-agent/print-queue.jsonl`).

### Agentning yangi versiyasini chiqarish

`bridge-agent/` katalogida:

```bash
pyinstaller --onefile --noconsole --name mebelix-agent agent.py
```

Natijadagi `mebelix-agent.exe` serverda `uploads/agent/` ga qo'yiladi — panel o'sha yerdagi faylni tarqatadi. Bu yo'l `.gitignore` da, ya'ni **binar repoda saqlanmaydi** va deploy uni ko'chirmaydi; serverga bir marta qo'lda yuklanadi:

```bash
docker compose -f docker-compose.prod.yml cp mebelix-agent.exe api:/app/backend/uploads/agent/
```

`uploads_data` volume tufayli fayl keyingi deploylarda joyida qoladi — yangi versiya chiqqandagina qayta yuklanadi.

Eslatma: SCX/CNC fayllar bridge orqali **o'tmaydi** — ular stanok kompyuterida brauzer orqali yuklab olinadi (TZ 12.5). Bridge faqat yorliq chop etish uchun.

---

## Sifat nazorati — pre-commit hooklar va GitHub Actions CI

### `.pre-commit-config.yaml` — commit-oldi hooklar

`make install-hooks` (`pre-commit install`) bilan o'rnatiladi; har commitda ishlaydi:

| Hook | Manba | Vazifasi |
|---|---|---|
| `check-added-large-files`, `check-toml`, `check-yaml --unsafe` | `pre-commit-hooks` v5.0.0 | umumiy sanitariya |
| `ruff --fix`, `ruff-format` | `ruff-pre-commit` v0.13.0 | Python lint + format |
| `mypy` (local, `language: system`) | `uv --directory backend run mypy app` | type check — loyiha venv'i kerakligi uchun local hook (`make install` prereq) |
| `biome-check` (local) | `cd frontend && npx --no-install biome check ...` | frontend lint — `frontend/biome.json` ni olishi uchun `frontend/` dan ishlaydi (`npm install` prereq) |

`mypy` va `biome` hooklari `pass_filenames: false` — butun loyiha bo'yicha tekshiradi.

### `.github/workflows/ci.yml` — GitHub Actions

`main` ga push va har bir pull request'da ishga tushadi; beshta job — `backend` va `frontend` parallel, `images` ularga bog'liq, `deploy` — `images` ga, `notify` — hammasiga:

| Job | Qadamlar |
|---|---|
| `backend` | `astral-sh/setup-uv` → `uv --project backend sync --all-groups` → `ruff check app` + `ruff format --check app` → `mypy app` → `python -m tests.test_giblab` (GibLab parser testlari) |
| `frontend` | `actions/setup-node` (versiya `frontend/.nvmrc` dan, npm cache) → `npm ci` → `npx biome ci .` → `npm run build` (`tsc && vite build`) |
| `images` | faqat `main` ga push + ikkala job yashil bo'lsa (`needs: [backend, frontend]`), `permissions: packages: write`. Ikki elementli matritsa: `backend` (context `.`, `./backend/Dockerfile`) va `frontend` (context `./frontend`, `./frontend/Dockerfile`, build-arglar `VITE_API_URL=` va `VITE_API_TIMEOUT_MS=30000`). `docker/setup-buildx-action` → `docker/login-action` (ghcr.io, `GITHUB_TOKEN`) → `docker/build-push-action@v6`, GitHub Actions qatlam keshi bilan (`cache-from`/`cache-to: type=gha, scope=<name>`). Teglar: `ghcr.io/<owner>/mebelix-mes-backend:<git sha>` va `...-frontend:<git sha>` |
| `deploy` | faqat `main` ga push + `images` yashil bo'lsa (`needs: [images]`), `permissions: packages: read`; `concurrency: prod-deploy` (parallel deploy yo'q). Qadamlar: SSH key setup → `rsync` kodni `root@DEPLOY_HOST:/opt/mebelix-mes` ga (`.git`/`node_modules`/`.venv`/`__pycache__`/`dist`/`uploads`/`.env` exclude) → serverni ghcr'ga login qilish → `ssh` orqali `TAG=<git sha> REGISTRY=ghcr.io/<owner> bash scripts/deploy.sh` → public smoke `https://mes.mebelix.uz/api/v1/ready` (nginx/TLS yo'li orqali). Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST` |
| `notify` | `if: always() && push && ref == main`, `needs: [backend, frontend, images, deploy]` — Telegram xabari. Secrets: `TG_BOT_TOKEN`, `TG_CHAT_ID` |

**Nega image'lar CI'da quriladi.** Avval ularni prod serverning o'zi build qilardi. Server 1 vCPU / 2 GB RAM — build jonli saytni sekinlashtirardi va CI allaqachon bajargan ishni takrorlardi. Endi build GitHub Actions runnerida bo'ladi, server esa faqat tortadi.

**Paket repoga bog'lanishi.** `build-push-action` `org.opencontainers.image.source` labelini qo'yadi — aynan shu label paketni repo bilan bog'laydi. Busiz paket alohida turadi va `deploy` job'ning `GITHUB_TOKEN` i uni tortishga huquq olmaydi.

**Serverdagi registry login.** GitHub paketlari private (repo private), shuning uchun server ghcr.io ga autentifikatsiya qilishi shart. Deploy oldidagi qadam vaqtinchalik `GITHUB_TOKEN` ni ssh stdin orqali `docker login ghcr.io --password-stdin` ga uzatadi: doimiy PAT serverda saqlanmaydi va token serverdagi process ro'yxatiga tushmaydi (buyruq argumentida emas).

**Nega `notify` alohida job.** Avval u `deploy` ichida `if: always()` qadami edi. Lekin `backend` yoki `frontend` yiqilsa `deploy` butunlay **skipped** bo'ladi — skip qilingan job'ning qadamlari umuman ishlamaydi, ya'ni CI yiqilganda xabar hech kimga bormasdi. Endi `notify` mustaqil job va to'rttala natijani `needs.<job>.result` orqali env'da oladi (`BACKEND`, `FRONTEND`, `IMAGES`, `DEPLOY`):

| `DEPLOY` natijasi | Xabar |
|---|---|
| `success` | `✅ MebeliX deploy OK` |
| `skipped` | `❌ MebeliX CI YIQILDI (deploy boshlanmadi) — backend: …, frontend: …, images: …` |
| qolgani (`failure`/`cancelled`) | `❌ MebeliX deploy YIQILDI (avto-rollback ishlagan bo'lishi kerak)` |

Xabar tanasiga commit subject (`head -1`), qisqa sha (`${GITHUB_SHA::7}`) va Actions run URL qo'shiladi. Commit message `COMMIT_MSG` env orqali uzatiladi va `--data-urlencode` bilan yuboriladi — maxsus belgilar shell'ga ham, URL'ga ham tushib ketmasligi uchun.

Ya'ni sifat nazorati ikki qatlamli: lokalda pre-commit + `make lint`, remote'da GitHub Actions har push/PR'ni tekshiradi, yashil `main` esa avtomatik prodga chiqadi.

---

## Environment variablelar (`.env.example`)

`.env.example` → `.env` (setup.sh avtomatik ko'chiradi). Backend `pydantic-settings` orqali o'qiydi, frontend `VITE_*` larni build vaqtida oladi. Composelar `POSTGRES_SERVER` / `REDIS_HOST` ni `db` / `redis` ga override qiladi.

| Variable | Default (example) | Tavsif |
|---|---|---|
| `APP_NAME` | `MebeliX` | Ilova nomi |
| `ENVIRONMENT` | `local` | `local` / `staging` / `production` |
| `SECRET_KEY` | placeholder | JWT imzo kaliti — production'da `openssl rand -hex 32` bilan almashtirilishi shart |
| `ALGORITHM` | `HS256` | JWT algoritmi |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token muddati |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token muddati |
| `BCRYPT_ROUNDS` | `12` | Parol hashing rounds |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | `postgres` / `postgres` | DB credentiallar (prod composeda defaultsiz — majburiy) |
| `POSTGRES_SERVER` | `localhost` | Docker'da `db` (compose override qiladi) |
| `POSTGRES_PORT` | `5432` | DB port |
| `POSTGRES_DB` | `fastapi` | DB nomi |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` | SQLAlchemy pool sozlamalari |
| `REDIS_HOST` | `localhost` | Docker'da `redis` |
| `REDIS_PORT` | `6379` | Redis port |
| `LOGIN_RATE_LIMIT_ATTEMPTS` / `LOGIN_RATE_LIMIT_PERIOD` | `5` / `300` | Login urinishlari limiti — `.env.example` dagi yagona rate-limit kaliti |
| `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` | `50` / `100` | Pagination |
| `STARTUP_RETRY_MAX_ATTEMPTS` / `STARTUP_RETRY_DELAY_SECONDS` | `5` / `2` | Lifespan'da DB/Redis health retry |
| `THREADPOOL_TOKENS` | `100` | AnyIO sync-bridge slotlari |
| `FORWARDED_ALLOW_IPS` | `["*"]` | `X-Forwarded-*` ga ishoniladigan upstream IPlar; `*` — Caddy/nginx yagona yo'l bo'lganda maqbul |
| `ADMIN_PHONE` / `ADMIN_USERNAME` / `ADMIN_PASSWORD` | misol qiymatlar | Startupda yaratiladigan birinchi superuser (E.164 telefon) |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | JSON-array CORS originlar |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API bazasi; reverse proxy ortida (prod compose) `""` — SDK yo'llari o'zi `/api/v1` bilan boshlanadi |
| `VITE_API_TIMEOUT_MS` | `30000` | Axios timeout |
| `GUNICORN_WORKERS` | `4` | Prod worker soni; odatda `(2 * CPU) + 1` |
| `SITE_ADDRESS` | `:80` | Caddy listener; domen berilsa auto-HTTPS |
| `BRIDGE_TOKEN` | `""` (bo'sh) | **Legacy, ixtiyoriy.** Bridge-agentlar endi admin paneldagi pairing orqali o'z tokenini oladi; bu maydon faqat eski, pairing'gacha o'rnatilgan agent uchun qoldirilgan. Yangi o'rnatishda bo'sh qoladi va chop etish to'liq ishlayveradi |

Eslatma: chop etishga tegishli **majburiy** server sozlamasi yo'q. `BRIDGE_TOKEN` ixtiyoriy legacy, printer env'lari esa umuman server `.env` ida emas (G500-U'da tarmoq porti yo'q, printerni faqat agent ko'radi) — `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME`, `QUEUE_FILE` printerli mashinadagi `%APPDATA%\MebelixAgent\.env` da yashaydi (yuqoridagi "Chop etish infratuzilmasi" bo'limi).

Eslatma: Redis navbati va rate-limitini o'chiradigan flag yo'q — pool'lar lifespan'da so'zsiz ochiladi, `RateLimiter` esa client bo'lmaganda **fail-closed** ishlaydi (so'rov rad etiladi). Umumiy (login'dan tashqari) rate limit sozlamasi ham yo'q.

Eslatma: `CADDY_HTTP_BIND` / `CADDY_HTTPS_BIND` `.env.example` da yo'q — ular `docker-compose.prod.yml` dagi compose-level substitutsiyalar (defaultlari `80` / `443`); behind-nginx rejimida `.env` ga qo'lda qo'shiladi. `TAG` va `REGISTRY` ham shu kategoriyada — compose-level substitutsiyalar (defaultlari `latest` va `ghcr.io/dshukriddinov`), CI ularni git sha va `ghcr.io/<owner>` bilan beradi.

---

## Yordamchi konfiguratsiya fayllari

### `.dockerignore`

Backend build contexti (repo root) uchun denylist. Chiqariladi: `.git`, barcha `.env` va `.venv` lar, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `docker-compose*.yml`, hamda backend image'iga umuman kirmaydigan yirik kataloglar — `bridge-agent`, `frontend`, `docs`, `uploads`, `backups`, `caddy`. `backend/Dockerfile` baribir faqat `backend` va `scripts` ni `COPY` qiladi, qolgani daemon'ga behuda uzatilardi (~43 MB). Shu bilan secretlar ham image'ga tushmaydi.

Frontend'ning o'z konteksti (`./frontend`) va o'z `frontend/.dockerignore` i bor — ikki qator: `node_modules`, `dist`.

### `.gitattributes`

Bitta qoida: `* text=auto eol=lf` — barcha matn fayllar LF line-ending bilan normalizatsiya qilinadi (Windows/Linux aralash muhitda script va Dockerfile'lar buzilmasligi uchun).

### `.gitignore`

Standart Python artefaktlari (`__pycache__`, egg/build/dist), virtualenvlar (`.venv`, `backend/.venv`), **`.env` fayllar** (secretlar repoga tushmaydi), test/lint cache (`.mypy_cache`, `.ruff_cache`, `.coverage`), IDE fayllari (`.vscode/*` lekin `settings.json`/`launch.json`/`extensions.json` istisno), `backend/app/logs/*.log`. MES runtime artefaktlari ham ignore: `backend/uploads/` (`projects/`, `scx/`, `survey/` — yuklangan fayllar va anketa xona rasmlari, hamda `agent/mebelix-agent.exe` — binar repoda saqlanmaydi), `bridge-agent/print-queue.jsonl` (agent'ning durable print navbati), `frontend/openapi.json`, serverdagi shifrlangan DB nusxalari uchun `backups/` (`scripts/backup.sh`), hamda lokal sex ma'lumotlari — `uploads/` (repo root'da: `.project`/SCX namunalari) va `chek/` (namuna yorliq fotolari, `labels.py` maketi shulardan olingan). PyInstaller'ning `bridge-agent/build/` va `bridge-agent/dist/` kataloglari alohida qoida talab qilmaydi — umumiy `build/` / `dist/` naqshlari ularni istalgan chuqurlikda tutadi. E'tiborli nuqta: `**/lib/` ignore qilinadi, lekin `!frontend/src/lib/` istisno (shadcn util katalogi).

---

## Til/versiya manifestlari

### `backend/pyproject.toml`

`mebelix-backend` 0.1.0, `requires-python >=3.11, <3.14`, build-backend `hatchling` (faqat `app/` package). Runtime dependencylar (21 ta): `fastapi`, `uvicorn` + `uvloop` (uvloop faqat non-Windows), `websockets`, `gunicorn`, `SQLAlchemy` 2 + `asyncpg` + `greenlet` + `alembic`, `pydantic[email]`/`pydantic-settings`, `pyjwt[crypto]` + `bcrypt`, `redis` + `arq` (queue/worker), `prometheus-fastapi-instrumentator` (metrics), `python-multipart` (fayl yuklash: `.project`, SCX, anketa rasmlari), `openpyxl` (Excel), `pillow` + `qrcode` (`render_label_png` — yorliq PNG), `tzdata` (`ZoneInfo("Asia/Tashkent")` yorliq sanasi uchun). `websockets` aynan runtime dependency: uvicorn `[standard]` extra'siz o'rnatilgan (`wsproto` ham yo'q), ya'ni `/ws/events` va `/ws/bridge` transporti shu paketga tayanadi — dev groupda qolsa prod image'da WebSocket ishlamasdi. Dev group — to'rtta: `mypy`, `ruff`, `pre-commit`, `types-openpyxl`. Tooling konfiguratsiyasi shu faylda: **ruff** (`target-version py311`, line-length 120, `F/E/W/C/UP/I` rulesetlar, `__init__.py` da unused/star import istisno) va **mypy** (`python_version 3.11`, `app.*` uchun `disallow_untyped_defs = true`).

### `frontend/package.json` va `frontend/.nvmrc`

`.nvmrc` — `24` (Dockerfile'dagi `node:24-alpine` bilan sinxron; `nvm use` / `fnm use` uchun). `package.json` scriptlari: `dev` (vite), `build` (`tsc && vite build`), `lint` (biome, `--write --unsafe`), `preview`, `generate-client` (`openapi-ts`). Stack: React 19, TanStack Router + Query (react-table yo'q — jadvallar oddiy `<Table>` bilan chiziladi), Tailwind CSS 4, Radix UI, react-hook-form + zod, axios, sonner; dev tomonda Biome, `@hey-api/openapi-ts`, Vite 8 + SWC, TypeScript 6 (7 emas — sabab `docs/08-packages.md` da).

### `backend/README.md`

Backend dev qo'llanmasi: texnologiyalar ro'yxati, `make setup` yoki qo'lda setup (`uv sync`, `.env`, migratsiyalar, superuser, seed), ishga tushirish (`make run-backend` / `make docker-local`), ARQ worker, test/lint/migratsiya buyruqlari. `docs/07-infra-devops.md` va `docs/09-mes-domain.md` ga yo'naltiradi.

### `frontend/README.md`

Frontend dev qo'llanmasi: nvm/fnm bilan Node o'rnatish, `npm install` + `npm run dev` (port 5173), Docker'siz lokal dev tavsiyasi, OpenAPI client generatsiyasi (`make frontend-gen` yoki qo'lda), `VITE_API_URL` bilan remote API'ga ulanish, `src/` katalog strukturasi (`client/` — generatsiyalangan client, `components/`, `hooks/`, `lib/`, `queries/`, `routes/`) va `public/assets`.

---

## Fayllararo bog'lanishlar xulosasi

- `Makefile` → `scripts/setup.sh`, `scripts/generate-client.sh`, ikkala compose fayl, `backend/pyproject.toml` (uv), `frontend/package.json` (npm).
- `docker-compose.local.yml` → `backend/Dockerfile` (context root, `scripts/` ni oladi), `frontend/Dockerfile` (+`VITE_API_URL` / `VITE_API_TIMEOUT_MS` build-arglar); ikkala compose ham → `scripts/prestart.sh` (api command), `.env` / `.env.example`. `docker-compose.prod.yml` build qilmaydi — tayyor `ghcr.io/<owner>/mebelix-mes-*` image'larini oladi (ularni `.github/workflows/ci.yml` dagi `images` job quradi).
- `docker-compose.prod.yml` → `caddy/Caddyfile` (`SITE_ADDRESS` env orqali TLS rejimi) → `api:8000` va `frontend:80` (`frontend/nginx/index.conf`).
- `.pre-commit-config.yaml` → `backend/pyproject.toml` (ruff/mypy config), `frontend/biome.json` (biome hook).
- `.github/workflows/ci.yml` → `backend/pyproject.toml` (uv sync, ruff/mypy), `backend/tests/test_giblab.py`, `frontend/.nvmrc` + `frontend/package-lock.json` (Node versiya va npm cache), `backend/Dockerfile` + `frontend/Dockerfile` → ghcr.io (`images` job), `scripts/deploy.sh` (deploy job — `TAG` + `REGISTRY`), Telegram secrets (notify job).
- `scripts/generate-client.sh` → backend OpenAPI spec → `frontend/src/client/` (frontend va backend orasidagi kontrakt sinxronizatsiyasi).
- Chop etish zanjiri: `backend/app/api/routes/terminal.py` (`POST /terminal/labels/{id}`) → `backend/app/tasks/__init__.py` (`print_label`) → `backend/app/services/labels.py` (`load_label_data` + `render_label_png` + `backend/app/assets/label-*.png`) → Redis `mes:print:queue` → `backend/app/api/routes/ws.py` (`/ws/bridge`, `Authorization: Bearer`) → `bridge-agent/agent.py` (`_print_png_gdi`) → USB GoDEX.
- Agent autentifikatsiyasi: `frontend/src/routes/_layout/printers.tsx` → `backend/app/api/routes/bridge_agents.py` (kod berish, `/pair`, `/download`) → `bridge_agent` jadvali (`token_hash`, `last_seen_at`) → `backend/app/api/routes/ws.py` (`ws_bridge`, `touch_agent`) → `%APPDATA%\MebelixAgent\.env`.
