# 08 — Paketlar va versiyalar

Holat: **2026-07-09**. Barcha paketlar shu sanadagi eng so'ngi stable versiyaga ko'tarilgan (quyidagi 2 ta ataylab qilingan istisno bilan).

## Yangilash tarixi (2026-07-09 upgrade)

### Backend (`backend/pyproject.toml` + `uv.lock`)

`uv lock --upgrade && uv sync --all-groups` bilan yangilandi. `pyproject.toml` dagi `>=` minimal constraintlar o'zgartirilmadi — real versiyalarni `uv.lock` boshqaradi.

Lock'da ko'tarilganlar: `uvicorn` 0.50.0→0.51.0, `mypy` 2.1.0→2.2.0, `cffi` 2.0.0→2.1.0, `filelock`, `librt`, `python-discovery`, `types-setuptools`, `virtualenv`.

Asosiy paketlar (yangilangandan keyin):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| fastapi | 0.139.0 | latest |
| starlette | 1.3.1 | latest (fastapi bilan keladi) |
| uvicorn | 0.51.0 | latest |
| gunicorn | 26.0.0 | latest |
| pydantic | 2.13.4 | latest |
| sqlalchemy | 2.0.51 | latest |
| alembic | 1.18.5 | latest |
| asyncpg | 0.31.0 | latest |
| **redis** | **5.3.1** | ⚠️ 8.0.1 mavjud, lekin `arq` bloklaydi (pastga qarang) |
| arq | 0.28.0 | latest |
| pyjwt | 2.13.0 | latest |
| bcrypt | 5.0.0 | latest |
| mypy (dev) | 2.2.0 | latest |
| ruff (dev) | 0.15.20 | latest |
| pre-commit (dev) | 4.6.0 | latest |

Tekshiruv: `uv run ruff check .` ✅ · `uv run mypy app` ✅ (46 fayl) · `import app.main` ✅

### Frontend (`frontend/package.json` + `package-lock.json`)

`npm update` bilan barcha paketlar caret range ichida latestga ko'tarildi (jumladan: vite 8.1.4, @biomejs/biome 2.5.3, lucide-react 1.24.0, radix-ui paketlari). Runtime dependencies allaqachon latest edi.

Asosiy paketlar (yangilangandan keyin):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| react / react-dom | 19.2.7 | latest |
| @tanstack/react-query | 5.101.2 | latest |
| @tanstack/react-router | 1.170.17 | latest |
| @tanstack/react-table | 8.21.3 | latest |
| axios | 1.18.1 | latest |
| tailwindcss / @tailwindcss/vite | 4.3.2 | latest |
| zod | 4.4.3 | latest |
| react-hook-form | 7.81.0 | latest |
| vite (dev) | 8.1.4 | latest |
| @biomejs/biome (dev) | 2.5.3 | latest |
| **typescript (dev)** | **6.0.3** | ⚠️ 7.0.2 mavjud, lekin openapi-ts bloklaydi (pastga qarang) |
| **@hey-api/openapi-ts (dev)** | **0.86.12** | ⚠️ 0.99.0 mavjud, lekin legacy client kerak (pastga qarang) |

Tekshiruv: `npm run build` (tsc + vite) ✅ · `bash scripts/generate-client.sh` ✅ (client qayta generate qilindi, build o'tdi)

## Ataylab ushlab qolingan versiyalar (ceilinglar)

### 1. redis 5.3.1 (latest: 8.0.1)

`arq` (task queue, latest 0.28.0) `redis[hiredis]<6,>=4.2.0` talab qiladi. redis 5.3.1 — shu constraint ichidagi maksimum.

**Yangilash yo'li:** arq redis 6+ ni qo'llaganda `uv lock --upgrade` o'zi ko'taradi. Yoki arq'dan boshqa queue'ga (masalan taskiq, saq) o'tilsa.

### 2. @hey-api/openapi-ts 0.86.12 (latest: 0.99.0)

`openapi-ts.config.ts` `legacy/axios` client ishlatadi (`OpenAPI` config obyekti, `ApiError`, `CancelablePromise`, `*Service` klasslari — butun frontend shu API'ga qurilgan). **0.87.0 da legacy clientlar butunlay olib tashlangan** — 0.99.0 bilan `legacy/axios` jimgina 0 fayl generate qiladi (0.99 sinab ko'rildi: `src/client` bo'shab qoldi, qaytarildi). 0.86.12 — legacy clientni qo'llaydigan eng so'ngi versiya.

⚠️ **Security eslatma:** 0.86.12 ichidagi `handlebars` transitive dependency'sida npm audit 2 ta vulnerability ko'rsatadi (1 high, 1 critical). Bu **faqat dev-time code-generator** — production bundlega kirmaydi, input esa o'zimizning `openapi.json`. Xavf past, lekin quyidagi migratsiya bilan butunlay yo'qoladi.

**Yangilash yo'li:** `legacy/axios` dan modern `@hey-api/client-axios` pluginiga migratsiya:

- `openapi-ts.config.ts` da `legacy/axios` → `@hey-api/client-axios`
- `src/client/core/*` yo'qoladi; `OpenAPI.TOKEN` / interceptorlar o'rniga `client.setConfig()` / `client.interceptors`
- `hooks/useAuth.ts`, `queries/users.ts` va `ApiError` ishlatadigan barcha joylar yangi API'ga moslanadi
- Keyin `@hey-api/openapi-ts` → `^0.99.0` va TypeScript 7 ham ochiladi

### 3. typescript 6.0.3 (latest: 7.0.2)

TypeScript 7 — Go'da yozilgan native port; eski compiler API'ni (`ts.SyntaxKind` va h.k.) bermaydi. `@hey-api/openapi-ts` (0.86 ham, 0.99 ham) shu API'ga bog'liq — TS 7 bilan `generate-client` crash bo'ladi (sinab ko'rildi: `TypeError: Cannot read properties of undefined (reading 'AnyKeyword')`). `tsc` build o'zi TS 7 bilan ishlagan edi, lekin bitta repo'da ikkita TS ushlab turish shart emas.

**Yangilash yo'li:** openapi-ts TS 7 ni qo'llaganda (yoki yuqoridagi modern client migratsiyasidan keyin qayta tekshirilganda) `typescript` → `^7`.

## Yangilashni takrorlash (keyingi safar)

```bash
# Backend
cd backend && uv lock --upgrade && uv sync --all-groups
uv run ruff check . && uv run mypy app

# Frontend
cd frontend && npm update && npm outdated   # outdated bo'sh bo'lsa — hammasi latest
npm run build

# Client regeneratsiya (backend schema o'zgarganda)
bash scripts/generate-client.sh
```

`npm outdated` major bump ko'rsatsa — `package.json` dagi caret versiyani qo'lda ko'tarish kerak (caret major'dan o'tkazmaydi). Yuqoridagi 3 ceiling'ni tekshirishni unutmang.
