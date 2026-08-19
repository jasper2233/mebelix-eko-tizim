# 08 — Paketlar va versiyalar

Holat: **2026-08-18** to'liq upgrade (oldingisi: 2026-07-09). Barcha paketlar 2026-08-18 dagi eng so'ngi stable versiyaga ko'tarilgan (quyidagi 2 ta ataylab qilingan istisno bilan). Shu upgrade bilan birga ikkita qo'lda manifest o'zgarishi bo'ldi: backend'da `pyjwt[crypto]` → `pyjwt`, frontend'da esa `@hey-api/openapi-ts` `^0.86.12` → `^0.99.0` — bu bilan API klient `legacy/axios` dan zamonaviy `@hey-api/client-axios` pluginiga ko'chdi, ya'ni avvalgi ceiling #2 **yopildi**.

**Manifest tarixi (2026-07-09 upgrade'dan keyin):** manifestlar o'n marta o'zgardi — avval ikkita qo'shish (2026-07-10), keyin uchta kamaytirish (2026-07-27), so'ng ikkita metadata tahriri (2026-08-05 va 2026-08-13) va oxirida 2026-08-18 ning uchta commiti:

- `26e00af` — MES core bilan `openpyxl` (runtime, Excel eksport) va dev'ga `types-openpyxl` + `websockets` qo'shildi;
- `b5ee41d` — yorliq chop etish uchun `tzdata`/`pillow`/`qrcode` (pastdagi jadval), frontend'ga `@radix-ui/react-popover` va `react-day-picker`;
- `4306a42` — `websockets` dev group'dan asosiy `dependencies` ga ko'chirildi (pastda alohida bo'lim);
- `87d23ab` — `httpx` va `uuid6` runtime'dan, `types-redis` dev'dan chiqarildi (kod ularni hech qayerda import qilmasdi); `uv.lock` 71 → **63** paketga tushdi (`certifi`, `httpcore`, `types-cffi`, `types-pyopenssl`, `types-setuptools` transitiv bo'lib birga ketdi);
- `a916088` — `@tanstack/react-table` o'chirildi (`Common/DataTable.tsx` va `Admin/columns.tsx` bilan birga; `admin.tsx` endi oddiy `<Table>` chizadi), `backend/pyproject.toml` dagi `license` kaliti ham olib tashlandi;
- `a4f7f21` — `frontend/package.json` da `name` `frontend` → `mebelix-mes-frontend` bo'ldi va yangi `description` kaliti qo'shildi; bog'liqliklarning o'ziga tegilmadi;
- `159e27b` — `frontend/package.json` dagi `description` matnida "sex" → "tsex" (repo bo'yicha atama almashtirishning bir qismi); bu ham sof metadata, bog'liqliklarga tegmagan;
- **2026-08-18 (shu upgrade, `3b814a8` + `a0c506e`)** — `backend/pyproject.toml` da `pyjwt[crypto]` → `pyjwt` (extra olib tashlandi, pastda alohida bo'lim); `frontend/package.json` da `@hey-api/openapi-ts` `^0.86.12` → `^0.99.0`, `axios` qattiq pin `1.18.1` → `^1.19.0` va yangi `overrides` bloki (`js-yaml` `^4.3.1`);
- `5eec038` — shu seriyaning o'z diffiga qilingan audit `a0c506e` da qo'shilgan `@hey-api/client-axios` `^0.9.1` runtime bog'liqligini olib tashladi: openapi-ts 0.99 klient kodini `src/client/client/` ga inline generatsiya qiladi, ya'ni npm paketining o'zi kerak emas (pastga qarang).

Bulardan tashqari ikkita bog'liqlik manifestdan **tashqarida** yashaydi va ikkalasi ham quyida alohida bo'limlarda yozilgan:

- bridge-agent'ning Windows GDI chop etish yo'li — `pywin32` + `pillow` (repo'da manifest fayli yo'q);
- `labels.py` dagi uchala render funksiyasi uchun tizim TrueType shriftlari (Docker image'ga `fonts-liberation` apt paketi bilan qo'shilgan).

## Yangilash tarixi (2026-08-18 upgrade)

### Backend (`backend/pyproject.toml` + `uv.lock`)

`uv lock --upgrade && uv sync --all-groups` bilan yangilandi. `pyproject.toml` dagi `>=` minimal constraintlar o'zgartirilmadi — real versiyalarni `uv.lock` boshqaradi.

Lock'da ko'tarilgan transitivlar: `annotated-doc` 0.0.4→0.0.5, `annotated-types` 0.7.0→0.8.0, `anyio` 4.14.1→4.14.2, `ast-serialize` 0.6.0→0.8.0, `filelock` 3.29.7→3.32.3, `hiredis` 3.4.0→3.4.1, `idna` 3.18→3.19, `librt` 0.13.0→0.15.0, `mako` 1.3.12→1.4.1, `packaging` 26.2→26.3, `platformdirs` 4.10.0→4.11.3, `prometheus-client` 0.25.0→0.26.0, `python-discovery` 1.4.4→1.5.2, `python-dotenv` 1.2.2→1.2.3, `typing-inspection` 0.4.2→0.4.4, `virtualenv` 21.6.0→21.7.4.

Asosiy paketlar (yangilangandan keyin):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| fastapi | 0.141.1 | latest (0.139.0 edi) |
| starlette | 1.6.0 | latest (fastapi bilan keladi; 1.3.1 edi) |
| uvicorn | 0.52.3 | latest (0.51.0 edi) |
| gunicorn | 26.0.0 | latest (o'zgarmadi) |
| pydantic | 2.13.4 | latest (o'zgarmadi) |
| sqlalchemy | 2.0.52 | latest (2.0.51 edi) |
| alembic | 1.19.1 | latest (1.18.5 edi) |
| asyncpg | 0.31.0 | latest (o'zgarmadi) |
| **redis** | **5.3.1** | ⚠️ 8.1.0 mavjud, lekin `arq` bloklaydi (pastga qarang) |
| arq | 0.28.0 | latest (o'zgarmadi) |
| pyjwt | 2.13.0 | latest; `[crypto]` extra'siz (pastga qarang) |
| bcrypt | 5.0.0 | latest (o'zgarmadi) |
| websockets | 17.0.1 | latest (16.0 edi) |
| mypy (dev) | 2.3.1 | latest (2.2.0 edi) |
| ruff (dev) | 0.16.3 | latest (0.15.20 edi) |
| pre-commit (dev) | 4.6.2 | latest (4.6.0 edi) |

Tekshiruv: `uv run ruff check .` ✅ · `uv run mypy app` ✅ (125 fayl) · `import app.main` ✅

**`pyjwt[crypto]` → `pyjwt` (extra olib tashlandi):** `app/core/config.py` dagi `ALGORITHM` — `HS256`, ya'ni simmetrik HMAC, va `app/core/security.py` tokenni faqat shu bilan imzolaydi/tekshiradi (`jwt.encode(..., algorithm=ALGORITHM)` / `jwt.decode(..., algorithms=[ALGORITHM])`). `cryptography` faqat RS\*/ES\* kabi asimmetrik algoritmlar uchun kerak bo'lardi. Extra olingach lock'dan uchta paket birgalikda chiqib ketdi — `cryptography` 49.0.0, `cffi` 2.1.0, `pycparser` 3.0 — va `uv.lock` 63 → **60** paketga tushdi. `pyproject.toml` da qator ustiga sabab izoh qilib yozib qo'yilgan.

Jadvalda ko'rsatilmagan, lekin manifestda e'lon qilingan runtime paketlar (lock versiyalari bilan): `openpyxl` 3.1.5 — Excel eksport (`app/services/excel.py`; dev'da `types-openpyxl` 3.1.5.20260807), `pydantic-settings` 2.15.0 — `app/core/config.py` dagi `Settings`, `python-multipart` 0.0.32 — fayl yuklash (FastAPI `UploadFile`/`Form`, `orders.py`), `prometheus-fastapi-instrumentator` 8.1.0 — `/metrics` (`app/core/setup.py`), `uvloop` 0.22.1 — faqat `sys_platform != 'win32'`, `greenlet` 3.5.5 — SQLAlchemy async uchun.

**2026-07-10 (b5ee41d) da qo'shilganlar** — yorliq chop etish (label-printing) feature uchun yangi runtime dependency'lar:

| Paket | Constraint | Lock | Izoh |
| --- | --- | --- | --- |
| tzdata | >=2026.2 | 2026.3 | Windows'da timezone datasi |
| pillow | >=12.3.0 | 12.3.0 | Yorliqni PNG qilib render qilish |
| qrcode | >=8.2 | 8.2 | Yorliqdagi QR kod generatsiyasi |

Bu uchtasining **haqiqiy ishlatilishi** (99cebc3 dagi `render_label_png()` qayta yozilishidan keyin) — hammasi `backend/app/services/labels.py` da, importlar funksiya ichida (modul importi og'irlashmasin):

- **pillow** — `Image`, `ImageDraw`, `ImageFont`, uchala render funksiyasi ichida. Detal yorlig'i 80×60 mm, 203 dpi → 640×480 px; hammasida `draw.fontmode = "1"` bilan antialiasing o'chirilgan (termoprinter 1-bit, aks holda drayver dither qiladi). `render_label_png()` `backend/app/assets/label-logo.png` va `label-icon-drill.png` fayllarini, `render_pachka_label_png()` esa `label-logo.png` ni ochadi.
- **qrcode** — `qrcode.make(..., box_size=..., border=0)` xuddi shu uchala funksiya ichida: `d.qr_text` (detal), `d.code` (pachka), `d.badge_id` (beyjik). Pillow o'rnatilgani uchun PIL image qaytaradi va to'g'ridan-to'g'ri yorliq rasmiga joylashtiriladi.
- **tzdata** — `ZoneInfo("Asia/Tashkent")` uchun IANA ma'lumoti (Windows'da tizimda yo'q). 2026-08-05 dan konstanta bitta joyda — `app.core.config.TASHKENT_TZ`; `labels.py` uni `printed_at` uchun import qiladi (`load_label_data()`), `app/tasks/__init__.py` (`print_pachka_label` dagi `printed_at`), `app/api/routes/audit.py` va `app/api/routes/reports.py` ham shu konstantani ishlatadi.

`labels.py` ning butun tashqi yuzasi shu uchtaga tayanadi — boshqa paket talab qilmaydi: `LabelData` + `load_label_data()` + `render_label_png()` (detal yorlig'i, yordamchisi `_n()`; `_bw()` esa uchala render funksiyasi ishlatadigan umumiy 1-bit chegara filtri), `PachkaLabelData` + `render_pachka_label_png()` (qadoq cheki) va `BadgeLabelData` + `render_badge_png()` (hodim beyjigi). Uchala render funksiyasini `backend/app/tasks/__init__.py` dagi tasklar chaqiradi (`all_tasks = [print_label, print_pachka_label, print_badge]`): ular PNG'ni base64 qilib Redis navbatiga (`mes:print:queue`) qo'yadi, job JSON'i `{"type", "instance_id", "png"}` — printer dialekti generatsiya qilinmaydi, shuning uchun task tomonda ham qo'shimcha bog'liqlik yo'q.

`websockets>=16.0` asosiy `dependencies` da, garchi `backend/app` ichida hech qayerda `import` qilinmasa ham (repo bo'yicha yagona `import websockets` — `bridge-agent/agent.py` da). Sabab: `uvicorn` 0.52.3 `[standard]` extra'siz o'rnatilgan (lock'da bog'liqliklari faqat `click` + `h11`), `wsproto` esa umuman yo'q — ya'ni `/ws/events` va `/ws/bridge` uchun WebSocket transporti aynan shu paket. Dev group'da tursa `uv sync --no-dev` bilan yig'ilgan image'da TABLO ham, yorliq chop etish ham jimgina o'lardi; shuning uchun `pyproject.toml` da qator ustiga izoh yozib qo'yilgan.

### Frontend (`frontend/package.json` + `package-lock.json`)

`npm update` bilan barcha paketlar caret range ichida latestga ko'tarildi (jumladan: vite 8.2.1, @biomejs/biome 2.5.9, lucide-react 1.31.0, radix-ui/tanstack paketlari). Ikkita qo'lda o'zgarish: `axios` qattiq pin (`1.18.1`) edi — `^1.19.0` ga o'tkazildi, `@hey-api/openapi-ts` esa `^0.86.12` → `^0.99.0` (caret major'dan o'tkazmaydi). Biome 2.5.9 uchun `biome migrate` ishlatildi — `frontend/biome.json` dagi `$schema` 2.5.3 → 2.5.9 ga ko'chdi, qoidalarning o'ziga tegilmadi.

Asosiy paketlar (yangilangandan keyin):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| react / react-dom | 19.2.8 | latest |
| @tanstack/react-query | 5.101.4 | latest |
| @tanstack/react-router | 1.170.29 | latest |
| axios | 1.19.0 | latest (endi caret: `^1.19.0`) |
| tailwindcss / @tailwindcss/vite | 4.3.3 | latest |
| zod | 4.4.3 | latest |
| react-hook-form | 7.85.0 | latest |
| vite (dev) | 8.2.1 | latest |
| @biomejs/biome (dev) | 2.5.9 | latest |
| **typescript (dev)** | **6.0.3** | ⚠️ 7.0.2 mavjud, lekin openapi-ts bloklaydi (pastga qarang) |
| @hey-api/openapi-ts (dev) | 0.99.0 | latest — 0.86.12 (`legacy/axios`) dan migratsiya qilindi |

`@hey-api/client-axios` jadvalda yo'q va `package.json` da ham yo'q: bu npm paket emas, `openapi-ts.config.ts` dagi plugin **nomi** (oddiy string). 0.99 klient runtime'ini `src/client/client/` ga inline generatsiya qiladi, generatsiya qilingan fayllar esa faqat `axios` ni import qiladi (`src/client/client/client.gen.ts`).

Tekshiruv: `npm run build` (tsc + vite) ✅ · `bash scripts/generate-client.sh` ✅ (klient 0.99 bilan noldan qayta generate qilindi — `openapi.json` 106 operatsiya; fayl git'da tracked emas, skript uni har safar backend'dan eksport qiladi) · `npm audit` ✅ 0 vulnerability

**2026-08-18 tekshiruvi:** `frontend/src` dagi barcha TS/TSX tashqi importlar (29 ta modul) `package.json` da e'lon qilingan — e'lon qilinmagan (phantom) bog'liqlik yo'q. Teskari yo'nalishda ham toza: e'lon qilingan 32 ta runtime bog'liqlikning 29 tasi aynan shu importlar, qolgan uchtasi (`@fontsource-variable/archivo`, `tailwindcss`, `@tailwindcss/vite`) TS importisiz — CSS/vite-config tomonda keladi, ya'ni ishlatilmaydigan (orphan) bog'liqlik yo'q. `src/index.css` boshidagi `@import` qatorlari: `tailwindcss`, `tw-animate-css` 1.4.0 (dev) va `@fontsource-variable/archivo` 5.3.0; `@tailwindcss/vite` esa `vite.config.ts` dagi plagin. Jadvalda ko'rsatilmagan, lekin ishlatiladigan runtime paketlar: `qrcode.react` 4.2.0 (`components/Terminal/CutmapView.tsx`, `routes/_layout/employees.tsx`), `react-day-picker` 10.0.1 (`ui/date-picker` — anketa, buyurtma formasi, hisobot va log sanalarida), `sonner` 2.0.8 (`ui/sonner`, `Toaster` `routes/__root.tsx` da mount qilinadi; `useCustomToast` 2026-08-05 da o'chirilgan — komponentlar to'g'ridan-to'g'ri `toast.success/error` chaqiradi). `ui/textarea.tsx` — xom `<textarea>` ustidagi wrapper, Radix paketi talab qilmaydi; `Terminal/SheetSvg.tsx` faqat React va inline SVG ishlatadi (chizma kutubxonasi yo'q).

## Bridge-agent bog'liqliklari (manifestsiz)

`bridge-agent/` da `pyproject.toml` ham, `requirements.txt` ham **yo'q**. To'rtta runtime paket agent `mebelix-agent.exe` ichiga PyInstaller bilan yig'iladi (`pyinstaller --onefile --noconsole --name mebelix-agent agent.py`) — tsexdagi kompyuterga na Python, na `pip`, na alohida paket o'rnatiladi. `pyinstaller`ning o'zi faqat **build-time** asbob (dasturchi mashinasida), runtime bog'liqlik emas va hech qaysi manifestda yozilmagan.

| Paket | Nima uchun |
| --- | --- |
| websockets | `uplink()` — serverga outbound WS (`/api/v1/ws/bridge`), modul darajasidagi yagona tashqi import. **>=14 talab** — v13/14 shim 2026-08-05 da olib tashlandi, README'dagi build qatori `pip install "websockets>=14" ...` |
| pywin32 | `win32print` — `_detect_printer()` da printerni topish va `_print_png_gdi()` da DEVMODE; `win32gui`, `win32ui`, `win32con` — GDI konteksti; `win32api`+`win32event`+`winerror` — `_single_instance()` mutexi |
| pillow | `PIL.Image`, `PIL.ImageWin` — serverdan kelgan base64 PNG'ni GDI kontekstiga chizish |
| pynput | `start_scan_forward()` — stanok skanerining klaviatura kirishini passiv kuzatib `/bridge-agents/scan` ga forvard qilish. Ixtiyoriy: o'rnatilmagan bo'lsa faqat skan-forvard jim o'chadi, chop etish ishlayveradi |

Birinchi uchtasi majburiy: chiqish yo'li bitta — `_print_png_gdi()` (Windows drayveri, DEVMODE'da qog'oz 80×60 mm ga majburlanadi). `pywin32` va `pillow` importlari funksiya ichida, lekin ularsiz `send_to_printer()` ishlamaydi, ya'ni agent amalda Windows'ga bog'langan.

Pip paketlardan tashqari exe **tkinter/Tcl-Tk** ga ham tayanadi (stdlib, lekin Tcl/Tk runtime'ini PyInstaller exe'ga qo'shadi): pairing oynasi `_pair_dialog()` va `_alert()` messageboxlari shu bilan chiziladi; tkinter bo'lmasa pairing konsolga (`_pair_console()`) tushadi, `_alert()` esa jim log bilan kifoyalanadi. `_notify_connected()` dagi "serverga ulandi" xabari esa `ctypes.windll.user32.MessageBoxTimeoutW` (stdlib `ctypes`) bilan chiqadi.

Printer nomi sozlanmaydi: `_detect_printer()` `win32print.EnumPrinters()` bilan nomida "godex" bor lokal printerni qidiradi, `PRINTER_NAME` env faqat qo'lda override uchun. Agent env'lari to'liq ro'yxati — `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`, `SCAN_FORWARD` (default yoqiq, `0` o'chiradi).

Agent faqat printer ulangan kompyuterga o'rnatiladi. Menejer, texnolog va boshqa post terminallarida hech qanday paket kerak emas — ular brauzerdan tugmani bosadi.

## Tizim darajasidagi bog'liqliklar (paket menejeridan tashqari)

Yorliq render qilish PyPI paketlaridan tashqari **OS shriftlariga** bog'liq — uchala funksiya (`render_label_png()`, `render_pachka_label_png()`, `render_badge_png()`) bitta qidiruv ro'yxatiga murojaat qiladi. `labels.py` dagi ro'yxatlar:

- `_FONT_REGULAR`: `C:/Windows/Fonts/arial.ttf` → `/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` → `/usr/share/fonts/dejavu/DejaVuSans.ttf`
- `_FONT_BOLD`: `C:/Windows/Fonts/arialbd.ttf` → `/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` → `/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf`

Liberation Sans birinchi Linux nomzodi: Arial bilan metrik mos (harf kengliklari bir xil), shuning uchun Windowsda sozlangan maket serverda ham aynan shunday joylashadi. DejaVu kengroq — maketni siljitadi, faqat zaxira bo'lib qoladi.

Hech biri topilmasa `ImageFont.load_default()` ga tushadi (kichik bitmap shrift — `size_mm` e'tiborga olinmaydi, yorliq matni o'lchamsiz chiqadi).

`backend/Dockerfile` final stage'da `curl` bilan birga `fonts-liberation` ham o'rnatiladi (`apt-get install -y --no-install-recommends curl fonts-liberation`) — konteynerda `LiberationSans-Regular.ttf` topiladi va yorliq `load_default()` ga tushmaydi. `fonts-dejavu-core` o'rnatilmagan: DejaVu yo'llari faqat boshqa muhitlar uchun zaxira.

Yorliq rasm assetlari — `backend/app/assets/label-logo.png`, `label-icon-drill.png` — image'ga `COPY backend /app/backend` orqali, wheel'ga esa `[tool.hatch.build.targets.wheel] include = ["app/"]` orqali tushadi.

## Ataylab ushlab qolingan versiyalar (ceilinglar)

### 1. redis 5.3.1 (latest: 8.1.0)

`arq` (task queue, latest 0.28.0) `redis[hiredis]<6,>=4.2.0` talab qiladi. redis 5.3.1 — shu constraint ichidagi maksimum.

**Yangilash yo'li:** arq redis 6+ ni qo'llaganda `uv lock --upgrade` o'zi ko'taradi. Yoki arq'dan boshqa queue'ga (masalan taskiq, saq) o'tilsa.

### 2. typescript 6.0.3 (latest: 7.0.2)

TypeScript 7 — Go'da yozilgan native port; eski compiler API'ni (`ts.SyntaxKind` va h.k.) bermaydi. `@hey-api/openapi-ts` shu API'ga bog'liq — TS 7 bilan `generate-client` crash bo'ladi (`TypeError: Cannot read properties of undefined (reading 'AnyKeyword')`). 2026-08-18 da qayta sinaldi: **0.99.0 ga migratsiyadan keyin ham** natija o'zgarmadi, ya'ni bu ceiling legacy clientning oqibati emas edi — TS 7.0.2 rad etildi va `typescript` `^6.0.3` da qoldi. Buni `openapi-ts` 0.99 ning o'z `peerDependencies` i ham tasdiqlaydi: `typescript: ">=5.5.3 || >=6.0.0 || 6.0.1-rc"` — 7 umuman e'lon qilinmagan. `tsc` build o'zi TS 7 bilan ishlagan edi, lekin bitta repo'da ikkita TS ushlab turish shart emas.

**Yangilash yo'li:** openapi-ts TS 7 ni qo'llagan versiyani chiqarganda `typescript` → `^7`.

### Yopilgan ceiling: @hey-api/openapi-ts 0.86.12 → 0.99.0

Ilgari uchinchi ceiling `@hey-api/openapi-ts` 0.86.12 edi: `openapi-ts.config.ts` `legacy/axios` clientini ishlatardi (`OpenAPI` config obyekti, `ApiError`, `CancelablePromise`), 0.87.0 da esa legacy clientlar butunlay olib tashlangan. **2026-08-18 da migratsiya bajarildi** — plugin `@hey-api/client-axios` (`throwOnError: true`) ga almashdi, eski `src/client/core/*` (`ApiError`, `CancelablePromise`, `OpenAPI`, `request`) o'chib o'rniga `core/*.gen.ts` + `client/` katalogi generatsiya qilinadigan bo'ldi, chaqiruv shakli `{ path, query, body }` + `.data` ga o'tdi va `ApiError` o'rnini `AxiosError` egalladi. Servis/metod nomlari (`OrdersService.readOrders` kabi) o'zgarmadi — konfigda `asClass`/`classNameBuilder` saqlangan, `operationId` esa `5eec038` da olib tashlandi, chunki 0.99 da u sukutda yoqiq (generatsiya chiqishi bayt-ma-bayt bir xil qoldi). To'liq tafsilot: `05-frontend-app.md` → «6. API Client (`frontend/src/client/`)».

⚠️ **Security eslatma:** hozir `npm audit` — **0 vulnerability** (ilgari bu yerda 3 ta topilma yozilgan edi: `handlebars` critical, `@hey-api/openapi-ts` high, `postcss` high). Eski uchtasidan hech biri qolmadi: `handlebars` 0.99 zanjirida umuman yo'q (`npm ls handlebars` → bo'sh), `@hey-api/openapi-ts` ning o'ziga qarshi advisory 0.99 bilan yopildi, `postcss` esa `vite` 8.2.1 orqali 8.5.26 ga ko'tarildi. Migratsiya paytida esa `@hey-api/json-schema-ref-parser` → `js-yaml` 4.2.0 zanjiri yangi advisory olib keldi (audit 5 topilma ko'rsatdi: 1 critical + 4 high); u `package.json` dagi `"overrides": { "js-yaml": "^4.3.1" }` bilan yopildi va audit 0 ga tushdi (`npm ls js-yaml` → `js-yaml@4.3.1 overridden`). Override kerak, chunki zaif versiya to'g'ridan-to'g'ri bog'liqligimiz emas — u transitiv va faqat dev-time codegen ichida ishlatiladi.

## Yangilashni takrorlash (keyingi safar)

```bash
# Backend
cd backend && uv lock --upgrade && uv sync --all-groups
uv run ruff check . && uv run mypy app

# Frontend
cd frontend && npm update && npm outdated   # outdated bo'sh bo'lsa — hammasi latest
npm audit                                   # 0 vulnerability bo'lishi kerak
npm run build

# Client regeneratsiya (backend schema o'zgarganda)
bash scripts/generate-client.sh
```

`ruff` lock'da ko'tarilsa (`uv lock --upgrade` uni o'zi ko'taradi) `.pre-commit-config.yaml` dagi `ruff-pre-commit` `rev` ni ham qo'lda o'sha teg'ga tenglashtirish kerak — hozir `v0.16.3`, ya'ni hook va `uv.lock` bir xil ruff'ni ishlatadi (batafsil: `07-infra-devops.md`).

`npm outdated` major bump ko'rsatsa — `package.json` dagi caret versiyani qo'lda ko'tarish kerak (caret major'dan o'tkazmaydi). Yuqoridagi 2 ceiling'ni tekshirishni unutmang. Biome major/minor'dan keyin `npx biome migrate --write` — u `biome.json` dagi `$schema` ni va eskirgan kalitlarni yangilaydi.

Bridge-agent bu siklga kirmaydi: uning `websockets` (>=14) / `pywin32` / `pillow` / `pynput` versiyalari exe yig'ilgan paytdagi dasturchi muhitidan keladi, lock fayli yo'q. Yangilash = paketlarni yangilab exe'ni qayta yig'ish va yangi `mebelix-agent.exe` ni printerli kompyuterlarga qo'lda tarqatish (flashka/lokal tarmoq — panel ichidagi yuklab olish olib tashlangan). Har agent kod o'zgarishida `agent.py` dagi `AGENT_VERSION` qo'lda +1 qilinadi (hozir 1.2.1) — u WS headerida (`X-Agent-Version`) serverga boradi va admin paneldagi Printerlar sahifasida qaysi exe ishlayotgani ko'rinadi.
