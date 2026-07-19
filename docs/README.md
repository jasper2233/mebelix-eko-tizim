# MebeliX MES — Hujjatlar

Loyihaning to'liq texnik hujjatlari. Har bir fayl o'z subsystemidagi **har bir manba faylni** boshidan oxirigacha o'rganib yozilgan va manba kod bilan solishtirilib tekshirilgan (oxirgi sinxronizatsiya: 2026-07-19).

| Hujjat | Mazmun |
| --- | --- |
| [01-architecture.md](01-architecture.md) | Umumiy arxitektura: stack, topologiya diagrammasi, request lifecycle (login + authenticated flow), yorliq chop etish zanjiri, buyurtma anketasi, arrachi terminali, kod konventsiyalari |
| [02-backend-core.md](02-backend-core.md) | `backend/app/core/` + `main.py`: config, DB engine, security (JWT + bcrypt), middleware, logger, ARQ worker (`print_label`), rate limit, queue |
| [03-backend-api.md](03-backend-api.md) | `backend/app/api/`: barcha endpointlar jadvali (method, path, auth, schema), anketa (`/survey`, `/survey/photos`), terminal/yorliq endpointlari, deps (get_current_user va h.k.) |
| [04-backend-data.md](04-backend-data.md) | Models (jadval strukturalari, `order.survey` JSONB), Pydantic schemas (`OrderSurvey` va b.), CRUD layer, Alembic migrations, CLI commandlar, ARQ tasklar |
| [05-frontend-app.md](05-frontend-app.md) | `frontend/src/`: routing (TanStack Router), `/anketa/:id`, terminal kiosk rejimi, auth flow, hooks, queries, generated API client, Vite/TS/Biome config |
| [06-frontend-components.md](06-frontend-components.md) | Komponentlar: Admin, Common, Sidebar, UserSettings, Terminal (`CutmapView`, `SheetSvg`), anketa komponentlari, shadcn/ui jadvali (custom o'zgartirishlar bilan) |
| [07-infra-devops.md](07-infra-devops.md) | Docker Compose (local/prod), Dockerfilelar, Caddy, nginx, Makefile, scriptlar, pre-commit, CI/CD (avto-deploy, rollback, backup, Telegram notify), **chop etish infratuzilmasi (bridge-agent + GoDEX G500-U)**, env variablelar jadvali |
| [08-packages.md](08-packages.md) | Paket versiyalari, upgrade tarixi, bridge-agent bog'liqliklari (manifestsiz), ataylab ushlab qolingan versiyalar (ceilinglar) va yangilash yo'llari |
| [09-mes-domain.md](09-mes-domain.md) | MES domen qatlami (TT implementatsiyasi): data model, GibLab parser (CS blob, SCX), scan engine, real-time, buyurtma anketasi, yorliq chop etish (PNG + EZPL), API xaritasi, frontend tuzilishi |
| [Mebelix_MES_TZ_v2.2.docx](Mebelix_MES_TZ_v2.2.docx) | Texnik Topshiriq (TT) — talablarning yagona manbasi |

## Yangilab borish

Kod o'zgarganda tegishli hujjatni yangilang. Paket yangilashda [08-packages.md](08-packages.md) dagi "Yangilashni takrorlash" bo'limiga amal qiling.
