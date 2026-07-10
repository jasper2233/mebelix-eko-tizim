# MebeliX MES — Hujjatlar

Loyihaning to'liq texnik hujjatlari. Har bir fayl o'z subsystemidagi **har bir manba faylni** boshidan oxirigacha o'rganib yozilgan va manba kod bilan solishtirilib tekshirilgan (2026-07-09).

| Hujjat | Mazmun |
| --- | --- |
| [01-architecture.md](01-architecture.md) | Umumiy arxitektura: stack, topologiya diagrammasi, request lifecycle (login + authenticated flow), kod konventsiyalari |
| [02-backend-core.md](02-backend-core.md) | `backend/app/core/` + `main.py`: config, DB engine, security (JWT + bcrypt), middleware, logger, ARQ worker, rate limit, queue |
| [03-backend-api.md](03-backend-api.md) | `backend/app/api/`: barcha endpointlar jadvali (method, path, auth, schema), deps (get_current_user va h.k.) |
| [04-backend-data.md](04-backend-data.md) | Models (User, Item — jadval strukturalari), Pydantic schemas, CRUD layer, Alembic migrations, CLI commandlar, ARQ tasklar |
| [05-frontend-app.md](05-frontend-app.md) | `frontend/src/`: routing (TanStack Router), auth flow, hooks, queries, generated API client, Vite/TS/Biome config |
| [06-frontend-components.md](06-frontend-components.md) | Komponentlar: Admin (user CRUD), Common, Sidebar, UserSettings, shadcn/ui jadvali (custom o'zgartirishlar bilan) |
| [07-infra-devops.md](07-infra-devops.md) | Docker Compose (local/prod), Dockerfilelar, Caddy, nginx, Makefile, scriptlar, pre-commit, env variablelar jadvali |
| [08-packages.md](08-packages.md) | Paket versiyalari, 2026-07-09 upgrade tarixi, ataylab ushlab qolingan versiyalar (ceilinglar) va yangilash yo'llari |
| [09-mes-domain.md](09-mes-domain.md) | MES domen qatlami (TT implementatsiyasi): data model, GibLab parser (CS blob, SCX), scan engine, real-time, chop etish (EZPL + bridge-agent), API xaritasi, frontend tuzilishi |
| [Mebelix_MES_TZ_v2.2.docx](Mebelix_MES_TZ_v2.2.docx) | Texnik Topshiriq (TT) — talablarning yagona manbasi |

## Yangilab borish

Kod o'zgarganda tegishli hujjatni yangilang. Paket yangilashda [08-packages.md](08-packages.md) dagi "Yangilashni takrorlash" bo'limiga amal qiling.
