# Frontend App — Routes, Hooks, Queries, Client va Konfiguratsiya

Bu hujjat MebeliX MES frontend ilovasining yadro qismini tavsiflaydi: build/tooling konfiguratsiyasi, ilova entry point'i, routing tuzilmasi, autentifikatsiya oqimi (auth flow), custom hook'lar, TanStack Query so'rovlari va OpenAPI'dan generatsiya qilinadigan API client.

**Texnologiyalar stack'i:**

| Qatlam | Texnologiya |
|---|---|
| Build tool | Vite + `@vitejs/plugin-react-swc` |
| UI framework | React 19 (StrictMode) |
| Routing | TanStack Router (file-based, code-generated) |
| Server state | TanStack Query (`QueryClient`, `queryOptions` factory'lar) |
| HTTP | Axios (cookie-based auth, `withCredentials`) |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`), shadcn/ui (new-york style) |
| Formalar | react-hook-form + zod (`zodResolver`) |
| Lint/format | Biome |
| API client | `@hey-api/openapi-ts` (legacy/axios plugin) |

---

## 1. Konfiguratsiya fayllari

### `frontend/index.html`
Ilovaning yagona HTML entry point'i. `<div id="root">` konteyneri va `./src/main.tsx` modul skriptini yuklaydi. Title — "MebeliX", favicon `/assets/images/favicon.png`.

### `frontend/vite.config.ts`
Vite konfiguratsiyasi. Uchta plugin ulangan:
- `tanstackRouter({ target: "react", autoCodeSplitting: true })` — `src/routes/` papkasidan `src/routeTree.gen.ts` faylini avtomatik generatsiya qiladi va har bir route'ni alohida chunk'ga ajratadi (code splitting);
- `react()` — SWC-asosli React plugin;
- `tailwindcss()` — Tailwind v4 Vite integratsiyasi.

`@` alias'i `./src` ga yo'naltirilgan (`resolve.alias`), bu `tsconfig.json`dagi `paths` bilan mos.

### `frontend/tsconfig.json` va `frontend/tsconfig.node.json`
- `tsconfig.json`: `strict: true`, `noUnusedLocals`, `noUnusedParameters`, `noEmit` (build'da faqat type-check, transpilyatsiya Vite/SWC'da), `moduleResolution: "bundler"`, `jsx: "react-jsx"`, `@/*` path alias. Faqat `src` papkasini qamrab oladi.
- `tsconfig.node.json`: composite project reference — faqat `vite.config.ts` uchun (Node muhitida ishlaydigan config fayl).

### `frontend/openapi-ts.config.ts`
`@hey-api/openapi-ts` konfiguratsiyasi. Input: `./openapi.json` (backend'dan eksport qilinadi), output: `./src/client`. Plugin'lar:
- `legacy/axios` — Axios asosidagi legacy client core (`src/client/core/*`);
- `@hey-api/sdk` — `asClass: true` bilan servis klasslari (`{{name}}Service`, masalan `UsersService`, `LoginService`) va camelCase metodlar generatsiya qilinadi (tree-shaking'ga yo'l qo'ymaydi, lekin qulay namespace beradi).

`@hey-api/schemas` plugini olib tashlangan (config'dagi izohga qarang): u generatsiya qiladigan `schemas.gen.ts`ni hech kim import qilmasdi.

### `frontend/components.json`
shadcn/ui CLI konfiguratsiyasi: `new-york` style, `neutral` base color, CSS variables rejimi, ikonkalar — `lucide`. Alias'lar: `@/components`, `@/components/ui`, `@/lib/utils`, `@/hooks`. Yangi UI komponent qo'shishda shadcn CLI shu faylga tayanadi.

### `frontend/biome.json`
Biome linter/formatter sozlamalari. Generatsiya qilinadigan va tashqi fayllar (`src/components/ui/**`, `src/routeTree.gen.ts`, `src/client/**`, `dist`, `public`, `src/index.css`) tekshiruvdan chiqarilgan. Format: 2 space, double quotes, `semicolons: "asNeeded"`. `noExplicitAny`, `noArrayIndexKey`, `noNonNullAssertion` qoidalari o'chirilgan. `organizeImports` yoqilgan. `npm run lint` — `biome check --write --unsafe ...`.

---

## 2. Entry point va global fayllar

### `frontend/src/main.tsx`
Ilovaning eng muhim fayli — bootstrap + global HTTP xatti-harakati:

1. **API client sozlash**: `OpenAPI.BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"`, `OpenAPI.WITH_CREDENTIALS = true`. Token JS xotirasida saqlanmaydi — autentifikatsiya to'liq HttpOnly cookie'lar orqali (`withCredentials` bilan avtomatik yuboriladi). Axios global timeout: `VITE_API_TIMEOUT_MS` (default 30 000 ms).

2. **Silent refresh interceptor**: Axios response interceptor 401 kelganda (agar so'rov `/login/refresh` yoki `/login/access-token` bo'lmasa va hali retry qilinmagan bo'lsa) `LoginService.refreshAccessToken()` ni chaqiradi — server yangi `access_token` cookie'sini o'rnatadi — so'ng asl so'rov qayta yuboriladi. Bir vaqtda kelgan parallel 401'lar bitta umumiy promise'ni kutadi (`refreshing ??= ...`, `finally`da tozalanadi): refresh muvaffaqiyatli bo'lsa hammasi qayta yuboriladi, yiqilsa hammasi shu xato bilan rad etiladi.

3. **401 fallback**: `QueryCache`/`MutationCache` `onError` handler'i (`handleApiError`) — agar interceptor'dan keyin ham `ApiError` 401 bo'lib chiqsa (masalan, boshqa tab'da logout tufayli `token_version` mos kelmasa), `queryClient.clear()` qilinadi va `window.location.href = "/login"` ga majburiy redirect.

4. **Render**: `createRouter({ routeTree })` (generatsiya qilingan `routeTree.gen.ts`dan), `QueryClientProvider` + `RouterProvider` StrictMode ichida render qilinadi (Toaster bu yerda emas — `__root.tsx`dagi `AppToaster`da). `declare module "@tanstack/react-router"` orqali router type-registratsiyasi qilinadi (type-safe navigatsiya).

### `frontend/src/index.css`
Tailwind v4 uslubidagi global CSS: `@import "tailwindcss"`, `tw-animate-css`, `@fontsource-variable/archivo` (asosiy shrift — Archivo Variable). `@theme inline` bloki shadcn CSS o'zgaruvchilarini Tailwind token'lariga bog'laydi. `:root`da MebeliX brend palitrasi: navy `#2F496E` (primary), gold `#F0A52F` (ring/sidebar-primary), sidebar uchun to'q navy `#243a59` fon, kiosk ekranlar (tablo/terminal) uchun umumiy `--surface` `#f4f6f9` "qog'oz" foni; brend aksent token'lari — `--brand-gold` `#eaa83c`, `--brand-gold-deep` `#8a6420` (oq fondagi mayda yozuv uchun to'q oltin — `#b8862f` WCAG AA dan o'tmasdi), `--brand-navy-deep` `#16233a`. `@layer base`da border/outline default'lari va `button { cursor: pointer }`.

### `frontend/src/utils.ts`
API xatolarini toast'ga aylantirish yordamchilari:
- `extractErrorMessage(err: ApiError)` — `AxiosError` bo'lsa kod bo'yicha o'zbekcha xabar (`ERR_NETWORK` → "Tarmoq xatosi — internet aloqasini tekshiring", `ECONNABORTED` → "So'rov vaqti tugadi — qayta urinib ko'ring", aks holda `err.message`); boshqa hollarda `body.detail`dan xabar — FastAPI validation array, string yoki MES tuzilmali `{code, message}` konverti (`"E003: ..."` ko'rinishida; busiz toast'ga "[object Object]" tushardi), u ham bo'lmasa "Xatolik yuz berdi. Qayta urinib ko'ring." fallback;
- `detailParts(err)` / `detailMessage(err)` — MES `{code, message}` konvertini ajratish; `detailParts` kod ALOHIDA kerak bo'lganda (terminal skan oqimi xato kodiga qarab ovoz beradi), `detailMessage` bitta satr qaytaradi;
- `handleError(err)` — TanStack Query `onError` uchun to'g'ridan-to'g'ri handler (`onError: handleError`) — `toast.error(extractErrorMessage(err))`; avvalgi curried varianti va `useCustomToast` wrapper'i olib tashlangan, hamma joyda sonner `toast.success/error` to'g'ridan-to'g'ri chaqiriladi;
- `getInitials(name)` — ismdan 2 harfli initsiallar (avatar uchun).

### `frontend/src/vite-env.d.ts`
Vite client type'lari + `ImportMetaEnv` interfeysi (`VITE_API_URL`, `VITE_API_TIMEOUT_MS?`) — env o'zgaruvchilarga type-safe murojaat.

### `frontend/src/lib/utils.ts`
shadcn standarti — `cn(...inputs)`: `clsx` + `tailwind-merge` kombinatsiyasi, class name'larni konfliktlarsiz birlashtirish uchun. Deyarli barcha UI komponentlar shuni ishlatadi.

### `frontend/src/lib/mes.ts`
MES domen konstantalari va format helper'lari — deyarli barcha sahifa va komponentlar shu modulga tayanadi:
- **O'zbekcha label map'lar**: `ORDER_STATUS_LABELS`/`ORDER_STATUS_COLORS` (draft → "QORALAMA", ... + CSS o'zgaruvchi ranglar), `PRIORITY_LABELS`, `ROLE_LABELS` (`Record<UserRole, string>` — generatsiya qilingan enum bo'yicha tiplangan, 13 rol; yorliqsiz yangi rol build'ni yiqitadi), `EMPLOYEE_STATUS_LABELS`, `MACHINE_STATUS_LABELS`, `CAPACITY_UNIT_LABELS` (m²/soat, m/soat, dona/soat — backend `CapacityUnit`), `MATERIAL_TYPE_LABELS`; `TERMINAL_STATUSES` — yakuniy holatlar tuple'i (`delivered`, `cancelled`);
- **`PRIORITY_DOT_CLASSES` / `PRIORITY_TEXT_CLASSES` / `PRIORITY_BADGE_CLASSES`** — prioritet ranglarining yagona manbasi: select nuqtalari, reestr matni va to'ldirilgan badge (terminal proyekt kartalari) uchun Tailwind class map'lari;
- **`POST_COLORS`** — post kodi (ARRA, KROMKA, OVAL, PRISADKA, ROVER, STOLYARKA, BOYOQ) → CSS o'zgaruvchisi (`var(--post-arra)` ...); bosqich ranglari butun ilova bo'ylab shu map'dan olinadi;
- **`mixTint(color, pct)` / `chipColors(color, bgPct)`** — chip rang formulasi (WCAG AA): matn rangning to'q variantida (`78%, black`), fon oq tint; ilgari PostBadge/StatusBadge/OrderMatrix shu satrni alohida takrorlardi;
- **Noodatiy marshrut helper'lari** — `PROCESS_OPS` (modul-ichki map: 14 jarayon kodi → amal nomi + post, backend `PROCESS_POSTS` bilan sinxron), `isCustomRoute(name)` (detal marshruti nomdagi `{kodlar}`dan olinganmi) va `partOperations(name, postCode)` (nomdagi `{7;11;8}` ro'yxatidan SHU postga tegishli amal nomlari; faqat bir postga bir nechta amal tushadigan postlarda — ARRA/KROMKA/STOLYARKA). `Common/OperationChips` va `OrderMatrix` shulardan foydalanadi;
- **`OPERATOR_ROLES`** — 7 ta operator rol tuple'i (arrachi, kromkachi, ovalchi, prisadkachi, roverchi, stolyar, boyoqchi); route guard'lar (`_layout.tsx`, `/terminal`) shu ro'yxat bilan tekshiradi. **`MACHINE_BOUND_ROLES`** — stanok bog'lami majburiy qurilma rollari (`terminal`, `tablo`);
- **Sahifa huquqi predikatlari** — to'rt daraja: `isSuperuser` (foydalanuvchilar ro'yxati), `isAdmin` (superuser yoki `role === "admin"` — printer agentlar, loglar), `isManagement` (admin + manager + direktor — mijozlar, hodimlar, hisobotlar), `isProductionStaff` (boshqaruv + texnolog — buyurtmalar, stanoklar, materiallar); `RoleUser` tipidagi `role` maydoni `UserRole` bilan tiplangan, ya'ni rol qayta nomlansa solishtirish jimgina `false` bo'lib qolmay, build yiqiladi (`ROLE_LABELS` bilan bir xil qoida). **Sidebar menyusi ham (`AppSidebar` `NAV_ITEMS`), route guard'lar ham (`lib/guards`) SHU predikatlarni o'qiydi** — ilgari ikkalasi alohida yozilgani uchun "menyuda ko'rinadi, ochsang bosh sahifaga uloqtiradi" holati chiqib qolgandi;
- **Domen predikatlari**: `isCut(i)` — arrachi nazarida "kesildi" (ARRA skan bor YOKI chek chiqarilgan; CutmapView va SheetSvg bitta ta'rifdan foydalanadi), `deadlineTone(value)` — muddat ohangi (`overdue`/`today`/`""`, kun aniqligida — `date` UTC yarim tun bo'lgani uchun xom solishtirish Toshkentda noto'g'ri ishlar edi; terminal (vazifalar jadvali va `OrderPicker`) hamda tablo ishlatadi);
- **Format helper'lar**: `formatDate`/`formatDateTime` (brauzer locale'idan mustaqil `dd.mm.yyyy`), `formatMoney` (`Intl.NumberFormat("uz-Latn-UZ")` + "so'm"), `remainingPayment(o)` (qoldiq to'lov = `amount − advance_payment`), `formatSize(l, w, t)` (`L × W × T mm`).

### `frontend/src/lib/guards.ts`
Ikki guard:
- `requireAuth()` — autentifikatsiya guard'i: `readUserMe()` chaqiradi, faqat 401 da `redirect({ to: "/login" })` (tarmoq uzilishi/5xx da sessiya o'ldirilmaydi — xato `errorComponent`da ko'rinadi); foydalanuvchini qaytaradi, rolga qarab qo'shimcha yo'naltirish chaqiruvchining ishi. `_layout.tsx`, `/terminal` va `/tablo` `beforeLoad`lari shu bilan;
- `requireAccess(allow)` — route guard fabrikasi: `beforeLoad`da `readUserMe()` chaqiradi va predikat (`lib/mes`dan) `false` qaytarsa `redirect({ to: "/" })`. **`beforeLoad`da bo'lgani muhim** — sahifaning so'rovlari umuman yuborilmaydi; render ichida tekshirish kech, brauzer ma'lumotni yuklab, keshga solib bo'lgach "ruxsat yo'q" ekrani chiqadi. Ishlatuvchilar: `/admin` (`isSuperuser`); `/printers`, `/logs` (`isAdmin`); `/clients`, `/employees`, `/reports` (`isManagement`); `/machines`, `/materials` (`isProductionStaff`).

### `frontend/src/lib/scxDir.ts`
CNC postlari uchun SCX fayllarni saqlash yordamchilari (File System Access API): `dirSupported()`, `getSavedDir()`/`pickDir()` (bir marta tanlangan papka IndexedDB'da saqlanadi), `projectFolder(name)` (proyekt nomli subpapka), `saveScxToDir()`, `downloadScx(id, projectName)` (papka bo'lmasa Downloads'ga) va `scxFileUrl(id)` — yuklab olish URL'ini quruvchi. Terminal (PRISADKA/ROVER oqimi va skan avto-yuklash) shu moduldan foydalanadi.

### `frontend/src/lib/anketa.ts`
Buyurtma anketasining variantlar katalogi (qog'oz formadan ko'chirilgan). Bazaga faqat **kod** yoziladi, matn shu yerda turadi — label o'zgarsa saqlangan tarix buzilmaydi.

| Eksport | Mazmuni |
|---|---|
| `Option` | `{ value, label }` tipi |
| `FURNITURE_TYPES` | 10 ta mebel turi (oshxona, shkaf_kupe, yotoq, divan, bolalar, ofis, prixojaya, tv_tumba, komod, vannaxona) |
| `LAYOUT_SHAPES` | Xonadagi joylashuv: `togri` / `burchak` / `p_shakl` / `orolchali` |
| `CORPUS_MATERIALS`, `CORPUS_THICKNESS` | Korpus materiali (ldsp/mdf/massiv/plastik/fanera) va qalinligi (16/18/boshqa) |
| `FACADE_MATERIALS`, `COUNTERTOPS` | Fasad materiali (7 ta) va stol usti (postforming / sun'iy tosh / massiv / kerak emas) |
| `HARDWARE_LEVELS` | `oddiy` / `medium` / `premium` |
| `EXTRA_SERVICES` | Xona jihozlari — 4 ta: LED, rozetka, organayzer, oyna. Yetkazish/montaj bu ro'yxatda EMAS: ular butun buyurtmaga tegishli (`OrderSurvey.delivery`/`installation`) |
| `WALL_LETTERS` | `["A","B","C","D","E"]` — o'lchov varag'ida devor harflari (A dan soat yo'nalishi bo'yicha) |
| `labelOf(options, value)` / `labelsOf(options, values)` | Kod → matn; kodlar ro'yxati → vergul bilan ajratilgan matn (texnolog jamlanmasi uchun) |

### `frontend/src/lib/validation.ts`
Umumiy zod schema'lar — backend cheklovlari bilan sinxron ushlab turiladi (`backend/app/schemas/users.py` ga qarang):

| Eksport | Tavsif |
|---|---|
| `PHONE_PATTERN = /^\+998\d{9}$/` | E.164 O'zbekiston mobil formati (server `PHONE_PATTERN` bilan mos) |
| `passwordSchema` | Majburiy parol (parol o'rnatish/yangilash) — min 8 belgi + kuch talablari: kamida bitta kichik harf, katta harf, raqam va maxsus belgi (alohida regex'lar, o'zbekcha xabarlar; server `validate_password_strength` bilan mos) |
| `optionalPasswordSchema` | `passwordSchema`dan hosil qilingan ixtiyoriy variant (`.optional().or(z.literal(""))`) — admin edit: bo'sh = "o'zgartirmaslik" |
| `phoneSchema` | Majburiy telefon, regex bilan |
| `optionalNameSchema` | Ixtiyoriy ism: `trim`, max 30 belgi, to'ldirilgan bo'lsa min 2 belgi; bo'sh satr `undefined`ga transform qilinadi (backend `min_length=2` tufayli 422 bermasligi uchun) |
| `optionalFormattedPhoneSchema` | Ko'rinishda formatlangan telefon (`+998 90 123-45-67`) qabul qilinadi; transform'da bo'shliq/defis olib tashlanib kanonik `PHONE_PATTERN` bilan tekshiriladi, bo'sh satr ruxsat |
| `formatUzPhone(input, prev?)` | Yozish paytida jonli avto-format: `+998 90 123-45-67`; `prev` argumenti separator o'chirilganda oxirgi raqamni ham olib tashlaydi (backspace qulfini oldini oladi) |
| `formatMoneyInput(input)` | Pul maydoni avto-separatori: `"5000000"` → `"5 000 000"`, max 12 raqam; submit oldidan bo'shliqlar olib tashlanadi |

Xato xabarlari o'zbek tilida — formalar to'g'ridan-to'g'ri foydalanuvchiga ko'rsatadi.

---

## 3. Routing tuzilmasi va Auth flow

### Routing tuzilmasi (file-based)

TanStack Router `src/routes/` papkasidan quyidagi daraxtni quradi (`routeTree.gen.ts` — Vite plugin tomonidan avtomatik generatsiya qilinadi, qo'lda tahrirlanmaydi):

```
__root.tsx                 → root layout (Outlet, devtools, 404/error)
├── login.tsx              → /login       (mehmon sahifa, teskari guard)
├── terminal.tsx           → /terminal    (fullscreen operator POS ekrani, sidebar'siz)
├── tablo.tsx              → /tablo       (fullscreen sex TV-tablosi, sidebar'siz)
└── _layout.tsx            → pathless layout (auth guard + rol-router + sidebar shell)
```

`_layout` ichidagi sahifalar (`frontend/src/routes/_layout/*`):

| Route | Fayl | Mazmuni |
|---|---|---|
| `/` | `index.tsx` | Dashboard — jonli ishlab chiqarish monitori (quyida) |
| `/orders` | `orders/index.tsx` | Buyurtmalar reestri: status tab'lar + to'lov ustunlari (quyida) |
| `/orders/:id` | `orders/$orderId.tsx` | Buyurtma sahifasi — lifecycle tugmalari, to'lovlar, matritsa (quyida) |
| `/anketa/:id` | `anketa.$orderId.tsx` | Buyurtma anketasi — mijoz so'rovnomasi + o'lchov varag'i (quyida) |
| `/cutmap/:id` | `cutmap.$orderId.tsx` | Kesish xaritalari — admin/print ko'rinishi (quyida) |
| `/clients` | `clients.tsx` | Mijozlar reestri (guard: `requireAccess(isManagement)`): qidiruv (ism/telefon), `AddClient` dialogi, buyurtmalar soni ustuni |
| `/employees` | `employees.tsx` | Hodimlar (guard: `isManagement`): qidiruv, post chip'lari (`POST_COLORS`), `AddEmployee` (admin-only; multi-post checkbox, kamida 1 post), beyjik dialogi — UUID `QRCodeSVG` sifatida chop etishga tayyor, beyjikni qayta generatsiya admin-only (eski beyjik bloklanadi). Admin/superuser uchun har qatorda `EditEmployee` (qalam) va `DeleteEmployee` (savat) tugmalari — `EmployeesService.updateEmployee` / `deleteEmployee` |
| `/machines` | `machines.tsx` | Stanoklar (guard: `isProductionStaff`): post badge'lari, holat (`MACHINE_STATUS_LABELS`), `AddMachine` (admin-only) |
| `/materials` | `materials.tsx` | Materiallar (guard: `isProductionStaff`): turi tab'lari (List/Kromka/Furnitura) + qidiruv; reestr project fayllardan avtomatik to'ldiriladi (TZ 4.5) |
| `/reports` | `reports.tsx` | Hisobotlar (TZ 11, guard: `isManagement`): Mahsuldorlik / Buyurtmalar / Material sarfi tab'lari, `DatePicker` sana oralig'i, Excel eksport (`GET /api/v1/reports/{kind}?format=xlsx`) |
| `/admin` | `admin.tsx` | Foydalanuvchilar boshqaruvi (superuser guard, quyida) |
| `/printers` | `printers.tsx` | Printer agentlar — ulanish kodlari, jonli holat (WS), versiya, stanok bog'lash (`requireAccess(isAdmin)` guard'i, quyida) |
| `/logs` | `logs.tsx` | Loglar (`requireAccess(isAdmin)` guard'i) — audit jurnal: kategoriya tugmalari, xabar bo'yicha qidiruv (`useDebounced` 400ms), `DatePicker` sana filtri, 50 talik sahifalash; qator bosilsa detal dialogi (post/stanok/agent ID'lari lug'atdan nomga aylantiriladi) |
| `/settings` | `settings.tsx` | Foydalanuvchi sozlamalari (quyida) |

Ro'yxat sahifalarida umumiy naqsh: qidiruv maydoni `Common/SearchInput`, so'rov xatosida `Common/QueryError` (qayta urinish tugmasi bilan), bo'sh ro'yxatda `Common/EmptyRow` (komponent tafsilotlari `docs/06-frontend-components.md`da).

### `frontend/src/routes/__root.tsx`
`createRootRoute` — barcha route'larning ildizi. `HeadContent` (route'lardagi `head()` meta/title'larni renderlash), `Outlet`, `AppToaster`, hamda `TanStackRouterDevtools` va `ReactQueryDevtools`. `notFoundComponent` → `@/components/Common/NotFound`, `errorComponent` → `@/components/Common/ErrorComponent`. **`AppToaster`** — sonner `Toaster` (`richColors closeButton`) pathname'ga qarab moslashadi: `/terminal` va `/tablo`da top-center, 1.3rem shrift, 560px kenglik, 6s (operator monitordan uzoqda turadi); qolgan sahifalarda odatdagi bottom-right, 4s.

### `frontend/src/routes/login.tsx`
`/login` sahifasi. **Teskari guard**: `beforeLoad`da `UsersService.readUserMe()` chaqiriladi — agar muvaffaqiyatli bo'lsa (foydalanuvchi allaqachon tizimda), `redirect({ to: "/" })` tashlanadi; xato bo'lsa sahifa ochiladi. Forma react-hook-form + zod (sxema `makeFormSchema()` bilan komponent ichida quriladi — top-level `z.object` zod'ni entry chunk'ka tortib, terminal/tablo kioskini ham og'irlashtirardi): `username` — foydalanuvchi nomi yoki telefon, `password` — faqat `min(1)` (bo'sh emasligi; kuch talablari faqat parol o'rnatishda qo'llanadi, eski/seed parollar bilan kirish saqlanadi); `satisfies z.ZodType<Body_login_access_token>` orqali generatsiya qilingan API tipiga bog'langan. Submit `useAuth().loginMutation` ga yuboriladi, UI `AuthLayout`, `LoadingButton`, `PasswordInput` komponentlaridan foydalanadi. Login xatosi toast emas — forma ichida inline `role="alert"` bloki sifatida ko'rsatiladi (`extractErrorMessage`).

### `frontend/src/routes/_layout.tsx`
Pathless layout — himoyalangan sahifalar qobig'i. **Auth guard + rol-router**: `beforeLoad`da `requireAuth()` (`lib/guards`) chaqiriladi — 401 bo'lsa `/login`ga redirect, boshqa xatolar (tarmoq uzilishi, 5xx) `errorComponent`da ko'rinadi (sessiya o'ldirilmaydi); so'ng rol bo'yicha yo'naltiriladi (TZ 3.4/3.5) — `terminal` roli yoki `OPERATOR_ROLES`dagi rollar (`@/lib/mes`) → `redirect({ to: "/terminal" })`, `tablo` roli → `/tablo`; ya'ni qurilma/operator akkauntlari admin panelga umuman kira olmaydi. Layout `SidebarProvider` + `AppSidebar` (`@/components/Sidebar/AppSidebar`) + `SidebarInset`dan iborat; mobil ko'rinishda (md dan kichik) `SidebarTrigger`li header ko'rsatiladi. `main` ichida kontent `max-w-[1800px]` bilan chegaralangan (keng monitorda jadval ustunlari yoyilib ketmasin; 1600 rad etilgan — 1920px monitorda 1920−256−64 = 1600, ya'ni menyuni yig'ish kontentga bir piksel ham qo'shmasdi). `sectionTitles` map'i pathname bo'yicha mobil header sarlavhasini beradi — sidebar bilan BITTA manbadan quriladi: `AppSidebar`ning `NAV_ITEMS` eksporti + menyuda yo'q `/settings`.

### `frontend/src/routes/_layout/index.tsx`
`/` — Dashboard, jonli ishlab chiqarish monitori (TZ 10.2):
- **Stanoklar jadvali**: `getMachinesQueryOptions()` ro'yxati — karta emas, `<Table>` (TZ 10.2.1): Stanok / Post (`PostBadge`) / Quvvat / Navbatda / Bugun / Tugash / Holat ustunlari. Navbat statistikasi (`queue_scans`, hajm, bugungi scanlar, `forecast_hours` — TZ 4.3 prognoz) `ReportsService.reportDashboard`dan 60s poll bilan olinadi va faqat superuser/admin/manager/director'ga so'raladi (`enabled: canStats`);
- **Aktiv buyurtmalar**: `TabloService.readTabloMatrix` (60s poll) — har qatorda `StagePipeline` (bosqichlar bo'yicha done/total), muddat, `StatusBadge`; qator buyurtma sahifasiga link;
- **Jonli rejim**: `useMesWs` — `scan.*`/`order.*`/`session.*` event'larida `["tablo"]` invalidatsiyasi; header'da `online` flag'idan JONLI / ALOQA YO'Q badge.

### Orders moduli (`_layout/orders/*`, `_layout/anketa.$orderId.tsx`, `_layout/cutmap.$orderId.tsx`)
- **`orders/index.tsx` — `/orders` reestri.** Status tab'lari (Hammasi / Qoralama / Texnologda / Jarayonda / Tayyor (sexda) / Topshirilgan / Bekor qilingan) jonli count'lar bilan — `OrdersService.readOrderStatusCounts`, 30s poll; texnologga (superuser bo'lmasa) "Qoralama" va "Bekor qilingan" tab'lari ko'rinmaydi (backend ham filtrlaydi). Qidiruv (raqam/nom/mijoz) server-side (`getOrdersQueryOptions`), saralash client-side (`created_at`, `deadline`, `priority`, `amount`, qoldiq to'lov; reestr bitta sahifaga sig'adi — limit 100, oshsa server-side sort kerak bo'ladi). To'lov ustunlari: "Umumiy narx" va "Qoldiq to'lov" (`remainingPayment`, `lib/mes`). Yangi buyurtma (`AddOrder`) faqat admin/manager/superuser'ga.
- **`orders/$orderId.tsx` — buyurtma sahifasi.** Meta grid (holat, mijoz, muddat, prioritet, umumiy narx / boshlang'ich to'lov / qoldiq, detallar/nusxalar, sanalar, bekor sababi) + rol-gated lifecycle tugmalari: **Tahrirlash** (`EditOrder` — manager, buyurtma `delivered`/`cancelled` bo'lmaganda), Tasdiqlash (manager, `draft` → `confirmOrder`), Project fayl yuklash (texnolog, `technical_review`, `.project`), Ishlab chiqarishga uzatish (manager, fayl yuklangach), **Anketa** (`Link to="/anketa/$orderId"` — har doim ko'rinadi), Kesish xaritalari (fayl bor bo'lsa), TOPSHIRILDI (manager, `completed`), Bekor qilish (sabab kamida 3 belgi). Texnolog `technical_review` holatida meta grid ustida **drag&drop zonasi** oladi: `.project` fayl sudrab tashlanadi yoki zonaga bosilib file dialog ochiladi; kengaytma `.project` bo'lmasa "Faqat .project fayl qabul qilinadi" toast'i (klaviatura yo'li — headerdagi "Project fayl yuklash" tugmasi). Pastda `MachineAssign` (stanok biriktirish — faqat manager, `draft`/`technical_review` holatida va project fayl yuklangan bo'lsa) va `OrderMatrix` (detallar matritsasi, texnologga tahrirlanadi; marshruti nomdagi `{kodlar}`dan olingan detal qatorida amber "Marshrut nomdan" belgisi — `isCustomRoute`, qo'lda belgilangan o'zgarish faylni qayta yuklaganda yo'qolishini ogohlantiradi). Texnologda va furnitura bo'lsa (`hardware.length > 0 && isTexnolog`) matritsa `Tabs` ichiga tushadi: **Detallar matritsasi** / **Furnituralar (N)** — ikkinchi tab `material_usage`ning `kind === "hardware"` yozuvlaridan (Kod / Nomi / Soni / Birlik; SKU kodlilar oldinda, chunki kodsizlar orasida 3D-model qoldiqlari uchraydi). Eng pastda fayllar ro'yxati yuklab olish havolalari bilan; ro'yxat SCX'ni chiqarib tashlaydi (`f.kind !== "scx"`) va SCX uchun alohida qator turadi: "SCX dasturlari (N ta)", "Hammasini yuklab olish (ZIP)" (`/orders/{id}/files/scx.zip`), yopiq `<details>`da to'liq ro'yxat va faqat texnologga **"Qayta yaratish"** tugmasi (fayllarni nusxa QR'i bilan qayta nomlash — Nanxing skan mosligi). Har amal `["orders"]` key'larini invalidatsiya qiladi.
- **`anketa.$orderId.tsx` — `/anketa/:id`, buyurtma anketasi.** Qog'oz so'rovnomaning ekran varianti; ma'lumot `Order.survey` JSONB ustunida, `OrderSurvey` schema'si bo'yicha. Sahifa `getOrderQueryOptions(id)` bilan buyurtmani oladi va `order.survey` ni **faqat bir marta** (`loaded` ref) lokal `useState`ga ko'chiradi — aks holda saqlashdan keyingi refetch menejer yozayotgan matn ustiga tushadi.
  - **Rollar**: `canEdit` = superuser / `admin` / `manager` — forma ko'rinishi. Qolganlar (texnolog, direktor) `RoomSummary` — o'qish uchun jamlanma; tartib qog'ozning teskarisi (avval modullar va o'lchamlar, keyin material), bo'sh maydonlar tashlab yuboriladi (`Facts`). "Xona o'lchamlari" bo'limida o'lchov qatoridan keyin **"Buyurtma bo'yicha"** qatori ham bor — `ORDER_SERVICES`dan belgilanganlari vergul bilan.
  - **Xonalar**: anketa xonalar massivi (`survey.rooms`), tepada xona pill'lari + "Xona qo'shish"; xona o'chirish pilldagi `×` da (brauzer tablari naqshi — obyekt va uni o'chirish tugmasi bir joyda), `ConfirmDialog` orqali (rasmlar ham server tomonda o'chadi); bitta xona qolganda `×` ko'rsatilmaydi. Har xona: 1) nomi va rasmlar, 2) mebel turi, 3) shakl (`ShapeChoice` — SVG piktogrammali `SHAPE_ART`) va xona uzunlik/kenglik/balandlik + mebel devori uzunligi, 4) korpus materiali/rangi/qalinligi/izohi, 5) fasad materiali/rangi/stol usti/izohi, 6) furnitura darajasi + qo'shimcha xizmatlar, 7) izoh (`Textarea`, max 1000). 8-bo'lim — **O'lchov varag'i** `<details>` ichida yopiq turadi (zamerdan keyin to'ldiriladi): `WALL_LETTERS` bo'yicha 5 ta devor uzunlik/balandligi, modullar jadvali (nomi, devor, eni/chuqurlik/balandlik, soni, izoh — qator qo'shish/o'chirish) va umumiy pm/balandlik.
  - **"Butun buyurtma uchun" kartasi** (faqat `canEdit`): xona pill'lari bilan xona bo'limlari orasida turadi. Ichida `ORDER_SERVICES`ning uchta checkbox'i — `packaging` "Upakovka qilish", `delivery` "Yetkazib berish", `installation` "O'rnatish (montaj)" — hamda o'lchov sanasi (`DatePicker`) va o'lchagan usta (`survey.measured_at` / `measured_by`). Bu maydonlar xona emas, BUYURTMA darajasida: sex bitta `.project` fayl ustida ishlaydi, logistika ham butun buyurtmani bitta mashinada olib ketadi; ilgari xona bo'limida turgani uchun menejer 3-xonada o'zgartirsa, jimgina butun buyurtma uchun o'zgarardi.
  - **Avtosaqlash**: har tahrirda `dirty` yoqiladi, 1.5s debounce'dan keyin `OrdersService.saveOrderSurvey` (PUT `/orders/{id}/survey`); pastda `sticky` panel holatni ko'rsatadi — besh holat ("Saqlanmoqda..." / xato bo'lsa **"Saqlanmadi — qayta urinib ko'ring"**, `text-destructive` va `role="alert"` bilan / "O'zgarishlar avtomatik saqlanadi" / "Saqlandi HH:MM" / sahifa endi ochilgan va hali saqlash bo'lmaganda "Hammasi saqlangan"), yonida esa qo'lda "Saqlash" tugmasi (`disabled={!dirty}`). `beforeunload` da ogohlantirish, komponent unmount bo'lganda saqlanmagan qoralama fire-and-forget yuboriladi. Muvaffaqiyatda `["orders", id]` invalidatsiya qilinadi.
  - **Xona rasmlari** (`RoomPhotos`): anketa JSON'ida emas — `OrderFile(kind=DOCUMENT, meta.room_id)` da, shuning uchun avtosaqlash bilan aralashmaydi. Butun panel drop-zona; `OrdersService.uploadRoomPhoto` (POST `/orders/{id}/survey/photos`, form-data `room_id` + `file`) va `deleteRoomPhoto`. Klient chegaralari: xonaga 6 tagacha rasm, har biri 5 MB gacha, faqat `image/*` — chegara buzilsa toast, serverga so'rov ketmaydi. Rasm `src` = `${OpenAPI.BASE}/api/v1/orders/{id}/files/{fileId}` (`crossOrigin="use-credentials"` — cookie auth), bosilsa `Dialog`da kattalashadi. Har amaldan keyin `["orders", orderId]` invalidatsiya (rasmlar `order.files`dan o'qiladi).
  - Raqamli maydonlar `NumInput`/`Num` orqali: yozilayotgan xom matn saqlanadi (aks holda "3," yozilganda maydon o'zini tozalab yuboradi), blur'da normallashadi; `numOrNull` vergulni nuqtaga aylantiradi.
- **`cutmap.$orderId.tsx` — `/cutmap/:id`.** Kesish xaritalarining admin ko'rinishi (TZ 10.3): `Terminal/CutmapView` `admin` rejimida (`OrdersService.readOrderCutmap`), `registerPrint` callback'i orqali "PDF / Chop etish" tugmasi barcha xaritalarni yangi oynada A4 landscape sahifalarga chiqaradi (har list — alohida sahifa).

### `frontend/src/routes/_layout/admin.tsx`
`/admin` — foydalanuvchilar boshqaruvi. **Superuser guard**: `beforeLoad: requireAccess(isSuperuser)` — `is_superuser` bo'lmasa `redirect({ to: "/" })` (backend ham ro'yxatni faqat superuser'ga beradi: ro'yxat barcha telefon raqamlarni ochadi). Sidebar'dagi "Foydalanuvchilar" yozuvi ham AYNAN shu shartda qo'shiladi — `role === "admin"` bo'lgan superuser bo'lmagan foydalanuvchiga ko'rinmaydi (ilgari ko'rinardi va bosilganda bosh sahifaga qaytarardi). `useQuery(getUsersQueryOptions())` bilan ro'yxat olinadi (`isLoading`da `Skeleton` — Suspense ishlatilmaydi). Jadval — oddiy `<Table>` va fayl ichidagi lokal `UserRow` komponenti (ism + `Siz` badge'i `useCurrentUser` bilan solishtirib, telefon, rol `ROLE_LABELS`dan, faol/nofaol nuqtasi, `UserActionsMenu`), `clients.tsx`/`employees.tsx` bilan bir uslubda; sahifalash yo'q — `getUsersQueryOptions` barcha sahifalarni bitta ro'yxatga yig'adi. Yuqorida `AddUser` dialog tugmasi; `AddUser` va `EditUser` forma yadrosi umumiy `components/Admin/UserForm.tsx`da (`buildUserFormSchema`, `UserFormFields`).

### `frontend/src/routes/_layout/printers.tsx`
`/printers` — printer agentlari (TZ 2.2.2 pairing oqimi), sarlavha `head()` orqali "Printer agentlar | MebeliX". Sahifa admin uchun: `beforeLoad: requireAccess(isAdmin)` (guardsiz admin bo'lmagan foydalanuvchi URL bilan kirib, bo'sh jadval ko'rib, 403 qaytaradigan endpointni 10s da bir so'rab turardi), `AppSidebar.tsx` da `Printer` ikonkali yozuv ham `admin` blokida, ro'yxat/amal endpointlari esa backendda `AdminUser` bilan himoyalangan. Yuqorida "Yangi agent" dialogi (exe qo'lda tarqatiladi — yuklab olish tugmasi ataylab olib tashlangan, serverda eski nusxa adashtirardi); ostida uch qadamli o'rnatish yo'riqnomasi (drayver → exe → kod). Jadval `getBridgeAgentsQueryOptions()` (`queries/mes.ts`, `BridgeAgentsService.readBridgeAgents`) dan — WS `bridge.paired/connected/disconnected` eventlari `["bridge-agents"]` ni invalidatsiya qiladi (sahifada spread bilan qo'shilgan 10s poll faqat zaxira): nomi, versiya chipi (`v1.2.0`, yo'q bo'lsa "eski exe"), holat — **"Ulandi"** (`last_seen_at` 6 daqiqadan yangi, `ONLINE_MS`), **"Uzilgan"**, **"Kod kutilmoqda"** yoki **"Kod muddati o'tgan"** — stanok bog'lash dropdown'i ("Stanok (skan-forvard)" ustuni; almashtirish/olib tashlash `ConfirmDialog` bilan — noto'g'ri tanlov skanlarni boshqa postga yozib yuborardi), **"Chek chiqarish"** ustunida `agent.can_print` `Switch`i (`ConfirmDialog` bilan: yoqilsa agent chek navbatidan ish oladi va o'sha kompyuterda GoDEX ulangan bo'lishi SHART, o'chirilsa faqat skan-forvard uchun ulanadi — printersiz stansiya uchun to'g'ri), oxirgi ulanish vaqti va har qatorda ikki amal: `KeyRound` — yangi kod (`regenerateBridgeCode`, eski token bekor bo'ladi) va `Trash2` — agentni bekor qilish (`deleteBridgeAgent`); ikkalasi ham `ConfirmDialog` orqali. Kod "Yangi agent" dialogida katta shriftda va jadvalning "Ulanish kodi" ustunida ko'rsatiladi — `fmtCode` bilan `AB12-CD34` ko'rinishida (telefonda aytish oson), 15 daqiqa amal qiladi; ulanish amalga oshgach yoki muddat o'tgach server `pair_code = null` qaytaradi (`bridge_agents.py` `_read()`) va ustunda "—" turadi.

### `frontend/src/routes/_layout/settings.tsx`
`/settings` — sozlamalar, Tabs asosida. `tabsConfig`da ikkita yozuv: "Profilim" (`UserInformation`) va "Parol" (`ChangePassword`) — ikkalasi ham hammaga ko'rinadi, rolga bog'liq filtr yo'q. Hisobni o'chirish bo'limi ("Xavfli zona", `DeleteAccount`) olib tashlangan: MES'da foydalanuvchini faqat superuser `/admin` orqali o'chiradi. `currentUser` hali yuklanmagan bo'lsa `null` qaytaradi.

### `frontend/src/routes/terminal.tsx` — `/terminal` (operator POS ekrani)
Fullscreen terminal (TZ 8) — sidebar'siz, POS monoblokda doim ochiq turadi. Guard: faqat `terminal`, `admin`, superuser va `OPERATOR_ROLES`; boshqalar `/` ga qaytariladi (401 → `/login`). Asosiy mexanika:
- **Majburiy to'liq ekran**: `document.fullscreenElement` ham, `matchMedia("(display-mode: fullscreen)")` ham false bo'lsa butun ekranni overlay yopadi va faqat "To'liq ekranga o'tish" tugmasi qoladi (`requestFullscreen` user-gesture talab qiladi). `fullscreenchange` va media-query `change` event'lari holatni kuzatadi; `chrome --kiosk` / PWA rejimida overlay chiqmaydi.
- **Kiosk avto-yangilanish**: har 5 daqiqada `/` ga `HEAD` so'rov, `ETag` o'zgargani yangi build belgisi (`updateReady`). Reload faqat xavfsiz paytda — xarita yopiq va oxirgi skandan 2 daqiqa o'tgan bo'lsa (30s da bir tekshiriladi). `import.meta.env.DEV` da butunlay o'chirilgan (Vite ETag'i o'zgaruvchan — reload sikli bo'ladi).
- **Avto-skan input** doim fokusda (har 2s qayta fokus; xarita ochiq yoki ekran qulflangan bo'lsa fokus qaytarilmaydi). Header'dagi SKAN ON / SKAN OFF tugmasi (OFF holatida `destructive` qizil) uni o'chiradi. Qiymat UUID regex'ga mos kelsa **beyjik** — `TerminalService.startTerminalSession` (sessiya ochish); aks holda **detal QR** — `ScansService.recordScan` (idempotentlik uchun `client_event_id = crypto.randomUUID()`). Bir xil kod uchun 2s cooldown (duplikat yutiladi, TZ 8.4.4); WS offline bo'lsa detal scan bloklanadi (E007 "Aloqa yo'q").
- **Scan natijasi**: audio signal (`Terminal/audio.ts`), "Oxirgi skan" paneli (kod + qoldiq yoki xato kodi; chiziq 15 s da o'zi yo'qoladi), 50 talik tarix ("Faqat xatolar" `Switch` filtri), 60s ichida BEKOR QILISH (`cancelScan`, ConfirmDialog bilan); javobda `scx_file_ids` kelsa fayllar avtomatik yuklab olinadi (ROVER postidan tashqari — ROVER'ga SCX kerak emas) — saqlangan SCX papkasi bo'lsa o'sha yerga (`lib/scxDir.ts`), bo'lmasa Downloads (TZ 12.5).
- **Post sahifalari**: ARRA — kesish xaritasi; KROMKA/OVAL — `Terminal/KromkaView` (skan darhol yoziladi, bir QR uchun 5 s to'siq, picker'da skan proyektni o'zi ochadi `/qr/{qr}/order` orqali); CNC postlari (PRISADKA/ROVER) — `Terminal/PrisadkaView` (SCX fayllarni BIR MARTA tanlangan papkaga, proyekt nomli subpapkada; yuklab olish progressi, ish-navbat tartibi, oxirgi skan qatori ajralib turadi; ROVER'da SCX ustuni ko'rsatilmaydi — `showScx=false`); qolganlari (STOLYARKA, BOYOQ) — umumiy vazifalar jadvali. Umumiy vazifalar so'rovi (`getTerminalTasksQueryOptions`) faqat o'z ko'rinishiga ega bo'lmagan postlarda yuboriladi — `OWN_VIEW_POSTS = [ARRA, PRISADKA, ROVER, KROMKA, OVAL]` da `enabled: false` (aks holda 7 terminalning hammasi 30s da bir keraksiz so'rov yuborardi). Bir postga bir nechta amal tushadigan postlarda detal nomi yonida amal nomi chip'lari — `Common/OperationChips` (`partOperations`, `lib/mes`): vazifalar jadvali va `KromkaView`da (masalan stolyarkada `{11}` o'rniga "G petlya o'ngdan"). Skan inputi fokussiz ham QR ni tutadi (birinchi tugmada fokus qaytadi). Skan banneri, tarix va Jarayonda panellari to'liq nusxa ID ko'rsatadi — chek/QR/SCX bilan belgima-belgi bir xil satr.
- **ARRA posti** — GibSaw uslubidagi drill-down: proyekt kartalari (`OrderPicker`, `TerminalService.readTerminalOrders`, 30s poll — raqam, proyekt nomi, `PRIORITY_BADGE_CLASSES` badge'i, materiallar ro'yxati, ARRA done/total progress va qoldiq, listlar soni, muddat rangi) → tanlangan proyekt `Terminal/CutmapView` ichida ochiladi: material tab'lari → list gridi → to'liq ekran xaritasi (`Terminal/SheetSvg`). Xarita ochiqda (`mapOpen`) header'dagi skan inputi o'rnini `statsContainer` portali egallaydi (material statistikasi 3×3 blok), chap ustundagi `toolbarContainer` portaliga esa CutmapView toolbari tushadi (Orqaga / Oldingi / Keyingi / Katta / Kichik / To'liq / **Chop etish**). "Chop etish" belgilangan detalning navbatdagi nusxasini `TerminalService.printInstanceLabel` orqali GoDEX navbatiga yuboradi (dialog yo'q); chop etish mutatsiyasi `Terminal/usePrintLabel.ts` hook'ida — CutmapView (`scope: "cutmap"`) va PrisadkaView (`scope: "prisadka"`) baham ko'radi. Xarita ochiqda `main` paddingi teskari margin bilan qoplanadi — xarita katta ko'rinadi. Boshqa postlarda: navbatdagi vazifalar jadvali (70%) + o'ng panel (30%).
- **Header**: chapda stanok nomi post rangida (`ctx.machine_name`, bo'lmasa post nomi) — "post/uskuna" taksonomiyasi olib tashlandi, arrachi tilida bitta identitet; yonida sessiya chipi (yashil nuqta + hodim ismi yoki amber "Beyjik QR scan qiling"), o'ngda SKAN ON/OFF tugmasi va WS uzilganda "ALOQA YO'Q" bloki. Jonli soat va alohida vaqt paneli yo'q — vaqt faqat scan tarixi qatorlarida.
- **Qulf va chiqish**: chap ustunning pastida doim turadigan `TBtn` tugmalari — "Qulflash" (butun ekranni yopadigan overlay, "Ochish" tugmasi bilan), operator rollar uchun "Chiqish" (logout), `terminal` qurilma akkauntida sessiya bo'lsa "Yakunlash" (`endTerminalSession`). `useMesWs` `scan.recorded/scan.cancelled/order.started/order.cancelled` event'larida `["terminal"]` invalidatsiyasi.

Yorliq (chek) chop etish zanjiri: terminal → `POST /api/v1/terminal/labels/{instance_id}` → arq task → Redis `mes:print:queue` → `/ws/bridge` → `bridge-agent` → GoDEX G500-U. Frontend faqat zanjirning birinchi bo'g'ini; tafsilotlar `docs/03-backend-api.md` va `docs/07-infra-devops.md` da.

Domen tafsilotlari (scan engine, xatolik kodlari, cutmap modeli): `docs/09-mes-domain.md`.

### `frontend/src/routes/tablo.tsx` — `/tablo` (sex TV-tablosi)
Fullscreen jonli matritsa (TZ 9): buyurtmalar × postlar jadvali `TabloService.readTabloMatrix`dan — 60s poll + WS `scan.*`/`order.*` invalidatsiyasi (WS uzilib qayta ulanganda darhol qo'shimcha invalidatsiya) + **soatiga bir marta** to'liq sahifa reload (TZ 9.7). Reload MA'LUMOT yangiligi uchun emas — buni WS push va 60s polling qiladi; yagona vazifasi deploydan keyin yangi bundle'ni olish (devordagi TV hech qachon qo'lda yangilanmaydi), shuning uchun drill-down ochiq bo'lsa taymer umuman qo'yilmaydi (`if (drill !== null) return`). Ilgari 5 daqiqada bir edi: har safar oq ekran chaqnab, ochilgan detal ro'yxati yopilib, tanlangan rejim ham "foiz" ga qaytardi. Uch rejim: **HAJM** (volume done/total, post birligida m²/m/dona), **SONI** (done/total), **FOIZ** (fallback) — tanlangan rejim `localStorage`da `tablo-mode` kaliti ostida saqlanadi (sahifa yangilangan yoki TV qayta yoqilgan paytda o'zgarmasin). Yuqorida "Jami" yig'indi qatori (nomi rejimga bog'lanmagan — qator hajm/soni/foizdan qaysi biri turishini rejim hal qiladi); har katakda post rangida progress fill, tugagan bosqich yashil "✓", muddati o'tib boshlanmagani qizil "BOSHLANMADI", qiymat OSHGANDA katak bir marta 0.9s yashil uriladi (`animate-cell-flash` → `@keyframes mx-cell-flash`, `index.css`; kamayishda — skan bekor qilinganda — urilmaydi). `tablo` roli stanokka bog'langan bo'lsa boshqa post ustunlari xiralashadi (kontekst rejim, "JORIY NUQTA" chipi). Qator bosilsa buyurtma drill-down'i — detal × post jadvali (`readTabloOrder`, 30s poll); post ustunlari matritsa javobidagi `posts` ro'yxatidan dinamik quriladi (typed `TabloPostCol`, hozir 7 post — BOYOQ bilan), rejim sarlavhasi ("Foiz nazorati" / "Soni nazorati") faqat shu drill header'ida qoladi. Guard faqat login talab qiladi (`requireAuth()` — har qanday rol ochishi mumkin; `tablo` rolining o'zi `_layout`dan shu yerga yo'naltiriladi). Header: to'liq logo (`/assets/logo/logo-gold.png` — sidebar/login bilan bitta brend manbasi), "JORIY NUQTA: {stanok}" chipi, o'rtada HAJM/SONI/FOIZ tugmalari, online nuqtasi (uzilganda qizil "OFFLINE" yozuvi) va `me && me.role !== "tablo"` shartida "Boshqaruv paneli" qaytish havolasi — busiz admin to'liq ekranda qamalib qolardi. Soat yo'q.

### Auth flow (login → cookie token → guard → silent refresh)

1. **Login**: `/login` formasida `useAuth().loginMutation` → `LoginService.loginAccessToken({ formData })` (OAuth2 form-data: username/password). Server javobida `access_token` va `refresh_token` **HttpOnly cookie** sifatida o'rnatiladi — frontend token'ni hech qayerda saqlamaydi (`localStorage` yo'q). Muvaffaqiyatda `navigate({ to: "/" })`.
2. **Guard + rol-router**: har bir himoyalangan sahifaga kirishda `_layout.tsx` `beforeLoad`i `requireAuth()` (`lib/guards` — ichida `readUserMe()`) chaqiradi — cookie yaroqli bo'lsa rol tekshiriladi: `terminal`/operator rollar `/terminal` ga, `tablo` `/tablo` ga yo'naltiriladi, qolganlar o'tadi; 401 bo'lsa `/login` ga redirect (boshqa xatolar `errorComponent`ga chiqadi). Ustiga sakkiz sahifa o'z `beforeLoad` guard'idan o'tkazadi (`lib/guards.requireAccess`, predikatlar `lib/mes`dan): `/admin` — `isSuperuser`; `/printers`, `/logs` — `isAdmin`; `/clients`, `/employees`, `/reports` — `isManagement`; `/machines`, `/materials` — `isProductionStaff`; `/terminal` esa o'z rol tekshiruvidan. `/login` esa teskari tekshiradi: sessiya bor bo'lsa `/` ga qaytaradi.
3. **So'rovlar**: barcha API chaqiriqlar `withCredentials: true` bilan ketadi (`main.tsx`da `OpenAPI.WITH_CREDENTIALS = true`), cookie avtomatik biriktiriladi.
4. **Silent refresh**: access token muddati tugab 401 kelsa, `main.tsx`dagi Axios interceptor `LoginService.refreshAccessToken()` orqali cookie'ni yangilab, asl so'rovni bir marta qayta yuboradi; parallel so'rovlar bitta umumiy refresh promise'ini kutadi.
5. **Fallback logout**: refresh ham 401 bersa (yoki `token_version` mismatch), `QueryCache`/`MutationCache` `onError`i cache'ni tozalab `/login` ga yo'naltiradi.
6. **Logout**: `useAuth().logout` → `LoginService.logout()` (server cookie'larni o'chiradi), `onSettled`da `queryClient.clear()` + `/login` ga navigate — server xato bersa ham lokal sessiya tozalanadi.

---

## 4. Hooks

### `frontend/src/hooks/useAuth.ts`
Autentifikatsiya mutation'lari:
- `loginMutation` — `LoginService.loginAccessToken({ formData })`; success'da `/` ga navigate; `onError` yo'q — xato login sahifasida inline ko'rsatiladi (toast emas);
- `logout()` — `logoutMutation.mutate()`; `onSettled`da har doim `queryClient.clear()` + `/login`.

`frontend/src/routes/login.tsx` va sidebar'dagi user menyusi tomonidan ishlatiladi.

### `frontend/src/hooks/useCurrentUser.ts`
Joriy foydalanuvchi — `useQuery(getCurrentUserQueryOptions())`, `retry: false` (401'da qayta urinmaslik). `queryKey: ["currentUser"]` — Dashboard, admin jadvali ("Siz" badge'i), settings va sidebar shu key'dan ulanadi. Guard'lar (`beforeLoad`) esa cache'siz to'g'ridan-to'g'ri `readUserMe()` chaqiradi.

### `frontend/src/hooks/useDebounced.ts`
`useDebounced(value, delay = 300)` — qiymatni kechiktirib qaytaradi. Qidiruv maydonlari uchun: busiz har harf yangi query key yaratib, jadval skeleton bilan "lip-lip" qiladi. Reestrlar va `/logs` qidiruvi (400ms) shu hookdan foydalanadi.

### `frontend/src/hooks/useScanFlash.ts`
`useScanFlash(items, getKey, getCount, rowIdPrefix)` — hisobi O'ZGARGAN qatorni aniqlab qaytaradi (skan ham, bekor ham) va uni 150ms dan keyin markazga scroll qiladi (`{rowIdPrefix}{key}` DOM id bo'yicha). Flash keyingi skangacha turadi. Bitta mexanizm uch joyda: prisadka, kromka va vazifalar jadvali.

### `frontend/src/hooks/useMobile.ts`
`useIsMobile()` — `matchMedia("(max-width: 767px)")` (breakpoint 768) asosida responsive flag. shadcn `sidebar` komponenti mobil/desktop rejimni shu bilan aniqlaydi.

### `frontend/src/hooks/useMesWs.ts`
`useMesWs(onEvent)` — jonli yangilanishlar kanali (TZ 2.3): `OpenAPI.BASE`dagi `http` `ws` ga almashtirilib `/api/v1/ws/events` ga WebSocket ochiladi. Ulanish uzilsa 3s dan keyin avto-reconnect, har 30s "ping" heartbeat ("pong" va JSON bo'lmagan frame'lar filtrlanadi); `onEvent` ref orqali saqlanadi — har doim eng so'nggi callback chaqiriladi. Qaytaradi: `{ online }` — Dashboard'dagi JONLI / ALOQA YO'Q badge, terminaldagi "ALOQA YO'Q" bloki va tablodagi nuqta/"OFFLINE" shu flag'dan. Iste'molchilar event turi bo'yicha (`scan.*`, `order.*`, `session.*`) tegishli query key'larni invalidatsiya qiladi.

---

## 5. Queries

### `frontend/src/queries/users.ts`
TanStack Query options factory'lari — queryKey'lar bir joyda markazlashtirilgan:

```ts
getUsersQueryOptions()        // queryKey: ["users"],       readUsers — barcha sahifalar yig'iladi
getCurrentUserQueryOptions()  // queryKey: ["currentUser"], readUserMe
```

Ikkalasi `queryOptions()` bilan e'lon qilingan (key/fn tiplashgan); `getCurrentUserQueryOptions` `queryFn`i `Promise<UserRead | null>` — `useCurrentUser` 401 da `null` bilan ishlaydi. `getUsersQueryOptions` `queryFn`i sahifalab yig'adi: `PAGE_SIZE = 100` (`queries/mes.ts`dan import, backend `MAX_PAGE_SIZE`) bilan `readUsers({ skip, limit })` loop'da `count`ga yetguncha chaqiriladi — 100 dan ortiq foydalanuvchi ham to'liq ko'rinadi (jadval client-side; foydalanuvchilar minglab bo'lsa server-side paginatsiyaga o'tish kerak bo'ladi).

`/admin` sahifasi ham, `useCurrentUser` ham oddiy `useQuery` bilan ishlatadi. Foydalanuvchi CRUD mutation'lari (Admin komponentlarida) invalidatsiya uchun shu key'larga tayanadi.

### `frontend/src/queries/mes.ts`
MES query factory'lari — 13 ta, `PAGE_SIZE = 100` (eksport, backend max sahifa — `queries/users.ts` ham shuni import qiladi):

```ts
getPostsQueryOptions()             // ["posts"], readPosts — staleTime 5 min (deyarli statik)
getMachinesQueryOptions()          // ["machines"], readMachines — staleTime 60s
getClientsQueryOptions(search)     // ["clients", search] — search-parametrli, limit 100
getEmployeesQueryOptions(search)   // ["employees", search]
getMaterialsQueryOptions(search, type) // ["materials", search, type] — type: sheet|band|hardware
getOrdersQueryOptions({status, search, page}) // ["orders", status, search, page], skip = page*100
getOrderQueryOptions(id)           // ["orders", id]
getOrderMatrixQueryOptions(id)     // ["orders", id, "matrix"]
getTerminalContextQueryOptions()   // ["terminal", "context"], refetchInterval 30s (admin stanok tuzatgach terminal o'zi tiklansin)
getTerminalTasksQueryOptions()     // ["terminal", "tasks"], refetchInterval 30s (WS asosiy trigger, bu zaxira)
getTabloMatrixQueryOptions()       // ["tablo", "matrix"], refetchInterval 60s — /tablo va Dashboard bitta so'rovdan
getOrderStatusCountsQueryOptions() // ["orders", "status-counts"], refetchInterval 30s — reestr tab'lari + sidebar badge
getBridgeAgentsQueryOptions()      // ["bridge-agents"] — /printers (10s poll spread) va /logs (staleTime 5 min, lug'at)
```

Yana bitta helper — `crudCallbacks(queryClient, queryKey, successMsg)`: CRUD mutatsiya callback triosi (muvaffaqiyat toast'i + `handleError` + `onSettled`da invalidatsiya) — har dialogda qo'lda takrorlanadigan naqsh bitta joyda.

Mutation va WS event handler'lar shu key'larga invalidatsiya qiladi: scan/sessiya event'lari `["terminal"]`, buyurtma amallari `["orders"]`, tablo/dashboard `["tablo"]`.

Factory'lardan tashqarida sahifa/komponent ichida inline e'lon qilingan `useQuery`lar ham bor:

| Key | Joyi | Sozlama |
|---|---|---|
| `["terminal", "orders"]` | `routes/terminal.tsx` → `OrderPicker` | `TerminalService.readTerminalOrders`, `refetchInterval` 30s |
| `["terminal" \| "admin", "cutmap", orderId]` | `components/Terminal/CutmapView.tsx` → `getCutmapQueryOptions(orderId, admin)` | `admin` bo'lsa `OrdersService.readOrderCutmap`, aks holda `TerminalService.readTerminalCutmap`; `refetchInterval` 60s. Yorliq chop etilgach `["terminal", "cutmap"]`, bekor qilinganda esa ikkala prefiks (`["terminal", "cutmap"]` + `["admin", "cutmap"]`) invalidatsiya qilinadi |
| `["terminal", "kromka", orderId]` | `components/Terminal/KromkaView.tsx` | `TerminalService.readTerminalKromka`, `refetchInterval` 30s |
| `["terminal", "prisadka", orderId]` | `components/Terminal/PrisadkaView.tsx` | `TerminalService.readTerminalPrisadka`, `refetchInterval` 30s |
| `["tablo", "order", orderId]` | `routes/tablo.tsx` → qator drill-down'i | `TabloService.readTabloOrder`, `refetchInterval` 30s |
| `["reports", "dashboard"]` | `_layout/index.tsx` (Dashboard) | `ReportsService.reportDashboard`, `refetchInterval` 60s, `enabled: canStats` |
| `["reports", "productivity" \| "orders" \| "materials", params]` | `_layout/reports.tsx` — uch tab | `ReportsService.report*(params)`; poll yo'q, sana oralig'i (`params`) key'ning bir qismi |
| `["audit-logs", module, q, day, page]` | `_layout/logs.tsx` | `AuditService.readAuditLogs` — `q` qidiruv (`useDebounced` 400ms), `dateFrom`/`dateTo` bitta kun, `limit` 50 |

Factory'ni spread bilan kengaytirib ishlatadigan joylar ham bor: `tablo.tsx` — `getMachinesQueryOptions()` (`enabled: me?.role === "tablo"`; rolni aniqlaydigan `getCurrentUserQueryOptions()` esa shartsiz chaqiriladi), `ClientCombobox` — `getClientsQueryOptions(debounced)` (`enabled: open`), `terminal.tsx` — `getTerminalTasksQueryOptions()` (`enabled: !!ctx && !OWN_VIEW_POSTS.includes(ctx.post_code)` — umumiy vazifalar so'rovi faqat maxsus ko'rinishsiz postlarda), `printers.tsx`/`logs.tsx` — `getBridgeAgentsQueryOptions()` (mos ravishda `refetchInterval` 10s va `staleTime` 5 min).

---

## 6. API Client (`frontend/src/client/`)

`@hey-api/openapi-ts` tomonidan generatsiya qilinadi; `core/` fayllar ham generator template'idan keladi, lekin qo'lda o'qilishi mumkin bo'lgan barqaror runtime.

### `frontend/src/client/index.ts`
Barrel eksport: `ApiError`, `CancelablePromise`/`CancelError`, `OpenAPI`/`OpenAPIConfig` hamda `sdk.gen.ts` (servis klasslari) va `types.gen.ts` (request/response tiplari) dagi hamma narsa. Ilova bo'ylab import faqat `@/client` orqali.

### `frontend/src/client/core/OpenAPI.ts`
Global client konfiguratsiyasi — `OpenAPI` singleton obyekti: `BASE` (API URL), `WITH_CREDENTIALS`, `TOKEN`/`USERNAME`/`PASSWORD`/`HEADERS` (statik qiymat yoki async resolver), `VERSION`, va `interceptors.request`/`interceptors.response` (`Interceptors<T>` klassi — `use`/`eject` metodli oddiy middleware ro'yxati). `main.tsx` startup'da `BASE` va `WITH_CREDENTIALS`ni o'rnatadi; `TOKEN` ishlatilmaydi (cookie auth).

### `frontend/src/client/core/request.ts`
HTTP so'rov dvigateli. Asosiy eksport:

```ts
request<T>(config: OpenAPIConfig, options: ApiRequestOptions<T>, axiosClient = axios): CancelablePromise<T>
```

Bosqichlari: URL qurish (`getUrl` — `{param}` path-interpolyatsiya + `getQueryString` query-serializatsiya, massiv/obyekt/Date qo'llab-quvvatlanadi), `getFormData` (FormData yig'ish), `getHeaders` (Bearer/Basic auth resolver'lari, Content-Type aniqlash), `sendRequest` (Axios orqali, `AbortController` + `onCancel` bilan bekor qilish, custom request interceptor'lar), keyin response interceptor'lar, `getResponseBody`/`getResponseHeader`, ixtiyoriy `responseTransformer`, va nihoyat `catchErrorCodes` — 4xx/5xx status'larni `ApiError`ga aylantirib throw qiladi. Muhim nuans: Axios xatosi response bilan kelsa, u throw qilinmasdan response sifatida qaytariladi va status tekshiruvi `catchErrorCodes`da bajariladi (shu tufayli `main.tsx`dagi Axios-level 401 interceptor retry'dan keyin ham ishlaydi).

### `frontend/src/client/core/ApiError.ts`
`Error` subklassi — `url`, `status`, `statusText`, `body` (server javobi, masalan FastAPI `detail`), `request` maydonlari bilan. `main.tsx` (401 fallback) va `utils.ts` (`extractErrorMessage`) shu tipga tayanadi.

### `frontend/src/client/core/CancelablePromise.ts`
`Promise<T>` implementatsiyasi + `cancel()` metodi: executor'ga `onCancel` callback beriladi (`request.ts` unga `controller.abort()` ni ro'yxatlaydi); `cancel()` chaqirilsa barcha cancel handler'lar ishga tushib, promise `CancelError` bilan reject bo'ladi. Resolved/rejected/cancelled holatlaridan keyin ikkinchi o'tish yo'q (idempotent).

### `frontend/src/client/core/ApiRequestOptions.ts` va `ApiResult.ts`
Faqat tip deklaratsiyalari. `ApiRequestOptions<T>` — bitta so'rovning to'liq tavsifi: `method` (GET/POST/...), `url`, `path`/`query`/`headers`/`cookies` parametrlari, `body`/`formData`/`mediaType`, status-kodga xos xato matnlari (`errors`), `responseHeader` va ixtiyoriy `responseTransformer`. `ApiResult<TData>` — xom javob: `url`, `ok`, `status`, `statusText`, `body`. Ikkalasi `request.ts` ichida ishlatiladi; `sdk.gen.ts` metodlari `ApiRequestOptions` obyektlarini yig'ib `request()`ga uzatadi.

### Generatsiya qilinadigan fayllar va yangilash buyrug'i

| Fayl | Nima | Generator |
|---|---|---|
| `frontend/src/routeTree.gen.ts` | Route daraxti (type-safe) — `src/routes/` fayllaridan | `@tanstack/router-plugin` (Vite dev/build paytida avtomatik) |
| `frontend/src/client/sdk.gen.ts` | 15 ta servis klass: `AuditService`, `BridgeAgentsService`, `ClientsService`, `EmployeesService`, `HealthService`, `LoginService`, `MachinesService`, `MaterialsService`, `OrdersService`, `PostsService`, `ReportsService`, `ScansService`, `TabloService`, `TerminalService`, `UsersService` — har metod `CancelablePromise` qaytaradi | `@hey-api/openapi-ts` |
| `frontend/src/client/types.gen.ts` | Request/response TypeScript tiplari (`UserRead`, `Body_login_access_token`, `OrderSurvey`/`SurveyRoom`/`SurveyWall`/`SurveyModule`, `OrderFileRead.meta`, `TerminalOrderCard`, `QrOrderRef`, `PrisadkaOrderState`, `TabloPostCol`, `Message`, ...) | `@hey-api/openapi-ts` |

API client'ni yangilash — `scripts/generate-client.sh` (repo root'dan):
1. `backend/`da `uv run python -c "...app.openapi()..."` bilan `openapi.json` eksport qilinadi;
2. fayl `frontend/`ga ko'chiriladi;
3. `npm run generate-client` (`openapi-ts`, konfiguratsiya `frontend/openapi-ts.config.ts`);
4. `npx biome format --write ./src/client`.

Backend endpoint/schema o'zgarganda shu skript qayta ishga tushiriladi; generatsiya qilingan fayllar qo'lda tahrirlanmaydi (Biome ham ularni lint'dan chiqargan). 2026-08-05 regeneratsiyasi: backend'da `GET /scans/recent` o'chirilgani uchun `ScansService`da endi faqat `recordScan`/`cancelScan` bor; terminal/tablo javoblari typed schema'larga o'tdi (`TerminalOrderCard`, `QrOrderRef`, `PrisadkaOrderState`, `TabloPostCol`) — frontend'dagi qo'lda yozilgan `TabloPost` tipi va cast'lar olib tashlandi; `OrderSurvey` esa buyurtma darajasidagi `packaging`/`delivery`/`installation` bayroqlarini oldi (anketadagi "Butun buyurtma uchun" kartasi).

Anketa/yorliq oqimidagi e'tiborli metodlar:

| Metod | Endpoint | Ishlatilishi |
|---|---|---|
| `OrdersService.saveOrderSurvey` | `PUT /api/v1/orders/{order_id}/survey` | `/anketa/:id` avtosaqlash va "Saqlash" tugmasi |
| `OrdersService.uploadRoomPhoto` | `POST /api/v1/orders/{order_id}/survey/photos` | `RoomPhotos` — form-data `room_id` + `file` |
| `OrdersService.deleteRoomPhoto` | `DELETE /api/v1/orders/{order_id}/survey/photos/{file_id}` | `RoomPhotos` o'chirish tugmasi |
| `TerminalService.renderInstanceLabel` | `GET /api/v1/terminal/labels/{instance_id}.png` | Yorliq PNG'ini brauzerda ko'rish (UI'da hozircha chaqirilmaydi — chop etish `printInstanceLabel` orqali ketadi) |

---

## 7. Fayllararo bog'lanish xulosasi

```
main.tsx ──(BASE, WITH_CREDENTIALS)──> client/core/OpenAPI.ts
main.tsx ──(401 interceptor)─────────> LoginService.refreshAccessToken (sdk.gen.ts)
routes/* ──(beforeLoad guard)────────> lib/guards.requireAuth ──> UsersService.readUserMe (+ rol-router: lib/mes.ts OPERATOR_ROLES)
routes/_layout/{admin,printers,logs,clients,employees,machines,materials,reports}.tsx ──> lib/guards.requireAccess ──> lib/mes.ts (isSuperuser/isAdmin/isManagement/isProductionStaff) <── Sidebar/AppSidebar (NAV_ITEMS)
routes/login.tsx ──> hooks/useAuth ──> LoginService.loginAccessToken / logout
routes/_layout/* ──> queries/mes.ts ──> 9 ta *Service (BridgeAgents/Clients/Employees/Machines/Materials/Orders/Posts/Tablo/Terminal, sdk.gen.ts)
routes/_layout/anketa.$orderId.tsx ──> lib/anketa.ts (kod→label) + OrdersService.saveOrderSurvey / uploadRoomPhoto / deleteRoomPhoto
routes/terminal.tsx ──> TerminalService / ScansService + Terminal/CutmapView (+ SheetSvg) + hooks/useMesWs
routes/terminal.tsx ──(TBtn "Chop etish")──> TerminalService.printInstanceLabel ──> arq/Redis ──> bridge-agent ──> GoDEX
routes/tablo.tsx, _layout/index.tsx ──> TabloService (matrix) + hooks/useMesWs
hooks/useMesWs ──(ws://.../api/v1/ws/events)──> query invalidatsiya + {online} flag
routes/_layout/admin.tsx ──> queries/users.ts ──> UsersService.readUsers
hooks/useCurrentUser ──> queries/users.ts (["currentUser"])
sdk.gen.ts ──> core/request.ts ──> core/CancelablePromise.ts, core/ApiError.ts
utils.ts (handleError ──> sonner toast) <── mutation onError'lar / queries/mes.ts crudCallbacks
lib/mes.ts (label/rang/format konstantalari) <── deyarli barcha route va komponentlar
lib/validation.ts <──> backend/app/schemas/users.py (qo'lda sinxron)
```
