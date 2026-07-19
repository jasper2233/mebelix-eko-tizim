# 07 — Infra & DevOps (Docker, Caddy, Makefile, scripts, chop etish, CI hooks)

Bu hujjat MebeliX MES loyihasining infratuzilma va DevOps qatlamini tavsiflaydi: Docker Compose stacklari (lokal va production), backend/frontend Dockerfile'lar, Caddy reverse proxy, nginx static server, `Makefile` buyruqlari, yordamchi scriptlar, sexdagi chop etish infratuzilmasi (Chrome kiosk-printing + GoDEX G500-U), pre-commit hooklar, CI/CD va environment konfiguratsiyasi.

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
| `docker-local` / `docker-prod` / `docker-down` / `docker-logs` | compose lifecycle (`docker-prod` `--build` bilan — deploy'da image'lar doim qayta build qilinadi) |
| `clean` | `__pycache__`, `.mypy_cache`, `.ruff_cache` tozalash |

---

## Production flow

### `docker-compose.prod.yml`

Lokaldan asosiy farqlar:

- **Hech qanday servis DB/Redis/API portini hostga ochmaydi** — `api` va `frontend` faqat `expose` qiladi; tashqi dunyoga faqat `caddy` port ochadi, host binding parametrlangan: `${CADDY_HTTP_BIND:-80}:80` va `${CADDY_HTTPS_BIND:-443}:443` (default — to'g'ridan-to'g'ri `80`/`443`).
- **Image'lar `TAG` bilan parametrlangan** — `mebelix-mes-backend:${TAG:-latest}` / `mebelix-mes-frontend:${TAG:-latest}`; CI `TAG` sifatida git sha beradi (rollback uchun, pastda `scripts/deploy.sh`), default `latest` — lokal qo'lda ishga tushirishga. `worker` `api` image'ini qayta ishlatadi — alohida build yo'q.
- **`api`** production serverda ishlaydi:
  ```
  bash -c "/app/scripts/prestart.sh && gunicorn app.main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --forwarded-allow-ips '*'"
  ```
  `--forwarded-allow-ips` flag sifatida beriladi, chunki gunicorn `FORWARDED_ALLOW_IPS` env'ini ham o'qiydi va pydantic'ning JSON list formati (`'["*"]'`) uni yiqitadi. `env_file: .env` orqali to'liq konfiguratsiya, `POSTGRES_SERVER=db` / `REDIS_HOST=redis` override. `restart: always`. Healthcheck: `curl -f http://localhost:8000/api/v1/health` (`start_period: 40s`) — `caddy` shu healthcheck'ka tayanadi.
- **`db` / `redis`** credentiallari defaultsiz — `.env` da majburiy (`${POSTGRES_USER}` va h.k.).
- **`frontend`** `VITE_API_URL=""` (bo'sh string) bilan build qilinadi — generatsiyalangan SDK yo'llari allaqachon `/api/v1` bilan boshlanadi, shuning uchun bo'sh base same-origin so'rovlar beradi va ularni Caddy backendga proxy qiladi (avvalgi `/api` qiymati so'rovlarni `/api/api/v1` ga aylantirib 404 berardi). Qo'shimcha build-arg: `VITE_API_TIMEOUT_MS` (`${VITE_API_TIMEOUT_MS:-30000}`). Healthcheck `wget --spider http://127.0.0.1/` ga qadalgan — konteyner ichida `localhost` `::1` ga ketadi, nginx esa faqat IPv4 tinglaydi.
- **`caddy`** — `caddy:2-alpine`, `./caddy/Caddyfile` read-only mount, `caddy_data` (TLS sertifikatlar) va `caddy_config` volumelari. `SITE_ADDRESS` env (default `:80`). `depends_on`: `api` `service_healthy`, `frontend` `service_started` — Caddy backend tayyor bo'lgandan keyingina start oladi. Healthcheck `http://localhost:8080/healthz` orqali — Caddyfile'dagi alohida `:8080` health blokiga (asosiy `:80` emas, chunki `SITE_ADDRESS` domen bo'lganda `:80` HTTPS'ga avto-redirect qiladi).

Ishga tushirish: `.env` ni production qiymatlar bilan to'ldirish (ayniqsa `SECRET_KEY`, `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SITE_ADDRESS`, `ENVIRONMENT=production`), so'ng `make docker-prod`.

**Mavjud nginx ortida (ISPmanager) ishga tushirish.** Hostda `80`/`443` allaqachon band bo'lsa, Caddy'ni loopback'ka bog'lab TLS'ni host nginx'iga qoldirish mumkin — `.env` ga:

```
CADDY_HTTP_BIND=127.0.0.1:8200
CADDY_HTTPS_BIND=127.0.0.1:8443
SITE_ADDRESS=:80
```

Bunda Caddy oddiy HTTP'da qoladi (sertifikatni nginx tugatadi), host nginx esa saytni `127.0.0.1:8200` ga proxy qiladi. Shu retsept `docker-compose.prod.yml` dagi `ports` izohida ham yozilgan.

### Yuklangan fayllar (`UPLOAD_DIR`) — hozircha volume'siz

Backend yuklangan fayllarni diskka yozadi (`backend/app/core/config.py`: `UPLOAD_DIR: str = "uploads"` — **nisbiy** yo'l, image ichidagi CWD `/app/backend` dan hisoblanadi, ya'ni `/app/backend/uploads`). Katalog tarkibi:

| Kichik katalog | Nima | Yozuvchi |
|---|---|---|
| `projects/` | yuklangan GibLab `.project` fayllari | `upload_order_project` |
| `scx/` | SCX/CNC fayllari | orders route'lari |
| `survey/{order_id}/` | anketa xona rasmlari, nomi `{uuid4().hex}{ext}` | `upload_room_photo` (`POST /orders/{id}/survey/photos`) |

DB'da faqat nisbiy yo'l saqlanadi (`OrderFile.path`), o'qishda `Path(settings.UPLOAD_DIR).resolve() / row.path` bilan qayta yig'iladi.

**Muhim:** hech qaysi compose faylda `uploads` uchun volume yoki bind-mount **yo'q** — `docker-compose.local.yml` faqat `./backend/app` va `./scripts` ni mount qiladi, `docker-compose.prod.yml` esa `api`/`worker` uchun umuman volume bermaydi. CI `rsync` ham `uploads` ni exclude qiladi. Natijada prod'da yuklangan fayllar konteyner qatlamida yashaydi va **har deploy'da (image qayta build + konteyner almashishi) yo'qoladi** — DB'dagi `OrderFile` yozuvlari qoladi, fayl esa yo'q bo'ladi (`download_order_file` "Fayl diskda topilmadi" beradi). Doimiy saqlash kerak bo'lganda `api` ga named volume (`/app/backend/uploads`) qo'shilishi kerak — `uploads/` ga yozish ham, o'qish ham faqat `api` da bo'ladi (`.project` parse, SCX, anketa rasmlari); `worker` bu katalogga tegmaydi.

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
2. **Final stage** — `python:3.13-slim-bookworm`. Healthcheck uchun `curl` o'rnatiladi. Xavfsizlik uchun **non-root `app` user** (uid/gid 1000). Builderdan `/app/backend/.venv`, `/app/backend`, `/app/scripts` ko'chiriladi. `PATH` ga venv qo'shiladi, `PYTHONPATH=/app/backend`. Default `CMD` — `uvicorn app.main:app --host 0.0.0.0 --port 8000`, lekin ikkala compose ham buni override qiladi (dev: reload'li uvicorn; prod: gunicorn; worker: arq).

Muhim: build context — **repo root** (`context: .`), chunki image'ga `scripts/` ham kiradi (`prestart.sh` shu yerdan ishlaydi).

### `frontend/Dockerfile` — multi-stage, Node → nginx

1. **build-stage** — `node:24-alpine` (versiya `frontend/.nvmrc` dagi `24` bilan mos). `package*.json` avval ko'chiriladi → `npm ci` (layer caching), keyin kod. `ARG VITE_API_URL` va `ARG VITE_API_TIMEOUT_MS` (default `30000`) build vaqtida env'ga aylanadi — Vite build'ga statik ravishda "pishiriladi" (shuning uchun lokal va prod composelar turli `VITE_API_URL` bilan alohida build qiladi). `npm run build` → `tsc && vite build` → `dist/`.
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

CI chaqiradi: `TAG=<git sha> bash scripts/deploy.sh`. Oqim: build (yiqilsa eski stack joyida qoladi) → yangi `TAG` ga switch (`docker compose up -d`) → smoke. Smoke `SMOKE_URL` ga uradi (default `http://127.0.0.1:8200/api/v1/ready`) — `/api/v1/ready` DB+Redis'ni tekshiruvchi readiness probe (`/api/v1/health` dan farqli, u faqat process tirikligini aytadi); CI'ning public smoke'i ham shu endpointga uradi. Smoke o'tsa `TAG` `.stable_tag` fayliga yoziladi va eski image'lar tozalanadi (joriy + oldingi stable qoladi); yiqilsa `.stable_tag` dagi oxirgi barqaror tag'ga avto-rollback qilinadi. **Muhim qoida: rollback DB'ni pastga tushirmaydi — migratsiyalar additive bo'lishi shart** (ustun/jadval qo'shish; eski kod yangi ustunlarga chidashi kerak).

### `scripts/backup.sh` — kunlik shifrlangan DB backup

Server cron'ida kunlik ishlaydi (`0 2 * * *`). Oqim: `pg_dump` (db konteyneri ichida) | `gzip` | `openssl aes-256-cbc -pbkdf2` (parol — `.env` dagi `ADMIN_PASSWORD`), so'ng natija Telegram'ga document sifatida yuboriladi. `.env` dan tashqari `.backup.env` fayli kerak (`TG_BOT_TOKEN`, `TG_CHAT_ID`). Ochish: `openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc | gunzip > dump.sql`.

---

## Chop etish infratuzilmasi — Chrome kiosk-printing va GoDEX G500-U

GoDEX G500-U faqat **USB** bilan ishlaydi va yorliqni printer yonidagi odam — arrachi o'z monoblogida — bosadi. Masofaviy chop etish talab qilinmaydi, shuning uchun butun oqim brauzerda kechadi: **printerli kompyuterga qo'shimcha dastur o'rnatilmaydi**, GoDEX drayveri va Chrome yetarli.

### Zanjir (uchdan-uchgacha)

```
Arrachi monoblok — "Chop etish" tugmasi     (frontend/src/components/Terminal/CutmapView.tsx)
  ├── printLabelPng(instance_id)
  │     yashirin iframe (srcdoc, @page{size:80mm 60mm;margin:0})
  │       <img crossorigin="use-credentials"
  │            src="{BASE}/api/v1/terminal/labels/{instance_id}.png">
  │       img yuklangach → win.focus() → win.print()
  │         → Chrome --kiosk-printing bo'lsa DIALOGSIZ standart printerga (USB GoDEX)
  │       2 s dan keyin iframe DOM'dan o'chiriladi
  └── POST /api/v1/terminal/labels/{instance_id}    (backend/app/api/routes/terminal.py)
        ├── instance.label_printed_at = now()
        └── ws_manager.publish("label.printed", {instance_id, qr_text})  → TABLO va boshqa brauzerlar

GET /api/v1/terminal/labels/{instance_id}.png        (backend/app/api/routes/terminal.py)
  load_label_data(db, instance_id) → render_label_png(data) → Response(image/png)
                                                     (backend/app/services/labels.py)
```

Ikki so'rov **parallel** ketadi: POST faqat holatni yozib TABLO'ga xabar beradi, qog'ozga chiqarish esa iframe ichida brauzerning o'z print yo'li bilan bo'ladi. Chop etish ARQ'ga umuman tegmaydi — `backend/app/tasks/__init__.py` da faqat `ping` bor (ARQ hech bo'lmasa bitta registratsiyalangan funksiya talab qiladi), `worker` servisi yorliqda ishtirok etmaydi.

Rasm `crossorigin="use-credentials"` bilan olinadi — endpoint `TerminalUser` autentifikatsiyasini talab qiladi, iframe esa cookie'ni shu atribut bilan yuboradi.

### Monoblokni sozlash (bir martalik)

1. GoDEX G500-U USB'ga ulanadi, drayveri o'rnatiladi va **standart printer** qilib qo'yiladi (Printers & scanners → Set as default) — `--kiosk-printing` aynan standart printerga yuboradi.
2. Drayver sozlamalarida qog'oz o'lchami **80×60 mm** qilinadi (Printing preferences → Stock/Paper). Iframe `@page{size:80mm 60mm;margin:0}` beradi, lekin drayverdagi stock mos kelmasa yorliq siljib chiqadi.
3. Chrome yorlig'i shu bayroqlar bilan ochiladi:

```
chrome.exe --kiosk-printing --kiosk https://mes.mebelix.uz/terminal
```

`--kiosk-printing` chop etish dialogini butunlay olib tashlaydi — `window.print()` to'g'ridan-to'g'ri standart printerga ketadi. Bayroqsiz oqim baribir ishlaydi, lekin har yorliqda dialog chiqadi va operator "Print" bosishi kerak. `--kiosk` esa terminalni to'liq ekranda ushlaydi (frontend'ning o'z fullscreen darvozasi `display-mode: fullscreen` ni ham tan oladi, `frontend/src/routes/terminal.tsx`).

Avtostart: yorliq `shell:startup` katalogiga qo'yiladi.

### Yorliq PNG — bitta render yo'li

`backend/app/services/labels.py` da `LabelData` (DB'dan `load_label_data` bilan yig'iladi) va undan chiqadigan yagona format:

| Funksiya | Chiqish |
|---|---|
| `render_label_png(d, scale=1)` | 80×60 mm, 203 dpi (8 dot/mm → 640×480 px), **1-bit** PNG |

PNG maketi GibSaw `mebelix.lbl` ga taqlid qiladi: chap ustun — logo, `Formatka` + zakaz kodi, detal kodi, loyiha nomi, 2×2 kromka jadvali (tagchiziq bilan), katta `L x W = count`, `N_detal` nomi, XNC belgilari (`П`=paz, `Ф`=freza), material va sana; o'ng ustun — QR (tepada, `qrcode` kutubxonasi bilan chiziladi) va vertikal detal eskizi. Eskizda kromka konturdan 1 mm tashqarida qalin chiziq bilan, `d.texture` bo'lsa uzunlik bo'ylab 3 ta chiziq, `d.holes` (cutmap'dan olingan haqiqiy teshiklar) aylana/qirra tikkalari bilan chiziladi.

Termoprinter uchun ikki qat'iy qoida kodga o'rnatilgan: `draw.fontmode = "1"` (antialiasing o'chiq) va yakuniy `img.convert("L").point(… , "1")` — har piksel sof qora yoki oq. Aks holda drayver dither qiladi va QR skanerlanmay qoladi. Shuningdek barcha chiziqlar `width=max(2, scale)` — drayver rasmni kichraytirganda 1 px chiziq yo'qolib ketadi.

**Assetlar** (`backend/app/assets/`, image ichiga `COPY backend /app/backend` bilan tushadi):

| Fayl | Qayerda |
|---|---|
| `label-logo.png` | yorliq tepa-chapida, 160 threshold bilan 1-bit qilinadi; ochib bo'lmasa `MEBELIX` matni fallback |
| `label-icon-drill.png` | teshik bor detallarda sverlo ikonkasi (alpha oq fonga flatten qilinadi); ochib bo'lmasa `С` harfi fallback |

**Shrift eslatmasi.** `_FONT_REGULAR` / `_FONT_BOLD` ro'yxatlari Windows (`C:/Windows/Fonts/arial.ttf`, `arialbd.ttf`) va Debian DejaVu yo'llarini sinab ko'radi, hech biri topilmasa `ImageFont.load_default()` ga tushadi. `backend/Dockerfile` final stage'ida faqat `curl` o'rnatiladi — `fonts-dejavu-core` yo'q. PNG server tomonda (`GET /labels/{id}.png`) render qilingani uchun yorliq TTF shriftda chiqishi kerak bo'lsa, image'ga shrift paketi qo'shilishi shart.

### Yorliqdan tashqari chiqish yo'llari

- **SCX/CNC fayllar** — stanok kompyuterida brauzer orqali `GET /api/v1/terminal/files/{file_id}` bilan yuklab olinadi (TZ 12.5), yorliq yo'liga aloqasi yo'q.
- **Kesish xaritalari** — `CutmapView` dagi `printAllMaps()` yangi oyna ochib har listni o'z sahifasida chiqaradi (`@page{size:A4 landscape;margin:8mm}`): bu yorliq printeri emas, oddiy A4 printer uchun.

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

`main` ga push va har bir pull request'da ishga tushadi; to'rtta job — `backend` va `frontend` parallel, `deploy` ularga bog'liq, `notify` uchalasiga:

| Job | Qadamlar |
|---|---|
| `backend` | `astral-sh/setup-uv` → `uv --project backend sync --all-groups` → `ruff check app` + `ruff format --check app` → `mypy app` → `python -m tests.test_giblab` (GibLab parser testlari) |
| `frontend` | `actions/setup-node` (versiya `frontend/.nvmrc` dan, npm cache) → `npm ci` → `npx biome ci .` → `npm run build` (`tsc && vite build`) |
| `deploy` | faqat `main` ga push + ikkala job yashil bo'lsa (`needs: [backend, frontend]`); `concurrency: prod-deploy` (parallel deploy yo'q). Qadamlar: SSH key setup → `rsync` kodni `root@DEPLOY_HOST:/opt/mebelix-mes` ga (`.git`/`node_modules`/`.venv`/`__pycache__`/`dist`/`uploads`/`.env` exclude) → `ssh` orqali `TAG=<git sha> bash scripts/deploy.sh` → public smoke `https://mes.mebelix.uz/api/v1/ready` (nginx/TLS yo'li orqali). Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST` |
| `notify` | `if: always() && push && ref == main`, `needs: [backend, frontend, deploy]` — Telegram xabari. Secrets: `TG_BOT_TOKEN`, `TG_CHAT_ID` |

**Nega `notify` alohida job.** Avval u `deploy` ichida `if: always()` qadami edi. Lekin `backend` yoki `frontend` yiqilsa `deploy` butunlay **skipped** bo'ladi — skip qilingan job'ning qadamlari umuman ishlamaydi, ya'ni CI yiqilganda xabar hech kimga bormasdi. Endi `notify` mustaqil job va uchala natijani `needs.<job>.result` orqali env'da oladi (`BACKEND`, `FRONTEND`, `DEPLOY`):

| `DEPLOY` natijasi | Xabar |
|---|---|
| `success` | `✅ MebeliX deploy OK` |
| `skipped` | `❌ MebeliX CI YIQILDI (deploy boshlanmadi) — backend: …, frontend: …` |
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
| `ENABLE_REDIS_QUEUE` | `True` | ARQ queue yoqilgan/o'chiq |
| `ENABLE_REDIS_RATE_LIMIT` | `True` | Redis-based rate limiting |
| `DEFAULT_RATE_LIMIT_LIMIT` / `DEFAULT_RATE_LIMIT_PERIOD` | `10` / `3600` | Umumiy rate limit (so'rov / sekund oynasi) |
| `LOGIN_RATE_LIMIT_ATTEMPTS` / `LOGIN_RATE_LIMIT_PERIOD` | `5` / `300` | Login urinishlari limiti |
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

Eslatma: chop etish uchun serverda **hech qanday env yo'q** — printer sozlamasi butunlay monoblok tomonda (standart printer + Chrome `--kiosk-printing`, yuqoridagi "Chop etish infratuzilmasi" bo'limi).

Eslatma: `CADDY_HTTP_BIND` / `CADDY_HTTPS_BIND` `.env.example` da yo'q — ular `docker-compose.prod.yml` dagi compose-level substitutsiyalar (defaultlari `80` / `443`); behind-nginx rejimida `.env` ga qo'lda qo'shiladi. `TAG` ham shu kategoriyada — compose-level substitutsiya (default `latest`), CI uni git sha bilan beradi.

---

## Yordamchi konfiguratsiya fayllari

### `.dockerignore`

Docker build contextdan chiqariladi: `.git`, barcha `.env` va `.venv` lar, `__pycache__`, `frontend/node_modules`, `frontend/dist`, `docker-compose*.yml`. Bu image'ga secretlar va keraksiz artefaktlar kirmasligini va build tezligini ta'minlaydi (backend build contexti repo root bo'lgani uchun ayniqsa muhim).

### `.gitattributes`

Bitta qoida: `* text=auto eol=lf` — barcha matn fayllar LF line-ending bilan normalizatsiya qilinadi (Windows/Linux aralash muhitda script va Dockerfile'lar buzilmasligi uchun).

### `.gitignore`

Standart Python artefaktlari (`__pycache__`, egg/build/dist), virtualenvlar (`.venv`, `backend/.venv`), **`.env` fayllar** (secretlar repoga tushmaydi), test/lint cache (`.mypy_cache`, `.ruff_cache`, `.coverage`), IDE fayllari (`.vscode/*` lekin `settings.json`/`launch.json`/`extensions.json` istisno), `backend/app/logs/*.log`. MES runtime artefaktlari ham ignore: `backend/uploads/` (`projects/`, `scx/`, `survey/` — yuklangan fayllar va anketa xona rasmlari), `frontend/openapi.json`, hamda lokal sex ma'lumotlari `uploads/` (repo root'da: `.project`/SCX namunalari va `forma/mebel_buyurtma_anketa.html` — anketaning qog'oz manbasi) va `chek/` (namuna yorliq fotolari, `labels.py` maketi shulardan olingan). E'tiborli nuqta: `**/lib/` ignore qilinadi, lekin `!frontend/src/lib/` istisno (shadcn util katalogi).

---

## Til/versiya manifestlari

### `backend/pyproject.toml`

`mebelix-backend` 0.1.0, `requires-python >=3.11, <3.14`, build-backend `hatchling` (faqat `app/` package). Asosiy runtime dependencylar: `fastapi`, `uvicorn` + `uvloop`, `gunicorn`, `SQLAlchemy` 2 + `asyncpg` + `alembic`, `pydantic`/`pydantic-settings`, `pyjwt[crypto]` + `bcrypt`, `redis` + `arq` (queue/worker), `prometheus-fastapi-instrumentator` (metrics), `uuid6`, `httpx`, `python-multipart` (fayl yuklash: `.project`, SCX, anketa rasmlari), `openpyxl` (Excel), `pillow` + `qrcode` (`render_label_png` — yorliq PNG), `tzdata` (`ZoneInfo("Asia/Tashkent")` yorliq sanasi uchun). Dev group: `mypy`, `ruff`, `pre-commit`, `types-redis`, `types-openpyxl`, `websockets`. Tooling konfiguratsiyasi shu faylda: **ruff** (`target-version py311`, line-length 120, `F/E/W/C/UP/I` rulesetlar, `__init__.py` da unused/star import istisno) va **mypy** (`python_version 3.11`, `app.*` uchun `disallow_untyped_defs = true`).

### `frontend/package.json` va `frontend/.nvmrc`

`.nvmrc` — `24` (Dockerfile'dagi `node:24-alpine` bilan sinxron; `nvm use` / `fnm use` uchun). `package.json` scriptlari: `dev` (vite), `build` (`tsc && vite build`), `lint` (biome, `--write --unsafe`), `preview`, `generate-client` (`openapi-ts`). Stack: React 19, TanStack Router/Query/Table, Tailwind CSS 4, Radix UI, react-hook-form + zod, axios, sonner; dev tomonda Biome, `@hey-api/openapi-ts`, Vite 8 + SWC, TypeScript 6 (7 emas — sabab `docs/08-packages.md` da).

### `backend/README.md`

Backend dev qo'llanmasi: texnologiyalar ro'yxati, `make setup` yoki qo'lda setup (`uv sync`, `.env`, migratsiyalar, superuser, seed), ishga tushirish (`make run-backend` / `make docker-local`), ARQ worker, test/lint/migratsiya buyruqlari. `docs/07-infra-devops.md` va `docs/09-mes-domain.md` ga yo'naltiradi.

### `LICENSE.md`

Repo root'da — **MIT License**, copyright (c) 2026 Olimbek Nizomov. `backend/pyproject.toml` dagi `license = { text = "MIT" }` shu bilan mos.

### `frontend/README.md`

Frontend dev qo'llanmasi: nvm/fnm bilan Node o'rnatish, `npm install` + `npm run dev` (port 5173), Docker'siz lokal dev tavsiyasi, OpenAPI client generatsiyasi (`make frontend-gen` yoki qo'lda), `VITE_API_URL` bilan remote API'ga ulanish, `src/` katalog strukturasi (`client/` — generatsiyalangan client, `routes/`, `components/`, `hooks/`).

---

## Fayllararo bog'lanishlar xulosasi

- `Makefile` → `scripts/setup.sh`, `scripts/generate-client.sh`, ikkala compose fayl, `backend/pyproject.toml` (uv), `frontend/package.json` (npm).
- `docker-compose.*.yml` → `backend/Dockerfile` (context root, `scripts/` ni oladi), `frontend/Dockerfile` (+`VITE_API_URL` / `VITE_API_TIMEOUT_MS` build-arglar), `scripts/prestart.sh` (api command), `.env` / `.env.example`.
- `docker-compose.prod.yml` → `caddy/Caddyfile` (`SITE_ADDRESS` env orqali TLS rejimi) → `api:8000` va `frontend:80` (`frontend/nginx/index.conf`).
- `.pre-commit-config.yaml` → `backend/pyproject.toml` (ruff/mypy config), `frontend/biome.json` (biome hook).
- `.github/workflows/ci.yml` → `backend/pyproject.toml` (uv sync, ruff/mypy), `backend/tests/test_giblab.py`, `frontend/.nvmrc` + `frontend/package-lock.json` (Node versiya va npm cache), `scripts/deploy.sh` (deploy job), Telegram secrets (notify job).
- `scripts/generate-client.sh` → backend OpenAPI spec → `frontend/src/client/` (frontend va backend orasidagi kontrakt sinxronizatsiyasi).
- Chop etish zanjiri: `frontend/src/components/Terminal/CutmapView.tsx` (`printLabelPng` — yashirin iframe + `window.print()`) → `backend/app/api/routes/terminal.py` (`GET /terminal/labels/{id}.png`) → `backend/app/services/labels.py` (`load_label_data` + `render_label_png` + `backend/app/assets/label-*.png`) → Chrome `--kiosk-printing` → USB GoDEX. Parallel: `POST /terminal/labels/{id}` → `label_printed_at` + `ws_manager.publish("label.printed")` → `backend/app/api/routes/ws.py` (`/ws/events`) → TABLO.
