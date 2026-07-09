# Frontend Components (Admin, Common, Pending, Sidebar, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini qamrab oladi. Stack: React + TypeScript, TanStack Router/Query/Table, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService va model turlari) orqali gaplashadi; toast xabarlari `useCustomToast` hooki, xatoliklar `handleError` utiliti orqali ko'rsatiladi.

Umumiy naqsh (pattern): **forma → zod schema → react-hook-form → useMutation → UsersService → toast + query invalidation**. Barcha UI matnlari o'zbek tilida.

---

## Admin komponentlari — `frontend/src/components/Admin/`

Admin panel (`/admin` route) uchun foydalanuvchilarni CRUD boshqarish komponentlari.

### `frontend/src/components/Admin/AddUser.tsx`

**Maqsadi:** yangi foydalanuvchi yaratish dialogi (o'zining trigger tugmasi bilan).

- `formSchema` — zod: `phone` (`phoneSchema`), `name` (`optionalNameSchema`), `password` (`passwordSchema`), `confirm_password`, `is_superuser`, `is_active`; `.refine()` bilan parollar mosligi tekshiriladi ("Parollar mos emas").
- Default qiymatlar: `is_superuser: false`, `is_active: true` — yangi foydalanuvchi darhol tizimga kira oladi.
- Mutation: `UsersService.createUser({ requestBody })`; muvaffaqiyatda toast, forma reset, dialog yopiladi; `onSettled` da `["users"]` query invalidatsiya qilinadi.
- Forma `mode: "onBlur"` rejimida validatsiya qiladi; trigger — `<Plus /> Foydalanuvchi qo'shish` tugmasi.
- Submit tugmasi `LoadingButton` (`loading={mutation.isPending}`).

**Bog'lanishlar:** `@/lib/validation` (schema'lar), `@/hooks/useCustomToast`, `@/utils` (`handleError`), ui: `dialog`, `form`, `input`, `checkbox`, `button`, `loading-button`. Admin route sahifasidan chaqiriladi.

### `frontend/src/components/Admin/columns.tsx`

**Maqsadi:** foydalanuvchilar jadvali uchun TanStack Table ustun ta'riflari.

- Eksport: `UserTableData = UserRead & { isCurrentUser: boolean }` va `columns: ColumnDef<UserTableData>[]`.
- Ustunlar: `name` (bo'sh bo'lsa "—", joriy foydalanuvchiga "Siz" badge), `phone`, `is_superuser` → "Admin"/"Foydalanuvchi" Badge, `is_active` → yashil/kulrang nuqta + "Faol"/"Faol emas", `actions` → o'ngga tekislangan `UserActionsMenu`.

**Bog'lanishlar:** `Common/DataTable.tsx` ga uzatiladi; `UserActionsMenu` ni render qiladi; `ui/badge`, `cn` (`@/lib/utils`).

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

- `baseItems: Item[] = [{ icon: Home, title: "Boshqaruv paneli", path: "/" }]`; agar `currentUser?.is_superuser` bo'lsa `{ icon: Users, title: "Foydalanuvchilar", path: "/admin" }` qo'shiladi — **rolga qarab navigatsiya**.
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

shadcn/ui asosidagi 20 ta primitiv. Ko'pchiligi standart generatsiya; quyidagi jadvalda qaysilari o'zgartirilgani ko'rsatilgan.

| Fayl | Komponent(lar) | Asos | Custom o'zgartirish |
|---|---|---|---|
| `avatar.tsx` | Avatar, AvatarImage, AvatarFallback | Radix Avatar | Yo'q (standart) |
| `badge.tsx` | Badge, badgeVariants | cva | Deyarli standart (`rounded-full` shakl) |
| `button.tsx` | Button, buttonVariants | cva + Slot | **Qo'shimcha o'lchamlar**: `icon-sm` (size-8), `icon-lg` (size-10) |
| `checkbox.tsx` | Checkbox | Radix Checkbox | Yo'q |
| `dialog.tsx` | Dialog, DialogContent, DialogHeader/Footer/Title/Description, ... | Radix Dialog | Yo'q (`showCloseButton` prop — yangi shadcn standarti) |
| `dropdown-menu.tsx` | DropdownMenu* (Item `variant="destructive"` bilan), 15 ta eksport | Radix DropdownMenu | Yo'q |
| `form.tsx` | Form, FormField, FormItem/Label/Control/Message, useFormField | react-hook-form + Radix Label | Yo'q |
| `input.tsx` | Input | native `<input>` | Yo'q |
| `label.tsx` | Label | Radix Label | Yo'q |
| `loading-button.tsx` | LoadingButton, ButtonProps | cva (button nusxasi) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | native `<input>` + Button | **To'liq custom** (pastda) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 10 ta eksport | Radix Select | Yo'q |
| `separator.tsx` | Separator | Radix Separator | Yo'q |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 24 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
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

Barcha mutation submit tugmalarida ishlatiladi (AddUser, EditUser, ConfirmDialog, ChangePassword, UserInformation).

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `Input` stillari bilan bir xil native `<input>` (`pr-10` bilan), o'ng tomonida ghost `Button` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi). `error?: string` prop → `aria-invalid`. `React.forwardRef` bilan react-hook-form'ga mos. `UserSettings/ChangePassword.tsx` va `routes/login.tsx` da ishlatiladi (Admin formalarida esa oddiy `Input type="password"`).

---

## Bog'lanishlar xulosasi

```
routes (admin sahifa)          routes (settings)         routes (__root / layout)
  ├─ AddUser                     ├─ UserInformation        ├─ SidebarProvider (ui/sidebar)
  ├─ DataTable + columns         ├─ ChangePassword         ├─ AppSidebar
  │    └─ UserActionsMenu        └─ DeleteAccount          │    ├─ Main (nav, rolga qarab)
  │         ├─ EditUser               └─ ConfirmDialog     │    └─ User (avatar + logout)
  │         └─ DeleteUser                                  └─ NotFound / ErrorComponent
  │              └─ ConfirmDialog
  └─ PendingUsers (skeleton)

Tashqi bog'liqliklar: @/client (UsersService, UserRead/UserCreate/UserUpdate/UserAdminUpdate/UpdatePassword),
@/hooks (useAuth, useCurrentUser, useCustomToast, useMobile), @/lib/validation (zod schema'lar),
@/lib/utils (cn), @/utils (handleError, getInitials).
```
