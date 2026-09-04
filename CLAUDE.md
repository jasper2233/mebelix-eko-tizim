<!--
last_updated: 2026-09-04
scope: butun repo
owner: apayziev
-->

# MebeliX MES

Mebel tsexi uchun MES. FastAPI + PostgreSQL + Redis backend, React SPA frontend,
Windows'da ishlaydigan `bridge-agent` (yorliq chop etish + skan forvard).

## Commands

Hammasi repo ildizidan. `make help` — to'liq ro'yxat.

```bash
# Tekshiruv (CI aynan shularni chaqiradi)
cd backend && uv run ruff check --no-fix app && uv run ruff format --check app
cd backend && uv run mypy app
cd frontend && npx biome ci .
cd frontend && npm run build              # tsc + vite

make lint                                 # ruff + mypy birga
make check-migrations                     # alembic upgrade head && alembic check (DB kerak)


# API klient (backend sxemasi o'zgarganda MAJBURIY)
make frontend-gen                         # scripts/generate-client.sh
```

## Qat'iy qoidalar

- **Test yo'q — ataylab** (`683e47e` hammasini olib tashlagan). Test qo'shishni
  o'z tashabbusi bilan taklif qilma. Tekshiruv = yuqoridagi linter/tayp/CI
  buyruqlari. Xulq haqidagi da'voni tasdiqlash kerak bo'lsa — bir martalik
  skript yozib ISHGA TUSHIR, mulohaza bilan cheklanma.
- **Generatsiya qilingan, qo'lda tahrirlanmaydi:** `frontend/src/client/**`,
  `frontend/src/routeTree.gen.ts`. Birinchisi `make frontend-gen` bilan,
  ikkinchisi TanStack Router bilan qayta yaraladi.
- **Til:** foydalanuvchi ko'radigan hamma matn (UI, API xato xabarlari) —
  **o'zbekcha**, istisnosiz. Kod identifikatorlari va commit'lar — inglizcha.
  Izohlar asosan o'zbekcha.
- **`docs/` — birlamchi manba va QO'LDA yuritiladi.** Kod o'zgarsa tegishli
  hujjatni ham yangila (xarita: `docs/README.md`). Hujjat kod bilan zid kelsa —
  qaysi biri to'g'riligini tekshirib, ikkalasini moslashtir.
- **Migratsiya:** modelga ustun qo'shsang migratsiya ham yoz — `alembic check`
  CI'da qizil beradi. Prodga qo'llangan migratsiya fayli HECH QACHON
  o'chirilmaydi/tahrirlanmaydi; o'rniga yangi migratsiya yoziladi.

## Ish qanday taqsimlanadi (model marshruti)

Bu bo'lim ASSISTENT uchun. Subagent chaqirishdan oldin ishni tur bo'yicha ajrat.
Birinchi mos qatorda to'xta — pastdan boshlama.

| Ish turi | Kim bajaradi |
| --- | --- |
| **Javobi determinlashgan** | **Hech qanday model emas — skript yoz** (endpoint ro'yxati, import grafi, migratsiya zanjiri, versiya solishtirish) |
| Mexanik sanash / grep | `census` (haiku) |
| Fayl o'qib fakt chiqarish | `reader` (sonnet) |
| Semantik hukm, ziddiyat, haqiqiy bug | `judge` (fable→opus) |

Kichik ish bo'lsa — o'zing bajar. Bitta fayllik savolni subagentga uzatish
javob berishdan qimmatroq turadi.

**Modelning da'vosiga ishonma — tekshir.** Agent qaytargan har bir iqtibos manba
faylda so'zma-so'z borligini `grep -F` bilan tasdiqla. Ammo esda tut: iqtibos
haqiqiy bo'lishi — xulosa to'g'ri degani EMAS.

## Bu loyihada tekshiruv qanday ishlaydi

**Test yo'q, ya'ni yagona orakl — sen yozgan bir martalik skript.** Xulq haqidagi
har qanday da'vo ("bu poyga", "bu autoflush tufayli ishlamaydi") bajarilib
tasdiqlanishi shart; mulohaza yetarli emas.

**Mavjud orakllar** — da'vodan oldin shularni ishlat:

```bash
cd backend && uv run ruff check --no-fix app   # --no-fix SHART (pastga qarang)
cd backend && uv run mypy app
cd frontend && npx biome ci . && npm run build
make check-migrations                          # alembic upgrade head && alembic check
```

⚠️ `pyproject.toml` da `fix = true` turibdi: `--no-fix` siz `ruff check` xatoni
JIMGINA tuzatib exit 0 qaytaradi. 2026-08-26 gacha CI lint darvozasi shu sabab
umuman ishlamagan.

2026-08-26 auditining o'lchangan xulosasi (`docs/audit-2026-09-02.md` → «Metod»):
eng ishonchli topilmalar bajarilgan skriptlardan chiqdi, 16.7M tokenlik agent
oqimidan emas.

## Bilib turish kerak

- Bazada **6 ta yetim jadval** va **7 ta yetim ustun** bor (OEE va materiallar
  ombori modullari olib tashlangan, migratsiyalari prodda qolgan). Ular
  `migrations/env.py` dagi `LEGACY_TABLES`/`LEGACY_COLUMNS` da sanab o'tilgan va
  `alembic check` ularni e'tiborsiz qoldiradi. Batafsil: `docs/04` §4.4.
- Detal ID = chek = QR = SCX fayl nomi = Panel ID — **bitta satr**, 2026-09-03 dan
  `{buyurtma}_` prefiksli (`giblab/models.py: instance_qr`). Qoidasi `docs/11` da.
- Enum matnlari backend (`models/enums.py`) va frontend (`lib/mes.ts`) da
  QO'LDA oynalangan; zod sxemasi (`lib/validation.ts`) ham backend
  `schemas/users.py` cheklovlariga qo'lda moslangan. Birini o'zgartirsang —
  ikkinchisini ham.
- Prod deploy: `main`ga push -> CI image quradi -> `scripts/deploy.sh`
  serverda faqat pull+switch, smoke yiqilsa avto-rollback.
