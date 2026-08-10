# Frontend Components (Admin, Clients, Common, Orders, Anketa, Sidebar, Terminal, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini va anketa sahifasi ichidagi komponentlarni (`routes/_layout/anketa.$orderId.tsx`) qamrab oladi. Stack: React + TypeScript, TanStack Router/Query, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService, ClientsService, OrdersService, TerminalService va model turlari) orqali gaplashadi; umumiy query'lar `@/queries/mes` dagi `queryOptions` fabrikalarida (getClients/getMachines/getPosts/getOrderMatrixQueryOptions va h.k.), domen konstantalari `@/lib/mes` da (ROLE_LABELS, PRIORITY_LABELS, PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES — prioritet ranglari yagona manbadan, POST_COLORS, ORDER_STATUS_LABELS/COLORS, chipColors/mixTint — chip rang formulasi, isCut, formatSize), buyurtma anketasi variantlari `@/lib/anketa` da; toast xabarlari to'g'ridan-to'g'ri sonner `toast.success/error` (`useCustomToast` hooki o'chirilgan), xatoliklar `handleError` utiliti orqali (`onError: handleError` — curry emas); takrorlanuvchi toast+xato+invalidatsiya triosi `@/queries/mes` dagi `crudCallbacks()` da.

Umumiy naqsh (pattern): **forma → zod schema → react-hook-form → useMutation → @/client servisi → toast + query invalidation**. Barcha ko'rinadigan UI matnlari o'zbek tilida; shadcn primitivlaridagi ekran o'quvchi matnlari ham o'zbekchalashtirilgan (`sidebar.tsx` trigger — "Menyuni yig'ish/Menyuni ochish", mobil sidebar sr-only sarlavhasi "Yon menyu", tavsifi "Mobil yon menyu"; `dialog.tsx`/`sheet.tsx` — sr-only "Yopish"; `password-input.tsx` — aria-label "Parolni yashirish/ko'rsatish").

---

## Admin komponentlari — `frontend/src/components/Admin/`

Admin panel (`/admin` route, guard: `requireAccess(isSuperuser)`) uchun foydalanuvchilarni CRUD boshqarish komponentlari. Jadvalning o'zi route faylida — `routes/_layout/admin.tsx` dagi lokal `UserRow` oddiy `ui/table` qatorini chizadi (clients.tsx/employees.tsx bilan bir xil naqsh; joriy foydalanuvchi qatorida "Siz" badge); sahifalash yo'q, `getUsersQueryOptions` barcha sahifalarni bitta ro'yxatga yig'adi. Yuklanish holati — `isLoading` + `Skeleton` (avvalgi `Pending/PendingUsers` skeleton komponenti va Suspense naqshi o'chirilgan). Add/Edit dialoglarining umumiy yadrosi — `UserForm.tsx`.

### `frontend/src/components/Admin/UserForm.tsx`

**Maqsadi:** AddUser va EditUser uchun umumiy forma yadrosi — schema va maydonlar bir joyda (avval har dialogda ~320 qatordan takrorlangan edi).

- Eksportlar: `buildUserFormSchema(requirePassword)` — zod: `phone` (`phoneSchema`), `name` (`optionalNameSchema`), `password` (Add'da `passwordSchema`, Edit'da `optionalPasswordSchema` — bo'sh qoldirilsa parol o'zgarmaydi), `confirm_password`, `role` (`z.enum(Object.keys(ROLE_LABELS))` — 15 rol yagona manbadan, generatsiya qilingan `UserRole` tipida), `machine_id` (ixtiyoriy), `is_superuser`, `is_active`; ikkita `.refine()`: stanokka bog'liq rolga stanok majburiy ("Terminal/TABLO uchun stanok tanlang") va parollar mosligi ("Parollar mos emas").
- `UserFormFields({ form, passwordRequired })` — 8 maydonli grid: rol `Select` `ROLE_LABELS` (`@/lib/mes`) dan to'ldiriladi; rol stanokka bog'liq bo'lsa shartli "Stanok" `Select` chiqadi (`getMachinesQueryOptions()` — `@/queries/mes`).
- `isMachineBoundRole(role)` — `MACHINE_BOUND_ROLES` (`@/lib/mes`, terminal/tablo) asosidagi predikat; ikkala dialog submitda ham shundan foydalanadi.

### `frontend/src/components/Admin/AddUser.tsx`

**Maqsadi:** yangi foydalanuvchi yaratish dialogi (o'zining trigger tugmasi bilan).

- Schema `buildUserFormSchema(true)` (parol majburiy) + maydonlar `UserFormFields` — ikkalasi `UserForm.tsx` dan.
- Default qiymatlar: `role: "manager"`, `is_superuser: false`, `is_active: true` — yangi foydalanuvchi darhol tizimga kira oladi.
- Submitda `machine_id` faqat stanokka bog'liq rolda (`isMachineBoundRole`) `Number` ga o'giriladi, aks holda `null` — rol keyin almashtirilsa yashirin qolgan stanok tanlovi ofis rolga jo'nab ketmaydi.
- Mutation: `UsersService.createUser({ requestBody })`; muvaffaqiyatda toast, forma reset, dialog yopiladi; `onSettled` da `["users"]` query invalidatsiya qilinadi.
- Forma `mode: "onBlur"` rejimida validatsiya qiladi; trigger — `<Plus /> Foydalanuvchi qo'shish` tugmasi.
- Submit tugmasi `LoadingButton` (`loading={mutation.isPending}`).

**Bog'lanishlar:** `Admin/UserForm` (schema + maydonlar), sonner `toast`, `@/utils` (`handleError`), ui: `dialog`, `form`, `button`, `loading-button`. Admin route sahifasidan chaqiriladi.

### `frontend/src/components/Admin/DeleteUser.tsx`

**Maqsadi:** foydalanuvchini o'chirish — dropdown menu bandi + tasdiqlash dialogi.

- Props: `{ id: string; onSuccess: () => void }`.
- Mutation: `UsersService.deleteUser({ userId: Number.parseInt(id, 10) })`; muvaffaqiyatda toast, dialog yopiladi, `onSuccess()` (ota-menuni yopish); `onSettled` da `["users"]` queryi invalidatsiya qilinadi.
- `DropdownMenuItem variant="destructive"` da `onSelect={(e) => e.preventDefault()}` — menyu yopilib dialog ochilishini ta'minlaydi.
- Dialog UI to'liq `Common/ConfirmDialog` orqali (`destructive`, `confirmText="O'chirish"`); description matni soft-delete'ga mos — foydalanuvchi **o'chirilgan deb belgilanadi** va tizimga kira olmaydi (ma'lumotlar butunlay o'chirilmaydi).

### `frontend/src/components/Admin/EditUser.tsx`

**Maqsadi:** mavjud foydalanuvchini tahrirlash dialogi (dropdown menu bandi ichidan ochiladi).

- Props: `{ user: UserRead; onSuccess: () => void }`.
- Schema `buildUserFormSchema(false)` (`UserForm.tsx`): `password` — `optionalPasswordSchema` (bo'sh qoldirilsa parol o'zgarmaydi), refine faqat parol kiritilganda mosligini tekshiradi.
- `onSubmit` da to'liq `UserAdminUpdate` payload quriladi (rol va stanok ham tahrirlanadi); `password` faqat kiritilgan bo'lsa qo'shiladi:

```ts
const payload: UserAdminUpdate = {
  phone, name, role,
  machine_id: isMachineBoundRole(role) && machine_id ? Number(machine_id) : null,
  is_superuser, is_active,
}
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
- Mutation: `ClientsService.createClient` (`crudCallbacks` triosi — toast + xato + `["clients"]` invalidatsiyasi); muvaffaqiyatda reset, dialog yopilib `onCreated?.(client)` chaqiriladi.

### `frontend/src/components/Clients/ClientCombobox.tsx`

**Maqsadi:** server-qidiruvli mijoz tanlagich — ro'yxat backend `?search=` bilan filtrlanadi, mijozlar soni mingga yetsa ham ishlaydi.

- Qidiruv 300ms debounce (`useDebounced` hooki) bilan `getClientsQueryOptions(search)` ga uzatiladi (`enabled: open`); ArrowUp/ArrowDown/Enter klaviatura navigatsiyasi.
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

**Foydalanuvchilari:** `Admin/DeleteUser.tsx`, `routes/_layout/orders/$orderId.tsx`, `routes/_layout/anketa.$orderId.tsx` (xona o'chirish), `routes/_layout/employees.tsx`, `routes/_layout/printers.tsx` (stanok bog'lash/uzish, chek chiqarish `can_print` switch'i, agentga yangi kod berish va agentni bekor qilish — to'rtta dialog), `routes/terminal.tsx`.

### `frontend/src/components/Common/EmptyRow.tsx`

**Maqsadi:** jadvalning bo'sh holati qatori (`colSpan` + markazlangan muted xabar — "topilmadi / hali yo'q") — har reyestrda qo'lda takrorlanadigan `TableRow`+`TableCell` naqshi bitta joyda. 8 ta reyestr sahifasida ishlatiladi (clients, employees, logs, machines, reports, materials, printers, orders ro'yxati).

### `frontend/src/components/Common/ErrorComponent.tsx`

**Maqsadi:** routerning global xato ekrani — `ErrorScreen` ga delegatsiya (`code="Xato"`, "Xatolik yuz berdi..." matni).

### `frontend/src/components/Common/ErrorScreen.tsx`

**Maqsadi:** xato/404 ekranlarining umumiy maketi (`code` + `message` + "Bosh sahifaga" tugmasi, `Link to="/"`) — ikki nusxa layout drift bermasin. `ErrorComponent` va `NotFound` shundan quriladi.

### `frontend/src/components/Common/Footer.tsx`

**Maqsadi:** oddiy footer — `MebeliX MES · {joriy yil}`. `AuthLayout` ichida ishlatiladi.

### `frontend/src/components/Common/NotFound.tsx`

**Maqsadi:** 404 ekrani — `ErrorScreen` ga delegatsiya (`code="404"`, "Siz qidirayotgan sahifa topilmadi." matni). Router'ning `notFoundComponent` sifatida ulanadi.

### `frontend/src/components/Common/OperationChips.tsx`

**Maqsadi:** marshrut QADAMINING amal nomi chipi (kod 11 → "G petlya o'ngdan") — amber chip; chipsiz operator raqamni yoddan tarjima qilishi kerak edi, va noto'g'ri petlya eshikni brak qiladi.

- Props: `processCode: number | null | undefined` va `postCode: string | null | undefined`. Kod endi detal NOMIDAN o'qilmaydi — nomdagi `{kodlar}` sintaksisi butunlay olib tashlangan; `process_code` marshrut qadamining o'zida saqlanadi va backend uni `TaskRow`/`KromkaPartRow` da beradi.
- `PROCESS_OPS` (`@/lib/mes` dan import — 14 kod, backend `PROCESS_POSTS` bilan bir xil bo'lishi shart) kodni amal nomi + postga o'giradi. Chip chizilmaydi, agar: kod noma'lum bo'lsa (xato nom emas, hech nima), kod boshqa postga tegishli bo'lsa yoki post bitta amalli bo'lsa (prisadka, rover, oval, bo'yoq — post nomi ekran sarlavhasida turibdi). Ya'ni chip faqat ARRA, KROMKA va STOLYARKA da ko'rinadi.
- Ishlatilish joylari: `Terminal/KromkaView` (`postCode={oval ? "OVAL" : "KROMKA"}`) va `routes/terminal.tsx` vazifalar jadvali (`postCode={ctx?.post_code}`).

### `frontend/src/components/Common/PageHeader.tsx`

**Maqsadi:** sahifa sarlavhasi — `title`, ixtiyoriy `description` va o'ng tomonda `actions` slot. Barcha `_layout` sahifalarida ishlatiladi (dashboard, orders ro'yxati va sahifasi, clients, employees, machines, materials, reports, logs, printers, anketa, admin, settings — 13 ta sahifa); yagona istisno — `cutmap.$orderId.tsx`, unda sarlavha umuman yo'q (to'liq ekran).

### `frontend/src/components/Common/PostBadge.tsx`

**Maqsadi:** bosqich (post) kodi chipi (ARRA, KROMKA, ...) — `POST_COLORS` + `chipColors(color, 12)` (`@/lib/mes`) asosida: matn post rangining to'qroq variantida (`78%, black` — WCAG AA kontrasti, sof rang tint fonda o'tmasdi), fon 12% oq tint. Avval `employees.tsx` va `machines.tsx` da qo'lda takrorlangan edi.

### `frontend/src/components/Common/QueryError.tsx`

**Maqsadi:** so'rov yiqilganda ko'rsatiladigan `role="alert"` bloki — xato matni + ixtiyoriy "Qayta urinish" tugmasi (`onRetry`). Busiz sahifalar xato holatida abadiy skeletonda qotib qolardi.

### `frontend/src/components/Common/SearchInput.tsx`

**Maqsadi:** ichida `Search` ikonkasi bo'lgan qidiruv maydoni (`value`/`onChange`/`placeholder`/`className`) — reyestr sahifalarida (clients, employees, orders ro'yxati, materials, logs) qo'lda takrorlanadigan `relative` div + absolyut ikonka + `pl-8` Input naqshi bitta joyda; kenglik/joylashuv `className` orqali chaqiruvchidan.

### `frontend/src/components/Common/SectionTitle.tsx`

**Maqsadi:** sahifa ichidagi bo'lim sarlavhasi (`h2`, uppercase muted) — ierarxiya: `PageHeader` (h1) > `SectionTitle` (h2) > panel sarlavhalari (h3); avval bir daraja to'rt xil yozilgan edi.

### `frontend/src/components/Common/StagePipeline.tsx`

**Maqsadi:** ishlab chiqarish pipeline'i (TZ 4.4) — ulangan progress kataklar zanjiri, loyihaning "signature" vizual elementi. Kataklar data-driven (`stages` propidan), hozir bazada 7 post (PAZ olib tashlangan, BOYOQ qo'shilgan).

- Props: yagona `stages: StageCell[]` (`{ code, done, total }`); har katak (`h-6 w-12`) `POST_COLORS[code]` rangida (`mixTint` fon + foizli progress chizig'i), ichida `done/total` (`--foreground` rangda — post rangi o'z tinti ustida AA dan o'tmasdi), tugallanganda "✓"; kataklar orasida ulovchi chiziqcha, `title` da `KOD: done/total (N%)`.
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

**Maqsadi:** texnolog matritsasi (TZ 6.3.3) — qatorlar: detallar, ustunlar: STANDART detalning postlari, ya'ni `getPostsQueryOptions` ro'yxati `STANDARD_MATRIX_POSTS` (`@/lib/mes` — ARRA, KROMKA, PRISADKA) bo'yicha filtrlanadi. Rover/stolyarka/bo'yoq/oval ustunlari olib tashlangan: fayldan avtomatik marshrut faqat shu uch postni beradi (roverdan chiqqan detal keyin bo'yalishi mumkinligini fayl bilmaydi), qolgani hech qachon to'lmaydigan bo'sh ustun bo'lib turardi — ular endi "Nostandart detallar" tabida qo'lda chiziladi.

- O'qish rejimida har katak `total_done/total_required` progress (`POST_COLORS`, tugallanganda "✓"), o'chirilgan bosqich "—". Bitta post marshrutda BIR NECHA MARTA kelishi mumkin (kromka → prisadka → yana kromka), shuning uchun katak shu postdagi barcha qadamlarning yig'indisini ko'rsatadi.
- `editable` bo'lsa "Marshrutni tahrirlash" rejimi: bosqich checkboxlari + izoh inputlari + "Nostandart" katakchasi, hammasi bitta `OrdersService.editOrderMatrix` batchida saqlanadi (`crudCallbacks`). Checkbox locked bo'ladi ikki holatda: ARRA (standart detalda majburiy — TZ 5.4.1) va detal nostandart bo'lsa (uning marshruti bu yerda emas, alohida tabda chiziladi).
- **"Nostandart" ustuni** (post ustunlaridan keyin): o'qish rejimida amber "✓" yoki "—", tahrirlashda `Checkbox` → `MatrixPartEdit.is_custom`. Belgilangan detal fayldan avtomatik marshrut olmaydi (mavjud avtomatik qadamlar yumshoq o'chadi, bayroq qaytarilsa aynan tiklanadi), marshrutini texnolog `Orders/CustomRoutes` da chizadi.
- Boshqaruv qatorida detal qidiruvi ("Qidirish: kod yoki nom...") va `N / M detal` hisobi; jadval balandligi 70vh bilan chegaralangan, sarlavha sticky.
- Har detal kodi yonida Map-ikonka — `/cutmap/$orderId?part=...` havolasi: kesish xaritasida detalning listi ochilib katagi belgilanadi (`CutmapView` `focusPartKey` oqimi).
- `part.is_custom` bo'lsa detal nomi ostida amber belgi — "Nostandart · N qadam" yoki (marshrut hali chizilmagan bo'lsa) "Nostandart · marshrut yo'q", `title` da tushuntirish.
- Ma'lumot: `getOrderMatrixQueryOptions(orderId)`; o'lchamlar `formatSize` (`@/lib/mes`) bilan.

### `frontend/src/components/Orders/CustomRoutes.tsx`

**Maqsadi:** "Nostandart detallar" tabi (TZ 6.3.3) — matritsada `is_custom` deb belgilangan detallarning marshrutini texnolog QO'LDA chizadi. Fayl bunday detalning yo'lini bilmaydi (nomdagi `{kodlar}` sintaksisi olib tashlangan, marshrut endi detal nomiga umuman bog'liq emas), shuning uchun yagona manba — texnologning shu ekrandagi tanlovi.

- Props: `{ orderId: number; editable: boolean }`. Ma'lumot — `OrderMatrix` bilan AYNAN bitta query (`getOrderMatrixQueryOptions(orderId)`, TanStack dedupe qiladi), `parts.filter(p => p.is_custom)`; nostandart detal bo'lmasa tushuntirish matni chiqadi ("Detallar matritsasida 'Nostandart' ustunidan belgilang").
- Har detal kartochkasida `PROCESS_OPS` ning 14 kodi tugma bo'lib chiziladi (`title` da `kod · POST`). Tugma bosilsa kod marshrut oxiriga QO'SHILADI va tanlangan tartibda raqamlanadi (1, 2, 3...); bitta jarayonni qayta bosish yangi qadam beradi (kromka → prisadka → yana kromka — shuning uchun tugmada `1,3` kabi bir necha raqam turishi mumkin), OXIRGI qadamni bosish esa uni bekor qiladi. O'ng tomonda joriy marshrut `7 / 11 / 8` ko'rinishida.
- Validatsiya: marshrut bo'sh bo'lmasligi va `ROUTE_START_POSTS` (`@/lib/mes` — ARRA yoki ROVER) dan boshlanishi shart — chek shu birinchi postda chiqadi. Buzilgan detal kartochkasi qizil ramkada, tepada nechta ekani sanaladi, "Saqlash" tugmasi bloklanadi (backend ham marshrutsiz detalni ishlab chiqarishga o'tkazmaydi).
- Tahrirlar `draft` state'da (`part_id -> kodlar massivi`) yig'iladi, faqat tegilgan detallar; saqlash — `OrdersService.editOrderMatrix` (`edits[].route_codes`, `stages: {}`), muvaffaqiyatda `draft` tozalanadi. `editable=false` bo'lsa tugmalar `disabled`, saqlash paneli umuman chizilmaydi (ko'rish rejimi).
- `routes/_layout/orders/$orderId.tsx` da texnolog uchun DOIM ikkinchi tab sifatida turadi ("Nostandart detallar (N)").

---

## Anketa komponentlari — `frontend/src/routes/_layout/anketa.$orderId.tsx`

Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i) komponentlari `components/` da emas, sahifa faylining o'zida (~1470 qator) — faqat shu sahifada ishlatiladi. Variantlar katalogi alohida: `frontend/src/lib/anketa.ts`.

**Ma'lumot oqimi:** `Order.survey` (JSONB) — `OrderSurvey { version, measured_at, measured_by, packaging, delivery, installation, rooms[] }`; xona `SurveyRoom` (materiallar, o'lchamlar, `walls: SurveyWall[]`, `modules: SurveyModule[]`). Saqlash `OrdersService.saveOrderSurvey` (`PUT /orders/{id}/survey`); xona rasmlari JSON'da emas, `OrderFile(kind=DOCUMENT, meta.room_id)` da (`OrdersService.uploadRoomPhoto` / `deleteRoomPhoto`) — shuning uchun avtosaqlash bilan aralashmaydi.

**Sahifa xulq-atvori (`AnketaPage`):**

- Server ma'lumoti **faqat bir marta** state'ga yuklanadi (`loaded` ref) — aks holda saqlashdan keyingi refetch menejer yozayotgan matn ustiga tushardi.
- Avtosaqlash: har tahrirdan 1.5s keyin (`dirty` bo'lsa va `canEdit` bo'lsa) `save.mutate`; `beforeunload` da ogohlantirish, unmount'da fire-and-forget `saveOrderSurvey`.
- `canEdit = is_superuser || role === "admin" | "manager"` — faqat ular formani ko'radi; qolganlar (texnolog/direktor) `RoomSummary` jamlanmasini ko'radi.
- Xonalar tab pill'lari: har pill — `div` konteyner, ichida xona nomi tugmasi (`r.name || "Xona N"`) va undan alohida `×` o'chirish tugmasi (`aria-label` "{nom} — o'chirish"; faqat `canEdit && rooms.length > 1` da chiziladi — ichma-ich `<button>` bo'lmasligi uchun ikkitasi alohida). `×` bosilsa `removeIdx` (`number | null`) belgilanadi va `ConfirmDialog` ochiladi — istalgan xona oldindan tanlanmasdan o'chiriladi (rasmlar ham o'chadi — backend `save_order_survey` da yetim rasmlarni tozalaydi). Yonida "Xona qo'shish" tugmasi.
- "Butun buyurtma uchun" kartasi (faqat `canEdit`, raqamlangan xona bo'limlaridan tepada): `ORDER_SERVICES` katakchalari — Upakovka qilish (`packaging`), Yetkazib berish (`delivery`), O'rnatish (montaj) (`installation`) — hamda o'lchov sanasi (`DatePicker`) va o'lchagan usta. Bular xonaga bo'linmaydi: sex bitta `.project` fayl ustida ishlaydi, logistika butun buyurtmani bitta mashinada olib ketadi. Yuklashda eski anketalar migratsiya qilinadi — biror xonaning `extra_services` da `yetkazish`/`montaj` bo'lsa, buyurtma bayrog'i yoqiladi va kod xona ro'yxatidan olib tashlanadi (avtosaqlash keyingi tahrirda yangi shaklni yozadi).
- Pastda sticky saqlash paneli: holat matni ("Saqlanmoqda..." / "Saqlanmadi — qayta urinib ko'ring" — `role="alert"` + `text-destructive` / "O'zgarishlar avtomatik saqlanadi" / "Saqlandi HH:MM" / "Hammasi saqlangan") + `LoadingButton`. Manfiy margin (`-mx-6 md:-mx-8`) bilan main padding'i qoplanadi; suvbelgi va dekor konteyner olib tashlangach `routes/_layout.tsx` da `overflow-hidden` umuman yo'q — `sticky` to'siqsiz ishlaydi.

**Bo'limlar (qog'oz anketa raqamlari bilan):** 1 Xona va rasmlar · 2 Qanday mebel kerak · 3 Xonadagi shakli va o'lchamlari · 4 Korpus materiali · 5 Fasad materiali · 6 Furnitura va qo'shimcha xizmat · 7 Qo'shimcha izoh · 8 O'lchov varag'i (`<details>` ichida yopiq — zamerdan keyin usta to'ldiradi: A–E devor uzunlik/balandligi, modullar jadvali, umumiy pm/balandlik; o'lchov sanasi/ustasi bu yerda emas — ular "Butun buyurtma uchun" blokida).

**Sahifa ichidagi komponentlar:**

| Komponent | Vazifasi |
|---|---|
| `RoomPhotos` | Xona rasmlari: butun panel drag&drop zona, `MAX_PHOTOS = 6`, `MAX_PHOTO_MB = 5`, MIME/hajm/soni klientda tekshiriladi; rasm bosilsa `Dialog` da katta ko'rinish + "Asl hajmda yangi oynada ochish"; rasmlar `<img crossOrigin="use-credentials">` bilan `/api/v1/orders/{id}/files/{fileId}` dan olinadi |
| `RoomSummary` | Texnolog/direktor ko'rinishi — tartib qog'ozning teskarisi: avval modullar jadvali va o'lchamlar, keyin material, so'ng mebel turi/xizmatlar (texnolog GibLab'da shu tartibda ishlaydi). `room` bilan birga `survey` propini oladi: o'lchamlar bo'limining oxirida "O'lchov" (`survey.measured_at` — `survey.measured_by`) va "Buyurtma bo'yicha" (belgilangan `ORDER_SERVICES` yorliqlari) qatorlari |
| `Facts` | `dl` jadvali; bo'sh qiymatlar tashlab yuboriladi, hech nima yo'q bo'lsa "To'ldirilmagan." |
| `Section` | `n?` raqami + `title` + `hint?` bo'lgan karta (raqam qog'oz anketa bilan bir xil — menejer telefonda "3-bo'limga o'tamiz" deb ayta oladi) |
| `Field` / `Num` | Label + child; `Num` — `Field` + `NumInput` |
| `NumInput` | Raqamli maydon: yozilayotgan xom matn `raw` state'da saqlanadi (aks holda "3," yozilganda maydon o'zini tozalab qo'yardi), blur'da normallashadi; vergul o'nlik ajratgich sifatida qabul qilinadi (`numOrNull`); `integer` bo'lsa `Math.trunc` |
| `CheckGrid` | Ko'p tanlovli katakchalar (butun katak bosiladi — sensorli ekran) |
| `Choice` | Bitta tanlov, qayta bosilsa bekor qilinadi (radio'da imkonsiz); `h-9` — `Input` bilan bir xil balandlik |
| `ShapeChoice` + `SHAPE_ART` | Planirovka siluetlari (I / L / П / orolchali) — inline SVG to'rtburchaklar; mijoz "П-shakl (U)" jargonini emas, shaklni taniydi |

### `frontend/src/lib/anketa.ts`

Anketa variantlari katalogi — bazaga faqat `value` kodlari yoziladi, matnlar shu yerda (matn o'zgarsa tarix buzilmaydi).

- `Option = { value, label }`; ro'yxatlar: `FURNITURE_TYPES` (10), `LAYOUT_SHAPES` (4), `CORPUS_MATERIALS` (5), `CORPUS_THICKNESS` (16/18/boshqa), `FACADE_MATERIALS` (7), `COUNTERTOPS` (4), `HARDWARE_LEVELS` (oddiy/medium/premium), `EXTRA_SERVICES` (4 — led, rozetka, organayzer, oyna), `WALL_LETTERS` (`A`–`E`). Yetkazib berish va montaj bu ro'yxatdan chiqarilgan: ular butun buyurtmaga tegishli (`OrderSurvey.delivery` / `installation`).
- `labelOf(options, value)` va `labelsOf(options, values)` — kodni/kodlar ro'yxatini o'qiladigan matnga (`RoomSummary` ishlatadi).

---

## Sidebar komponentlari — `frontend/src/components/Sidebar/`

Claude.com uslubidagi yon panel: trigger sidebar ichida; desktopda alohida app header/footer yo'q, mobil rejimda esa `routes/_layout.tsx` da yupqa header bor (`h-12`, `md:hidden`) — `SidebarTrigger` + joriy bo'lim sarlavhasi (`sectionTitles` — `NAV_ITEMS` dan quriladi).

### `frontend/src/components/Sidebar/AppSidebar.tsx`

**Maqsadi:** ilovaning asosiy yon paneli — brend, navigatsiya va foydalanuvchi menyusini yig'adi.

- Modul darajasidagi `NAV_ITEMS` ro'yxati (TZ 3.7 rollar-modullar matritsasi, eksport — `routes/_layout.tsx` mobil sarlavhalari ham shu ro'yxatdan) 11 tagacha punkt beradi, har bandda `show(user)` predikati. Huquq predikatlari `@/lib/mes` dan — `isProductionStaff` / `isManagement` / `isAdmin` / `isSuperuser`; **route guard'lar ham AYNAN shularni ishlatadi** (`lib/guards.requireAccess`), ya'ni menyuda ko'rinadigan sahifa albatta ochiladi. Bandlar: Boshqaruv paneli `/` va LIVE Tablo `/tablo` — hammaga; Buyurtmalar `/orders`, Stanoklar `/machines`, Materiallar `/materials` — `isProductionStaff` (boshqaruv + texnolog); Mijozlar `/clients`, Hodimlar `/employees`, Hisobotlar `/reports` — `isManagement` (admin/manager/direktor); Printer agentlar `/printers` (`Printer` ikonkasi) va Loglar `/logs` (`ScrollText` ikonkasi) — `isAdmin` (superuser yoki `role === "admin"`); Foydalanuvchilar `/admin` — **faqat `isSuperuser`**, chunki ro'yxat barcha telefon raqamlarni ochadi va backend ham uni faqat superuser'ga beradi. **Rolga qarab navigatsiya**.
- Buyurtmalar bandida jonli badge — faol buyurtmalar soni (`TERMINAL_STATUSES` — delivered/cancelled — dan boshqa statuslar yig'indisi): `getOrderStatusCountsQueryOptions()` reyestr sahifasi bilan AYNAN bitta query key'da, TanStack dedupe qiladi — sidebar qo'shimcha so'rov qo'shmaydi; `enabled` faqat `/orders` bandi ko'rinadigan rollarda.
- `<Sidebar collapsible="icon">`: yig'ilganda faqat ikonkalar qoladi. Header'da `Link to="/"` — ichida faqat to'liq logo (`/assets/logo/logo-gold.png`, `h-9 w-auto`, `alt="MebeliX — bosh sahifa"`; login ekrani bilan bir xil brend), matn tuguni yo'q. Yig'ilganda BUTUN havola `group-data-[collapsible=icon]:hidden` bilan yashiriladi — brend tab sarlavhasi, favicon va login ekranida qoladi, bosh sahifa havolasi esa menyuning birinchi qatorida ("Boshqaruv paneli"). `SidebarTrigger` yig'ilgan railda `group-data-[collapsible=icon]:mx-auto` bilan markazga tushadi.
- `SidebarContent` → `Main items={items}`; `SidebarFooter` → `User user={currentUser}`.

**Bog'lanishlar:** `@/hooks/useCurrentUser`, `ui/sidebar.tsx`, `Sidebar/Main.tsx`, `Sidebar/User.tsx`. Layout route ichida `SidebarProvider` + `SidebarInset` bilan ishlatiladi.

### `frontend/src/components/Sidebar/Main.tsx`

**Maqsadi:** navigatsiya menyusi ro'yxati.

- Eksport: `type Item = { icon: LucideIcon; title: string; path: string; badge?: number }` va `Main({ items })`; `badge` bo'lsa (0 emas) band yonida `SidebarMenuBadge` chiqadi.
- `useRouterState()` dan `currentPath` olinib `isActive = currentPath === item.path` aniqlanadi; aktiv bandda chapdan 3px oltin chiziq `before:` pseudo-element bilan (`data-[active=true]:before:...w-[3px]...before:bg-sidebar-primary`) va ikonka `text-sidebar-primary` ga o'tadi — inset soya tugmaning rounded burchaklarida qirqilib ko'rinmasdi.
- Har band `SidebarMenuButton tooltip={item.title} asChild` ichida `RouterLink`; mobil rejimda bosilganda `setOpenMobile(false)` bilan panel yopiladi.

### `frontend/src/components/Sidebar/User.tsx`

**Maqsadi:** sidebar footeridagi foydalanuvchi kartasi va dropdown menyusi.

- Ichki `UserInfo({ fullName, phone })` — tema tokenlaridagi `Avatar` (`bg-sidebar-primary` oltin fon, `text-sidebar-primary-foreground` matn) + `getInitials()` (`@/utils`) initsiallari (ism bo'sh bo'lsa "Foydalanuvchi" dan), ism va telefon. Yig'ilganda ism/telefon ustuni ham, yonidagi `ChevronsUpDown` ikonkasi ham `group-data-[collapsible=icon]:hidden` bilan yashiriladi — aks holda avatar 32px ga qisqargan tugmadan (`sidebarMenuButtonVariants` da `group-data-[collapsible=icon]:size-8!`) toshib chiqardi; dropdown ichidagi nusxaga bu qoida tegmaydi (sidebar `group`i unga ajdod emas), ya'ni menyuda ism ko'rinaveradi.
- `User({ user }: { user?: UserRead | null })`: `user` bo'lmasa `null`. `SidebarMenuButton size="lg"` trigger → `DropdownMenu` (`side`: mobil bo'lsa "bottom", aks holda "right"): `DropdownMenuLabel` da yana `UserInfo`, so'ng "Sozlamalar" (`RouterLink to="/settings"`) va "Chiqish" (`useAuth().logout()`).

---

## Terminal komponentlari — `frontend/src/components/Terminal/`

### `frontend/src/components/Terminal/CutmapView.tsx` (~970 qator)

**Maqsadi:** ARRA kesish xaritasi (TZ 7.1.7) — GibSaw/GibLab uslubidagi ekran, GibCut litsenziyasi o'rnini bosadi. `routes/terminal.tsx` (operator) va `routes/_layout/cutmap.$orderId.tsx` (admin) ishlatadi; `admin` prop'ga qarab `OrdersService.readOrderCutmap` yoki `TerminalService.readTerminalCutmap` (`refetchInterval: 60_000`).

**Props:** `orderId`, `onBack`, `admin?`, `registerPrint?(fn)`, `statsContainer?: HTMLElement | null`, `toolbarContainer?: HTMLElement | null`, `focusPartKey?: string` — matritsadagi Map-havoladan (`/cutmap/$orderId?part=...`) kelganda detalning listini ochib katakni belgilaydi.

- **Drill-down oqim (bitta sahifa, ikki holat):** `sheetIdx === null` bo'lsa jadval sahifasi — material tablari (bitta qator, `overflow-x-auto`, har tabda `bajarilgan/jami` list hisobi) + listlar gridi (`sm:grid-cols-3 lg:grid-cols-4`); har list kartochkasida №, `L×W`, tugallanganda ✓ va `SheetSvg thumbnail` mini-xaritasi. `mult>1` naqshlar render paytida HAR JISMONIY LIST uchun alohida kartaga yoyiladi (№ `3c1` ko'rinishida) — ×mult badge yo'q. List bosilsa — to'liq maydonli xarita.
- **Portal joylashuv:** `statsContainer` berilsa material statistikasi `createPortal` bilan terminal headeriga, `toolbarContainer` berilsa chap toolbar tugmalari terminalning umumiy chap ustuniga ko'chiriladi; portal berilmasa terminal rejimida toolbar `w-[68px]` ustunda qoladi, admin rejimida esa bu ustun umuman chizilmaydi — o'rniga sichqonchaga mo'ljallangan ixcham `webToolbar` icon-qatori (oldingi/keyingi list, zoom +/−/to'liq) va "Listlar ro'yxati" tugmasi, stats xarita ustida.
- **Statistika qatori (`statsRow`):** GibSaw uslubidagi qat'iy 3 qator × 3 ustun grid — Listlar / Detallar (`jami−bajarilgan=qoldiq` formatida), Atxot (`ko`), Rez m (`dr`), Rezlar (`kr`), To'ldirish (`fill`, %), Arra (`kerf`), Tirim uz. (`trimL`), Tirim en (`trimW`). Xarita ochiq bo'lsa yonida `№N — L × W mm` (N — yoyilgan raqam, `disp ?? no`) va material nomi.
- **Chap toolbar** (`TBtn` tugmalari): Orqaga (xarita ochiq bo'lsa listlar jadvaliga, aks holda `onBack()`), Oldingi/Keyingi list, Katta/Kichik/To'liq (`SheetSvg` `registerZoom` bergan `zin/zout/reset`), Chop etish — belgilangan detalning navbatdagi CHIQARILMAGAN nusxasini GoDEX navbatiga yuboradi (dialogsiz); hammasi chiqarilgan bo'lsa yozilmaydi, "avval bekor qiling" xabari. Chop etish mutatsiyasi umumiy `usePrintLabel("cutmap")` hookida (`Terminal/usePrintLabel.ts` — PrisadkaView bilan baham ko'riladi), bekor qilish modul darajasidagi `useCancelLabel()` da (`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi).
- **Chek chiqarilgan = kesildi:** `isCut(i)` (`@/lib/mes` dan import — SheetSvg ham shu predikatni ishlatadi) — ARRA skan BOR yoki `label_printed_at` bor; statlar, list kartalari va kataklar shu o'lchovda. Xato chek: katakni long press (~600ms) — tasdiq dialogi ("Ha, bekor qilinsin" / "Yo'q"), skan qilingan nusxa himoyada. Hamma detali chiqarilgan list kartasi yashil tusda (`border-green-500/60 bg-green-50 text-green-700`).
- **Tanlash semantikasi:** xaritada detal bosilsa `markedCell` moviy bo'lib qoladi (kartochka yopilgandan keyin ham) — terminalda tap faqat belgilaydi, chop etish chap toolbardan; `admin` bo'lsa qo'shimcha ravishda `PartCard` dialogi ochiladi.
- `instancesByCell` — `useMemo` bilan `pattern_no:cell_index` kalitli Map; `sheetDone(s)` list to'liq kesilganini (har bir waste bo'lmagan katakning barcha instansiyalari `done`) hisoblaydi.
- **Eksportlar:** `CutmapView` va `TBtn` — `TBtn` (ikonka + `text-2xs` yozuv — `index.css` da 0.6875rem, `h-16`, `TBTN_TONES`: default/primary/warn/danger/success) `routes/terminal.tsx` da ham skan/sessiya tugmalari uchun ishlatiladi.
- `PartPreview` — tanlangan detal mini-chizmasi (276×190 viewBox): o'lcham strelkalari, `holes` dan yuza (`bores`) va qirra (`edge`) teshiklari masshtablangan holda, aylantirilgan detalda ⟳.
- `PartCard` dialogi: `PartPreview`, katta QR (`qrcode.react` `QRCodeSVG`, `next.qr_text`), o'lcham/kromka/yorliq raqami, instansiyalar ro'yxati (`✓ kesildi` / `✓ chek chiqarilgan`) va `h-12` "Yopish" tugmasi. Chiqarilgan (skan qilinmagan) nusxa yonida qizil "Chekni bekor qilish" (`admin` shartida) — proyekt ARRA ro'yxatidan tushib bo'lgach texnolog xato chekni shu yerdan tuzatadi. PartCard faqat admin rejimida ochiladi va unda chop etish tugmasi yo'q — terminalda chop etish yo'li chap toolbardagi "Chop etish".
- `printAllMaps` — barcha xaritalarni chop etish: `renderToStaticMarkup(<SheetSvg .../>)` bilan yangi oynaga yoziladi, har list o'z A4 landscape sahifasida (`@page size: A4 landscape`), "Material | №N — L × W mm" sarlavhasi bilan (listlar jismoniy nusxalarga yoyilgani uchun `× k list` yo'q); sahifadagi "PDF / Chop etish" tugmasiga `registerPrint` prop orqali ulanadi. `escapeHtml` bilan nom/raqam ekranlanadi.
- Xarita mavjud bo'lmasa (`data.model` yo'q — fayl GibLabda optimizatsiya qilinmagan, TEMPLATE) tushuntirish matni + "Orqaga" tugmasi.

### `frontend/src/components/Terminal/SheetSvg.tsx` (~710 qator)

**Maqsadi:** bitta listning to'liq SVG renderi — GibLabViewer'dan portlangan render qoidalari. `CutmapView` (interaktiv, thumbnail va print oqimi) ishlatadi.

**Props:** `sheet`, `holes`, `instancesByCell`, `onSelect(part)`, `selectedCell`, `thumbnail?`, `registerZoom?({zin,zout,reset})`, `onSwipe?("next"|"prev")`.

- **Eksport qilingan geometriya yordamchilari** (`CutmapView/PartPreview` ham ishlatadi): `holeXY(part, H, bx, by)` — teshik lokal koordinatasini katakka o'giradi (`p.rot` da o'q almashinuvi, oynasiz), `edgeLocalXY(H, side, pos)` — qirra teshigining lokal nuqtasi (t/b/l/r), `edgeBoreRect(part, cx, cy, d, dp)` — eng yaqin chetdan ichkariga to'rtburchak (uzunligi = burg'u chuqurligi).
- **Ranglar/qoidalar:** barcha detallar `#e88b00` (to'q apelsin), tanlangani `#2596be`, nostandart detal (`Part.is_custom` → barcha nusxalarida `custom` bayrog'i) kesilmagan holatda binafsha (`PART_CUSTOM = "#a78bfa"`), chek chiqarilgach odatdagidek yashil (`allDone` fondan ustun), bekor qilinsa yana binafsha; chegara barcha detallarda bir xil; atxot va list foni `zebra` pattern (`patternTransform rotate(45)`); kesim chiziqlari (`sheet.cuts`) qora `#242424`; yozuvlar halo'siz (to'q apelsin fonda kerak emas).
- **Zoom/pan/swipe (Pointer Events):** g'ildirak zoom kursor nuqtasiga (native `wheel` listener, `passive: false`), bir barmoq pan (zoomda) yoki gorizontal swipe → `onSwipe` bilan list almashtirish (>80px, <600ms), ikki barmoqli pinch. `setPointerCapture` **ataylab ishlatilmaydi** — u keyingi `click`ni SVG'ga retarget qilib detal tanlashni o'ldiradi. G'ildirak, pinch va toolbar tugmalari bitta `zoomAt(f, ax, ay)` yordamchisiga tushadi (tugmalar markaz atrofida 1.5x, `zoomBy`), zoom chegarasi ham shu yerda — `base.w/14`; `viewBox` `base` dan kichik bo'lsagina `vb` state saqlanadi, list almashsa (`sheet.no`) tiklanadi.
- **Yozuv joylashtirish:** har detal uchun eni/bo'yi (kromka kodlari bilan: `p.eH`/`p.eW`) va nom (`№num nom`, aylantirilganda ⟳, ko'p nusxada `done/total`) yoziladi; shrift o'lchami detal o'lchamidan hisoblanadi (cap 42 / 110), joy yetmasa faqat raqam qoladi yoki yozuv olib tashlanadi. Teshiklardan `obstacles` ro'yxati yig'ilib, har yozuv uchun bir necha nomzod joydan teshiksiz birinchisi tanlanadi (`pickSpot`) — tanlangan joy keyingi yozuvlarga ham to'siq, shuning uchun yozuvlar bir-birining va teshiklarning ustiga tushmaydi.
- **Tekstura yo'nalishi:** `p.txt` bo'lsa (va detal >60×40) matn ortida 3 ta gorizontal chiziq.
- **Teshiklar haqiqiy masshtabda:** `H.bores` — radiusi `d/2` doiralar, `H.edge` — `edgeBoreRect` to'rtburchaklari; hammasi `#fafafa` to'ldirish, `#202020` kontur.
- **O'lcham zanjirlari** (`sheet.dims`, `ax: "X"|"Y"`): chetda strelka, ichki chegarada kesim davomi + ✕ belgisi, o'rtada 44px qiymat; `PAD = 110` bilan viewBox'da siqilmaydi (assimetrik ramka — zanjir faqat tepa/chapda).
- Barcha nusxalari "kesilgan" (skan yoki chek chiqarilgan — `isCut`, `@/lib/mes`) katak YASHIL (`PART_DONE = "#22c55e"`, Tailwind green-500 — tizimdagi boshqa "bajarildi" belgilari bilan bir ton) to'ldiriladi — belgisiz; `onLongPress` prop berilsa katakni ~600ms bosib turish uni chaqiradi (12px siljish yoki pinch bekor qiladi, keyingi click yutiladi) — CutmapView bekor qilish dialogi uchun. `thumbnail` rejimda `pointer-events-none`.

### `frontend/src/components/Terminal/KromkaView.tsx`

**Maqsadi:** KROMKA/OVAL post sahifasi. Ikki panel: chapda arradan chiqqan (`arra_passed`), kromkasi tugamagan detallar (tugaganlari yashil bo'lib pastga tushadi), o'ngda "Jarayonda" — 2+ tomonli, boshlangan-u tugamagan nusxalar. Detal nomi ostida `Common/OperationChips` — noodatiy marshrutli detalda shu postga tegishli amal nomi chiplari (postCode: `oval ? "OVAL" : "KROMKA"`). Har skan darhol yoziladi (tomon = skan); `registerScan` prop orqali terminalga lokal tekshiruv beradi (`null` = yozish mumkin, `"NOTFOUND"` = bu proyektda yo'q, boshqa string = xato matni: arradan chiqmagan / allaqachon tugagan). `oval` prop: bir panel, tomonlar ustuni yo'q, har detal bitta skan. Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + markazga avto-scroll (`useScanFlash` hooki — xuddi shu mexanizm `routes/terminal.tsx` vazifalar jadvalida ham). Ma'lumot: `readTerminalKromka` (`refetchInterval: 30_000` + har skanda invalidatsiya).

### `frontend/src/components/Terminal/PrisadkaView.tsx`

**Maqsadi:** PRISADKA va ROVER post sahifasi (TZ 12.5): detallar + SCX fayllari, "Hammasini yuklab olish" tugmasi. Props: `orderId`, `onBack`, `showScx?` (default `true`; `routes/terminal.tsx` ROVER postida `false` beradi — SCX fayllar kerak emas), `toolbarContainer?` (ROVER "Chop etish" tugmasi terminalning umumiy chap ustuniga portal qilinadi). Ma'lumot: `readTerminalPrisadka` (`refetchInterval: 30_000`).

- SCX oqimi (`showScx`): `lib/scxDir.ts` bilan — File System Access API `showDirectoryPicker` BIR MARTA, tanlangan papka IndexedDB'da (`mebelix-terminal/kv/scx-dir`), keyingi yuklab olishlar so'roqsiz; papka ichida proyekt nomli subpapka (`project_name`, taqiqlangan belgilar `_` ga) ochilib fayllar shu yerga yoziladi (URL — `scxFileUrl(id)`). API bo'lmasa `<a download>` fallback. Har skandagi avto-SCX ham saqlangan papkaga tushadi. Yuklab olishda tugmada jonli progress ("Yuklanmoqda… 12/81"); papka tugmasi yozuvli ("Papka" — sensorli ekranda hover yo'q).
- Jadval ish-navbat tartibida: qilinmaganlar tepada, tugaganlar (✓ yashil) pastda; oxirgi skan bo'lgan qator KEYINGI skangacha amber ajralib turadi va markazga avto-scroll bo'ladi (`useScanFlash` hooki — `done` o'zgargan qatorni topadi: lokal skan ham, stanokdan skan-forvard ham). Har SCX fayl chipi bitta nusxaga mos (fayl nomi = QR): QR'i `done_qrs` da bo'lsa chip yashil ✓ — operator qaysi nusxalar qolganini ko'radi.
- **QR chekni chiqarish** (`usePrintLabel("prisadka")`): marshrutida ARRA bo'lmagan (`arra_route=false`) detal jarayonni shu postdan boshlaydi — cheki shu yerdan chiqariladi. ROVER rejimida (`showScx=false`) qator (nusxa) tanlanadi va chapdagi katta "Chop etish" `TBtn` (portal) bosiladi; PRISADKA rejimida chek chiqarish tugmasi instansiya chipining ichida (printer ikonkasi, faqat `!done && !label_printed && !arra_route` nusxalarda).

### `frontend/src/components/Terminal/PostQueueView.tsx`

**Maqsadi:** BOYOQ va STOLYARKA post sahifasi — NUSXA darajasidagi navbat (`readTerminalPostQueue`, `refetchInterval: 30_000`). Umumiy "Navbatdagi vazifalar" jadvali detal darajasida agregat berardi ("qoldiq 6/6") va navbatni hisobga olmasdi: operator hali arradan chiqmagan detalni ko'rib, skanerlab E004 olardi.

- Uch guruh: **kelgan** (`ready && !done`) — asosiy ish ro'yxati; **bajarilgan** (`done`, yashil ✓); yetib KELMAGANLARI ro'yxatda umuman ko'rsatilmaydi, faqat "yana N detal sexda" satri (ularni skanerlab bo'lmaydi, izlash ham vaqt yo'qotish).
- Sarlavhalar postga moslanadi (`LABELS`: BOYOQ → "Bo'yashga kelgan"/"Bo'yalgan", STOLYARKA → "Stolyarkaga kelgan"/"Bajarilgan").
- Qatorda: QR (yirik), detal nomi, **material** (bo'yoqchi uchun bu RANG — amber), texnolog izohi, `Common/OperationChips` (stolyarkada olti xil amal, noto'g'ri petlya eshikni brak qiladi), yig'ma buyum biriktirilgan mayda detallari (`+ 01_007 ×2`), o'lcham va oxirgi bajarilgan bosqich.
- Skan alohida yo'l talab qilmaydi — terminalning umumiy skan mutatsiyasidan o'tadi, qator `done` bo'lib pastga tushadi.

### `frontend/src/components/Terminal/UpakovkaView.tsx`

**Maqsadi:** QADOQLASH post sahifasi. Chapda ochiq qadoq (kod, detallar soni, `~kg` — taxminiy, bloklamaydi), o'ngda "Qadoqlanmagan" va "Yakunlangan". Oqim: "Qadoq yaratish" → detallarni birma-bir skanerlash → "Qadoqni yakunlash" (chek QR bilan chiqadi). Har qatorda o'chirish tugmasi — xato skan qaytariladi va UPAKOVKA skani ham bekor bo'ladi. `registerScan` prop orqali terminalga skan qabul qiluvchi beradi: detal qaysi QADOQqa tushishini faqat shu ekran biladi.

### `frontend/src/components/Terminal/OmborView.tsx`

**Maqsadi:** OMBOR post sahifasi, ikki tab (ikki xil ish bir ekranda aralashmasin).

- **Qabul** — omborga yetib kelganlar (qadoq kodi bilan), skan `PK-...` bo'lsa qadoq ichidagi hammasini birdan qabul qiladi. Pastda "Sexda" ro'yxati: har detalga ishi TUGAGAN post yozilgan (`stage`) — omborchi buyumni aynan o'sha yerdan topadi.
- **Topshirish** — qadoqlangan buyurtmada har qadoq alohida (to'liq qabul qilinmagani bloklangan), qadoqsizda bitta "Buyurtmani topshirish" tugmasi.
- `registerScan` aktiv tabga qarab qabul yoki topshirishga yo'naltiradi.

### `frontend/src/components/Terminal/usePrintLabel.ts`

**Maqsadi:** yorliq chop etish mutatsiyasi — `CutmapView` (ARRA xaritasi) va `PrisadkaView` (ROVER/PRISADKA) baham ko'radi: `TerminalService.printInstanceLabel` + toast + `handleError`; `scope` ("cutmap" | "prisadka") qaysi terminal keshi (`["terminal", scope]`) yangilanishini belgilaydi.

### `frontend/src/components/Terminal/audio.ts`

**Maqsadi:** skan ovoz signallari (TZ 8.4.3, sex shovqinida majburiy) — WebAudio, internetsiz ishlaydi: `playSuccess` (600 Hz qisqa), `playError` (200 Hz uzun), `playWarning` (2×800 Hz). `routes/terminal.tsx` da skan natijasiga qarab chalinadi.

---

## UserSettings komponentlari — `frontend/src/components/UserSettings/`

`/settings` sahifasining bo'limlari (joriy foydalanuvchining o'z profili, `*Me` endpointlari).

**O'z hisobini o'chirish UI'da yo'q:** `DeleteAccount.tsx` olib tashlangan, `routes/_layout/settings.tsx` da `tabsConfig` faqat ikkita band beradi ("Profilim", "Parol"). Backend endpointi (`DELETE /users/me` — `backend/app/api/routes/users.py`) va generatsiya qilingan `UsersService.deleteUserMe` (`frontend/src/client/sdk.gen.ts`) saqlanib qolgan, lekin `frontend/src` da uni chaqiradigan joy yo'q.

### `frontend/src/components/UserSettings/UserInformation.tsx`

**Maqsadi:** profil ma'lumotlari (ism, telefon) — ko'rish/tahrirlash rejimi almashinadigan forma.

- `editMode` state: o'qish rejimida qiymatlar `<p>` sifatida (bo'sh ism — "—"), "Tahrirlash" tugmasi; tahrirlash rejimida `Input` lar, "Saqlash" (`disabled={!form.formState.isDirty}`) va "Bekor qilish" (`form.reset()` + rejimdan chiqish).
- `onSubmit` faqat o'zgargan maydonlarni `UserUpdate` payloadga qo'shadi va `UsersService.updateUserMe` ni chaqiradi; muvaffaqiyatda `form.reset(form.getValues())` va `["currentUser"]` invalidatsiyasi (kalitsiz chaqiruv butun ilova querylarini qayta so'rardi).

### `frontend/src/components/UserSettings/ChangePassword.tsx`

**Maqsadi:** parolni o'zgartirish formasi.

- zod: `current_password`, `new_password` (`passwordSchema`), `confirm_password` + mos kelish refine'i; `mode: "onSubmit"`.
- Mutation: `UsersService.updatePasswordMe({ requestBody })`; muvaffaqiyatda toast + `form.reset()`.
- Uchchala maydon `PasswordInput` (ko'rish/yashirish ko'zchali) bilan, `aria-invalid={fieldState.invalid}` uzatiladi.

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
| `loading-button.tsx` | LoadingButton (`ButtonProps` — fayl ichida, eksport emas) | `buttonVariants` (button.tsx dan import) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | `Input` + Button | **To'liq custom** (pastda) |
| `popover.tsx` | Popover, PopoverTrigger, PopoverContent | Radix Popover | Deyarli standart (`rounded-xl`, `p-3`, `align="start"`) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 10 ta eksport | Radix Select | Yo'q |
| `separator.tsx` | Separator | Radix Separator | Yo'q |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 24 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
| `switch.tsx` | Switch | Radix Switch | Yo'q (terminaldagi "Faqat xatolar" filtri, `employees.tsx` hodim dialogidagi AKTIV/NOFAOL va `printers.tsx` dagi chek chiqarish `can_print` almashtirgichi) |
| `table.tsx` | Table, TableHeader/Body/Footer/Row/Head/Cell/Caption | native table | **Stil custom**: konteyner `rounded-lg border`, TableHeader `bg-muted/50`, TableHead `h-11 text-xs font-semibold uppercase tracking-wider`, TableCell `px-4 py-3 whitespace-nowrap` |
| `tabs.tsx` | Tabs, TabsList, TabsTrigger, TabsContent | Radix Tabs | Yo'q |
| `textarea.tsx` | Textarea | native `<textarea>` | Yo'q (standart shadcn; anketa "Qo'shimcha izoh" maydoni uchun qo'shilgan) |
| `tooltip.tsx` | Tooltip, TooltipTrigger/Content/Provider | Radix Tooltip | Yo'q (delayDuration=0) |

### `frontend/src/components/ui/sidebar.tsx` (custom tafsilotlari)

Eng katta ui fayl (~740 qator, 24 eksport). shadcn'ning rasmiy sidebar blokiga asoslangan, quyidagi o'zgarishlar bilan:

- **Cookie'dan boshlang'ich holatni o'qish**: standart shadcn faqat cookie'ga *yozadi*; bu yerda `getInitialOpen()` funksiyasi `sidebar_state` cookie'sini o'qib, sahifa yangilanganda ochiq/yopiq holatni tiklaydi (`useState(getInitialOpen)` lazy initializer).
- `SidebarTrigger` sr-only matni dinamik va o'zbekcha: `open ? "Menyuni yig'ish" : "Menyuni ochish"`; mobil `Sheet` ning sr-only sarlavhasi "Yon menyu", tavsifi "Mobil yon menyu".
- `sidebarMenuButtonVariants` o'lchamlari brendga moslangan: `default: "h-8 text-sm rounded-lg"`, `lg: "... rounded-xl data-[state=closed]:rounded-lg"`.
- `SidebarHeader` (`p-2 pb-3`) va `SidebarFooter` (`gap-3 p-2`) padding'lari sozlangan; `SidebarInset` `bg-transparent`.
- Muhim konstantalar: `SIDEBAR_WIDTH = "16rem"`, `SIDEBAR_WIDTH_ICON = "3rem"`, `SIDEBAR_WIDTH_MOBILE = "18rem"`, klaviatura yorlig'i **Ctrl/Cmd+B** (`SIDEBAR_KEYBOARD_SHORTCUT = "b"`).
- Mobil rejimda `Sheet` ichida render qilinadi (`useIsMobile` — `@/hooks/useMobile`); `useSidebar()` hooki `{ state, open, setOpen, openMobile, setOpenMobile, isMobile, toggleSidebar }` kontekstini beradi — `Sidebar/Main.tsx` va `Sidebar/User.tsx` shundan foydalanadi.

### `frontend/src/components/ui/loading-button.tsx` (custom)

shadcn'da yo'q, loyihaga qo'shilgan komponent. `buttonVariants` ni `button.tsx` dan import qiladi (BITTA manba — avvalgi copy-paste nusxa divergensiya bergani uchun birlashtirilgan; `icon-sm`/`icon-lg` o'lchamlari ham ishlaydi) va ustiga `loading` prop qo'shadi.

```tsx
function LoadingButton({ loading = false, disabled, asChild = false, ... }: ButtonProps)
// loading=true -> disabled + <Loader2 className="mr-2 h-5 w-5 animate-spin" />
```

Barcha mutation submit tugmalarida ishlatiladi (AddUser, EditUser, AddClient, AddOrder, EditOrder, MachineAssign, OrderMatrix, CutmapView, ConfirmDialog, ChangePassword, UserInformation, login formasi, anketa saqlash paneli, employees hodim formalari, machines stanok formasi, buyurtma sahifasi amallari, printers agent qo'shish formasi) va uzoq davom etadigan amallarda — `PrisadkaView` dagi SCX "Hammasini yuklab olish" tugmasi jonli progress yozuvi bilan ("Yuklanmoqda… 12/81").

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `ui/input` ni compose qiladi (`pr-10` bilan), o'ng tomonida ghost `Button size="icon-sm"` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi; aria-label "Parolni yashirish/ko'rsatish"). `React.ComponentProps<"input">` propslarini o'tkazadi (forwardRef yo'q — React 19 uslubi); `aria-invalid` ni chaqiruvchi o'zi uzatadi. `UserSettings/ChangePassword.tsx` va `routes/login.tsx` da ishlatiladi (Admin formalarida esa oddiy `Input type="password"`).

### `frontend/src/components/ui/date-picker.tsx` (custom)

shadcn'da yo'q, to'liq loyihaga yozilgan o'zbekcha sana tanlagich: `react-day-picker` (`uz` locale) + `Popover`. Qiymati form/API bilan mos `"YYYY-MM-DD"` satr, ko'rinishi `DD.MM.YYYY`; tanlangach trigger yonida ALOHIDA "X" tozalash tugmasi (aria-label "Sanani tozalash" — trigger ichida emas: tugma ichida tugma yaroqsiz HTML edi, tab bilan yetib bo'lmasdi), kalendar ostida "Bugun"/"Tozalash" tugmalari. Props: `value`, `onChange`, `placeholder?`, `className?` (trigger tugma kengligi uchun — masalan anketada `w-full`), `aria-label?` (`<Field>` ichida ko'rinadigan label bo'lmaganda). Buyurtma deadline'i (`Orders/orderForm.tsx` — `AddOrder`/`EditOrder`), hisobot oralig'i (`routes/_layout/reports.tsx`), loglar sana filtri (`routes/_layout/logs.tsx`) va anketa o'lchov sanasi (`routes/_layout/anketa.$orderId.tsx`) uchun ishlatiladi — jami to'rtta chaqiruvchi.

---

## Bog'lanishlar xulosasi

```
routes (_layout sahifalar)                      routes (terminal / cutmap)
  ├─ PageHeader / StatusBadge / StagePipeline     ├─ CutmapView + TBtn
  ├─ SearchInput / EmptyRow / QueryError          │    ├─ SheetSvg (zoom/pan/swipe,
  ├─ AddOrder / EditOrder ─ orderForm             │    │    dims, teshiklar, thumbnail)
  │        ├─ ClientCombobox                      │    └─ PartCard → PartPreview + QR
  │        └─ AddClient (inline)                  ├─ KromkaView / PrisadkaView
  ├─ MachineAssign / OrderMatrix / CustomRoutes   │    ├─ OperationChips
  └─ admin.tsx: ui/table + UserRow                │    └─ usePrintLabel
       │    (isLoading → Skeleton)                └─ audio (playSuccess/Error/Warning)
       ├─ AddUser ─┐
       └─ UserActionsMenu ─ EditUser ─┴─ UserForm (umumiy schema+maydonlar)
                          └ DeleteUser ─ ConfirmDialog

routes/_layout/anketa.$orderId (sahifa ichidagi komponentlar)
  ├─ Section / Field / Num / NumInput / CheckGrid / Choice / ShapeChoice
  ├─ RoomPhotos (drag&drop + Dialog preview)
  ├─ RoomSummary (room + survey) → Facts (canEdit=false ko'rinishi)
  └─ ConfirmDialog (xona o'chirish) · DatePicker · Textarea · LoadingButton

routes (settings)                               routes (__root / layout)
  ├─ UserInformation                              ├─ SidebarProvider (ui/sidebar)
  └─ ChangePassword                               ├─ AppSidebar (NAV_ITEMS eksporti)
                                                  │    ├─ Main (rolga qarab bandlar)
                                                  │    └─ User (avatar + logout)
                                                  └─ NotFound / ErrorComponent

Tashqi bog'liqliklar: @/client (UsersService, ClientsService, OrdersService, TerminalService va
User*/Client*/Order*/Post* model turlari), @/queries/mes (getClients/getMachines/getPosts/
getOrderMatrixQueryOptions/getOrderQueryOptions va h.k.; PAGE_SIZE, crudCallbacks),
@/queries/users (getUsersQueryOptions — barcha sahifalarni bitta ro'yxatga yig'adi, `admin.tsx`;
getCurrentUserQueryOptions — `useCurrentUser` va `tablo.tsx` shundan foydalanadi), @/lib/mes (ROLE_LABELS, PRIORITY_LABELS,
PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES, POST_COLORS,
ORDER_STATUS_LABELS/COLORS, chipColors/mixTint, isCut, PROCESS_OPS (14 amal kodi →
nom+post; OperationChips va CustomRoutes ishlatadi), STANDARD_MATRIX_POSTS,
ROUTE_START_POSTS, isAdmin/isSuperuser/isManagement/isProductionStaff,
MACHINE_BOUND_ROLES, TERMINAL_STATUSES, formatSize),
@/hooks (useAuth, useCurrentUser, useMobile, useDebounced, useScanFlash), sonner (toast),
@/lib/validation (zod schema'lar, formatMoneyInput, formatUzPhone), @/lib/utils (cn),
@/lib/anketa (variant kataloglari, labelOf/labelsOf), @/lib/scxDir (papka + scxFileUrl),
@/utils (handleError, getInitials).
```
