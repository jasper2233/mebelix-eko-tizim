# MebeliX MES — Hujjatlar

Loyihaning to'liq texnik hujjatlari. Har bir fayl o'z subsystemidagi **har bir manba faylni** boshidan oxirigacha o'rganib yozilgan va manba kod bilan solishtirilib tekshirilgan (oxirgi sinxronizatsiya: 2026-09-05).

| Hujjat | Mazmun |
| --- | --- |
| [01-architecture.md](01-architecture.md) | Umumiy arxitektura: stack, topologiya diagrammasi, request lifecycle (login + authenticated flow), yorliq chop etish zanjiri, buyurtma anketasi, arrachi terminali, kod konventsiyalari |
| [02-backend-core.md](02-backend-core.md) | `backend/app/core/` + `main.py`: config, DB engine, security (JWT + bcrypt), middleware, logger, ARQ worker (`print_label`, `print_pachka_label`, `print_waste_label`, `print_badge`), rate limit, queue |
| [03-backend-api.md](03-backend-api.md) | `backend/app/api/`: barcha 152 endpoint (150 HTTP + 2 WS) modul-ma-modul jadvallarda (jumladan «Tizim holati» — `system`); `health`, `login`, `logout` va `users` jadvallarida request/response sxemalari ham, anketa (`/survey`, `/survey/photos`), terminal/yorliq endpointlari, deps (get_current_user va h.k.) |
| [04-backend-data.md](04-backend-data.md) | Models (jadval strukturalari, `order.survey` JSONB), Pydantic schemas (`OrderSurvey` va b.), CRUD layer, Alembic migrations, CLI commandlar, ARQ tasklar |
| [05-frontend-app.md](05-frontend-app.md) | `frontend/src/`: routing (TanStack Router), `/anketa/:id`, terminal kiosk rejimi, auth flow, hooks, queries, generated API client, Vite/TS/Biome config |
| [06-frontend-components.md](06-frontend-components.md) | Komponentlar: People (`PersonDialog` — hodim va hisob bitta dialogda), Clients, Common, Orders, Sidebar, UserSettings, Terminal (`CutmapView`, `SheetSvg`), anketa komponentlari, shadcn/ui jadvali (custom o'zgartirishlar bilan) |
| [07-infra-devops.md](07-infra-devops.md) | Docker Compose (local/prod), Dockerfilelar, Caddy, nginx, Makefile, scriptlar (deploy, serverda saqlanadigan shifrlangan kunlik backup), pre-commit, CI/CD (ghcr.io image build, avto-deploy, avto-rollback, Telegram notify), **chop etish infratuzilmasi (bridge-agent + GoDEX G500-U)**, env variablelar jadvali |
| [08-packages.md](08-packages.md) | Paket versiyalari, upgrade tarixi, bridge-agent bog'liqliklari (manifestsiz), tizim darajasidagi bog'liqliklar (OS shriftlari), ataylab ushlab qolingan versiyalar (ceilinglar) va yangilash yo'llari |
| [09-mes-domain.md](09-mes-domain.md) | MES domen qatlami (TT implementatsiyasi): data model, GibLab parser (CS blob, SCX), scan engine, real-time, buyurtma anketasi, yorliq chop etish (PNG, USB GoDEX), API xaritasi, frontend tuzilishi |
| [10-giblab-reference.md](10-giblab-reference.md) | Manba tizim GibLab: interfeys tuzilishi, `.project` fayl formati (tovarlar, detal/zagotovka/qoldiq, to'rt juft o'lcham, o'lcham kiritish rejimlari), to'qqiz operatsiya turi, XNC dasturi teglari, sozlamalar (katalog, postprotsessorlar, yorliq shablonlari), 1C qoldiq integratsiyasi, parser nimani o'qiydi va nima uchun ogohlantiradi |
| [11-detal-id-nomlash.md](11-detal-id-nomlash.md) | Detal ID qoidasi: `{mahsulot}_{kod}[-N][_n]` — chek = QR = SCX nomi; `-N` kod to'qnashuvi (boshqa detal), `_n` nusxa raqami; qo'llanadigan joylar va misollar |
| [12-oee.md](12-oee.md) | OEE (Prisadka): formula va har qismining manbasi, tarix (2026-08-21 qaytarilgan modul, andon), Pico signal ustuni shartnomasi, ish jadvali sozlamalari, `scripts/oee_audit.sql` va prod auditi natijalari, `scripts/oracles/` dagi tekshiruv skriptlari (§4.14), keyingi qadamlar, ochiq qarorlar, xavflar |
| [13-bazis-3d.md](13-bazis-3d.md) | Bazis `.b3d` formati (teskari muhandislik: konteyner, daraxt kodlashi, kontur segmentlari, iyerarxik joylashuv) va yig'uvchiga ochiq 3D havola moduli: MES bilan bog'lanish kaliti, oqim, capability-URL himoyasi, endpointlar, frontend sahnasi va chegaralar |
| [14-mahsulotlar-ombori.md](14-mahsulotlar-ombori.md) | Mahsulotlar ombori katalogi: to'rt qismli kodlash tizimi (katalog/guruh/model/variant) va matritsa raqamlari, `catalog_item` jadvali, `scripts/catalog_import.py` (varaq → CSV → baza, qoldiqqa tegmaydigan upsert), `/catalog` endpointlari va rollari, `/warehouse` sahifasi |

## Yangilab borish

Kod o'zgarganda tegishli hujjatni yangilang. Paket yangilashda [08-packages.md](08-packages.md) dagi "Yangilashni takrorlash" bo'limiga amal qiling.
