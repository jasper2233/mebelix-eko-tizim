# 08 — Paketlar va versiyalar

Holat: **2026-09-02** caret/lock ichida yangilash; oxirgi to'liq upgrade **2026-08-18** (oldingisi: 2026-07-09). Barcha paketlar 2026-08-18 dagi eng so'ngi stable versiyaga ko'tarilgan (quyidagi 2 ta ataylab qilingan istisno bilan). Shu upgrade bilan birga ikkita qo'lda manifest o'zgarishi bo'ldi: backend'da `pyjwt[crypto]` → `pyjwt`, frontend'da esa `@hey-api/openapi-ts` `^0.86.12` → `^0.99.0` — bu bilan API klient `legacy/axios` dan zamonaviy `@hey-api/client-axios` pluginiga ko'chdi, ya'ni avvalgi ceiling #2 **yopildi**.

**Manifest tarixi (2026-07-09 upgrade'dan keyin):** manifestlar o'n marta o'zgardi — avval ikkita qo'shish (2026-07-10), keyin uchta kamaytirish (2026-07-27), so'ng ikkita metadata tahriri (2026-08-05 va 2026-08-13) va oxirida 2026-08-18 ning uchta commiti:

- `26e00af` — MES core bilan `openpyxl` (runtime, Excel eksport) va dev'ga `types-openpyxl` + `websockets` qo'shildi;
- `b5ee41d` — yorliq chop etish uchun `tzdata`/`pillow`/`qrcode` (pastdagi jadval), frontend'ga `@radix-ui/react-popover` va `react-day-picker`;
- `4306a42` — `websockets` dev group'dan asosiy `dependencies` ga ko'chirildi (pastda alohida bo'lim);
- `87d23ab` — `httpx` va `uuid6` runtime'dan, `types-redis` dev'dan chiqarildi (kod ularni hech qayerda import qilmasdi); `uv.lock` 71 → **63** paketga tushdi (`certifi`, `httpcore`, `types-cffi`, `types-pyopenssl`, `types-setuptools` transitiv bo'lib birga ketdi);
- `a916088` — `@tanstack/react-table` o'chirildi (`Common/DataTable.tsx` va `Admin/columns.tsx` bilan birga; `admin.tsx` endi oddiy `<Table>` chizadi), `backend/pyproject.toml` dagi `license` kaliti ham olib tashlandi;
- `a4f7f21` — `frontend/package.json` da `name` `frontend` → `mebelix-mes-frontend` bo'ldi va yangi `description` kaliti qo'shildi; bog'liqliklarning o'ziga tegilmadi;
- `159e27b` — `frontend/package.json` dagi `description` matnida "sex" → "tsex" (repo bo'yicha atama almashtirishning bir qismi); bu ham sof metadata, bog'liqliklarga tegmagan;
- **2026-09-02** — caret/constraint ichida latest: backend `uv lock --upgrade` (gunicorn 26.2.0, pydantic 2.13.5, uvicorn 0.52.4, websockets 17.1, click 8.5.0, ruff 0.16.5 → `.pre-commit-config.yaml` rev `v0.16.5`; redis 5.3.1 ceiling'da qoldi; gunicorn 26.2.0 endi `packaging` ga bog'lanmaydi, shuning uchun `packaging` 26.3 lock'dan chiqdi — `uv.lock` 60 → **59** paket), frontend `npm update` (@biomejs/biome 2.5.11 + `biome migrate`, @tanstack/react-query 5.102.8, @tanstack/react-router 1.170.32, axios 1.20.0, zod 4.5.4, lucide-react 1.39.0, react-hook-form 7.87.0, vite 8.2.2; typescript 6.0.3 ceiling'da). Barcha darvozalar yashil.
- **2026-08-18 (shu upgrade, `3b814a8` + `a0c506e`)** — `backend/pyproject.toml` da `pyjwt[crypto]` → `pyjwt` (extra olib tashlandi, pastda alohida bo'lim); `frontend/package.json` da `@hey-api/openapi-ts` `^0.86.12` → `^0.99.0`, `axios` qattiq pin `1.18.1` → `^1.19.0` va yangi `overrides` bloki (`js-yaml` `^4.3.1`);
- `5eec038` — shu seriyaning o'z diffiga qilingan audit `a0c506e` da qo'shilgan `@hey-api/client-axios` `^0.9.1` runtime bog'liqligini olib tashladi: openapi-ts 0.99 klient kodini `src/client/client/` ga inline generatsiya qiladi, ya'ni npm paketining o'zi kerak emas (pastga qarang).

Bulardan tashqari ikkita bog'liqlik manifestdan **tashqarida** yashaydi va ikkalasi ham quyida alohida bo'limlarda yozilgan:

- bridge-agent'ning Windows GDI chop etish yo'li — `pywin32` + `pillow` (repo'da manifest fayli yo'q);
- `labels.py` dagi to'rtala render funksiyasi uchun tizim TrueType shriftlari (Docker image'ga `fonts-liberation` apt paketi bilan qo'shilgan).

## Yangilash tarixi (2026-08-18 upgrade)

### Backend (`backend/pyproject.toml` + `uv.lock`)

`uv lock --upgrade && uv sync --all-groups` bilan yangilandi. `pyproject.toml` dagi `>=` minimal constraintlar o'zgartirilmadi — real versiyalarni `uv.lock` boshqaradi.

Lock'da ko'tarilgan transitivlar: `annotated-doc` 0.0.4→0.0.5, `annotated-types` 0.7.0→0.8.0, `anyio` 4.14.1→4.14.2, `ast-serialize` 0.6.0→0.8.0, `filelock` 3.29.7→3.32.3, `hiredis` 3.4.0→3.4.1, `idna` 3.18→3.19, `librt` 0.13.0→0.15.0, `mako` 1.3.12→1.4.1, `packaging` 26.2→26.3, `platformdirs` 4.10.0→4.11.3, `prometheus-client` 0.25.0→0.26.0, `python-discovery` 1.4.4→1.5.2, `python-dotenv` 1.2.2→1.2.3, `typing-inspection` 0.4.2→0.4.4, `virtualenv` 21.6.0→21.7.4.

Asosiy paketlar (2026-09-02 holati):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| fastapi | 0.141.1 | latest (0.139.0 edi) |
| starlette | 1.6.0 | latest (fastapi bilan keladi; 1.3.1 edi) |
| uvicorn | 0.52.4 | latest (0.51.0 edi) |
| gunicorn | 26.2.0 | latest (o'zgarmadi) |
| pydantic | 2.13.5 | latest (o'zgarmadi) |
| sqlalchemy | 2.0.52 | latest (2.0.51 edi) |
| alembic | 1.19.1 | latest (1.18.5 edi) |
| asyncpg | 0.31.0 | latest (o'zgarmadi) |
| **redis** | **5.3.1** | ⚠️ 8.1.0 mavjud, lekin `arq` bloklaydi (pastga qarang) |
| arq | 0.28.0 | latest (o'zgarmadi) |
| pyjwt | 2.13.0 | latest; `[crypto]` extra'siz (pastga qarang) |
| bcrypt | 5.0.0 | latest (o'zgarmadi) |
| websockets | 17.1 | latest (16.0 edi) |
| mypy (dev) | 2.3.1 | latest (2.2.0 edi) |
| ruff (dev) | 0.16.5 | latest (0.15.20 edi) |
| pre-commit (dev) | 4.6.2 | latest (4.6.0 edi) |

Tekshiruv: `uv run ruff check .` ✅ · `uv run mypy app` ✅ (139 fayl) · `import app.main` ✅

**`pyjwt[crypto]` → `pyjwt` (extra olib tashlandi):** `app/core/config.py` dagi `ALGORITHM` — `HS256`, ya'ni simmetrik HMAC, va `app/core/security.py` tokenni faqat shu bilan imzolaydi/tekshiradi (`jwt.encode(..., algorithm=ALGORITHM)` / `jwt.decode(..., algorithms=[ALGORITHM])`). `cryptography` faqat RS\*/ES\* kabi asimmetrik algoritmlar uchun kerak bo'lardi. Extra olingach lock'dan uchta paket birgalikda chiqib ketdi — `cryptography` 49.0.0, `cffi` 2.1.0, `pycparser` 3.0 — va `uv.lock` 63 → **60** paketga tushdi. `pyproject.toml` da qator ustiga sabab izoh qilib yozib qo'yilgan.

Jadvalda ko'rsatilmagan, lekin manifestda e'lon qilingan runtime paketlar (lock versiyalari bilan): `openpyxl` 3.1.5 — Excel eksport (`app/services/excel.py`; dev'da `types-openpyxl` 3.1.5.20260827), `pydantic-settings` 2.15.0 — `app/core/config.py` dagi `Settings`, `python-multipart` 0.0.32 — fayl yuklash (FastAPI `UploadFile`/`Form`, `orders/files.py` va `orders/survey.py`), `prometheus-fastapi-instrumentator` 8.1.0 — `/metrics` (`app/core/setup.py`), `uvloop` 0.22.1 — faqat `sys_platform != 'win32'`, `greenlet` 3.5.5 — SQLAlchemy async uchun.

**2026-07-10 (b5ee41d) da qo'shilganlar** — yorliq chop etish (label-printing) feature uchun yangi runtime dependency'lar:

| Paket | Constraint | Lock | Izoh |
| --- | --- | --- | --- |
| tzdata | >=2026.2 | 2026.3 | Windows'da timezone datasi |
| pillow | >=12.3.0 | 12.3.0 | Yorliqni PNG qilib render qilish |
| qrcode | >=8.2 | 8.2 | Yorliqdagi QR kod generatsiyasi |

Bu uchtasining **haqiqiy ishlatilishi** (99cebc3 dagi `render_label_png()` qayta yozilishidan keyin) — hammasi `backend/app/services/labels.py` da, importlar funksiya ichida (modul importi og'irlashmasin):

- **pillow** — `Image`, `ImageDraw`, `ImageFont`, render funksiyalari va ularning yordamchilari (`_canvas()`, `_font()`, `_logo()`) ichida. Detal yorlig'i 80×60 mm, 203 dpi → 640×480 px; to'rtala chek `_canvas()` dan boshlanadi va u `draw.fontmode = "1"` bilan antialiasing'ni o'chiradi (termoprinter 1-bit, aks holda drayver dither qiladi). `render_label_png()`, `render_pachka_label_png()` va `render_waste_label_png()` logoni `_paste_logo()` bilan qo'yadi — `backend/app/assets/logo-black.png` ni `_logo()` ochadi (beyjik logosiz).
- **qrcode** — `qrcode.make(..., box_size=..., border=0)` xuddi shu to'rtala funksiya ichida: `d.qr_text` (detal), `d.code` (pachka), `d.qr_text` (foydali atxot), `d.badge_id` (beyjik). Pillow o'rnatilgani uchun PIL image qaytaradi va to'g'ridan-to'g'ri yorliq rasmiga joylashtiriladi.
- **tzdata** — `ZoneInfo("Asia/Tashkent")` uchun IANA ma'lumoti (Windows'da tizimda yo'q). 2026-08-05 dan konstanta bitta joyda — `app.core.config.TASHKENT_TZ`; `labels.py` uni `printed_at` uchun import qiladi (`load_label_data()`), `app/tasks/__init__.py` (`print_pachka_label` va `print_waste_label` dagi `printed_at`), `app/api/routes/audit.py`, `reports.py`, `scans.py`, `tablo.py`, `orders/_common.py` va `app/services/scanning.py` ham shu konstantani ishlatadi.

`labels.py` ning butun tashqi yuzasi shu uchtaga tayanadi — boshqa paket talab qilmaydi: `LabelData` + `load_label_data()` + `render_label_png()` (detal yorlig'i), `PachkaLabelData` + `render_pachka_label_png()` (qadoq cheki), `WasteLabelData` + `render_waste_label_png()` (foydali-atxot cheki) va `BadgeLabelData` + `render_badge_png()` (hodim beyjigi). Modul darajasida to'qqizta xususiy yordamchi bor: `_n()` — o'lchov sonini formatlaydi (`render_label_png()` va `render_waste_label_png()` chaqiradi); `_bw()` — umumiy 1-bit chegara filtri (`_BW_THRESHOLD = 160`), to'rtala render funksiyasi uni yakuniy `_to_1bit_png()` orqali ishlatadi (`_logo()` va detal yorlig'idagi sverlo ikonkasi — to'g'ridan-to'g'ri); `_canvas()` — bo'sh 80×60 mm blank; `_font()` — shrift qidiruvi (pastga qarang); `_logo()` (`lru_cache`) + `_paste_logo()` — logo; `_teksturasiz()` — detal yorlig'ida boshqa element bilan ustma-ust tushgan tekstura chizig'ini tashlaydi; `_instagram_glyph()` — qadoq chekidagi Instagram belgisi (PIL primitivlari, rasm faylisiz). To'rtala render funksiyasini `backend/app/tasks/__init__.py` dagi tasklar chaqiradi (`all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`): ular PNG'ni base64 qilib agentning Redis navbatiga (`print_queue_key(agent_id)` → `mes:print:queue:{agent_id}`; `agent_id` majburiy — manzilsiz umumiy `mes:print:queue` ni hech kim o'qimaydi) qo'yadi, job JSON'i `{"type", "job_id", "instance_id", "png"[, "queued_at"]}` (`queued_at` — arq `enqueue_time` i, «Tizim holati» chek kechikishini o'lchash uchun) — printer dialekti generatsiya qilinmaydi, shuning uchun task tomonda ham qo'shimcha bog'liqlik yo'q.

`websockets>=16.0` asosiy `dependencies` da, garchi `backend/app` ichida hech qayerda `import` qilinmasa ham (repo bo'yicha yagona `import websockets` — `bridge-agent/agent.py` da). Sabab: `uvicorn` 0.52.4 `[standard]` extra'siz o'rnatilgan (lock'da bog'liqliklari faqat `click` + `h11`), `wsproto` esa umuman yo'q — ya'ni `/ws/events` va `/ws/bridge` uchun WebSocket transporti aynan shu paket. Ilgari u dev group'da turgan edi va prod image'ga faqat tasodifan tushardi: `backend/Dockerfile` dagi `uv sync --frozen --no-install-project` o'shanda `--no-dev` siz edi. Image'ni tozalash uchun bu bayroq qo'shilsa TABLO ham, chek chiqarish ham jimgina o'lardi (`uvicorn` `ws="auto"` ni `"none"` ga tushirib handshake'ni rad etadi); shuning uchun `4306a42` uni asosiy `dependencies` ga ko'chirdi va `pyproject.toml` da qator ustiga sabab izoh qilib yozib qo'yilgan. 2026-09-02 dan (`14f60ce`) `backend/Dockerfile:16` aynan `uv sync --frozen --no-install-project --no-dev` ni chaqiradi — dev asboblari (mypy/ruff/pre-commit) prod image'ga tushmaydi, websockets esa asosiy `dependencies` da bo'lgani uchun qoladi.

### Frontend (`frontend/package.json` + `package-lock.json`)

`npm update` bilan barcha paketlar caret range ichida latestga ko'tarildi (jumladan: vite 8.2.1, @biomejs/biome 2.5.9, lucide-react 1.31.0, radix-ui/tanstack paketlari). Ikkita qo'lda o'zgarish: `axios` qattiq pin (`1.18.1`) edi — `^1.19.0` ga o'tkazildi, `@hey-api/openapi-ts` esa `^0.86.12` → `^0.99.0` (caret major'dan o'tkazmaydi). Biome 2.5.9 uchun `biome migrate` ishlatildi — `frontend/biome.json` dagi `$schema` 2.5.3 → 2.5.9 ga ko'chdi, qoidalarning o'ziga tegilmadi.

Asosiy paketlar (2026-09-02 holati):

| Paket | Versiya | Izoh |
| --- | --- | --- |
| react / react-dom | 19.2.8 | latest |
| @tanstack/react-query | 5.102.8 | latest |
| @tanstack/react-router | 1.170.32 | latest |
| axios | 1.20.0 | latest (endi caret: `^1.19.0`) |
| tailwindcss / @tailwindcss/vite | 4.3.3 | latest |
| zod | 4.5.4 | latest |
| react-hook-form | 7.87.0 | latest |
| vite (dev) | 8.2.2 | latest |
| @biomejs/biome (dev) | 2.5.11 | latest |
| **typescript (dev)** | **6.0.3** | ⚠️ 7.0.2 mavjud, lekin openapi-ts bloklaydi (pastga qarang) |
| @hey-api/openapi-ts (dev) | 0.99.0 | latest — 0.86.12 (`legacy/axios`) dan migratsiya qilindi |

`@hey-api/client-axios` jadvalda yo'q va `package.json` da ham yo'q: bu npm paket emas, `openapi-ts.config.ts` dagi plugin **nomi** (oddiy string). 0.99 klient runtime'ini `src/client/client/` ga inline generatsiya qiladi, generatsiya qilingan fayllar esa faqat `axios` ni import qiladi (`src/client/client/client.gen.ts`).

Tekshiruv: `npm run build` (tsc + vite) ✅ · `bash scripts/generate-client.sh` ✅ (klient 0.99 bilan noldan qayta generate qilindi — `openapi.json` 76 yo'l / 97 operatsiya; fayl git'da tracked emas, skript uni har safar backend'dan eksport qiladi) · `npm audit` ✅ 0 vulnerability

**2026-08-18 tekshiruvi:** `frontend/src` dagi barcha TS/TSX tashqi importlar (29 ta modul) `package.json` da e'lon qilingan — e'lon qilinmagan (phantom) bog'liqlik yo'q. Teskari yo'nalishda ham toza: e'lon qilingan 32 ta runtime bog'liqlikning 29 tasi aynan shu importlar, qolgan uchtasi (`@fontsource-variable/archivo`, `tailwindcss`, `@tailwindcss/vite`) TS importisiz — CSS/vite-config tomonda keladi, ya'ni ishlatilmaydigan (orphan) bog'liqlik yo'q. `src/index.css` boshidagi `@import` qatorlari: `tailwindcss`, `tw-animate-css` 1.4.0 (dev) va `@fontsource-variable/archivo` 5.3.0; `@tailwindcss/vite` esa `vite.config.ts` dagi plagin. Jadvalda ko'rsatilmagan, lekin ishlatiladigan runtime paketlar: `qrcode.react` 4.2.0 (`components/Terminal/PartCard.tsx` va `components/Orders/BazisPanel.tsx`), `three` 0.186.0 + `@types/three` 0.186.0 (2026-09-22, `e0e829a`; ikkalasi ham `dependencies` da — `components/Bazis/scene.ts` va `ilgak.ts`, 3D yig'ish ko'rinishi, batafsil `13-bazis-3d.md`), `react-day-picker` 10.0.1 (`ui/date-picker` — anketa, buyurtma formasi, hisobot va log sanalarida), `sonner` 2.0.8 (`ui/sonner`, `Toaster` `routes/__root.tsx` da mount qilinadi; `useCustomToast` 2026-08-05 da o'chirilgan — komponentlar to'g'ridan-to'g'ri `toast.success/error` chaqiradi). `ui/textarea.tsx` — xom `<textarea>` ustidagi wrapper, Radix paketi talab qilmaydi; `Terminal/SheetSvg.tsx` faqat React va inline SVG ishlatadi (chizma kutubxonasi yo'q).

## Bridge-agent bog'liqliklari (manifestsiz)

`bridge-agent/` da `pyproject.toml` ham, `requirements.txt` ham **yo'q**. Oltita runtime paket agent `mebelix-agent.exe` ichiga PyInstaller bilan yig'iladi (`pyinstaller --onefile --noconsole --icon mebelix.ico --name mebelix-agent agent.py`) — tsexdagi kompyuterga na Python, na `pip`, na alohida paket o'rnatiladi. `pyinstaller`ning o'zi faqat **build-time** asbob, runtime bog'liqlik emas. Rasmiy manifest o'rnida repoga commit qilingan ikkita bir xil `pip install` qatori turadi: `bridge-agent/README.md` («Dasturchi uchun: exe yig'ish») va `.github/workflows/ci.yml` dagi `agent` job — exe endi dasturchi mashinasida emas, CI'da (`windows-latest`, Python 3.12) har `main` push'ida quriladi. Runtime paketlar versiyasi pinlanmagan: har build eng so'nggi `pillow`/`pywin32`/`pynput`/`pystray`/`pyserial` ni tortadi. Faqat build-time `pyinstaller` `==6.22.2` ga qotirilgan (sababi `ci.yml` izohida: bootloader o'zgarishi bat orqali qayta ishga tushgan agentni yiqitgan, ko'tarish onefile restart oqimini tsexda qayta sinashni talab qiladi).

| Paket | Nima uchun |
| --- | --- |
| websockets | `uplink()` — serverga outbound WS (`/api/v1/ws/bridge`), modul darajasidagi yagona tashqi import. **>=14 talab** — v13/14 shim 2026-08-05 da olib tashlandi, README'dagi build qatori `pip install "websockets>=14" ...` |
| pywin32 | `win32print` — `_detect_printer()` da printerni topish va `_print_png_gdi()` da DEVMODE; `win32gui`, `win32ui`, `win32con` — GDI konteksti; `win32api`+`win32event`+`winerror` — `_single_instance()` mutexi |
| pillow | `PIL.Image`, `PIL.ImageWin` — serverdan kelgan base64 PNG'ni GDI kontekstiga chizish |
| pynput | `start_scan_forward()` — stanok skanerining klaviatura kirishini passiv kuzatib `/bridge-agents/scan` ga forvard qilish. Ixtiyoriy: o'rnatilmagan bo'lsa faqat skan-forvard jim o'chadi, chop etish ishlayveradi |
| pystray | `start_tray()` — tray belgisi (v1.4.0+): yashil/qizil holat ikonkasi va uchta elementli menyu — holat satri (o'chirilgan), «Log papkasini ochish», «Qayta ulash (yangi kod)»; «Chiqish» ATAYIN yo'q. Ikonkani PIL chizadi. Ixtiyoriy: `ImportError` da agent jim, tray'siz ishlayveradi (eski build) |
| pyserial | `start_andon()` → `_andon_loop()` — stanok Pico'sining (Raspberry Pi VID `0x2E8A`) COM portini o'qish: prisadka/kromka/rover andon hodisalari. Ixtiyoriy: `ImportError` da faqat andon jim o'chadi, chop etish va skan-forvard ishlayveradi |

Birinchi uchtasi majburiy: chiqish yo'li bitta — `_print_png_gdi()` (Windows drayveri, DEVMODE'da qog'oz 80×60 mm ga majburlanadi). `pywin32` va `pillow` importlari funksiya ichida, lekin ularsiz `send_to_printer()` ishlamaydi, ya'ni agent amalda Windows'ga bog'langan.

Pip paketlardan tashqari exe **tkinter/Tcl-Tk** ga ham tayanadi (stdlib, lekin Tcl/Tk runtime'ini PyInstaller exe'ga qo'shadi): pairing oynasi `_pair_dialog()` va `_alert()` messageboxlari shu bilan chiziladi; tkinter bo'lmasa pairing konsolga (`_pair_console()`) tushadi, `_alert()` esa jim log bilan kifoyalanadi. `_notify_connected()` dagi "serverga ulandi" xabari esa `ctypes.windll.user32.MessageBoxTimeoutW` (stdlib `ctypes`) bilan chiqadi.

Printer nomi odatda sozlanmaydi: `_detect_printer()` `win32print.EnumPrinters()` bilan nomi yorliq-printerga o'xshagan lokal printerni qidiradi — `_PRINTER_KEYWORDS` da yettita rusum kaliti (`godex`, `xprinter`, `gprinter`, `tsc`, `zebra`, `argox`, `postek`), chunki tsexda GoDEX ham, Xprinter ham bor. `PRINTER_NAME` env qo'lda override uchun: berilgan bo'lsa `PRINTER_FIXED` yoqiladi va nom har doim ustun turadi; berilmagan bo'lsa `refresh_printer()` nomni qayta aniqlaydi (drayver qaytganda agentni qayta ishga tushirish shart emas — ilgari nom faqat startda bir marta olinardi). Agent env'lari to'liq ro'yxati — `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`, `SCAN_FORWARD` (default yoqiq, `0` o'chiradi); andon (Pico, pyserial) uchun — `ANDON` (default yoqiq, `0` o'chiradi), `ANDON_PORT` (bo'sh = Raspberry Pi VID bo'yicha o'zi topadi), `ANDON_TAKEOVER` (default yoqiq), `ANDON_QUEUE_FILE`, `ANDON_TUR` (faqat boshlang'ich taxmin), `ROVER_AUTO_SHUTDOWN` (default `0`), `ROVER_T_REASON` (default 300 s).

Agent printersiz kompyuterda ham ATAYLAB ishlaydi: printer topilmasa `main()` yiqilmaydi, tray'da alohida «printer yo'q (skan-forvard)» rejimi ko'rinadi — u aynan stanok (Nanxing) kompyuteriga skan-forvard uchun o'rnatiladi. Menejer, texnolog va boshqa post terminallarida hech qanday paket kerak emas — ular brauzerdan tugmani bosadi.

## Tizim darajasidagi bog'liqliklar (paket menejeridan tashqari)

Yorliq render qilish PyPI paketlaridan tashqari **OS shriftlariga** bog'liq — to'rtala funksiya (`render_label_png()`, `render_pachka_label_png()`, `render_waste_label_png()`, `render_badge_png()`) bitta qidiruv ro'yxatiga murojaat qiladi. `labels.py` dagi ro'yxatlar:

- `_FONT_REGULAR`: `C:/Windows/Fonts/arial.ttf` → `/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` → `/usr/share/fonts/dejavu/DejaVuSans.ttf`
- `_FONT_BOLD`: `C:/Windows/Fonts/arialbd.ttf` → `/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf` → `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` → `/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf`

Liberation Sans birinchi Linux nomzodi: Arial bilan metrik mos (harf kengliklari bir xil), shuning uchun Windowsda sozlangan maket serverda ham aynan shunday joylashadi. DejaVu kengroq — maketni siljitadi, faqat zaxira bo'lib qoladi.

Hech biri topilmasa `ImageFont.load_default()` ga tushadi (kichik bitmap shrift — `size_mm` e'tiborga olinmaydi, yorliq matni o'lchamsiz chiqadi).

`backend/Dockerfile` final stage'da `curl` bilan birga `fonts-liberation` ham o'rnatiladi (`apt-get install -y --no-install-recommends curl fonts-liberation`) — konteynerda `LiberationSans-Regular.ttf` topiladi va yorliq `load_default()` ga tushmaydi. `fonts-dejavu-core` o'rnatilmagan: DejaVu yo'llari faqat boshqa muhitlar uchun zaxira.

Yorliq rasm assetlari — `backend/app/assets/logo-black.png` va `label-icon-drill.png` (`design/` dagi masterlarning nusxasi) — image'ga `COPY backend /app/backend` orqali, wheel'ga esa `[tool.hatch.build.targets.wheel] packages = ["app"]` orqali tushadi.

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

`ruff` lock'da ko'tarilsa (`uv lock --upgrade` uni o'zi ko'taradi) `.pre-commit-config.yaml` dagi `ruff-pre-commit` `rev` ni ham qo'lda o'sha teg'ga tenglashtirish kerak — hozir `v0.16.5`, ya'ni hook va `uv.lock` bir xil ruff'ni ishlatadi (batafsil: `07-infra-devops.md`).

`npm outdated` major bump ko'rsatsa — `package.json` dagi caret versiyani qo'lda ko'tarish kerak (caret major'dan o'tkazmaydi). Yuqoridagi 2 ceiling'ni tekshirishni unutmang. Biome HAR QANDAY versiya ko'tarilishidan keyin (patch ham) `npx biome migrate --write` — u `biome.json` dagi `$schema` ni va eskirgan kalitlarni yangilaydi. Sabab: `$schema` aniq versiyaga qotirilgan (hozir `2.5.11`), `package.json` esa `^2.5.2` bergani uchun `npm update` patch/minor'ni jimgina ko'taradi va ikkalasi bir-biriga mos kelmay qoladi. Tekshirish: `npx biome ci .` chiqishida «The configuration schema version does not match the CLI version» bo'lmasligi kerak (`$schema` ni qo'lda ko'tarish ham yetadi).

Bridge-agent bu siklga kirmaydi: uning `websockets` (>=14) / `pywin32` / `pillow` / `pynput` / `pystray` / `pyserial` versiyalari exe yig'ilgan paytdagi CI windows-runner muhitidan keladi (`.github/workflows/ci.yml` dagi `agent` job), lock fayli yo'q. Yangilash = `pip install` qatoridagi paketlarni yangilab exe'ni qayta yig'ish; tarqatish esa avtomatik — agent `GET /api/v1/bridge-agents/latest` dan yangi versiyani ko'rib, `/bridge-agents/download` dan exe'ni tortadi va sha256 mos kelsa o'zini almashtiradi (v1.4.0+; batafsil: `07-infra-devops.md`). Flashka faqat birinchi o'rnatishda. Har agent kod o'zgarishida `agent.py` dagi `AGENT_VERSION` qo'lda +1 qilinadi (hozir 1.12.0) — u WS headerida (`X-Agent-Version`) serverga boradi, avto-yangilanish taqqoslashi ham, admin paneldagi «MES agentlar» sahifasidagi «qaysi exe ishlayapti» belgisi ham shunga tayanadi.
