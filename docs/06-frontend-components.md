# Frontend Components (Admin, Clients, Common, Orders, Anketa, Pending, Sidebar, Terminal, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini va anketa sahifasi ichidagi komponentlarni (`routes/_layout/anketa.$orderId.tsx`) qamrab oladi. Stack: React + TypeScript, TanStack Router/Query, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService, ClientsService, OrdersService, TerminalService va model turlari) orqali gaplashadi; umumiy query'lar `@/queries/mes` dagi `queryOptions` fabrikalarida (getClients/getMachines/getPosts/getOrderMatrixQueryOptions va h.k.), domen konstantalari `@/lib/mes` da (ROLE_LABELS, PRIORITY_LABELS, PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES — prioritet ranglari yagona manbadan, POST_COLORS, ORDER_STATUS_LABELS/COLORS, formatSize), buyurtma anketasi variantlari `@/lib/anketa` da; toast xabarlari `useCustomToast` hooki, xatoliklar `handleError` utiliti orqali ko'rsatiladi.

Umumiy naqsh (pattern): **forma → zod schema → react-hook-form → useMutation → @/client servisi → toast + query invalidation**. Barcha ko'rinadigan UI matnlari o'zbek tilida; shadcn primitivlaridan qolgan ekran o'quvchi uchun yashirin matnlar hozircha inglizcha (`sidebar.tsx` — "Collapse/Open Sidebar", mobil sidebar sr-only sarlavhasi "Sidebar"/"Displays the mobile sidebar."; `dialog.tsx`/`sheet.tsx` — sr-only "Close"; `password-input.tsx` — aria-label "Show/Hide password").

---

## Admin komponentlari — `frontend/src/components/Admin/`

Admin panel (`/admin` route) uchun foydalanuvchilarni CRUD boshqarish komponentlari. Jadvalning o'zi route faylida — `routes/_layout/admin.tsx` dagi lokal `UserRow` oddiy `ui/table` qatorini chizadi (clients.tsx/employees.tsx bilan bir xil naqsh); sahifalash yo'q, `getUsersQueryOptions` barcha sahifalarni bitta ro'yxatga yig'adi.

### `frontend/src/components/Admin/AddUser.tsx`

**Maqsadi:** yangi foydalanuvchi yaratish dialogi (o'zining trigger tugmasi bilan).

- `formSchema` — zod: `phone` (`phoneSchema`), `name` (`optionalNameSchema`), `password` (`passwordSchema`), `confirm_password`, `role` (`z.enum(Object.keys(ROLE_LABELS))` — 13 rol yagona manbadan, generatsiya qilingan `UserRole` tipida), `machine_id` (ixtiyoriy), `is_superuser`, `is_active`; ikkita `.refine()`: terminal/tablo roliga stanok majburiy ("Terminal/TABLO uchun stanok tanlang") va parollar mosligi ("Parollar mos emas").
- Default qiymatlar: `role: "manager"`, `is_superuser: false`, `is_active: true` — yangi foydalanuvchi darhol tizimga kira oladi.
- Rol `Select` `ROLE_LABELS` (`@/lib/mes`) dan to'ldiriladi; rol terminal yoki tablo bo'lsa shartli "Stanok" `Select` chiqadi (`getMachinesQueryOptions()` — `@/queries/mes`); submitda `machine_id` `Number` ga o'giriladi (bo'sh bo'lsa `null`).
- Mutation: `UsersService.createUser({ requestBody })`; muvaffaqiyatda toast, forma reset, dialog yopiladi; `onSettled` da `["users"]` query invalidatsiya qilinadi.
- Forma `mode: "onBlur"` rejimida validatsiya qiladi; trigger — `<Plus /> Foydalanuvchi qo'shish` tugmasi.
- Submit tugmasi `LoadingButton` (`loading={mutation.isPending}`).

**Bog'lanishlar:** `@/lib/validation` (schema'lar), `@/lib/mes` (ROLE_LABELS), `@/queries/mes` (getMachinesQueryOptions), `@/hooks/useCustomToast`, `@/utils` (`handleError`), ui: `dialog`, `form`, `input`, `select`, `checkbox`, `button`, `loading-button`. Admin route sahifasidan chaqiriladi.

### `frontend/src/components/Admin/DeleteUser.tsx`

**Maqsadi:** foydalanuvchini o'chirish — dropdown menu bandi + tasdiqlash dialogi.

- Props: `{ id: string; onSuccess: () => void }`.
- Mutation: `UsersService.deleteUser({ userId: Number.parseInt(id, 10) })`; muvaffaqiyatda toast, dialog yopiladi, `onSuccess()` (ota-menuni yopish); `onSettled` da **barcha** querylar invalidatsiya qilinadi (`invalidateQueries()` argumentsiz).
- `DropdownMenuItem variant="destructive"` da `onSelect={(e) => e.preventDefault()}` — menyu yopilib dialog ochilishini ta'minlaydi.
- Dialog UI to'liq `Common/ConfirmDialog` orqali (`destructive`, `confirmText="O'chirish"`); description matni soft-delete'ga mos — foydalanuvchi **o'chirilgan deb belgilanadi** va tizimga kira olmaydi (ma'lumotlar butunlay o'chirilmaydi).

### `frontend/src/components/Admin/EditUser.tsx`

**Maqsadi:** mavjud foydalanuvchini tahrirlash dialogi (dropdown menu bandi ichidan ochiladi).

- Props: `{ user: UserRead; onSuccess: () => void }`.
- `formSchema` `AddUser` dan farqi: `password` — `optionalPasswordSchema` (bo'sh qoldirilsa parol o'zgarmaydi), refine faqat parol kiritilganda mosligini tekshiradi.
- `onSubmit` da `UserAdminUpdate` payload quriladi; `password` faqat kiritilgan bo'lsa qo'shiladi:

```ts
const payload: UserAdminUpdate = { phone, name, is_superuser, is_active }
if (data.password) payload.password = data.password
```

- Mutation: `UsersService.updateUser({ userId: Number.parseInt(user.id, 10), requestBody })`; `["users"]` invalidatsiyasi.
- Forma default qiymatlari `user` obyektidan olinadi.

### `frontend/src/components/Admin/UserActionsMenu.tsx`

**Maqsadi:** jadval qatoridagi "..." (EllipsisVertical) amallar menyusi.

- Props: `{ user: UserRead }`. `useCurrentUser` orqali joriy foydalanuvchi aniqlanadi; **agar qator joriy foydalanuvchining o'zi bo'lsa `null` qaytaradi** (o'zini tahrirlash/o'chirish mumkin emas — buning uchun UserSettings bor).
- Menyu ichida `EditUser` va `DeleteUser`; ikkalasiga `onSuccess={() => setOpen(false)}` uzatiladi (muvaffaqiyatdan keyin dropdown yopilsin).

---

## Clients komponentlari — `frontend/src/components/Clients/`

### `frontend/src/components/Clients/AddClient.tsx`

**Maqsadi:** yangi mijoz yaratish dialogi (TZ 4.6) — mustaqil ham, boshqa forma ichidan ham ishlaydi.

- zod: `full_name` (min 2 belgi), `phone`/`phone_alt` (`optionalFormattedPhoneSchema`), `address`, `notes`; telefon inputlari yozish paytida `formatUzPhone` bilan "+998 90 123-45-67" ko'rinishida maskalanadi (placeholder esa "+998 90 123 45 67"); submitda `optionalFormattedPhoneSchema` probel/chiziqchalarni olib tashlab kanonik `+998901234567` ga o'tkazadi.
- Props: `trigger?` (default "+ Yangi mijoz" tugmasi o'rniga istalgan React node) va `onCreated?(client)` — `Clients/ClientCombobox` popover footeri shulardan foydalanib mijozni inline yaratadi va combobox'da avtomatik tanlaydi.
- Mutation: `ClientsService.createClient`; muvaffaqiyatda toast, reset, dialog yopilib `onCreated?.(client)` chaqiriladi; `["clients"]` invalidatsiyasi.

### `frontend/src/components/Clients/ClientCombobox.tsx`

**Maqsadi:** server-qidiruvli mijoz tanlagich — ro'yxat backend `?search=` bilan filtrlanadi, mijozlar soni mingga yetsa ham ishlaydi.

- Qidiruv 300ms debounce bilan `getClientsQueryOptions(search)` ga uzatiladi (`enabled: open`); ArrowUp/ArrowDown/Enter klaviatura navigatsiyasi.
- Dialog ichida ishlashi uchun `Popover` `modal` rejimda; `onOpenAutoFocus` da Radix avto-fokusi bekor qilinib, fokus qidiruv inputiga beriladi.
- Props: `value`/`onChange`, `initialLabel?` (tanlangan mijoz nomi tashqaridan kelganda, masalan EditOrder), `disabled?`.
- Popover footerida inline `AddClient` ("Yangi mijoz qo'shish" ghost tugma trigger, `onCreated` yangi mijozni avtomatik tanlaydi). `Orders/AddOrder` va `Orders/EditOrder` da ishlatiladi.

---

## Common komponentlari — `frontend/src/components/Common/`

### `frontend/src/components/Common/AuthLayout.tsx`

**Maqsadi:** login sahifasi uchun ikki ustunli layout.

- Chap ustun (faqat `lg:` da): solid `bg-(--brand-navy-deep)` fon, ustida animatsiyali `CutmapArt` SVG — stilize kesish xaritasi (2440×1220 plita, GibSaw uslubi), chiziqlar `mx-draw`/`mx-fade` animatsiyalari bilan `--brand-gold` rangda chizilib paydo bo'ladi; `logo-gold.png` tepada (`self-start`), pastda tagline bloki ("Ishlab chiqarishni boshqarish tizimi" + "Kesishdan yetkazishgacha — har bir detal nazorat ostida.").
- O'ng ustun: markazlangan `max-w-md` forma konteyneri (`children`), pastda `Footer`; mobil ko'rinishda navy watermark (`icon-navy.png`).
- Hozircha yagona auth route — `routes/login.tsx` shu layout bilan o'raladi (signup route yo'q).

### `frontend/src/components/Common/ConfirmDialog.tsx`

**Maqsadi:** umumiy "Ishonchingiz komilmi?" (controlled) dialog. Trigger va `open` holati chaqiruvchiga tegishli — trigger tugma, menyu bandi yoki boshqa narsa bo'lishi mumkin; komponent faqat modal tanasini chizadi.

- Props: `open`, `onOpenChange`, `title`, `description?`, `confirmText?` (default "Tasdiqlash"), `cancelText?` (default "Bekor qilish"), `destructive?`, `loading?`, `onConfirm`.
- Tasdiqlash tugmasi `LoadingButton` (`variant={destructive ? "destructive" : "default"}`); ikkala tugma ham `h-11 px-5` — 44px minimal barmoq o'lchami terminal (touch) va admin uchun bir xil.

**Foydalanuvchilari:** `Admin/DeleteUser.tsx`, `UserSettings/DeleteAccount.tsx`, `routes/_layout/orders/$orderId.tsx`, `routes/_layout/anketa.$orderId.tsx` (xona o'chirish), `routes/_layout/employees.tsx`, `routes/_layout/printers.tsx` (agentga yangi kod berish va agentni bekor qilish — ikkita dialog), `routes/terminal.tsx`.

### `frontend/src/components/Common/ErrorComponent.tsx`

**Maqsadi:** routerning global xato ekrani — `ErrorScreen` ga delegatsiya (`code="Xato"`, "Xatolik yuz berdi..." matni).

### `frontend/src/components/Common/ErrorScreen.tsx`

**Maqsadi:** xato/404 ekranlarining umumiy maketi (`code` + "Voy!" + `message` + "Bosh sahifaga" tugmasi, `Link to="/"`) — ikki nusxa layout drift bermasin. `ErrorComponent` va `NotFound` shundan quriladi.

### `frontend/src/components/Common/Footer.tsx`

**Maqsadi:** oddiy footer — `MebeliX MES · {joriy yil}`. `AuthLayout` ichida ishlatiladi.

### `frontend/src/components/Common/NotFound.tsx`

**Maqsadi:** 404 ekrani — `ErrorScreen` ga delegatsiya ("404 / Voy!" + "Siz qidirayotgan sahifa topilmadi." matni). Router'ning `notFoundComponent` sifatida ulanadi.

### `frontend/src/components/Common/PageHeader.tsx`

**Maqsadi:** sahifa sarlavhasi — `title`, ixtiyoriy `description` va o'ng tomonda `actions` slot. Deyarli barcha `_layout` sahifalarida ishlatiladi (dashboard, orders ro'yxati va sahifasi, clients, employees, machines, materials, reports, transactions, printers, anketa — 11 ta sahifa); istisno — `admin.tsx` va `settings.tsx` sarlavhani o'zi qo'lda (`<h1>`) chizadi, `cutmap.$orderId.tsx` da esa sarlavha umuman yo'q (to'liq ekran).

### `frontend/src/components/Common/PostBadge.tsx`

**Maqsadi:** bosqich (post) kodi chipi (ARRA, KROMKA, ...) — `POST_COLORS` asosida, matn post rangining to'qroq variantida (`color-mix ... 78%, black` — WCAG AA kontrasti, sof rang tint fonda o'tmasdi). Avval `employees.tsx` va `machines.tsx` da qo'lda takrorlangan edi.

### `frontend/src/components/Common/QueryError.tsx`

**Maqsadi:** so'rov yiqilganda ko'rsatiladigan `role="alert"` bloki — xato matni + ixtiyoriy "Qayta urinish" tugmasi (`onRetry`). Busiz sahifalar xato holatida abadiy skeletonda qotib qolardi.

### `frontend/src/components/Common/SectionTitle.tsx`

**Maqsadi:** sahifa ichidagi bo'lim sarlavhasi (`h2`, uppercase muted) — ierarxiya: `PageHeader` (h1) > `SectionTitle` (h2) > panel sarlavhalari (h3); avval bir daraja to'rt xil yozilgan edi.

### `frontend/src/components/Common/StagePipeline.tsx`

**Maqsadi:** 6 bosqichli ishlab chiqarish pipeline'i (TZ 4.4) — ulangan progress kataklar zanjiri, loyihaning "signature" vizual elementi.

- Props: yagona `stages: StageCell[]` (`{ code, done, total }`); har katak (`h-6 w-12`) `POST_COLORS[code]` rangida (`color-mix` fon + foizli progress chizig'i), ichida `done/total`, tugallanganda "✓"; kataklar orasida ulovchi chiziqcha, `title` da `KOD: done/total (N%)`.
- Dashboard'da (`routes/_layout/index.tsx`) ishlatiladi; xuddi shu vizual grammatika `Orders/OrderMatrix` va TABLO ekranida takrorlanadi.

### `frontend/src/components/Common/StatusBadge.tsx`

**Maqsadi:** buyurtma holati pill'i — `ORDER_STATUS_LABELS`/`ORDER_STATUS_COLORS` (`@/lib/mes`) asosida rangli nuqta + matn. Dashboard, buyurtmalar ro'yxati/sahifasi va hisobotlarda ishlatiladi.

---

## Orders komponentlari — `frontend/src/components/Orders/`

Buyurtma sahifalari (`/orders`, `/orders/$orderId`) uchun dialog va jadval komponentlari.

### `frontend/src/components/Orders/orderForm.tsx`

**Maqsadi:** AddOrder va EditOrder uchun umumiy forma manbasi — ikkala dialog bitta backend kontraktiga tegadi, shuning uchun schema, payload va maydonlar bir joyda.

- Eksportlar: `formSchema` (zod: `client_id` majburiy, `deadline?`, `priority` enum low/medium/high/urgent, `amount` majburiy, `advance_payment?`, `notes?`; `.refine()` — boshlang'ich to'lov umumiy narxdan oshmasligi kerak), `FormValues`, `toRequestBody(data)` va `OrderFields({ control })`.
- `toRequestBody` — create va update bir xil payload kutadi: `client_id` `Number` ga, pul maydonlaridan probellar olib tashlanadi, bo'shlari `null`.
- `OrderFields` — ikkala dialogdagi bir xil maydonlar: topshirish sanasi (`ui/date-picker` DatePicker), prioritet `Select` (`PRIORITY_LABELS` yorliqlari, bandlarida `PRIORITY_DOT_CLASSES` rangli nuqtalar), umumiy narx va boshlang'ich to'lov (`formatMoneyInput` bilan ming ajratkichli). Mijoz va izoh maydonlari dialoglarda qoladi — ular ikkalasida farq qiladi.

### `frontend/src/components/Orders/AddOrder.tsx`

**Maqsadi:** yangi buyurtma dialogi ("+ Yangi buyurtma") — raqamni tizim beradi (B-YYYY-NNN), fayl keyin texnolog tomonidan yuklanadi.

- Forma `orderForm.tsx` dan: `formSchema` + `OrderFields` + `toRequestBody`; default `priority: "medium"`, qolgan maydonlar bo'sh.
- Mijoz maydoni — `Clients/ClientCombobox` (server-side qidiruvli; yangi mijoz combobox popover footeridagi inline `AddClient` orqali qo'shiladi); izoh — erkin `Input` ("Maxsus talablar (masalan, qora kromka)").
- Mutation: `OrdersService.createOrder`; muvaffaqiyatda toast va yangi buyurtma sahifasiga `navigate`.

### `frontend/src/components/Orders/EditOrder.tsx`

**Maqsadi:** buyurtmani tahrirlash dialogi (manager) — AddOrder bilan umumiy `orderForm.tsx` (schema, maydonlar, payload), qiymatlar `values:` orqali `order` dan olinadi (pul maydonlari `formatMoneyInput` bilan).

- Mijoz maydoni — `ClientCombobox` (`initialLabel={order.client_name}`, `disabled={!isDraft}`) — DRAFT dan keyin mijoz almashtirilmaydi ("faqat qoralamada almashtiriladi"; backend ham shu qoidani ushlaydi).
- Mutation: `OrdersService.updateOrder`; muvaffaqiyatda `onSaved()` callback.

### `frontend/src/components/Orders/MachineAssign.tsx`

**Maqsadi:** stanok tanlovi paneli (TZ 6.4.1) — `requires_assignment_choice` bo'lgan postlar uchun aniq manager tanlovi.

- Har post uchun `POST_COLORS` rangli sarlavha + faol stanoklar selecti (`getPostsQueryOptions` + `getMachinesQueryOptions`); `OrdersService.assignOrderMachines` ga saqlanadi; tanlov talab qiluvchi post bo'lmasa `null` qaytaradi.

### `frontend/src/components/Orders/OrderMatrix.tsx`

**Maqsadi:** texnolog matritsasi (TZ 6.3.3) — qatorlar: detallar, ustunlar: 6 post.

- O'qish rejimida har katak `total_done/total_required` progress (`POST_COLORS`, tugallanganda "✓"), o'chirilgan bosqich "—"; `editable` bo'lsa "Marshrutni tahrirlash" rejimi: bosqich checkboxlari (ARRA majburiy — TZ 5.4.1, checkbox locked) + izoh inputlari, `OrdersService.editOrderMatrix` ga batch saqlanadi.
- Ma'lumot: `getOrderMatrixQueryOptions(orderId)`; o'lchamlar `formatSize` (`@/lib/mes`) bilan.

---

## Anketa komponentlari — `frontend/src/routes/_layout/anketa.$orderId.tsx`

Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i) komponentlari `components/` da emas, sahifa faylining o'zida (~1340 qator) — faqat shu sahifada ishlatiladi. Variantlar katalogi alohida: `frontend/src/lib/anketa.ts`.

**Ma'lumot oqimi:** `Order.survey` (JSONB) — `OrderSurvey { version, measured_at, measured_by, rooms[] }`; xona `SurveyRoom` (materiallar, o'lchamlar, `walls: SurveyWall[]`, `modules: SurveyModule[]`). Saqlash `OrdersService.saveOrderSurvey` (`PUT /orders/{id}/survey`); xona rasmlari JSON'da emas, `OrderFile(kind=DOCUMENT, meta.room_id)` da (`OrdersService.uploadRoomPhoto` / `deleteRoomPhoto`) — shuning uchun avtosaqlash bilan aralashmaydi.

**Sahifa xulq-atvori (`AnketaPage`):**

- Server ma'lumoti **faqat bir marta** state'ga yuklanadi (`loaded` ref) — aks holda saqlashdan keyingi refetch menejer yozayotgan matn ustiga tushardi.
- Avtosaqlash: har tahrirdan 1.5s keyin (`dirty` bo'lsa va `canEdit` bo'lsa) `save.mutate`; `beforeunload` da ogohlantirish, unmount'da fire-and-forget `saveOrderSurvey`.
- `canEdit = is_superuser || role === "admin" | "manager"` — faqat ular formani ko'radi; qolganlar (texnolog/direktor) `RoomSummary` jamlanmasini ko'radi.
- Xonalar tab tugmalari (`r.name || "Xona N"`), "Xona qo'shish", xona o'chirish `ConfirmDialog` orqali (rasmlar ham o'chadi — backend `save_order_survey` da yetim rasmlarni tozalaydi).
- Pastda sticky saqlash paneli: holat matni ("Saqlanmoqda..." / "O'zgarishlar avtomatik saqlanadi" / "Saqlandi HH:MM" / "Hammasi saqlangan") + `LoadingButton`. Manfiy margin (`-mx-6 md:-mx-8`) bilan main padding'i qoplanadi; suvbelgi va dekor konteyner olib tashlangach `routes/_layout.tsx` da `overflow-hidden` umuman yo'q — `sticky` to'siqsiz ishlaydi.

**Bo'limlar (qog'oz anketa raqamlari bilan):** 1 Xona va rasmlar · 2 Qanday mebel kerak · 3 Xonadagi shakli va o'lchamlari · 4 Korpus materiali · 5 Fasad materiali · 6 Furnitura va qo'shimcha xizmat · 7 Qo'shimcha izoh · 8 O'lchov varag'i (`<details>` ichida yopiq — zamerdan keyin usta to'ldiradi: o'lchov sanasi/ustasi, A–E devor uzunlik/balandligi, modullar jadvali, umumiy pm/balandlik).

**Sahifa ichidagi komponentlar:**

| Komponent | Vazifasi |
|---|---|
| `RoomPhotos` | Xona rasmlari: butun panel drag&drop zona, `MAX_PHOTOS = 6`, `MAX_PHOTO_MB = 5`, MIME/hajm/soni klientda tekshiriladi; rasm bosilsa `Dialog` da katta ko'rinish + "Asl hajmda yangi oynada ochish"; rasmlar `<img crossOrigin="use-credentials">` bilan `/api/v1/orders/{id}/files/{fileId}` dan olinadi |
| `RoomSummary` | Texnolog/direktor ko'rinishi — tartib qog'ozning teskarisi: avval modullar jadvali va o'lchamlar, keyin material, so'ng mebel turi/xizmatlar (texnolog GibLab'da shu tartibda ishlaydi) |
| `Facts` | `dl` jadvali; bo'sh qiymatlar tashlab yuboriladi, hech nima yo'q bo'lsa "To'ldirilmagan." |
| `Section` | `n?` raqami + `title` + `hint?` bo'lgan karta (raqam qog'oz anketa bilan bir xil — menejer telefonda "3-bo'limga o'tamiz" deb ayta oladi) |
| `Field` / `Num` | Label + child; `Num` — `Field` + `NumInput` |
| `NumInput` | Raqamli maydon: yozilayotgan xom matn `raw` state'da saqlanadi (aks holda "3," yozilganda maydon o'zini tozalab qo'yardi), blur'da normallashadi; vergul o'nlik ajratgich sifatida qabul qilinadi (`numOrNull`); `integer` bo'lsa `Math.trunc` |
| `CheckGrid` | Ko'p tanlovli katakchalar (butun katak bosiladi — sensorli ekran) |
| `Choice` | Bitta tanlov, qayta bosilsa bekor qilinadi (radio'da imkonsiz); `h-9` — `Input` bilan bir xil balandlik |
| `ShapeChoice` + `SHAPE_ART` | Planirovka siluetlari (I / L / П / orolchali) — inline SVG to'rtburchaklar; mijoz "П-shakl (U)" jargonini emas, shaklni taniydi |

### `frontend/src/lib/anketa.ts`

Anketa variantlari katalogi — bazaga faqat `value` kodlari yoziladi, matnlar shu yerda (matn o'zgarsa tarix buzilmaydi).

- `Option = { value, label }`; ro'yxatlar: `FURNITURE_TYPES` (10), `LAYOUT_SHAPES` (4), `CORPUS_MATERIALS` (5), `CORPUS_THICKNESS` (16/18/boshqa), `FACADE_MATERIALS` (7), `COUNTERTOPS` (4), `HARDWARE_LEVELS` (oddiy/medium/premium), `EXTRA_SERVICES` (6), `WALL_LETTERS` (`A`–`E`).
- `labelOf(options, value)` va `labelsOf(options, values)` — kodni/kodlar ro'yxatini o'qiladigan matnga (`RoomSummary` ishlatadi).

---

## Pending — `frontend/src/components/Pending/PendingUsers.tsx`

**Maqsadi:** foydalanuvchilar jadvali yuklanayotganda ko'rsatiladigan skeleton holati.

- Haqiqiy jadval bilan bir xil sarlavhalar (To'liq ism, Telefon, Rol, Holat, sr-only Amallar) va 5 ta qator; har katakda mos o'lchamli `Skeleton` (badge uchun `rounded-full`, holat nuqtasi uchun `size-2` va h.k.) — layout shift bo'lmasligi uchun `routes/_layout/admin.tsx` dagi `UserRow` tuzilishini aks ettiradi.
- Admin sahifasida `useSuspenseQuery` ishlatilgani uchun `<Suspense fallback={<PendingUsers />}>` sifatida render qilinadi (`isLoading` tekshiruvi emas).

---

## Sidebar komponentlari — `frontend/src/components/Sidebar/`

Claude.com uslubidagi yon panel: trigger sidebar ichida, alohida app header/footer yo'q (qarang: commit tarixi).

### `frontend/src/components/Sidebar/AppSidebar.tsx`

**Maqsadi:** ilovaning asosiy yon paneli — brend, navigatsiya va foydalanuvchi menyusini yig'adi.

- `navItems(user)` funksiyasi (TZ 3.7 rollar-modullar matritsasi) 12 tagacha punkt quradi. Huquq predikatlari `@/lib/mes` dan — `isAdmin` / `isAdminOrDirector` / `isSuperuser`; **route guard'lar ham AYNAN shularni ishlatadi** (`lib/guards.requireAccess`), ya'ni menyuda ko'rinadigan sahifa albatta ochiladi. Bandlar: Boshqaruv paneli `/` va LIVE Tablo `/tablo` — hammaga; Buyurtmalar `/orders`, Stanoklar `/machines`, Materiallar `/materials` — admin/manager/texnolog/director; Mijozlar `/clients`, Hodimlar `/employees`, Hisobotlar `/reports` — admin/manager/director; Tranzaksiyalar `/transactions` — `isAdminOrDirector`; Printer agentlar `/printers` (`Printer` ikonkasi) va Loglar `/logs` (`ScrollText` ikonkasi) — `isAdmin` (superuser yoki `role === "admin"`); Foydalanuvchilar `/admin` — **faqat `isSuperuser`**, chunki ro'yxat barcha telefon raqamlarni ochadi va backend ham uni faqat superuser'ga beradi. **Rolga qarab navigatsiya**.
- Buyurtmalar bandida jonli badge — faol buyurtmalar soni (delivered/cancelled dan boshqa statuslar yig'indisi): `getOrderStatusCountsQueryOptions()` reyestr sahifasi bilan AYNAN bitta query key'da, TanStack dedupe qiladi — sidebar qo'shimcha so'rov qo'shmaydi; `enabled` faqat `/orders` bandi ko'rinadigan rollarda.
- `<Sidebar collapsible="icon">`: yig'ilganda faqat ikonkalar qoladi. Header'da `Link to="/"` (logo `icon-gold.png` + "MebeliX" yozuvi, yig'ilganda `group-data-[collapsible=icon]:hidden` bilan yashiriladi) va `SidebarTrigger` (yig'ilgan railda yolg'iz qoladi).
- `SidebarContent` → `Main items={items}`; `SidebarFooter` → `User user={currentUser}`.

**Bog'lanishlar:** `@/hooks/useCurrentUser`, `ui/sidebar.tsx`, `Sidebar/Main.tsx`, `Sidebar/User.tsx`. Layout route ichida `SidebarProvider` + `SidebarInset` bilan ishlatiladi.

### `frontend/src/components/Sidebar/Main.tsx`

**Maqsadi:** navigatsiya menyusi ro'yxati.

- Eksport: `type Item = { icon: LucideIcon; title: string; path: string; badge?: number }` va `Main({ items })`; `badge` bo'lsa (0 emas) band yonida `SidebarMenuBadge` chiqadi.
- `useRouterState()` dan `currentPath` olinib `isActive = currentPath === item.path` aniqlanadi; aktiv bandda chapdan 3px oltin chiziq: `data-[active=true]:shadow-[inset_3px_0_0_0_var(--sidebar-primary)]`.
- Har band `SidebarMenuButton tooltip={item.title} asChild` ichida `RouterLink`; mobil rejimda bosilganda `setOpenMobile(false)` bilan panel yopiladi.

### `frontend/src/components/Sidebar/User.tsx`

**Maqsadi:** sidebar footeridagi foydalanuvchi kartasi va dropdown menyusi.

- Ichki `UserInfo({ fullName, phone })` — brend ranglaridagi `Avatar` (`bg-[#f0a52f]` oltin fon, `#1c2b42` navy matn) + `getInitials()` (`@/utils`) initsiallari, ism va telefon.
- `User({ user })`: `user` bo'lmasa `null`. `SidebarMenuButton size="lg"` trigger → `DropdownMenu` (`side`: mobil bo'lsa "bottom", aks holda "right"): `DropdownMenuLabel` da yana `UserInfo`, so'ng "Sozlamalar" (`RouterLink to="/settings"`) va "Chiqish" (`useAuth().logout()`).
- Kamchilik sifatida qayd: `user: any` tipi ishlatilgan (`UserRead` emas).

---

## Terminal komponentlari — `frontend/src/components/Terminal/`

### `frontend/src/components/Terminal/CutmapView.tsx` (~755 qator)

**Maqsadi:** ARRA kesish xaritasi (TZ 7.1.7) — GibSaw/GibLab uslubidagi ekran, GibCut litsenziyasi o'rnini bosadi. `routes/terminal.tsx` (operator) va `routes/_layout/cutmap.$orderId.tsx` (admin) ishlatadi; `admin` prop'ga qarab `OrdersService.readOrderCutmap` yoki `TerminalService.readTerminalCutmap` (`refetchInterval: 60_000`).

**Props:** `orderId`, `onBack`, `admin?`, `registerPrint?(fn)`, `statsContainer?: HTMLElement | null`, `toolbarContainer?: HTMLElement | null`.

- **Drill-down oqim (bitta sahifa, ikki holat):** `sheetIdx === null` bo'lsa jadval sahifasi — material tablari (bitta qator, `overflow-x-auto`, har tabda `bajarilgan/jami` list hisobi) + listlar gridi (`sm:grid-cols-3 lg:grid-cols-4`); har list kartochkasida №, `L×W`, `×mult` badge, tugallanganda ✓ va `SheetSvg thumbnail` mini-xaritasi. List bosilsa — to'liq maydonli xarita.
- **Portal joylashuv:** `statsContainer` berilsa material statistikasi `createPortal` bilan terminal headeriga, `toolbarContainer` berilsa chap toolbar tugmalari terminalning umumiy chap ustuniga ko'chiriladi; berilmasa (admin sahifa) o'z joyida — stats xarita ustida, toolbar `w-[76px]` ustunda qoladi.
- **Statistika qatori (`statsRow`):** GibSaw uslubidagi qat'iy 3 qator × 3 ustun grid — Listlar / Detallar (`jami−bajarilgan=qoldiq` formatida), Atxot (`ko`), Rez m (`dr`), Rezlar (`kr`), To'ldirish (`fill`, %), Arra (`kerf`), Tirim uz. (`trimL`), Tirim en (`trimW`). Xarita ochiq bo'lsa yonida `№N — L × W mm`, `× k list` va material nomi.
- **Chap toolbar** (`TBtn` tugmalari): Orqaga (xarita ochiq bo'lsa listlar jadvaliga, aks holda `onBack()`), Oldingi/Keyingi list, Katta/Kichik/To'liq (`SheetSvg` `registerZoom` bergan `zin/zout/reset`), Chop etish — belgilangan detalning navbatdagi CHIQARILMAGAN nusxasini GoDEX navbatiga yuboradi (dialogsiz); hammasi chiqarilgan bo'lsa yozilmaydi, "avval bekor qiling" xabari. Chop etish mutatsiyasi modul darajasidagi `usePrintLabel()` hookida, bekor qilish `useCancelLabel()` da (`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi).
- **Chek chiqarilgan = kesildi:** modul darajasidagi `isCut(i)` — ARRA skan BOR yoki `label_printed_at` bor; statlar, list kartalari va kataklar shu o'lchovda. Xato chek: katakni long press (~600ms) — tasdiq dialogi ("Ha, bekor qilinsin" / "Yo'q"), skan qilingan nusxa himoyada. Hamma detali chiqarilgan list kartasi butun yashil.
- **Tanlash semantikasi:** xaritada detal bosilsa `markedCell` moviy bo'lib qoladi (kartochka yopilgandan keyin ham) — terminalda tap faqat belgilaydi, chop etish chap toolbardan; `admin` bo'lsa qo'shimcha ravishda `PartCard` dialogi ochiladi.
- `instancesByCell` — `useMemo` bilan `pattern_no:cell_index` kalitli Map; `sheetDone(s)` list to'liq kesilganini (har bir waste bo'lmagan katakning barcha instansiyalari `done`) hisoblaydi.
- **Eksportlar:** `CutmapView` va `TBtn` — `TBtn` (ikonka + `text-[10px]` yozuv, `h-16`, `TBTN_TONES`: default/primary/warn/danger/success) `routes/terminal.tsx` da ham skan/sessiya tugmalari uchun ishlatiladi.
- `PartPreview` — tanlangan detal mini-chizmasi (276×190 viewBox): o'lcham strelkalari, `holes` dan yuza (`bores`) va qirra (`edge`) teshiklari masshtablangan holda, aylantirilgan detalda ⟳.
- `PartCard` dialogi: `PartPreview`, katta QR (`qrcode.react` `QRCodeSVG`, `next.qr_text`), o'lcham/kromka/yorliq raqami, instansiyalar ro'yxati (`✓ kesildi` / `✓ chek chiqarilgan`) va `h-12` "Yopish" tugmasi. Admin rejimida chiqarilgan (skan qilinmagan) nusxa yonida qizil "Chekni bekor qilish" — proyekt ARRA ro'yxatidan tushib bo'lgach texnolog xato chekni shu yerdan tuzatadi. Dialogdagi "YORLIQ CHOP ETISH" tugmasi (PNG'ni `${OpenAPI.BASE}/api/v1/terminal/labels/{instance_id}.png` da yangi tabda ochadi + parallel `printInstanceLabel` bilan GoDEX navbatiga yuboradi) `!admin` shartida — PartCard esa faqat `admin` rejimida ochilgani uchun amalda ko'rinmaydi (terminalda chop etish yo'li — chap toolbardagi "Chop etish").
- `printAllMaps` — barcha xaritalarni chop etish: `renderToStaticMarkup(<SheetSvg .../>)` bilan yangi oynaga yoziladi, har list o'z A4 landscape sahifasida (`@page size: A4 landscape`), "Material | №N — L × W mm × k list" sarlavhasi bilan; sahifadagi "PDF / Chop etish" tugmasiga `registerPrint` prop orqali ulanadi. `escapeHtml` bilan nom/raqam ekranlanadi.
- Xarita mavjud bo'lmasa (`data.model` yo'q — fayl GibLabda optimizatsiya qilinmagan, TEMPLATE) tushuntirish matni + "Orqaga" tugmasi.

### `frontend/src/components/Terminal/SheetSvg.tsx` (~655 qator)

**Maqsadi:** bitta listning to'liq SVG renderi — GibLabViewer'dan portlangan render qoidalari. `CutmapView` (interaktiv, thumbnail va print oqimi) ishlatadi.

**Props:** `sheet`, `holes`, `instancesByCell`, `onSelect(part)`, `selectedCell`, `thumbnail?`, `registerZoom?({zin,zout,reset})`, `onSwipe?("next"|"prev")`.

- **Eksport qilingan geometriya yordamchilari** (`CutmapView/PartPreview` ham ishlatadi): `holeXY(part, H, bx, by)` — teshik lokal koordinatasini katakka o'giradi (`p.rot` da o'q almashinuvi, oynasiz), `edgeLocalXY(H, side, pos)` — qirra teshigining lokal nuqtasi (t/b/l/r), `edgeBoreRect(part, cx, cy, d, dp)` — eng yaqin chetdan ichkariga to'rtburchak (uzunligi = burg'u chuqurligi).
- **Ranglar/qoidalar:** barcha detallar `#e88b00` (to'q apelsin), tanlangani `#2596be`; atxot va list foni `zebra` pattern (`patternTransform rotate(45)`); kesim chiziqlari (`sheet.cuts`) qora `#242424`; yozuvlar halo'siz (to'q apelsin fonda kerak emas).
- **Zoom/pan/swipe (Pointer Events):** g'ildirak zoom kursor nuqtasiga (native `wheel` listener, `passive: false`), bir barmoq pan (zoomda) yoki gorizontal swipe → `onSwipe` bilan list almashtirish (>80px, <600ms), ikki barmoqli pinch. `setPointerCapture` **ataylab ishlatilmaydi** — u keyingi `click`ni SVG'ga retarget qilib detal tanlashni o'ldiradi. G'ildirak, pinch va toolbar tugmalari bitta `zoomAt(f, ax, ay)` yordamchisiga tushadi (tugmalar markaz atrofida 1.5x, `zoomBy`), zoom chegarasi ham shu yerda — `base.w/14`; `viewBox` `base` dan kichik bo'lsagina `vb` state saqlanadi, list almashsa (`sheet.no`) tiklanadi.
- **Yozuv joylashtirish:** har detal uchun eni/bo'yi (kromka kodlari bilan: `p.eH`/`p.eW`) va nom (`№num nom`, aylantirilganda ⟳, ko'p nusxada `done/total`) yoziladi; shrift o'lchami detal o'lchamidan hisoblanadi (cap 42 / 110), joy yetmasa faqat raqam qoladi yoki yozuv olib tashlanadi. Teshiklardan `obstacles` ro'yxati yig'ilib, har yozuv uchun bir necha nomzod joydan teshiksiz birinchisi tanlanadi (`pickSpot`) — tanlangan joy keyingi yozuvlarga ham to'siq, shuning uchun yozuvlar bir-birining va teshiklarning ustiga tushmaydi.
- **Tekstura yo'nalishi:** `p.txt` bo'lsa (va detal >60×40) matn ortida 3 ta gorizontal chiziq.
- **Teshiklar haqiqiy masshtabda:** `H.bores` — radiusi `d/2` doiralar, `H.edge` — `edgeBoreRect` to'rtburchaklari; hammasi `#fafafa` to'ldirish, `#202020` kontur.
- **O'lcham zanjirlari** (`sheet.dims`, `ax: "X"|"Y"`): chetda strelka, ichki chegarada kesim davomi + ✕ belgisi, o'rtada 44px qiymat; `PAD = 110` bilan viewBox'da siqilmaydi (assimetrik ramka — zanjir faqat tepa/chapda).
- Barcha nusxalari "kesilgan" (skan yoki chek chiqarilgan) katak YASHIL (`#6cb56e`) to'ldiriladi — belgisiz; `onLongPress` prop berilsa katakni ~600ms bosib turish uni chaqiradi (12px siljish yoki pinch bekor qiladi, keyingi click yutiladi) — CutmapView bekor qilish dialogi uchun. `thumbnail` rejimda `pointer-events-none`.

### `frontend/src/components/Terminal/KromkaView.tsx`

**Maqsadi:** KROMKA/OVAL post sahifasi. Ikki panel: chapda arradan chiqqan (`arra_passed`), kromkasi tugamagan detallar (tugaganlari yashil bo'lib pastga tushadi), o'ngda "Jarayonda" — 2+ tomonli, boshlangan-u tugamagan nusxalar. Har skan darhol yoziladi (tomon = skan); `registerScan` prop orqali terminalga lokal tekshiruv beradi (`null` = yozish mumkin, `"NOTFOUND"` = bu proyektda yo'q, boshqa string = xato matni: arradan chiqmagan / allaqachon tugagan). `oval` prop: bir panel, tomonlar ustuni yo'q, har detal bitta skan. Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + markazga avto-scroll (`useScanFlash` hooki — xuddi shu mexanizm `routes/terminal.tsx` vazifalar jadvalida ham). Ma'lumot: `readTerminalKromka` (`refetchInterval: 30_000` + har skanda invalidatsiya).

### `frontend/src/components/Terminal/PrisadkaView.tsx`

**Maqsadi:** PRISADKA sahifasi (TZ 12.5): detallar + SCX fayllari, "Hammasini yuklab olish" tugmasi. `lib/scxDir.ts` bilan: File System Access API `showDirectoryPicker` BIR MARTA — tanlangan papka IndexedDB'da (`mebelix-terminal/kv/scx-dir`), keyingi yuklab olishlar so'roqsiz; papka ichida proyekt nomli subpapka (`project_name`, taqiqlangan belgilar `_` ga) ochilib fayllar shu yerga yoziladi. API bo'lmasa `<a download>` fallback. Har skandagi avto-SCX (`downloadScx`) ham saqlangan papkaga tushadi. Yuklab olishda tugmada jonli progress ("Yuklanmoqda… 12/81"); papka tugmasi yozuvli ("Papka" — sensorli ekranda hover yo'q). Jadval ish-navbat tartibida: qilinmaganlar tepada, tugaganlar (✓ yashil) pastda; oxirgi skan bo'lgan qator KEYINGI skangacha amber ajralib turadi va markazga avto-scroll bo'ladi (`useScanFlash` hooki — `done` o'zgargan qatorni topadi: lokal skan ham, stanokdan skan-forvard ham). Har SCX fayl chipi bitta nusxaga mos (fayl nomi = QR): QR'i `done_qrs` da bo'lsa chip yashil ✓ — operator qaysi nusxalar qolganini ko'radi.

### `frontend/src/components/Terminal/audio.ts`

**Maqsadi:** skan ovoz signallari (TZ 8.4.3, sex shovqinida majburiy) — WebAudio, internetsiz ishlaydi: `playSuccess` (600 Hz qisqa), `playError` (200 Hz uzun), `playWarning` (2×800 Hz). `routes/terminal.tsx` da skan natijasiga qarab chalinadi.

---

## UserSettings komponentlari — `frontend/src/components/UserSettings/`

`/settings` sahifasining bo'limlari (joriy foydalanuvchining o'z profili, `*Me` endpointlari).

### `frontend/src/components/UserSettings/UserInformation.tsx`

**Maqsadi:** profil ma'lumotlari (ism, telefon) — ko'rish/tahrirlash rejimi almashinadigan forma.

- `editMode` state: o'qish rejimida qiymatlar `<p>` sifatida (bo'sh ism — "N/A"), "Tahrirlash" tugmasi; tahrirlash rejimida `Input` lar, "Saqlash" (`disabled={!form.formState.isDirty}`) va "Bekor qilish" (`form.reset()` + rejimdan chiqish).
- `onSubmit` faqat o'zgargan maydonlarni `UserUpdate` payloadga qo'shadi va `UsersService.updateUserMe` ni chaqiradi; muvaffaqiyatda `form.reset(form.getValues())` va barcha querylar invalidatsiyasi.

### `frontend/src/components/UserSettings/ChangePassword.tsx`

**Maqsadi:** parolni o'zgartirish formasi.

- zod: `current_password`, `new_password` (`passwordSchema`), `confirm_password` + mos kelish refine'i; `mode: "onSubmit"`.
- Mutation: `UsersService.updatePasswordMe({ requestBody })`; muvaffaqiyatda toast + `form.reset()`.
- Uchchala maydon `PasswordInput` (ko'rish/yashirish ko'zchali) bilan, `aria-invalid={fieldState.invalid}` uzatiladi.

### `frontend/src/components/UserSettings/DeleteAccount.tsx`

**Maqsadi:** "xavfli zona" — o'z hisobini o'chirish. Backend soft-delete qiladi (`crud_users.delete` → `is_deleted=True`, `deleted_at=now`), ya'ni `Admin/DeleteUser` bilan bir xil semantika: foydalanuvchi tizimga kira olmaydi, yozuv esa bazada qoladi. Komponent matni ("butunlay o'chiriladi") haqiqiy xatti-harakatdan kuchliroq.

Superuser bu bo'limni ko'rmaydi: `routes/_layout/settings.tsx` da `is_superuser` bo'lsa tablar `slice(0, 2)` bilan kesiladi; backend ham `delete_user_me` da adminga `ForbiddenException` qaytaradi.

- Qizil hoshiyali karta (`border-destructive/50`), "Hisobni o'chirish" destructive tugmasi → `ConfirmDialog` (destructive, "O'chirish").
- Mutation: `UsersService.deleteUserMe()`; muvaffaqiyatda toast va `useAuth().logout()` (sessiya tugatiladi); `["currentUser"]` invalidatsiyasi.

---

## ui komponentlari — `frontend/src/components/ui/`

shadcn/ui asosidagi 25 ta primitiv. Ko'pchiligi standart generatsiya; quyidagi jadvalda qaysilari o'zgartirilgani ko'rsatilgan.

| Fayl | Komponent(lar) | Asos | Custom o'zgartirish |
|---|---|---|---|
| `avatar.tsx` | Avatar, AvatarImage, AvatarFallback | Radix Avatar | Yo'q (standart) |
| `badge.tsx` | Badge, badgeVariants | cva | Deyarli standart (`rounded-full` shakl) |
| `button.tsx` | Button, buttonVariants | cva + Slot | **Qo'shimcha o'lchamlar**: `icon-sm` (size-8), `icon-lg` (size-10) |
| `card.tsx` | Card, `cardSurface` konstanta | native div | **Soddalashtirilgan custom**: faqat yuza (`rounded-xl border bg-card`), shadcn'ning 5 qismli Header/Title/... API'si ataylab yo'q; `<ul>`/`<details>` kabi teglar uchun `cardSurface` klassi ham eksport |
| `checkbox.tsx` | Checkbox | Radix Checkbox | Yo'q |
| `date-picker.tsx` | DatePicker | react-day-picker + Popover | **To'liq custom** (pastda) |
| `dialog.tsx` | Dialog, DialogContent, DialogHeader/Footer/Title/Description, ... | Radix Dialog | Yo'q (`showCloseButton` prop — yangi shadcn standarti) |
| `dropdown-menu.tsx` | DropdownMenu* (Item `variant="destructive"` bilan), 15 ta eksport | Radix DropdownMenu | Yo'q |
| `form.tsx` | Form, FormField, FormItem/Label/Control/Message, useFormField | react-hook-form + Radix Label | Yo'q |
| `input.tsx` | Input | native `<input>` | Yo'q |
| `label.tsx` | Label | Radix Label | Yo'q |
| `loading-button.tsx` | LoadingButton (`ButtonProps` — fayl ichida, eksport emas) | cva (button nusxasi) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | native `<input>` + Button | **To'liq custom** (pastda) |
| `popover.tsx` | Popover, PopoverTrigger, PopoverContent | Radix Popover | Deyarli standart (`rounded-xl`, `p-3`, `align="start"`) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 10 ta eksport | Radix Select | Yo'q |
| `separator.tsx` | Separator | Radix Separator | Yo'q |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 24 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
| `switch.tsx` | Switch | Radix Switch | Yo'q (terminaldagi "Faqat xatolar" filtri va `employees.tsx` hodim dialogidagi AKTIV/NOFAOL almashtirgichi) |
| `table.tsx` | Table, TableHeader/Body/Footer/Row/Head/Cell/Caption | native table | **Stil custom**: konteyner `rounded-lg border`, TableHeader `bg-muted/50`, TableHead `h-11 text-xs font-semibold uppercase tracking-wider`, TableCell `px-4 py-3 whitespace-nowrap` |
| `tabs.tsx` | Tabs, TabsList, TabsTrigger, TabsContent | Radix Tabs | Yo'q |
| `textarea.tsx` | Textarea | native `<textarea>` | Yo'q (standart shadcn; anketa "Qo'shimcha izoh" maydoni uchun qo'shilgan) |
| `tooltip.tsx` | Tooltip, TooltipTrigger/Content/Provider | Radix Tooltip | Yo'q (delayDuration=0) |

### `frontend/src/components/ui/sidebar.tsx` (custom tafsilotlari)

Eng katta ui fayl (~740 qator, 24 eksport). shadcn'ning rasmiy sidebar blokiga asoslangan, quyidagi o'zgarishlar bilan:

- **Cookie'dan boshlang'ich holatni o'qish**: standart shadcn faqat cookie'ga *yozadi*; bu yerda `getInitialOpen()` funksiyasi `sidebar_state` cookie'sini o'qib, sahifa yangilanganda ochiq/yopiq holatni tiklaydi (`useState(getInitialOpen)` lazy initializer).
- `SidebarTrigger` sr-only matni dinamik: `open ? "Collapse Sidebar" : "Open Sidebar"`.
- `sidebarMenuButtonVariants` o'lchamlari brendga moslangan: `default: "h-8 text-sm rounded-lg"`, `lg: "... rounded-xl data-[state=closed]:rounded-lg"`.
- `SidebarHeader` (`p-2 pb-3`) va `SidebarFooter` (`gap-3 p-2`) padding'lari sozlangan; `SidebarInset` `bg-transparent`.
- Muhim konstantalar: `SIDEBAR_WIDTH = "16rem"`, `SIDEBAR_WIDTH_ICON = "3rem"`, `SIDEBAR_WIDTH_MOBILE = "18rem"`, klaviatura yorlig'i **Ctrl/Cmd+B** (`SIDEBAR_KEYBOARD_SHORTCUT = "b"`).
- Mobil rejimda `Sheet` ichida render qilinadi (`useIsMobile` — `@/hooks/useMobile`); `useSidebar()` hooki `{ state, open, setOpen, openMobile, setOpenMobile, isMobile, toggleSidebar }` kontekstini beradi — `Sidebar/Main.tsx` va `Sidebar/User.tsx` shundan foydalanadi.

### `frontend/src/components/ui/loading-button.tsx` (custom)

shadcn'da yo'q, loyihaga qo'shilgan komponent. `button.tsx` dagi `buttonVariants` nusxasini o'zida saqlaydi va ustiga `loading` prop qo'shadi. **Nusxa allaqachon ajralib ketgan:** `loading-button.tsx` da `icon-sm`/`icon-lg` o'lchamlari yo'q (`<LoadingButton size="icon-sm">` TypeScript xatosi beradi), `default`/`destructive`/`secondary` variantlarida esa `button.tsx` da bo'lmagan `shadow-xs` bor — ikkalasini bir manbaga birlashtirish yoki qo'lda sinxronlash kerak.

```tsx
function LoadingButton({ loading = false, disabled, asChild = false, ... }: ButtonProps)
// loading=true -> disabled + <Loader2 className="mr-2 h-5 w-5 animate-spin" />
```

Barcha mutation submit tugmalarida ishlatiladi (AddUser, EditUser, AddClient, AddOrder, EditOrder, MachineAssign, OrderMatrix, CutmapView, ConfirmDialog, ChangePassword, UserInformation, login formasi, anketa saqlash paneli, employees hodim formalari, machines stanok formasi, buyurtma sahifasi amallari, printers agent qo'shish formasi).

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `Input` stillari bilan bir xil native `<input>` (`pr-10` bilan), o'ng tomonida ghost `Button` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi). `error?: string` prop → `aria-invalid`. `React.forwardRef` bilan react-hook-form'ga mos. `UserSettings/ChangePassword.tsx` va `routes/login.tsx` da ishlatiladi (Admin formalarida esa oddiy `Input type="password"`).

### `frontend/src/components/ui/date-picker.tsx` (custom)

shadcn'da yo'q, to'liq loyihaga yozilgan o'zbekcha sana tanlagich: `react-day-picker` (`uz` locale) + `Popover`. Qiymati form/API bilan mos `"YYYY-MM-DD"` satr, ko'rinishi `DD.MM.YYYY`; trigger tugmada tanlangach "X" tozalash ikonkasi, kalendar ostida "Bugun"/"Tozalash" tugmalari. Props: `value`, `onChange`, `placeholder?`, `className?` (trigger tugma kengligi uchun — masalan anketada `w-full`), `aria-label?` (`<Field>` ichida ko'rinadigan label bo'lmaganda). Buyurtma deadline'i (`Orders/AddOrder`, `Orders/EditOrder`), hisobot oralig'i (`routes/_layout/reports.tsx`) va anketa o'lchov sanasi uchun ishlatiladi.

---

## Bog'lanishlar xulosasi

```
routes (_layout sahifalar)                      routes (terminal / cutmap)
  ├─ PageHeader / StatusBadge / StagePipeline     ├─ CutmapView + TBtn
  ├─ AddOrder / EditOrder ─ orderForm             │    ├─ SheetSvg (zoom/pan/swipe,
  │        ├─ ClientCombobox                      │    │    dims, teshiklar, thumbnail)
  │        └─ AddClient (inline)                  │    └─ PartCard → PartPreview + QR
  ├─ MachineAssign / OrderMatrix                  └─ audio (playSuccess/Error/Warning)
  ├─ AddUser
  ├─ admin.tsx: ui/table + UserRow (sahifalashsiz)
  │    └─ UserActionsMenu ─ EditUser / DeleteUser ─ ConfirmDialog
  └─ PendingUsers (skeleton)

routes/_layout/anketa.$orderId (sahifa ichidagi komponentlar)
  ├─ Section / Field / Num / NumInput / CheckGrid / Choice / ShapeChoice
  ├─ RoomPhotos (drag&drop + Dialog preview)
  ├─ RoomSummary → Facts (canEdit=false ko'rinishi)
  └─ ConfirmDialog (xona o'chirish) · DatePicker · Textarea · LoadingButton

routes (settings)                               routes (__root / layout)
  ├─ UserInformation                              ├─ SidebarProvider (ui/sidebar)
  ├─ ChangePassword                               ├─ AppSidebar
  └─ DeleteAccount                                │    ├─ Main (navItems, rolga qarab)
       └─ ConfirmDialog                           │    └─ User (avatar + logout)
                                                  └─ NotFound / ErrorComponent

Tashqi bog'liqliklar: @/client (UsersService, ClientsService, OrdersService, TerminalService va
User*/Client*/Order*/Post* model turlari), @/queries/mes (getClients/getMachines/getPosts/
getOrderMatrixQueryOptions/getOrderQueryOptions va h.k.),
@/queries/users (getUsersQueryOptions — barcha sahifalarni bitta ro'yxatga yig'adi, `admin.tsx`;
getCurrentUserQueryOptions — `useCurrentUser` va `tablo.tsx` shundan foydalanadi), @/lib/mes (ROLE_LABELS, PRIORITY_LABELS,
PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES, POST_COLORS,
ORDER_STATUS_LABELS/COLORS, formatSize),
@/hooks (useAuth, useCurrentUser, useCustomToast, useMobile),
@/lib/validation (zod schema'lar, formatMoneyInput, formatUzPhone), @/lib/utils (cn),
@/lib/anketa (variant kataloglari, labelOf/labelsOf), @/utils (handleError, getInitials).
```
