# 08 — Paketlar va versiyalar

Holat: **2026-08-06** tekshiruvi (oxirgi to'liq upgrade: 2026-07-09). Barcha paketlar 2026-07-09 dagi eng so'ngi stable versiyaga ko'tarilgan (quyidagi 3 ta ataylab qilingan istisno bilan). 2026-08-05 dagi katta refaktor manifestlarning faqat **metadatasiga** tegdi — bog'liqliklar ro'yxati 2026-07-27 dan beri o'zgarmagan.

**Manifest tarixi (upgrade'dan keyin):** manifestlar olti marta o'zgardi — avval ikkita qo'shish (2026-07-10), keyin uchta kamaytirish (2026-07-27), oxirida bitta metadata tahriri (2026-08-05):

- `26e00af` — MES core bilan `openpyxl` (runtime, Excel eksport) va dev'ga `types-openpyxl` + `websockets` qo'shildi;
- `b5ee41d` — yorliq chop etish uchun `tzdata`/`pillow`/`qrcode` (pastdagi jadval), frontend'ga `@radix-ui/react-popover` va `react-day-picker`;
- `4306a42` — `websockets` dev group'dan asosiy `dependencies` ga ko'chirildi (pastda alohida bo'lim);
- `87d23ab` — `httpx` va `uuid6` runtime'dan, `types-redis` dev'dan chiqarildi (kod ularni hech qayerda import qilmasdi); `uv.lock` 71 → **63** paketga tushdi (`certifi`, `httpcore`, `types-cffi`, `types-pyopenssl`, `types-setuptools` transitiv bo'lib birga ketdi);
- `a916088` — `@tanstack/react-table` o'chirildi (`Common/DataTable.tsx` va `Admin/columns.tsx` bilan birga; `admin.tsx` endi oddiy `<Table>` chizadi), `backend/pyproject.toml` dagi `license` kaliti ham olib tashlandi;
- `a4f7f21` — `frontend/package.json` da `name` `frontend` → `mebelix-mes-frontend` bo'ldi va yangi `description` kaliti qo'shildi; bog'liqliklarning o'ziga tegilmadi (yagona metadata o'zgarishi).

Yangi bog'liqliklar faqat manifestdan **tashqarida** paydo bo'ldi va ikkalasi ham quyida alohida bo'limlarda yozilgan:

- bridge-agent'ning Windows GDI chop etish yo'li — `pywin32` + `pillow` (repo'da manifest fayli yo'q);
- `render_label_png()` uchun tizim TrueType shriftlari (Docker image'ga `fonts-liberation` apt paketi bilan qo'shilgan).

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
| **redis** | **5.3.1** | ⚠️ 8.1.0 mavjud, lekin `arq` bloklaydi (pastga qarang) |
| arq | 0.28.0 | latest |
| pyjwt | 2.13.0 | latest |
| bcrypt | 5.0.0 | latest |
| mypy (dev) | 2.2.0 | latest |
| ruff (dev) | 0.15.20 | latest |
| pre-commit (dev) | 4.6.0 | latest |

Tekshiruv: `uv run ruff check .` ✅ · `uv run mypy app` ✅ (104 fayl) · `import app.main` ✅

Jadvalda ko'rsatilmagan, lekin manifestda e'lon qilingan runtime paketlar (lock versiyalari bilan): `openpyxl` 3.1.5 — Excel eksport (`app/services/excel.py`; dev'da `types-openpyxl`), `pydantic-settings` 2.14.2 — `app/core/config.py` dagi `Settings`, `python-multipart` 0.0.32 — fayl yuklash (FastAPI `UploadFile`/`Form`, `orders.py`), `prometheus-fastapi-instrumentator` 8.0.2 — `/metrics` (`app/core/setup.py`), `uvloop` 0.22.1 — faqat `sys_platform != 'win32'`, `greenlet` 3.5.3 — SQLAlchemy async uchun.

**2026-07-10 (b5ee41d) da qo'shilganlar** — yorliq chop etish (label-printing) feature uchun yangi runtime dependency'lar:

| Paket | Constraint | Lock | Izoh |
| --- | --- | --- | --- |
| tzdata | >=2026.2 | 2026.2 | Windows'da timezone datasi |
| pillow | >=12.3.0 | 12.3.0 | Yorliqni PNG qilib render qilish |
| qrcode | >=8.2 | 8.2 | Yorliqdagi QR kod generatsiyasi |

Bu uchtasining **haqiqiy ishlatilishi** (99cebc3 dagi `render_label_png()` qayta yozilishidan keyin) — hammasi `backend/app/services/labels.py` da, importlar funksiya ichida (modul importi og'irlashmasin):

- **pillow** — `Image`, `ImageDraw`, `ImageFont`, `render_label_png()` ichida. 80×60 mm, 203 dpi → 640×480 px; `draw.fontmode = "1"` bilan antialiasing o'chirilgan (termoprinter 1-bit, aks holda drayver dither qiladi). Shu funksiya `backend/app/assets/label-logo.png` va `label-icon-drill.png` fayllarini ham ochadi.
- **qrcode** — `qrcode.make(d.qr_text, box_size=..., border=0)` shu funksiya ichida. Pillow o'rnatilgani uchun PIL image qaytaradi va to'g'ridan-to'g'ri yorliq rasmiga joylashtiriladi.
- **tzdata** — `ZoneInfo("Asia/Tashkent")` uchun IANA ma'lumoti (Windows'da tizimda yo'q). 2026-08-05 dan konstanta bitta joyda — `app.core.config.TASHKENT_TZ`; `labels.py` uni `printed_at` uchun import qiladi (`load_label_data()`), `app/api/routes/audit.py` va `app/api/routes/reports.py` ham shu konstantani ishlatadi.

`labels.py` ning butun tashqi yuzasi shu uchtaga tayanadi: `LabelData`, `load_label_data()`, `_n()`, `_bw()`, `render_label_png()` — boshqa paket talab qilmaydi. `print_label` taski (`backend/app/tasks/__init__.py`) PNG'ni base64 qilib Redis navbatiga (`mes:print:queue`) qo'yadi, job JSON'i `{"type", "instance_id", "png"}` — printer dialekti generatsiya qilinmaydi, shuning uchun task tomonda ham qo'shimcha bog'liqlik yo'q.

`websockets>=16.0` asosiy `dependencies` da, garchi `backend/app` ichida hech qayerda `import` qilinmasa ham (repo bo'yicha yagona `import websockets` — `bridge-agent/agent.py` da). Sabab: `uvicorn` 0.51.0 `[standard]` extra'siz o'rnatilgan (lock'da bog'liqliklari faqat `click` + `h11`), `wsproto` esa umuman yo'q — ya'ni `/ws/events` va `/ws/bridge` uchun WebSocket transporti aynan shu paket. Dev group'da tursa `uv sync --no-dev` bilan yig'ilgan image'da TABLO ham, yorliq chop etish ham jimgina o'lardi; shuning uchun `pyproject.toml` da qator ustiga izoh yozib qo'yilgan.

### Frontend (`frontend/package.json` + `package-lock.json`)

`npm update` bilan barcha paketlar caret range ichida latestga ko'tarildi (jumladan: vite 8.1.4, @biomejs/biome 2.5.3, lucide-react 1.24.0, radix-ui paketlari). Runtime dependencies allaqachon latest edi.

Asosiy paketlar (yangilangandan keyin):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| react / react-dom | 19.2.7 | latest |
| @tanstack/react-query | 5.101.2 | latest |
| @tanstack/react-router | 1.170.17 | latest |
| axios | 1.18.1 | latest |
| tailwindcss / @tailwindcss/vite | 4.3.2 | latest |
| zod | 4.4.3 | latest |
| react-hook-form | 7.81.0 | latest |
| vite (dev) | 8.1.4 | latest |
| @biomejs/biome (dev) | 2.5.3 | latest |
| **typescript (dev)** | **6.0.3** | ⚠️ 7.0.2 mavjud, lekin openapi-ts bloklaydi (pastga qarang) |
| **@hey-api/openapi-ts (dev)** | **0.86.12** | ⚠️ 0.99.0 mavjud, lekin legacy client kerak (pastga qarang) |

Tekshiruv: `npm run build` (tsc + vite) ✅ · `bash scripts/generate-client.sh` ✅ (client qayta generate qilindi, build o'tdi)

**2026-08-05 tekshiruvi:** `frontend/src` dagi barcha TS/TSX tashqi importlar (29 ta modul) `package.json` da e'lon qilingan — e'lon qilinmagan (phantom) bog'liqlik yo'q va aksincha, ishlatilmay qolgan paket ham yo'q. Ikki paket TS importisiz, faqat CSS orqali keladi: `@fontsource-variable/archivo` 5.2.8 va `tw-animate-css` 1.4.0 (dev) — `src/index.css` boshidagi `@import` qatorlari; `tailwindcss`/`@tailwindcss/vite` ham CSS/vite-config tomonda, shuning uchun 29 talik hisobga kirmaydi. Jadvalda ko'rsatilmagan, lekin ishlatiladigan runtime paketlar: `qrcode.react` 4.2.0 (`components/Terminal/CutmapView.tsx`, `routes/_layout/employees.tsx`), `react-day-picker` 10.0.1 (`ui/date-picker` — anketa, hisobot va log sanalarida), `sonner` 2.0.7 (`ui/sonner`, `Toaster` `routes/__root.tsx` da mount qilinadi; `useCustomToast` 2026-08-05 da o'chirilgan — komponentlar to'g'ridan-to'g'ri `toast.success/error` chaqiradi). `ui/textarea.tsx` — xom `<textarea>` ustidagi wrapper, Radix paketi talab qilmaydi; `Terminal/SheetSvg.tsx` faqat React va inline SVG ishlatadi (chizma kutubxonasi yo'q).

## Bridge-agent bog'liqliklari (manifestsiz)

`bridge-agent/` da `pyproject.toml` ham, `requirements.txt` ham **yo'q**. To'rtta runtime paket agent `mebelix-agent.exe` ichiga PyInstaller bilan yig'iladi (`pyinstaller --onefile --noconsole --name mebelix-agent agent.py`) — sexdagi kompyuterga na Python, na `pip`, na alohida paket o'rnatiladi. `pyinstaller`ning o'zi faqat **build-time** asbob (dasturchi mashinasida), runtime bog'liqlik emas va hech qaysi manifestda yozilmagan.

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

`render_label_png()` PyPI paketlaridan tashqari **OS shriftlariga** bog'liq. `labels.py` dagi qidiruv ro'yxatlari:

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

### 2. @hey-api/openapi-ts 0.86.12 (latest: 0.99.0)

`openapi-ts.config.ts` `legacy/axios` client ishlatadi (`OpenAPI` config obyekti, `ApiError`, `CancelablePromise`, `*Service` klasslari — butun frontend shu API'ga qurilgan). **0.87.0 da legacy clientlar butunlay olib tashlangan** — 0.99.0 bilan `legacy/axios` jimgina 0 fayl generate qiladi (0.99 sinab ko'rildi: `src/client` bo'shab qoldi, qaytarildi). 0.86.12 — legacy clientni qo'llaydigan eng so'ngi versiya.

⚠️ **Security eslatma:** `npm audit` jami 3 ta vulnerability ko'rsatadi (2 high + 1 critical), shundan ikkitasi shu ceiling'dan keladi: transitive `handlebars` (critical) va `@hey-api/openapi-ts` ning **o'ziga** qarshi advisory (high — `buildClientParams` shablonida noma'lum `$<slot>___proto__` kaliti orqali prototip zanjirini almashtirish; npm uni `via` da o'z advisory'si + `handlebars` bilan ko'rsatadi). Ikkalasi ham **faqat dev-time code-generator** ichida — production bundlega kirmaydi, input esa o'zimizning `openapi.json`. Xavf past, lekin quyidagi migratsiya bilan butunlay yo'qoladi. Uchinchi topilma — `postcss` (high, `sourceMappingURL` orqali path traversal) — `vite` zanjiridan keladi va bu ceiling'ga aloqasi yo'q.

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

Bridge-agent bu siklga kirmaydi: uning `websockets` (>=14) / `pywin32` / `pillow` / `pynput` versiyalari exe yig'ilgan paytdagi dasturchi muhitidan keladi, lock fayli yo'q. Yangilash = paketlarni yangilab exe'ni qayta yig'ish va yangi `mebelix-agent.exe` ni printerli kompyuterlarga qo'lda tarqatish (flashka/lokal tarmoq — panel ichidagi yuklab olish olib tashlangan). Har agent kod o'zgarishida `agent.py` dagi `AGENT_VERSION` qo'lda +1 qilinadi (hozir 1.2.1) — u WS headerida (`X-Agent-Version`) serverga boradi va admin paneldagi Printerlar sahifasida qaysi exe ishlayotgani ko'rinadi.
