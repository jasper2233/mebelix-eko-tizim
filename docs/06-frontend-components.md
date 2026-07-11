# Frontend Components (Admin, Clients, Common, Orders, Pending, Sidebar, Terminal, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini qamrab oladi. Stack: React + TypeScript, TanStack Router/Query/Table, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService, ClientsService, OrdersService, TerminalService va model turlari) orqali gaplashadi; umumiy query'lar `@/queries/mes` dagi `queryOptions` fabrikalarida (getClients/getMachines/getPosts/getOrderMatrixQueryOptions va h.k.), domen konstantalari `@/lib/mes` da (ROLE_LABELS, PRIORITY_LABELS, POST_COLORS, ORDER_STATUS_LABELS/COLORS, formatSize); toast xabarlari `useCustomToast` hooki, xatoliklar `handleError` utiliti orqali ko'rsatiladi.

Umumiy naqsh (pattern): **forma → zod schema → react-hook-form → useMutation → @/client servisi → toast + query invalidation**. Barcha UI matnlari o'zbek tilida.

---

## Admin komponentlari — `frontend/src/components/Admin/`

Admin panel (`/admin` route) uchun foydalanuvchilarni CRUD boshqarish komponentlari.

### `frontend/src/components/Admin/AddUser.tsx`

**Maqsadi:** yangi foydalanuvchi yaratish dialogi (o'zining trigger tugmasi bilan).

- `formSchema` — zod: `phone` (`phoneSchema`), `name` (`optionalNameSchema`), `password` (`passwordSchema`), `confirm_password`, `role` (12 qiymatli enum: admin, director, manager, texnolog, terminal, tablo, arrachi, kromkachi, prisadkachi, pazchi, roverchi, stolyar), `machine_id` (ixtiyoriy), `is_superuser`, `is_active`; ikkita `.refine()`: terminal/tablo roliga stanok majburiy ("Terminal/TABLO uchun stanok tanlang") va parollar mosligi ("Parollar mos emas").
- Default qiymatlar: `role: "manager"`, `is_superuser: false`, `is_active: true` — yangi foydalanuvchi darhol tizimga kira oladi.
- Rol `Select` `ROLE_LABELS` (`@/lib/mes`) dan to'ldiriladi; rol terminal yoki tablo bo'lsa shartli "Stanok" `Select` chiqadi (`getMachinesQueryOptions()` — `@/queries/mes`); submitda `machine_id` `Number` ga o'giriladi (bo'sh bo'lsa `null`).
- Mutation: `UsersService.createUser({ requestBody })`; muvaffaqiyatda toast, forma reset, dialog yopiladi; `onSettled` da `["users"]` query invalidatsiya qilinadi.
- Forma `mode: "onBlur"` rejimida validatsiya qiladi; trigger — `<Plus /> Foydalanuvchi qo'shish` tugmasi.
- Submit tugmasi `LoadingButton` (`loading={mutation.isPending}`).

**Bog'lanishlar:** `@/lib/validation` (schema'lar), `@/lib/mes` (ROLE_LABELS), `@/queries/mes` (getMachinesQueryOptions), `@/hooks/useCustomToast`, `@/utils` (`handleError`), ui: `dialog`, `form`, `input`, `select`, `checkbox`, `button`, `loading-button`. Admin route sahifasidan chaqiriladi.

### `frontend/src/components/Admin/columns.tsx`

**Maqsadi:** foydalanuvchilar jadvali uchun TanStack Table ustun ta'riflari.

- Eksport: `UserTableData = UserRead & { isCurrentUser: boolean }` va `columns: ColumnDef<UserTableData>[]`.
- Ustunlar: `name` (bo'sh bo'lsa "—", joriy foydalanuvchiga "Siz" badge), `phone`, `role` → "Rol" Badge (superuser bo'lsa "Admin", aks holda `ROLE_LABELS[role]`, topilmasa xom qiymat; variant: admin uchun `default`, qolganlarga `secondary`), `is_active` → yashil/kulrang nuqta + "Faol"/"Faol emas", `actions` → o'ngga tekislangan `UserActionsMenu`.

**Bog'lanishlar:** `Common/DataTable.tsx` ga uzatiladi; `UserActionsMenu` ni render qiladi; `ui/badge`, `ROLE_LABELS` (`@/lib/mes`), `cn` (`@/lib/utils`).

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

- zod: `full_name` (min 2 belgi), `phone`/`phone_alt` (`optionalFormattedPhoneSchema`), `address`, `notes`; telefon inputlari yozish paytida `formatUzPhone` bilan "+998 90 123 45 67" ko'rinishida maskalash qiladi.
- Props: `trigger?` (default "+ Yangi mijoz" tugmasi o'rniga istalgan React node) va `onCreated?(client)` — `Orders/AddOrder` shulardan foydalanib mijozni inline yaratadi va selectda avtomatik tanlaydi.
- Mutation: `ClientsService.createClient`; muvaffaqiyatda toast, reset, dialog yopilib `onCreated?.(client)` chaqiriladi; `["clients"]` invalidatsiyasi.

---

## Common komponentlari — `frontend/src/components/Common/`

### `frontend/src/components/Common/AuthLayout.tsx`

**Maqsadi:** login sahifasi uchun ikki ustunli layout.

- Chap ustun (faqat `lg:` da): navy gradient (`#2f496e → #1c2e49`) fon, markazda oltin `logo-gold.png`, burchakda katta shaffof `icon-gold.png` watermark (opacity 0.09).
- O'ng ustun: markazlangan `max-w-md` forma konteyneri (`children`), pastda `Footer`; mobil ko'rinishda navy watermark (`icon-navy.png`).
- Hozircha yagona auth route — `routes/login.tsx` shu layout bilan o'raladi (signup route yo'q).

### `frontend/src/components/Common/ConfirmDialog.tsx`

**Maqsadi:** umumiy "Ishonchingiz komilmi?" (controlled) dialog. Trigger va `open` holati chaqiruvchiga tegishli — trigger tugma, menyu bandi yoki boshqa narsa bo'lishi mumkin; komponent faqat modal tanasini chizadi.

- Props: `open`, `onOpenChange`, `title`, `description?`, `confirmText?` (default "Tasdiqlash"), `cancelText?` (default "Bekor qilish"), `destructive?`, `loading?`, `onConfirm`.
- Tasdiqlash tugmasi `LoadingButton` (`variant={destructive ? "destructive" : "default"}`).

**Foydalanuvchilari:** `Admin/DeleteUser.tsx`, `UserSettings/DeleteAccount.tsx`.

### `frontend/src/components/Common/DataTable.tsx`

**Maqsadi:** umumiy (generic) TanStack Table jadvali — client-side pagination bilan.

- Signature: `function DataTable<TData, TValue>({ columns, data }: DataTableProps<TData, TValue>)`.
- `useReactTable` + `getCoreRowModel` + `getPaginationRowModel`; bo'sh natijada "Natija topilmadi." qatori.
- Pagination paneli faqat `getPageCount() > 1` bo'lsa chiqadi: "X dan Y gacha, jami N" hisoblagichi, sahifa hajmi `Select` (5/10/25/50), "Sahifa X / Y" va to'rtta navigatsiya tugmasi (birinchi/oldingi/keyingi/oxirgi, sr-only labellar bilan).

**Bog'lanishlar:** `Admin/columns.tsx` bilan admin sahifasida ishlatiladi; ui: `table`, `select`, `button`.

### `frontend/src/components/Common/ErrorComponent.tsx`

**Maqsadi:** routerning global xato ekrani ("Xato / Voy!" + "Xatolik yuz berdi..." matni + "Bosh sahifaga" tugmasi, `Link to="/"`).

### `frontend/src/components/Common/Footer.tsx`

**Maqsadi:** oddiy footer — `MebeliX - {joriy yil}`. `AuthLayout` ichida ishlatiladi.

### `frontend/src/components/Common/NotFound.tsx`

**Maqsadi:** 404 ekrani — `ErrorComponent` bilan bir xil tuzilish, "404 / Voy!" + "Siz qidirayotgan sahifa topilmadi." matni. Router'ning `notFoundComponent` sifatida ulanadi.

### `frontend/src/components/Common/PageHeader.tsx`

**Maqsadi:** sahifa sarlavhasi — `title`, ixtiyoriy `description` va o'ng tomonda `actions` slot. Barcha `_layout` sahifalarida ishlatiladi (dashboard, orders, clients, employees, machines, materials, reports, transactions, logs).

### `frontend/src/components/Common/StagePipeline.tsx`

**Maqsadi:** 6 bosqichli ishlab chiqarish pipeline'i (TZ 4.4) — ulangan progress kataklar zanjiri, loyihaning "signature" vizual elementi.

- Props: `stages: StageCell[]` (`{ code, done, total }`) va `compact?`; har katak `POST_COLORS[code]` rangida (`color-mix` fon + foizli progress chizig'i), tugallanganda "✓", compact rejimda kod'ning bosh 2 harfi.
- Dashboard'da (`routes/_layout/index.tsx`) ishlatiladi; xuddi shu vizual grammatika `Orders/OrderMatrix` va TABLO ekranida takrorlanadi.

### `frontend/src/components/Common/StatusBadge.tsx`

**Maqsadi:** buyurtma holati pill'i — `ORDER_STATUS_LABELS`/`ORDER_STATUS_COLORS` (`@/lib/mes`) asosida rangli nuqta + matn. Dashboard, buyurtmalar ro'yxati/sahifasi va hisobotlarda ishlatiladi.

---

## Orders komponentlari — `frontend/src/components/Orders/`

Buyurtma sahifalari (`/orders`, `/orders/$orderId`) uchun dialog va jadval komponentlari.

### `frontend/src/components/Orders/AddOrder.tsx`

**Maqsadi:** yangi buyurtma dialogi ("+ Yangi buyurtma") — raqamni tizim beradi (B-YYYY-NNN), fayl keyin texnolog tomonidan yuklanadi.

- zod: `client_id` (majburiy), `deadline?`, `priority` enum (low/medium/high/urgent, default medium, `PRIORITY_LABELS`), `amount` (majburiy), `advance_payment?`, `notes?`; `.refine()` — boshlang'ich to'lov umumiy narxdan oshmasligi kerak.
- Mijoz `Select` (`getClientsQueryOptions`) yonida inline `Clients/AddClient` (`+` icon trigger, `onCreated` yangi mijozni avtomatik tanlaydi); deadline — `ui/date-picker` DatePicker; pul maydonlari `formatMoneyInput` bilan ming ajratkichli.
- Mutation: `OrdersService.createOrder`; muvaffaqiyatda toast va yangi buyurtma sahifasiga `navigate`.

### `frontend/src/components/Orders/EditOrder.tsx`

**Maqsadi:** buyurtmani tahrirlash dialogi (manager) — AddOrder bilan bir xil schema/maydonlar, qiymatlar `values:` orqali `order` dan olinadi.

- Mijoz select `disabled={!isDraft}` — DRAFT dan keyin mijoz almashtirilmaydi ("faqat qoralamada almashtiriladi"; backend ham shu qoidani ushlaydi).
- Mutation: `OrdersService.updateOrder`; muvaffaqiyatda `onSaved()` callback.

### `frontend/src/components/Orders/MachineAssign.tsx`

**Maqsadi:** stanok tanlovi paneli (TZ 6.4.1) — `requires_assignment_choice` bo'lgan postlar uchun aniq manager tanlovi.

- Har post uchun `POST_COLORS` rangli sarlavha + faol stanoklar selecti (`getPostsQueryOptions` + `getMachinesQueryOptions`); `OrdersService.assignOrderMachines` ga saqlanadi; tanlov talab qiluvchi post bo'lmasa `null` qaytaradi.

### `frontend/src/components/Orders/OrderMatrix.tsx`

**Maqsadi:** texnolog matritsasi (TZ 6.3.3) — qatorlar: detallar, ustunlar: 6 post.

- O'qish rejimida har katak `total_done/total_required` progress (`POST_COLORS`, tugallanganda "✓"), o'chirilgan bosqich "—"; `editable` bo'lsa "Marshrutni tahrirlash" rejimi: bosqich checkboxlari (ARRA majburiy — TZ 5.4.1, checkbox locked) + izoh inputlari, `OrdersService.editOrderMatrix` ga batch saqlanadi.
- Ma'lumot: `getOrderMatrixQueryOptions(orderId)`; o'lchamlar `formatSize` (`@/lib/mes`) bilan.

---

## Pending — `frontend/src/components/Pending/PendingUsers.tsx`

**Maqsadi:** foydalanuvchilar jadvali yuklanayotganda ko'rsatiladigan skeleton holati.

- Haqiqiy jadval bilan bir xil sarlavhalar (To'liq ism, Telefon, Rol, Holat, sr-only Amallar) va 5 ta qator; har katakda mos o'lchamli `Skeleton` (badge uchun `rounded-full`, holat nuqtasi uchun `size-2` va h.k.) — layout shift bo'lmasligi uchun `Admin/columns.tsx` tuzilishini aks ettiradi.
- Admin sahifasida `useSuspenseQuery` ishlatilgani uchun `<Suspense fallback={<PendingUsers />}>` sifatida render qilinadi (`isLoading` tekshiruvi emas).

---

## Sidebar komponentlari — `frontend/src/components/Sidebar/`

Claude.com uslubidagi yon panel: trigger sidebar ichida, alohida app header/footer yo'q (qarang: commit tarixi).

### `frontend/src/components/Sidebar/AppSidebar.tsx`

**Maqsadi:** ilovaning asosiy yon paneli — brend, navigatsiya va foydalanuvchi menyusini yig'adi.

- `navItems(role, isSuperuser)` funksiyasi (TZ 3.7 rollar-modullar matritsasi) 11 tagacha punkt quradi (`admin = is_superuser || role === "admin"`): Boshqaruv paneli `/` va LIVE Tablo `/tablo` — hammaga; Buyurtmalar `/orders`, Stanoklar `/machines`, Materiallar `/materials` — admin/manager/texnolog/director; Mijozlar `/clients`, Hodimlar `/employees`, Hisobotlar `/reports` — admin/manager/director; Tranzaksiyalar `/transactions` — admin/director; Foydalanuvchilar `/admin` va Logs `/logs` — faqat admin. **Rolga qarab navigatsiya**.
- `<Sidebar collapsible="icon">`: yig'ilganda faqat ikonkalar qoladi. Header'da `Link to="/"` (logo `icon-gold.png` + "MebeliX" yozuvi, yig'ilganda `group-data-[collapsible=icon]:hidden` bilan yashiriladi) va `SidebarTrigger` (yig'ilgan railda yolg'iz qoladi).
- `SidebarContent` → `Main items={items}`; `SidebarFooter` → `User user={currentUser}`.

**Bog'lanishlar:** `@/hooks/useCurrentUser`, `ui/sidebar.tsx`, `Sidebar/Main.tsx`, `Sidebar/User.tsx`. Layout route ichida `SidebarProvider` + `SidebarInset` bilan ishlatiladi.

### `frontend/src/components/Sidebar/Main.tsx`

**Maqsadi:** navigatsiya menyusi ro'yxati.

- Eksport: `type Item = { icon: LucideIcon; title: string; path: string }` va `Main({ items })`.
- `useRouterState()` dan `currentPath` olinib `isActive = currentPath === item.path` aniqlanadi; aktiv bandda chapdan 3px oltin chiziq: `data-[active=true]:shadow-[inset_3px_0_0_0_var(--sidebar-primary)]`.
- Har band `SidebarMenuButton tooltip={item.title} asChild` ichida `RouterLink`; mobil rejimda bosilganda `setOpenMobile(false)` bilan panel yopiladi.

### `frontend/src/components/Sidebar/User.tsx`

**Maqsadi:** sidebar footeridagi foydalanuvchi kartasi va dropdown menyusi.

- Ichki `UserInfo({ fullName, phone })` — brend ranglaridagi `Avatar` (`bg-[#f0a52f]` oltin fon, `#1c2b42` navy matn) + `getInitials()` (`@/utils`) initsiallari, ism va telefon.
- `User({ user })`: `user` bo'lmasa `null`. `SidebarMenuButton size="lg"` trigger → `DropdownMenu` (`side`: mobil bo'lsa "bottom", aks holda "right"): `DropdownMenuLabel` da yana `UserInfo`, so'ng "Sozlamalar" (`RouterLink to="/settings"`) va "Chiqish" (`useAuth().logout()`).
- Kamchilik sifatida qayd: `user: any` tipi ishlatilgan (`UserRead` emas).

---

## Terminal komponentlari — `frontend/src/components/Terminal/`

### `frontend/src/components/Terminal/CutmapView.tsx` (~1160 qator)

**Maqsadi:** ARRA kesish xaritasi (TZ 7.1.7) — GibSaw-parity ekran, GibCut litsenziyasi o'rnini bosadi. `routes/terminal.tsx` (operator) va `routes/_layout/cutmap.$orderId.tsx` (admin) ishlatadi; `admin` prop'ga qarab `OrdersService.readOrderCutmap` yoki `TerminalService.readTerminalCutmap` (60s refetch).

- Chap panel: materiallar ro'yxati (har birida bajarilgan/jami list hisobi) + GibSaw uslubidagi 9 katakli statistika (KK/KD/KO/DR/KR/PZ/TP/TD/TSh — listlar, detallar, atxot, rez metri/soni, to'ldirish %, arra qalinligi, tirim) + zich listlar ro'yxati (×mult, ✓ belgilar).
- `SheetSvg` — to'liq list SVG: g'ildirak zoom (kursor nuqtasiga), pan va ikki barmoqli pinch (Pointer Events); halo-konturlangan yorliqlar, atxot uchun zebra pattern, `sheet.dims` root-strip **o'lcham zanjirlari** (strelka/extension chiziqlar bilan), teshik (bore) va yon (edge-bore) overlaylar real masshtabda.
- `PartCard` dialogi: detal eskizi (`PartPreview`), katta QR (`qrcode.react`, qr_text bilan) va har instansiya uchun "YORLIQ CHOP ETISH" — PNG yorliq yangi tabda ochiladi (`/api/v1/terminal/labels/{id}.png`, istalgan printerga) + parallel GoDEX navbatiga yuboriladi (`TerminalService.printInstanceLabel`).
- `printAllMaps` — barcha xaritalarni chop etish: har list o'z A4 landscape sahifasida, "Material | №N — L × W mm × k list" sarlavhasi bilan; sahifadagi "PDF / Chop etish" tugmasiga `registerPrint` prop orqali ulanadi.

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

**Maqsadi:** "xavfli zona" — o'z hisobini butunlay o'chirish.

- Qizil hoshiyali karta (`border-destructive/50`), "Hisobni o'chirish" destructive tugmasi → `ConfirmDialog` (destructive, "O'chirish").
- Mutation: `UsersService.deleteUserMe()`; muvaffaqiyatda toast va `useAuth().logout()` (sessiya tugatiladi); `["currentUser"]` invalidatsiyasi.

---

## ui komponentlari — `frontend/src/components/ui/`

shadcn/ui asosidagi 23 ta primitiv. Ko'pchiligi standart generatsiya; quyidagi jadvalda qaysilari o'zgartirilgani ko'rsatilgan.

| Fayl | Komponent(lar) | Asos | Custom o'zgartirish |
|---|---|---|---|
| `avatar.tsx` | Avatar, AvatarImage, AvatarFallback | Radix Avatar | Yo'q (standart) |
| `badge.tsx` | Badge, badgeVariants | cva | Deyarli standart (`rounded-full` shakl) |
| `button.tsx` | Button, buttonVariants | cva + Slot | **Qo'shimcha o'lchamlar**: `icon-sm` (size-8), `icon-lg` (size-10) |
| `checkbox.tsx` | Checkbox | Radix Checkbox | Yo'q |
| `date-picker.tsx` | DatePicker | react-day-picker + Popover | **To'liq custom** (pastda) |
| `dialog.tsx` | Dialog, DialogContent, DialogHeader/Footer/Title/Description, ... | Radix Dialog | Yo'q (`showCloseButton` prop — yangi shadcn standarti) |
| `dropdown-menu.tsx` | DropdownMenu* (Item `variant="destructive"` bilan), 15 ta eksport | Radix DropdownMenu | Yo'q |
| `form.tsx` | Form, FormField, FormItem/Label/Control/Message, useFormField | react-hook-form + Radix Label | Yo'q |
| `input.tsx` | Input | native `<input>` | Yo'q |
| `label.tsx` | Label | Radix Label | Yo'q |
| `loading-button.tsx` | LoadingButton, ButtonProps | cva (button nusxasi) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | native `<input>` + Button | **To'liq custom** (pastda) |
| `popover.tsx` | Popover, PopoverTrigger, PopoverContent | Radix Popover | Deyarli standart (`rounded-xl`, `p-3`, `align="start"`) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 10 ta eksport | Radix Select | Yo'q |
| `separator.tsx` | Separator | Radix Separator | Yo'q |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 24 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
| `switch.tsx` | Switch | Radix Switch | Yo'q (terminal ekranida ishlatiladi) |
| `table.tsx` | Table, TableHeader/Body/Footer/Row/Head/Cell/Caption | native table | **Stil custom**: konteyner `rounded-lg border`, TableHeader `bg-muted/50`, TableHead `h-11 text-xs font-semibold uppercase tracking-wider`, TableCell `px-4 py-3 whitespace-nowrap` |
| `tabs.tsx` | Tabs, TabsList, TabsTrigger, TabsContent | Radix Tabs | Yo'q |
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

shadcn'da yo'q, loyihaga qo'shilgan komponent. `button.tsx` dagi `buttonVariants` nusxasini o'zida saqlaydi (dublikat — sinxron ushlab turish kerak) va ustiga `loading` prop qo'shadi:

```tsx
function LoadingButton({ loading = false, disabled, asChild = false, ... }: ButtonProps)
// loading=true -> disabled + <Loader2 className="mr-2 h-5 w-5 animate-spin" />
```

Barcha mutation submit tugmalarida ishlatiladi (AddUser, EditUser, AddClient, AddOrder, EditOrder, MachineAssign, OrderMatrix, CutmapView, ConfirmDialog, ChangePassword, UserInformation).

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `Input` stillari bilan bir xil native `<input>` (`pr-10` bilan), o'ng tomonida ghost `Button` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi). `error?: string` prop → `aria-invalid`. `React.forwardRef` bilan react-hook-form'ga mos. `UserSettings/ChangePassword.tsx` va `routes/login.tsx` da ishlatiladi (Admin formalarida esa oddiy `Input type="password"`).

### `frontend/src/components/ui/date-picker.tsx` (custom)

shadcn'da yo'q, to'liq loyihaga yozilgan o'zbekcha sana tanlagich: `react-day-picker` (`uz` locale) + `Popover`. Qiymati form/API bilan mos `"YYYY-MM-DD"` satr, ko'rinishi `DD.MM.YYYY`; trigger tugmada tanlangach "X" tozalash ikonkasi, kalendar ostida "Bugun"/"Tozalash" tugmalari. Buyurtma deadline'i (`Orders/AddOrder`, `Orders/EditOrder`) va hisobot oralig'i (`routes/_layout/reports.tsx`) uchun ishlatiladi.

---

## Bog'lanishlar xulosasi

```
routes (_layout sahifalar)                      routes (terminal / cutmap)
  ├─ PageHeader / StatusBadge / StagePipeline     ├─ CutmapView (SheetSvg → PartCard + QR)
  ├─ AddOrder ─── AddClient (inline)              └─ audio (playSuccess/Error/Warning)
  ├─ EditOrder / MachineAssign / OrderMatrix
  ├─ AddUser
  ├─ DataTable + columns
  │    └─ UserActionsMenu ─ EditUser / DeleteUser ─ ConfirmDialog
  └─ PendingUsers (skeleton)

routes (settings)                               routes (__root / layout)
  ├─ UserInformation                              ├─ SidebarProvider (ui/sidebar)
  ├─ ChangePassword                               ├─ AppSidebar
  └─ DeleteAccount                                │    ├─ Main (navItems, rolga qarab)
       └─ ConfirmDialog                           │    └─ User (avatar + logout)
                                                  └─ NotFound / ErrorComponent

Tashqi bog'liqliklar: @/client (UsersService, ClientsService, OrdersService, TerminalService va
User*/Client*/Order*/Post* model turlari), @/queries/mes (getClients/getMachines/getPosts/
getOrderMatrixQueryOptions va h.k.), @/lib/mes (ROLE_LABELS, PRIORITY_LABELS, POST_COLORS,
ORDER_STATUS_LABELS/COLORS, formatSize), @/hooks (useAuth, useCurrentUser, useCustomToast, useMobile),
@/lib/validation (zod schema'lar, formatMoneyInput, formatUzPhone), @/lib/utils (cn),
@/utils (handleError, getInitials).
```
