# 07 — Infra & DevOps (Docker, Caddy, Makefile, scripts, chop etish, CI hooks)

Bu hujjat MebeliX MES loyihasining infratuzilma va DevOps qatlamini tavsiflaydi: Docker Compose stacklari (lokal va production), backend/frontend Dockerfile'lar, Caddy reverse proxy, nginx static server, `Makefile` buyruqlari, yordamchi scriptlar, tsexdagi chop etish infratuzilmasi (bridge-agent + GoDEX), pre-commit hooklar, CI/CD va environment konfiguratsiyasi.

## Umumiy arxitektura

Stack ikki rejimda ishlaydi:

| Rejim | Compose fayl | Kirish nuqtasi | App server | TLS |
|---|---|---|---|---|
| Lokal (dev) | `docker-compose.local.yml` | `8000`/`3000` hostga ochiq; `5432`/`6379` faqat loopback (`127.0.0.1`) | `uvicorn --reload` | yo'q |
| Production | `docker-compose.prod.yml` | faqat Caddy (default `:80`/`:443`; `CADDY_HTTP_BIND`/`CADDY_HTTPS_BIND` bilan o'zgartiriladi); `api`/`frontend` faqat `expose`, `db`/`redis` umuman port ochmaydi | `gunicorn` + `UvicornWorker` | Caddy auto-HTTPS (Let's Encrypt) |

Servislar: `db` (PostgreSQL 15), `redis` (Redis 7, ARQ queue + rate limit), `api` (FastAPI), `worker` (ARQ background worker), `frontend` (Vite build + nginx), production'da qo'shimcha `caddy` (reverse proxy + TLS).

So'rov oqimi (production):

```
Client → Caddy (:80/:443)
           ├── /api*, /docs*, /redoc*, /openapi.json → api:8000 (FastAPI)
           ├── /metrics → har doim 403 (Prometheus tashqariga umuman chiqmaydi)
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

Bu rejimda `POSTGRES_SERVER=localhost` va `REDIS_HOST=localhost` bo'lishi kerak (`.env.example` dagi default). DB/Redis'ni konteynerdan olish mumkin: `docker-compose.local.yml` ular portlarini faqat loopback'ka ochadi (`127.0.0.1:5432`, `127.0.0.1:6379` — dev mashina tsex tarmog'ida bo'lgani uchun default parolli Postgres/parolsiz Redis tarmoqqa chiqmaydi). `frontend/README.md` ham aynan shu workflow'ni tavsiya qiladi — Docker image'ni har o'zgarishda qayta build qilish samarasiz, live reload bilan lokal server yaxshiroq.

### 2-yo'l: konteynerlashgan dev — `docker-compose.local.yml`

`make docker-local` → `docker compose -f docker-compose.local.yml up -d`. Xususiyatlari:

- **`db`** — `postgres:15-alpine`, `postgres_data` named volume, `pg_isready` healthcheck, port `127.0.0.1:5432:5432` — faqat loopback. Credentiallar defaultli: `${POSTGRES_USER:-postgres}` va h.k.
- **`redis`** — `redis:7-alpine`, `redis_data` volume, `redis-cli ping` healthcheck, port `127.0.0.1:6379:6379` (faqat loopback).
- **`api`** — `backend/Dockerfile` dan build (context = repo root). Command:
  ```
  bash -c "/app/scripts/prestart.sh && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
  ```
  Ya'ni avval migratsiya + superuser + default seedlar (`scripts/prestart.sh`), keyin hot-reload uvicorn. **Bind-mountlar** hot-reload uchun: `./backend/app`, `./scripts`. `.env` esa bind-mount emas, `env_file: .env` orqali yuklanadi — fayl yo'q bo'lsa compose aniq xato beradi (bind-mount holatida Docker jimgina bo'sh katalog yaratardi). `POSTGRES_SERVER=db`, `REDIS_HOST=redis` environment orqali override qilinadi (`.env` dagi `localhost` ni yengadi). Healthcheck: `curl -f http://localhost:8000/api/v1/health`, `start_period: 40s`. `db` va `redis` `service_healthy` bo'lgandan keyingina start oladi.
- **`worker`** — xuddi shu image, command: `arq app.core.worker.WorkerSettings --custom-log-dict app.core.logger.ARQ_LOG_DICT` (bayroqsiz arq log yozuvlari plain matn + JSON bo'lib ikki marta chiqadi), xuddi shu mountlar va env (`build` + `command` + `env_file` + `volumes` + `environment` + `depends_on`). Lokal composeda worker uchun **healthcheck yo'q** — u faqat `docker-compose.prod.yml` da (pastdagi "Production flow" bo'limi).
- **`frontend`** — `frontend/Dockerfile` dan build, build-arglar: `VITE_API_URL` (default `http://localhost:8000` — brauzer API'ga to'g'ridan-to'g'ri boradi) va `VITE_API_TIMEOUT_MS` (default `30000`), port `3000:80`.

Lokal composeda Caddy yo'q — frontend nginx'i to'g'ridan-to'g'ri `3000` portda, API `8000` da.

### Kundalik dev buyruqlari (`Makefile`)

`Makefile` (root) `PYTHONPATH := backend` ni export qiladi va `uv --project backend` orqali backend virtualenv'idan foydalanadi. `make help` — barcha targetlar ro'yxati (`##` izohlaridan avtogeneratsiya).

| Target | Vazifasi |
|---|---|
| `setup` | `scripts/setup.sh` + `install-hooks` |
| `install` / `frontend-install` | `uv sync` / `npm install` |
| `run-backend` / `run-frontend` / `worker` | dev serverlar va ARQ worker |
| `lint` / `format` | `ruff check --no-fix app` + `ruff format --check app` + `mypy app` (`backend/` dan, CI bilan aynan bir xil — `--no-fix` SHART: `pyproject.toml` da `fix = true`, usiz `ruff check` xatoni jimgina tuzatib exit 0 qaytaradi) / `ruff format app` + `ruff check app --fix` — ikkalasi ham `backend/` dan va bir xil qamrovda (`app/`), ya'ni `format` faqat CI tekshiradigan fayllarni o'zgartiradi |
| `frontend-lint` / `frontend-format` / `frontend-build` | `npx biome ci .` — CI bilan aynan bir xil, TEKSHIRUV (hech narsani yozmaydi) / `npm run lint` = `biome check --write --unsafe` — YOZADI, tuzatish uchun / `npm run build` |
| `frontend-gen` | `scripts/generate-client.sh` — OpenAPI → TS client |
| `migrate` / `makemigrations m="msg"` / `check-migrations` | `alembic upgrade head` / `alembic revision --autogenerate` / `alembic upgrade head && alembic check` — model↔migratsiya drifti, ishlab turgan DB kerak; CI ham aynan shuni chaqiradi |
| `cmd n="name"` | `python -m app.commands.<name>` — custom CLI commandlar |
| `docker-local` / `docker-prod` / `docker-down` / `docker-logs` | compose lifecycle (`docker-prod` endi `pull` + `up -d` — prod image'lar CI'da quriladi, serverda build yo'q) |
| `clean` | `__pycache__`, `.mypy_cache`, `.ruff_cache` tozalash |

---

## Production flow

### `docker-compose.prod.yml`

Lokaldan asosiy farqlar:

- **Hech qanday servis DB/Redis/API portini hostga ochmaydi** — `api` va `frontend` faqat `expose` qiladi; tashqi dunyoga faqat `caddy` port ochadi, host binding parametrlangan: `${CADDY_HTTP_BIND:-80}:80` va `${CADDY_HTTPS_BIND:-443}:443` (default — to'g'ridan-to'g'ri `80`/`443`).
- **Prod composeda `build:` bo'limlari yo'q — image'lar tayyor holda registrydan olinadi.** `${REGISTRY:-ghcr.io/dshukriddinov}/mebelix-mes-backend:${TAG:-latest}` (`api` va `worker` bittasini bo'lishadi) va `${REGISTRY:-ghcr.io/dshukriddinov}/mebelix-mes-frontend:${TAG:-latest}`. CI ikkala qiymatni ham beradi — `REGISTRY=ghcr.io/<owner>` va `TAG=<git sha>` (git sha rollback uchun, pastda `scripts/deploy.sh`); `TAG` defaulti — `latest`, uni `images` job har main-push'da sha bilan bir manifestga qo'shib push qiladi, ya'ni `latest` = main'ning oxirgi CI build'i (TAG'siz `make docker-prod` shunga tayanadi). Image'larni GitHub Actions quradi va ghcr.io ga yuboradi (`images` job, pastda CI bo'limi), server faqat `pull` qiladi. Lokal build `docker-compose.local.yml` da qoladi — u o'z `build:` bo'limlarini saqlab qolgan.
- **`api`** production serverda ishlaydi:
  ```
  bash -c "/app/scripts/prestart.sh && gunicorn app.main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --forwarded-allow-ips '${GUNICORN_FORWARDED_ALLOW_IPS:-172.16.0.0/12}'"
  ```
  `--forwarded-allow-ips` flag sifatida beriladi, chunki gunicorn `FORWARDED_ALLOW_IPS` env'ini ham o'qiydi va pydantic'ning JSON list formati (`'["172.16.0.0/12"]'`) uni yiqitadi — shuning uchun flagning o'z o'zgaruvchisi `GUNICORN_FORWARDED_ALLOW_IPS` (oddiy satr, JSON emas, default `172.16.0.0/12`). `env_file: .env` orqali to'liq konfiguratsiya, `POSTGRES_SERVER=db` / `REDIS_HOST=redis` override. `restart: always`. Healthcheck: `curl -f http://localhost:8000/api/v1/health` (`start_period: 40s`) — `caddy` shu healthcheck'ka tayanadi.
- **`worker`** — `api` bilan aynan bir xil image, command: `arq app.core.worker.WorkerSettings --custom-log-dict app.core.logger.ARQ_LOG_DICT` (bayroq arq loggerini root JSON handlerga propagate qiladi — busiz har qator ikki marta chiqadi), `restart: always`. Lokaldan farqli o'laroq prodda healthcheck bor: `arq app.core.worker.WorkerSettings --check` (`interval: 30s`, `start_period: 40s` — `api` bilan bir xil, worker startda DB ulanishini kutadi). U Redis'dagi worker yozuvini o'qiydi, yozuvni esa worker `WorkerSettings.health_check_interval = 30` bo'yicha yangilab turadi (`backend/app/core/worker.py`; arq defaulti 3600s — bir soat, unda yangi ko'tarilgan worker soat davomida "unhealthy" ko'rinardi). Busiz worker jimgina o'lsa ham konteyner `up` bo'lib turardi: chek chiqarish navbati to'xtaydi, lekin deploy ham, monitoring ham buni ko'rmasdi.
- **`db` / `redis`** credentiallari defaultsiz — `.env` da majburiy (`${POSTGRES_USER}` va h.k.). Prod `redis` bundan tashqari `command:` bilan ishga tushadi: `--appendonly yes --appendfsync everysec --maxmemory-policy noeviction` — chek navbati (`mes:print:queue:{agent_id}`) ma'lumot, kesh emas: sukutdagi RDB snapshot restartda soniyalab ish yo'qotardi (chiqib bo'lgan yorliq qayta chiqar, kutilayotgani yo'qolardi), `noeviction` esa xotira siqilganda navbatni o'chirtirmaydi.
- **`frontend`** `VITE_API_URL=""` (bo'sh string) bilan build qilinadi — generatsiyalangan SDK yo'llari allaqachon `/api/v1` bilan boshlanadi, shuning uchun bo'sh base same-origin so'rovlar beradi va ularni Caddy backendga proxy qiladi (avvalgi `/api` qiymati so'rovlarni `/api/api/v1` ga aylantirib 404 berardi). `VITE_*` build-arglar (`VITE_API_URL=` va `VITE_API_TIMEOUT_MS=30000`) endi compose faylida emas, CI'ning `images` job'ida beriladi — prod uchun ular belgilanadigan yagona joy. Compose'da alohida healthcheck yo'q — image'ning o'z `HEALTHCHECK`i (`frontend/Dockerfile`: `wget --spider http://127.0.0.1/`) yagona manba.
- **`caddy`** — `caddy:2-alpine`, `./caddy` **katalogi** `/etc/caddy` ga read-only mount (`- ./caddy:/etc/caddy:ro`), `caddy_data` (TLS sertifikatlar) va `caddy_config` volumelari. Mount ataylab katalog, fayl emas: `rsync` faylni almashtirganda yangi inode yaratadi, fayl-mount esa eskisiga bog'langan qolardi — prodda Caddy 3 hafta eski Caddyfile bilan ishlagan va `caddy reload` ham o'sha eskisini qayta yuklardi. Katalog mountda inode o'zgarmaydi, ichidagi fayl esa doim ko'rinadi (`scripts/deploy.sh` ham `--config /etc/caddy/Caddyfile` deb katalog ichidagi faylga murojaat qiladi). `SITE_ADDRESS` env (default `:80`). `depends_on`: `api` `service_healthy`, `frontend` `service_started` — Caddy backend tayyor bo'lgandan keyingina start oladi. Healthcheck `http://localhost:8080/healthz` orqali — Caddyfile'dagi alohida `:8080` health blokiga (asosiy `:80` emas, chunki `SITE_ADDRESS` domen bo'lganda `:80` HTTPS'ga avto-redirect qiladi).

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

Backend yuklangan fayllarni diskka yozadi (`backend/app/core/config.py`: `UPLOAD_DIR: str = "uploads"` — **nisbiy** yo'l, `backend/` paket ildizidan hisoblanadi, image ichida bu `/app/backend`, ya'ni `/app/backend/uploads`). Katalog tarkibi:

| Kichik katalog | Nima | Yozuvchi |
|---|---|---|
| `projects/` | yuklangan GibLab `.project` fayllari | `upload_order_project` |
| `scx/` | SCX/CNC fayllari | orders route'lari |
| `survey/{order_id}/` | anketa xona rasmlari, nomi `{uuid4().hex}{ext}` | `upload_room_photo` (`POST /orders/{id}/survey/photos`) |

(`agent/` katalogi endi ishlatilmaydi — u eski tarqatish oqimidan qolgan. `mebelix-agent.exe` ni hozir CI quradi va deploy uni `UPLOAD_DIR` dan tashqaridagi `agent-dist/` ga qo'yadi — `docker-compose.prod.yml` uni `api` konteynerga read-only mount qiladi (`- ./agent-dist:/app/backend/agent-dist:ro`), `GET /api/v1/bridge-agents/download` esa shu yerdan beradi; pastdagi "Agent o'rnatish" bo'limi.) **PyInstaller versiyasi CI'da qotirilgan** (`pyinstaller==6.22.2`): 6.22 bootloader'i onefile bola jarayonida OTA exe'ni tekshira boshladi (GHSA-9fxf-4qw3-ghmr) va `.bat` orqali qayta ishga tushgan agent «Security validation failure: failed to obtain executable path for parent process!» bilan yiqildi (2026-08-28, Prisadka/Arra). Agent v1.4.7 `_spawn_bat` da `_PYI_*` env'ni tozalaydi; versiya ko'tarilsa restart oqimi tsex kompyuterida qayta sinaladi.

DB'da faqat nisbiy yo'l saqlanadi (`OrderFile.path`), o'qishda `upload_root() / row.path` bilan qayta yig'iladi (`upload_root()` — `app/core/config.py` dagi helper: nisbiy `UPLOAD_DIR` ni `backend/` paket ildiziga bog'lab `resolve()` qiladi — CWD'ga emas, ya'ni ildiz xizmat qayerdan ishga tushirilganiga bog'liq emas; path-traversal tekshiruvlari ham shu root'ga nisbatan).

**Prod'da doimiylik:** `docker-compose.prod.yml` da `api` xizmati `uploads_data` named volume'ini `/app/backend/uploads` ga mount qiladi. Mount nuqtasining o'zi image'da oldindan yaratilgan va `app:app` ga tegishli (`backend/Dockerfile` dagi `mkdir -p` + `chown`) — busiz Docker bo'sh volume'ni `root:root` bilan yaratar, uid 1000 ostidagi konteyner esa unga yozolmasdi (pastdagi "Dockerfile'lar" bo'limi). Volume bo'lmaganda fayllar konteyner qatlamida qolar va **har deploy'da (yangi image + konteyner almashishi) yo'qolar edi** — DB'dagi `OrderFile` yozuvlari qolib, fayl yo'q bo'lardi (`download_order_file` "Fayl diskda topilmadi" beradi). `worker` ga mount berilmagan: arq tasklari (`print_label`) faylga tegmaydi, yorliq DB ma'lumotidan chiziladi — `UPLOAD_DIR` ni faqat `api` route'lari o'qiydi.

`docker-compose.local.yml` faqat `./backend/app` va `./scripts` ni mount qiladi — `uploads` uchun na bind-mount, na volume bor, ya'ni `make docker-local` rejimida yuklangan fayllar konteynerning yozuvchi qatlamida (`/app/backend/uploads`) qoladi va konteyner qayta yaratilganda yo'qoladi (lokal sinov uchun ataylab shunday). Hostda ishlaganda (`make run-backend`, CWD = repo ildizi) fayllar baribir `backend/uploads/` ga tushadi: nisbiy `UPLOAD_DIR` paket ildiziga bog'langan, ya'ni konteyner bilan bir xil joyga (`.gitignore` da `uploads/` ham, `backend/uploads/` ham bor). CI `rsync` `uploads` ni exclude qiladi, ya'ni deploy serverdagi fayllarga tegmaydi.

### `caddy/Caddyfile` — reverse proxy va TLS

Site bloki `{$SITE_ADDRESS::80}` — env-driven listener:

- `:80` (default) → oddiy HTTP (boshqa proxy ortida yoki lokal sinov uchun);
- `your-domain.com` → Caddy **avtomatik Let's Encrypt sertifikat** oladi va `:443` da tinglaydi;
- `your-domain.com:8443` → custom port, TLS baribir provision qilinadi.

Blok ichida: security headerlar (`X-Frame-Options SAMEORIGIN`, `X-Content-Type-Options nosniff` — `X-XSS-Protection` olib tashlandi: barcha hozirgi brauzerlar uni e'tiborsiz qoldiradi), `encode gzip`, so'ng routing:

| Handle | Upstream | Izoh |
|---|---|---|
| `/api*` | `api:8000` | qo'lda `header_up` yo'q — `Host` passthrough va `X-Forwarded-For`/`X-Forwarded-Proto` ni Caddy `reverse_proxy` o'zi default qo'yadi, backend esa faqat shularni o'qiydi |
| `/docs*`, `/redoc*`, `/openapi.json` | `api:8000` | API hujjatlari |
| `/metrics` | — (`403`) | Prometheus — upstream'ga umuman uzatilmaydi, `respond "Forbidden" 403` |
| qolgani (`handle {}`) | `frontend:80` | SPA |

**Nega `/metrics` butunlay yopiq.** Ilgari bu handle'da `@internal_metrics` matcher (`remote_ip private_ranges`) turardi va private tarmoqdan kelgan so'rovlar `api:8000` ga o'tardi. Lekin prodda Caddy **host-nginx ortida** ishlaydi: har bir tashqi so'rovning `remote_host`i proxy'ning o'zi (`127.0.0.1` / docker bridge) bo'lib ko'rinadi, ya'ni matcher hech kimni to'smasdi va Prometheus metrikalari amalda ochiq internetda edi. Endi matcher olib tashlangan — `handle /metrics` har doim `403` qaytaradi. Repoda Prometheus/Grafana xizmati umuman yo'q; scraper qo'shilganda u compose tarmog'i ichidan to'g'ridan-to'g'ri `api:8000/metrics` ga boradi, bu yo'ldan emas.

Asosiy site blokidan tashqari alohida **`:8080` bloki** bor — `respond /healthz "OK" 200`. Bu Docker healthcheck uchun doimiy plain-HTTP endpoint: `SITE_ADDRESS` domenga o'tib asosiy blok TLS'ga ko'chganda ham ishlayveradi.

Backend `X-Forwarded-*` headerlariga ishonishi ikki qatlamli: app-level `ProxyHeadersMiddleware` `.env`/kod default'idagi `FORWARDED_ALLOW_IPS` dan oladi, gunicorn darajasi esa `--forwarded-allow-ips` flagi bilan — u compose'da `GUNICORN_FORWARDED_ALLOW_IPS` o'zgaruvchisidan olinadi (yuqoridagi `api` command). **Ikkalasining defaulti ham `172.16.0.0/12`** — docker compose tarmog'i, ya'ni Caddy konteyneri. Ikki o'zgaruvchi mustaqil: birini o'zgartirsang ikkinchisini ham qo'lda moslashtir. App-level middleware gunicorn qatlamidan ICHKARIDA ishlaydi, ya'ni `FORWARDED_ALLOW_IPS=["*"]` flagdagi qat'iy ro'yxatni bekor qilardi — shuning uchun non-LOCAL muhitda `*` bilan boot rad etiladi.

⚠️ `*` QO'YMANG. `*` da uvicorn XFF'ning eng CHAP (mijoz bergan) qiymatini oladi. 2026-08-26 da o'lchandi: `X-Forwarded-For` ni har so'rovda almashtirgan mijoz login rate-limitini TO'LIQ aylanib o'tdi (barqaror IP'da 8 urinishdan 3 tasi bloklandi, almashib turganda 12 tadan 0 tasi), audit logdagi IP ham soxta bo'lardi. Konkret ro'yxat berilganda uvicorn XFF'ni O'NGDAN chapga yuradi va birinchi ISHONILMAGAN manzilni — Caddy haqiqatan ko'rgan mijoz IP'sini — oladi.

### `frontend/nginx/index.conf` — konteyner ichidagi static server

Frontend konteyneri ichida nginx `:80` da:

- gzip (`text/*`, `application/json`, `application/javascript` va h.k., `gzip_min_length 1024`);
- `location = /manifest.webmanifest` — `types { application/manifest+json webmanifest; }` + `no-cache`: nginx default `mime.types` da `.webmanifest` yo'q (`application/octet-stream` bo'lib ketardi, Chrome manifestni rad etadi va «o'rnatish» taklifi chiqmaydi); hash'siz nom bo'lgani uchun `index.html` kabi keshlanmaydi. 2026-09-04 da haqiqiy nginx 1.24 bilan lokal tekshirildi.
- `location = /index.html` — `Cache-Control: no-cache`: `index.html` hech qachon keshlanmaydi, aks holda deploy'dan keyin brauzer eski hash'li assetlarga ishora qiluvchi eski SPA'ni ushlab qolib oq ekran berardi;
- `location /` — `/usr/share/nginx/html` dan static, `try_files $uri $uri/ /index.html` (SPA fallback). Oxirgi parametr **URI** (`=404` kod emas): shundagina nginx ichki redirect qiladi va chuqur havola (`/orders/123`) ham yuqoridagi `location = /index.html` blokidan o'tib `no-cache` header'ini oladi — `=404` bilan tugaganda `index.html` joriy `location /` kontekstida fayl sifatida berilar va header'siz qolar edi;
- static assetlar (`js/css/img/font`) uchun `expires 1y` + `Cache-Control: public, immutable`;
- `/api`, `/docs`, `/redoc` → **404** — bu pathlar reverse proxy (Caddy) tomonidan xizmat qilinadi, frontend konteyneriga tushib qolsa xato ekanini aniq bildiradi.

---

## Dockerfile'lar

### `backend/Dockerfile` — multi-stage, uv asosida

1. **Builder stage** — `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`. `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`. **Faqat bog'liqliklar** o'rnatiladi: `uv.lock` + `pyproject.toml` bind-mount bilan `uv sync --frozen --no-install-project --no-dev` (cache mount `/root/.cache/uv`). `--no-dev` `[dependency-groups] dev` ni (mypy, ruff, pre-commit, types-openpyxl va ularning tranzitiv bog'liqliklari) tashlab ketadi — 56 emas, 39 paket. Loyihaning o'zi venv'ga o'rnatilmaydi (app `PYTHONPATH` orqali ishlaydi) — shunda venv qatlami faqat `uv.lock` ga bog'liq: kod o'zgarganda ~380 MB qatlam qayta qurilmaydi va server har deployda uni qayta tortmaydi.
2. **Final stage** — `python:3.13-slim-bookworm`. Healthcheck uchun `curl`, yorliq PNG'si TTF shriftda chiqishi uchun `fonts-liberation` o'rnatiladi. Xavfsizlik uchun **non-root `app` user** (uid/gid 1000). Builderdan faqat `/app/backend/.venv` ko'chiriladi; `backend` va `scripts` esa to'g'ridan-to'g'ri build kontekstidan `COPY --chown=app:app` qilinadi — tez-tez o'zgaradigan kod qatlamlari oxirida tursin. So'ng `RUN mkdir -p /app/backend/uploads && chown app:app /app/backend/uploads` — **yuklamalar katalogi image'da oldindan yaratiladi** (pastda sabab). `PATH` ga venv qo'shiladi, `PYTHONPATH=/app/backend`. Default `CMD` — `uvicorn app.main:app --host 0.0.0.0 --port 8000`, lekin ikkala compose ham buni override qiladi (dev: reload'li uvicorn; prod: gunicorn; worker: arq).

**Nega `uploads` katalogi image'da oldindan yaratiladi.** `backend/uploads` `.dockerignore` da, ya'ni `COPY backend /app/backend` uni image'ga olib kelmaydi — katalog umuman bo'lmasdi. Prodda esa aynan shu yo'l `uploads_data` named volume'ning mount nuqtasi: Docker bo'sh volume'ni mount qilganda mavjud katalogning egaligini ko'chiradi, katalog bo'lmasa esa uni **`root:root`** bilan yaratadi. Konteyner `USER app` (uid 1000) ostida ishlagani uchun har qanday fayl yuklash `EACCES`/"Permission denied" bilan yiqilardi. `mkdir` + `chown app:app` shuni oldini oladi: volume katalogning `app:app` egaligini oladi.

Muhim: build context — **repo root** (`context: .`), chunki image'ga `scripts/` ham kiradi (`prestart.sh` shu yerdan ishlaydi).

### `frontend/Dockerfile` — multi-stage, Node → nginx

1. **build-stage** — `node:24-alpine` (versiya `frontend/.nvmrc` dagi `24` bilan mos). `package*.json` avval ko'chiriladi → `npm ci` (layer caching), keyin kod. `ARG VITE_API_URL` va `ARG VITE_API_TIMEOUT_MS` (default `30000`) build vaqtida env'ga aylanadi — Vite build'ga statik ravishda "pishiriladi" (shuning uchun lokal compose va CI'ning `images` job'i turli `VITE_API_URL` bilan alohida build qiladi). `npm run build` → `tsc && vite build` → `dist/`.
2. **Runtime** — `nginx:1.29-alpine`. Default config o'chiriladi, `dist/` → `/usr/share/nginx/html`, `nginx/index.conf` → `default.conf`. `HEALTHCHECK` — `wget --spider http://127.0.0.1/` (`localhost` `::1` ga resolve bo'lib IPv4-only nginx'da unhealthy berardi); prod compose bu healthcheck'ni takrorlamaydi — image'niki yagona manba.

---

## Scriptlar

Barcha `scripts/*.sh` fayllar git'da **executable (mode 100755)** saqlanadi. Bu muhim: avval ular 644 bo'lib, image ichida `/app/scripts/prestart.sh` ishga tushmasdi va `api` konteynerlar umuman start bo'lmasdi.

### `scripts/setup.sh` — bir martalik lokal setup

`make setup` chaqiradi. Birinchi qadam — `cd "$(dirname "$0")/.."`: script cwd'ni repo ildiziga keltiradi (`deploy.sh`/`backup.sh` singari), shuning uchun uni istalgan katalogdan chaqirish mumkin; ilgari `scripts/` ichidan chaqirilsa `.env.example` topilmay `set -e` ostida yiqilardi. So'ng `set -e` bilan: (1) `uv` o'rnatilganini tekshiradi, yo'q bo'lsa xato bilan chiqadi; (2) `.env` bo'lmasa `.env.example` dan nusxa oladi; (3) `uv --project backend sync`; (4) `alembic upgrade head`; (5) `python -m app.commands.create_first_superuser` (`.env` dagi `ADMIN_*` qiymatlaridan); (6) `python -m app.commands.seed_defaults` — default organizatsiya, 9 ta ishlab chiqarish posti (Arra, Kromka, Oval kromka, Prisadka, Rover, Stolyarka, Bo'yoq, Qadoqlash, TMO) va har post uchun bitta `is_system` texnik hisob (`_seed_post_accounts`). `Makefile` dagi `setup` targeti bundan keyin `install-hooks` (pre-commit) ni ham bajaradi.

### `scripts/prestart.sh` — konteyner startidan oldingi bosqich

Ikkala composeda ham `api` command zanjirining birinchi qismi. Uch qadam: `python -m alembic upgrade head` (shartsiz — WORKDIR `/app/backend`, `alembic.ini` shu yerda; yo'q bo'lsa start ataylab yiqiladi), so'ng `python -m app.commands.create_first_superuser` (idempotent: mavjud admin `is_deleted=False` bo'lgan qatorlar orasidan TELEFON YOKI USERNAME bo'yicha qidiriladi — shu tufayli `ADMIN_PHONE` rotatsiya qilinganda ham eski qatorning `username` i `ix_user_username` partial unique indeksini buzmaydi va prestart `set -e` ostida yiqilmaydi), oxirida `python -m app.commands.seed_defaults` (default organizatsiya, 9 ta ishlab chiqarish posti — Arra, Kromka, Oval kromka, Prisadka, Rover, Stolyarka, Bo'yoq, Qadoqlash, TMO — hamda HAR post uchun bitta `is_system` texnik hisob idempotent seed qilinadi; `order_index` 1,2,3,4,6,7,8,9,10, ya'ni 5 (eski PAZ) ataylab bo'sh; yangi post qo'shilganda mavjud bazalarda `order_index` ham sinxronlanadi). Post hisoblari (`_seed_post_accounts`) alohida ahamiyatli: usiz beyjik bilan kirish 401 beradi. Shu tufayli konteyner har startda schema'ni head'ga keltiradi, admin user, default org/postlar va post hisoblari mavjudligini kafolatlaydi. `worker` servisi buni ishlatmaydi (migratsiyani `api` ga qoldiradi).

Ketma-ketlikning nozik joyi: default `organization` qatorini seed emas, **`1393a241b793` migratsiyasi** qo'yadi (idempotent `INSERT ... WHERE NOT EXISTS`). Undan keyingi uchta post migratsiyasi (`b3e9a1d76c42`, `f1b6d0c73a25`, `a3f8d61c9b04`) `post` ga `organization_id = 1` bilan yozadi, `seed_defaults` esa migratsiyalardan **keyin** ishlaydi — busiz toza bazada `alembic upgrade head` FK buzilishi bilan yiqilar va yangi muhit umuman ko'tarilmasdi (tafsilot: `docs/04-backend-data.md`).

### `scripts/generate-client.sh` — OpenAPI → TypeScript client

`make frontend-gen` chaqiradi. U ham avval `cd "$(dirname "$0")/.."` bilan repo ildiziga o'tadi — quyidagi nisbiy yo'llar zanjiri shunga tayanadi. Oqim: `backend/` da `app.main.app.openapi()` ni Python orqali JSON'ga dump → `frontend/openapi.json`; keyin `npm run generate-client` (`@hey-api/openapi-ts`, `frontend/package.json` dagi `generate-client: openapi-ts` script) → `frontend/src/client/`. (Biome format qadami olib tashlandi: `biome.json` `src/client/**` ni butunlay ignore qiladi, ya'ni u har safar "Checked 0 files" berardi.) Backend endpoint/schema o'zgarganda shu buyruqni qayta ishlatish kerak (`frontend/README.md` da ham qo'lda variant tasvirlangan).

### `scripts/deploy.sh` — prod deploy avto-rollback bilan

CI chaqiradi: `TAG=<git sha> REGISTRY=ghcr.io/<owner> bash scripts/deploy.sh`. Oqim: `docker compose pull` — serverda build yo'q, tayyor image ghcr.io dan tortiladi (yiqilsa eski stack joyida qoladi) → yangi `TAG` ga switch (`docker compose up -d`) → **`caddy reload`** → smoke. Reload qadami majburiy: `up -d` bind-mount qilingan faylning MAZMUNI o'zgarganini bilmaydi (compose faqat service ta'rifi — image, env, volumes ro'yxati — o'zgarsa konteynerni qayta yaratadi), ya'ni reload'siz `rsync` olib kelgan Caddyfile o'zgarishlari deployda jimgina yo'qolardi. `$COMPOSE exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile` zero-downtime va konfigni AVVAL tekshiradi — sintaksis buzuq bo'lsa eski konfig joyida qoladi va sayt tirik qolaveradi; shuning uchun `|| true` emas: reload yiqilsa script `exit 1` bilan to'xtaydi (smoke ham, rollback ham ishlamaydi) va aniq xabar beradi — yangi image'lar ko'tarilgan, lekin `caddy/Caddyfile` o'zgarishi tushmagan. Smoke `SMOKE_URL` ga uradi — default manzil `.env` dagi `SITE_ADDRESS` ga qarab tanlanadi: bo'sh yoki `:PORT` bo'lsa `http://<CADDY_HTTP_BIND>/api/v1/ready` (qiymat faqat port bo'lsa oldiga `127.0.0.1:` qo'shiladi, `.env` da yo'q bo'lsa `80` — qotirilgan `8200` port bind default `80` bo'lgan o'rnatishda har deployni yolg'ondan yiqitardi), domen bo'lsa `https://<SITE_ADDRESS>/api/v1/ready` va `--resolve <domen>:443:127.0.0.1`. Ikkala qiymat ham skriptdagi `env_get` helperi orqali o'qiladi — u o'rab turgan qo'shtirnoq/apostrofni olib tashlaydi (`.env.example` da shu konventsiya bor, docker/pydantic uni bemalol yutadi): aks holda `CADDY_HTTP_BIND="127.0.0.1:8200"` `http://"127.0.0.1:8200"/…` degan buzuq URL berib, sog' deploy'ni 30×5s smoke'dan keyin yolg'ondan rollback qilardi. Domen holati majburiy: Caddy HTTP'ni HTTPS'ga 308 bilan yo'naltiradi, ya'ni oddiy HTTP smoke hech qachon 200 olmasdi va prodda (`mes.mebelix.uz`) har deploy yolg'ondan rollback bo'lardi; `--resolve` esa tekshiruvni shu mashinada qoldiradi — tashqi DNS ham, internet ham aralashmaydi. `/api/v1/ready` DB+Redis'ni tekshiruvchi readiness probe (`/api/v1/health` dan farqli, u faqat process tirikligini aytadi); CI'ning public smoke'i ham shu endpointga uradi. Smoke o'tsa `TAG` `.stable_tag` fayliga yoziladi va eski image'lar tozalanadi (joriy + oldingi stable qoladi); yiqilsa `.stable_tag` dagi oxirgi barqaror tag'ga avto-rollback qilinadi. Rollback **serverda oldingi image hali turganiga** tayanadi — aynan shu tozalash qadami buni kafolatlaydi (joriy tag va oldingi stable tag hech qachon o'chirilmaydi). **Rollback chegarasi:** u FAQAT image `TAG` ni qaytaradi — `caddy/Caddyfile`, `docker-compose.prod.yml` va scriptlar diskda YANGI holicha qoladi (CI `rsync --delete` bilan yuboradi, ya'ni serverda eski nusxa qolmaydi) va `caddy reload` smoke'dan OLDIN bir marta chaqilgani uchun Caddy xotirasida ham yangi konfig turaveradi. Demak sintaksisi to'g'ri (CI `caddy validate` dan o'tgan), lekin semantikasi buzuq Caddyfile smoke'ni yiqitsa rollback uni TUZATMAYDI — «ROLLBACK SMOKE HAM YIQILDI» ga tushadi; skript buni rollback xabarida aytadi, tuzatish qo'lda (konfigni to'g'irlab qayta deploy).

Tozalash `docker images --format '{{.Repository}}:{{.Tag}}' | grep 'mebelix-mes-'` bilan ishlaydi, `--filter=reference='mebelix-mes-*'` bilan emas: docker glob'i `/` dan o'tmaydi, ya'ni `ghcr.io/<owner>/mebelix-mes-*` nomlariga u hech qachon mos kelmasdi va eski image'lar to'planib qolardi. Natija o'sha `grep -vE ":(TAG|STABLE)$"` filtridan o'tkaziladi. **Rollback va DB (2026-09-02):** smoke yiqilsa eski image `SKIP_MIGRATIONS=1` bilan ko'tariladi — `prestart.sh` migratsiyani o'tkazib yuboradi, chunki eski image'ning alembic'i bazadagi yangi revision'ni tanimaydi va `upgrade head` `Can't locate revision` bilan yiqilib api'ni crash loop'ga tushirardi (2026-09-02 da repro bilan isbotlangan; bungacha har migratsiyali deploy'da avto-rollback ishlamas edi). `alembic_version` ga tegilmaydi (`stamp` YO'Q — u keyingi deploy'da migratsiyani qayta yuritib yiqitardi), keyingi to'g'ri deploy `upgrade head` bilan davom etadi. **Qoida: migratsiya oldingi reliz bilan mos bo'lsin (expand/contract)** — ustun/jadval qo'shish bemalol; o'chirish/nomini o'zgartirish — kod uni ishlatmay qo'ygan KEYINGI relizda. Additiv bo'lmagan migratsiya deploy qilinganda `ROLLBACK_DOWNGRADE=1`: rollback'dan oldin YANGI image bilan `alembic downgrade <eski image head>` yuriladi (eski head `TAG=<stable> compose run --rm --no-deps api python -m alembic heads` dan). Bu bayroq FAQAT serverda qo'lda deploy'da ishlaydi (`cd /opt/mebelix-mes && docker login ghcr.io` PAT bilan, so'ng `ROLLBACK_DOWNGRADE=1 TAG=<sha> REGISTRY=ghcr.io/<owner> bash scripts/deploy.sh`) — CI ssh qatori faqat `TAG`/`REGISTRY` uzatadi. Yana ikki qoida: (1) prodga tushgan (hatto rollback qilingan) migratsiya fayli QAYTA YOZILMAYDI — tuzatish yangi migratsiya bilan; agar id o'zgartirilgan/o'chirilgan bo'lsa keyingi deploy `Can't locate revision` beradi va deploy'dan oldin qo'lda `alembic stamp <mavjud id>` kerak — `stamp` o'rinli bo'lgan yagona holat shu; (2) rollback holatida (stable konteyner `SKIP_MIGRATIONS=1` bilan turganda) qo'lda `docker compose up -d` qilinsa `SKIP_MIGRATIONS=1` ni ham bering, aks holda env o'zgargani uchun konteyner qayta yaratilib eski alembic yana yiqiladi. Yangi NOT NULL ustun — `server_default` bilan (eski image `seed_defaults`/INSERT'lari yiqilmasin). Prestart'ning o'zi yiqilgan holat (migratsiya xatosi) ham rollback'ga yetadi: `up -d` `dependency failed` bilan exit 1 bersa ham skript to'xtamaydi, smoke yiqilib rollback ishlaydi (DB tranzaksiya sabab eski revision'da qoladi).

### `scripts/backup.sh` — kunlik shifrlangan backup (DB + yuklangan fayllar)

Server cron'ida kunlik ishlaydi (`0 18 * * *` — server UTC'da, ya'ni **23:00 Toshkent**: ish kuni tugagach). Fayl nomidagi sana ham Toshkent bo'yicha olinadi (`TZ=Asia/Tashkent date +%F`), aks holda cron soati bir oz surilsa nom bir kun orqaga tushib qolardi. Oqim: `pg_dump` (prod composedagi `db` konteyneri ichida) | `gzip` | `openssl aes-256-cbc -pbkdf2` (parol — `.env` dagi `ADMIN_PASSWORD`) → natija **serverdagi `/var/backups/mebelix/mebelix-YYYY-MM-DD.sql.gz.enc`** fayliga yoziladi — ataylab **deploy daraxtidan tashqarida**: CI `rsync --delete` bilan `/opt/mebelix-mes` ni repo bilan tenglashtiradi va repoda yo'q katalogni o'chirib yuborardi (backuplar aynan shu tarzda yo'qolgan edi). So'ng ikkita nazorat: fayl 1000 baytdan kichik bo'lsa dump yiqilgan deb hisoblanadi (fayl o'chiriladi, script `exit 1`), va `BACKUP_KEEP_DAYS` (default `14`) kundan eski nusxalar `find … -delete` bilan tozalanadi. Katalogni `BACKUP_DIR` (default `/var/backups/mebelix`), saqlash muddatini `BACKUP_KEEP_DAYS` o'zgartiradi — ikkalasi ham `.env.example` da yo'q, kerak bo'lsa `.env` ga qo'lda qo'shiladi. Repo ichidagi `backups/` `.gitignore` da qoladi (kimdir `BACKUP_DIR` ni nisbiy yo'lga qaytarsa ham).

Telegram — **tashqi nusxa**: `.backup.env` da `TG_BOT_TOKEN` va `TG_CHAT_ID` (ixtiyoriy `TG_TOPIC_ID` — mavzuli guruhda nusxa shu mavzuga tushadi) bo'lsa fayl document sifatida ham yuboriladi, bo'lmasa script "Telegram sozlanmagan" deb yozib normal tugaydi; bu faylni **CI deploy job'i yozadi** (`Backup Telegram sozlamasi (serverda)` qadami) — deploy xabarlari ketadigan `notify` job'i bilan aynan bir xil sirlardan, ya'ni backup va deploy xabarlari bitta botga tushadi va tokenni qo'lda ko'chirish kerak emas; yuborish yiqilsa ogohlantirish chiqadi, lekin lokal backup joyida. Diskka yozish asosiy yo'l ekani ataylab: Telegram yagona yo'l bo'lganda `.backup.env` yo'qligi butun scriptni yiqitib, 15 kecha davomida birorta backup olinmagan edi.

**Yuklangan fayllar ham backup qilinadi** (`mebelix-uploads-YYYY-MM-DD.tar.gz.enc`): `api` konteyneri ichidan `tar -cz -C /app/backend uploads`, `--exclude='uploads/agent'` bilan (u ma'lumot emas — eski tarqatish oqimidan qolgan 19 MB exe: backupni sakkiz barobar shishirardi va har kecha o'zgarmasdan qayta ketardi; yangi exe bu yerga umuman tushmaydi, CI uni `agent-dist/` ga qo'yadi). Bu ataylab **best-effort** qadam: yiqilsa (masalan `api` o'chik bo'lsa) script to'xtamaydi, chunki DB dumpi allaqachon olingan va yuborilgan. Kerakligi sababi — DB'da faqat nisbiy yo'l saqlanadi (`OrderFile.path`), ya'ni DB dumpi **yolg'iz o'zi buyurtmani tiklamaydi**: `.project`, SCX va anketa rasmlarisiz buyurtma kartochkasi "Fayl diskda topilmadi" beradi.

`.env` **source qilinmaydi**: u pydantic uchun yozilgan va ichida bash uchun yaroqsiz qatorlar bor — `CORS_ORIGINS=["http://a", "http://b"]` dagi vergul ortidagi bo'shliq tufayli bash ikkinchi bo'lakni BUYRUQ deb o'qiydi va `set -e` ostida script `pg_dump`gacha yetmasdan o'ladi (exit 127). Docker va pydantic o'sha faylni muammosiz o'qigani uchun nosozlik faqat shu yerda, jimgina ko'rinardi. Shuning uchun `env_get` helperi faqat kerakli kalitlarni (`POSTGRES_USER`, `POSTGRES_DB`, `ADMIN_PASSWORD`, hamda `.backup.env` dan `TG_*`) `sed` bilan o'qiydi, qiymatni python-dotenv qoidasi bo'yicha tozalaydi — qo'shtirnoq/apostrof yechiladi, izoh esa faqat oldida bo'shliq bo'lgan `#` dan boshlanadi (aks holda `ADMIN_PASSWORD` ichidagi `#` jimgina kesilib, backup boshqa parol bilan shifrlanardi); uchtasi topilmasa script darhol aniq xabar bilan to'xtaydi. Telegram `curl`ida ham `--connect-timeout`/`--max-time` bor va natija `|| resp=...` bilan ushlanadi — aks holda tarmoq xatosi (`set -e`) butun scriptni o'ldirib, yuklangan fayllar backupi va retention bajarilmay qolardi.

Ochish:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc | gunzip > dump.sql   # DB
openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.tar.gz.enc | tar -xz            # fayllar
```

---

## Chop etish infratuzilmasi — bridge-agent va GoDEX G500-U

Printer tsexda, server esa masofada (`mes.mebelix.uz`) turadi. GoDEX G500-U **faqat USB** — unda tarmoq porti umuman yo'q, ya'ni printerga IP orqali murojaat qilish imkoni yo'q. Shuning uchun oraliqda **bridge-agent** — printer ulangan kompyuterda ishlaydigan, serverga **chiquvchi** (outbound) WebSocket ochadigan servis. Manbasi bitta Python fayl (`bridge-agent/agent.py`), tsexga esa u **Windows exe** (`mebelix-agent.exe`) sifatida boradi — o'rnatiladigan mashinada Python ham, kutubxona ham kerak emas. Tsex tarmog'ida hech qanday port ochilmaydi, oq IP kerak emas.

Agent faqat **printer ulangan bitta kompyuterga** o'rnatiladi; menejer, texnolog va boshqa post terminallariga hech narsa kerak emas — ular brauzerdan tugmani bosadi.

### Zanjir (uchdan-uchgacha)

```
Terminal (arrachi)
  POST /api/v1/terminal/labels/{instance_id}          (backend/app/api/routes/terminal.py)
    ├── instance.label_printed_at = now()
    ├── ws_manager.publish("label.printed", …)         → brauzerlarga live yangilanish
    └── require_printer(db, machine_id) → arq enqueue_job("print_label", instance_id, agent_id)
          (agent biriktirilmagan bo'lsa NoPrinterBound → 422, chek YUBORILMAYDI)
          ↓
  print_label task                                     (backend/app/tasks/__init__.py)
    ├── load_label_data(db, instance_id)               (backend/app/services/labels.py)
    ├── render_label_png(data)      → PNG, base64
    └── redis.lpush(print_queue_key(agent_id), job)    → job = {type, job_id, instance_id, png}
          ↓
  GET /api/v1/ws/bridge  (Authorization: Bearer …)     (backend/app/api/routes/ws.py)
    brpop([o'z kaliti], 5) → send → ack kutish (15s) → yo'q bo'lsa src_key ga rpush
          ↓
  bridge-agent (tsex)                                   (bridge-agent/agent.py)
    uplink() → local_enqueue(job) → ack → FLUSH_EVENT.set()
    flusher() → send_to_printer(png)                   → Windows GDI → USB GoDEX
```

Job'ning Redis kaliti — `print_queue_key(agent_id)`: `mes:print:queue:{agent_id}` manzilli job uchun,
`PRINT_QUEUE_KEY = "mes:print:queue"` esa endi o'qilmaydi ham, yozilmaydi ham: har chek aniq agentga manzillanadi (`require_printer`), manzilsiz job umuman yaratilmaydi. Umumiy navbat aynan "boshqa postdagi printer chekni tortib oldi" nuqsonining mexanizmi edi (`backend/app/tasks/__init__.py`).

### Ishonchlilik: hech bir yorliq yo'qolmaydi

Zanjirning har bo'g'inida jobni yo'qotmaslik choralari bor:

- **Server → agent.** `ws_bridge` jobni `brpop` bilan Redis'dan **oladi** (ya'ni navbatdan chiqadi), keyin yuboradi va `{"ok": true}` ack kutadi (`asyncio.wait_for`, 15s). Ikkala nosoz yo'lda ham job `rpush` bilan **aynan o'z kalitiga** qaytariladi, lekin oqibat boshqacha: ack umuman kelmasa (timeout) ulanish uziladi; `ok` false kelsa (agent chekni rad etdi — printeri yo'q) ulanish **tirik qoladi**, server 15 soniya pauza qilib navbatni davom ettiradi (pastdagi "Chiqish yo'li" bo'limi).
- **Agent tomonda.** `uplink()` jobni avval `local_enqueue()` bilan diskka yozadi (`print-queue.jsonl`, JSONL append), **keyin** ack yuboradi. Ya'ni server jobni faqat u tsexdagi diskda turgani aniq bo'lgach unutadi — agent yoki kompyuter o'chsa ham job saqlanadi.
- **Printer o'chiq bo'lsa.** `flusher()` navbatni BITTADAN chiqaradi: har muvaffaqiyatli yorliqdan keyin fayl qayta o'qilib faqat chiqqan job olib tashlanadi (v1.4.0). Ilgari butun batch bitta snapshot bilan yurar edi — chop etish paytida kelgan ack qilingan job rewrite'da o'chib ketardi (isbotlangan critical), tok o'chsa esa chiqqan yorliqlar qayta chiqardi. Birinchi muvaffaqiyatsiz jobda to'xtaydi (tartib buzilmaydi), `"Printer kutilmoqda — navbatda N ta yorliq"` deb log yozadi. `local_enqueue`/`local_rewrite` endi fsync qiladi — ack ketishidan oldin yozuv haqiqatan diskda.
- **Bo'sh vaqtda.** Agent oddiy holatda 5 sekundda bir sikl uradi, lekin yangi job kelganda `FLUSH_EVENT.set()` flusher'ni **darhol** uyg'otadi — kutish yo'q.
- **Navbat fayli qulflansa.** `flusher()` ning butun sikli `except Exception` bilan o'ralgan: `local_drain`/`local_rewrite` dagi OSError (Windows'da antivirus yoki zaxira dasturi `print-queue.jsonl` ni qulflashi odatiy hol) faqat logga yoziladi va 5 soniyadan keyin qayta urinadi. Ilgari o'sha bitta xato `asyncio.gather` orqali BUTUN agentni — chop etish, skan-forvard, log yuborish bilan birga — o'ldirardi, `__main__` esa faqat `KeyboardInterrupt`/`SystemExit` ni ushlagani va exe `--noconsole` bilan qurilgani uchun oynasiz jimgina yo'q bo'lardi (isbotlangan). Endi `__main__` da `except Exception` ham bor: sabab `agent.log` ga yoziladi va operatorga xato dialogi ko'rsatiladi — `log_shipper` ham o'lgani uchun serverga xabar yetmaydi, bu yagona ko'rinadigan kanal.
- **Avto-yangilanish (v1.4.0+).** CI'dagi `agent` job (windows-latest) har main-push'da PyInstaller exe quradi, deploy artifactni `agent-dist/` ga rsync qiladi (api konteynerga read-only mount), agent `self_update()` bilan har qayta ulanishda (deploy = WS uzilish = trigger) va zaxira har 10 daqiqada (v1.4.3; avvalgi 6 soat bo'sh agentni asossiz kuttirardi) `/bridge-agents/latest` ni tekshirib sha256-tasdiqlangan exe bilan o'zini almashtiradi (`update.bat`: chiqishni kutadi → move → start). Token/navbat `%APPDATA%` da — yangilanish ulanishga tegmaydi. Ikkala bat ham (`update.bat` va tray'dagi «Qayta ulash» yozadigan `restart.bat`) **sof ASCII** matn: exe va yangi exe yo'llari matnga emas, `_spawn_bat()` orqali env'ga (`%MBX_EXE%` / `%MBX_NEW%`) beriladi — ilgari yo'l matnga yozilardi va ASCII bo'lmagan Windows profil nomida (`C:\Users\Oʻktam\…`) `write_text` UnicodeEncodeError bilan yiqilib, avto-yangilanish ham, qayta ulash ham JIMGINA o'lardi (v1.4.6). Endi bat ishga tushmasa sabab log'ga yoziladi; qayta ulash holatida operator xato dialogini ham ko'radi. Flashka faqat birinchi o'rnatishda. Agent tray belgisi ko'rsatadi (yashil/qizil, v1.4.0+), nomi endi «MebeliX MES agent» — printersiz skan-forvard stansiyalarini ham qamraydi, ulanish xabari rejimga qarab («chek chiqarishga tayyor» / «skan-forvard rejimi»).
- **Yarim-ochiq TCP.** Server jobsiz 5 sekunddan keyin `{"type": "ping"}` yuboradi va javob kutadi; agent unga `{"type": "pong"}` qaytaradi (job-ack bilan bir xil `{"ok": true}` **emas** — kechikkan ping-javob keyingi jobning ack'i deb o'qilib ketmasin). Server ack kutishda `pong` xabarlarini o'tkazib yuboradi va job jo'natishdan oldin soketda qolgan eskirgan javoblarni drain qiladi; pingga `{"ok": true}` qaytarish faqat eski agentlarda qolgan. Tsex tarmog'ida "o'lgan" ulanish tez aniqlanadi. Agent tomonda `websockets.connect(..., ping_interval=30)`, uzilganda 5s backoff bilan qayta ulanish.
- **Printersiz stansiya (`can_print` o'chiq).** Chek chiqarish ruxsati o'chirilgan agent (masalan faqat skan-forvard uchun ulangan stanok kompyuteri) o'z navbatidan ham `brpop` **qilmaydi** — aks holda jobni olib, chiqara olmay lokalida qoldirardi (`ws_bridge`, `backend/app/api/routes/ws.py`). `touch_agent` har 5 daqiqada `can_print` ni ham qayta o'qiydi, ya'ni admin paneldagi belgi jonli ulanishda ~5 daqiqada kuchga kiradi.

### Autentifikatsiya — har agent uchun alohida token (pairing)

Avval serverda bitta umumiy `BRIDGE_TOKEN` bo'lardi va uni har printerli mashinaga qo'lda ko'chirish kerak edi. Endi **har agent o'z tokeni bilan** ishlaydi, tokenni esa admin panel beradi — serverga SSH ham, `.env` tahriri ham kerak emas (`backend/app/api/routes/bridge_agents.py`).

Oqim:

1. **Kod.** Admin panelda "Yangi agent" → `bridge_agent` qatori yaratiladi va 8 belgili **bir martalik kod** beriladi (`P7HJ-N46U` ko'rinishida ko'rsatiladi), muddati **15 daqiqa** (`PAIR_TTL`). Alifboda `I/L/O/0/1` yo'q — kodni telefonda aytganda adashilmaydi; 31⁸ ≈ 8.5e11 kombinatsiya 15 daqiqalik oynada brute-force'ni ma'nosiz qiladi.
2. **Almashtirish.** Agent kodni `POST /api/v1/bridge-agents/pair` ga yuboradi va **muddatsiz token** oladi (`secrets.token_hex(24)`). Bazada faqat `sha256` xesh saqlanadi, kod esa o'chiriladi. UPDATE atomik — bitta kodni ikki kompyuter bir vaqtda yuborsa faqat bittasi yutadi. Kod noto'g'ri yoki eskirgan bo'lsa bitta umumiy xato qaytadi (kod umuman bor-yo'qligi oshkor qilinmaydi). `/pair` — ochiq endpoint, chunki agentda sessiya yo'q; `POST /scan` (skan-forvard) va `POST /logs` (log yuborish) agent tokeni bilan ishlaydi; `GET /latest` va `GET /download` (exe tarqatish) ataylab himoyasiz — agentda sessiya yo'q va exe sir emas. Qolgan `bridge-agents` endpointlari (`GET /`, `POST /`, `PATCH /{id}`, `POST /{id}/code`, `DELETE /{id}`, `GET /{id}/logs`) `AdminUser` bilan yopiq.
3. **Ulanish.** `/ws/bridge` tokenni **`Authorization: Bearer`** headeridan oladi (URL query'da emas — server access-loglariga tushmasin); `?token=` query eski agentlar uchun fallback bo'lib qolgan. Token avval legacy `settings.BRIDGE_TOKEN` bilan `secrets.compare_digest` orqali solishtiriladi (bytes'da — non-ASCII tokenda `str` solishtirish `TypeError` beradi), mos kelmasa `sha256` bo'yicha `bridge_agent` jadvalidan qidiriladi. Ikkovi ham topilmasa WebSocket `code=4401` bilan yopiladi.

`settings.BRIDGE_TOKEN` endi **ixtiyoriy legacy back-compat** — bo'sh bo'lsa ham chop etish to'liq ishlaydi. Yangi o'rnatishlarda uni umuman to'ldirmaslik kerak.

**Bekor qilish (revoke) deyarli darhol.** Admin "yangi kod" yoki "o'chirish" bosganda `_revoke_live_connection()` Redis'ga `mes:agent:revoked:{id}` bayrog'ini qo'yadi (TTL 10 daqiqa), `ws_bridge` esa uni **HAR** `brpop` iteratsiyasida o'qiydi — jonli ulanish `4401` bilan **~5 soniyada** uziladi (kechikish `brpop` siklining o'zi). Ilgari yagona tekshiruv 5 daqiqalik `touch_agent` edi: bekor qilingan token yana ~5 daqiqa chek olib chop etaverardi (repro bilan 295 s o'lchangan). `touch_agent()` endi zaxira: har **300 sekundda** `last_seen_at` ni yangilaydi (paneldagi "Ulandi" indikatorining manbai) va shu UPDATE'ning o'zi agent hali mavjudligini qayta tekshiradi — `token_hash` mos kelmasa yoki qator o'chirilgan bo'lsa `RETURNING` bo'sh qaytadi. Ikkala yo'lda ham qo'lda turgan job Redis navbatiga `rpush` bilan qaytariladi — yo'qolmaydi. DB xatosi ulanishni **yiqitmaydi** (jobni saqlab qolish ustuvor).

### Admin panel — "MES agentlar"

`frontend/src/routes/_layout/agents.tsx`, faqat admin. Sahifada: sarlavha tavsifidagi "mebelix-agent.exe yuklab olish" havolasi (`GET /api/v1/bridge-agents/download`), uch qatorli o'rnatish yo'riqnomasi va agentlar jadvali — nomi, holati (faqat ulangan agentda yonida versiya belgisi), joriy ulanish kodi, ish markazi bog'lami (skan-forvard), chek chiqarish ruxsati, oxirgi ulanish vaqti, amallar.

| Holat | Qachon |
|---|---|
| `Ulandi` | `last_seen_at` 6 daqiqadan yangi (server 5 daqiqada bir yangilaydi — bitta sikl zaxira); yonida versiya belgisi — `v<versiya>`, versiyasiz eski exe'da `eski exe` |
| `Uzilgan` | ulangan (token bor), lekin oxirgi 6 daqiqada ko'rinmadi |
| `Kod kutilmoqda` | kod berilgan, agent hali ulanmagan |
| `Kod muddati o'tgan` | 15 daqiqa o'tdi, agent ulanmadi — "yangi kod" kerak |

Amallar: **yangi kod** (`POST /{id}/code` — eski tokenni ham bekor qiladi, kompyuter almashganda) va **bekor qilish** (`DELETE /{id}` — soft delete, ulanish endi rad etiladi). Ikkalasi ham `audit_log` ga yozadi va ikkalasi ham `_revoke_live_connection()` orqali jonli ulanishni ~5 soniyada uzadi. `DELETE` bundan tashqari agent navbatini (`mes:print:queue:{id}`) **tozalaydi** va admin javobda "Navbatdagi N ta chek bekor qilindi" xabarini oladi — bu "hech bir yorliq yo'qolmaydi" kafolatining yagona ataylab qilingan istisnosi: agent o'chirilgach o'sha cheklarni hech kim ololmaydi (har chek aniq agentga manzillangan), kalit esa jimgina abadiy qolardi.

Har agent qatorida **"Loglar"** dialogi bor (`AgentLogs` → `GET /{id}/logs`). Zanjir: agent har **30 sekundda** bufer log satrlarini `POST /bridge-agents/logs` ga yuboradi (`log_shipper`, HTTP — ataylab `/ws/bridge` orqali emas: o'sha soketda log xabari job ack'i o'rniga o'qilib chop etishni buzardi; yuborilmasa satrlar tashlab yuboriladi, fayl nusxasi baribir kompyuterda qoladi), server ularni Redis ro'yxatida saqlaydi (`mes:agent:log:{id}`, oxirgi `AGENT_LOG_KEEP = 200` satr, TTL 7 kun). Tsexga bormasdan diagnostika qilishning asosiy yo'li aynan shu.

### Yorliq PNG — bitta format

`backend/app/services/labels.py` da yorliqning yagona chiqish formati bor:

| Funksiya | Chiqish | Kim ishlatadi |
|---|---|---|
| `load_label_data(db, instance_id)` | `LabelData` (DB'dan yig'iladi, cutmap'dagi haqiqiy teshiklar bilan) | `print_label` task va PNG endpoint uchun umumiy manba |
| `render_label_png(d, scale=1)` | 80×60 mm, 203 dpi (8 dot/mm → 640×480 px), **1-bit** PNG | agent'ning Windows GDI yo'li; `GET /api/v1/terminal/labels/{id}.png` (brauzerdan istalgan printerga) |

`print_label` task jobga base64 `png` va har yuborishda yangi `job_id` soladi — job JSON:
`{"type": "print", "job_id", "instance_id", "png"}`; agent takrorni `job_id` bo'yicha tashlaydi. PNG printer dialektiga bog'liq emas — server hech qanday xom printer formatini generatsiya qilmaydi, chizishni Windows drayveri bajaradi.

PNG maketi GibSaw `mebelix.lbl` ga taqlid qiladi (ammo paz/freza GibSaw'dagidek bitta П/Ф bayrog'i emas — eskizda QAYSI QIRRA ekani chiziladi, docs/09): chap ustun — logo, `Formatka` + zakaz kodi, detal kodi, loyiha nomi, 2×2 kromka jadvali (tagchiziq bilan), katta `L x W = count`, `N_detal` nomi, marshrut qatori (`Marshrut: 7/11/8` — `LabelData.route_codes`, y=41.5 mm; detal nomiga qo'shilmaydi, chunki nom 24 belgida kesiladi), material va sana; o'ng ustun — QR (tepada, `qrcode` kutubxonasi bilan chiziladi) va vertikal detal eskizi. Eskizda kromka konturdan 1 mm tashqarida qalin chiziq bilan, `d.texture` bo'lsa uzunlik bo'ylab 3 ta chiziq, `d.holes` (cutmap'dan olingan haqiqiy teshiklar) aylana/qirra tikkalari bilan chiziladi.

Termoprinter uchun ikki qat'iy qoida kodga o'rnatilgan: `draw.fontmode = "1"` (antialiasing o'chiq) va yakuniy `img.convert("L").point(… , "1")` — har piksel sof qora yoki oq. Aks holda drayver dither qiladi va QR skanerlanmay qoladi. Shuningdek barcha chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qolib ketadi.

**Assetlar** (`backend/app/assets/`, image ichiga `COPY backend /app/backend` bilan tushadi):

| Fayl | Qayerda |
|---|---|
| `label-logo.png` | yorliq tepa-chapida, 160 threshold bilan 1-bit qilinadi; ochib bo'lmasa `MEBELIX` matni fallback |
| `label-icon-drill.png` | teshik bor detallarda sverlo ikonkasi (alpha oq fonga flatten qilinadi); ochib bo'lmasa `С` harfi fallback |

**Shrift eslatmasi.** `_FONT_REGULAR` / `_FONT_BOLD` ro'yxatlari tartib bilan sinaladi: Windows (`C:/Windows/Fonts/arial.ttf`, `arialbd.ttf`) → Debian Liberation Sans (`/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf` / `-Bold.ttf`) → zaxira DejaVu; hech biri topilmasa `ImageFont.load_default()` ga tushadi. `backend/Dockerfile` final stage'i `curl` bilan birga `fonts-liberation` ni ham o'rnatadi, shuning uchun server tomonda PNG (`/labels/{id}.png` endpointi va `print_label` task'idagi `render_label_png`) ham TTF shriftda chiqadi — qo'shimcha paket kerak emas. Liberation Sans Arial bilan metrik mos, ya'ni Windowsda sozlangan maket serverda ham aynan shunday joylashadi (DejaVu kengroq va maketni siljitgani uchun faqat zaxira).

### Chiqish yo'li — bitta: Windows GDI

`send_to_printer(png_b64)` da bitta yo'l bor: `_print_png_gdi()` — win32ui/PIL orqali Windows drayveriga rasm chizish. Bu GibSaw'ning "Used the printer driver" rejimi bilan bir xil; admin huquqi ham, printer share ham kerak emas.

Printer **avtomatik topiladi**: `_detect_printer()` `win32print.EnumPrinters(PRINTER_ENUM_LOCAL)` bo'yicha yuradi va nomi tanish yorliq-printer rusumiga (`_PRINTER_KEYWORDS`: godex, xprinter, gprinter, tsc, zebra, argox, postek — v1.4.1, Roverga Xprinter qo'yilganda rusumga qotib qolish aniqlangan) mos birinchi lokal printerni oladi. Chop etish GDI orqali — istalgan Windows drayveri ishlaydi. Odatdagi o'rnatishda hech qanday printer sozlamasi yozilmaydi; `PRINTER_NAME` env'i faqat ro'yxatda yo'q rusum uchun. Topilmasa agent log'iga KOMPYUTERDAGI BOR printerlar ro'yxati yoziladi — panel loglaridan diagnostika qilinadi. Agent chekni rad etganda (`ok:false`) server ulanishni UZMAYDI (v1.4.1 gacha uzardi — 5 soniyalik ulan-uzil sikli va terminal chipining lipillashi): job navbatga qaytadi, 15s pauza, ulanish tirik qoladi.

Printer topilmasa job navbatda qoladi va log'da `Yorliq printeri topilmadi — drayver o'rnatilganini tekshiring. Bor printerlar: …` xatosi chiqadi (rusumga qotib qolmaslik uchun matnda "GoDEX" yo'q). `png` maydonisiz job (eski format yozuvi) navbatni to'smasligi uchun tashlab yuboriladi.

**`_print_png_gdi()` nima qiladi.** Windows printer drayveri default qog'oz o'lchamiga (ko'pincha A4 yoki roll default'i) qarab yorliqni noto'g'ri joylashtiradi, shuning uchun DEVMODE qo'lda majburlanadi:

1. `win32print.GetPrinter(h, 2)["pDevMode"]` — drayverning joriy DEVMODE'i olinadi;
2. `PaperSize = 256` (`DMPAPER_USER`), `PaperWidth = 800`, `PaperLength = 600` — birlik **0.1 mm**, ya'ni 80×60 mm; `Orientation = 1` (portret);
3. `dm.Fields |= DM_PAPERSIZE | DM_PAPERWIDTH | DM_PAPERLENGTH | DM_ORIENTATION` — drayverga bu maydonlar haqiqiy ekani bildiriladi;
4. `win32gui.CreateDC("WINSPOOL", PRINTER_NAME, dm)` bilan shu DEVMODE'li DC ochiladi;
5. rasm `HORZRES`/`VERTRES` ga proporsional (`min` scale) sig'diriladi va `ImageWin.Dib(img).draw(...)` bilan `StartDoc`/`StartPage` ichida chiziladi.

Printer xatosi ushlanadi va `False` qaytariladi — job navbatda qoladi, yo'qolmaydi. ISTISNO — PNG'ning o'zi o'qilmasa (buzuq base64/rasm): bu printer xatosi emas, qayta urinish tuzatmaydi, shuning uchun job `log.error` bilan TASHLANADI (`True`) — aks holda flusher navbat boshida to'xtab, orqasidagi hamma yorliqni abadiy to'sardi (v1.5.1).

### Agent o'rnatish

Faqat printer USB bilan ulangan Windows kompyuterga (tsexdagi terminal monoblokning o'zi ham bo'ladi). Hammasi brauzerdan bajariladi — serverga SSH kirish, server `.env` ini tahrirlash yoki tsex routerida biror port ochish **kerak emas** (ulanish baribir chiquvchi). Qadamlar (`bridge-agent/README.md`):

1. **GoDEX drayverini o'rnatish** — printer USB'ga ulangan holda. Agent printerni nomidan o'zi topadi, boshqa sozlash yo'q.
2. **Exe'ni olish** — admin panel > "MES agentlar" sahifasidagi "mebelix-agent.exe yuklab olish" havolasidan (`GET /api/v1/bridge-agents/download`). Manba yagona: CI har deploy'da windows runner'da exe qurib `agent-dist/` ga qo'yadi, ya'ni serverda eskirgan nusxa qolishi mumkin emas (2026-08-02 da endpoint aynan shu sabab olib tashlangan edi, 2026-08-27 da sabab bartaraf bo'lgach qaytarilgan). Serverga kirish yo'q bo'lsa — flashka yoki lokal tarmoq. Python, `pip`, kutubxonalar — hech biri kerak emas, hammasi exe ichida.
3. **Ulanish kodini olish** — o'sha sahifada "Yangi agent", kompyuterga nom beriladi va 8 belgili bir martalik kod chiqadi (masalan `P7HJ-N46U`), 15 daqiqa amal qiladi.
4. **Exe'ni ishga tushirish** — kichik oyna chiqadi: server manzili (default `wss://mes.mebelix.uz`) va ulanish kodi. "Ulash" bosilgach kod doimiy tokenga almashtiriladi va `%APPDATA%\MebelixAgent\.env` ga saqlanadi. Kod noto'g'ri bo'lsa oyna xato matni bilan qayta ochiladi — dasturni qayta ishga tushirish shart emas. Kod muddati o'tishi allaqachon ulangan agentga ta'sir qilmaydi.

Beshinchi qadam yo'q: agent birinchi ulanishda o'zini `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` ga yozadi, ya'ni kompyuter yonganda o'zi tushadi (admin huquqi kerak emas, faqat shu foydalanuvchi uchun). Exe `--noconsole` bilan qurilgani uchun doimiy oyna yo'q — yopib qo'yish mumkin bo'lgan konsol ko'rinmaydi. Yagona istisno: har ishga tushishdagi **birinchi muvaffaqiyatli ulanishda** 5 soniyada o'zi yopiladigan `MebeliX MES agent serverga ulandi (v<versiya>)` xabari chiqadi, ostida rejim qatori — "Chek chiqarishga tayyor." yoki "Skan-forvard rejimi (printer ulanmagan)." (`MessageBoxTimeoutW`, bosish shart emas) — monoblok yonganda arrachi agent tayyorligini shundan biladi.

Ishlayotganini admin paneldagi **Ulandi** belgisi bildiradi. Diagnostika ikki joyda, mazmuni bir xil: tsexdagi `%APPDATA%\MebelixAgent\agent.log` (`RotatingFileHandler`, 1 MB x 3) va **admin paneldagi "Loglar" dialogi** (agent o'sha satrlarni har 30 sekundda serverga yuboradi — yuqoridagi "Admin panel" bo'limi), ya'ni odatda tsexga borish shart emas. Qaralayotgan satrlar: `Printer: Godex G500` va `Serverga ulandi` — tayyor; `Printer: TOPILMADI — yorliq printeri drayverini o'rnating` — drayver yo'q.

Ikkinchi nusxa ishga tushmaydi — `win32event.CreateMutex` bilan singleton. Oyna ko'rinmagani uchun foydalanuvchi "ishlayaptimi?" deb exe'ni qayta bosishi tabiiy; ikki agent bir printerga ulansa navbat ular orasida bo'linib ketardi.

Token bekor qilinganda (admin "yangi kod" yoki "o'chirish" bosgan) handshake `403`/`4401` bilan rad etiladi. Agent tokenni faqat **ketma-ket 2 ta** 401/403 raddan keyin bekor deb hisoblaydi (`reject_streak`) va sozlash oynasini qayta ochadi — yangi kod kiritilsa ishlashda davom etadi. Bekor qilinsa agent TO'XTAMAYDI: `uplink` `SystemExit` ni ushlab 30 s kutadi va qayta urinadi, ya'ni oyna yana ochiladi (tray'dagi «Qayta ulash» yo'li ham ochiq). Saqlangan `.env` fayl o'chirilmaydi: muvaffaqiyatli pairing uni baribir qayta yozadi. Bu mexanizmsiz foydalanuvchi `.env` ni qo'lda o'chirib, avval fon jarayonini Task Manager'dan yopishga majbur bo'lardi.

Streak nozik joyi: u faqat **muvaffaqiyatli ulanishda** va **auth bo'lmagan HTTP javobida** (deploy paytidagi 502/503 — token aybdor emas) nolga tushadi. Tarmoq uzilishi (TCP timeout, `except Exception` shoxi) uni nolga **tushirmaydi** — ilgari tushirardi va notekis tsex tarmog'ida ketma-ket 403 hech yig'ilmasdi (403 → timeout → 403 → …), ya'ni bekor qilingan agent yangi kod so'ramay qolardi.

Agent sozlamalari (bular **server `.env`** ida emas — printerli mashinada, `%APPDATA%\MebelixAgent\.env` da). O'qish tartibi: **env o'zgaruvchi > exe yonidagi `.env` > `%APPDATA%\MebelixAgent\.env`**. Odatda qo'lda hech narsa yozilmaydi — birinchi ulanish `MES_URL` va `BRIDGE_TOKEN` ni o'zi to'ldiradi.

| Env | Default | Tavsif |
|---|---|---|
| `MES_URL` | `ws://localhost:8000` | server manzili; agent oxiriga `/api/v1/ws/bridge` qo'shadi. Pairing paytida `https://`/`http://`/sxemasiz manzil ham qabul qilinadi va `wss://`/`ws://` ga normallashtiriladi (TLS'siz manzilga ogohlantirish chiqadi) |
| `BRIDGE_TOKEN` | — | pairing bergan doimiy token; bo'sh bo'lsa agent ishga tushishda pairing oynasini ochadi (`_pair()`) va faqat foydalanuvchi bekor qilganda `SystemExit` bilan to'xtaydi |
| `PRINTER_NAME` | avto-topish (rusumlar ro'yxati) | printer nomini qo'lda berish — faqat avto-topish mos kelmaganda |
| `QUEUE_FILE` | `%APPDATA%\MebelixAgent\print-queue.jsonl` | lokal durable navbat fayli (avtostartda ishchi papka System32 — nisbiy yo'l ishlamaydi); eski o'rnatishlardagi exe yonidagi navbat fayli birinchi ishga tushishda avtomatik shu yerga ko'chiriladi |
| `SCAN_FORWARD` | `1` (yoqiq) | stanok skanerini passiv kuzatib MES'ga forvard qilish; `0` o'chiradi |
| `ANDON` | `1` (yoqiq) | stanok signal ustunini (Pico, USB) o'qib `POST /api/v1/bridge-agents/andon` ga yuborish; `0` o'chiradi. Pico topilmagan kompyuterda jim turadi |
| `ANDON_PORT` | avto (VID `2E8A`) | Pico COM portini qo'lda berish |
| `ANDON_TAKEOVER` | `1` (yoqiq) | port band bo'lsa eski `PrisadkaMES.exe` ni BIR MARTA to'xtatib avtozapuskdan olish (`andon-takeover.done`); `0` o'chiradi |
| `ANDON_QUEUE_FILE` | `%APPDATA%\MebelixAgent\andon-queue.jsonl` | andon hodisalarining durable navbati (chek navbatidan alohida; 20 000 qatordan oshsa eng eskisi tashlanadi) |

Navbat fayli `.gitignore` da (`bridge-agent/print-queue.jsonl`).

### Agentning yangi versiyasini chiqarish

`bridge-agent/` katalogida:

```bash
pip install "websockets>=14" pywin32 pillow pynput pystray pyserial pyinstaller
pyinstaller --onefile --noconsole --icon mebelix.ico --name mebelix-agent agent.py
```

`websockets>=14` majburiy — agent kodi v14+ API'siga (`additional_headers`) yozilgan, eski v13 shim olib tashlangan; v13 bilan yig'ilgan exe serverga ulanolmaydi. `pystray` ham majburiy: usiz qurilgan exe tray belgisisiz chiqadi (`start_tray` ImportError bilan jimgina o'chadi). `pyserial` ham shunday — usiz andon (Pico) qismi jimgina o'chadi (`start_andon`). Joriy `AGENT_VERSION` — `1.5.1`.

Natijadagi `mebelix-agent.exe` ni **CI o'zi quradi va serverga qo'yadi** (`agent` job → `agent-dist/` artifact, deploy uni rsync bilan serverga eltadi): paneldagi havola ham, agentning `self_update()` i ham exe'ni `GET /api/v1/bridge-agents/download` dan, versiya/sha256 ni esa `GET /api/v1/bridge-agents/latest` dan oladi. Qo'lda (flashka) ko'chirish faqat serverga kirish yo'q bo'lganda kerak; binar repoda saqlanmaydi. Paneldagi versiya belgisi (handshake'dagi `X-Agent-Version` → `bridge_agent.version`) qaysi mashinada eski exe qolganini ko'rsatadi.

Eslatma: SCX/CNC fayllar bridge orqali **o'tmaydi** — ular stanok kompyuterida brauzer orqali yuklab olinadi. Bridge yorliq chop etishdan tashqari **skan-forvard** ham qiladi: stanok kompyuterida skaner-klaviaturani `pynput` bilan passiv kuzatadi (6+ belgi, o'rtacha <50 ms/belgi, Enter bilan tugaydi — odam terishi bu tezlikka tushmaydi) va nusxasini `POST /api/v1/bridge-agents/scan` ga yuboradi — bitta fizik skan Nanxing'ga ham, MES'ga ham tushadi. Buning uchun admin panelda agentga **ish markazi bog'lanadi** (`PATCH /bridge-agents/{id}`, `machine_id`); `SCAN_FORWARD=0` o'chiradi.

---

## Sifat nazorati — pre-commit hooklar va GitHub Actions CI

### `.pre-commit-config.yaml` — commit-oldi hooklar

`make install-hooks` (`pre-commit install`) bilan o'rnatiladi; har commitda ishlaydi:

| Hook | Manba | Vazifasi |
|---|---|---|
| `check-added-large-files`, `check-toml`, `check-yaml --unsafe` | `pre-commit-hooks` v5.0.0 | umumiy sanitariya |
| `ruff --fix`, `ruff-format` | `ruff-pre-commit` v0.16.5 (`backend/uv.lock` dagi ruff bilan bir xil versiya) | Python lint + format, **faqat `^backend/`** |
| `mypy` (local, `language: system`) | `uv --directory backend run mypy app` | type check — loyiha venv'i kerakligi uchun local hook (`make install` prereq) |
| `biome-check` (local) | `cd frontend && npx --no-install biome check ...` | frontend lint — `frontend/biome.json` ni olishi uchun `frontend/` dan ishlaydi (`npm install` prereq) |

`mypy` va `biome` hooklari `pass_filenames: false` — butun loyiha bo'yicha tekshiradi.

Ikkala ruff hook'ida `files: ^backend/` cheklovi bor — **pre-commit qamrovi CI bilan bir xil** (`ci.yml`: `cd backend && uv run ruff check --no-fix app && uv run ruff format --check app`; `backend/` ichidagi yagona python kodi aynan `app/`). Busiz hook butun repoga tushardi: `bridge-agent/agent.py` uchun ruff konfigi yo'q (repo ildizida `pyproject.toml` ham, `ruff.toml` ham yo'q — sozlama faqat `backend/pyproject.toml` da), ya'ni u DEFAULT line-length 88 ni olib, CI hech qachon tekshirmaydigan uslubga qayta yozilardi. Hujjatlar (`docs/*.md`) baribir hook'ka tushmaydi — ruff-pre-commit hooklari `types_or: [python, pyi, jupyter]` bilan cheklangan.

Muhim: CLI'da ruff qamrovi kengroq — **ruff 0.16 markdown ichidagi python bloklarini ham formatlaydi** (0.15.20 `.md` fayllarni umuman ko'rmasdi). Shuning uchun `make format` ham hook/CI bilan bir xil toraytirilgan: `cd backend && uv run ruff format app && uv run ruff check app --fix`. Repo **ildizidan** (`ruff format .`) chaqirilsa `docs/*.md` dagi qo'lda tekislangan python bloklari va `bridge-agent/agent.py` (u yerda konfig yo'q → line-length 88) qayta yozilardi — bu fayllarni na hook, na CI tekshiradi, ya'ni o'zgarish sof zarar bo'lardi. Ildizdan ruff chaqirmang.

### `.github/workflows/uptime.yml` — tashqi monitoring (kunlik)

Serverning O'ZIDAN chiqmaydigan yagona signal (2026-09-04). TLS'ni Caddy o'zi yangilaydi (ACME ARI — LE bergan oynada, muddatdan ~1 oy oldin; serverda tekshirildi: `got renewal info` har ~6 soatda, `caddy_data` da `mes.mebelix.uz.json` renewal meta) va deploy smoke'i faqat deploy paytida ishlaydi. Yangilanish yiqilsa yoki server o'lsa serverdagi cron ham u bilan o'ladi — shuning uchun tekshiruv GitHub Actions'dan: `schedule: 0 3 * * *` (08:00 Toshkent, ish boshlanishidan oldin) + `workflow_dispatch`.

Ikki tekshiruv, faqat o'qiydi: (1) `https://mes.mebelix.uz/api/v1/ready` → 200 (deploy smoke bilan bir URL); (2) `openssl s_client` bilan sertifikat muddati — **14 kundan kam** qolsa ogohlantirish (Caddy ~30-kunda yangilaydi; 14 ga yetish = ~2 hafta ketma-ket yiqilish, shovqin emas). Muammo bo'lsagina Telegram (`ci.yml` `notify` bilan bir `TG_BOT_TOKEN`/`TG_CHAT_ID`), job qizil; sog'lom kunda hech narsa yozmaydi. Skript lokalda uch yo'lda sinaldi: sog'lom sayt → OK, chegara sun'iy 400 kun → ogohlantirish matni, mavjud bo'lmagan host → ikki xato.

Tarix: 2026-08-19 da xuddi shu xavotir uchun `scripts/backup.sh` ga certbot faylidan (`/etc/letsencrypt/...`) muddat o'qish yozilgan edi (`backup/local-f919d9f`, merge bo'lmagan) — 2026-08-26 dan server almashib TLS'ni Caddy o'zi beradi, host nginx/certbot yo'q, shuning uchun u variant o'lik va o'chirildi.

### `.github/workflows/ci.yml` — GitHub Actions

`main` ga push va har bir pull request'da ishga tushadi; oltita job — `backend`, `frontend`, `images` va `agent` parallel (`images`/`agent` lint joblarini kutmaydi), `deploy` — to'rttalasiga (`needs: [backend, frontend, images, agent]`), `notify` — hammasiga:

| Job | Qadamlar |
|---|---|
| `backend` | `astral-sh/setup-uv` → `uv --project backend sync --all-groups` → `ruff check --no-fix app` + `ruff format --check app` → `mypy app` → **Migratsiya drifti** (`postgres:15-alpine` service konteyneri ustida `alembic upgrade head && alembic check` — toza bazaga butun zanjir qo'llanadi, ya'ni "prodda ishlagan, toza bazada yiqiladigan" migratsiya shu yerda tutiladi, keyin model natija sxema bilan solishtiriladi; ataylab qoldirilgan yetim jadval/ustunlar `migrations/env.py` dagi `LEGACY_TABLES`/`LEGACY_COLUMNS` da) → **Caddyfile validate** (`docker run --rm -v "$PWD/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" -e SITE_ADDRESS=:80 caddy:2-alpine caddy validate …`) — sintaksisni deploydan OLDIN tutadi, aks holda `deploy.sh` dagi `caddy reload` yarim yo'lda yiqiladi |
| `frontend` | `actions/setup-node` (versiya `frontend/.nvmrc` dan, npm cache) → `npm ci` → `npx biome ci .` → `npm run build` (`tsc && vite build`) |
| `images` | faqat `main` ga push; lint joblariga bog'liq emas — ular bilan **parallel** yuradi (ketma-ket kutish har deployga 1–2 daqiqa qo'shardi; lint yiqilsa `deploy` baribir skip bo'ladi, ortiqcha image'ni `delete-package-versions` tozalaydi). `permissions: packages: write`. Ikki elementli matritsa: `backend` (context `.`, `./backend/Dockerfile`) va `frontend` (context `./frontend`, `./frontend/Dockerfile`, build-arglar `VITE_API_URL=` va `VITE_API_TIMEOUT_MS=30000`). `docker/setup-buildx-action` → `docker/login-action` (ghcr.io, `GITHUB_TOKEN`) → `docker/build-push-action@v6`, GitHub Actions qatlam keshi bilan (`cache-from`/`cache-to: type=gha, scope=<name>`). Har image ikki teg bilan push qilinadi (bitta manifest): `:<git sha>` — deploy/rollback uchun, `:latest` — compose'dagi `${TAG:-latest}` defaulti uchun; job faqat main-push'da yurgani uchun `:latest` doim main'ning oxirgi build'i |
| `deploy` | faqat `main` ga push + to'rttala job yashil bo'lsa (`needs: [backend, frontend, images, agent]`), `permissions: packages: read`; `concurrency: prod-deploy` (parallel deploy yo'q). Qadamlar: `checkout` → `download-artifact` (`agent-dist/` — windows job qurgan exe+version.json, rsync bilan serverga boradi) → SSH key setup → `rsync` kodni `root@DEPLOY_HOST:/opt/mebelix-mes` ga (`.git`/`node_modules`/`.venv`/`__pycache__`/`dist`/`uploads`/`.env`/`backups`/`.stable_tag`/`.backup.env` exclude — serverdagi secretlar, yuklangan fayllar, DB nusxalari, avto-rollback tayanchi va Telegram backup sozlamasi `--delete` ostida qolib ketmasligi uchun) → serverdagi `.backup.env` ni yangilash (`Backup Telegram sozlamasi (serverda)`) → serverni ghcr'ga login qilish → `ssh` orqali `TAG=<git sha> REGISTRY=ghcr.io/<owner> bash scripts/deploy.sh` → public smoke `https://mes.mebelix.uz/api/v1/ready` (nginx/TLS yo'li orqali). Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST` |
| `agent` | faqat `main` ga push: windows-latest'da PyInstaller `mebelix-agent.exe` (repo ildizidan: `--icon bridge-agent/mebelix.ico … bridge-agent/agent.py`) + `version.json` (versiya `AGENT_VERSION` dan regex bilan, sha256) → `agent-dist` artifact (7 kun). Yiqilsa deploy ham to'xtaydi — artifactsiz download-artifact baribir yiqilardi |
| `notify` | `if: always() && push && ref == main`, `needs: [backend, frontend, images, agent, deploy]` — Telegram xabari; CI yiqilganda xabar to'rttala lint/build natijasini ham, `agent` natijasini ham aytadi. Secrets: `TG_BOT_TOKEN`, `TG_CHAT_ID`, ixtiyoriy `TG_TOPIC_ID`. **Mavzuli guruh (forum):** `TG_CHAT_ID` — superguruh id si (`-100` + ichki raqam, masalan `-1003916337053`), `TG_TOPIC_ID` — o'sha mavzuning id si; u `message_thread_id` bo'lib ketadi. Bo'sh qoldirilsa xabar guruhning umumiy oqimiga tushadi, ya'ni eski sozlama buzilmaydi. Shart `if` bilan yozilgan: `[ -n ... ] && x=y` bo'sh qiymatda 1 qaytaradi va qadam `bash -e` ostida yiqilardi |

**Nega image'lar CI'da quriladi.** Avval ularni prod serverning o'zi build qilardi. Server 1 vCPU / 2 GB RAM — build jonli saytni sekinlashtirardi va CI allaqachon bajargan ishni takrorlardi. Endi build GitHub Actions runnerida bo'ladi, server esa faqat tortadi.

**Paket repoga bog'lanishi.** `build-push-action` `org.opencontainers.image.source` labelini qo'yadi — aynan shu label paketni repo bilan bog'laydi. Busiz paket alohida turadi va `deploy` job'ning `GITHUB_TOKEN` i uni tortishga huquq olmaydi.

**Serverdagi registry login.** GitHub paketlari private (repo private), shuning uchun server ghcr.io ga autentifikatsiya qilishi shart. Deploy oldidagi qadam vaqtinchalik `GITHUB_TOKEN` ni ssh stdin orqali `docker login ghcr.io --password-stdin` ga uzatadi: doimiy PAT serverda saqlanmaydi va token serverdagi process ro'yxatiga tushmaydi (buyruq argumentida emas).

**Nega `notify` alohida job.** Avval u `deploy` ichida `if: always()` qadami edi. Lekin `backend` yoki `frontend` yiqilsa `deploy` butunlay **skipped** bo'ladi — skip qilingan job'ning qadamlari umuman ishlamaydi, ya'ni CI yiqilganda xabar hech kimga bormasdi. Endi `notify` mustaqil job va beshtala natijani `needs.<job>.result` orqali env'da oladi (`BACKEND`, `FRONTEND`, `IMAGES`, `AGENT`, `DEPLOY`):

| `DEPLOY` natijasi | Xabar |
|---|---|
| `success` | `✅ MebeliX deploy OK` |
| `skipped` | `❌ MebeliX CI YIQILDI (deploy boshlanmadi) — backend: …, frontend: …, images: …, agent: …` |
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
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | `postgres` / `postgres` | DB credentiallar (prod composeda defaultsiz — majburiy). Parolda `@ / : # ? %` kabi belgilar bo'lishi mumkin: `POSTGRES_URI` ularni percent-encode qiladi (`docs/02` §config.py) |
| `POSTGRES_SERVER` | `localhost` | Docker'da `db` (compose override qiladi) |
| `POSTGRES_PORT` | `5432` | DB port |
| `POSTGRES_DB` | `fastapi_db` | DB nomi (eski o'rnatishlarda `fastapi` bo'lishi mumkin — mavjud `.env` dagi qiymat saqlanadi) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` | SQLAlchemy pool sozlamalari |
| `REDIS_HOST` | `localhost` | Docker'da `redis` |
| `REDIS_PORT` | `6379` | Redis port |
| `LOGIN_RATE_LIMIT_ATTEMPTS` / `LOGIN_RATE_LIMIT_PERIOD` | `5` / `300` | Login urinishlari limiti — `.env.example` dagi yagona rate-limit kaliti |
| `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` | `50` / `100` | Pagination |
| `STARTUP_RETRY_MAX_ATTEMPTS` / `STARTUP_RETRY_DELAY_SECONDS` | `5` / `2` | Lifespan'da DB/Redis health retry |
| `THREADPOOL_TOKENS` | `100` | AnyIO sync-bridge slotlari |
| `FORWARDED_ALLOW_IPS` | `["172.16.0.0/12"]` | `X-Forwarded-*` ga ishoniladigan upstream (CIDR bo'lishi mumkin). **`*` EMAS** — u rate-limit aylanib o'tishga yo'l ochadi (yuqoriga qarang); non-LOCAL muhitda `*` bilan ilova umuman ko'tarilmaydi (`_validate_production_settings` `RuntimeError` beradi) |
| `GUNICORN_FORWARDED_ALLOW_IPS` | `172.16.0.0/12` | Faqat prod compose: gunicorn `--forwarded-allow-ips` flagi (oddiy satr, JSON emas). `FORWARDED_ALLOW_IPS` bilan sinxron turishi kerak |
| `ADMIN_PHONE` / `ADMIN_USERNAME` / `ADMIN_PASSWORD` | misol qiymatlar | Startupda yaratiladigan birinchi superuser (E.164 telefon) |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | JSON-array CORS originlar |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API bazasi; reverse proxy ortida (prod compose) `""` — SDK yo'llari o'zi `/api/v1` bilan boshlanadi |
| `VITE_API_TIMEOUT_MS` | `30000` | Axios timeout |
| `GUNICORN_WORKERS` | `4` | Prod worker soni; odatda `(2 * CPU) + 1` |
| `SITE_ADDRESS` | `:80` | Caddy listener; domen berilsa auto-HTTPS |
| `BRIDGE_TOKEN` | `""` (bo'sh) | **Legacy, ixtiyoriy.** Bridge-agentlar endi admin paneldagi pairing orqali o'z tokenini oladi; bu maydon faqat eski, pairing'gacha o'rnatilgan agent uchun qoldirilgan. Yangi o'rnatishda bo'sh qoladi va chop etish to'liq ishlayveradi |

Eslatma: chop etishga tegishli **majburiy** server sozlamasi yo'q. `BRIDGE_TOKEN` ixtiyoriy legacy, printer env'lari esa umuman server `.env` ida emas (G500-U'da tarmoq porti yo'q, printerni faqat agent ko'radi) — `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME`, `QUEUE_FILE` printerli mashinadagi `%APPDATA%\MebelixAgent\.env` da yashaydi (yuqoridagi "Chop etish infratuzilmasi" bo'limi).

Eslatma: Redis navbati va rate-limitini o'chiradigan flag yo'q — pool'lar lifespan'da so'zsiz ochiladi, `RateLimiter` esa client bo'lmaganda **fail-closed** ishlaydi (so'rov rad etiladi). Umumiy (login'dan tashqari) rate limit sozlamasi ham yo'q.

Eslatma: `CADDY_HTTP_BIND` / `CADDY_HTTPS_BIND` `.env.example` da izohga olingan holda turadi — `docker-compose.prod.yml` dagi compose-level substitutsiyalar (defaultlari `80` / `443`); behind-nginx rejimida izohdan chiqarilib loopback qiymat beriladi. `scripts/deploy.sh` smoke manzilini ham aynan shu `CADDY_HTTP_BIND` dan yig'adi (qiymat qo'shtirnoqlangan bo'lsa tozalab) — lekin FAQAT `SITE_ADDRESS` bo'sh yoki `:PORT` bo'lganda; domen berilsa smoke `https://<domen>/api/v1/ready` + `--resolve <domen>:443:127.0.0.1` ga o'tadi va `CADDY_HTTP_BIND` umuman qatnashmaydi (yuqoridagi "`scripts/deploy.sh`" bo'limi). `TAG` va `REGISTRY` esa `.env.example` da yo'q — compose-level substitutsiyalar (defaultlari `latest` va `ghcr.io/dshukriddinov`), CI ularni git sha va `ghcr.io/<owner>` bilan beradi; `latest` tegi ham CI'da push qilinadi, shuning uchun TAG'siz `pull` ishlaydi.

---

## Yordamchi konfiguratsiya fayllari

### `.dockerignore`

Backend build contexti (repo root) uchun denylist. Chiqariladi: `.git`, barcha `.env` **va ularning variantlari** (`**/.env` + `**/.env.*` — birinchi naqsh faqat aynan `.env` nomini tutadi, shuning uchun `.env.local`/`.env.server` uchun ikkinchisi kerak; `.env.example` ham kontekstga kirmaydi — backend image'iga u baribir kerak emas), `.venv` lar, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `docker-compose*.yml`, hamda backend image'iga umuman kirmaydigan yirik kataloglar — `bridge-agent`, `frontend`, `docs`, `design` (logo masterlari, 411 KB — kontekstning 39% i edi), `uploads`, `backend/uploads` (dev mashinadagi runtime yuklamalar `COPY backend` bilan image'ga tushmasin), `backups`, `caddy`, va lokal ish papkalari — `stanok rasmlar`, `scx`, `chek` (bu ikki fayldagi papka nomi "ish markazi" nomlanishiga o'tishda yangilanmagan, eski nom bilan qolgan). `backend/Dockerfile` baribir faqat `backend` va `scripts` ni `COPY` qiladi, qolgani daemon'ga behuda uzatilardi (~43 MB). Shu bilan secretlar ham image'ga tushmaydi.

Frontend'ning o'z konteksti (`./frontend`) va o'z `frontend/.dockerignore` i bor: `node_modules`, `dist`, `.env`, `.env.*` (dev'ning lokal `.env` fayllari image va Vite bundle env'iga sizmasin).

### `.gitattributes`

Bitta qoida: `* text=auto eol=lf` — barcha matn fayllar LF line-ending bilan normalizatsiya qilinadi (Windows/Linux aralash muhitda script va Dockerfile'lar buzilmasligi uchun).

### `.gitignore`

Standart Python artefaktlari (`__pycache__`, `*.py[cod]`, `build/`, `dist/` — setuptools/buildout davridan qolgan `egg`/`sdist`/`tox` naqshlari olib tashlandi: loyiha uv + hatchling'da, ular hech qachon paydo bo'lmaydi), virtualenvlar (`.venv`, `backend/.venv`), **`.env` va barcha `.env.*` variantlari** (`.env.local`, `.env.server`, `.env.prod` … — secretlar repoga tushmaydi; yagona istisno `!.env.example`, u ataylab kuzatiladi), test/lint cache (`.mypy_cache`, `.ruff_cache`, `.coverage`), IDE fayllari (`.vscode/*` lekin `settings.json`/`launch.json`/`extensions.json` istisno), `backend/app/logs/*.log`. MES runtime artefaktlari ham ignore: `backend/uploads/` (`projects/`, `scx/`, `survey/` — yuklangan fayllar va anketa xona rasmlari), `bridge-agent/print-queue.jsonl` (agent'ning durable print navbati), `frontend/openapi.json`, serverdagi shifrlangan DB nusxalari uchun `backups/` (`scripts/backup.sh`), hamda lokal tsex ma'lumotlari — `uploads/` (repo root'da: `.project`/SCX namunalari), `chek/` (namuna yorliq fotolari, `labels.py` maketi shulardan olingan), `/scx/` va `/stanok rasmlar/` (terminal SCX test papkalari — nomi `.dockerignore` dagi kabi eski shaklda qolgan). PyInstaller'ning `bridge-agent/build/` va `bridge-agent/dist/` kataloglari alohida qoida talab qilmaydi — umumiy `build/` / `dist/` naqshlari ularni istalgan chuqurlikda tutadi (spec fayli uchun esa alohida `bridge-agent/*.spec` qoidasi bor). E'tiborli nuqta: `**/lib/` ignore qilinadi, lekin `!frontend/src/lib/` istisno (shadcn util katalogi).

---

## Til/versiya manifestlari

### `backend/pyproject.toml`

`mebelix-backend` 0.1.0, `requires-python >=3.11, <3.14`, build-backend `hatchling` (faqat `app/` package). Runtime dependencylar (21 ta): `fastapi`, `uvicorn` + `uvloop` (uvloop faqat non-Windows), `websockets`, `gunicorn`, `SQLAlchemy` 2 + `asyncpg` + `greenlet` + `alembic`, `pydantic[email]`/`pydantic-settings`, `pyjwt` (`[crypto]` extra'siz — `ALGORITHM=HS256` simmetrik, `cryptography` faqat RS*/ES* uchun kerak bo'lardi) + `bcrypt`, `redis` + `arq` (queue/worker), `prometheus-fastapi-instrumentator` (metrics), `python-multipart` (fayl yuklash: `.project`, SCX, anketa rasmlari), `openpyxl` (Excel), `pillow` + `qrcode` (`render_label_png` — yorliq PNG), `tzdata` (`TASHKENT_TZ = ZoneInfo("Asia/Tashkent")` — `app/core/config.py`; yorliq sanasi va audit/hisobot sana filtrlari). `websockets` aynan runtime dependency: uvicorn `[standard]` extra'siz o'rnatilgan (`wsproto` ham yo'q), ya'ni `/ws/events` va `/ws/bridge` transporti shu paketga tayanadi — dev groupda qolsa prod image'da WebSocket ishlamasdi. Dev group — to'rtta: `mypy`, `ruff`, `pre-commit`, `types-openpyxl`. Tooling konfiguratsiyasi shu faylda: **ruff** (`target-version py311`, line-length 120, `F/E/W/C/UP/I` rulesetlar, `__init__.py` da unused/star import istisno) va **mypy** (`python_version 3.11`, `app.*` uchun `disallow_untyped_defs = true`).

### `frontend/package.json` va `frontend/.nvmrc`

`.nvmrc` — `24` (Dockerfile'dagi `node:24-alpine` bilan sinxron; `nvm use` / `fnm use` uchun). `package.json` scriptlari: `dev` (vite), `build` (`tsc && vite build`), `lint` (biome, `--write --unsafe`), `preview`, `generate-client` (`openapi-ts`). Stack: React 19, TanStack Router + Query (react-table yo'q — jadvallar oddiy `<Table>` bilan chiziladi), Tailwind CSS 4, Radix UI, react-hook-form + zod, axios, sonner; dev tomonda Biome, `@hey-api/openapi-ts`, Vite 8 + SWC, TypeScript 6 (7 emas — sabab `docs/08-packages.md` da).

### `README.md` (repo ildizi)

Repoga kirish nuqtasi — qisqa: stack qatori (FastAPI + PostgreSQL + Redis / React + Vite / Docker Compose + Caddy), bir martalik `cp .env.example .env` (`api` va `worker` uni `env_file` orqali majburiy o'qiydi), "hammasi konteynerda" uchun `make docker-local`, uchala kichik README'ga havola (`backend/`, `frontend/`, `bridge-agent/` — oxirgisi tsexdagi printerli kompyuter uchun), to'liq texnik hujjatlar indeksi sifatida `docs/README.md`, va prod manzili `https://mes.mebelix.uz` (CI yashil `main`dan avto-deploy).

### `backend/README.md`

Backend dev qo'llanmasi: texnologiyalar ro'yxati, `make setup` yoki qo'lda setup (`uv sync`, `.env`, migratsiyalar, superuser, seed), ishga tushirish (`make run-backend` / `make docker-local`), ARQ worker, lint/migratsiya buyruqlari. `docs/07-infra-devops.md` va `docs/09-mes-domain.md` ga yo'naltiradi.

### `frontend/README.md`

Frontend dev qo'llanmasi: nvm/fnm bilan Node o'rnatish, `npm install` + `npm run dev` (port 5173), Docker'siz lokal dev tavsiyasi, OpenAPI client generatsiyasi (`make frontend-gen` yoki qo'lda), `VITE_API_URL` bilan remote API'ga ulanish, `src/` katalog strukturasi (`client/` — generatsiyalangan client, `components/`, `hooks/`, `lib/`, `queries/`, `routes/`) va `public/assets`.

---

## Fayllararo bog'lanishlar xulosasi

- `Makefile` → `scripts/setup.sh`, `scripts/generate-client.sh`, ikkala compose fayl, `backend/pyproject.toml` (uv), `frontend/package.json` (npm).
- `docker-compose.local.yml` → `backend/Dockerfile` (context root, `scripts/` ni oladi), `frontend/Dockerfile` (+`VITE_API_URL` / `VITE_API_TIMEOUT_MS` build-arglar); ikkala compose ham → `scripts/prestart.sh` (api command), `.env` / `.env.example`. `docker-compose.prod.yml` build qilmaydi — tayyor `ghcr.io/<owner>/mebelix-mes-*` image'larini oladi (ularni `.github/workflows/ci.yml` dagi `images` job quradi).
- `docker-compose.prod.yml` → `caddy/Caddyfile` (`SITE_ADDRESS` env orqali TLS rejimi) → `api:8000` va `frontend:80` (`frontend/nginx/index.conf`).
- `.pre-commit-config.yaml` → `backend/pyproject.toml` (ruff/mypy config), `frontend/biome.json` (biome hook).
- `.github/workflows/ci.yml` → `backend/pyproject.toml` (uv sync, ruff/mypy), `caddy/Caddyfile` (`backend` job'ning `caddy validate` qadami — `deploy.sh` dagi `caddy reload` yiqilmasligi uchun), `frontend/.nvmrc` + `frontend/package-lock.json` (Node versiya va npm cache), `backend/Dockerfile` + `frontend/Dockerfile` → ghcr.io (`images` job), `scripts/deploy.sh` (deploy job — `TAG` + `REGISTRY`), Telegram secrets (notify job).
- `scripts/generate-client.sh` → backend OpenAPI spec → `frontend/src/client/` (frontend va backend orasidagi kontrakt sinxronizatsiyasi).
- Chop etish zanjiri: `backend/app/api/routes/terminal.py` (`POST /terminal/labels/{id}`) → `backend/app/tasks/__init__.py` (`print_label`) → `backend/app/services/labels.py` (`load_label_data` + `render_label_png` + `backend/app/assets/label-*.png`) → Redis `mes:print:queue:{agent_id}` → `backend/app/api/routes/ws.py` (`/ws/bridge`, `Authorization: Bearer`) → `bridge-agent/agent.py` (`_print_png_gdi`) → USB GoDEX.
- Agent autentifikatsiyasi: `frontend/src/routes/_layout/agents.tsx` → `backend/app/api/routes/bridge_agents.py` (kod berish, `/pair`, `/scan`) → `bridge_agent` jadvali (`token_hash`, `last_seen_at`) → `backend/app/api/routes/ws.py` (`ws_bridge`, `touch_agent`) → `%APPDATA%\MebelixAgent\.env`.
