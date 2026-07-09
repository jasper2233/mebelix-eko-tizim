# Frontend App — Routes, Hooks, Queries, Client va Konfiguratsiya

Bu hujjat MebeliX MES frontend ilovasining yadro qismini tavsiflaydi: build/tooling konfiguratsiyasi, ilova entry point'i, routing tuzilmasi, autentifikatsiya oqimi (auth flow), custom hook'lar, TanStack Query so'rovlari va OpenAPI'dan generatsiya qilinadigan API client.

**Texnologiyalar stack'i:**

| Qatlam | Texnologiya |
|---|---|
| Build tool | Vite + `@vitejs/plugin-react-swc` |
| UI framework | React 19 (StrictMode) |
| Routing | TanStack Router (file-based, code-generated) |
| Server state | TanStack Query (`QueryClient`, `useSuspenseQuery`) |
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
- `@hey-api/sdk` — `asClass: true` bilan servis klasslari (`{{name}}Service`, masalan `UsersService`, `LoginService`) va camelCase metodlar generatsiya qilinadi (tree-shaking'ga yo'l qo'ymaydi, lekin qulay namespace beradi);
- `@hey-api/schemas` (type: json) — JSON schema'lar (`schemas.gen.ts`).

### `frontend/components.json`
shadcn/ui CLI konfiguratsiyasi: `new-york` style, `neutral` base color, CSS variables rejimi, ikonkalar — `lucide`. Alias'lar: `@/components`, `@/components/ui`, `@/lib/utils`, `@/hooks`. Yangi UI komponent qo'shishda shadcn CLI shu faylga tayanadi.

### `frontend/biome.json`
Biome linter/formatter sozlamalari. Generatsiya qilinadigan va tashqi fayllar (`src/components/ui/**`, `src/routeTree.gen.ts`, `src/client/**`, `dist`, `public`, `src/index.css`) tekshiruvdan chiqarilgan. Format: 2 space, double quotes, `semicolons: "asNeeded"`. `noExplicitAny`, `noArrayIndexKey`, `noNonNullAssertion` qoidalari o'chirilgan. `organizeImports` yoqilgan. `npm run lint` — `biome check --write --unsafe ...`.

---

## 2. Entry point va global fayllar

### `frontend/src/main.tsx`
Ilovaning eng muhim fayli — bootstrap + global HTTP xatti-harakati:

1. **API client sozlash**: `OpenAPI.BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"`, `OpenAPI.WITH_CREDENTIALS = true`. Token JS xotirasida saqlanmaydi — autentifikatsiya to'liq HttpOnly cookie'lar orqali (`withCredentials` bilan avtomatik yuboriladi). Axios global timeout: `VITE_API_TIMEOUT_MS` (default 30 000 ms).

2. **Silent refresh interceptor**: Axios response interceptor 401 kelganda (agar so'rov `/login/refresh` yoki `/login/access-token` bo'lmasa va hali retry qilinmagan bo'lsa) `LoginService.refreshAccessToken()` ni chaqiradi — server yangi `access_token` cookie'sini o'rnatadi — so'ng asl so'rov qayta yuboriladi. Bir vaqtda kelgan parallel 401'lar `refreshSubscribers` navbatiga qo'yiladi (`isRefreshing` flag), refresh tugagach hammasi birga resolve/reject qilinadi — "concurrent request queuing" naqshi.

3. **401 fallback**: `QueryCache`/`MutationCache` `onError` handler'i (`handleApiError`) — agar interceptor'dan keyin ham `ApiError` 401 bo'lib chiqsa (masalan, boshqa tab'da logout tufayli `token_version` mos kelmasa), `queryClient.clear()` qilinadi va `window.location.href = "/login"` ga majburiy redirect.

4. **Render**: `createRouter({ routeTree })` (generatsiya qilingan `routeTree.gen.ts`dan), `QueryClientProvider` + `RouterProvider` + `Toaster` (sonner, `richColors closeButton`) StrictMode ichida render qilinadi. `declare module "@tanstack/react-router"` orqali router type-registratsiyasi qilinadi (type-safe navigatsiya).

### `frontend/src/index.css`
Tailwind v4 uslubidagi global CSS: `@import "tailwindcss"`, `tw-animate-css`, `@fontsource-variable/archivo` (asosiy shrift — Archivo Variable). `@theme inline` bloki shadcn CSS o'zgaruvchilarini Tailwind token'lariga bog'laydi. `:root`da MebeliX brend palitrasi: navy `#2F496E` (primary), gold `#F0A52F` (ring/sidebar-primary/chart-1), sidebar uchun to'q navy `#243a59` fon. `@layer base`da border/outline default'lari va `button { cursor: pointer }`.

### `frontend/src/utils.ts`
API xatolarini toast'ga aylantirish yordamchilari:
- `extractErrorMessage(err: ApiError)` — `AxiosError` bo'lsa kod bo'yicha o'zbekcha xabar (`ERR_NETWORK` → "Tarmoq xatosi — internet aloqasini tekshiring", `ECONNABORTED` → "So'rov vaqti tugadi — qayta urinib ko'ring", aks holda `err.message`); boshqa hollarda `body.detail`dan (FastAPI validation array yoki string) xabar, u ham bo'lmasa "Xatolik yuz berdi. Qayta urinib ko'ring." fallback;
- `handleError(showToast)(err)` — curried funksiya, TanStack Query `onError` uchun: `onError: handleError(showErrorToast)`;
- `getInitials(name)` — ismdan 2 harfli initsiallar (avatar uchun).

### `frontend/src/vite-env.d.ts`
Vite client type'lari + `ImportMetaEnv` interfeysi (`VITE_API_URL`) — env o'zgaruvchilarga type-safe murojaat.

### `frontend/src/lib/utils.ts`
shadcn standarti — `cn(...inputs)`: `clsx` + `tailwind-merge` kombinatsiyasi, class name'larni konfliktlarsiz birlashtirish uchun. Deyarli barcha UI komponentlar shuni ishlatadi.

### `frontend/src/lib/validation.ts`
Umumiy zod schema'lar — backend cheklovlari bilan sinxron ushlab turiladi (`backend/app/schemas/users.py` ga qarang):

| Eksport | Tavsif |
|---|---|
| `PASSWORD_MIN_LENGTH = 8` | Parol minimal uzunligi |
| `NAME_MAX_LENGTH = 30` | Ism maksimal uzunligi |
| `PHONE_PATTERN = /^\+998\d{9}$/` | E.164 O'zbekiston mobil formati (server `PHONE_PATTERN` bilan mos) |
| `passwordSchema` | Majburiy parol (parol o'rnatish/yangilash) — min 8 belgi + kuch talablari: kamida bitta kichik harf, katta harf, raqam va maxsus belgi (alohida regex'lar, o'zbekcha xabarlar; server `validate_password_strength` bilan mos) |
| `optionalPasswordSchema` | `passwordSchema`dan hosil qilingan ixtiyoriy variant (`.optional().or(z.literal(""))`) — admin edit: bo'sh = "o'zgartirmaslik" |
| `phoneSchema` | Majburiy telefon, regex bilan |
| `optionalNameSchema` | Ixtiyoriy ism: `trim`, max 30 belgi, to'ldirilgan bo'lsa min 2 belgi; bo'sh satr `undefined`ga transform qilinadi (backend `min_length=2` tufayli 422 bermasligi uchun) |

Xato xabarlari o'zbek tilida — formalar to'g'ridan-to'g'ri foydalanuvchiga ko'rsatadi.

---

## 3. Routing tuzilmasi va Auth flow

### Routing tuzilmasi (file-based)

TanStack Router `src/routes/` papkasidan quyidagi daraxtni quradi (`routeTree.gen.ts` — Vite plugin tomonidan avtomatik generatsiya qilinadi, qo'lda tahrirlanmaydi):

```
__root.tsx                 → root layout (Outlet, devtools, 404/error)
├── login.tsx              → /login          (mehmon sahifa, teskari guard)
└── _layout.tsx            → pathless layout (auth guard + sidebar shell)
    ├── _layout/index.tsx    → /             (Dashboard)
    ├── _layout/admin.tsx    → /admin        (Foydalanuvchilar boshqaruvi)
    └── _layout/settings.tsx → /settings     (Foydalanuvchi sozlamalari)
```

### `frontend/src/routes/__root.tsx`
`createRootRoute` — barcha route'larning ildizi. `HeadContent` (route'lardagi `head()` meta/title'larni renderlash), `Outlet`, hamda `TanStackRouterDevtools` va `ReactQueryDevtools`. `notFoundComponent` → `@/components/Common/NotFound`, `errorComponent` → `@/components/Common/ErrorComponent`.

### `frontend/src/routes/login.tsx`
`/login` sahifasi. **Teskari guard**: `beforeLoad`da `UsersService.readUserMe()` chaqiriladi — agar muvaffaqiyatli bo'lsa (foydalanuvchi allaqachon tizimda), `redirect({ to: "/" })` tashlanadi; xato bo'lsa sahifa ochiladi. Forma react-hook-form + zod (`formSchema`: `username` — foydalanuvchi nomi yoki telefon, `password` — faqat `min(1)` (bo'sh emasligi; kuch talablari faqat parol o'rnatishda qo'llanadi, eski/seed parollar bilan kirish saqlanadi); `satisfies z.ZodType<Body_login_access_token>` orqali generatsiya qilingan API tipiga bog'langan). Submit `useAuth().loginMutation` ga yuboriladi, UI `AuthLayout`, `LoadingButton`, `PasswordInput` komponentlaridan foydalanadi.

### `frontend/src/routes/_layout.tsx`
Pathless layout — himoyalangan sahifalar qobig'i. **Auth guard**: `beforeLoad`da `UsersService.readUserMe()` chaqiriladi — faqat `ApiError.status === 401` bo'lsa `redirect({ to: "/login" })`; boshqa xatolar (tarmoq uzilishi, 5xx) qayta throw qilinadi va `errorComponent`da ko'rinadi (sessiya o'ldirilmaydi). Layout `SidebarProvider` + `AppSidebar` (`@/components/Sidebar/AppSidebar`) + `SidebarInset`dan iborat; fon suvbelgisi sifatida navy logo (opacity 0.06), mobil ko'rinishda (md dan kichik) `SidebarTrigger`li header ko'rsatiladi. `sectionTitles` map'i pathname bo'yicha mobil header sarlavhasini beradi (`/` → "Boshqaruv paneli", `/admin` → "Foydalanuvchilar", `/settings` → "Sozlamalar").

### `frontend/src/routes/_layout/index.tsx`
`/` — Dashboard. Hozircha minimal: `useCurrentUser()` orqali joriy foydalanuvchini olib, "Salom, {name || phone}" salomlashuvi. `head()` orqali sahifa title'i o'rnatiladi.

### `frontend/src/routes/_layout/admin.tsx`
`/admin` — foydalanuvchilar boshqaruvi. **Superuser guard**: `beforeLoad`da `readUserMe()` natijasi `is_superuser` bo'lmasa `redirect({ to: "/" })` (backend ham ro'yxatni faqat superuser'ga beradi). `useSuspenseQuery(getUsersQueryOptions())` bilan ro'yxat olinadi (`Suspense` fallback — `PendingUsers` skeleton). Har bir `UserRead`ga `isCurrentUser` flag'i qo'shilib (`useCurrentUser` bilan solishtirish) `DataTable`ga (`@/components/Common/DataTable`, ustunlar `@/components/Admin/columns`) uzatiladi. Yuqorida `AddUser` dialog tugmasi.

### `frontend/src/routes/_layout/settings.tsx`
`/settings` — sozlamalar, Tabs asosida: "Profilim" (`UserInformation`), "Parol" (`ChangePassword`), "Xavfli zona" (`DeleteAccount`). Superuser uchun "Xavfli zona" yashiriladi (`tabsConfig.slice(0, 2)`) — superuser o'z hisobini o'chira olmaydi. `currentUser` hali yuklanmagan bo'lsa `null` qaytaradi.

### Auth flow (login → cookie token → guard → silent refresh)

1. **Login**: `/login` formasida `useAuth().loginMutation` → `LoginService.loginAccessToken({ formData })` (OAuth2 form-data: username/password). Server javobida `access_token` va `refresh_token` **HttpOnly cookie** sifatida o'rnatiladi — frontend token'ni hech qayerda saqlamaydi (`localStorage` yo'q). Muvaffaqiyatda `navigate({ to: "/" })`.
2. **Guard**: har bir himoyalangan sahifaga kirishda `_layout.tsx` `beforeLoad`i `readUserMe()` chaqiradi — cookie yaroqli bo'lsa o'tadi, 401 bo'lsa `/login` ga redirect (boshqa xatolar `errorComponent`ga chiqadi). `/admin` qo'shimcha superuser tekshiruvidan o'tkazadi. `/login` esa teskari tekshiradi: sessiya bor bo'lsa `/` ga qaytaradi.
3. **So'rovlar**: barcha API chaqiriqlar `withCredentials: true` bilan ketadi (`main.tsx`da `OpenAPI.WITH_CREDENTIALS = true`), cookie avtomatik biriktiriladi.
4. **Silent refresh**: access token muddati tugab 401 kelsa, `main.tsx`dagi Axios interceptor `LoginService.refreshAccessToken()` orqali cookie'ni yangilab, asl so'rovni bir marta qayta yuboradi; parallel so'rovlar navbatda kutadi.
5. **Fallback logout**: refresh ham 401 bersa (yoki `token_version` mismatch), `QueryCache`/`MutationCache` `onError`i cache'ni tozalab `/login` ga yo'naltiradi.
6. **Logout**: `useAuth().logout` → `LoginService.logout()` (server cookie'larni o'chiradi), `onSettled`da `queryClient.clear()` + `/login` ga navigate — server xato bersa ham lokal sessiya tozalanadi.

---

## 4. Hooks

### `frontend/src/hooks/useAuth.ts`
Autentifikatsiya mutation'lari:
- `loginMutation` — `LoginService.loginAccessToken({ formData })`; success'da `/` ga navigate, error'da `handleError(showErrorToast)`;
- `logout()` — `logoutMutation.mutate()`; `onSettled`da har doim `queryClient.clear()` + `/login`.

`frontend/src/routes/login.tsx` va sidebar'dagi user menyusi tomonidan ishlatiladi.

### `frontend/src/hooks/useCurrentUser.ts`
Joriy foydalanuvchi — `useQuery(getCurrentUserQueryOptions())`, `retry: false` (401'da qayta urinmaslik). `queryKey: ["currentUser"]` — Dashboard, admin jadvali (`isCurrentUser`), settings va sidebar shu key'dan ulanadi. Guard'lar (`beforeLoad`) esa cache'siz to'g'ridan-to'g'ri `readUserMe()` chaqiradi.

### `frontend/src/hooks/useCustomToast.ts`
`sonner` toast wrapper'i: `showSuccessToast(description)` ("Muvaffaqiyat!") va `showErrorToast(description)` ("Xatolik yuz berdi!"). `handleError` (`frontend/src/utils.ts`) bilan birga mutation error handler'larida ishlatiladi.

### `frontend/src/hooks/useMobile.ts`
`useIsMobile()` — `matchMedia("(max-width: 767px)")` (breakpoint 768) asosida responsive flag. shadcn `sidebar` komponenti mobil/desktop rejimni shu bilan aniqlaydi.

---

## 5. Queries

### `frontend/src/queries/users.ts`
TanStack Query options factory'lari — queryKey'lar bir joyda markazlashtirilgan:

```ts
getUsersQueryOptions()        // queryKey: ["users"],       readUsers — barcha sahifalar yig'iladi
getCurrentUserQueryOptions()  // queryKey: ["currentUser"], readUserMe
```

`getUsersQueryOptions` `queryFn`i sahifalab yig'adi: `PAGE_SIZE = 100` (backend `MAX_PAGE_SIZE`) bilan `readUsers({ skip, limit })` loop'da `count`ga yetguncha chaqiriladi — 100 dan ortiq foydalanuvchi ham to'liq ko'rinadi (jadval client-side; foydalanuvchilar minglab bo'lsa server-side paginatsiyaga o'tish kerak bo'ladi).

`/admin` sahifasi `useSuspenseQuery` bilan, `useCurrentUser` oddiy `useQuery` bilan ishlatadi. Foydalanuvchi CRUD mutation'lari (Admin komponentlarida) invalidatsiya uchun shu key'larga tayanadi.

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
| `frontend/src/client/sdk.gen.ts` | Servis klasslari: `HealthService`, `LoginService`, `UsersService` — har metod `CancelablePromise` qaytaradi (`ItemsService`/`TasksService` backend demo modullari bilan birga olib tashlangan) | `@hey-api/openapi-ts` |
| `frontend/src/client/types.gen.ts` | Request/response TypeScript tiplari (`UserRead`, `Body_login_access_token`, ...) | `@hey-api/openapi-ts` |
| `frontend/src/client/schemas.gen.ts` | JSON schema'lar | `@hey-api/openapi-ts` |

API client'ni yangilash — `scripts/generate-client.sh` (repo root'dan):
1. `backend/`da `uv run python -c "...app.openapi()..."` bilan `openapi.json` eksport qilinadi;
2. fayl `frontend/`ga ko'chiriladi;
3. `npm run generate-client` (`openapi-ts`, konfiguratsiya `frontend/openapi-ts.config.ts`);
4. `npx biome format --write ./src/client`.

Backend endpoint/schema o'zgarganda shu skript qayta ishga tushiriladi; generatsiya qilingan fayllar qo'lda tahrirlanmaydi (Biome ham ularni lint'dan chiqargan).

---

## 7. Fayllararo bog'lanish xulosasi

```
main.tsx ──(BASE, WITH_CREDENTIALS)──> client/core/OpenAPI.ts
main.tsx ──(401 interceptor)─────────> LoginService.refreshAccessToken (sdk.gen.ts)
routes/* ──(beforeLoad guard)────────> UsersService.readUserMe
routes/login.tsx ──> hooks/useAuth ──> LoginService.loginAccessToken / logout
routes/_layout/admin.tsx ──> queries/users.ts ──> UsersService.readUsers
hooks/useCurrentUser ──> queries/users.ts (["currentUser"])
sdk.gen.ts ──> core/request.ts ──> core/CancelablePromise.ts, core/ApiError.ts
utils.ts (handleError) <── hooks/useCustomToast <── mutation onError'lar
lib/validation.ts <──> backend/app/schemas/users.py (qo'lda sinxron)
```
