# 08 — Paketlar va versiyalar

Holat: **2026-07-19** tekshiruvi (oxirgi to'liq upgrade: 2026-07-09). Barcha paketlar 2026-07-09 dagi eng so'ngi stable versiyaga ko'tarilgan (quyidagi 3 ta ataylab qilingan istisno bilan).

**2026-07-19 tekshiruvi:** 2026-07-11 (59a7f59) dan HEAD (8d02c7d) gacha bo'lgan 37 ta commitda `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json` fayllarining birortasi ham **o'zgarmagan**. Buyurtma anketasi (`anketa.$orderId.tsx`, `Order.survey`), arrachi terminali qayta dizayni (`SheetSvg.tsx`, `CutmapView.tsx`) va GoDEX yorliq chop etish — hammasi mavjud bog'liqliklar ustiga qurilgan, bitta ham yangi npm/PyPI paketi qo'shilmagan.

Manifestdan **tashqaridagi** yagona bog'liqlik — `render_label_png()` uchun tizim TrueType shriftlari (Docker image'da o'rnatilmagan). Quyida alohida bo'limda. Yorliqni qog'ozga chiqarish hech qanday paket talab qilmaydi: buni brauzerning o'zi qiladi (o'sha bo'limga qarang).

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

**2026-07-10 (b5ee41d) da qo'shilganlar** — yorliq chop etish (label-printing) feature uchun yangi runtime dependency'lar:

| Paket | Constraint | Lock | Izoh |
| --- | --- | --- | --- |
| tzdata | >=2026.2 | 2026.2 | Windows'da timezone datasi |
| pillow | >=12.3.0 | 12.3.0 | Yorliqni PNG qilib render qilish |
| qrcode | >=8.2 | 8.2 | Yorliqdagi QR kod generatsiyasi |

Bu uchtasining **haqiqiy ishlatilishi** (99cebc3 dagi `render_label_png()` qayta yozilishidan keyin) — hammasi `backend/app/services/labels.py` da, importlar funksiya ichida (modul importi og'irlashmasin):

- **pillow** — `Image`, `ImageDraw`, `ImageFont`, `render_label_png()` ichida. 80×60 mm, 203 dpi → 640×480 px; `draw.fontmode = "1"` bilan antialiasing o'chirilgan (termoprinter 1-bit, aks holda drayver dither qiladi). Shu funksiya `backend/app/assets/label-logo.png` va `label-icon-drill.png` fayllarini ham ochadi.
- **qrcode** — `qrcode.make(d.qr_text, box_size=..., border=0)` shu funksiya ichida. Pillow o'rnatilgani uchun PIL image qaytaradi va to'g'ridan-to'g'ri yorliq rasmiga joylashtiriladi.
- **tzdata** — `zoneinfo.ZoneInfo("Asia/Tashkent")`, `load_label_data()` da `printed_at` qiymati uchun (modul darajasidagi import).

`labels.py` da shu uchtadan boshqa hech narsa yo'q: modul `LabelData`, `load_label_data()`, `_n()` va `render_label_png()` dan iborat — PNG maketi yagona chiqish formati, printer dialekti (EZPL va h.k.) generatsiya qilinmaydi.

Dev group'dagi `websockets>=16.0` `backend/app` da hech qayerda import qilinmaydi, lekin **runtime uchun kerak**: `uvicorn` bu yerda `[standard]` extrasisiz o'rnatilgan, WS protokol implementatsiyasini esa `uvicorn/protocols/websockets/auto.py` `import websockets` bilan tanlaydi. Paket bo'lmasa `AutoWebSocketsProtocol` `None` bo'lib qoladi va `/ws/events` ishlamaydi. Image'da mavjud, chunki `backend/Dockerfile` `uv sync --frozen` ni `--no-dev` siz chaqiradi — dev group ham o'rnatiladi. Agar dev group tozalansa, `websockets` asosiy `dependencies` ga ko'chirilishi kerak.

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

**2026-07-19:** `frontend/src` dagi barcha tashqi importlar `package.json` da e'lon qilingan — e'lon qilinmagan (phantom) bog'liqlik yo'q. Jadvalda ko'rsatilmagan, lekin ishlatiladigan runtime paketlar: `qrcode.react` 4.2.0 (`components/Terminal/CutmapView.tsx`, `routes/_layout/employees.tsx`), `react-day-picker` 10.0.1 (`ui/date-picker`, anketa sanalarida), `sonner` 2.0.7 (`useCustomToast`). Yangi `ui/textarea.tsx` — xom `<textarea>` ustidagi wrapper, Radix paketi talab qilmaydi; `SheetSvg.tsx` faqat React va inline SVG ishlatadi (chizma kutubxonasi yo'q).

## Tizim darajasidagi bog'liqliklar (paket menejeridan tashqari)

### Chop etish: paket emas, sozlama

Printerli kompyuterga (arrachi monobloki) **hech qanday dastur o'rnatilmaydi** — na agent, na drayverdan boshqa narsa. Chop etish butunlay brauzerda: `CutmapView.tsx` dagi `printLabelPng()` yashirin `<iframe>` ochadi (`srcdoc` ichida `@page{size:80mm 60mm;margin:0}` va `GET /api/v1/terminal/labels/{instance_id}.png`), rasm yuklangach `win.print()` chaqiradi. Parallel `POST /api/v1/terminal/labels/{instance_id}` faqat `label_printed_at` ni yozadi va `ws_manager.publish("label.printed", ...)` qiladi (TABLO uchun) — navbat ham, arq taski ham yo'q.

Shuning uchun bu bo'g'inda PyPI/npm bog'liqligi o'rniga uchta sozlama turadi:

| Nima | Qiymat | Nima uchun |
| --- | --- | --- |
| Chrome yorlig'i | `chrome.exe --kiosk-printing --kiosk <url>/terminal` | `--kiosk-printing` chop etish dialogini o'chiradi — `win.print()` to'g'ridan-to'g'ri standart printerga ketadi |
| Standart printer | GoDEX G500-U (USB) | G500-U faqat USB; chekni printer yonidagi odam bosadi, masofaviy chop etish talab qilinmaydi |
| Drayver qog'ozi | 80×60 mm | `render_label_png()` aynan shu o'lchamda chizadi (203 dpi → 640×480 px); mos kelmasa drayver masshtablaydi |

`--kiosk-printing` siz ochilgan brauzerda oqim baribir ishlaydi — faqat operator har safar chop etish dialogini tasdiqlaydi.

### Shriftlar

`render_label_png()` PyPI paketlaridan tashqari **OS shriftlariga** bog'liq. `labels.py` dagi qidiruv ro'yxatlari:

- `_FONT_REGULAR`: `C:/Windows/Fonts/arial.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` → `/usr/share/fonts/dejavu/DejaVuSans.ttf`
- `_FONT_BOLD`: `C:/Windows/Fonts/arialbd.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` → `/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf`

Hech biri topilmasa `ImageFont.load_default()` ga tushadi (kichik bitmap shrift — `size_mm` e'tiborga olinmaydi, yorliq matni o'lchamsiz chiqadi).

⚠️ `backend/Dockerfile` final stage'da faqat `curl` o'rnatiladi (`apt-get install -y --no-install-recommends curl`) — `fonts-dejavu-core` yo'q. Ya'ni konteynerda yuqoridagi barcha yo'llar topilmaydi va yorliq `load_default()` bilan render bo'ladi. Windows dev mashinasida arial.ttf topilgani uchun muammo lokal ko'rinmaydi.

Yorliq rasm assetlari — `backend/app/assets/label-logo.png`, `label-icon-drill.png` — image'ga `COPY backend /app/backend` orqali, wheel'ga esa `[tool.hatch.build.targets.wheel] include = ["app/"]` orqali tushadi.

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
