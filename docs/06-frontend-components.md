# Frontend Components (Agents, Clients, Common, Orders, Anketa, Bazis, People, Sidebar, Terminal, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini va ularni yig'adigan anketa sahifasini (`routes/_layout/anketa.$orderId.tsx`) qamrab oladi. Stack: React + TypeScript, TanStack Router/Query, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService, ClientsService, OrdersService, TerminalService, TerminalDevicesService va model turlari) orqali gaplashadi — chaqiruv shakli `@hey-api/client-axios` niki: argumentlar `{ path, query, body }` guruhlarida beriladi va path/query kalitlari backend'dagi XOM snake_case nomlar (`path: { user_id }`, `query: { employee_id }`), natija esa `AxiosResponse`, ya'ni foydali yuk `.data` da (`onSuccess: ({ data: client }) => ...`, `queryFn: async () => (await ...).data`); umumiy query'lar `@/queries/mes` dagi `queryOptions` fabrikalarida (getClients/getMachines/getPosts/getOrderMatrixQueryOptions va h.k.), domen konstantalari `@/lib/mes` da (yorliq/rang map'lari `satisfies` bilan generatsiya qilingan enumlarga bog'langan — yorliqsiz yangi backend qiymati build'ni yiqitadi: ROLE_LABELS, PRIORITY_LABELS, PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES — prioritet ranglari yagona manbadan, POST_COLORS, ORDER_STATUS_LABELS/COLORS, chipColors/mixTint — chip rang formulasi, isCut, formatSize), buyurtma anketasi variantlari `@/lib/anketa` da; toast xabarlari to'g'ridan-to'g'ri sonner `toast.success/error` (`useCustomToast` hooki o'chirilgan), xatoliklar `handleError` utiliti orqali (`onError: handleError` — curry emas; imzosi `(err: unknown)`, chunki bu klient har qanday xatoni `AxiosError` qilib tashlaydi — eski `ApiError` klassi yo'q, server tanasi `err.response.data.detail` da); takrorlanuvchi toast+xato+invalidatsiya triosi `@/queries/mes` dagi `crudCallbacks()` da.

Umumiy naqsh (pattern): **forma → zod schema → react-hook-form → useMutation → @/client servisi → toast + query invalidation**. Barcha ko'rinadigan UI matnlari o'zbek tilida; shadcn primitivlaridagi ekran o'quvchi matnlari ham o'zbekchalashtirilgan (`sidebar.tsx` trigger — "Menyuni yig'ish/Menyuni ochish", mobil sidebar sr-only sarlavhasi "Yon menyu", tavsifi "Mobil yon menyu"; `dialog.tsx`/`sheet.tsx` — sr-only "Yopish"; `password-input.tsx` — aria-label "Parolni yashirish/ko'rsatish").

---

## People komponentlari — `frontend/src/components/People/`

Birlashgan "Hodimlar" sahifasining yozish qismi. Ilgari bu yerda `Admin/` papkasi turardi
(`AddUser`, `EditUser`, `DeleteUser`, `UserActionsMenu`, `UserForm` — 616 qator): u
`/admin` sahifasi bilan birga o'lik qoldi va o'chirildi, chunki odam ham, hisob ham endi
BITTA dialogdan yaratiladi.

### `frontend/src/components/People/PersonDialog.tsx`

**Maqsadi:** hodim qo'shish va tahrirlash. Uch savol: F.I.Sh, telefon, **lavozim** —
qolganini lavozim hal qiladi.

- **Lavozim** (`lib/mes.ts` `POSITIONS`) uch turga bo'linadi:
  `tsex` (9 ta, har biri postga ko'rsatadi — backend `POST_ROLES` bilan bir xil jadval),
  `ofis` (5 ta — skladchi, menejer, texnolog, direktor, admin; har biri `UserRole` ga ko'rsatadi), `boshqa` (nomi qo'lda — haydovchi,
  farrosh; post ham, hisob ham berilmaydi). Ko'rinadigan nom `ROLE_LABELS[role]` dan
  keladi, shuning uchun dialog va Hodimlar jadvalining "Lavozim" ustuni bir so'zni aytadi.
- **Hodim yozuvi hisobdan OLDIN yaratiladi**, hisob keyin ochilib
  `updateEmployee({user_id})` bilan bog'lanadi (`login._open_shift_for` aynan shu bog'lamdan
  hodimni topadi). Rol lavozim jadvalidan keladi (`POSITIONS[].role` — backend `POST_ROLES`
  bilan bir xil). Ikki so'rov bitta tranzaksiya EMAS: hodim yozuvi tushmasa hisob umuman
  ochilmaydi. Ilgari hisob avval ochilib, hodim tushmasa YETIM qolardi (tsex roli Hodimlar
  ro'yxatida yashiriladi — `employees.tsx`: `isDeviceAccount(u) || linked.has(...)`, qayta
  urinish `crud_users.exists(phone)` da 409 ga urilardi); kompensatsion `deleteUser` esa
  yaramasdi — `delete_user` guard'i o'shanda post rolli har hisobni 403 bilan qaytarardi
  (endi faqat TERMINAL/TABLO va `is_system` post hisobini; xodimning shaxsiy logini o'chadi).
- **Post lavozimdan keladi**: "Arrachi" tanlansa ARRA belgilanadi. Dialog OCHILGANDA ham
  hisoblanadi (`postsFor`), faqat almashtirilganda emas — ilgari admin tayyor turgan
  lavozimga tegmasdan saqlasa POSTSIZ hodim yaratilardi va uning beyjigi ishlamasdi.
  Dialogda post tanlagichi YO'Q: katalog lavozimi ko'pi bilan BITTA post beradi, katalogda
  yo'q lavozim ("Boshqa") esa post OLMAYDI — payload'da `assigned_post_ids: []`, ya'ni
  "Boshqa" ga o'tkazilgan yoki "Boshqa" hodim saqlanganda avvalgi posti olib tashlanadi
  (`postsFor` dagi fallback postlarni faqat forma holatida ushlaydi, so'rovga tushmaydi). Bir odamni ikki postga
  qo'yish — hozircha mahsulot cheklovi (ma'lumot modeli `employee.posts` ro'yxatni ko'taradi).
  Hisob BIR MARTA, ochilishda bo'lgani uchun chaqiruvchi dialogni post katalogi kelgunicha
  MOUNT QILMAYDI (`employees.tsx`: `{(adding || editFor) && posts && (`) — bo'sh katalog bilan
  ochilgan dialog tsex xodimini "Kamida bitta post tanlang" da qotirardi, saqlansa esa posti
  jimgina o'chardi. "Hodim qo'shish" tugmasi ham shu sababdan `disabled={!posts}`.
- **Lavozim MATNDAN emas MA'LUMOTDAN tiklanadi** (`positionOf`): ofis odamida
  `user.role`, tsex odamida biriktirilgan post bo'yicha. Matn bilan solishtirish
  "Manager" != "Menejer" da sinib, tahrirlash o'rniga ikkinchi yozuv yaratardi.
- **Yozish yo'li lavozim turiga qarab:** `ofis` -> `UsersService` (hisob), aks holda
  `EmployeesService` (tsex yozuvi). Tur o'zgarsa qarama-qarshi yozuv o'chiriladi va
  buning uchun TASDIQ so'raladi ("beyjigi bekor qilinadi" / "kirish hisobi o'chiriladi") —
  ilgari bu jimgina bo'lardi. Tasdiq FAQAT yozuv haqiqatan yo'qolganda chiqadi:
  shaxsiy logini SAQLANAYOTGAN tsex xodimini tahrirlashda (`withLogin` — katakcha
  belgilangan) hisob `updateUser` bilan yangilanadi, shuning uchun `switching` shartida
  `&& !withLogin` turadi — busiz har tahrirda yolg'on destruktiv tasdiq chiqardi.
  Allaqachon tsexda bo'lgan xodimning logini olib tashlanganda (yozuv qoladi, faqat
  hisob o'chadi) tasdiq «Kirish hisobi o'chirilsinmi?» deydi — «Tsexga o'tkazilsinmi?» emas.
- **O'chiq "Saqlash" sababini aytadi** (`missing`): "F.I.Sh yozing", "Lavozim nomini
  yozing", "Kamida bitta post tanlang", "Telefon +998XXXXXXXXX formatida bo'lsin",
  "Kirish uchun telefon kerak — login o'shandan olinadi" (ofis lavozimida ham,
  tsexda parol bilan kirishda ham), "Parol kiriting".
- **Telefon EKRANDAGI ko'rinishdan kanonlashtiriladi**: maydon `formatUzPhone` bilan
  maskalanadi, payload esa o'sha maskadan `optionalFormattedPhoneSchema` orqali
  `+998901234567` ga o'tkaziladi. Ilgari u xom kiritmadan raqamlarni yig'ib olardi:
  "901234567" paste qilinsa ekranda to'g'ri "+998 90 123-45-67" turardi, serverga esa
  "+901234567" ketardi; chala terilgan raqamda ham "Saqlash" faol qolib, server 422
  qaytarardi. Endi naqshga mos kelmagan raqam `missing` bilan bloklanadi.
- Parol va login qoidalari maydon ostida turadi — ilgari ular faqat serverdan xato
  bo'lib qaytardi (endi o'zbekcha: `schemas/users.py` `validate_password_strength`).

## Clients komponentlari — `frontend/src/components/Clients/`

### `frontend/src/components/Clients/AddClient.tsx`

**Maqsadi:** yangi mijoz yaratish dialogi — mustaqil ham, boshqa forma ichidan ham ishlaydi.

- zod: `full_name` (min 2 belgi), `phone`/`phone_alt` (`optionalFormattedPhoneSchema`), `address` (ko'pi bilan 255 belgi — backend ustuni `String(255)`; maydonda `maxLength={255}` va `FormMessage` bor, aks holda uzun manzilda submit sababsiz jim bloklanardi), `notes` (cheklovsiz — backend `Text`); telefon inputlari yozish paytida `formatUzPhone` bilan "+998 90 123-45-67" ko'rinishida maskalanadi (placeholder ham shunday); submitda `optionalFormattedPhoneSchema` probel/chiziqchalarni olib tashlab kanonik `+998901234567` ga o'tkazadi.
- Props: `trigger?` (default "+ Yangi mijoz" tugmasi o'rniga istalgan React node), `onCreated?(client)`, `client?` va `onClose?`. `Clients/ClientCombobox` popover footeri birinchi ikkitasidan foydalanib mijozni inline yaratadi va combobox'da avtomatik tanlaydi.
- **Bu ayni paytda TAHRIRLASH dialogi ham:** `client` propi berilsa forma boshqariladigan rejimda ochiladi (`ochiq = true`, yopilishi `onClose` orqali); telefonlar `formatUzPhone(client.phone)` bilan MASKALANGAN holda to'ldiriladi (2026-09-27 gacha xom `+998901234567` turardi). Ikkinchi nusxa yozilmagan, chunki maydonlar va tekshiruvlar aynan bir xil — nusxa bo'lsa telefon formati bir joyda o'zgarib, ikkinchisida qolardi.
- Mutation: `client` berilmasa `ClientsService.createClient`, berilsa `ClientsService.updateClient` (`crudCallbacks` triosi — toast "Mijoz qo'shildi"/"Mijoz yangilandi" + xato + `["clients"]` invalidatsiyasi); muvaffaqiyatda reset, dialog yopiladi va FAQAT yaratishda `onCreated?.(client)` chaqiriladi. Yaratish rejimida dialog YOPILGANDA ham `form.reset()` bo'ladi — komponent unmount bo'lmagani uchun (faqat `DialogContent` ketadi) tashlab ketilgan qoralama va `onBlur` xatolari qayta ochilganda ko'rinib qolardi.

- Trigger tugmasi `Plus` ikonkasi bilan («+ Yangi mijoz» matni emas — «Yangi buyurtma» bilan bir xil); telefon placeholder'i formatter chiqishi bilan bir xil (`+998 90 123-45-67`).

### `frontend/src/components/Clients/ClientCard.tsx`

**Maqsadi:** mijoz kartochkasi — reyestrda qator ustiga bosilganda ochiladi (`clientId` berilsa `Dialog`, `sm:max-w-4xl`). Reyestrdagi savol "bu mijoz kim" emas, "bu mijoz nima buyurtma qilgan", shuning uchun asosiy joyni buyurtmalar jadvali egallaydi.

- Ma'lumot: `ClientsService.readClientDetail` (`["clients", "detail", clientId]`, `enabled: clientId !== null`); yuklanayotganda `Skeleton`.
- Sarlavhada ism + `Clients/ClientSegment`, tavsifda `N buyurtma · summa · aylanmaning X%`. Tepada kontakt qatori (telefon, qo'shimcha telefon, manzil, qo'shilgan sana, izoh) — ichki `Maydon` yordamchisi bilan.
- Pastda buyurtmalar jadvali (`ui/table`): raqam `Link to="/orders/$orderId"` (kartochka yakuniy manzil emas, o'tish joyi), `Common/StatusBadge`, prioritet, muddat, summa; bo'sh bo'lsa `Common/EmptyRow`.

- Buyurtmalar jadvali reestr bilan bir tilda: prioritet `PRIORITY_TEXT_CLASSES` rangida, muddat faol buyurtmada `deadlineTone` (o'tgan — qizil, bugun — amber), yangi **Qoldiq** ustuni (`remainingPayment`; ≤0 — «To'langan»); sarlavha tavsifida **qarz** — bekor qilingan VA qoralama buyurtmalarsiz qoldiqlar yig'indisi (qoralama hali tasdiqlanmagan, mijoz hech narsaga majbur emas — boshqaruv panelidagi «qarz» bilan bir xil filtr, `3280acf`) (`ClientOrderRow.advance_payment` dan; «bizga qarzi bormi?» — kartochkadagi asosiy savol). Telefonlar `formatUzPhone` bilan.

### `frontend/src/components/Clients/ClientCombobox.tsx`

**Maqsadi:** server-qidiruvli mijoz tanlagich — ro'yxat backend `?search=` bilan filtrlanadi, mijozlar soni mingga yetsa ham ishlaydi.

- Qidiruv 300ms debounce (`useDebounced` hooki) bilan `getClientsQueryOptions(search)` ga uzatiladi (`enabled: open`); ArrowUp/ArrowDown/Enter klaviatura navigatsiyasi. So'rov yiqilsa «mijoz topilmadi» EMAS, qizil «Mijozlar ro'yxatini yuklab bo'lmadi — qayta urinish» qatori chiqadi (`isError` + `refetch`): aks holda footerdagi «Yangi mijoz qo'shish» vaqtinchalik xatodan keyin takroriy mijoz yaratishga undardi.
- Belgilangan qator `active` o'zgarganda `scrollIntoView({ block: "nearest" })` bilan ko'rinishga suriladi (ro'yxat `max-h-64 overflow-y-auto` — busiz 5-6 natijadan keyin belgilash ko'rinmas joyda yurardi). Qidiruv inputi `role="combobox"` + `aria-controls`/`aria-activedescendant`, optionlar `useId()` dan olingan `id` bilan belgilanadi — skrinrider faol qatorni o'qiy oladi.
- Dialog ichida ishlashi uchun `Popover` `modal` rejimda; `onOpenAutoFocus` da Radix avto-fokusi bekor qilinib, fokus qidiruv inputiga beriladi.
- Props: `value`/`onChange`, `initialLabel?` (tanlangan mijoz nomi tashqaridan kelganda, masalan EditOrder), `disabled?`.
- Tugmadagi nom (`label`) tashqi `value` bilan sinxron: `value` bo'shasa (forma reset qilinsa) nom ham "Mijozni tanlang" ga qaytadi, `initialLabel` keyin o'zgarsa yangilanadi. Busiz forma qiymati tozalangan holda tugmada eski mijoz nomi qolib ketardi.
- Popover footerida inline `AddClient` ("Yangi mijoz qo'shish" ghost tugma trigger, `onCreated` yangi mijozni avtomatik tanlaydi). `Orders/AddOrder` va `Orders/EditOrder` da ishlatiladi.

### `frontend/src/components/Clients/ClientSegment.tsx`

**Maqsadi:** ABC (Pareto) segment nishoni — mijozning aylanmadagi og'irligi (`SEGMENTS` jadvali: A "Aylanmaning birinchi 80% i", B "80–95% oralig'i", C "Oxirgi 5%"; `title` da shu izoh). Yulduzcha reyting bu ma'lumotda ishlamaydi: prodda o'lchandi, eng yirik mijoz aylanmaning 81% ini beradi, ya'ni qolgan yigirmatasi bir xil past bahoni olardi. Rang bilan emas, OG'IRLIK bilan kodlangan — qizil/yashil tizimda holat degani (kechikdi, bajarildi).

### `frontend/src/components/Clients/DeleteClient.tsx`

**Maqsadi:** mijozni o'chirish tasdig'i — `Common/ConfirmDialog` ustidagi yupqa o'ram (`destructive`, `confirmText="O'chirish"`) + `ClientsService.deleteClient` (`crudCallbacks`, `["clients"]`). Buyurtmasi bor mijozni SERVER 409 bilan rad etadi va nechta ekanini aytadi — bu yerda takrorlanmaydi, aks holda qoida ikki joyda yuritilardi.

---

## Anketa komponentlari — `frontend/src/components/Anketa/`

Anketa sahifasi (`routes/_layout/anketa.$orderId.tsx`) uch mustaqil bo'lakdan iborat — ular bir-birini chaqiradi, lekin har biri o'z sababi bilan o'zgaradi:

### `frontend/src/components/Anketa/fields.tsx`

Anketaning O'Z UI tili: `Section`, `Field`, `Num`, `NumInput`, `CheckCard`, `CheckGrid`, `ShapeChoice`, `Choice`, `Facts`, `numOrNull` va raqamli maydon chegaralari (`MM_RANGE`, `PM_RANGE`, `COUNT_RANGE`). Qog'oz so'rovnomaning aksi (raqam katagi, belgilash to'ri, shakl tanlash) — shuning uchun `Common/` ga chiqarilmagan: hech biri anketadan tashqarida ishlatilmaydi. Yangi umumiy forma elementi kerak bo'lsa u `Common/` ga boradi, bu yerga emas.

### `frontend/src/components/Anketa/RoomPhotos.tsx`

Xona rasmlari galereyasi. Rasmlar anketa JSONB'sida EMAS — `OrderFile(kind=DOCUMENT, meta.room_id)` da, shuning uchun avtosaqlash bilan aralashmaydi va o'z mutatsiyalarini yuritadi (`uploadRoomPhoto`, `deleteRoomPhoto`). Klient chegaralari: xonaga 6 rasm, har biri 5 MB gacha, MIME turi faqat `image/jpeg`/`image/png`/`image/webp` (`ACCEPTED` — backend `orders/survey.py` dagi `_ROOM_PHOTO_TYPES` bilan bir xil; `<input accept>` ham shundan quriladi, shuning uchun HEIC/GIF/SVG serverga bormasdan rad etiladi).

### `frontend/src/components/Anketa/RoomSummary.tsx`

Texnolog/direktor ko'rinishi: forma emas, o'qish uchun jamlanma. **Diqqat:** u anketa formasi bilan bir xil ma'lumotni chizadi — anketaga yangi maydon qo'shilsa, shu yerda ham ko'rsatilishi kerak, aks holda texnolog uni umuman ko'rmaydi.

---

## Agents komponentlari — `frontend/src/components/Agents/`

### `frontend/src/components/Agents/TerminalDevices.tsx`

**Maqsadi:** chek qurilmalari (post monobloklari) — `/agents` sahifasining ikkinchi bo'limi (`routes/_layout/agents.tsx` agentlar jadvalidan keyin `<TerminalDevicesSection />` ni chizadi). Terminal hisobi ODAMGA bog'langan (ish markazi `post_machine` dan), qurilmaga emas: 2026-09-24 da arrachi TELEFONDAN o'z hisobiga kirib chek chiqargan — bitta nusxaning ikki bir xil cheki ikki xil detalga yopishtirilgan. Ish markaziga qurilma ULANSA, shu ish markazining cheki faqat o'sha monoblok brauzeridan chiqadi (backend `services/terminal_device.py`, rad etish — E011; terminal tomoni — `Terminal/PrintDevice.tsx`). Qurilma ulanmagan ish markazida cheklov yo'q.

- Eksport bitta: `TerminalDevicesSection`; ichki `DeviceRow`, `PairedOn`, `AddDevice`.
- Ma'lumot: `TerminalDevicesService.readTerminalDevices` (`["terminal-devices"]`, `refetchInterval: 30_000` — zaxira). Asosiy signal — WS (`useMesWs`): `terminal_device.` bilan boshlanadigan hodisa (`terminal_device.code` / `.paired` / `.deleted`) shu kalitni invalidatsiya qiladi, ya'ni monoblokda kod kiritilishi bilan holat «Ulangan» bo'ladi.
- Sarlavha `Common/SectionTitle` («Chek qurilmalari (post monobloklari)») + izoh (telefondan yoki boshqa kompyuterdan chek to'siladi, skan va xarita ishlayveradi; qurilma ulanmagan ish markazida cheklov yo'q) va uch qadamli «Ulash — postning o'zida» yo'riqnomasi.
- Jadval (`isLoading ? Skeleton : isError ? QueryError : Table`): Nomi · Ish markazi · Holat · Oxirgi faollik (`formatDateTime` + `formatAgo`, yo'q bo'lsa «Hali ulanmagan») · amallar. Holat: `paired` — «Ulangan»; `pair_code` bor — «Kod kutilmoqda» + kod (`fmtCode`) va qolgan muddat (`CodeTtl`, `Common/PairCode`); ikkalasi ham yo'q — «Kod muddati o'tgan» va «Yangi ulanish kodi» ishorasi. Bo'sh jadval — `Common/EmptyRow` «Qurilma yo'q — chek hozir har qurilmadan chiqadi.»
- **Qaysi qurilma ulangan** (`PairedOn`): «Ulangan» ostida kod kiritilgan brauzer turi `paired_user_agent` dan qo'pol aniqlanadi (`deviceKind`: TELEFON / Windows / Linux / Mac kompyuter; to'liq UA `title` da) + `paired_at`. TELEFON bo'lsa qizil qalin «— telefon ulangan! Yangi kod berib, monoblokda ulang»: kodni ishchi ko'rib o'z telefonida kiritib qo'ysa, admin buni darhol ko'rsin.
- Qator amallari — `Common/RowAction`: `KeyRound` «Yangi ulanish kodi (eski ulanish bekor bo'ladi)» (`regenerateTerminalDeviceCode`) va `Trash2` «Qurilmani o'chirish» (`deleteTerminalDevice`, `danger`). Ikkalasi ham `Common/ConfirmDialog` orqali, `crudCallbacks` bilan. Tasdiq matni (`afterText`) HOLATGA qarab oqibatni aytadi — cheklov faqat ULANGAN qurilmalar bilan yashaydi: qurilma hali ulanmagan bo'lsa «cheklov o'zgarmaydi»; ulangan-u ish markazida boshqa ulangan qurilma bor bo'lsa (`othersPaired`) chek o'shandan chiqaveradi; yo'q bo'lsa «cheklov o'chadi: chek yana har qurilmadan (telefondan ham) chiqadi». Yangi kodda oldidan «Eski kod va ulanish darhol bekor bo'ladi», ulangan qurilmada oxirida «Yangi kod monoblokda kiritilgach cheklov qaytadi».
- `AddDevice` — «Yangi qurilma» dialogi (`sm:max-w-md`, react-hook-form + zod: `name` 2–100 belgi, `machine_id` MAJBURIY — ish markazi `ui/select` da, `getMachinesQueryOptions` dan). `createTerminalDevice` muvaffaqiyatli bo'lsa o'sha dialogning o'zida kod katta harflarda chiqadi (`fmtCode`; «Kod 15 daqiqa amal qiladi va bir marta ishlaydi»), xato — `handleError`.

---

## Common komponentlari — `frontend/src/components/Common/`

### Qachon nima ishlatiladi (konventsiya)

Yangi sahifa yoki dialog yozganda quyidagilarni **qo'lda takrorlamang** — har biri
ilgari bir necha joyda alohida yozilib, nusxalar bir-biridan uzoqlashgani uchun
ajratilgan:

| Ehtiyoj | Komponent | Eslatma |
| --- | --- | --- |
| Reyestr jadvali | `ui/table` dagi `Table` | Admin panelida xom `<table>` **biome bilan taqiqlangan** (`noRestrictedElements`); terminal kiosk ekranlari mustasno |
| Jadvalning bo'sh holati | `Common/EmptyRow` | `colSpan` beriladi; matn yo'l ko'rsatuvchi bo'lsin ("Hali X yo'q — ... bilan qo'shing") |
| So'rov xatosi | `Common/QueryError` | `useQuery` dan `isError, refetch` olinadi; naqsh: `isLoading ? Skeleton : isError ? QueryError : Table` |
| Sahifalash | `Common/TablePagination` | `page`/`pageSize`/`total`/`onPage`; natija bo'sh bo'lsa o'zi chizilmaydi |
| Qatordagi amal tugmasi | `Common/RowAction` | Ikonka tugma; buzuvchi amalga `danger` (hoverda qizil) |
| Dialog maydoni yorlig'i | `Common/Field` | react-hook-form ishlatilmaydigan formalar uchun; rhf bo'lsa `ui/form` dagi `FormField`/`FormLabel` |
| Tasdiqlash so'rovi | `Common/ConfirmDialog` | O'chirishda `destructive` |
| Qidiruv maydoni | `Common/SearchInput` | `useDebounced(search.trim())` bilan |
| Tanlov ro'yxati | `Common/SelectField` | Xom `<select>` **biome bilan taqiqlangan** |
| Sahifa sarlavhasi | `Common/PageHeader` | `title`/`description`/`actions` |
| Status yoki post nishoni | `Common/StatusBadge`, `Common/PostBadge` | Rang formulasi `lib/mes.ts` dagi `chipColors` da — qo'lda yozilmaydi |

Mahkamlash uch qatlamli: (1) komponent — yagona manba; (2) `frontend/biome.json`
dagi `noRestrictedElements` — xom element ishlatilsa CI **xato** beradi va sababini
tushuntiradi; (3) shu jadval — qaysi ehtiyojga qaysi komponent.

Ataylab chetlanish bo'lsa `biome-ignore` izohida SABABI yoziladi (namuna:
`anketa.$orderId.tsx` dagi forma jadvallari — ular reyestr emas, kataklarida
kiritish maydonlari turadi).

**Menyu guruhi ikki xil chiziladi** (`Main.tsx`): odatda ota band + chevron, bosilganda ochiladi
(`NavGroup`); `Item.flat` berilsa esa ota band UMUMAN chizilmaydi va bo'limlar yuqori daraja
sifatida, doim ochiq turadi. Ikkinchisi butun menyusi bitta bo'limdan iborat rol uchun (mahsulot
omborchisi, `docs/14` §11.2): u yerda ota band hech qayerga olib bormaydi va har kirganda bitta
ortiqcha bosish qo'shardi. Bo'lim havolasi ikkalasida ham bitta komponent (`SubLink`) — `nested`
bilan chekinma va kichik shrift oladi.

### Belgilar lug'ati (lucide) — bitta tushuncha, bitta belgi

Ma'noni foydalanuvchi oldingi tajribasidan oladi (NN/g, «Icon Usability»), yig'ilgan yon menyuda esa yozuv
ko'rinmaydi — shuning uchun bir belgi ilovada ikki ma'noda ishlatilmaydi va bir tushuncha ikki xil belgi
olmaydi. 2026-09-26 auditi (100 belgi, 219 joy, skript bilan sanalgan) shu qoidani buzgan 13 joyni tuzatdi.

| Tushuncha | Belgi | Izoh |
| --- | --- | --- |
| Tizim holati (server sog'lig'i) | `Activity` (puls chizig'i) | Grafana `heart-rate`, GitHub `pulse` bilan bir odat; ilovada BOSHQA joyda ishlatilmaydi |
| Jonli ma'lumot / aloqa uzildi | `Radio` / `WifiOff` | Boshqaruv paneli «JONLI», terminal «ALOQA YO'Q». Tarmoq bo'lmagan xato uchun `WifiOff` emas — `TriangleAlert` |
| Buyurtmalar / Anketa | `ClipboardList` / `ClipboardPen` | Anketa — to'ldiriladigan shakl; ikkalasi bir belgi edi |
| Kesish xaritasi | `CutMap` (`Common/CutMapIcon.tsx`, maxsus) | Terminal «Xarita», buyurtma «Kesish xaritalari», «Kesish xaritasida ko'rsatish» — hammasi bitta. Lucide'da mosi yo'q: `Grid2x2` — teng to'rt katak, odatda «katak ko'rinishi» (Fluent `Grid`: «Used to represent grid view in products») yoki «oyna» (lucide teglari: window, skylight); `Map` — geografik xarita. Maxsus belgi GibLab «Раскроить» (`giblab.com/images/icons/cuttingsheet.gif`) shaklida: yotiq list, teng bo'lmagan kesimlar |
| Loglar | `ScrollText` | Menyu ham, agent loglari ham |
| Tasdiqlash | `Check` | `CheckCheck` (ikki belgi — «o'qildi») emas |
| Kattalashtirish / kichraytirish | `ZoomIn` / `ZoomOut` | `Plus` ilovada faqat «qo'shish» |
| Yangi hujjat (list) | `FilePlus` | `RotateCcw` — «qaytarish/tiklash» (3D ko'rinishni tiklash) |
| Ombor kategoriyalari | Material `Layers`, Furnitura `Bolt`, **Kromka `Ruler`**, Xizmat `Hammer` (ota «Mahsulotlar ombori» — `Boxes`) | Furnitura — mahkamlagich (lucide teglari: nut, screw, parts), asbob emas; kromka metrlab o'lchanadi — chizg'ich |
| Havola ishlamaydi | `Link2Off` | Havolani yopish ham shu belgi (`BazisPanel`) |
| 3D ko'rinishni ochish / modeli yo'q mahsulot | `Rotate3d` / `Box` | «Ko'rish» tugmasi (`BazisPanel`); `Box` — ro'yxatda eskiz o'rnidagi punktir katak. Yuklash — `.project` bilan bir xil `FileUp` |
| Umumiy ogohlantirish / xato | `TriangleAlert` | Brak ham shu (menyu, terminal BRAK tugmasi, brak dialogi) — brak «muammo» sinfi; alternativalar qadoq (`PackageX`), bekor qilish (`CircleX`) yoki xavfsizlik (`ShieldX`) ma'nosi bilan to'qnashardi |

### `frontend/src/components/Common/CutMapIcon.tsx`

`CutMap` — kesish xaritasining maxsus belgisi (`createLucideIcon`, lucide uslubi: 24 katak, chiziq 2). Yotiq list (`rect 20×14`), bo'ylama kesim va ikki tomonida turli ko'ndalang kesimlar — 5 ta teng bo'lmagan bo'lak, GibLab «Раскроить» belgisi kabi. Lucide'dagi eng yaqin stok nomzodlar solishtirildi: `panels-top-left`/`table-2` «maket/jadval», `layout-*` bo'shliqli kartochkalar (bitta list emas), `grid-2x2` teng kataklar. Sabablari «Belgilar lug'ati» jadvalida.

### Dialog kengligi qoidasi

`DialogContent` sukut bo'yicha `sm:max-w-lg` (512px). Ikki ustunli formalar (`grid-cols-2`) uni `sm:max-w-xl` (576px) qiladi: `sm:max-w-md` (448px) da ustun 194px bo'lib qolardi, eng uzun yorliq esa 166px (`Boshlang'ich to'lov (so'm)`, brauzerda o'lchangan) — maydon bilan yorliq bir-biriga tiqilardi. 576px da ustun 258px. Bu formalar: `Orders/AddOrder`, `Orders/EditOrder`, `Clients/AddClient`. Bitta ustunli qisqa dialoglar (`ConfirmDialog`, `PersonDialog`, `AddAgent`, `Agents/TerminalDevices` dagi `AddDevice`, `Terminal/PrintDevice` dagi `PrintDeviceDialog`) `md` da qoladi — kenglik MAZMUNGA qarab tanlanadi, umumiy cheklov emas.

### Dialog maydonlari — `Common/Field`

react-hook-form ishlatmaydigan dialoglarda yorliq va maydon `Field` orqali beriladi: u `grid gap-1.5` bo'shliqni ham, yorliqni bosganda fokusni ham (implicit `<label>`) beradi. Yalang'och `<Label>` + `<Input>` ishlatilsa bo'shliq umuman bo'lmaydi va yozuv maydonga tegib turadi — beyjik printeri dialogida aynan shu bo'lgan. Qoida: rhf yo'q dialogda **doim `Field`**.

### `frontend/src/components/Common/BadgePrompt.tsx`

**Maqsadi:** login ekranining beyjik chaqirig'i — `routes/login.tsx` da parol formasi yopiq bo'lganda ko'rinadi (`{!showPassword && <BadgePrompt pending={badge.isPending} />}`).

- Nega TUGMA emas: skaner tugmasiz ishlaydi (klaviatura kabi yozadi), bosilganda hech nima qilmaydigan tugma — yolg'on afforadans. Punktir ramka ham shunday edi: bu loyihada punktir "faylni shu yerga tashlang" degani.
- O'rniga beyjikning O'ZI chizilgan (inline SVG `BadgeCard`, 120×148): lentali karta va ichida QR — uchta burchak belgisi + o'ng-pastdagi modullar, ATAYLAB to'liq emas (ekrandagi kod skanerlanmasin). Chiziq tili `AuthLayout` chap panelidagi kesish xaritasi bilan bir xil (`mx-draw` konturi + `mx-fade`), rang navy/gold (`--brand-navy-deep` / `--brand-gold-deep`); karta konturi navy 0.45 opacity — 0.28 da och fonda «sharpa» bo'lib, QR belgilari havoda muallaq turardi.
- Yagona prop `pending: boolean` — skan yuborilib javob kutilayotganda yozuv "Beyjikni skanerlang" o'rniga "Tekshirilmoqda..." bo'ladi va QR navy rangga o'tadi. Ostida doim "Smena avtomatik ochiladi".
- Kutish holatida QR ustidan **skan-chizig'i** o'tadi (`mx-scan`: 1.5 px oltin, ≤0.35 xiralik, 2.8 s sikl, 1.4 s boshlang'ich kechikish — karta chizilib bo'lgach) — "ekran kutmoqda" degani, matnsiz; `pending` da chizilmaydi, `prefers-reduced-motion` da `display:none`. Pulsatsiya/porlash ATAYLAB yo'q — kioskda doimiy yaltirash bezovta qiladi.
- O'lchamlar `lg:` da bir pog'ona katta (chaqiriq 24 → 30 px, ikkilamchi qator 14 → 16 px): login 17" kioskda ~70 sm dan o'qiladi; tokenlar admin bilan bir xil qoladi.

### `frontend/src/components/Common/BrandLoader.tsx`

**Maqsadi:** MX logotipli yuklanish indikatori — sahifa/route darajasidagi kutishlarda spinner o'rniga brend. Kontur o'zini chizadi, to'ladi, so'nadi, qaytadan (`mx-loader` keyframes, **1.8s**; chizish 0-25% = 450ms; `prefers-reduced-motion` da statik to'liq logo). Har kontur ALOHIDA `<path>` elementida (`MX_SUBPATHS`): SVG'da dash naqshi har subpathda qaytadan boshlanadi, ya'ni bitta elementda ikkala kontur parallel chizilib, har biri o'z uzunligiga qarab turli vaqtda tugardi — 2.4s siklda kontur ~660ms da tayyor bo'lib qolgan vaqt o'lik turardi, router esa loader'ni kamida 500ms ko'rsatadi, natijada qisqa yuklanishlarda X ning o'ng-past qanoti UMUMAN chizilmasdi (o'lchandi: eski kodda 450ms da 6325 piksel yetishmasdi, yangisida 2). Alohida elementda har biri chizish fazasi oxirida aniq tugaydi. Ostida 12% xira SHARPA — qisqa yuklanishda ham brend butun ko'rinadi. Vektor `icon-navy.png` dan potrace bilan olingan (piksel-mos, headless Chrome'da solishtirilgan), `pathLength=1` — dasharray real uzunlikka bog'liq emas. Rang `currentColor`: panelda `text-primary`, tabloda oltin. Ishlatilishi: router `defaultPendingComponent` (`main.tsx`, 200ms dan cho'zilgan yuklanishda, minMs 500), tablo `isLoading`. Tugma ichidagi spinner (`LoadingButton`) va toast ikonkasi ATAYLAB o'zgarmagan — 16-20px masshtabda logo shovqin, spinner tanish konvensiya.

### `frontend/src/components/Common/AuthLayout.tsx`

**Maqsadi:** login sahifasi uchun ikki ustunli layout.

- Chap ustun (faqat `lg:` da): solid `bg-(--brand-navy-deep)` fon, ustida animatsiyali `CutmapArt` SVG — stilize kesish xaritasi (2750×1830 plita, GibSaw uslubi), chiziqlar `mx-draw`/`mx-fade` animatsiyalari bilan `--brand-gold` rangda chizilib paydo bo'ladi; `logo-gold.png` tepada (`self-start`), pastda tagline bloki ("Ishlab chiqarishni boshqarish tizimi" + "Kesishdan yetkazishgacha — har bir detal nazorat ostida.").
- O'ng ustun: markazlangan `max-w-md` forma konteyneri (`children`), pastda `Footer`; mobil ko'rinishda navy watermark (`icon-navy.png`).
- Hozircha yagona auth route — `routes/login.tsx` shu layout bilan o'raladi (signup route yo'q).

### `frontend/src/components/Common/ConfirmDialog.tsx`

**Maqsadi:** umumiy "Ishonchingiz komilmi?" (controlled) dialog. Trigger va `open` holati chaqiruvchiga tegishli — trigger tugma, menyu bandi yoki boshqa narsa bo'lishi mumkin; komponent faqat modal tanasini chizadi.

- Props: `open`, `onOpenChange`, `title`, `description?`, `confirmText?` (default "Tasdiqlash"), `cancelText?` (default "Bekor qilish"), `destructive?`, `loading?`, `onConfirm`.
- Tasdiqlash tugmasi `LoadingButton` (`variant={destructive ? "destructive" : "default"}`); ikkala tugma ham `h-11 px-5` — 44px minimal barmoq o'lchami terminal (touch) va admin uchun bir xil.

**Foydalanuvchilari:** `Agents/TerminalDevices.tsx` (chek qurilmasiga yangi ulanish kodi va qurilmani o'chirish — ikkita dialog), `Anketa/RoomPhotos.tsx` (rasm o'chirish), `Clients/DeleteClient.tsx` (mijozni o'chirish), `People/PersonDialog.tsx` (lavozim turi o'zgarganda qarama-qarshi yozuv o'chirilishi), `Orders/BazisPanel.tsx` (havolani yangilash/yopish, modelni o'chirish), `routes/_layout/orders/index.tsx` (buyurtma/qoralamani o'chirish), `routes/_layout/orders/$orderId.tsx`, `routes/_layout/anketa.$orderId.tsx` (xona o'chirish), `routes/_layout/employees.tsx`, `routes/_layout/work-centers.tsx` (ish markazini o'chirish), `routes/_layout/agents.tsx` (ish markazi bog'lash/uzish, chek chiqarish `can_print` switch'i, agentga yangi kod berish va agentni bekor qilish — to'rtta dialog), `routes/_layout/system-health.tsx` (baza statistikasini nollash), `routes/terminal.tsx` — jami 12 fayl.

### `frontend/src/components/Common/EmptyRow.tsx`

**Maqsadi:** jadvalning bo'sh holati qatori (`colSpan` + markazlangan muted xabar — "topilmadi / hali yo'q") — har reyestrda qo'lda takrorlanadigan `TableRow`+`TableCell` naqshi bitta joyda. 12 faylda, 17 joyda ishlatiladi (agents, clients, defects, employees, logs, orders ro'yxati, reports — to'rt marta, system-health — uch marta, warehouse, work-centers va `Clients/ClientCard`, `Agents/TerminalDevices`; `printers.tsx` endi `/agents` ga redirect).

### `frontend/src/components/Common/Field.tsx`

Dialog maydoni yorlig'i — `useState` bilan yozilgan formalar uchun (`People/PersonDialog`, `employees.tsx` dagi `BadgeDialog`, `work-centers`, `system-settings`). Maydon `<label>` ICHIDA turadi, ya'ni yorliqni bosish fokus beradi. react-hook-form ishlatiladigan joyda `ui/form` dagi `FormField`/`FormLabel` qoladi.

### `frontend/src/components/Common/RowAction.tsx`

Jadval qatoridagi amal tugmasi: `icon`/`title`/`onClick`, buzuvchi amalga `danger`. O'lcham bitta (`size="icon"` + `size-8`), `danger` odatda kulrang va faqat hoverda qizil. `aria-label` `title` dan olinadi.

### `frontend/src/components/Common/RowOpen.tsx`

**Maqsadi:** «bu qator nimadir ochadi» ishorasi — o'ng chetdagi kichik strelka (`RowOpenCell` = `w-8` katak + xira `ChevronRight`, `aria-hidden`; sarlavhada bo'sh `<TableHead className="w-8" />`). 2026-09-04: ilgari yagona belgi `cursor-pointer` edi, `TableRow` ning O'ZIDA esa `hover:bg-muted/50` bor — Hodimlar, Ish markazlari, MES agentlar va Hisobotlar qatorlari ham yonardi-yu, hech narsa ochmasdi, ya'ni yonish «bosiladi» degani emasdi.

- Ishlatiladi FAQAT qator bosilganda nimadir ochiladigan to'rt jadvalda: `orders/index` (sahifa), `clients` (mijoz kartasi), `logs` (batafsil panel), `system-health` endpointlari (tafsilot paneli). Amal tugmalari (`RowAction`, o'chirish) O'Z ustunida qoladi — strelka ulardan KEYIN, alohida ustunda: bittasi «amal», ikkinchisi «ochish».
- Tanlash uchun bosiladigan qator strelka OLMAYDI (terminal `PrisadkaView` — qator tanlanadi, hech narsa ochilmaydi); TABLO qatori ham olmaydi (uzoqdan o'qiladigan taxta, har qatordagi belgi shovqin).

### `frontend/src/components/Common/TablePagination.tsx`

Reyestr sahifalagichi: `page` (0 dan), `pageSize`, `total`, `onPage`. Tartib bitta — butun blok o'ngga tekislangan (`justify-end`): avval "N tadan X–Y", keyin `[Oldingi] [k / n] [Keyingi]`. `total === 0` da `null` qaytaradi. Chaqiruvchilari — `clients` va `warehouse` (`PAGE_SIZE`=100, `queries/mes`) hamda `logs` (PAGE=50); sahifa hajmi baribir prop bo'lib qoladi, chunki u qator balandligiga bog'liq va har reyestrda boshqacha bo'lishi mumkin.

### `frontend/src/components/Common/ErrorComponent.tsx`

**Maqsadi:** routerning global xato ekrani — `ErrorScreen` ga delegatsiya (`code="Xato"`, "Xatolik yuz berdi..." matni). TanStack beradigan `ErrorComponentProps` ni QABUL QILADI: `error` `extractErrorMessage` (`@/utils`) dan o'tib `detail` sifatida umumiy jumla ostida chiqadi, `reset` esa "Qayta urinish" tugmasiga ulanadi. Shuning uchun `__root.tsx` da `errorComponent: ErrorComponent` deb ulanadi — o'rab qo'yilgan `() => <ErrorComponent />` proplarni yutar va har xato bir xil sababsiz matn ko'rsatardi.

### `frontend/src/components/Common/ErrorScreen.tsx`

**Maqsadi:** xato/404 ekranlarining umumiy maketi (`code` + `message` + "Bosh sahifaga" tugmasi, `Link to="/"`) — ikki nusxa layout drift bermasin. `ErrorComponent` va `NotFound` shundan quriladi. Ikki ixtiyoriy prop: `detail` (sabab — umumiy matn ostida mayda shriftda) va `action` ("Bosh sahifaga" yonidagi qo'shimcha tugma); ikkalasi ham berilmasa ekran o'zgarmaydi — `NotFound` aynan shunday ishlatadi.

### `frontend/src/components/Common/Footer.tsx`

**Maqsadi:** oddiy footer — `MebeliX MES · {joriy yil}`. `AuthLayout` ichida ishlatiladi. Ustki chiziqsiz: login formasining o'z ajratgichi bor, 160 px oraliqda ikkita turli uzunlikdagi chiziq shovqin edi.

### `frontend/src/components/Common/NotFound.tsx`

**Maqsadi:** 404 ekrani — `ErrorScreen` ga delegatsiya (`code="404"`, "Siz qidirayotgan sahifa topilmadi." matni). Router'ning `notFoundComponent` sifatida ulanadi.

### `frontend/src/components/Common/OperationChips.tsx`

**Maqsadi:** marshrut QADAMINING amal nomi chipi (kod 11 → "G petlya o'ngdan") — amber chip; chipsiz operator raqamni yoddan tarjima qilishi kerak edi, va noto'g'ri petlya eshikni brak qiladi.

- Props: `processCode: number | null | undefined`, `postCode: string | null | undefined` va `defaultCode?: number` (postning odatdagi amali). Kod endi detal NOMIDAN o'qilmaydi — nomdagi `{kodlar}` sintaksisi butunlay olib tashlangan; `process_code` marshrut qadamining o'zida saqlanadi va backend uni `KromkaPartRow` va `PostQueueRow` da beradi.
- `PROCESS_OPS` (`@/lib/mes` dan import — 16 kod (1–16), backend `PROCESS_POSTS` bilan bir xil bo'lishi shart) kodni amal nomi + postga o'giradi. Chip chizilmaydi, agar: kod noma'lum bo'lsa (xato nom emas, hech nima), kod boshqa postga tegishli bo'lsa, post bitta amalli bo'lsa (prisadka, rover, oval, bo'yoq — post nomi ekran sarlavhasida turibdi) yoki kod postning odatdagi amali (`defaultCode`) bo'lsa — kromka postida oddiy «Kromka» chipsiz, faqat «Fasat kromka» ko'rinadi. Ya'ni chip faqat ARRA, KROMKA va STOLYARKA da ko'rinadi.
- Ishlatilish joylari: `Terminal/KromkaView` (`postCode={oval ? "OVAL" : "KROMKA"}`, `defaultCode={oval ? 5 : 3}`) va `Terminal/PostQueueView` (`postCode={data?.post_code}`).

### `frontend/src/components/Common/PairCode.tsx`

**Maqsadi:** 8 belgili ulanish kodini ko'rsatish — MES agenti ham, chek qurilmasi ham bir xil kod oladi (backend `bridge_agents.new_pair_code`, `PAIR_TTL` 15 daqiqa). Ikki eksport: `fmtCode` (`AB12CD34` → `AB12-CD34` — telefonda aytish oson) va `CodeTtl({ expiresAt })` — qolgan muddat «m:ss qoldi», oxirgi 2 daqiqada (`<= 120` s) qalin qizil. Soat SHU komponent ichida (1 s `setInterval`) — aks holda har soniyada butun jadval qayta chizilardi. Ilgari ikkalasi `routes/_layout/agents.tsx` ichida lokal edi; chek qurilmalari bo'limi qo'shilgach shu faylga chiqarildi. Chaqiruvchilar: `routes/_layout/agents.tsx` va `Agents/TerminalDevices.tsx`.

### `frontend/src/components/Common/PageHeader.tsx`

**Maqsadi:** sahifa sarlavhasi — `title`, ixtiyoriy `description` va o'ng tomonda `actions` slot. Barcha `_layout` sahifalarida ishlatiladi (dashboard, orders ro'yxati va sahifasi, agents, anketa, clients, defects, employees, logs, reports, settings, sotuv, system-health, system-settings, warehouse, work-centers — 16 ta sahifa; `admin.tsx` sanoqqa kirmaydi — u endi redirect, chizadigan sarlavhasi yo'q); yagona istisno — `cutmap.$orderId.tsx`, unda sarlavha umuman yo'q (to'liq ekran).

- `description` `div` ichida (`<p>` emas) — `ReactNode` qabul qiladi, `<p>` ichida blok element HTML'da noto'g'ri bo'lardi.
- `actions` konteyneri `flex-wrap` + telefonda `w-full` (`md:w-auto`) — ichidagi qidiruv `w-full md:w-72` to'liq qatorni oladi, tugma pastga tushadi (2026-09-04 kech; standart mobil naqsh) (2026-09-04): qidiruv + tugma birga kelganda (Mijozlar, Hodimlar) telefonda qator sig'maydi va butun sahifa yonga skroll bo'lardi — 390 px da o'lchandi (sahifa kengligi 441/434 px, boshqa 8 sahifa 390). Endi tugma pastga tushadi. Bu tizimning mobil holati: admin sahifalari sidebar Sheet + `sm/md/lg` gridlar bilan telefonga MOSLASHADI, jadvallar `overflow-x-auto` konteynerda yonga skroll (Buyurtmalar — 4 ekran kenglik), terminal/tablo esa ataylab 1366+ landshaft. Prod Caddy logida (22.08–04.09, 923 so'rov) mobil UA 0 ta — hech kim telefondan ochmagan.

- `titleAside?: ReactNode` — sarlavha bilan BIR QATORDA (`flex-wrap`, tor ekranda pastga buqiladi): buyurtma sahifasi holat/prioritet badge'lari va bosqichlar zanjirini beradi — alohida qator o'rniga.

### `frontend/src/components/Common/PostBadge.tsx`

**Maqsadi:** bosqich (post) kodi chipi (ARRA, KROMKA, ...) — `POST_COLORS` + `chipColors(color, 12)` (`@/lib/mes`) asosida: matn post rangining to'qroq variantida (`78%, black` — WCAG AA kontrasti, sof rang tint fonda o'tmasdi), fon 12% oq tint. Avval `employees.tsx` va `work-centers.tsx` da qo'lda takrorlangan edi.

### `frontend/src/components/Common/QueryError.tsx`

**Maqsadi:** so'rov yiqilganda ko'rsatiladigan `role="alert"` bloki — xato matni (`message?`, default "Ma'lumotni olishda xatolik yuz berdi.") + doim chiziladigan "Qayta urinish" tugmasi (majburiy `onRetry`). Busiz sahifalar xato holatida abadiy skeletonda qotib qolardi.

### `frontend/src/components/Common/SearchInput.tsx`

**Maqsadi:** ichida `Search` ikonkasi bo'lgan qidiruv maydoni (`value`/`onChange`/`placeholder`/`className`) — reyestr sahifalarida (clients, employees, orders ro'yxati, logs) qo'lda takrorlanadigan `relative` div + absolyut ikonka + `pl-8` Input naqshi bitta joyda; kenglik/joylashuv `className` orqali chaqiruvchidan.

### `frontend/src/components/Common/SelectField.tsx`

**Maqsadi:** dialoglardagi tanlov maydoni. **Xom `<select>` ISHLATILMAYDI** — u ochilganda BRAUZERNING o'z ro'yxatini chizadi, uni CSS bilan o'zgartirib bo'lmaydi, ya'ni balandligi/burchagi/shrifti/fokus halqasi yonidagi `Input` va `Button` bilan mos kelmaydi va bitta shunday maydon butun formani "tayyor shablon" qilib ko'rsatadi. Radix `Select` ni har dialogda beshta komponent bilan yozish o'rniga shu o'ram: tanlov maydonining shakli BIR joyda.

- Props: `value`/`onChange`, `options: SelectOption[]` (`{ value, label, hint? }` — `hint` kod/telefon kabi ikkinchi darajali matn), `placeholder?`, `emptyLabel?`, `disabled?`, `className?`. `emptyLabel` — "tanlanmagan" varianti: Radix bo'sh `""` qiymatni qabul qilmaydi, shuning uchun ichki `EMPTY = "__empty__"` sentineli bilan ifodalanadi va tashqariga `""` qaytadi.
- **Qoida biome bilan mahkamlangan**: `correctness/noRestrictedElements` `<select>` va `<textarea>` ni taqiqlaydi va nima ishlatish kerakligini xato matnida aytadi. `src/components/ui/**` biome tekshiruvidan chiqarilgan, ya'ni shadcn primitivlarining o'zi bu qoidaga tushmaydi.
- Chaqiruvchilari: `Orders/CustomRoutes.tsx`, `Orders/MachineAssign.tsx`, `People/PersonDialog.tsx`, `routes/_layout/agents.tsx`, `routes/_layout/sotuv.tsx`, `routes/_layout/warehouse.tsx`, `routes/_layout/work-centers.tsx`.

### `frontend/src/components/Common/SectionTitle.tsx`

**Maqsadi:** sahifa ichidagi bo'lim sarlavhasi (`h2`, uppercase muted) — ierarxiya: `PageHeader` (h1) > `SectionTitle` (h2) > panel sarlavhalari (h3); avval bir daraja to'rt xil yozilgan edi.

### `frontend/src/components/Common/StagePipeline.tsx`

**Maqsadi:** ishlab chiqarish pipeline'i — ulangan progress kataklar zanjiri, loyihaning "signature" vizual elementi. Kataklar data-driven (`stages` propidan), hozir bazada 9 post (PAZ olib tashlangan; BOYOQ, UPAKOVKA va TMO qo'shilgan) — `POST_COLORS` da ham shu to'qqiz kalit.

- Props: `stages: StageCell[]` (`{ code, done, total }`) va `showLabels?` (pastda); har katak (`h-6 w-12`) `POST_COLORS[code]` rangida (`mixTint` fon + foizli progress chizig'i), ichida `done/total` (`--foreground` rangda — post rangi o'z tinti ustida AA dan o'tmasdi), tugallanganda "✓"; kataklar orasida ulovchi chiziqcha, `title` da `KOD: done/total (N%)`.
- Buyurtma sahifasi sarlavhasida (`routes/_layout/orders/$orderId.tsx`) va `Orders/PartTrace` da ishlatiladi (boshqaruv paneli endi ishlatmaydi); xuddi shu vizual grammatika `Orders/OrderMatrix` va TABLO ekranida takrorlanadi.

- `showLabels` — katak ostida post kodi (jadval ustunisiz turganda rangning o'zi bosqichni aytmaydi); ikkala chaqiruvchi ham beradi. Shu rejimda zanjir `flex-wrap` — tor ekranda kataklar keyingi qatorga o'tadi: yorliq katakni kengaytiradi va 360 px da 6 bosqich (354 px) ichki kenglikdan (312 px) oshib, buyurtma sahifasini yonga surardi. Yashirilmaydi — hamma bosqich ko'rinsin. Telefonda (`<sm`) ulovchi chiziqcha yashirin, kataklar orasida oraliq (`gap-x-1.5`) — aks holda o'ralgan qator «—» bilan boshlanardi.

### `frontend/src/components/Common/StatusBadge.tsx`

**Maqsadi:** buyurtma holati pill'i — `ORDER_STATUS_LABELS`/`ORDER_STATUS_COLORS` (`@/lib/mes`) asosida rangli nuqta + matn. Besh chaqiruvchi: buyurtmalar ro'yxati, buyurtma sahifasi, hisobotlar, `Clients/ClientCard` dagi buyurtmalar jadvali va `Orders/PartTrace` (detal izi).

---

## Orders komponentlari — `frontend/src/components/Orders/`

Buyurtma sahifalari (`/orders`, `/orders/$orderId`) uchun dialog va jadval komponentlari.

### `frontend/src/components/Orders/orderForm.tsx`

**Maqsadi:** AddOrder va EditOrder uchun umumiy forma manbasi — ikkala dialog bitta backend kontraktiga tegadi, shuning uchun schema, payload va maydonlar bir joyda.

- Eksportlar: `formSchema` (zod: `client_id` majburiy, `deadline?`, `priority` enum low/medium/high/urgent, `amount` majburiy, `advance_payment?`, `notes?`; `.refine()` — boshlang'ich to'lov umumiy narxdan oshmasligi kerak), `FormValues`, `toRequestBody(data)` va `OrderFields({ control, notesPlaceholder?, isNew? })`.
- `toRequestBody` — create va update bir xil payload kutadi: `client_id` `Number` ga, pul maydonlaridan probellar olib tashlanadi, bo'shlari `null`.
- `OrderFields` — ikkala dialogdagi bir xil maydonlar: topshirish sanasi (`ui/date-picker` DatePicker), prioritet `Select` (`PRIORITY_LABELS` yorliqlari, bandlarida `PRIORITY_DOT_CLASSES` rangli nuqtalar), umumiy narx va boshlang'ich to'lov (`formatMoneyInput` bilan ming ajratkichli) hamda izoh (`notesPlaceholder` propi bilan — faqat placeholder dialogga qarab farq qiladi). `isNew` (faqat `AddOrder` beradi) muddat tanlagichiga `disablePast` uzatadi: yangi buyurtma muddati o'tgan kun bo'lolmaydi. Sabab — B-2026-136: 2026-10-04 12:32 da 01.10 muddat bilan yaratilgan va 12:34 da tahrirda 08.10 ga to'g'rilangan (ikkalasi kalendarda bir ustunda, ustma-ust). Bazada faqat oxirgi muddat qoladi, audit `updated` qaysi maydon o'zgarganini yozmaydi — bunday tuzatilgan xatolar sonini bazadan sanab bo'lmaydi. Tahrirlashda cheklov yo'q — muddatsiz buyurtmaga kelishilgan (o'tgan) sanani keyin yozish mumkin, muddati o'tib ketgan buyurtmada esa uning o'tgan muddati tanlangan holda ko'rinadi. Mijoz maydoni dialoglarda qoladi: EditOrder'da `initialLabel` va `disabled` kerak.

### `frontend/src/components/Orders/AddOrder.tsx`

**Maqsadi:** yangi buyurtma dialogi ("+ Yangi buyurtma") — raqamni tizim beradi (B-YYYY-NNN), fayl keyin texnolog tomonidan yuklanadi.

- Forma `orderForm.tsx` dan: `formSchema` + `OrderFields` (`isNew` bilan — muddat tanlagichida bugundan oldingi kunlar xira va tanlanmaydi) + `toRequestBody`; default `priority: "medium"`, qolgan maydonlar bo'sh.
- Mijoz maydoni — `Clients/ClientCombobox` (server-side qidiruvli; yangi mijoz combobox popover footeridagi inline `AddClient` orqali qo'shiladi); izoh `OrderFields` dan keladi, `notesPlaceholder="Maxsus talablar (masalan, qora kromka)"` bilan.
- Mutation: `OrdersService.createOrder`; muvaffaqiyatda toast va yangi buyurtma sahifasiga `navigate`.
- Dialog yopilganda (`onOpenChange`) forma `reset()` qilinadi. Busiz: mijoz tanlab dialog Escape/X bilan yopilsa `client_id` formada qolar, combobox esa unmount bo'lib qayta ochilganda "Mijozni tanlang" ko'rsatardi — menejer bo'sh ko'ringan formadan ko'rinmas mijozga buyurtma yaratardi.

### `frontend/src/components/Orders/EditOrder.tsx`

**Maqsadi:** buyurtmani tahrirlash dialogi (manager) — AddOrder bilan umumiy `orderForm.tsx` (schema, maydonlar, payload), qiymatlar `values:` orqali `order` dan olinadi (pul maydonlari `moneyToInput` bilan — u `null` ni `""` ga aylantirib `formatMoneyInput` ni chaqiradi; API'ning `"14000000.00"` Decimal-satridagi kasr qismini `formatMoneyInput` ning o'zi tashlaydi — birinchi `.`/`,` sonning tugashi, summa 100 barobar oshmaydi; ilgari u faqat raqamlarni qoldirardi va kasr nollari summaga yopishardi).

- Mijoz maydoni — `ClientCombobox` (`initialLabel={order.client_name}`, `disabled={!isDraft}`) — DRAFT dan keyin mijoz almashtirilmaydi ("faqat qoralamada almashtiriladi"; backend ham shu qoidani ushlaydi).
- Mutation: `OrdersService.updateOrder` (`crudCallbacks(queryClient, ["orders"], …)`); muvaffaqiyatda toast + dialog yopiladi. `onSaved` propi YO'Q: `["orders"]` prefiksi `["orders", id]` va `["orders", id, "matrix"]` ni ham qamraydi, chaqiruvchidagi ikkinchi invalidatsiya har saqlashda ortiqcha so'rov berardi.

### `frontend/src/components/Orders/MachineAssign.tsx`

**Maqsadi:** ish markazi tanlovi paneli — `requires_assignment_choice` bo'lgan postlar uchun stanokni odam aniq tanlaydi. Panelni manager ham, texnolog ham ko'radi (`orders/$orderId.tsx`: `(canManage || isTexnolog) && canEdit && order.project_uuid`) — marshrutni texnolog chizadi, ya'ni qaysi stanok qaysi ishni bajarishini yaxshiroq biladi.

- Bitta IXCHAM QATOR (karta emas — bitta select uchun sarlavhali karta sahifada og'ir turardi): «Ish markazi:» + har post uchun `POST_COLORS` rangli kod + faol ish markazlari selecti (`h-8 w-56`; `getPostsQueryOptions` + `getMachinesQueryOptions`) + `size="sm"` «Biriktirish». Faqat HAQIQIY tanlovda ko'rinadi — postda 2+ aktiv stanok bo'lsa (`withChoice`); bittasi bo'lsa qator yo'q, backend ishlab chiqarishga uzatishda o'zi biriktiradi (`start_order_production`) — bitta variantli select odamga ortiqcha majburiy qadam edi; `OrdersService.assignOrderMachines` ga saqlanadi (`crudCallbacks(queryClient, ["orders"], …)` — `onSaved` propi yo'q); tanlov talab qiluvchi post bo'lmasa `null` qaytaradi.
- Selectda `emptyLabel="Biriktirilmagan"` varianti bor — biriktirishni BEKOR qilish mumkin (bo'sh qiymatlar payload'dan tushadi, server esa `machine_assignments` dict'ini butunlay almashtiradi). "Biriktirish" tugmasi faqat tanlov boshlang'ich holatdan farq qilganda faol: aks holda bo'sh formada bosib hamma biriktirishni tasodifan o'chirib yuborish mumkin edi.

### `frontend/src/components/Orders/PartMapDialog.tsx`

**Maqsadi:** detalning kesish xaritasini SHU SAHIFADA ko'rish — `PartMapButton({ orderId, partKey })`: matritsa qatoridagi va nostandart kartochkasidagi xarita ikonkasi. Bosilganda katta dialog (`sm:max-w-[min(1400px,96vw)]`, `h-[88vh]`) ochilib ichida haqiqiy `Terminal/CutmapView` (`admin`, `focusPartKey=partKey` — detalning listi ochiladi, katagi belgilanadi; zoom/pan, listlar orasida o'tish ishlaydi) chiziladi; sarlavhada «To'liq sahifada» havolasi (`/cutmap/$orderId?part=`). Esc/tashqariga bosish yopadi; `onBack` (xarita yo'q — TEMPLATE) ham yopadi. Faqat ochiqda render — yopiqda xarita so'rovi ketmaydi (query keshi `["admin","cutmap",id]` — sahifa bilan umumiy).

- Nega dialog, «bosib turish» emas: ushlab turgan holda zoom/surish yo'q, jest taxmin qilinmaydi, sensorda kontekst-menyu/matn tanlashni chaqiradi. Nega sahifaga o'tish emas: texnolog marshrut chizayotganda «bu detal qayerda» deb qaraydi — dialog tahrir holatiga (`stageEdits`, `draft`) tegmaydi, orqaga qaytish yo'q.

### `frontend/src/components/Orders/UnplacedParts.tsx`

**Maqsadi:** kesish xaritasida joyi yo'q detallarni texnologdan yashirmaslik. Arra terminali chekni FAQAT xaritadagi katakdan chiqaradi — GibLab listga joylamagan detalni arrachi ko'rmaydi. Ilgari bu ogohlantirish 4 soniyalik yashil toastda (5 ta nomgacha kesilib) chiqardi; 2026-09-26 da B-2026-088 ning uchta stoleshnitsasi shu yo'l bilan arrada qotgan.

- `UploadWarningsDialog({ result, onClose })` — `.project` yuklangach, javobda `unplaced_parts` yoki `unplaced_arra_parts` bo'sh bo'lmasa ochiladi (`orders/$orderId.tsx`; bo'lmasa avvalgidek toast). O'zi YOPILMAYDI — «Tushunarli» tugmasi. Tarkibi: tavsif — server `message` ining xulosa qismi (`" Diqqat ("` gacha; kesilgan ro'yxat ikkinchi marta chiqmasin), qizil blok — marshrutida Arra bor detallar («buyurtmani ishlab chiqarishga uzatib bo'lmaydi»), amber blok — xaritada joyi yo'q hamma detal (profil kabi listdan kesilmaydigan detal bo'lsa hammasi joyida, deb tushuntiradi), so'ng qolgan ogohlantirishlar. Shu ikki ro'yxatning `warnings` dagi matnli nusxasi (`"Kesish xaritasida"`, `"Marshrutida Arra bor"` bilan boshlanadiganlar) «Boshqa ogohlantirishlar» dan chiqarib tashlanadi — takrorlanmasin.
- `UnplacedArraBanner({ parts, status, canEdit })` — buyurtma sahifasida `order.unplaced_arra_parts` bo'sh bo'lmasa (va buyurtma bekor qilinmagan bo'lsa) qizil banner: «Arrachi N ta detalni ko'rmaydi — kesish xaritasida joyi yo'q», yechim (GibLab'da listga joylab qayta yuklash; Rover'da kesilsa marshrutni Rover'dan boshlash), `technical_review` da «uzatib bo'lmaydi» izohi, fayl qulflangan bo'lsa «adminga murojaat qiling». Ro'yxat — `PartList` (monospace, `max-h-48` ichida aylanadi).

### `frontend/src/components/Orders/OrderMatrix.tsx`

**Maqsadi:** texnolog matritsasi — qatorlar: detallar, ustunlar: STANDART detalning postlari, ya'ni `getPostsQueryOptions` ro'yxati `STANDARD_MATRIX_POSTS` (`@/lib/mes` — ARRA, KROMKA, PRISADKA) bo'yicha filtrlanadi. Rover/stolyarka/bo'yoq/oval ustunlari olib tashlangan: fayldan avtomatik marshrut faqat shu uch postni beradi (roverdan chiqqan detal keyin bo'yalishi mumkinligini fayl bilmaydi), qolgani hech qachon to'lmaydigan bo'sh ustun bo'lib turardi — ular endi "Nostandart detallar" tabida qo'lda chiziladi.

- O'qish rejimida har katak `total_done/total_required` progress (`POST_COLORS`, tugallanganda "✓"), o'chirilgan bosqich "—". Bitta post marshrutda BIR NECHA MARTA kelishi mumkin (kromka → prisadka → yana kromka), shuning uchun katak shu postdagi barcha qadamlarning yig'indisini ko'rsatadi.
- `editable` bo'lsa "Marshrutni tahrirlash" rejimi: bosqich checkboxlari + izoh inputlari + "Nostandart" katakchasi, hammasi bitta `OrdersService.editOrderMatrix` batchida saqlanadi (`crudCallbacks`, kalit `["orders", orderId]` — matritsa ham, buyurtmaning o'zi ham: marshrut o'zgarsa sahifadagi «xaritada joyi yo'q» banneri yangilansin; ilgari faqat `["orders", id, "matrix"]` edi). Checkbox locked bo'ladi ikki holatda: ARRA (standart detalda majburiy) va detal nostandart bo'lsa (uning marshruti bu yerda emas, alohida tabda chiziladi).
- **"Nostandart" ustuni** (post ustunlaridan keyin): o'qish rejimida marshrut nomlari (`routeStepNames`, bitta satr), marshruti yo'q nostandartda amber «marshrut yo'q», standartda «—» (batafsil pastda), tahrirlashda `Checkbox` → `MatrixPartEdit.is_custom`. Belgilangan detal fayldan avtomatik marshrut olmaydi (mavjud avtomatik qadamlar yumshoq o'chadi, bayroq qaytarilsa aynan tiklanadi), marshrutini texnolog `Orders/CustomRoutes` da chizadi. Katakcha almashtirilganda shu detalning KUTAYOTGAN bosqich tanlovlari `stageEdits` dan olib tashlanadi: katakchalar qulflanishi faqat keyingi bosishlarni to'xtatadi, oldin belgilanganlari esa o'sha batchda `is_custom` bilan birga ketib, backend endigina qayta qurgan marshrutga tegib ketardi.
- Boshqaruv qatorida detal qidiruvi ("Qidirish: kod yoki nom...") va `N / M detal` hisobi; jadval balandligi 70vh bilan chegaralangan, sarlavha sticky.
- Har detal kodi yonida xarita ikonkasi — `PartMapButton` (`Orders/PartMapDialog.tsx`): kesish xaritasi SHU SAHIFADA dialogda ochiladi, detalning listi ochilib katagi belgilanadi (`CutmapView` `focusPartKey` oqimi); to'liq sahifa (`/cutmap/$orderId?part=...`) — dialog sarlavhasidagi «To'liq sahifada» havolasida.
- Nom ostida ALOHIDA «Nostandart» belgisi YO'Q (u qatorni cho'zardi va ustun bilan takror edi). **«Nostandart» ustuni o'qish rejimida marshrutning O'ZINI ko'rsatadi** — BITTA satr «Raspil → Kromka → G petlya o'ngdan» (`routeStepNames`, `lib/mes`: `is_enabled` va dumsiz, `seq` bo'yicha jarayon NOMLARI; `truncate`, to'lig'i `title` da), nostandart-u marshruti hali chizilmaganida amber «marshrut yo'q» (`title` da tushuntirish), standart detalda «—»; ilgari «✓» turardi va u hech narsa demasdi (oraliq variant — raqamlangan chiplar — tor ustunda har biri alohida qatorga tushib qatorni cho'zardi). Tahrir rejimida o'sha ustun — `Checkbox`.
- Qidiruv — `Common/SearchInput` (lupa ikonkasi bilan, reestr bilan bir xil; oddiy `Input` topilishi qiyin edi). To'liq chek/QR satri ham qabul qilinadi: `B-2026-047_301401_01_001_2` dan buyurtma prefiksi (`^B-YYYY-NNN_`) va `_n` nusxa raqami (faqat 3 xonali detal kodidan keyin) tashlanadi → `301401_01_001` qatori topiladi. Qator = DETAL, nusxa emas — shuning uchun jadvalda ID prefiks va `_n` siz (`{product_code}_{code}`, docs/11 dagi «Kod» ustuni qoidasi bilan bir xil); to'liq serial nusxalarda — chek, skan, SCX, xarita kartochkasi. «Nostandart» ustun sarlavhasi tugma: bosilganda nostandart detallar YUQORIGA (`customFirst`, `aria-sort`, faol `ArrowUp`, nofaol xira `ChevronsUpDown`).
- `toolbarContainer?: HTMLElement | null` — boshqaruv qatori (qidiruv + hisob + «Marshrutni tahrirlash»/Saqlash) `createPortal` bilan shu elementga chiqadi; buyurtma sahifasi tab'lar qatorining o'ng tomonini beradi (`empty:hidden` slot), jadval ustida alohida qator qolmaydi. Berilmasa (manager/direktor — tab'siz ko'rinish) jadval ustida o'z qatorida.
- Izoh inputi CONTROLLED (`value={noteEdits[part.id] ?? part.note ?? ""}`): qidiruv filtri qatorni unmount qilib qaytarganda `defaultValue` bilan kiritilgan matn ekrandan yo'qolib, `noteEdits` da qolib ketardi — texnolog server izohini ko'rib turib, saqlash o'sha ko'rinmas matnni yozardi.
- Ma'lumot: `getOrderMatrixQueryOptions(orderId)`; o'lchamlar `formatSize` (`@/lib/mes`) bilan. So'rov yiqilsa Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`) — ilgari xato bo'sh holatga tushib, texnolog "Detallar yo'q — avval .project fayl yuklanishi kerak" degan yolg'on sababni o'qirdi.

- Soni 0 detal (GibLab faylida shunday keladi, prod bazasida 2 ta): soni xira, bosqich kataklari «—» — ilgari 0/0 «✓» bo'lib «tayyor» degan yolg'on taassurot berardi.

### `frontend/src/components/Orders/PartTrace.tsx`

**Maqsadi:** «Bu detal qayerda?» — OFIS javobi. Tsexda operator javobni o'z postidagi ro'yxatdan oladi (kromka sahifasida kelmagan nusxa qaysi postda turgani chipda yozilgan); ofisda savol boshqa — buyurtma nimadan to'xtab qoldi, detal kimda qolib ketdi.

- **Alohida maydon YO'Q.** Reestrdagi bitta qidiruv maydoni ikki javob beradi: `looksLikePartId(q)` rost bo'lsa jadval o'rniga shu panel chiqadi, buyurtma so'rovi esa `enabled: false` bo'ladi (bunday matn hech qachon raqam/nom/mijozga tushmaydi, javob doim bo'sh bo'lardi); reestrning «Faqat oxirgi 100 ta buyurtma ko'rsatilmoqda» izohi ham bu rejimda chiqmaydi (`!detalRejimi`, 2026-09-27 gacha panel ostida qolib ketardi).
- **Ajratgich — SHAKL bo'yicha, «`_` bor» emas.** «Pastki chiziq bor» qoidasi sinalib RAD ETILDI: prodda 82 buyurtmaning **45 tasida** loyiha nomida `_` bor (`3168_Muzaffar`, `4357_Murod_aka`), ya'ni u buyurtmalarning yarmini qidirishni buzardi. O'rniga ikki naqsh (prodda 5802 nusxa, 82 buyurtma, 46 mijozda o'lchangan):

  | Naqsh | Detal ID qamrovi | Yolg'on ijobiy (raqam/loyiha/mijoz) |
  |---|---|---|
  | `ORDER_PREFIX` = `^B-\d{4}-\d+_` (`lib/mes`) | **5802/5802** | **0** |
  | `PREFIKSSIZ` = `^\d{3,6}_\d{1,3}_` | qisman | **0** |

  Birinchisi chekda yozilgani — odam aynan shuni ko'chiradi; ikkinchisi buyurtma prefiksisiz, faqat detal kodini yozganlar uchun. Prefiks naqshi `lib/mes.ts: ORDER_PREFIX` da YAGONA: ilgari u `Serial`, `OrderMatrix` qidiruvi va bu yerda uch marta qo'lda yozilgandi va uchinchisi `\d{3}` bilan TOR edi — yilning 1000-buyurtmasi (`B-2026-1000_...`) tanilmay qolardi, chunki `next_number` `:03d` (MINIMAL kenglik) bilan yozadi.
- Ma'lumot — `getInstanceTraceQueryOptions(q)` → `GET /orders/instances?q=` (`StaffReadUser`: manager, texnolog, direktor, admin; frontda `isProductionStaff` bilan bir xil to'plam). Yangi ma'lumot yig'ilmaydi — backend `Scan` + `PartRoute` + `PartDefect` dan hisoblaydi.
- Har nusxa — kartochka-havola (buyurtma sahifasiga): Detal ID (`num`, primary) → detal nomi · buyurtma raqami → marshrut. Marshrut YANGI element emas — `Common/StagePipeline showLabels` qayta ishlatiladi (`steps[].post_code/done/need`), ya'ni ofis buyurtma sahifasi sarlavhasida ko'rgan bilan BIR XIL vizual grammatika. Nostandart marshrut avtomatik to'g'ri chiqadi: kataklar detalning O'Z marshrutidan keladi (prodda 9 xil shakl tekshirildi — KROMKA'siz, PRISADKA'siz va 4 qirrali variantlar).
- Ostida bitta satr matn, TO'RT holatda:
  - `last_post != next_post` — «**KROMKA** dan o'tgan · 2 soat oldin → **PRISADKA** navbatida»;
  - `last_post == next_post` — detal shu postda hali **ish ostida**: «**KROMKA** da — ish ostida (2/4) · oxirgi skan 2 soat oldin». Bu holat ko'p qadamli postlarda odatiy (kromkada `per_instance` 4 gacha); ajratilmasa matn «KROMKA dan o'tgan → KROMKA navbatida» bo'lib bema'ni chiqardi;
  - skansiz — «Hali skanlanmagan — **ARRA** dan boshlanadi»;
  - marshrutsiz — «Marshrut belgilanmagan» (aks holda «— dan boshlanadi» bo'lib chiqardi).

  `last_post` — oxirgi SKAN qaysi postda bo'lgani (detal jismonan o'sha yerda), «oxirgi TUGAGAN qadam» EMAS (`scanning.instance_stages` dan farqi shunda).
- Ochiq brak (`pending`/`confirmed`) bo'lsa pastda qizil satr: «BRAK · KROMKA — sabab». Rad etilgan (`rejected`) brak KO'RSATILMAYDI.
- Chegara 50 nusxa; yetilganda «Detal ID ni to'liqroq kiriting» eslatmasi.

### `frontend/src/components/Orders/CustomRoutes.tsx`

**Maqsadi:** "Nostandart detallar" tabi — matritsada `is_custom` deb belgilangan detallarning marshrutini texnolog QO'LDA chizadi. Fayl bunday detalning yo'lini bilmaydi (nomdagi `{kodlar}` sintaksisi olib tashlangan, marshrut endi detal nomiga umuman bog'liq emas), shuning uchun yagona manba — texnologning shu ekrandagi tanlovi.

- Props: `{ orderId: number; editable: boolean }`. Ma'lumot — `OrderMatrix` bilan AYNAN bitta query (`getOrderMatrixQueryOptions(orderId)`, TanStack dedupe qiladi), `parts.filter(p => p.is_custom)`; nostandart detal bo'lmasa tushuntirish matni chiqadi ("Detallar matritsasida 'Nostandart' ustunidan belgilang"). So'rov xatosida (`isError`) bo'sh holat emas, `Common/QueryError` chiziladi — aks holda 500 "nostandart detal yo'q" bo'lib ko'rinardi.
- Kartochka sarlavhasining o'ngida marshrut XULOSASI — bitta satr, nomlar bilan: «Raspil → Kromka → G petlya o'ngdan» (`PROCESS_OPS`; bo'sh bo'lsa «marshrut tanlanmagan»; Arra/Rover'dan boshlanmasa yoki bo'sh bo'lsa qizil; `truncate`, to'lig'i `title` da) — ilgari `1 / 3 / 11` kodlar edi. Tartibning o'zi TUGMALARDA: tanlangan tugma POST RANGIDA (`chipColors(POST_COLORS[post], 22)` — matritsa chiplari bilan bir til: ARRA apelsin, KROMKA ko'k-yashil, PRISADKA binafsha…; ilgari `primary` navy — tizim rang tiliga yot edi) va ichida qadam raqami + jarayon nomi + post kodi («1 Raspil ARRA») — «nechanchi bo'lib qaysi postga» tugmaning o'zida, ilgari post faqat `title`da edi. Kartochka sarlavhasida matritsadagi kabi xarita tugmasi (`PartMapButton` — shu sahifada dialog, qarang `Orders/PartMapDialog.tsx`). Tugmalar o'qish rejimida ham turadi (o'chirilgan) — texnolog shu ko'rinishga o'rgangan; ko'rsatma matni va biriktirish selecti (biriktirilmagan bo'lsa) faqat `editable` da. Kartochka `bg-card` — sahifa fonidan ajralib tursin.
- Har detal kartochkasida `PROCESS_OPS` ning 16 kodidan marshrut DUMI — `TAIL_CODES` (`@/lib/mes` — UPAKOVKA 15 va TMO 16) chiqarilib, qolgan 14 kodi tugma bo'lib chiziladi (`CODES` konstantasi, `title` da `kod · POST`) — qadoqlashni texnolog tanlamaydi, uni anketadagi "Upakovka qilish" bayrog'iga qarab backend oxirgi qadam qilib o'zi qo'shadi. Tugma bosilsa kod marshrut oxiriga QO'SHILADI va tanlangan tartibda raqamlanadi (1, 2, 3...); bitta jarayonni qayta bosish yangi qadam beradi (kromka → prisadka → yana kromka — shuning uchun tugmada `1,3` kabi bir necha raqam turishi mumkin), OXIRGI qadamni bosish esa uni bekor qiladi.
- Validatsiya: marshrut bo'sh bo'lmasligi va `ROUTE_START_POSTS` (`@/lib/mes` — ARRA yoki ROVER) dan boshlanishi shart — chek shu birinchi postda chiqadi. Buzilgan detal kartochkasi qizil ramkada, tepada nechta ekani sanaladi (`incomplete` — HAMMA nostandart detal); "Saqlash" tugmasi esa faqat TEGILGAN (`draft` dagi) detalning marshruti buzilgan bo'lsa bloklanadi (`blocking`) — tegilmagan to'liqsiz detallar saqlashga to'sqinlik qilmaydi, texnolog ishni bo'lib-bo'lib kiritadi (backend ham marshrutsiz detalni ishlab chiqarishga o'tkazmaydi).
- **Yig'ma buyum:** har nostandart detalni ASOSIY DETALGA biriktirish mumkin — kartochka pastida "Asosiy detalga biriktirish:" `SelectField` i (variantlar: o'zining oxirgi jarayoni bilan bir xil qadamga ega, hali hech kimga biriktirilmagan detallar). Biriktirilsa mayda detalning marshruti shu amalda TUGAYDI — qadoqlash/TMO faqat asosiy detalda. Bolalari bor detalda select o'rniga "Asosiy detal — `01_007 ×2` biriktirilgan" satri chiqadi. Tanlov `parents` state'da (`part_id -> assembly_parent_id`), saqlashda `edits[].assembly_parent_id` bo'lib ketadi (`0` = bog'lamni uzadi, backendga `null` yuboriladi).
- SAQLANGAN marshrutni o'qiyotganda (`codesOf`) dum kodlari filtrlanadi: backend `edits[].route_codes` ga dumni o'zi qo'shadi va uni qaytib qabul qilmaydi (`orders/matrix.py` — "Ruxsat etilgan: 1–14"), ya'ni filtrsiz qayta tahrir 403 berardi. Shu sababli "oxirgi qadam" (biriktirish variantlari filtri va "Marshrut … da tugaydi" matni) ham TMO emas, texnolog chizgan haqiqiy oxirgi amalni ko'rsatadi.
- Tahrirlar `draft` state'da (`part_id -> kodlar massivi`) yig'iladi, faqat tegilgan detallar; saqlash — `OrdersService.editOrderMatrix` (`crudCallbacks`, `["orders", orderId]` — `OrderMatrix` bilan bir xil sabab; `edits[].route_codes`, `stages: {}`, kerak bo'lsa `assembly_parent_id`; `draft` va `parents` id'lari birlashtiriladi), muvaffaqiyatda ikkala state ham tozalanadi. "Bekor qilish" tugmasi ham ikkalasini birga tozalaydi — `dirty` ikkalasidan hisoblanadi. `editable=false` bo'lsa tugmalar `disabled`, saqlash paneli umuman chizilmaydi (ko'rish rejimi).
- `routes/_layout/orders/$orderId.tsx` da texnolog uchun DOIM ikkinchi tab sifatida turadi ("Nostandart detallar (N)").

---

### `frontend/src/components/Orders/BazisPanel.tsx`

Buyurtma sahifasidagi **«3D model»** bloki (texnologda tab, menejer va direktorda matritsa ostida). **Uch qadamli oqim** (`Qadam`: raqam — bajarilganda navy doirada `Check`, joriysi navy halqa, kutilayotgani xira; o'ngda holat): Bazis fayllar project fayl yuklangach ochiladi, havola esa birinchi model yuklangach chiqadi (hamma mahsulot to'lishini kutmaydi). Nomlash: tab — natija («3D model», ochiq sahifa ham shunday ataladi), qadamlar — manba fayllar («Project fayl», «Bazis fayllar» — sahifadagi «Project fayl yuklash» bilan bir so'z). Format va himoya — [13-bazis-3d.md](13-bazis-3d.md). So'rov `useOrderBazis(orderId)`, kesh kaliti `["orders", id, "bazis"]` — `["orders"]` OSTIDA: `.project` qayta yuklansa va WS `order.*` hodisasida sahifa uni invalidatsiya qiladi; tab yorlig'i ham shu keshdan o'qiydi (ikkinchi so'rov ketmaydi). Qatorlar va hisob — `bazisHolati(state)`.

1. **Project fayl** — bajarilgan (buyurtmada mahsulot bor): fayl nomi va sanasi (`projectFile` — `order.files` dagi `project`), o'ngda «N ta mahsulot». Bajarilmagan: «Bazis fayllar project fayldagi mahsulotlarga bog'lanadi — avval uni yuklang» va, tahrirlash mumkin bo'lsa, «Project fayl yuklash» (`onUploadProject` — sahifa sarlavhasidagi o'sha tanlash oynasi).
2. **Bazis fayllar — har mahsulotga bitta** (o'ngda `K/N`; project yo'q bo'lsa xira, «Project fayl yuklangach ochiladi»; bajarildi — har mahsulotning modeli bor VA bog'lanmagan fayl yo'q). Ro'yxat — buyurtmaning HAR mahsuloti bitta qator (`products`, `.project` tartibida), buyurtmada kodi yo'q model ro'yxat BOSHIDA (muammo birinchi). Qatorda: eskiz (`GET /orders/{id}/bazis/{file_id}/thumb`, bosilsa ko'rish dialogi; modeli yo'q mahsulotda punktir `Box` katak), nom, `kod · N dona · M detal` (`num`). Amallar: modeli yo'q — «Bazis fayl yuklash» (`FileUp`, faqat `canUpload`; aks holda outline «Model yo'q»); modeli bor — «Model bor» (default `Badge`, navy — «Onlayn»/«Ulangan» bilan bir oila), «Ko'rish» (`Rotate3d`), «Almashtirish» (Bazisdan qayta eksport qilingan fayl), o'chirish (`ConfirmDialog`); bog'lanmagan — amber «Bog'lanmagan» va izoh «Bu Bazis fayli project faylga tegishli emas — ustalar chekdagi Detal ID bilan detal joyini topa olmaydi. O'chiring.» (yangi yuklash buni o'tkazmaydi — holat eski qatorlarda va `.project` qayta yuklangach qoladi). **Yuklash QATORDA**: tugma yoki faylni o'sha qatorga tashlash (ustida `ring`); so'rov `product_code` bilan ketadi — server fayldagi kod va nomni AYNAN shu mahsulot bilan solishtiradi (docs/13 §3). Rad etilsa server xabari qator ostida qizil «Yuklanmadi: …» bo'lib QOLADI (toast kabi yo'qolmaydi — texnolog o'qib, to'g'ri faylni tanlaydi); keyingi urinishda tozalanadi. `.b3d` bo'lmagan fayl so'rovsiz o'sha joyda rad etiladi. Bir vaqtda bitta fayl (serverda 1.7 s gacha CPU). Muvaffaqiyatda `toast.success` (««nom» — N detal yuklandi»). Alohida katta yuklash maydoni YO'Q: mahsulotlar ro'yxatining o'zi nima yuklanishi kerakligini aytadi (95% buyurtmada bitta mahsulot — bitta qator, bitta tugma). 2026-09-27 gacha: xulosa qatori + umumiy tashlash maydoni + nomi farq qilganlar uchun «Baribir yuklash» dialogi edi.
3. **Yig'uvchi uchun havola** — kamida bitta model bo'lgandagina (yoki havola ochiq qolgan bo'lsa — yopish uchun) chiqadi; direktorga faqat ochiq havola ko'rinadi. **`ShareBlock`**: havola yopiq — «Havolani ochsangiz, uni olgan usta modelni ko'ra oladi — tizimga kirmasdan. Boshqa buyurtmalar ochilmaydi» va «Havolani ochish»; ochiq — **QR** (`qrcode.react`, 116 px) + manzil + «Nusxalash» / «Yangilash» / «Yopish». QR ataylab: usta telefoni bilan bir skanda ochadi, 32 belgili tokenni terib o'tirmaydi. To'liq manzilni BRAUZER yig'adi (`window.location.origin` + `/3d/{token}`). Huquq: `canShare` (menejer ham — backend `ManagerOrTexnologUser`), `canUpload` (faqat texnolog, `.project` bilan bir qoida). «Yangilash» va «Yopish» ustalardagi havolani O'LDIRADI — ikkalasi `ConfirmDialog` bilan. Holat so'rovi kelmaguncha (`Skeleton`) yoki yiqilsa (`QueryError`) panel CHIZILMAYDI: ilgari shu paytda "havola yo'q" kartochkasi chiqardi va uning «Havolani ochish» tugmasi yangi token berib, ishlab turgan havolani o'ldirardi.

### `frontend/src/components/Orders/BazisPreview.tsx`

`BazisPreviewDialog` — panelda «Ko'rish»: texnolog ustaga aynan nima ketishini ochiq havolasiz, sahifadan chiqmasdan tekshiradi. Dialog `PartMapDialog` shaklida (`flex h-[88vh] flex-col gap-3 p-4 sm:max-w-[min(1400px,96vw)]`; sarlavhada `nom · kod`, havola ochiq bo'lsa o'ngda «To'liq sahifada» — `PartMapDialog` dagi bilan bir nom; `/3d/{token}`, ya'ni yig'uvchi havolasi ochadigan sahifa, yangi oynada). Qidiruvda yozuv bo'lsa Esc avval UNI tozalaydi (`onEscapeKeyDown` — Radix Esc'ni oldinroq ushlab, butun oynani yopardi), bo'sh qidiruvda Esc oynani yopadi. Bog'lanmagan modelda sarlavha ostida amber izoh. Model `GET /orders/{id}/bazis/{file_id}/model` dan (`staleTime: Infinity` — fayl `file_id` ga bog'langan, qayta yuklash yangi qator beradi), `MODEL_VERSIYA` tekshiruvi ochiq sahifadagi bilan bir xil; ko'ruvchi — o'sha `ModelViewer`, `React.lazy` bilan: three.js buyurtma sahifasi chunk'iga tushmaydi, dialog birinchi ochilganda yuklanadi. Kontent faqat dialog ochiqda chiziladi (so'rov va WebGL sahnasi yopiqda yaratilmaydi).

## Bazis 3D komponentlari — `frontend/src/components/Bazis/`

Ochiq sahifaning (`routes/3d.$token.tsx`) va panel ko'rish dialogining (`Orders/BazisPreview.tsx`) yadrosi. Aniq chegara bilan: **`model.ts`** — ma'lumot va sof funksiyalar, **`ilgak.ts`** — eshik ochilishining oraliq holatlari (faqat `three` ga bog'liq, `node` bilan sinab ko'rsa bo'ladi), **`scene.ts`** — three.js (Reactdan MUSTAQIL, chunki har kadrda React holatini yangilash telefonda kadr tezligini yo'qotardi), **`ModelViewer.tsx`** — ularni ulaydigan React qatlami. Sahifa `model.v` ni `MODEL_VERSIYA` bilan solishtiradi: boshqa versiyadagi (eski) model chizilmaydi, "Texnolog uni MESga qayta yuklasin" deyiladi.

### `frontend/src/components/Bazis/model.ts`

`BazisModel` / `BazisPanel` / `Furnitura` / `MeshQism` tiplari — backend `services/bazis/viewer.py` bilan QO'LDA oynalangan (kalitlar qisqa: `id`, `n`, `m`, `t`, `s`, `p`, `q`, `o`, `h`, `c`, `po`, `qo`, `g`, `rd`, `cp`, `r`; `meshes`, `furn`; docs/13 §4) va `MODEL_VERSIYA`. Qolgani sof funksiyalar: `materialColor` (avval Bazis katalogidan — `matRang.gen.ts`, topilmasa material nomidagi kalit so'zdan, docs/13 §7), `harakatBirligi` (panelning harakat birligi — `g`; harakatsizda `null`, `g` siz panel o'zi birlik), `harakatElementlari` (panellar + furnitura sahnadagi tartibda — sahna ham, boshqaruv ham birlik raqamini shundan oladi), `fasadlar` («Ichki» da konturga aylanadiganlar — `harakatElementlari` indekslari: eshik va surma eshik birligi butunlay, tortmaning old varag'i va undan oldindagi furnitura, harakatsiz «fasad» nomlilar va ularga tegib turgan 150 mm gacha furnitura — ilgak, qulf; nomdan emas, harakatdan — docs/13 §7), `maxsusYuza` (shisha / ko'zgu / ekran — uchalasi uch xil chiziladi), `isMetal` (furnitura metali), `materialTexture` (naqshli materialning rasmi, tayli, tola o'qi va ko'zgu ulanadigan o'qlari — `MAT_TEX`), `materialKorinishi` (kartochka uchun material nomi: plita kvadraturasi, formati, qalinligi va yetkazuvchisi olib tashlanadi — `normMat` dan alohida, u katalog kaliti), `modullar` / `modulKodi` (shkaflar — detal kodining birinchi bo'lagi; `00`, kodsiz, 4 tadan kam panelli va 60 mm dan yupqa guruhlar kirmaydi, bitta modulli mahsulotda bo'sh — docs/13 §7), `XONA_YUZASI` (devor, pol — doim xira, bosilmaydi) va `DEVOR_QOPLAMASI` (kafel — oddiy panel), `mebelEmas` (gabarit, haqiqiy qirra va modullarga kirmaydi: xona, kafel, `zamena`), `gabaritQirralari` (har o'q va chorak uchun gabarit o'lchami chiziladigan HAQIQIY qirra — panellar bo'ylab 80% qamrovli eng tashqi chiziq; U oshxonada eni orqa qatorda, quti qirrasi havoda bo'lsa ham — docs/13 §7), `matchPanel` (chekdagi to'liq Detal ID ni ham tushunadi — buyurtma prefiksi va mahsulot kodini olib tashlaydi; `_` bo'laklari bo'yicha solishtiradi, satr ichidan emas; 0 / 1 qisman / 2 aynan — docs/13 §7).

### `frontend/src/components/Bazis/scene.ts`

`createScene(canvas, onPick, qatlam?)` -> `{ load, setSelected, setFound, setPose, focusOn, nishonniQaytar, resetView, setPastkiBand, setYorliqZona, setOlchamlar, setIchki, dispose }`. `setIchki(yoniq)` — «Ichki» ko'rinish: `fasadlar` dagi panel `kontur` holatida (yuzasi 0.05, `depthWrite` siz; qirrasi `konturMat` bilan, tanlov yoki qidiruvda `fonQirraMat`), furniturasi butunlay yashirin (`visible = false`); kontur bosilmaydi va o'lcham nurini to'smaydi, fasadning o'zi topilsa/tanlansa oddiy tanlov/qidiruv rangida; bayroq model almashsa ham qoladi (`load` oxiridagi `applyStates` uni yangi modelga qo'llaydi). `setOlchamlar(yoniq)` — «O'lchamlar» tugmasi: gabarit va bazischining o'lchamlari (`model.d`); ular faqat kamera va harakat turganda joylanadi (nur bilan to'siq tekshiruvi), harakat paytida yashirin; tanlangan detalga tegadigan bazischi o'lchami tugmasiz chiziladi (docs/13 §7). `setYorliqZona(ust, past)` — o'lcham yorlig'i tushmaydigan qatlamlar (px): tepada tugmalar qatori, pastda kartochka + qidiruv; `ModelViewer` ularni ekrandagi haqiqiy o'lchamidan `ResizeObserver` bilan beradi. `qatlam` — `ModelViewer` dagi kanvas ustidagi `pointer-events-none` div: sahna unga tanlangan detal o'lchamining ikki yorlig'ini qo'yadi va har chizilgan kadrda O'ZI joylaydi (`olchamYangila`; eni va bo'yi detalning qirralarida, yorliq bilan 3D chizig'i doim birga — joy bo'lmasa ikkalasi yashiriladi; docs/13 §7). `controls.zoomToCursor` — yaqinlashtirish barmoq tomonga; `tick` uzoqlashganda (sig'dirish masofasining 85% idan) nishonni asta `fokus` ga qaytaradi; `nishonniQaytar` faqat `focusOn` ni qaytaradi (`fokusdanOldin`). Tanlovda uch qavat (`holatFor`): `tanlangan` (konturi `tanlanganQirraMat` — `depthTest` siz, `renderOrder` 10), `qoshni` (tanlanganga yopiq holatdagi qutisi 2 mm ichida tegadigan panel, 0.42; furnitura — `oddiy`; `setSelected` hisoblaydi, `qutilar` dan) va fon (`xira`, qirrasi `fonQirraMat` 0.13). `chiz` — o'lchamni chizmachilik qoidasi bilan: surilish yuza tekisligida bitta o'q bo'ylab (`gabaritOlcham`, `gabaritTomon` — 5% sustlik bilan), uzatma chiziq `TIRQISH` 3 px dan boshlanib `OSHISH` 6 px o'tadi, strelka (`STRELKA` 8 / `STRELKA_ENI` 2 px) har uchida o'z masshtabi bilan (`pikselda`), qirradan `OLCHAM_CHETI` 24 / `GABARIT_CHETI` 32 px, har nomzod oxirida `TOR_CHETI` 16 px bilan (`torga`); ekranda 20° dan kam og'gan yoki 5 barobar qisqargan variant tashlanadi; o'lchamning o'zi ko'rish yo'nalishiga 30° dan yaqin bo'lsa, past kamerada eni/chuqurlik ekranda tik ko'rinsa, yoki boshqa o'lcham uchi 10 px ichida bo'lsa (bir o'qdagi zanjirdan tashqari) ham. Gabarit yorlig'i «N mm», sig'masa «N» (`Olcham.matn`); qirrasi `gabaritQirralari` dan (`gabaritQirra`). **`focusOn(indexes)`** — kamera barcha nusxalarning umumiy markaziga boradi. `meshes` — avval panellar (`Mesh`, indeksi `panels` bilan bir xil), keyin furnitura (`Group`, qismlari umumiy `BufferGeometry` bilan); harakat massivlari ikkalasini qamraydi, bosish/qidiruv/qirra chizig'i faqat panellarda. `kes(geo, cp)` — profil uchini 45° ga kesadi (uch Z bo'ylab tekislikka suriladi). `panelMaterial(i, holat)` — naqshli materialda `[yuza (rasm bilan), yon devor (tekis)]`, rasm YUKLANGANDAN keyin qo'yiladi (`teksturaQoy`), undan oldin yuza o'rtacha rangda; teksturalar mahsulotlar orasida umumiy, burilgani `clone()`; chetlari tutashmaydigan o'qda `MirroredRepeatWrapping`, tola `r` va rasmdagi tola (`tolaU`) farq qilsa 90°. `naqshSiljit(geo, tex, burilgan, i)` — yuza UV'sini panel bitta tayl ichida qoladigan qilib siljitadi (har panel varaqning boshqa joyidan; docs/13 §7). **`setPastkiBand(px)`** — kanvas pastini egallagan qatlam (kartochka, natijalar) balandligi: kadr uning yarmicha yuqoriga suriladi (`camera.setViewOffset`, tween), orbit markazi joyida qoladi (docs/13 §7). Tanlov qidiruvdan ustun — tanlov bor bo'lsa qolgan topilganlar xira. **`setPose(ochiqBirliklar, explode)`** — MAQSAD holat BITTA chaqiruvda (qaysi harakat birliklari ochiq va ajratilganlik); harakatni sahnaning o'zi o'ynatadi. Har panel yopiq va ochiq holati orasida — eshik ikki holatdan tiklangan o'q atrofida buriladi (`ilgak.ts`), tortma to'g'ri chiziq bo'ylab suriladi (harakat ma'lumoti `.b3d` dan, docs/13 §2.7) — va ustiga ajratish. Holati o'zgargan birliklar KASKAD (`KASKAD_MS` 300: ekrandagi joyiga qarab chapdan o'ngga, tepadan pastga; yopilishda teskari; bitta birlik — kechikishsiz; paneli yo'q birlik — ichki mexanizm — ochishda eshiklardan KEYIN, yopishda OLDIN), har biri `HARAKAT_MS` 460, easeOutCubic; `prefers-reduced-motion` da darhol (docs/13 §7). Kamera masofasi eslab qolinmaydi — joriy masofa nisbat bilan kengaytiriladi, shuning uchun foydalanuvchining zoom'i saqlanadi. Kamera tween'i BITTA tutqichda (`tween`): yangi tween eskisini bekor qiladi. Yoritish `RoomEnvironment` (PMREM, 0.22) + KAMERAGA biriktirilgan ikki yo'nalish yorug'ligi (asosiy va to'ldiruvchi), tone mapping `NeutralToneMapping`, fon esa WebGL'da emas — `ModelViewer` dagi CSS gradient (kanvas `alpha: true`). Mahsulot tagida gradient kontakt soyasi (`shadowMap` emas — 268 panelda ikkinchi o'tish qimmat), AJRATILGANDA o'chadi. Panel — konturdan ekstruziya (`ExtrudeGeometry`, ichki kesmalar `h` va aylanalar `c` — `Shape.holes` ga), har panelda `EdgesGeometry` qirra chizig'i, tanlov/qidiruvdagi fonda u juda xira (`fonQirraMat` 0.13 — to'liq kuchda tanlangan detal ustida "qafas" bo'lardi); xona yuzasi va yashirin `zamena` qatlamida qirra yo'q. Materiallar `mat:holat` kaliti bilan keshlanadi va `clear()` da dispose qilinadi. Pan O'CHIRILGAN (mahsulot markazda turadi), aylantirish cheklanmagan (tagini ham ko'rish mumkin), masshtab `minDistance`/`maxDistance` bilan. Kamera gabaritni KAMERA ramkasiga proyeksiyalab sig'diradi; telefonda chegaralovchi burchak gorizontal bo'lgani uchun ikki burchakning kichigi olinadi va ekran burilganda foydalanuvchining burchagi saqlanib, masofa yetarlicha uzaytiriladi. Tanlash — `pointerup`, 8 pikseldan ortiq surilgan bosish aylantirish deb qabul qilinadi; barmoqlar `pointerId` to'plamida sanaladi va `pointercancel` ham tinglanadi; qidiruv faol bo'lsa nur faqat TOPILGANLARGA uriladi, xona yuzasiga esa hech qachon. Kadr faqat kerak bo'lganda chiziladi (`controls.update()` + "kir" bayrog'i) — batareya uchun.

### `frontend/src/components/Bazis/ModelViewer.tsx`

Props: `model` va ixtiyoriy `bogLanmagan` — model buyurtmaga bog'lanmagan bo'lsa (docs/13 §3), qidiruv bo'sh qolganda «Bunday detal topilmadi» ostida amber izoh: «chekdagi kod bilan topilmaydi, detal nomi bilan qidiring». `focusOn` — qidiruv ro'yxatidan yoki Enter bilan tanlanganda kamera detalga (barcha nusxalari markaziga) olib boriladi (sig'dirish masofasining 62% i: atrofi ko'rinib tursin); nishon panelning JORIY pozasidan olinadi, 3D da bosilganda esa kamera qimirlamaydi, lekin detalning barcha nusxalari tanlanadi (`nusxaKaliti`: kod + nom + o'lcham — qidiruv guruhi bilan bir xil kalit). Kartochka va natijalar bitta o'ramda (`ustRef`), uning balandligi `ResizeObserver` bilan `setPastkiBand` ga beriladi. Qidiruv `<search><form>`: Enter — birinchi natija (ajratib ko'rsatiladi; skaner ham Enter yuboradi), keyin input `blur` — telefonda klaviatura yopiladi; Esc — qidiruv va tanlov tozalanadi; natijalar ro'yxati `max-h-[min(19rem,34dvh)]`. Kartochka yopilganda `nishonniQaytar` nishonni ham, masofani ham qaytaradi — fokus vaqtinchalik chekinish. Holat va kartochkadan almashtirilgan birliklar (`almashgan` — holatga TESKARI qo'yilganlar) `ochiqBirliklar` ga yig'iladi va `setPose` ga beriladi; kartochkada detal turgan shkaf — «Moduli №04 · 790 × 750 × 518 mm» (`modullar`, mahsulotda bir nechta shkaf bo'lsa), harakatlanadigan detal uchun «Ochish»/«Yopish» (tanlangan nusxalarning barcha birliklari). Model almashsa tanlov, qidiruv va holat EFFEKTDA emas, RENDER paytida tiklanadi — aks holda `setPose` effekti eski «Ochiq» bilan yangi modelni bir marta ochib yuborardi. Kartochkaning yopish tugmasi `aria-label="Kartochkani yopish"` («Yopish» — eshik tugmasi). Kanvas ustidagi qatlam: o'ngda **segmentli tanlov** («Yopiq / Ochiq / Ichki / Ajratilgan» — ikonka va yozuv bilan, tor ekranda (`sm` dan past) faqat faol holatning yozuvi, qolganlari `sr-only` + `title`; holatlar bir-birini istisno qiladi, shuning uchun tugmalar to'plami emas; «Ochiq» ochiladigan detali, «Ichki» fasadi (`fasadlar`) yo'q modelda ko'rsatilmaydi; «Ichki» pozasi — «Yopiq» niki, ustiga `setIchki(true)`) va yonida ko'rinishni tiklash tugmasi (44 px — barmoq o'lchami), pastda doimiy qidiruv maydoni (yonida «O'lchamlar» chizg'ich tugmasi, 48 px, `aria-pressed`; holati `localStorage` `mx3d-olcham` da, xotira yopiq bo'lsa o'chiq boshlanadi) va tanlangan detal kartochkasi (kod — `num`, nomi, o'lchami — qalinligi 0 bo'lsa yozilmaydi, materiali — `materialKorinishi` bilan shovqinsiz, to'liq nomi `title` da; kromka ataylab YO'Q — u chekda bor, docs/13 §4). Qidiruvda kod AYNAN topilsa faqat o'sha ko'rsatiladi, aks holda aniqrog'i yuqorida, keyin kod tartibida (`Intl.Collator` numeric, kodsizlari oxirida); bir xil kodli nusxalar bitta qatorga yig'iladi (`×2`): chap va o'ng eshik bir xil detal, ro'yxatda ikki marta chiqib xatodek ko'rinardi.

## Anketa sahifasi — `frontend/src/routes/_layout/anketa.$orderId.tsx`

Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i) sahifasi — ~790 qator. Ilgari UI bo'laklari ham shu faylning o'zida turardi; hozir ular `components/Anketa/` da (`fields.tsx`, `RoomPhotos.tsx`, `RoomSummary.tsx`) — sahifa faqat holat, saqlash va bo'limlar tartibini yuritadi. Variantlar katalogi alohida: `frontend/src/lib/anketa.ts`.

**Ma'lumot oqimi:** `Order.survey` (JSONB) — `OrderSurvey { version, measured_at, measured_by, packaging, delivery, installation, rooms[] }`; xona `SurveyRoom` (materiallar, o'lchamlar, `walls: SurveyWall[]`, `modules: SurveyModule[]`). Saqlash `OrdersService.saveOrderSurvey` (`PUT /orders/{id}/survey`); xona rasmlari JSON'da emas, `OrderFile(kind=DOCUMENT, meta.room_id)` da (`OrdersService.uploadRoomPhoto` / `deleteRoomPhoto`) — shuning uchun avtosaqlash bilan aralashmaydi.

**Sahifa xulq-atvori (`AnketaPage`):**

- Server ma'lumoti **faqat bir marta** state'ga yuklanadi (`loaded` ref) — aks holda saqlashdan keyingi refetch menejer yozayotgan matn ustiga tushardi.
- Avtosaqlash: har tahrirdan 1.5s keyin (`dirty` bo'lsa va `canEdit` bo'lsa) `save.mutate`; `beforeunload` da ogohlantirish, unmount'da fire-and-forget `saveOrderSurvey`.
- `canEdit = isManager(currentUser) && !!order && !readOnlyStatus` (`isManager` — `@/lib/mes`: superuser yoki `role` `admin`/`manager`; `readOnlyStatus` — buyurtma `delivered`/`cancelled`, backend `_editable_order` 403 bilan bir xil shart) — faqat shunda forma; qolganlar (texnolog/direktor) va yopilgan buyurtmada menejer ham `RoomSummary` jamlanmasini ko'radi.
- Xonalar tab pill'lari: har pill — `div` konteyner, ichida xona nomi tugmasi (`r.name || "Xona N"`) va undan alohida `×` o'chirish tugmasi (`aria-label` "{nom} — o'chirish"; faqat `canEdit && rooms.length > 1` da chiziladi — ichma-ich `<button>` bo'lmasligi uchun ikkitasi alohida). `×` bosilsa `removeIdx` (`number | null`) belgilanadi va `ConfirmDialog` ochiladi — istalgan xona oldindan tanlanmasdan o'chiriladi (rasmlar ham o'chadi — backend `save_order_survey` da yetim rasmlarni tozalaydi). Yonida "Xona qo'shish" tugmasi.
- "Butun buyurtma uchun" kartasi (faqat `canEdit`, raqamlangan xona bo'limlaridan tepada): `ORDER_SERVICES` katakchalari — Upakovka qilish (`packaging`), Yetkazib berish (`delivery`), O'rnatish (montaj) (`installation`) — hamda o'lchov sanasi (`DatePicker`) va o'lchagan usta. Bular xonaga bo'linmaydi: tsex bitta `.project` fayl ustida ishlaydi, logistika butun buyurtmani bitta mashinada olib ketadi. Yuklashda eski anketalar migratsiya qilinadi — biror xonaning `extra_services` da `yetkazish`/`montaj` bo'lsa, buyurtma bayrog'i yoqiladi va kod xona ro'yxatidan olib tashlanadi (avtosaqlash keyingi tahrirda yangi shaklni yozadi).
- Pastda sticky saqlash paneli: holat matni ("Saqlanmoqda..." / "Saqlanmadi — qayta urinib ko'ring" — `role="alert"` + `text-destructive` / "O'zgarishlar avtomatik saqlanadi" / "Saqlandi HH:MM" / "Hammasi saqlangan") + `LoadingButton`. Manfiy margin (`-mx-6 md:-mx-8`) bilan main padding'i qoplanadi; suvbelgi va dekor konteyner olib tashlangach `routes/_layout.tsx` da `overflow-hidden` umuman yo'q — `sticky` to'siqsiz ishlaydi.

**Bo'limlar (qog'oz anketa raqamlari bilan):** 1 Xona va rasmlar · 2 Qanday mebel kerak · 3 Xonadagi shakli va o'lchamlari · 4 Korpus materiali · 5 Fasad materiali · 6 Furnitura va qo'shimcha xizmat · 7 Qo'shimcha izoh · 8 O'lchov varag'i (`<details>` ichida yopiq — zamerdan keyin usta to'ldiradi: A–E devor uzunlik/balandligi, modullar jadvali, umumiy pm/balandlik; o'lchov sanasi/ustasi bu yerda emas — ular "Butun buyurtma uchun" blokida).

**Sahifa ishlatadigan komponentlar** (hammasi `components/Anketa/` da — `RoomPhotos.tsx`, `RoomSummary.tsx` va qolganlari `fields.tsx` da):

| Komponent | Vazifasi |
|---|---|
| `RoomPhotos` | Xona rasmlari: butun panel drag&drop zona, `MAX_PHOTOS = 6`, `MAX_PHOTO_MB = 5`, MIME/hajm/soni klientda tekshiriladi; rasm bosilsa `Dialog` da katta ko'rinish + "Asl hajmda yangi oynada ochish"; rasmlar `<img crossOrigin="use-credentials">` bilan `/api/v1/orders/{id}/files/{fileId}` dan olinadi |
| `RoomSummary` | Texnolog/direktor ko'rinishi — tartib qog'ozning teskarisi: avval modullar jadvali va o'lchamlar, keyin material, so'ng mebel turi/xizmatlar (texnolog GibLab'da shu tartibda ishlaydi). `room` bilan birga `survey`, `orderId` va `photos` proplarini oladi: o'lchamlar bo'limining oxirida "O'lchov" (`survey.measured_at` — `survey.measured_by`) va "Buyurtma bo'yicha" (belgilangan `ORDER_SERVICES` yorliqlari) qatorlari; modullar bo'limidan keyin `RoomPhotos` ni `canEdit={false}` bilan chizadi (o'sha galereya, faqat yuklash/o'chirishsiz) |
| `Facts` | `dl` jadvali; bo'sh qiymatlar tashlab yuboriladi, hech nima yo'q bo'lsa "To'ldirilmagan." |
| `Section` | `n?` raqami + `title` + `hint?` bo'lgan karta (raqam qog'oz anketa bilan bir xil — menejer telefonda "3-bo'limga o'tamiz" deb ayta oladi) |
| `Field` / `Num` | Label + child; `Num` — `Field` + `NumInput` (`range` ni ham uzatadi) |
| `NumInput` | Raqamli maydon: yozilayotgan xom matn `raw` state'da saqlanadi (aks holda "3," yozilganda maydon o'zini tozalab qo'yardi), blur'da normallashadi; vergul o'nlik ajratgich sifatida qabul qilinadi (`numOrNull`); `integer` bo'lsa `Math.trunc`. `range={{ min, max }}` — backend chegarasi (shu faylda: `MM_RANGE` 0–50000, `PM_RANGE` 0–1000, `COUNT_RANGE` 1–999 — `schemas/orders.py` `_Mm`/`total_running_meters`/`count` ning QO'LDA oynalangan aksi): chegaradan chiqqan qiymat RAD ETILMAYDI (yozish jarayoni buzilmasin), lekin maydon `aria-invalid` bilan qizil bo'lib, ostida "0–50000 oralig'ida bo'lsin" izohi chiqadi. Busiz "Soni" ga yozilgan `0` yoki mm ga tushib qolgan qo'shimcha raqam butun anketaning avtosaqlashini 422 bilan to'xtatardi va menejer qaysi katak aybdorligini o'nlab katak ichidan izlardi (`utils.ts` pydantic massivini "Kiritilgan ma'lumot noto'g'ri" degan umumiy matnga aylantiradi) |
| `CheckCard` | Bitta belgilash katagi (butun katak bosiladi — sensorli ekran); tanlangan holat klassi (`border-primary bg-primary/5`) FAQAT shu yerda. `CheckGrid` ham, anketa sahifasidagi "Butun buyurtma uchun" kartasi ham shuni chizadi — ilgari ikkinchisi markupni qo'lda takrorlab, belgilangan xizmat tanlanmagandek ko'rinardi |
| `CheckGrid` | `CheckCard` lardan tuzilgan ko'p tanlovli to'r (`Option[]` + `values`) |
| `Choice` | Bitta tanlov, qayta bosilsa bekor qilinadi (radio'da imkonsiz); `h-9` — `Input` bilan bir xil balandlik |
| `ShapeChoice` + `SHAPE_ART` | Planirovka siluetlari (I / L / П / orolchali) — inline SVG to'rtburchaklar; mijoz "П-shakl (U)" jargonini emas, shaklni taniydi |

### `frontend/src/lib/anketa.ts`

Anketa variantlari katalogi — bazaga faqat `value` kodlari yoziladi, matnlar shu yerda (matn o'zgarsa tarix buzilmaydi).

- `Option = { value, label }`; ro'yxatlar: `FURNITURE_TYPES` (10), `LAYOUT_SHAPES` (4), `CORPUS_MATERIALS` (5), `CORPUS_THICKNESS` (16/18/boshqa), `FACADE_MATERIALS` (7), `COUNTERTOPS` (4), `HARDWARE_LEVELS` (oddiy/medium/premium), `EXTRA_SERVICES` (4 — led, rozetka, organayzer, oyna), `WALL_LETTERS` (`A`–`E`). Yetkazib berish va montaj bu ro'yxatdan chiqarilgan: ular butun buyurtmaga tegishli (`OrderSurvey.delivery` / `installation`).
- `labelOf(options, value)` va `labelsOf(options, values)` — kodni/kodlar ro'yxatini o'qiladigan matnga (`RoomSummary` ishlatadi).

---

## Sidebar komponentlari — `frontend/src/components/Sidebar/`

Claude.com uslubidagi yon panel: trigger sidebar ichida; desktopda alohida app header/footer yo'q, mobil rejimda esa `routes/_layout.tsx` da yupqa header bor (`h-12`, `md:hidden`) — `SidebarTrigger` + joriy bo'lim sarlavhasi (`sectionTitles` — `NAV_ITEMS` dan quriladi).

**Telefonda nishon o'lchamlari (2026-09-04, o'lchandi):** menyu bandlari `size="lg"` = 48 px (`Sidebar/Main.tsx`, `useSidebar().isMobile` bo'lganda; desktopda 32 px qoladi — sichqoncha), `_layout.tsx` dagi mobil header trigger `size-10` = 40 px (ilgari 28). Apple 44 / Google 48 minimum.

### `frontend/src/components/Sidebar/AppSidebar.tsx`

**Maqsadi:** ilovaning asosiy yon paneli — brend, navigatsiya va foydalanuvchi menyusini yig'adi.

- Modul darajasidagi `NAV_ITEMS` ro'yxati (rollar-modullar matritsasi, eksport — `routes/_layout.tsx` mobil sarlavhalari ham shu ro'yxatdan) 14 ta punkt beradi, har bandda `show(user)` predikati. Huquq predikatlari `@/lib/mes` dan — `isProductionStaff` / `isManagement` / `isAdmin`; **route guard'lar ham AYNAN shularni ishlatadi** (`lib/guards.requireAccess`), ya'ni menyuda ko'rinadigan sahifa albatta ochiladi. Bandlar: Boshqaruv paneli `/` va LIVE Tablo `/tablo` — mahsulot omborchisidan boshqa hammaga (`show: (u) => !isWarehouseOnly(u)`; TABLO tsex zalidagi TV ekran); Buyurtmalar `/orders`, Ish markazlari `/work-centers` — `isProductionStaff` (boshqaruv + texnolog); Mijozlar `/clients`, Hodimlar `/employees`, Hisobotlar `/reports` — `isManagement` (admin/manager/direktor); Tizim sozlamalari `/system-settings` (`SlidersHorizontal`; ish vaqtida o'zgaradigan qiymatlar — besh tab: «Umumiy» (nostandart belgisi, harakatsizlikdan chiqish), «Ish jadvali» (+ OEE boshlanish kuni), «To'xtash sabablari», «Ideal sikl» (Prisadka, Kromka), «Brak sabablari» (+ kromka o'lchovi); batafsil docs/05 `/system-settings`), MES agentlar `/agents` (`MonitorCog` ikonkasi — `Printer` EMAS: agent tsex kompyuteri, chek printeri va stanok skaneri ko'prigi; Prisadka agenti umuman chek chiqarmaydi; sahifaning ikkinchi bo'limi — chek qurilmalari, `Agents/TerminalDevices.tsx`) Loglar `/logs` (`ScrollText` ikonkasi) va Tizim holati `/system-health` (`Activity` ikonkasi — server tezligi: sekin endpointlar, event loop bloklari, chek kechikishi; Loglar va Tizim sozlamalari orasida) — `isAdmin` (superuser yoki `role === "admin"`); shuningdek Mahsulotlar ombori `/warehouse` — `isWarehouseStaff`, Brak `/defects` — `isManager`, Stanoklar `/tablo/stanoklar` — ombor xodimidan boshqa hammaga; Foydalanuvchilar bandi OLIB TASHLANDI — u Hodimlar sahifasiga birlashtirildi (`/admin` endi redirect). **Rolga qarab navigatsiya**.
- Buyurtmalar bandida jonli badge — **TOPSHIRISHGA TAYYOR** buyurtmalar soni (`counts.completed`; yashil, 0 bo'lsa yo'q, hover'da «Topshirishga tayyor — tsex tugatgan buyurtmalar») — inbox belgisi kabi amalga undaydi; ilgari «faol buyurtmalar soni» (57) turardi — hech qanday amalga undamasdi va reestrdagi «Hammasi» bilan chalkashardi: `getOrderStatusCountsQueryOptions()` reyestr sahifasi bilan AYNAN bitta query key'da, ya'ni `/orders` da TanStack dedupe qiladi va sidebar qo'shimcha so'rov qo'shmaydi. Qolgan admin sahifalarida sidebar YAGONA obunachi — `refetchInterval: 30_000` pollni o'zi yuritadi (`queries/mes.ts`, `docs/05` §5 `queries/mes.ts`). `enabled` faqat `/orders` bandi ko'rinadigan rollarda.
- `<Sidebar collapsible="icon">`: yig'ilganda faqat ikonkalar qoladi. Header'da `Link to="/"` — ichida faqat to'liq logo (`/assets/logo/logo-gold.png`, `h-9 w-auto`, `alt="MebeliX — bosh sahifa"`; login ekrani bilan bir xil brend), matn tuguni yo'q. Yig'ilganda BUTUN havola `group-data-[collapsible=icon]:hidden` bilan yashiriladi — brend tab sarlavhasi, favicon va login ekranida qoladi, bosh sahifa havolasi esa menyuning birinchi qatorida ("Boshqaruv paneli"). `SidebarTrigger` yig'ilgan railda `group-data-[collapsible=icon]:mx-auto` bilan markazga tushadi.
- **Tizim holati belgisi** (faqat band ko'rinsa, ya'ni admin): `SystemService.readSystemStatus` (`["system","status"]`, 60 s) — oxirgi 15 daqiqada `warn`/`bad` bo'lsa bandga `alert` va `alertTitle` («Oxirgi 15 daqiqa: <birinchi topilma> (yana N ta)») qo'shiladi. Hukm backendda (`services/system_health.py`) — sahifadagi xulosa bilan bir xil. `ok`/`nodata` da belgi yo'q.
- `SidebarContent` → `Main items={withBadges}` (rolga qarab filtrlangan `items` + Buyurtmalar/Brak `badge`/`badgeTitle` va Tizim holati `alert` maydonlari); `SidebarFooter` → `User user={currentUser}`.
- `SidebarContent` da brauzerning O'Z scroll chizig'i qoladi, faqat to'q fonga moslangan (`scrollbar-width: thin`, `scrollbar-color: sidebar-foreground 35% / shaffof`). Telefonda (500×725) menyu 724 px, ko'rinadigan joy 593 px — aylantirish shart, shuning uchun chiziq yashirilmaydi (NN/g «Scrolling and Scrollbars»: «Offer a scrollbar if an area has scrolling content»; o'z scrollbar'ini yasamaslik). Oldin Windows Chrome'da och kulrang, strelkali keng chiziq to'q menyuni kesib turardi.

**Bog'lanishlar:** `@/hooks/useCurrentUser`, `ui/sidebar.tsx`, `Sidebar/Main.tsx`, `Sidebar/User.tsx`. Layout route ichida `SidebarProvider` + `SidebarInset` bilan ishlatiladi.

### `frontend/src/components/Sidebar/Main.tsx`

**Maqsadi:** navigatsiya menyusi ro'yxati.

- Eksport: `type Item = { icon: LucideIcon; title: string; path: string; children?: SubItem[]; badge?: number; badgeTitle?: string; alert?: "warn" | "bad"; alertTitle?: string }`, `type SubItem = { icon; title; path; search?; match(search) }` va `Main({ items })`; `badge` bo'lsa (0 emas) band yonida yashil `SidebarMenuBadge` chiqadi (amal kutayotgan narsa: topshirishga tayyor buyurtmalar, tasdiq kutayotgan brak).
- `alert` — son emas, OGOHLANTIRISH (hozircha faqat «Tizim holati»): ochiq menyuda qizil/sariq doira ichida «!» (`bg-red-500/25 text-red-200` yoki `bg-amber-400/25 text-amber-200`, sidebar fonida kontrast 6,95 va 5,65:1), yig'ilgan railda badge yashirinadi — o'rniga ikonka ustida nuqta (`group-data-[collapsible=icon]:block`). Havolada `title={alertTitle}` va ekran o'qigich uchun sr-only «— muammo bor / e'tibor bering»; badge'ning o'zi `aria-hidden`. Holat faqat rang bilan berilmaydi.
- `useRouterState()` dan `currentPath` olinib faollik aniqlanadi: ildiz (`/`) uchun qat'iy tenglik, qolgan bandlar uchun prefiks moslik (`currentPath === item.path || currentPath.startsWith(item.path + "/")`) — shu tufayli `/orders/123` da ham "Buyurtmalar" yonib turadi; aktiv bandda chapdan 3px oltin chiziq `before:` pseudo-element bilan (`data-[active=true]:before:...w-[3px]...before:bg-sidebar-primary`) va ikonka `text-sidebar-primary` ga o'tadi — inset soya tugmaning rounded burchaklarida qirqilib ko'rinmasdi.
- Har band `SidebarMenuButton tooltip={item.title} asChild` ichida `RouterLink`; mobil rejimda bosilganda `setOpenMobile(false)` bilan panel yopiladi.
- **`children` li band — `NavGroup` (bo'limli band, hozircha faqat «Mahsulotlar ombori»).** Bitta qoida: YOPIQ bandni bosish — omborni (butun katalogni) ochadi va bo'limlarni ko'rsatadi; OCHIQ bandni bosish — bo'limlarni yopadi, sahifa o'zgarmaydi (`onClick` da `preventDefault()` — TanStack Link `!e.defaultPrevented` bo'lsagina o'tadi, `link.js`). Butun katalogga qaytish ham shu: yopib, qayta ochish — alohida «Hammasi» bandi yo'q. Ombordan chiqilganda bo'limlar o'zi yopiladi, kirilganda (boshqa havola bilan ham) o'zi ochiladi (`useEffect(() => setOpen(inside), [inside])`) — boshqa sahifada menyu qisqa. Havolada `aria-expanded` va ochiqda `aria-controls`; o'ngdagi `ChevronRight` ochiqda pastga buriladi (`motion-reduce` da animatsiyasiz). Faol: bo'lim tanlangan va ochiq bo'lsa — o'sha bo'lim; butun katalog yoki bo'limlar yopiq bo'lsa — ota («siz shu yerdasiz» yo'qolmasin); bir vaqtda bitta. Bo'lim faolligi `match(search)` bilan — sahifa qidiruvni qanday o'qisa shunday (ombor: `guruh` berilsa undan, aks holda `katalog`). Telefonda ota bosilganda menyu yopilmaydi (ochilgan/yopilgan bo'limlar ko'rinsin), bo'lim bosilganda yopiladi. Yig'ilgan railda bo'limlar va strelka yo'q, ota — oddiy havola, ombor sahifasining har ko'rinishida yonadi. Telefonda bo'limlar 44 px. 2026-09-27 da brauzerda haqiqiy sichqoncha bosishlari bilan tekshirilgan: desktop'da ochildi → yopildi → ochildi (URL o'zgarmay), Material ichidan yopish (Material'da qoladi) va ochish (butun katalog), boshqa sahifaga o'tganda yopilishi, rail; telefon (420 px iframe) — uch bosishda ham menyu ochiq, bo'lim tanlanganda yopiladi.

### `frontend/src/components/Sidebar/User.tsx`

**Maqsadi:** sidebar footeridagi foydalanuvchi kartasi va dropdown menyusi.

- Ichki `UserInfo({ fullName, phone })` — tema tokenlaridagi `Avatar` (`bg-sidebar-primary` oltin fon, `text-sidebar-primary-foreground` matn) + `getInitials()` (`@/utils`) initsiallari, ism va telefon. Ism bo'sh bo'lsa `displayName = fullName || "Foydalanuvchi"` ishlatiladi — initsial ham, ism qatori ham shu bitta qiymatdan, ya'ni nomsiz hisobda "F" beyji yonida bo'sh qator qolmaydi. Yig'ilganda ism/telefon ustuni ham, yonidagi `ChevronsUpDown` ikonkasi ham `group-data-[collapsible=icon]:hidden` bilan yashiriladi — aks holda avatar 32px ga qisqargan tugmadan (`sidebarMenuButtonVariants` da `group-data-[collapsible=icon]:size-8!`) toshib chiqardi; dropdown ichidagi nusxaga bu qoida tegmaydi (sidebar `group`i unga ajdod emas), ya'ni menyuda ism ko'rinaveradi.
- `User({ user }: { user?: UserRead | null })`: `user` bo'lmasa `null`. `SidebarMenuButton size="lg"` trigger → `DropdownMenu` (`side`: mobil bo'lsa "bottom", aks holda "right"): `DropdownMenuLabel` da yana `UserInfo`, so'ng "Sozlamalar" (`DropdownMenuItem asChild` ichida `RouterLink to="/settings"` — Radix `role="menuitem"` va roving-focus proplarini anchor'ning o'ziga qo'yadi) va "Chiqish" (`useAuth().logout()`).

---

## Terminal komponentlari — `frontend/src/components/Terminal/`

### `frontend/src/components/Terminal/CutmapView.tsx` (~920 qator)

**Maqsadi:** ARRA kesish xaritasi — GibSaw/GibLab uslubidagi ekran, GibCut litsenziyasi o'rnini bosadi. `routes/terminal.tsx` (operator) va `routes/_layout/cutmap.$orderId.tsx` (admin) ishlatadi; `admin` prop'ga qarab `OrdersService.readOrderCutmap` yoki `TerminalService.readTerminalCutmap` (`refetchInterval: 60_000`).

**Xato holati TEMPLATE dan AJRATILGAN:** `useQuery` dan `isError, refetch` olinadi va
Skeleton'dan keyin `Common/QueryError` chiziladi. Ilgari faqat `isLoading` tekshirilardi,
ya'ni 500/tarmoq xatosida `data` undefined qolib operatorga "fayl GibLabda optimizatsiya
qilinmagan (TEMPLATE)" degan YOLG'ON sabab ko'rsatilardi. TEMPLATE xabari endi faqat javob
kelgan-u `model === null` bo'lganda chiqadi.

**Props:** `orderId`, `onBack`, `admin?`, `postCode?: string` (default `"ARRA"`; `routes/terminal.tsx` ikkala chaqiruvda ham `ctx?.post_code` beradi — pastdagi "List egaligi"), `registerPrint?(fn)`, `statsContainer?: HTMLElement | null`, `toolbarContainer?: HTMLElement | null`, `focusPartKey?: string` — matritsadagi Map-havoladan (`/cutmap/$orderId?part=...`) kelganda detalning listini ochib katakni belgilaydi; detal xaritada topilmasa jim qolmaydi — "Bu detal kesish xaritasida joylashtirilmagan" toasti chiqadi (bayroq baribir yoziladi, 60s refetch toastni takrorlamasin).

**Kartochka QOLDIQ uchun ham BITTA**: `PartCard` detalni ham, ro'yxatga olingan qoldiqni ham aynan bir tartibda ko'rsatadi — sarlavhada katta `№` va yonida nom yoki o'lcham (qoldiqda qo'shimcha «QOLDIQ» bayrog'i), sarlavha OSTIDA chek ID si (`qr_text`) va holati (`✓ kesildi` / `✓ chek chiqarilgan`); keyin chizma, QR + ma'lumot, eng pastda to'liq kenglikdagi qizil «Chekni bekor qilish» (`h-14 w-full`) va «Yopish». Ilgari qoldiq alohida shox edi: bekor qilish «Yopish» ustida, ID umuman yo'q, o'lcham sarlavhada — bitta xaritada ikki xil kartochka. Qoldiqda faqat kromka ko'rsatilmaydi (u material, ishlov berilmaydi). Chizmada teshiklardan tashqari **paz/freza** ham bor (2026-09-13): chek eskizidagi bilan bir xil til — paz UZUQ, freza TUTASH ko'k chiziq, ammo bu yerda STILIZATSIYA emas, HAQIQIY yo'l (`CutmapState.machining`, `holeXY` orqali — ya'ni burilgan katakda ham to'g'ri tushadi va teshiklar bilan bir fazoda), detal chegarasida `clipPath` bilan qirqiladi (asbob kirish yo'li detaldan tashqarida bo'lishi normal). Matnda «Ishlov: paz N ta · freza N ta» — TOMON NOMI ataylab yozilmaydi, chunki katak burilgan bo'lishi mumkin va nom chizmaga zid tushardi. `part.txt` bo'lsa TEKSTURA ham chiziladi — YO'NALISHI varaq bilan bir xil (`rot` — tik, aks holda yotiq 3 chiziq, ya'ni uzunlik o'qi bo'ylab), NISBATLARI esa CHEKDAN (`labels.py`: chiziq uzunligi o'lchamning 0.32 i, oraliq ikkinchi o'lchamning to'rtdan biri) — ishchi kartani qo'lidagi chek bilan solishtiradi; qat'iy piksel ATAYLAB yo'q, aks holda uzun-ingichka detalda karta siqilganda chiziqlar u bilan kichraymasdi — ilgari chek va varaqda bor edi, kartada yo'q edi. Rangi KULRANG va ishlovdan OLDIN chiziladi: qora chiziq ko'k uzuq chiziqning bo'shliqlarini to'ldirib, pazni freza qilib ko'rsatardi (chekda aynan shu o'lchangan, docs/09). Yo'nalish CHEKDAN farq qilishi mumkin: chek uzun tomonni doim tik chizadi (`long_side`), karta esa detalni VARAQDAGI holatida (`rot`) — karta o'sha varaqdan ochilgani uchun.

**Nega bitta chek, ro'yxat emas.** `count>1` detalning nusxalari xaritada ALOHIDA kataklarda turadi, `mult>1` list esa render paytida alohida kartalarga yoyiladi (`CutmapView` → `sorted.slice(k, k+1)`) — ya'ni **har katak = bitta jismoniy detal = bitta chek**. Prodda o'lchangan (2026-08-28): katakdagi nusxa soni listning `mult` iga AYNAN teng, 2601 katakda istisno yo'q (2430×1, 169×2, 2×3). Shuning uchun ID mayda kaption emas, sarlavha ostidagi asosiy qiymat (chekdagi matn bilan solishtiriladi), bekor qilish esa siqilgan qatorda emas — to'liq kenglikda: ishchi 1-nusxa katagidan 2-nusxa chekini bekor qila olmaydi, chalkashish manbai yo'q. Render yo'li baribir `cheklar.map()` — kutilmagan ikkinchi chek yashirinib qolmaydi, tugma yonida `qr_text` bilan chiqadi.

- **Drill-down oqim (bitta sahifa, ikki holat):** `sheetIdx === null` bo'lsa jadval sahifasi — material tablari (bitta qator, `overflow-x-auto`, har tabda `bajarilgan/jami` list hisobi) + listlar gridi (`sm:grid-cols-3 lg:grid-cols-4`); har list kartochkasida №, `L×W` va `SheetSvg thumbnail` mini-xaritasi; hamma detali chiqarilgan list kartasi yashil tusda va mini-xaritada «list tugadi» belgisi turadi (pastdagi `SheetSvg` bandiga qara). `mult>1` naqshlar render paytida HAR JISMONIY LIST uchun alohida kartaga yoyiladi (№ `3c1` ko'rinishida) — ×mult badge yo'q. List bosilsa — to'liq maydonli xarita.
- **List egaligi (`postCode`):** giyotina kesimi listni chetdan chetgacha kesadi — bitta katakni chetlab o'tib bo'lmaydi, ya'ni list yo butunlay arraniki, yo butunlay roverniki (`sheet.rover`). ROVER postida faqat o'z listlari ko'rsatiladi (roversiz materiallar butunlay tushib qoladi); ARRA da rover listlari material ichida ham, material tablari orasida ham OXIRIGA suriladi va begona deb belgilanadi: material tabida `bajarilgan/jami` hisoblagich o'rniga "roverda", aralash materialda begona guruh ustida "Roverda kesiladi" ajratkichi (soni bilan), xarita ustida "Bu listni rover kesadi" satri; begona list kartasi to'lgan bo'lsa ham yashil bo'lmaydi. Xiralashtirish yoki yangi rang ataylab ishlatilmagan — 17" kioskda kontrast birinchi yo'qoladi va ekranda yashil/binafsha/ko'k allaqachon band, tartib va MATN ishlaydi. `admin` rejimida bu mantiq umuman ishlamaydi: texnolog fayl tartibini ko'radi, uning "o'z listi" degan tushunchasi yo'q.
- **Portal joylashuv:** `statsContainer` berilsa sarlavha `createPortal` bilan tashqariga chiqadi — terminalda ochiq list nomi (`№3 — 2750 × 1830 mm` + material) headerga, adminda (`routes/_layout/cutmap.$orderId.tsx`) breadcrumb dumi sahifaning bitta sarlavha qatoriga: `← Buyurtma` (route) `B-2026-066 › Kesish xaritalari`, list ochiq bo'lsa `B-2026-066 › Listlar › №3 — 2750 × 1830 mm · material` + o'ngda oldingi/keyingi list va «To'liq ko'rinish» (⤢) icon-tugmalari, undan keyin `PDF / Chop etish`. Zoom +/− webda yo'q — g'ildirak kursor nuqtasiga zoom qiladi, surish pan. `toolbarContainer` berilsa chap toolbar tugmalari terminalning umumiy chap ustuniga ko'chiriladi; portal berilmasa terminal rejimida toolbar `w-[68px]` ustunda qoladi, admin rejimida esa bu ustun umuman chizilmaydi.
- **Sarlavha qatori (`statsRow`):** ochiq list nomi va o'lchami (`№{disp} — L × W mm`) + material nomi. Reja ko'rsatkichlari (atxot `ko`, rez `dr`/`kr`, to'ldirish `fill`, arra `kerf`, tirim `trimL`/`trimW`) hech qayerda chizilmaydi va cutmap JSON'ga ham yozilmaydi (2026-09-03 qarori; `CutmapMaterial` = `name` + `sheets`); 2026-09-27 dan parser arra/tirimni (`swSawthick`, `cTrimL`/`cTrimW`) umuman o'qimaydi — `CutOperation.kerf/trim_l/trim_w` olib tashlandi, xarita data blob'dan chiziladi.
- **Chap toolbar** (`TBtn` tugmalari): Orqaga (xarita ochiq bo'lsa listlar jadvaliga, aks holda `onBack()`), Oldingi/Keyingi list, Katta/Kichik/To'liq (`ZoomIn`/`ZoomOut`/`Maximize2`; `SheetSvg` `registerZoom` bergan `zin/zout/reset`), Chop etish — belgilangan detalning navbatdagi CHIQARILMAGAN nusxasini GoDEX navbatiga yuboradi (dialogsiz); hammasi chiqarilgan bo'lsa yozilmaydi, "avval bekor qiling" xabari. **Detal va qoldiq ikki xil endpointga boradi** — tugma bitta, mutatsiya ikkita. Detal nusxasi: umumiy `usePrintLabel("cutmap")` / `useCancelLabel()` (`Terminal/usePrintLabel.ts` — `printInstanceLabel`/`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi; PrisadkaView ham shularni chaqiradi). Belgilangan katak QOLDIQ bo'lsa (`markedWaste`) tugma CutmapView ichidagi lokal `wastePrint` / `wasteCancel` `useMutation` larga tushadi — `TerminalService.printWasteItemLabel` / `cancelWasteItemLabel` (`path: { waste_id }`, id `waste_items` dan `atx` raqami orqali topiladi). Ro'yxatga olinmagan qoldiqda ("eski yuklama") va allaqachon chiqarilgan chekda tugma jimgina o'chmaydi — sababini toast bilan aytadi. Klient tekshiruvi eskirgan xaritada (ikki qurilmada ochiq yoki tugma ikki marta bosilgan) o'tib ketishi mumkin — server buni E012 bilan ushlaydi (bitta nusxa — bitta chek, detalda ham, qoldiqda ham); ulangan monobloki bor ish markazida boshqa brauzerdan bosilsa — E011. Ikkalasi ham `handleError` toasti (`Terminal/usePrintLabel.ts` ga qarang).
- **Chek chiqarilgan = kesildi:** `isCut(i)` (`@/lib/mes` dan import — SheetSvg ham shu predikatni ishlatadi) — ARRA skan BOR yoki `label_printed_at` bor; statlar, list kartalari va kataklar shu o'lchovda. Xato chek: katakni ikki marta bosish (<450 ms) yoki ~600 ms bosib turish `PartCard` ni ochadi, undagi «Chekni bekor qilish» esa tasdiq dialogini beradi ("Ha, bekor qilinsin" / "Yo'q") va oxirgi CHEK CHIQARILGAN nusxani bekor qiladi. `done` holati to'sib qo'yilmaydi: kesish postida chek chiqarish avto-skan ham yozadi, ya'ni `!done` sharti jestni butunlay o'lik qilardi. Bu jest faqat terminal rejimida — `onOpenPart={admin ? undefined : setSelected}`, adminda kartochka BIR MARTA bosishda ochiladi (`onSelect` ichida `if (admin) setSelected(part)`); bekor qilish tugmasi ikkalasida ham kartochka ICHIDA, ya'ni jest buzg'unchi amalni o'zi bajarmaydi. Hamma detali chiqarilgan list kartasi yashil tusda (`border-green-500/60 bg-green-50 text-green-700`) — va 2026-09-21 dan mini-xaritaning o'zida ham «list tugadi» belgisi chiqadi.
- **Tanlash semantikasi:** xaritada detal bosilsa `markedCell` moviy bo'lib qoladi (kartochka yopilgandan keyin ham) — terminalda tap faqat belgilaydi, chop etish chap toolbardan; `admin` bo'lsa qo'shimcha ravishda `PartCard` dialogi ochiladi.
- `instancesByCell` — `useMemo` bilan `pattern_no:cell_index` kalitli Map; `sheetDone(s)` list to'liq kesilganini (har bir waste bo'lmagan katakning barcha instansiyalari `done`) hisoblaydi.
- `printAllMaps` — barcha xaritalarni chop etish: `renderToStaticMarkup(<SheetSvg .../>)` bilan yangi oynaga yoziladi, har list o'z A4 landscape sahifasida (`@page size: A4 landscape`), "Material | №N — L × W mm" sarlavhasi bilan (listlar jismoniy nusxalarga yoyilgani uchun `× k list` yo'q); sahifadagi "PDF / Chop etish" tugmasiga `registerPrint` prop orqali ulanadi. `escapeHtml` bilan nom/raqam ekranlanadi. Brauzer popup'ni bloklab `window.open` `null` qaytarsa toast bilan sabab aytiladi.
- Xarita mavjud bo'lmasa (`data.model` yo'q — fayl GibLabda optimizatsiya qilinmagan, TEMPLATE) tushuntirish matni + "Orqaga" tugmasi.
- **Eksporti bitta:** `CutmapView`. `TBtn` va `PartCard` alohida fayllarga ajratilgan (pastda) — CutmapView ularni import qiladi.

### `frontend/src/components/Terminal/Serial.tsx`

**Maqsadi:** nusxa ID'ini (chekdagi satr bilan aynan bir xil) ko'rsatish — buyurtma prefiksi (`B-2026-047_`) **xira**, farqlovchi qism (`301401_01_001_1`) **qalin**, `whitespace-nowrap`, `title` da to'liq matn. ID `qr-serialization` bilan 32 belgigacha cho'zildi: prefiks har qatorda takrorlanadi va sarlavhada allaqachon turadi, ko'z farqlovchi qismga tushishi kerak. Prefikssiz eski ID regex'ga tushmaydi va o'zgarishsiz chiqadi. Ishlatiladi: `ScanStrip` (muvaffaqiyat kodi), `PrisadkaView` (ROVER nusxa qatori va SCX chiplari), `UpakovkaView` (ochiq qadoq jadvali va yakunlangan qadoq tarkibi), `PartCard` (chek ID qatori va bekor qilish tugmasi), `DefectDialog` (skan kodi). `KromkaView`, `PostQueueView` va `TmoView` uni ishlatmaydi (post navbati nusxani `InstanceChip` bilan chizadi). 2026-09-03 terminal auditida qo'shildi; o'sha auditda: detal KOD kataklari `whitespace-nowrap` (nostandart `…_016-2` ikki qatorga sinardi), KROMKA «N tomon» katagi nowrap, TMO tab'lari `h-12`, UPAKOVKA chiqarish/qayta ochish tugmalari `h-11`, PRISADKA xarita ikonkasi `size-10`, brigada chiplari va «+ Qo'shish» `h-10` (qo'lqop uchun ≥40px).

### `frontend/src/components/Terminal/TBtn.tsx`

Chap toolbar tugmasi: ikonka + `text-2xs` yozuv (`index.css` da 0.6875rem), `h-16 w-full`, `TBTN_TONES` rang kodlari — default (oq fon, primary matn) / primary (asosiy nav) / success (chop etishga tayyor); `warn` (qulf) va `danger` (chiqish) tonlari 2026-09-27 da olib tashlandi — Qulflash/Chiqish headerga ko'chgach chaqiruvchisi qolmagan edi. Uchta chaqiruvchi: `CutmapView` (butun chap toolbar), `PrisadkaView` (ROVER "Chop etish", portal orqali) va `routes/terminal.tsx` (bitta tugma: "Xarita" — ROVER kesish xaritasi; "Qulflash" va "Chiqish"/"Smenani yakunlash" headerdagi `ui/button` ikonka tugmalari). Skan tugmasi YO'Q — skan avto-fokusli inputdan keladi (`useScanFocus`/`useTerminalScan`).

### `frontend/src/components/Terminal/PartCard.tsx` (~500 qator)

**Maqsadi:** kesish xaritasidagi detal/qoldiq kartochkasi. `CutmapView` dan ajratilgan — `PartCard` ning yagona chaqiruvchisi o'sha.

- `PartPreview` (eksport — `KromkaView` luppasi ham ishlatadi) — tanlangan detal mini-chizmasi (276×190 viewBox): o'lcham strelkalari, `holes` dan yuza (`bores`) va qirra (`edge`) teshiklari masshtablangan holda, aylantirilgan detalda ⟳.
- `PartCard` dialogi: sarlavha (`№` + nom) va ostida chek ID si + holati, `PartPreview`, katta QR (`qrcode.react` `QRCodeSVG` — kaptionsiz, ID yuqorida turibdi), o'lcham/kromka, so'ng `h-14 w-full` qizil "Chekni bekor qilish" (`LoadingButton variant="destructive"`) va `h-12` "Yopish". Bekor qilish sharti `c.printed && c.cancel` — kesish postida chek skan ham yozgani uchun `done` holati to'sib qo'yilmaydi; proyekt ARRA ro'yxatidan tushib bo'lgach texnolog xato chekni shu yerdan tuzatadi. Kartochka adminda bir marta bosishda, terminalda ikki marta bosish yoki uzoq bosishda ochiladi; unda chop etish tugmasi YO'Q — terminalda chop etish yo'li chap toolbardagi "Chop etish". Mutatsiya SHOXGA qarab: detal nusxasida `usePrintLabel.ts` dagi `useCancelLabel()` (`cancelInstanceLabel`), qoldiqda esa `cancel: () => onCancelWaste(wasteItem.id)` — ya'ni CutmapView dagi `wasteCancel` (`TerminalService.cancelWasteItemLabel`); `wasteCancelling` propi yuklanish holatini beradi.
- `onCancelRequest?` propi bekor qilish yo'lini belgilaydi: berilmasa (admin) bekor qilish DARHOL bajariladi, berilsa (terminal) chaqiruvchiga uzatiladi va tasdiq oynasi ochiladi — tsexda qo'lqopdagi barmoq bilan xato bosish adminning stoliga qaraganda ancha ehtimolli. Ro'yxatga olinmagan atxot (`part.waste && !part.atx`) kartochka umuman ochmaydi.

### `frontend/src/components/Terminal/SheetSvg.tsx` (~1110 qator)

**Maqsadi:** bitta listning to'liq SVG renderi — GibLabViewer'dan portlangan render qoidalari. `CutmapView` (interaktiv, thumbnail va print oqimi) ishlatadi.

**Props:** `sheet`, `holes`, `instancesByCell`, `onSelect(part)`, `onOpenPart?(part)` (detal kartochkasini ochadi — berilmasa jest umuman ulanmaydi, ya'ni admin rejimida o'chiq), `wastePrinted?: Set<number>` (cheki chiqarilgan qoldiqlarning `atx` raqamlari), `selectedCell`, `thumbnail?`, `registerZoom?({zin,zout,reset})`, `onSwipe?("next"|"prev")`.

- **«LIST TUGADI» BELGISI — detalga emas, LISTGA** (2026-09-21). Belgi listning
  chap-yuqori burchagida bitta katta yashil doira + oq galochka; `listTugadi`
  rosti bo'lganda chiqadi, ya'ni listdagi BARCHA ishchi katak (`!p.waste`)
  to'liq kesilganda. «Kesildi» ta'rifi bitta joyda — modul darajasidagi
  `kesildi(insts, waste)` yordamchisi, katakning `allDone` rangi ham shuni
  chaqiradi.

  Nega detalga emas: o'lchandi — haqiqiy buyurtmada (`B-2026-001`, 5 material,
  148 katak) kataklarning **26% ining** qisqa tomoni 150 mm dan kichik, eng
  ingichkasi 70 mm (17″ monoblokda ~30 px). Har katakka belgi qo'yish
  chegara talab qilardi va chegara har to'rtinchi katakni belgisiz qoldirardi.

  Mantiq GibSaw'dan olingan (`GibSaw.exe` ichidagi jar o'qildi): u ham
  `l[listIndeksi] = (kesilgan soni == jami)` bayrog'ini yuritadi (`o.q()`) va
  uni `setTransform` → `scale(4,4)` → `drawImage(ok48, 8, 8)` bilan panelning
  (32,32) nuqtasida 192×192 px qilib chizadi — katak o'lchamiga bog'liqsiz.
  Bizda SVG bo'lgani uchun ekvivalenti: o'lcham va chet `base.w` ulushi
  sifatida olinib `zoom` ga bo'linadi (`OK_ULUSH = 0.14`, `OK_CHET = 0.022`),
  joyi esa ko'rinib turgan `viewBox` burchagi — natijada yaqinlashtirilganda
  ham, pan qilinganda ham ekranda bir xil kattalikda va o'z joyida qoladi.
  ~1100 px enidagi xaritada ≈154 px (o'lchandi).

  **Farq:** GibSaw ikki toifani qo'shib hisoblaydi va atxotni ham «kesildi»
  deb belgilash mumkin; bizda qoldiq kesilmaydi, uning CHEKI chiqariladi —
  boshqa amal, shuning uchun `listTugadi` ga KIRMAYDI. Ya'ni list arrachining
  ishi tugaganda tugagan deb belgilanadi, qoldiq cheki chiqarilmagan bo'lsa ham.

  Ranglar XOM hex'da (`#22c55e`, `#0a4d26`, `#ffffff`) — xarita
  `renderToStaticMarkup` orqali Tailwind'siz oynaga chop etiladi, `className`
  u yerga yetib bormaydi. Oq galochka + to'q halqa: qora-oq printerda ham,
  rang ko'rmaslikda ham belgi rangdan emas, SHAKLDAN o'qiladi. `thumbnail`
  rejimida ham chiziladi — GibSaw listlar ro'yxatida ham shu bayroqni
  ko'rsatadi (`R.getListCellRendererComponent`).

- **Eksport qilingan geometriya yordamchilari** (`PartCard.tsx` dagi `PartPreview` ham ishlatadi): `holeXY(part, H, bx, by)` — teshik lokal koordinatasini katakka o'giradi (`p.rot` da o'q almashinuvi, oynasiz), `edgeLocalXY(H, side, pos)` — qirra teshigining lokal nuqtasi (t/b/l/r), `edgeBoreRect(part, cx, cy, d, dp)` — eng yaqin chetdan ichkariga to'rtburchak (uzunligi = burg'u chuqurligi).
- **Ranglar/qoidalar:** barcha detallar `#e88b00` (to'q apelsin), TANLANGANI qalin ko'k KONTUR bilan belgilanadi (`#2596be`, 14px) — fon almashtirilmaydi: ilgari tanlov fonni butunlay bosib, katakning HOLATINI yopardi va chek chiqarilgach katak tanlangan holda qolgani uchun yashil rang faqat boshqa katak tanlanganda ko'rinardi ("chek chiqdi, hech narsa o'zgarmadi" shikoyati shundan). Qoldiq katagida tanlov ilgari umuman ko'rinmasdi — endi u ham shu konturni oladi, nostandart detal (`Part.is_custom` → barcha nusxalarida `custom` bayrog'i) kesilmagan holatda binafsha (`PART_CUSTOM = "#a78bfa"`), chek chiqarilgach odatdagidek yashil (`allDone` fondan ustun), bekor qilinsa yana binafsha; chegara barcha detallarda bir xil; atxot va list foni `zebra` pattern (`patternTransform rotate(45)`); **QOLDIQ (`business`, `atx` raqamli) katagi zebra SAQLANADI, rang holatni aytadi**: chek chiqarilmagan — apelsin-oq zebra (`zebraQoldiq`, detal apelsini tilida «chek chiqarish mumkin»), chek chiqarilgach — yashil-oq zebra (`zebraDone`), bekor qilinsa yana apelsin-oq; qaysi qoldiq chiqarilganini `wastePrinted: Set<number>` propi aytadi — CutmapView uni `waste_items` dagi `label_printed_at` bor yozuvlarning `atx` raqamlaridan yig'adi. Prop ochiq listga ham, ro'yxatdagi `thumbnail` mini-xaritaga ham, `printAllMaps` PDF'iga ham beriladi — uchalasida qoldiq holati bir xil (ilgari faqat ochiq list olardi: ro'yxatda chiqarilgan qoldiq apelsin zebra bo'lib qolardi). **QOLDIQ DETAL BILAN BIR XIL OQIMDA**: bir marta bosish belgilaydi va chap qatordagi «Chop etish» ishlaydi (qoldiqda u `printWasteItemLabel` ga boradi), ikki marta bosish/uzoq bosish `PartCard` ni ochadi — bekor qilish o'sha yerda. Alohida `onOpenWaste` propi va alohida dialog OLIB TASHLANDI: bitta xaritada ikki xil jest qoidasi operator uchun ortiqcha yuk edi. Ro'yxatga olinmagan atxot (atx yo'q) avvalgidek inert. Ilgari qoldiq shoxidan yuqorida turgan `if (p.waste) return` uni umuman o'lik kodga aylantirgan edi. Yo'l-yo'l naqsh «bu atxot» identligini saqlaydi. Oddiy (ro'yxatga olinmagan) atxot kulrang zebra bo'lib qoladi; qoldiq katagidagi O'LCHAM YOZUVI detalning "tight" rejimi bilan AYNAN bir xil qoidada hisoblanadi (`DIM_FS` gacha, faqat sig'masa kichrayadi, `DIM_MIN`/zoom chegarasi ham o'sha) — ilgari unda alohida formula turib, shrift 34 ga QOTIRILGAN edi va bir xil o'lchamli detal 48 olib, qoldiq 34 da qolardi; kesim chiziqlari (`sheet.cuts`) qora `#242424`; yozuvlar halo'siz (to'q apelsin fonda kerak emas).
- **Zoom/pan/swipe (Pointer Events):** g'ildirak zoom kursor nuqtasiga (native `wheel` listener, `passive: false`), bir barmoq pan (zoomda) yoki gorizontal swipe → `onSwipe` bilan list almashtirish (>80px, <600ms), ikki barmoqli pinch. `setPointerCapture` **ataylab ishlatilmaydi** — u keyingi `click`ni SVG'ga retarget qilib detal tanlashni o'ldiradi. G'ildirak, pinch va toolbar tugmalari bitta `zoomAt(f, ax, ay)` yordamchisiga tushadi (tugmalar markaz atrofida 1.5x, `zoomBy`), zoom chegarasi ham shu yerda — `base.w/14`; `viewBox` `base` dan kichik bo'lsagina `vb` state saqlanadi, list almashsa (`sheet.no`) tiklanadi.
- **Yozuv joylashtirish (GibSaw pariteti, `GibSaw.exe` dekompilyatsiyasidan portlangan):** shrift QATTIQ — `DIM_FS = 48` mm, tsexdagi GibSaw.ini `pattrenPartDim=48` bilan bir xil; glyph geometriyasi TAXMIN EMAS, jonli brauzerda `getBBox` bilan O'LCHANGAN konstantalar: Archivo 700 ascent 0.884em → `ASC = 0.9`, descent 0.201em → `DESC = 0.22`, raqam eni 0.596em → `CH = 0.6` (taxminiy 0.75em bilan mm darajasidagi chiqib ketishlar qolayotgan edi). Vertikal (rotate(90)) matnda glyph bazachiziqdan +x (o'ngga) tomon chiqadi — bazachiziq shunga mos qirradan `ASC` masofada qo'yiladi; ilgari bo'sh tomon hisoblanib, 13/72 yorliq qo'shni katakka kirib ketgani jonli o'lchovda aniqlangan; detalga qarab KICHRAYMAYDI (ilgari `min(kondalang*0.28, boylab/len)` bilan 6-8 mm gacha tushib o'qib bo'lmasdi). Sig'masa o'lcham emas, YO'NALISH almashadi (`dimFit`: 'h' → 'v' → chizilmaydi). Sig'ish sharti: matn uzunligi o'z o'qiga, glyph qalinligi (`(ASC+DESC)·fs + 4`) ko'ndalangiga — +4 aynan yozuvning qirradan ichkarilik masofasi, ya'ni joylashuv geometriyasining o'zi; ilgari +8 zaxira 60 mm li strip (60×1490, odatiy) da ikkala o'lchamni ham yo'qotib, uni markazdagi birlashgan `W×H` ga tushirar va qo'shni 100 mm li kataklardan farqli ko'rsatardi — endi 58 mm dan keng strip standart shaklda (eni pastki-chapda burab, bo'yi o'ng qirrada, nom markazda). Joylashuv: ENI pastki-chap burchakda gorizontal, BO'YI o'ng qirrada vertikal (yuqoridan pastga) — diagonal qarama-qarshi burchaklar, ikki o'lcham strukturaviy to'qnashmaydi. MITTI detalda (burchak box'lari baribir kesishadigan yoki o'lcham umuman sig'maydigan) markazda bitta birlashgan `W×H` — atxot yozuvi bilan bir xil shakl; GibSaw bu holatda ustma-ust chizadi yoki tashlab yuboradi, bizniki yaxshiroq. Nom (`№num nom`) markazda, shrift qoidasi pastda; mitti rejimda yoki katak 16×8 dan kichik bo'lsa nom chizilmaydi (ilgari `availW/availH` — o'lcham bandi butun en bo'ylab ayirilgan qiymat — tekshirilib, 60×1490 stripda nom sababsiz o'chirilardi; haqiqiy teginishni kesishish himoyasi ushlaydi). Teshiklar yozuvga TO'SIQ EMAS — o'lcham ham, nom ham teshik ustiga bemalol tushadi (tsex talabi; GibSaw ham tekshirmaydi). Ilgari teshik-chetlab o'tish yozuvni muqobil nomzodga sakratardi va bir xil detal turli listlarda TURLI joyda yozuv olib, "o'lcham siljigan" bo'lib ko'rinardi — endi har yozuv o'rni DETERMINISTIK. Nom O'LCHAM FONTIGACHA chiziladi (`DIM_FS` = 48) — alohida kichik cap YO'Q, `nomMax` olib tashlangan; ko'ndalang cap KATAKNING qisqa tomoniga glyph bbox sig'ishi (`(shortC-10)/(ASC+DESC)`), `shortA*0.55` EMAS — eski cap botB/rightB zaxirasini butun en bo'ylab ayirib, cho'zinchoq detalda (2390×100 o'lchandi: 22.7 mm) nomni sababsiz kichraytirardi, o'lcham esa faqat burchakda turadi — GibSaw'da nom ham `pattrenPartDim` fonti bilan chiziladi, alohida kichik font yo'q; ilgari `nomMax` cap katta katakda nomni sababsiz kichraytirardi. O'lchamga tegsa avval 0.72 pog'ona kichrayadi, baribir tegsa NOM chizilmaydi: kichik detalda katta o'lcham ostida ko'rinmay qolgandan ko'ra yo'q bo'lgani yaxshi (1192 Anvar N11/N15/N16 350×97-90 da aynan shu holat). Birlashgan `W×H` yozuvi yo'nalishi katak shakliga qarab tanlanadi (`fitAlong` — qaysi o'qda shrift kattaroq chiqsa): ingichka-uzun detal (60×1490) da vertikal, ~43 mm; ilgari doim gorizontal bo'lib 13 mm ga tushardi.
- **Tekstura yo'nalishi:** `p.txt` bo'lsa (va detal >60×40) matn ortida 3 chiziq — detalning `l` o'qi bo'ylab (`p.rot` bo'lsa vertikal, aks holda gorizontal). GibSaw xaritada teksturani UMUMAN chizmaydi (dekompilyatsiya: part-draw'da faqat XNC, kromka punktiri, o'lchamlar, nom) — bu belgi bizning qo'shimcha, chek eskizi bilan bitta qoidada.
- **Burilgan detal (rot) — HAQIQIY 90°, transpose emas:** `holeXY` lokal `(x,y)` ni katakka `(y, h−x)` bilan o'tkazadi — GibSaw.exe dekompilyatsiyasi bilan tasdiqlangan (`translate(0,h); rotate(-90)`). Ilgari `(y,x)` transpose edi — bu OYNA (transpose = burilish + aks, fizikada detal ag'darilmaydi): 1803 mm detalda teshik ~1 metr noto'g'ri joyda chiqardi. Prodda burilgan+teshikli katak 493 ta edi. Kromka belgilari (`cutmap._edge_markers`) va chek eskizi (`labels.py`) ham shu konvensiyada.
- **Teshiklar haqiqiy masshtabda:** `H.bores` — radiusi `d/2` doiralar, `H.edge` — `edgeBoreRect` to'rtburchaklari; hammasi `#fafafa` to'ldirish, `#202020` kontur.
- **O'lcham zanjirlari** (`sheet.dims`, `ax: "X"|"Y"`): chetda strelka, ichki chegarada kesim davomi + ✕ belgisi; qiymat 48px va GibSaw kabi zanjir chizig'i ICHIDA (oq halo chiziqni matn joyida uzadi — dekompilyatsiyada chiziq matn uchun ikki segmentga bo'linadi). `PAD = 68` — GibSaw zanjir chuqurligi band-font balandligiga teng (~55 mm); ilgari 110 edi va list shuncha kichik render bo'lardi. Zanjir faqat ROOT kesim tomonida (tepa yoki chap) — GibSaw ham faqat birinchi darajali striplarni chizadi. Fontlar GibSaw.ini bilan paritet: `pattrenPartDim=48`, `pattrenBandDim=48`.
- Barcha nusxalari "kesilgan" (skan yoki chek chiqarilgan — `isCut`, `@/lib/mes`) katak YASHIL (`PART_DONE = "#22c55e"`, Tailwind green-500 — tizimdagi boshqa "bajarildi" belgilari bilan bir ton) to'ldiriladi — belgisiz; `onOpenPart` prop berilsa IKKI jest ham uni chaqiradi va DETAL KARTOCHKASINI ochadi: katakni ikki marta bosish (<450 ms — Windows ning 500 ms oynasidan bir oz tor, qo'lqopdagi barmoq sekinroq) yoki ~600 ms bosib turish (`LP_SLOP = 30` px siljish yoki pinch uzoq bosishni bekor qiladi, keyingi click yutiladi; bosish davomida katak `animate-hold` bilan asta bo'yaladi — jest qabul qilinganini ko'rsatadi). Ikki marta bosish GibSaw'dagi eski odat, uzoq bosish esa sensor DRAYVERIGA bog'liq bo'lib chiqdi (bir panelda ishlaydi, boshqasida yo'q) — shuning uchun ikkalasi ham qoldirilgan. Chekni bekor qilish tugmasi kartochka ichida: jest buzg'unchi amalni o'zi bajarmaydi. `thumbnail` rejimda `pointer-events-none`.

### `frontend/src/components/Terminal/DefectDialog.tsx`

**Maqsadi:** BRAK — skanerlangan nusxani yaroqsiz deb belgilash (OEE Quality, docs/12 §4.7).
Ikki eksport: `useDefectReasons()` (sabablar ro'yxati, `["terminal","defect-reasons"]`, 5 daqiqa
`staleTime`) va `DefectDialog`. Tugma `ScanStrip` da — faqat OXIRGI MUVAFFAQIYATLI skanda va faqat
sabablar ro'yxati bo'sh bo'lmaganda (`onDefect` berilmasa umuman chizilmaydi). Dialog sababni
tugmalar to'ridan oladi (klaviatura yo'q), izoh IXTIYORIY — majburiy qilinsa operator eng oson
sababni bosib ketardi. Belgilanayotgan skan dialog OCHILGANDA suratga olinadi (`undoFor` bilan bir
naqsh): keyingi skan tasmani almashtirsa ham oyna boshqa detalga o'tmaydi. `routes/terminal.tsx`
uni `dialogOpen` ga qo'shadi — dialog ochiqda skan fokusi o'chadi. Oyna FAQAT `ScanStrip` dagi BRAK
tugmasidan ochiladi. 2026-09-20 da qisqa vaqt KROMKA'da WS `kromka.measure` hodisasi
`verdict === "nomos"` bo'lganda o'zi ochilardi — datchik uzunlikka qarab xato o'lchagani
aniqlangach olib tashlandi (docs/12 §4.10); o'lchov endi faqat tasmada ko'rinadi.

### `frontend/src/components/Terminal/KromkaView.tsx`

**Maqsadi:** KROMKA/OVAL post sahifasi. (2026-09-03 dan BITTA to'liq kenglikdagi jadval — «Ikki panel» tavsifi eskirgan, pastdagi 2026-09-03 bandiga qarang.) Jadvalda buyurtmaning SHU postdagi hamma detali — hali yetib kelmaganlari ham (2026-09-21 gacha ular `arra_passed` bo'yicha FILTRLANIB, butunlay yo'qolardi: kromkachi sarlavhada 71/72 ni ko'rib, yetishmayotgani qaysi detal ekanini bilolmasdi; bundan yomoni, `finished` o'sha filtrlangan ro'yxat ustida hisoblanib, bir nusxasi arrada turgan detal qatori yashil «✓ Bajarildi» bo'lib chiqardi). Kelmagan nusxa UZUQ konturli chipda va ichida raqam emas, detal QAYERDALIGI turadi (`at` — `ARRA`, `PRISADKA`, `STOLYARKA`), o'sha postning rangida (`POST_COLORS`); ochiq braki bo'lsa qizil «brak». Shakl rangdan oldin aytadi: uzuq kontur = skanlab bo'lmaydi. `finished` va `tier` endi HAMMA nusxa ustida hisoblanadi (tugaganlari yashil bo'lib pastga tushadi), sarlavhada «Jarayonda N» — 2+ tomonli, boshlangan-u tugamagan nusxalar soni (ular jadval tepasida sariq; OVAL da yo'q). Detal nomi ostida `Common/OperationChips` — noodatiy marshrutli detalda shu postga tegishli amal nomi chiplari (postCode: `oval ? "OVAL" : "KROMKA"`). Har skan darhol yoziladi (tomon = skan); `registerScan` prop orqali terminalga lokal tekshiruv beradi (`null` = yozish mumkin, `"NOTFOUND"` = bu proyektda yo'q, boshqa string = xato matni: arradan chiqmagan / allaqachon tugagan). Tekshiruv QR ga mos KELGAN HAMMA qatorni yig'adi, birinchisida to'xtamaydi: nostandart marshrutda (`[3, 6, 3]`) bitta detal KROMKA'ni ikki marta oladi va backend har qadamga alohida qator qaytaradi — birinchi qatorga qarab javob berilsa, birinchi o'tish tugagach ikkinchi o'tishning skani "allaqachon tugagan" deb LOKAL bloklanardi (server esa `scanning.py` da seq bo'yicha birinchi ochiq qadamni olib qabul qilardi). Endi qadamlardan bittasi ochiq bo'lsa skan o'tadi; yakuniy hakam baribir backend (E00x). `oval` prop: bir panel, tomonlar ustuni yo'q va `done/sides` o'rniga `–` chiziladi — OVAL marshrut qadamida `per_instance` doim 1, ya'ni bir detal bir skanda tugaydi (`c3d97a1e5b02` gacha kod xato ravishda qirralar sonini berardi). Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + markazga avto-scroll (`useScanFlash` hooki — xuddi shu mexanizm `PrisadkaView` da ham). «Kromka» ustuni (OVAL da «Qirralar», 2026-09-12 dan u yerda ham ko'rinadi) — `{sides} tomon` va har lenta `A — 1-19 kashmir` ko'rinishida (`edges[side].symbol` + `.mat`, takrorlanmaydi, belgisiz qirra `•`). Ilgari faqat YALANG'OCH HARF chiqardi va tsexda uni tomonlar TARTIBI deb o'qishdi — sarlavhadagi izoh endi ochiq aytadi: «qalin = lenta · uzuq = paz · tutash = freza · harf = lenta turi (tartib emas)». Ishlangan qirra eskizda kontur ICHIDA ko'k chiziq bilan — paz UZUQ (`paz_sides`), freza TUTASH (`frez_sides`), chekdagi bilan bir xil manba va bir xil belgi; stanok buyrug'i ham har xil (groove / mill). Eskiz `size-16` (64 px = 17" monoblokda 16.8 mm) va yonidagi «N tomon» `text-xl` (20 px = 5.2 mm) — 2026-09-21 da kattalashtirildi, tsexda eski o'lcham kichik deb topilgan. Ilgari `size-12` (12.6 mm) edi; `size-8` (8.4 mm) da uzuq/tutash farqi umuman bilinmasdi. NARXI o'lchangan (1366 px, haqiqiy qurilgan CSS): paz qatori bor qator 82 → 94 px, ya'ni ekranga 7 o'rniga 6 qator sig'adi. `size-12` da qator balandligini eskiz EMAS, yonidagi matn ustuni (56 px) belgilardi — shuning uchun `size-14` gacha o'sish deyarli tekin edi (+4 px), `size-16` esa +12 px. «N tomon» ni 16 → 20 px qilish shu nuqtada BUTUNLAY tekin: eskiz 64 px bo'lgach qator balandligini o'sha belgilaydi va matn ustuni 64 px gacha bemalol o'sadi (o'lchangan — qator 94 px da qoladi). BIR MARTA BOSILGANDA luppa ochiladi, qayta bosilganda yopiladi — `EdgeZoom`, `fixed z-50` qatlam: eskiz **352 px (92 mm)**, yonida detal nomi, o'lchami, «N tomon» va lenta ro'yxati. Kromka chizig'i `band` propi bilan beriladi (viewBox birligida): jadvalda **3**, luppada **1**. Sabab — `strokeWidth` viewBox birligida, ya'ni eskiz bilan BIRGA kattalashadi: jadvaldagi 3 birlik (6.4 px = 1.7 mm) luppada 35 px = **9.2 mm plita** bo'lib panelni bosib ketardi (o'lchangan); 1 birlik esa 11.7 px = 3.1 mm. Chiziq qirraning ICHIGA suriladi (`band / 2`): markazda tursa yarmi tashqarida qolib, tor detalni ko'zga kengroq ko'rsatardi — sokl (100×1775) da chiziq panel enining 38% i edi, endi 13%. Ilgari `active:scale-[2.2]` (141 px) edi va u ikki sababdan yaramasdi: (1) `thead` `sticky z-10`, eskiz esa oddiy oqimda `z-index:auto` — tepadagi qatorda kattalashgan eskizning **71 px i sarlavha ORQASIDA** qolardi (haqiqiy ilovada o'lchangan), scroller ham kesardi; (2) 37 mm da qaysi tomon ishlanishi baribir aniq emasdi. Luppa Dialog EMAS va `dialogOpen` ni qo'zg'atmaydi — aks holda `useScanFocus` o'chib, luppani ochib qo'ygan kromkachining skani yo'qolardi; `pointer-events-none` bilan hech qanday hodisani ham yutmaydi. Boshqaruv BITTA hujjat-darajasidagi tap'da: `pointerdown` da nuqta va nishon eslab qolinadi, `pointerup` da 8 px dan kam surilgan bo'lsa BOSISH hisoblanadi — surilgan bo'lsa bu ro'yxatni aylantirish (`useDragScroll`) va luppaga tegilmaydi. Qoida: o'sha eskiz → yopiladi, boshqasi → almashadi, tashqarisi → yopiladi; alohida «X» tugmasi kerak emas. Bosib TURISH ataylab olib tashlandi — qo'lqopda uzluksiz tegib turish ishonchsiz va qo'lni band qiladi. Beshala xulq haqiqiy ilovada o'lchangan.

**LENTALAR SARLAVHA QATORIDA** (2026-09-21) — `PostHeader` ichida, loyiha nomidan
keyin: qaysi lentadan necha metr (`KromkaOrderState.bands`, ko'pdan ozga). Kromkachi
ishni boshlashdan oldin skladdan aynan shu rulonlarni olib keladi, ya'ni bu ma'lumot
ish BOSHIDA kerak; doim ochiq — tsex ekranida bosilmagan narsa ko'rilmaydi.
Son GibLab'ning o'z hisobi (docs/03), ya'ni texnolog ko'radigan raqam bilan bir xil.
Avval ALOHIDA qator edi — sarlavha qatoriga ko'chirildi, chunki tsex paneli
**1366×768** va BALANDLIK tanqis resurs: 40 px lik qator jadvalning yana bir
qatoriga teng. Eni yetarli, jonli ilovada o'lchandi: lentalar sarlavha chapidan
**643 px** da tugaydi, progress 197 px, ya'ni 1366 da 872 px kerak — 494 px zaxira.
`flex-wrap` qoldirilgan: juda ko'p lentali buyurtmada ikkinchi qatorga tushadi,
ya'ni eng yomon holat avvalgi ko'rinish. Lentalar BITTA to'ldirilgan blokda (`rounded-lg bg-muted`), sarlavhaning alohida bolalari emas: sarlavhada hamma oraliq bir xil (`gap-3` = 12 px) bo'lgani uchun ular sarlavha blokining davomi bo'lib o'qilardi va — qatorning vertikal markazida turgani uchun — loyiha nomi bilan buyurtma raqami ORASIGA kirib qolgandek ko'rinardi (o'lchandi: sarlavha bloki y 88..132, lentalar markazi y≈110, ya'ni aynan chegara). Ingichka ajratuvchi chiziq buni yengmaydi — u oraliqqa va vertikal joylashuvga bog'liq; fon esa alohida OBYEKT bo'lib o'qiladi va «Jarayonda N» belgisi bilan bir tilda. O'rash `flex-wrap` uchun ham to'g'ri: lentalar bir-biridan uzilib qolmaydi.

Kromka chizig'i **to'q** — ammo ikki joyda ikki xil manbadan, ataylab: jadval eskizi `stroke-foreground` (`--foreground: #1c2b42`, ya'ni loyihaning siyoh rangi, chunki eskiz UI elementi va qolgan jadval matni bilan bir xil token'da bo'lishi kerak), luppadagi `PartPreview` esa xom `#111` (u UI emas — termal chekning nusxasi, butunlay bosma ranglarda: `#d2d2d2`, `#242424`, `#fafafa`). Ikkalasining kontrast farqi **1.33×** — 2px chiziqda ko'zga bilinmaydi, ya'ni kromkachi uchun jadval ham, luppa ham, chek ham bir xil qora. Paz/freza ikkala joyda ham `sky-700` (`#0369a1`). Ilgari jadvalda amber edi (2026-09-03 yozuviga qarang) va uch sababdan almashtirildi: (1) kontrast chegarada — `amber-600` oq qatorda **3.19×**, `bg-amber-50/70` (jarayonda) da **3.10×**, `bg-green-50` (bajarildi) da **3.04×**; WCAG SC 1.4.11 minimumi 3.0×, `foreground` esa **13.6–14.3×** — 17" monoblokda kontrast birinchi yo'qoladi; (2) bu jadvalda amber HOLAT rangi (qator foni, «Jarayonda N», chek chiqarilgan nusxa chipi) — bitta rang ikki ma'noda edi; (3) eskizning butun maqsadi kromkachi qo'lidagi TERMAL CHEK bilan solishtirish, chek esa qora-oq. Sof qora (`#000`) esa YO'Q — zamonaviy UI'da sof qora sirt rangidan uzilib «teshik» bo'lib ko'rinadi, shuning uchun loyiha siyohi ham zangori tusli.

Teshigi bor detalda luppa sodda eskizni EMAS, **chekdagi chizmaning o'zini** ko'rsatadi — `PartCard.tsx` dagi `PartPreview` (kesish xaritasidagi detal kartochkasi bilan BITTA komponent): o'lcham strelkalari, konturdan tashqaridagi kromka chiziqlari, tekstura, teshiklar va qirra teshiklari. Sabab o'lchangan: prod ma'lumotida kromkali detallarning **67% ida** bir juft bir xil qirradan faqat bittasi lentalanadi — detal teskari ushlansa eskiz ham teskari bo'ladi va xato ko'rinmaydi; ularning **89% ida teshik bor**, ya'ni teshik o'rni yo'nalishni bir ma'noli qiladi (qolgan 8 tasida hech qanday nosimmetrik belgi yo'q — ularda sodda eskiz qoladi va yechim jarayon darajasida: ikkala qirraga kromka yoki arrada belgi). Teshik o'rinlari backenddan `KromkaPartRow.holes` bilan keladi va chek bilan BITTA manbadan — `services/giblab/cutmap.py: holes_by_label_num()`, uni `labels.py` ham chaqiradi (ilgari bu qidiruv faqat chek ichida edi). `zoomCell()` qatorni sintetik `CutmapCell` ga o'giradi; `eW`/`eH` xaritasi `labels.py` `burilgan` qoidasining AYNAN o'zi — haqiqiy ilovada tekshirilgan (burilgan detal, qirralari `r`+`t` → chizmada CHAP va TEPA).

Eskiz nisbati: `minW` propi eskiz enining pastki chegarasi (jadvalda **8**, luppada **4**). Klamp kerak, chunki sokl (100×1775) haqiqiy nisbatda 1.46 birlik = 64 px eskizda 3 px bo'lib ko'rinmasdi. Lekin luppada haqiqiy nisbat ham yaramaydi: 1.5 birlikda panel 17.6 px, kromka belgisi 11.7 px — belgi panelni to'ldirib, QAYSI qirra ishlanishi ko'rinmay qolardi (uch variant yonma-yon o'lchangan). 4 birlikda panel 47 px, belgi 25% — detal tor bo'lib o'qiladi, belgi esa tasma bo'lib. Qo'shimcha chegara: `bandW = min(band, w / 4)` — belgi hech qachon panel enining choragidan oshmaydi. Tomon NOMI (Chap/O'ng/Tepa/Past) ATAYLAB berilmaydi: yorliq eskizi uzun tomonni doim vertikal chizadi, ya'ni `l/r/t/b` ning eskizdagi joyi `length > width` bo'lganda almashadi (`services/labels.py` `burilgan` xaritasi) — qat'iy jadval odatiy uzun detalda operatorga eskizga 90° zid nom ko'rsatardi. Qator kaliti, DOM id (`kv-row-…`) va `useScanFlash` kaliti — hammasi `route_id`, `part_id` emas: nostandart marshrutda (masalan `[3, 6, 3]`) bitta detal KROMKA'ni ikki marta oladi, o'shanda `part_id` DOM id'ni takrorlab xatcho'pni noto'g'ri qatorga tushirardi. Ma'lumot: `readTerminalKromka` (`refetchInterval: 30_000` + har skanda invalidatsiya); so'rov yiqilsa Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`) — ilgari xato jim yutilib, jadval "Arradan kelgan detal yo'q" bo'sh holatiga tushardi va kromkachi kelmagan detallarni kutib turardi.

2026-09-03: (0) O'ng «Jarayonda» paneli OLIB TASHLANDI — u «Holat» ustunidagi nusxa chiplarini takrorlar va jadvalni yarim kenglikka siqib, ko'p nusxali qatorlarda chiplarni ustma-ust (qator 4 barobar baland) qilib yuborardi. Endi jadval to'liq kenglikda; qatorlar uch pog'onada (`tier`): jarayondagi (2+ tomonli, bir tomoni skan qilingan) TEPADA `bg-amber-50/70`, keyin boshlanmaganlar, tugaganlari pastda `bg-green-50`; `PostHeader`da «Jarayonda N» sariq hisob. (1) `OperationChips` ga `defaultCode` (KROMKA 3, OVAL 5) — postning odatdagi amali chip sifatida chizilmaydi, faqat farqlisi («Fasat kromka»); ilgari har qatorda «Kromka» chipi sarlavhani takrorlardi. (2) `EdgeGlyph` — KROMKA ustunida kichik eskiz: qaysi tomonlarga kromka (amber qalin chiziq), CHEKDAGI rasm bilan bir konvensiya (`labels.py` `burilgan`: uzun tomon `length` bo'lsa eskiz tik, t→chap, b→o'ng, l→past, r→tepa). Kromkachi chekdagi rasm bilan solishtiradi — yozuv («2 tomon A») yo'nalishni aytmaydi.

### `frontend/src/components/Terminal/PrisadkaView.tsx`

**Maqsadi:** PRISADKA va ROVER post sahifasi: detallar + SCX fayllari, «SCX (N fayl)» yuklab olish tugmasi. Props: `orderId`, `onBack`, `showScx?` (default `true`; `routes/terminal.tsx` ROVER postida `false` beradi — SCX fayllar kerak emas), `onShowOnMap?(partCode)` (ROVER: detalni kesish xaritasida ochish — tugma faqat `!p.arra_route` detallarda chiqadi, chunki arradan kelgani rover xaritasida umuman yo'q), `toolbarContainer?` (ROVER "Chop etish" tugmasi terminalning umumiy chap ustuniga portal qilinadi). Ma'lumot: `readTerminalPrisadka` (`refetchInterval: 30_000`).

**TESHIKLAR SARLAVHA QATORIDA** (2026-09-21) — progressdan oldin: jami, keyin
`yuza` va `qirra` ALOHIDA (`holes_face`/`holes_edge`). Kromkadagi bilan bir sabab:
panel 1366×768, balandlik tanqis. Ajratilgani bejiz emas — qirra teshigi boshqa
o'rnatishni talab qiladi, ya'ni bu operator uchun reja. GibSaw bu sonni HECH QACHON
ko'rsatmagan (uning jadvalida faqat `drillTH` — «teshik bor» bayrog'i), demak bu
tsex uchun yangi ma'lumot.

- SCX oqimi (`showScx`): `lib/scxDir.ts` bilan — File System Access API `showDirectoryPicker` BIR MARTA, tanlangan papka IndexedDB'da (`mebelix-terminal/kv/scx-dir`), keyingi yuklab olishlar so'roqsiz; papka ichida proyekt nomli subpapka (`project_name`, taqiqlangan belgilar `_` ga) ochilib fayllar shu yerga yoziladi (URL — `scxFileUrl(id)`). API bo'lmasa `<a download>` fallback — bu yo'lda natijani BILIB BO'LMAYDI (server 404 bersa yoki brauzer yuklashni bloklasa ham `click()` jim qaytadi), shuning uchun toast "N ta SCX yuklash boshlandi — brauzer yuklamalarini tekshiring" deydi, "yuklab olindi" deb yolg'on va'da bermaydi (FSA yo'li esa aksincha aniq sanaydi va kamomad bo'lsa `toast.error` beradi). **SKAN hech qanday fayl yuklamaydi** — `saveScxToDir` yagona joydan, «SCX (N fayl)» tugmasi ortidagi `downloadAll` dan chaqiriladi: yuklash operator xohlaganda bo'ladi. Yuklab olishda tugmada jonli progress ("Yuklanmoqda… 12/81"); papka tugmasi YO'Q — tanlangan papka nomi sarlavhada xira «Papka: NOMI» izohi bo'lib turadi.
- **Papka bosqichi jim yiqilmaydi:** `downloadAll` ning `try` bloki `catch` bilan yopiladi — saqlangan papka o'chirilgan/ko'chirilgan yoki flesh olib qo'yilgan bo'lsa (`getDirectoryHandle` → `NotFoundError`) saqlangan handle tozalanadi (`clearSavedDir`) va operator "SCX papkasini ochib bo'lmadi — qayta bosing va papkani tanlang" toastini ko'radi; `AbortError` (foydalanuvchi dialogni bekor qilgani) jim o'tkaziladi. Ilgari faqat `try/finally` bor edi va xato unhandled rejection bo'lib ketardi: tugma jimgina qaytardi. Subpapka nomi ham qo'riqlangan — `projectFolder(...) || "scx"`, chunki `projectFolder` faqat taqiqlangan belgilarni tozalaydi va " " kabi nomdan bo'sh satr qaytarib, `getDirectoryHandle("")` ni yiqitardi.
- **So'rov xatosi JIM yutilmaydi:** `isError` da Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`). Ilgari faqat `isLoading` tekshirilardi va birinchi yuklash yiqilganda bo'sh `parts` yolg'on bo'sh holatga aylanardi — PRISADKA shoxida "Bu buyurtmada prisadka detallari yo'q", ROVER shoxida "Bu buyurtmada bu postga detal yo'q".
- Jadval ish-navbat tartibida: qilinmaganlar tepada, tugaganlar (✓ yashil) pastda; oxirgi skan bo'lgan qator KEYINGI skangacha chap chetdagi xatcho'p bilan ajralib turadi (`border-l-4 border-l-primary` — holat rangini bosmasin deb ataylab chetga chiqarilgan) va markazga avto-scroll bo'ladi (`useScanFlash` hooki — `done` o'zgargan qatorni topadi: lokal skan ham, ish markazidan skan-forvard ham). Chiplar nusxa (`instances`) darajasida: `done` — yashil ✓, `label_printed` — amber, aks holda kulrang; nusxa umuman bo'lmaganda faqat kulrang fayl nomlari chiziladi (holatsiz). Qator kaliti, DOM id (`pv-row-…`) va `useScanFlash` kaliti — hammasi `route_id`, `part_id` emas (KromkaView'dagi bilan bir xil qoida): nostandart marshrutda bitta detal shu postni ikki marta oladi va `part_id` ikki qatorni bitta kalitga siqib, har refetchda yolg'on "skan bo'ldi" xatcho'pini berardi. ROVER jadvalida qator NUSXA darajasida — u yerdagi kalit `route_id:instance_id` juftligi (`instKey`, DOM id `pv-inst-…`, `selectedId` ham shu satr): yolg'iz `instance_id` bilan takroriy qadamda tanlov ham, xatcho'p ham ikkala qatorga birdan tushardi.
- **QR chekni chiqarish** (`usePrintLabel("prisadka")`): marshrutida ARRA bo'lmagan (`arra_route=false`) detal jarayonni shu postdan boshlaydi — cheki shu yerdan chiqariladi. ROVER rejimida (`showScx=false`) qator (nusxa) tanlanadi va chapdagi katta "Chop etish" `TBtn` (portal) bosiladi; PRISADKA rejimida chek chiqarish tugmasi instansiya chipining ichida (printer ikonkasi, faqat `!done && !label_printed && !arra_route` nusxalarda).
- **Chekni bekor qilish** (ROVER jadvalida): `label_printed` bo'lgan VA cheki SHU POSTDA chiqarilgan (`ownLabel(p)` — `Boolean(onShowOnMap) && !p.arra_route`, ya'ni chek ikonkasi bilan aynan bir shart) nusxa qatorini ikki marta bosish (`onDoubleClick`) yoki ~600 ms bosib turish tasdiq dialogini ochadi ("Chekni bekor qilasizmi?" → "Ha, bekor qilinsin" / "Yo'q") va `useCancelLabel()` ni chaqiradi — ARRA xaritasidagi ikki marta / uzoq bosish bilan bir xil imo-ishora (u yerda esa jest avval `PartCard` ni ochadi va tasdiq undagi tugmadan keladi). Alohida tugma ataylab qilinmagan: qatorlar tor, tasodifiy bosish chekni o'chirib yuborardi. Imo-ishora haqida ekranda yozuv YO'Q (sarlavha legendasiz — pastdagi 2026-09-03 bandi, (4)).

2026-09-03 (terminal 3-qadam): (1) nusxa chipi YARIM YO'Lni ko'rsatadi — backend `PrisadkaInstance.scans/need` (`per_instance`: prisadkada bir nusxa 2 skan talab qilishi mumkin): «1/2» sariq; ilgari chip faqat done/undone edi va «Bajarildi 1/2» ustuni «2 nusxadan 1» deb o'qilardi. (2) Ustun sarlavhalari o'z izohi bilan (kioskda hover yo'q): «Detal ID · SCX» ostida legenda (2026-09-04 dan: «kulrang — chek yo'q · sariq — chek chiqqan, skan kutilmoqda · ✓ bajarildi»; ilgari «✓ tugadi · sariq — chek chiqqan / yarim · 1/2 = skan» edi) va «Skanlar — qilingan / jami» (ilgari «Bajarildi»). (3) SCX papkasi — o'rnatish sozlamasi, operator amali emas: tanlangan bo'lsa sarlavhada xira «Papka: NOMI» izohi (`getSavedDir().name`), tugma YO'Q — papka birinchi yuklashda bir marta so'raladi va eslab qolinadi; almashtirish — brauzer sayt ma'lumotini tozalash. Yuklash tugmasi «SCX (N fayl)» (ilgari «Hammasini yuklab olish», keyin «SCX → papkaga (N)»). (4) ROVER (nusxa rejimi) «Holat»: rover o'zi kesadigan (`ownLabel`) detalda «Chek yo'q» → «✓ Bajarildi» (chek chiqishi = avto-skan = bajarildi; oraliq sariq «Chek chiqarilgan» faqat avto-skan yiqilganda), arradan kelgan detalda «Bajarilmagan» → «✓ Bajarildi» (skan bilan). Sarlavha legendasiz — chiplarning o'zi yetarli, oqimni roverchi biladi. Chekni bekor qilish — ARRA xaritasi bilan BIR XIL imo-ishora: qatorni ikki marta bosish yoki uzoq bosish (~600 ms) → tasdiq dialogi («Ha, bekor qilinsin»); alohida tugma va sarlavhadagi «qatorni bosib turing» ishorasi yo'q (2026-09-04 da qisqa vaqt tugma bo'lgan, olib tashlandi). (5) Qatorlar Kromka bilan bir qoidada (`partTier`): yarim qolganlar tepada `bg-amber-50/70`, keyin boshlanmaganlar, tugaganlar pastda yashil.

### `frontend/src/components/Terminal/PostQueueView.tsx`

**Maqsadi:** BOYOQ va STOLYARKA post sahifasi (TMO ham — `TmoView` orqali) — NUSXA darajasidagi navbat (`readTerminalPostQueue`, `refetchInterval: 30_000`). Umumiy "Navbatdagi vazifalar" jadvali detal darajasida agregat berardi ("qoldiq 6/6") va navbatni hisobga olmasdi: operator hali arradan chiqmagan detalni ko'rib, skanerlab E004 olardi.

- Bitta jadval, qator = DETAL (kalit `part_code|process_code` — stolyarkada bir detal ikki amal bilan kelishi mumkin): ishi bor detallar tepada, tugaganlari pastda yashil (`tier` 0/1). Yetib KELMAGAN nusxalar chip bo'lmaydi — qatorda «+N yo'lda», jadval ostida «Yana N detal tsexda — shu bosqichga yetib kelgach chip bo'lib chiqadi» (ularni skanerlab bo'lmaydi, izlash ham vaqt yo'qotish).
- `LABELS` — «Nusxalar» ustuni sarlavhasidagi legenda so'zlari postga moslanadi: `done` (BOYOQ «Bo'yalgan», STOLYARKA «Bajarilgan», TMO «Qabul qilindi», noma'lum post — «Bajarilgan») va ixtiyoriy `queued` (TMO «tayyor, qabul kutilmoqda», sukut «navbatda»): «kulrang — navbatda · ✓ bo'yalgan».
- Qatorda: Kod, detal nomi, `Common/OperationChips` (stolyarkada olti xil amal, noto'g'ri petlya eshikni brak qiladi), **material** FAQAT BO'YOQda (`showMaterial` — bo'yoqchi uchun bu RANG/pardoz, amber; stolyarda detal qo'lida, materiali chekda — shovqin), `Izoh:` (texnolog izohi), `Har nusxaga biriktiriladi:` (yig'ma buyumga biriktiriladigan mayda detallar, `kod ×N` — HAR BIR ota nusxaga, ya'ni har bir chipga; so'z buyurtma sahifasidagi «Asosiy detalga biriktirish» bilan bir), o'lcham va «Oxirgi post» (detalning ishi TUGAGAN oxirgi post — tizim faqat shuni biladi, kim tashishini emas, shuning uchun sarlavha fakt, «Qayerdan olish» degan buyruq emas; bajarilgan qatorda bo'sh, hech bir qator ko'rsatmasa ustun umuman chizilmaydi — `showStage`).
- Skan alohida yo'l talab qilmaydi — terminalning umumiy skan mutatsiyasidan o'tadi, qator `done` bo'lib pastga tushadi.
- **So'rov xatosi JIM yutilmaydi:** `isError` da `Common/QueryError` chiziladi. Ilgari faqat `isLoading` tekshirilardi va xatoda `rows` bo'sh qolib "Bu proyektda bu postga tegishli detal yo'q." chiqardi — operator postni ishsiz deb tashlab ketardi.

2026-09-04 (terminal 4-qadam): qatorlar endi NUSXA emas, DETAL bo'yicha (Kromka naqshi): bitta detal = bitta qator (Kod / Nomi + amal chipi + material (faqat BO'YOQ) + `Izoh:` + `Har nusxaga biriktiriladi:` / O'lchami / Oxirgi post / Nusxalar), nusxalar №1…№n chip (kulrang «–» — navbatda, yashil ✓ — bajarildi; raqam = chek ID dumi), hali yetib kelmagan nusxalar chip emas — «+N yo'lda» va pastdagi umumiy izoh. Ilgari har nusxa alohida 4 qatorli satr edi: stolyarkada bitta detalning 16 nusxasi 2 ekran bo'lib ketardi. Tartib: ishi bor detallar tepada, tugaganlari pastda yashil; alohida «Bajarilgan» jadvali yo'q; «Stolyarkaga kelgan (N)» sarlavhasi ham yo'q — son `PostProgress`da bor edi; «Qayerda» ustuni «Qayerdan olish» (TMO'da ham) — ustun amalni aytsin.

### `frontend/src/components/Terminal/UpakovkaView.tsx`

**Maqsadi:** QADOQLASH post sahifasi. Chapda ochiq qadoq (kod, detallar soni, `~kg` — taxminiy, bloklamaydi; jadval **Detal ID** (`Serial`) · Nomi · O'lchami · Og'irligi · qizil chiqarish tugmasi; oxirgi skanerlangan TEPADA), o'ngda buyurtma detallari post navbati naqshida (qator = detal, `InstanceChip`: kulrang — tayyor, ✓ — qadoqlangan, «+N yo'lda»; tugaganlari yashil pastda; «Yana N detal tsexda» izohi) — o'ng ustun TO'LIQ balandlikda faqat detallar. "Yakunlangan" qadoqlar CHAPDA, ochiq qadoq (yoki yaratish tugmasi) ostida ixcham bir qatorlik yozuvlar (kod · N detal · ~kg · "Qayta ochish" — faqat bosilgan qatorda spinner; qator bosilsa ichi ochiladi — Detal ID + nomi, ikki ustun — «№3 qaysi qadoqda?» ga qadoqni qayta ochmay javob): qadoq tomonida qadoqlar, detal tomonida detallar; ilgari o'ng ustun pastida 38 % balandlikda siqilib qolardi, tab/switcher esa ma'lumotni yashirardi. Sarlavhada `PostProgress` (QOLDIQ = qadoqlanmagan). Oqim: "Qadoq yaratish" (ochiq qadoq yo'q holatining o'zida, tayyor detal bo'lmasa o'chiq — bo'sh qadoq tuzoq edi) → skanerlash → "Qadoqni yakunlash" (ovoz + toast, chek chiqadi). 2026-09-04 gacha o'ng ro'yxat nusxa-nusxa (981 qator), QOLDIQ yo'q, qadoq jadvalida faqat Kod edi.

- **Skan javobi**: muvaffaqiyat — terminalning umumiy yashil tasmasi (WS `scan.recorded`, BEKOR QILISH bilan; `cancel_scan` qadoq skanini qaytarganda detalni ochiq qadoqdan ham chiqaradi), ekran o'z toast/ovozini BERMAYDI (ilgari tasma + toast + ikki «bip»). Xato — `playError` + `toastScanError` (xabar sarlavhada, «Kod E008» kichik), E008 «allaqachon qadoqda» — `playWarning`; ochiq qadoq bo'lmasa `playWarning` + «Avval qadoq yarating». Ro'yxat sahifasida skan — `useTerminalScan` buyurtmani ochadi va shu ogohlantirishni beradi.
- **Poyga**: har mutatsiya `onMutate` da fon so'rovini bekor qiladi (`cancelQueries`) — 30 s'lik eski javob `setQueryData` natijasini ustidan yozmasin; har xatodan keyin `invalidateQueries` (boshqa terminal qadoqni yopgan bo'lishi mumkin). `terminal.tsx` `pachka.item`/`pachka.closed` WS hodisalarida ham ish so'rovlarini yangilaydi.
- **So'rov yiqilsa `QueryError`** (`isError` → "Qayta urinish"): busiz kiosk "Ochiq qadoq yo'q" va "Hammasi qadoqlangan." deb yolg'on tinch holat ko'rsatardi.

### `frontend/src/components/Terminal/InstanceChip.tsx`

**Maqsadi:** nusxa chipi — `PostQueueView` (BOYOQ/STOLYARKA/TMO) va `UpakovkaView` bir xil belgini chizsin: `№n` (ko'p nusxada) + «–» kulrang / «✓» yashil; `instanceNo(qr)` — chek ID dumi. Ilgari chip markup'i `PostQueueView` ichida edi.

### `frontend/src/components/Terminal/TmoView.tsx`

**Maqsadi:** TMO post sahifasi — 2026-09-04 dan faqat SKAN o'rami: ro'yxat umumiy `PostQueueView` (BOYOQ/STOLYARKA bilan bir naqsh — detal qatori, nusxa chiplari kulrang «tayyor, qabul kutilmoqda» (oldingi post skani — jismonan kelgani tizimga noma'lum) / ✓ «qabul qilindi», hali tsexdagilar «+N yo'lda» va pastdagi izoh). Umumiy `/terminal/orders/{id}/queue` TMO uchun ham aynan shu holatni beradi — uch buyurtmada `TmoOrderState` bilan son-ma-son solishtirildi (37/33/1/3, 981/0/872/109, 52/0/44/8).

- Ilgari ikki tab («Qabulga kelgan» nusxa-nusxa ro'yxat + «Qabul qilingan» vaqti bilan) va sarlavhada uch son (`TMO ga keldi`, `Qabul qilindi`, QOLDIQ — ikkitasi bir xil) bor edi: 981 nusxali buyurtmada 872 qatorli ro'yxat, hech qachon to'lmaydigan «Qadoq» ustuni. `["terminal","tmo",orderId]` so'rovi ketdi, `read_tmo_order` endpointini frontend endi chaqirmaydi.
- **Skan** (`registerScan` → `accept_into_tmo`): qadoq cheki (`PK-...`) detal QR'i emas — umumiy skan yo'li uni rad etardi; server ichidagi HAMMA nusxani birdan qabul qiladi. Javob `TmoOrderState.accepted` keshdagi ✓ chiplar soni bilan solishtiriladi: bittaga o'sgan bo'lsa o'z xabari YO'Q — skan boshqa postlardagidek terminalning yashil tasmasi (WS `scan.recorded`) bilan ko'rinadi (ilgari tasma + toast + ikki «bip»), qadoq bo'lsa ovoz + «Qadoq qabul qilindi — N detal», o'smasa (takroriy skan, server 200 — `client_event_id` barqaror) ogohlantirish. Keyin navbat so'rovi invalidatsiya qilinadi.
- **"Buyurtmani topshirish" tugmasi YO'Q** (`deliver_tmo_order` endpointi bilan birga). TMO buyurtmani topshirmaydi: hamma detal TMO dan o'tgach buyurtma `record_scan_at` da o'zi TAYYOR (COMPLETED) bo'ladi, TOPSHIRILDI esa managerning amali (`/orders/{id}`, faqat TAYYOR holatdan).

### `frontend/src/components/Terminal/OrderPicker.tsx`

**Maqsadi:** proyekt tanlagichi — HAMMA post sahifasi shundan boshlanadi. Kartada LOYIHA NOMI katta (2026-09-04: raqam bilan o'rin almashdi — ishchi buyurtmani nomidan taniydi, chekda ham nom sarlavha; nomsiz buyurtmada raqam katta), raqam xira `num`, prioritet badge'i, materiallar, `done/total` progress va qoldiq, listlar soni, muddat rangi. Kromka metri va teshik soni kartada ATAYLAB YO'Q (2026-09-21 da qo'shilib, o'sha kuni olib tashlandi): ular buyurtma tanlashga ta'sir qilmaydi — ro'yxat prioritet va muddat bo'yicha tartiblangan, lenta bo'yicha partiyalash esa operatorning emas, rejaning qarori. Karta takrorlanuvchi plitka: qarorni o'zgartirmaydigan har qator butun grid bo'ylab ko'payadi. Ular buyurtma ochilganda, aynan skladga borish daqiqasida ko'rsatiladi. `done/total` va `sheets_total` post semantikasida (backend `/terminal/orders` hisoblaydi: ARRA — chek∪skan, o'z listlari; KROMKA — detal bo'yicha). Props: `onPick`, `showCutmapBadge?`. Sarlavha doim «Buyurtmalar» (2026-09-04: admin bilan bir so'z; ilgari `title` prop — «Proyektlar — X uchun proyektni tanlang», postga qarab to'rt xil).

### `frontend/src/components/Terminal/PostHeader.tsx`

**Maqsadi:** post ekranlarining umumiy sarlavhasi — "Orqaga" tugmasi + LOYIHA NOMI (katta, `text-lg font-black`) + buyurtma raqami (xira, `num` — Detal ID prefiksi `B-2026-072_` bilan solishtirish uchun). 2026-09-04 gacha teskari edi; chekda (`labels.py`) ham loyiha nomi sarlavha, ishchi buyurtmani «Farhod parta» deb biladi. Ilgari beshta ekran shu blokni so'zma-so'z ko'chirib yozgan va bir-biridan uzoqlashgan edi (loyiha nomi ba'zisida tushib qolgandi).

- Props: `onBack`, `orderNumber`, `projectName?` (bo'lmasa sarlavha raqamning o'zi; `KromkaOrderState` ham 2026-09-04 dan `project_name` beradi), `className?`, `children?` (o'ngdagi farqlar: progress, tugmalar, badge).
- Chaqiruvchilar: `UpakovkaView`, `KromkaView`, `PrisadkaView` (ROVER va SCX shoxlari), `PostQueueView` (TMO sarlavhani `PostQueueView` orqali oladi). Raqam `min-w-0`/`truncate` ichida — uzun raqamda ellips.

### `frontend/src/components/Terminal/PostProgress.tsx`

**Maqsadi:** post ekranining yagona UZOQDAN o'qiladigan raqami — qancha ish qoldi. Oltita ekran (kromka, prisadka, rover, post navbati, TMO — `PostQueueView` orqali, qadoqlash) shu bitta komponentdan foydalanadi.

- O'lcham sanoat HMI qoidasidan: qulay o'qish masofasi ≈ harf balandligi × 150…200. 17" monoblokda piksel qadami ~0.26 mm, ya'ni `text-base` (16px) ≈ 3 mm ≈ 0.5 m (operator terminalga borishi kerak edi), `text-5xl` (48px) ≈ 9 mm ≈ 1.5 m. Qolgan hamma narsa — qatorlar, o'lchamlar, kodlar — qo'l uzunligida o'qiladi va kattalashtirilmaydi.
- Raqam **qoldiq**, "bajarildi" emas: operatorning savoli "yana qancha qoldi?", `4/25` dan uni hisoblab olish qo'lqopda va arra shovqinida ortiqcha ish. Bajarilgan/jami kichik shriftda yonida (kontekst).
- Hammasi bajarilganda raqam o'rniga yashil **TAYYOR**.

### `frontend/src/components/Terminal/ScanStrip.tsx`

**Maqsadi:** oxirgi skan natijasi + BEKOR QILISH tugmasi, har post ekranining tepasida (`PostScreen` orqali). Tsex shovqinida ovoz signaliga ishonib bo'lmaydi. `LastScan` tipi ham shu yerda eksport qilinadi. Props: `scan`, `canUndo` (60 s oynasi — taymer chaqiruvchida), `onUndo`, `onDefect?` (BRAK tugmasi — berilmasa chizilmaydi), `birlik?` (KROMKA'da "qirra" — qoldiq nimada o'lchanishini aytadi). Chek chiqarishdan tug'ilgan AVTO-skanda muvaffaqiyat banneri ko'rsatilmaydi — filtr `scan.recorded` payload'idagi `auto` bayrog'i bo'yicha (server `finalize_scan(auto=True)` bilan qo'yadi), POST NOMI bo'yicha emas: ROVER ham chek chiqaradi (roverda kesiladigan detal), ham qo'lda skan oladi (arradan kelganning rover qadami) — farq skanning kelib chiqishida. Katakning yashil bo'lishi o'zi tasdiq, banner dublikat edi, undagi BEKOR QILISH esa yarim-tuzoq — skanni qaytarib chek bayrog'ini qoldirardi (to'liq bekor — katak dialogida). Qo'l skani va xato/rad hamma postda ko'rinaveradi. 2026-09-04: xato/ma'lumot tasmasida sarlavha KOD emas, BIR SO'Z (`lib/mes.ts` `SCAN_CODE_WORDS`: E001 «MOS EMAS», E002 «CHEK BUZUQ», E003 «BEKOR», E004 «NAVBAT», E005 «SMENA YO'Q», E006 «BEYJIK», E007 «ALOQA YO'Q» (2026-09-27 dan; ilgari so'zi yo'q edi), E008 «TAKROR», E009 «SOZLAMA», E011 «QURILMA», E012 «CHIQQAN», ATX «QOLDIQ»; E011/E012 — chek chiqarish kodlari: tasmaga emas, chek mutatsiyasining toastiga tushadi, jadvalda esa `SCAN_ERROR_LABELS` bilan juftlik qoidasi uchun turadi), kod xabar yonida kichik xira («E004») — ishchi so'zni uzoqdan o'qiydi, kodni adminga aytadi.

### `frontend/src/components/Terminal/ShiftGate.tsx`

**Maqsadi:** "Kim ishlayapti?" — smenaning o'zi, login ekrani emas. Monoblok TERMINAL hisobi bilan bir marta, o'rnatishda kirgan va boshqa hech qachon parol termaydi (tsexda klaviatura yo'q); bu yerda esa KIM ishlayotgani yoziladi — autentifikatsiya emas, atributsiya. `routes/terminal.tsx` ikkala eksportni ham ishlatadi.

- `ShiftGate({ employees, pending, onStart, onCancel? })` — brigada bo'sh bo'lganda ish maydonini yopadigan `absolute inset-0 z-30` to'siq: postga biriktirilgan hodimlar `h-20` katta tugmalarda (ism + `position`), pastda "Yoki beyjikni skanerlang". Hodim biriktirilmagan bo'lsa yo'l ko'rsatuvchi matn ("Admin Hodimlar bo'limida postni belgilashi kerak"). `onCancel` berilsa pastda "Bekor qilish" tugmasi chiqadi — "+ Qo'shish" oqimidan orqaga yo'l; qurilma hisobida ekran smenasiz ishlay olmaydi, o'shanda berilmaydi. Qulf va to'liq ekran to'siqlari (`KioskOverlays`) bundan ustunroq.
- `CrewChips({ crew, onEnd, onAdd })` — sarlavhadagi brigada (`md:` dan yuqorida): ikki kishi bir ish markazida ishlashi mumkin, shuning uchun SHERIK ismlari doim ko'rinib turadi — ketgan odam o'chirishni unutsa, qolgani begona ismni ko'radi va bosib qo'yadi. Kirgan odamning O'ZI ro'yxatda yo'q (`crew.filter((s) => !s.is_me)`): u kimligini login allaqachon aytgan. Qurilma hisobida (TERMINAL) hech kim `is_me` bo'lmaydi, ya'ni u yerda hamma ism chiqadi — monoblokda kim ishlayotganini faqat shu ro'yxat aytadi. Ism bosilsa o'sha smena yakunlanadi (`onEnd`), "+ Qo'shish" keyingi tanlovni `join` rejimiga o'tkazadi (`onAdd`).

### `frontend/src/components/Terminal/PrintDevice.tsx`

**Maqsadi:** chek qurilmasi (post monobloki) — terminal sarlavhasidagi belgi va ulash oynasi. Ish markazida ulangan monoblok bo'lsa chek FAQAT undan chiqadi (server E011 bilan rad etadi, `services/terminal_device.py`); qurilmani admin `/agents` sahifasida beradi (`Agents/TerminalDevices.tsx`). Ma'lumot `GET /terminal/context` dagi to'rt maydondan: `print_lock` (ish markazida ulangan qurilma bor), `print_allowed` (SHU brauzer chek chiqara oladimi; `print_lock` yo'q bo'lsa doim rost), `print_device_name` (shu brauzer ulangan qurilma nomi), `print_pairing` (ish markazida kodi kutilayotgan qurilma bor).

- `printBlocked(ctx)` — `print_lock && print_allowed === false`; ichki `pairingOffered` — `print_pairing && !print_device_name`.
- `PrintDeviceChip({ ctx, onOpen })` — `routes/terminal.tsx` sarlavhasida, MES agent belgisidan (`MonitorX`) keyin, `CrewChips` dan oldin. To'silgan brauzerda qizil (`destructive`) «Chek chiqmaydi» (`PrinterX`); admin kod bergan-u shu brauzer hali ulanmagan bo'lsa amber konturli «Qurilmani ulash» (`KeyRound`); boshqa holatda HECH NARSA chizilmaydi — sarlavha faqat muammoni ko'rsatadi (agent belgisi bilan bir falsafa). Ikkalasi `h-12`, bosilsa `onOpen`.
- `PrintDeviceDialog({ ctx, open, onOpenChange })` — `sm:max-w-md`. To'silgan holatda sarlavha «Bu qurilmadan chek chiqmaydi» va izoh (chek faqat shu ish markazi monoblokidan chiqadi, skan va xarita bu yerda ham ishlaydi, postning monobloki bo'lsa — kodni kiriting), aks holda «Qurilmani ulash». Kod maydoni (`placeholder="ABCD-EFGH"`, `maxLength={16}`, katta `font-mono`) — harf/raqamdan boshqa belgi olib tashlanib katta harfga o'tkaziladi; 4 belgidan kam bo'lsa «Ulash» (`LoadingButton`) o'chiq, Enter ham yuboradi (`isPending` da emas — ikkinchi Enter ishlatilgan kodni qayta yuborib «noto'g'ri kod» olardi). `TerminalDevicesService.pairTerminalDevice` (`POST /terminal-devices/pair`) muvaffaqiyatida toast «Qurilma ulandi: {nom} — chek shu yerdan chiqadi» va `["terminal","context"]` invalidatsiyasi; xato — `handleError` (kod boshqa ish markaziniki bo'lsa server o'sha ish markazini aytadi, aks holda «Ulanish kodi noto'g'ri yoki muddati o'tgan.»). Server httpOnly `terminal_device` cookie qo'yadi — JS uni ko'rmaydi, holat faqat kontekstdan o'qiladi.
- `routes/terminal.tsx`: oyna holati `deviceOpen` `dialogOpen` ga qo'shilgan (ochiqda skan fokusi o'chadi — kodni terish mumkin); shu ish markazining (`machine_id`) WS `terminal_device.*` hodisasi `["terminal","context"]` ni invalidatsiya qiladi — admin kod bersa yoki qurilmani o'chirsa belgi sahifa yangilanmasdan paydo bo'ladi yoki yo'qoladi.
- Chek tugmalari YASHIRILMAYDI: `printBlocked` faqat shu faylda ishlatiladi. To'silgan brauzerda chek bosilsa server E011 qaytaradi va u `handleError` toastida («E011: …») chiqadi (qarang `Terminal/usePrintLabel.ts`).

### `frontend/src/components/Terminal/KioskOverlays.tsx`

**Maqsadi:** ikkita to'siq ekrani — majburiy to'liq ekran (`requestFullscreen` user-gesture talab qiladi, shuning uchun tugma) va qulf. Ikkalasi bitta ichki `Overlay` maketidan. `requestFullscreen()` rad etilishi mumkin (iframe, brauzer sozlamasi), shuning uchun promise `.catch` bilan tutiladi va operator "To'liq ekranga o'tib bo'lmadi" toast'ini ko'radi — aks holda jim unhandled rejection bo'lardi.

Qulf ekranida `lockReason` berilsa (qulf tugmasida sabab tanlangan) matn «To'xtash sababi: X. Ochish uchun beyjikni skanerlang» bo'ladi.

### `frontend/src/components/Terminal/DowntimeReason.tsx`

**Maqsadi:** stanok to'xtashi sababini smenadagi hodim kiritadi (`docs/12-oee.md` §7, endpointlar `docs/03` — `downtimes.py`). Ikki eksport, bitta ichki `ReasonGrid` (rejasiz/rejali guruhlar, `min-h-14` katta tugmalar; `needs_note` sabab tanlansa izoh maydoni chiqadi va bo'sh izohda «Saqlash» o'chadi) va `Who` (kim kiritadi — brigada ismlari).

- `StopReasonPrompt({ crew, suppressed, onVisibleChange })` — Pico to'xtashi: `PENDING_KEY` so'rovining birinchi yozuvi; sarlavha qizilda «Avariya — nima bo'ldi?», qolganida «Stanok ishlamayapti — nima sababdan?», tur yorlig'i (`DOWNTIME_KIND_LABELS`), vaqt oralig'i, davomiyligi (1 s da yangilanadi), davom etayotgan bo'lsa «davom etmoqda»; bir nechta bo'lsa «yana N ta to'xtash sababsiz». MAJBURIY (2026-10-16): «Keyinroq» yo'q, X tugmasi chizilmaydi (`DialogContent showCloseButton={false}`), Esc va tashqariga bosish o'chirilgan — oyna faqat sabab saqlab yopiladi. Oynadagi to'xtash almashsa tanlangan sabab va izoh tozalanadi (render paytida, `shownId`), ya'ni eski tanlov boshqa to'xtashga saqlanmaydi. Ko'rinish holati `onVisibleChange` bilan `terminal.tsx` ga qaytadi (skan fokusi to'xtaydi).
- `LockReasonDialog({ open, crew, onCancel, onLocked })` — qulf tugmasi: sabab → «Saqlash va qulflash» (`lockWithDowntimeReason`) → `onLocked(sabab nomi)`. Sabablar ro'yxati bo'sh bo'lsa ogohlantirish va «Sababsiz qulflash» (`onLocked(null)`) — ro'yxat kiritilmagani ishni to'smaydi.

### `frontend/src/components/Terminal/useKiosk.ts`

**Maqsadi:** kiosk qobig'i. `useKioskShell(canReload)` — kontekst menyusini o'chirish (sensorda long press chekni bekor qilish uchun kerak), to'liq ekran holati (Fullscreen API yoki `display-mode`), yangi build tekshiruvi (`/` HEAD ETag, 5 daqiqada) va XAVFSIZ paytda avto-reload (`canReload()` — xarita yopiq va `QUIET_MS`=2 daqiqa skan bo'lmagan). `useScanFocus(enabled, inputRef)` — avto-skan inputini fokusda ushlash (2 s interval) va fokussiz terilgan birinchi belgida fokusni qaytarish. `terminal.tsx` `enabled` ni ARRA xaritasi ochiqda (input yashirin) VA tasdiq/sabab dialogi ochiqda (`dialogOpen`: `logoutOpen`/`endFor`/`undoFor`/`defectFor`/`stopPromptOpen`/`lockAsk`/`deviceOpen` — oxirgisi chek qurilmasini ulash oynasi, `Terminal/PrintDevice.tsx`) o'chiradi: input modaldan tashqarida, ya'ni aks holda interval fokusni tortadi, Radix fokus tuzog'i darhol qaytaradi — bemaqsad focus/blur churn. Dialog yopilgach effekt qayta yoqiladi va `focus()` darhol chaqiriladi.

### `frontend/src/components/Terminal/useTerminalScan.ts`

**Maqsadi:** skan yo'naltirgichi — bitta QR to'rt manzilga ketishi mumkin: beyjik UUID → smena (u ham 2 s duplikat to'sig'i ostida — skanerning takror o'qishi ikkita `POST /terminal/session` yuborardi; `routes/terminal.tsx` da `startShift.isPending` ikkilamchi to'siq); ekranning o'z sinki (`viewScanRef` — qadoqlash/TMO, chunki detal qaysi qadoqqa tushishini faqat o'sha ekran biladi va qadoq QR'i `PK-...` umumiy yo'lda rad etilardi); KROMKA/OVAL lokal tekshiruvi (`kromkaScanRef`, 5 s to'siq, picker ochiq bo'lsa `/qr/{qr}/order` bilan proyektni o'zi ochadi); qolgani umumiy skan (2 s duplikat to'sig'i). KROMKA/OVAL to'sig'i HAR urinishni hisoblaydi, faqat muvaffaqiyatlisini emas: ilgari u faqat yozilgan skanda o'rnatilardi, ya'ni rad etilgan QR to'siqni umuman ishga tushirmasdi va skanerning takror o'qishi har safar yangi `/qr/{qr}/order` so'rovi bilan yangi toast berardi (o'lchandi: bir xil QR 3 marta → 3 so'rov, 3 bip; endi 1 so'rov + 2 ta "endigina skan qilindi").

### `frontend/src/components/Terminal/usePrintLabel.ts`

**Maqsadi:** yorliq chop etish mutatsiyasi — `CutmapView` (ARRA xaritasi) va `PrisadkaView` (ROVER/PRISADKA) baham ko'radi: `TerminalService.printInstanceLabel` + toast + `handleError`; `scope` ("cutmap" | "prisadka") qaysi terminal keshi (`["terminal", scope]`) yangilanishini belgilaydi. Shu fayl `useCancelLabel()` ni ham eksport qiladi (`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi) — uni ham CutmapView, ham PrisadkaView chaqiradi. Server chek chiqarishni ikki holatda rad etadi — ikkalasi ham shu `handleError` toastida kodi bilan chiqadi («E011: …»): **E011** — ish markazida ulangan chek qurilmasi bor, so'rov esa boshqa brauzerdan (telefon; qarang `Terminal/PrintDevice.tsx`); **E012** — nusxaning cheki allaqachon chiqarilgan (server `label_printed_at` ni atomik band qiladi, xabarda Toshkent vaqti) — qayta chiqarish faqat `useCancelLabel()` orqali. Xuddi shu ikki tekshiruv qoldiq chekida ham bor (`CutmapView` dagi `wastePrint`, `handleError`); E011 qadoqni yakunlashda ham (`UpakovkaView`, `toastScanError` — xabar sarlavhada, «Kod E011» ostida).

### `frontend/src/components/Terminal/useDragScroll.ts`

**Maqsadi:** barmoq bilan SURIB aylantirish — tsex monoblokida scrollbar o'rniga. `useDragScroll(axis = "y")` `{ ref, props }` qaytaradi; `props` ni scroll konteyneriga yoyib qo'yish kifoya. Sabab: monoblokning sensor drayveri barmoqni SICHQONCHA deb ko'rsatadi, ya'ni surish brauzer uchun sichqoncha surishi bo'ladi — ro'yxat aylanmaydi, matn belgilanadi; ingichka scrollbar'ni qo'lqopda tortish esa deyarli imkonsiz. Hook surishni `scrollTop`/`scrollLeft` ga o'giradi. `pointerType === "touch"` bo'lsa ATAYLAB tegmaydi: u yerda aylantirishni brauzerning o'zi qiladi va ikkalasi birga ishlasa ro'yxat ikki barobar tez sirg'anardi (Chrome'da o'lchandi: sichqoncha 120px surish → `scrollTop` 120, sensor 120px surish → 0, ya'ni haqiqiy sensorli qurilmada xulq o'zgarmaydi). 8px ostidagi harakat SURISH hisoblanmaydi va bosishga tegmaydi, undan kattasi esa keyingi `click` ni yutadi (`onClickCapture`) — aks holda ro'yxatni surganda tasodifan detal ochilib ketardi (o'lchandi: 5px surish → `scrollTop` 0, bosish o'tadi). Bosish faqat ro'yxat HAQIQATAN qimirlagandagina yutiladi: sig'ib turgan qisqa ro'yxatda (OVAL 8, STOLYARKA 10 qator — prodda o'lchangan) aylantiriladigan joy yo'q, ya'ni barmoq qimirlasa ham bu bosish bo'lib qolaveradi (o'lchandi: qisqa ro'yxatda 120px surish → `scrollTop` 0, bosish O'TADI).

Nega hamma ro'yxatga: prod ma'lumotida bitta buyurtmadagi qator soni PRISADKA'da o'rtacha 70 (p90 109), KROMKA'da 48 (p90 109), ARRA'da 62 — 17" monoblokka ~11-12 qator sig'adi, ya'ni deyarli har buyurtmada aylantirish kerak. OVAL (max 8) va STOLYARKA (max 10) sig'adi, lekin ularni ALOHIDA chetlab o'tib bo'lmaydi: `KromkaView` ham KROMKA, ham OVAL ni, `PostQueueView` ham BOYOQ, ham STOLYARKA ni chizadi. Sig'ib turgan ro'yxatda hook baribir hech nima qilmaydi (yuqoridagi qoida), shuning uchun narxi nol.

Chaqiruvchilar — terminalning HAMMA aylanadigan ro'yxati, 10 ta konteyner: `OrderPicker` (proyekt tanlash), `KromkaView`, `PrisadkaView` (jadval + SCX ro'yxati), `UpakovkaView` (uchta: ro'yxat, tanlash, tugaganlar), `PostQueueView`, `CutmapView` (vertikal materiallar jadvali + gorizontal material tablari — `useDragScroll("x")`). Gorizontal variant ilgari `CutmapView` ichida lokal nusxa edi; `touch-pan-y` bilan birga ishlaydi — vertikalini brauzer, gorizontalini hook bajaradi, qo'sh aylantirish bo'lmaydi. `TmoView` da aylanadigan ro'yxat yo'q.

### `frontend/src/components/Terminal/audio.ts`

**Maqsadi:** skan ovoz signallari (tsex shovqinida majburiy) — WebAudio, internetsiz ishlaydi: `playSuccess` (600 Hz qisqa), `playError` (200 Hz uzun), `playWarning` (2×800 Hz). `AudioContext` birinchi bipda yaratiladi va har bipdan oldin `state === "suspended"` bo'lsa `resume()` qilinadi — stanok posti kiosk rejimida brauzer foydalanuvchi bosmasdan ochiladi, autoplay siyosati bo'yicha kontekst to'xtatilgan holda tug'iladi va resume'siz WS orqali kelgan majburiy signal jim qolardi. To'rtta chaqiruvchi bor: `routes/terminal.tsx` (skan natijasi — `E008` va ATX qoldiq QR'ida `playWarning`, qolgan xatolarda `playError`; smena ochish success/error; bekor qilish → `playWarning`; oflayn `E007` → `playError`), `useTerminalScan.ts` (qulflangan ekran va KROMKA/OVAL 5 s to'siqda `playWarning`, KROMKA/OVAL skani topilmasa/xato bo'lsa `playError`), `TmoView.tsx` (qabul javobi) va `UpakovkaView.tsx` (qadoqqa skan javobi).

---

## UserSettings komponentlari — `frontend/src/components/UserSettings/`

`/settings` sahifasining bo'limlari (joriy foydalanuvchining o'z profili, `*Me` endpointlari).

**O'z hisobini o'chirish UI'da yo'q:** `DeleteAccount.tsx` olib tashlangan, `routes/_layout/settings.tsx` da faqat ikkita tab qolgan ("Profilim", "Parol"). Backend endpointi (`DELETE /users/me` — `backend/app/api/routes/users.py`) va generatsiya qilingan `UsersService.deleteUserMe` (`frontend/src/client/sdk.gen.ts`) saqlanib qolgan, lekin `frontend/src` da uni chaqiradigan joy yo'q.

### `frontend/src/components/UserSettings/UserInformation.tsx`

**Maqsadi:** profil ma'lumotlari (ism, telefon) — ko'rish/tahrirlash rejimi almashinadigan forma.

- `editMode` state: o'qish rejimida qiymatlar `<p>` sifatida (bo'sh ism — "—"), "Tahrirlash" tugmasi; tahrirlash rejimida `Input` lar, "Saqlash" (`disabled={!form.formState.isDirty}`) va "Bekor qilish" (`form.reset()` + rejimdan chiqish).
- `onSubmit` faqat o'zgargan maydonlarni `UserUpdate` payloadga qo'shadi va `UsersService.updateUserMe` ni chaqiradi; muvaffaqiyatda `form.reset(form.getValues())` va `["currentUser"]` invalidatsiyasi (kalitsiz chaqiruv butun ilova querylarini qayta so'rardi). Ism `data.name ?? null` bilan uzatiladi: `optionalNameSchema` bo'sh matnni `undefined` ga aylantiradi, u esa JSON tanadan tushib qolardi va tozalash jimgina yo'qolardi — backend `name` ni nullable deb qabul qiladi (`_NULLABLE_FIELDS`, `backend/app/api/routes/users.py`).

### `frontend/src/components/UserSettings/ChangePassword.tsx`

**Maqsadi:** parolni o'zgartirish formasi.

- zod: `current_password` — `min(1)` (kuch sxemasi QO'LLANMAYDI: eski/seed parol bugungi siyosatga mos kelmasligi mumkin, backend uni faqat hash bilan solishtiradi — aks holda parolni umuman almashtirib bo'lmasdi), `new_password` — `passwordSchema`, `confirm_password` + mos kelish refine'i; `mode: "onSubmit"`.
- Mutation: `UsersService.updatePasswordMe({ body })`; muvaffaqiyatda toast + `form.reset()`.
- Uchchala maydon `PasswordInput` (ko'rish/yashirish ko'zchali) bilan, `aria-invalid={fieldState.invalid}` uzatiladi.

---

## ui komponentlari — `frontend/src/components/ui/`

shadcn/ui asosidagi 24 ta primitiv. Ko'pchiligi standart generatsiya; quyidagi jadvalda qaysilari o'zgartirilgani ko'rsatilgan.

**Tizim faqat light rejimda ishlaydi.** shadcn generatsiyasidan kelgan 23 ta `dark:` utility klass yettita fayldan olib tashlangan (`badge` 3, `button` 7, `checkbox` 3, `dropdown-menu` 1, `input` 2, `select` 3, `tabs` 4). Shu bilan birga `src/index.css` dagi `@custom-variant dark (&:where(.dark, .dark *));` qatori ham o'chirilgan — u faqat `dark:` klasslarni `prefers-color-scheme` dan uzib, o'lik `.dark` klassiga bog'lash uchun kerak edi; qo'llanadigan `dark:` klass qolmagach hack'ning ma'nosi yo'q (`index.css` da o'rniga qisqa izoh turibdi). Toaster ham `theme="light"` da qattiq belgilangan, tema tokenlari dark uchun qayta belgilanmagan.

| Fayl | Komponent(lar) | Asos | Custom o'zgartirish |
|---|---|---|---|
| `avatar.tsx` | Avatar, AvatarFallback | Radix Avatar | `AvatarImage` olib tashlangan (boshqasi standart) |
| `badge.tsx` | Badge (`badgeVariants` — fayl ichida, eksport emas) | cva | Deyarli standart (`rounded-full` shakl); `dark:` klasslar olib tashlangan |
| `button.tsx` | Button, buttonVariants | cva + Slot | **Qo'shimcha o'lcham**: `icon-sm` (size-8; `icon` — size-9); `dark:` klasslar olib tashlangan |
| `card.tsx` | Card, `cardSurface` konstanta | native div | **Soddalashtirilgan custom**: faqat yuza (`rounded-xl border bg-card`), shadcn'ning 5 qismli Header/Title/... API'si ataylab yo'q; `<ul>`/`<details>` kabi teglar uchun `cardSurface` klassi ham eksport |
| `checkbox.tsx` | Checkbox | Radix Checkbox | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `date-picker.tsx` | DatePicker | react-day-picker + Popover | **To'liq custom** (pastda) |
| `dialog.tsx` | Dialog, DialogContent, DialogHeader/Footer/Title/Description, ... | Radix Dialog | `showCloseButton` (sukut `true`; `false` — X chizilmaydi, majburiy oyna uchun: `StopReasonPrompt`, 2026-10-16) |
| `dropdown-menu.tsx` | DropdownMenu* (Item `variant="destructive"` bilan), 6 ta eksport | Radix DropdownMenu | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `form.tsx` | Form, FormField, FormItem/Label/Control/Message, useFormField | react-hook-form + Radix Label | Yo'q |
| `input.tsx` | Input | native `<input>` | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `label.tsx` | Label | Radix Label | Yo'q |
| `loading-button.tsx` | LoadingButton (`ButtonProps` — fayl ichida, eksport emas) | `buttonVariants` (button.tsx dan import) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | `Input` + Button | **To'liq custom** (pastda) |
| `popover.tsx` | Popover, PopoverTrigger, PopoverContent | Radix Popover | Deyarli standart (`rounded-xl`, `p-3`, `align="start"`) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 7 ta eksport | Radix Select | `dark:` klasslar olib tashlangan; `SelectContent` default'i `align="start"` (shadcn'da `center`) + `sideOffset={4}` — boshqa suzuvchi qatlamlar bilan bir xil |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 14 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
| `switch.tsx` | Switch | Radix Switch | Yo'q (butun frontendda YAGONA chaqiruvchi — `agents.tsx` dagi chek chiqarish `can_print` almashtirgichi) |
| `table.tsx` | Table, TableHeader/Body/Row/Head/Cell | native table | **Stil custom**: konteyner `rounded-lg border`, TableHeader `bg-muted/50`, TableHead `h-11 text-xs font-semibold uppercase tracking-wider`, TableCell `px-4 py-3 whitespace-nowrap` |
| `tabs.tsx` | Tabs, TabsList, TabsTrigger, TabsContent | Radix Tabs | `dark:` klasslar olib tashlangan; **mobil uchun o'zgartirilgan** (2026-09-27): `TabsList` ota elementdan kengaymaydi — `max-w-full overflow-x-auto justify-start`, tab'lar `shrink-0`, scroll chizig'i yashirin (`scrollbar-width: none`); qaysi tomonda yana tab bo'lsa o'sha chet 40 px xiralashadi (`index.css`: `@property --tabs-chap/--tabs-ong` + scroll-driven `tabs-chet`, `@supports` ichida — qator sig'sa timeline faol emas, xiralik yo'q); `Tabs` ildizi `min-w-0` (qatordagi flex element bo'lsa torayishi uchun — hisobotlar). Ilgari 360 px da buyurtma (+47 px), nuqsonlar (+24) va hisobotlar (+60) sahifasi yonga surilardi (390 px da buyurtma +17, hisobotlar +30), tizim sozlamalarida oxirgi tab'lar qirqilib, ularga yetib bo'lmasdi |
| `textarea.tsx` | Textarea | native `<textarea>` | Yo'q (standart shadcn; anketa "Qo'shimcha izoh" maydoni uchun qo'shilgan) |
| `tooltip.tsx` | Tooltip, TooltipTrigger/Content/Provider | Radix Tooltip | Yo'q (delayDuration=0) |

### `frontend/src/components/ui/sidebar.tsx` (custom tafsilotlari)

Eng katta ui fayl (~500 qator, 14 eksport). shadcn'ning rasmiy sidebar blokiga asoslangan, quyidagi o'zgarishlar bilan:

- **Cookie'dan boshlang'ich holatni o'qish**: standart shadcn faqat cookie'ga *yozadi*; bu yerda `getInitialOpen()` funksiyasi `sidebar_state` cookie'sini o'qib, sahifa yangilanganda ochiq/yopiq holatni tiklaydi (`useState(getInitialOpen)` lazy initializer).
- `SidebarTrigger` sr-only matni dinamik va o'zbekcha: `(isMobile ? openMobile : open) ? "Menyuni yig'ish" : "Menyuni ochish"` (telefonda tugma Sheet'ni almashtiradi; 2026-09-27 gacha desktop `open` olinib, mobilda teskari nom aytilardi); mobil `Sheet` ning sr-only sarlavhasi "Yon menyu", tavsifi "Mobil yon menyu".
- `sidebarMenuButtonVariants` o'lchamlari brendga moslangan: `default: "h-8 text-sm rounded-lg"`, `lg: "... rounded-xl data-[state=closed]:rounded-lg"`.
- `SidebarHeader` (`p-2 pb-3`) va `SidebarFooter` (`gap-3 p-2`) padding'lari sozlangan; `SidebarInset` `bg-transparent` va **`min-w-0` SHART**: u flex elementi va sukut `min-width: auto` bilan keng kontent (loglar jadvali, chip qatori) SAHIFANI kengaytirib yubordi — sarlavhadagi tugmalar ekrandan chiqib ketdi va skroll sahifa darajasida paydo bo'lib, ichkaridagi `overflow-x-auto` konteynerlari ishlamay qoldi.
- Muhim konstantalar: `SIDEBAR_WIDTH = "16rem"`, `SIDEBAR_WIDTH_ICON = "3rem"`, `SIDEBAR_WIDTH_MOBILE = "18rem"`, klaviatura yorlig'i **Ctrl/Cmd+B** (`SIDEBAR_KEYBOARD_SHORTCUT = "b"`).
- Mobil rejimda `Sheet` ichida render qilinadi (`useIsMobile` — `@/hooks/useMobile`); `useSidebar()` hooki `{ state, open, setOpen, openMobile, setOpenMobile, isMobile, toggleSidebar }` kontekstini beradi — `Sidebar/Main.tsx` va `Sidebar/User.tsx` shundan foydalanadi.

### `frontend/src/components/ui/dialog.tsx` (custom qism)

`DialogContent` ga `max-h-[calc(100dvh-2rem)] overflow-y-auto` qo'shilgan (2026-09-03): shadcn default'ida balandlik chegarasi yo'q edi — terminaldagi `PartCard` dialogi (chizma + QR + tugmalar, ~790px) 17" monoblokning 768px ekraniga sig'may, SARLAVHASI (№ va nusxa ID) ekrandan tepaga chiqib ketar va aylantirib ham bo'lmasdi. Endi har qanday uzun dialog ichida aylanadi.

### `frontend/src/components/ui/loading-button.tsx` (custom)

shadcn'da yo'q, loyihaga qo'shilgan komponent. `buttonVariants` ni `button.tsx` dan import qiladi (BITTA manba — avvalgi copy-paste nusxa divergensiya bergani uchun birlashtirilgan; `icon-sm` o'lchami ham ishlaydi) va ustiga `loading` prop qo'shadi.

```tsx
function LoadingButton({ className, loading = false, children, disabled, variant, size, ...props }: ButtonProps)
// loading=true -> disabled + <Loader2 className="h-5 w-5 animate-spin" />  (oraliqni buttonVariants dagi gap-2 beradi)
```

Barcha mutation submit tugmalarida ishlatiladi — jami 28 fayl (PersonDialog, AddClient, AddOrder, EditOrder, MachineAssign, OrderMatrix, CustomRoutes, BazisPanel, CutmapView, PartCard, PrisadkaView, UpakovkaView, DefectDialog, DowntimeReason, `Warehouse/CatalogEdit`, PrintDevice (ulash oynasi «Ulash»), `Agents/TerminalDevices` («Kod yaratish»), ConfirmDialog, ChangePassword, UserInformation, login formasi, anketa saqlash paneli, employees beyjik dialogi (`BadgeDialog` — "Chop etish" va "Yo'qolgan — yangi beyjik berish"), work-centers ish markazi formasi, buyurtma sahifasi amallari, agents sahifasidagi agent qo'shish formasi, brak sahifasi (`defects`), tizim sozlamalari sahifasi) va uzoq davom etadigan amallarda — `PrisadkaView` dagi «SCX (N fayl)» tugmasi jonli progress yozuvi bilan ("Yuklanmoqda… 12/81").

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `ui/input` ni compose qiladi (`pr-10` bilan), o'ng tomonida ghost `Button size="icon-sm"` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi; aria-label "Parolni yashirish/ko'rsatish"). `React.ComponentProps<"input">` propslarini o'tkazadi (forwardRef yo'q — React 19 uslubi); `aria-invalid` ni chaqiruvchi o'zi uzatadi. `UserSettings/ChangePassword.tsx`, `routes/login.tsx` va `People/PersonDialog.tsx` da ishlatiladi — jami uchta chaqiruvchi; oddiy `Input type="password"` frontendda umuman qolmagan.

### `frontend/src/components/ui/date-picker.tsx` (custom)

shadcn'da yo'q, to'liq loyihaga yozilgan o'zbekcha sana tanlagich: `react-day-picker` (`uz` locale) + `Popover`. Qiymati form/API bilan mos `"YYYY-MM-DD"` satr, ko'rinishi `DD.MM.YYYY`; tanlangach trigger yonida ALOHIDA "X" tozalash tugmasi (aria-label "Sanani tozalash" — trigger ichida emas: tugma ichida tugma yaroqsiz HTML edi, tab bilan yetib bo'lmasdi), kalendar ostida "Bugun"/"Tozalash" tugmalari. Props: `value`, `onChange`, `placeholder?`, `className?` (trigger tugma kengligi uchun — masalan anketada `w-full`), `disablePast?` (bugundan oldingi kunlar xira — `opacity-30`, `cursor-not-allowed`, hover fonsiz — va tanlanmaydi: react-day-picker `disabled={{ before: new Date() }}`, kalendar kuni bo'yicha, ya'ni bugun kunning istalgan soatida ochiq; hozir faqat yangi buyurtma muddatida), `aria-label?` (`<Field>` ichida ko'rinadigan label bo'lmaganda). **Bugun** och amber fon (`amber-100`, hoverda `amber-200`) va qalin `amber-800` raqam (fonda 6.41:1) bilan — tizimdagi «bugun» rangi, buyurtmalar jadvalidagi bugungi muddat ham amber (`deadlineTone`). Halqa emas, fon: ilovada amber halqa fokus belgisi (`--ring`), bugun unga o'xshamasin. Ilgari qalin `text-primary` edi: oddiy kun raqami (`--foreground`) bilan kontrasti 1.56:1 — tsex menejeri bugun ajralib turishini so'ragan (skrinshot 2026-10-04). Fon va raqam rangi faqat tanlanmagan bugunga (`data-selected` katakda, tugmada emas) — tanlangan bugun boshqa tanlangan kun kabi to'q ko'k fon va oq raqam. Qo'shni oy kunlari `muted-foreground/70` — tanlanadi, shuning uchun xira o'tgan kunlardan to'qroq (ilgari `/40` edi va ular bilan ≈1.05:1 — deyarli bir xil; endi 1.60:1). Buyurtma deadline'i (`Orders/orderForm.tsx` — `AddOrder`/`EditOrder`), hisobot oralig'i (`routes/_layout/reports.tsx`), loglar sana filtri (`routes/_layout/logs.tsx`), anketa o'lchov sanasi (`routes/_layout/anketa.$orderId.tsx`) va tizim sozlamalari (`routes/_layout/system-settings.tsx` — OEE boshlanish kuni va bayram sanalari) uchun ishlatiladi — jami beshta chaqiruvchi.

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
  └─ employees.tsx: ui/table + AccessCell         │    └─ usePrintLabel
       │    (isLoading → Skeleton)                └─ audio (playSuccess/Error/Warning)
       ├─ People/PersonDialog (F.I.Sh · telefon · lavozim)
       ├─ BadgeDialog (chop etish · yangi beyjik)
       └─ TogglePerson / DeletePerson ─ ConfirmDialog

routes/_layout/anketa.$orderId → components/Anketa
  ├─ Section / Field / Num / NumInput / CheckCard / CheckGrid / Choice / ShapeChoice
  ├─ RoomPhotos (drag&drop + Dialog preview)
  ├─ RoomSummary (room + survey) → Facts (canEdit=false ko'rinishi)
  └─ ConfirmDialog (xona o'chirish) · DatePicker · Textarea · LoadingButton

routes/_layout/agents → components/Agents
  └─ TerminalDevicesSection (chek qurilmalari) ─ PairCode (fmtCode/CodeTtl) · ConfirmDialog · RowAction · EmptyRow

routes/terminal (sarlavha) → Terminal/PrintDevice
  └─ PrintDeviceChip («Chek chiqmaydi» / «Qurilmani ulash») + PrintDeviceDialog (pairTerminalDevice)

routes (settings)                               routes (__root / layout)
  ├─ UserInformation                              ├─ SidebarProvider (ui/sidebar)
  └─ ChangePassword                               ├─ AppSidebar (NAV_ITEMS eksporti)
                                                  │    ├─ Main (rolga qarab bandlar)
                                                  │    └─ User (avatar + logout)
                                                  └─ NotFound / ErrorComponent

Tashqi bog'liqliklar: @/client (UsersService, ClientsService, OrdersService, TerminalService, TerminalDevicesService va
User*/Client*/Order*/Post* model turlari), @/queries/mes (getClients/getMachines/getPosts/
getOrderMatrixQueryOptions/getOrderQueryOptions va h.k.; PAGE_SIZE, crudCallbacks),
@/queries/users (getUsersQueryOptions — barcha sahifalarni bitta ro'yxatga yig'adi, `employees.tsx`;
getCurrentUserQueryOptions — `useCurrentUser` va `tablo.tsx` shundan foydalanadi), @/lib/mes (ROLE_LABELS, PRIORITY_LABELS,
PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES, POST_COLORS,
ORDER_STATUS_LABELS/COLORS, chipColors/mixTint, isCut, PROCESS_OPS (16 amal kodi →
nom+post; OperationChips va CustomRoutes ishlatadi), TAIL_CODES (15/16 — tizim
qo'shadigan dum; CustomRoutes uni ham tugmalardan, ham saqlangan marshrutdan
chiqarib tashlaydi, OrderMatrix esa `routeStepNames` zanjiridan),
STANDARD_MATRIX_POSTS,
ROUTE_START_POSTS, isAdmin/isSuperuser/isManagement/isProductionStaff,
MACHINE_BOUND_ROLES, TERMINAL_STATUSES, formatSize),
@/hooks (useAuth, useCurrentUser, useMobile, useDebounced, useScanFlash), sonner (toast),
@/lib/validation (zod schema'lar, formatMoneyInput, formatUzPhone), @/lib/utils (cn),
@/lib/anketa (variant kataloglari, labelOf/labelsOf), @/lib/scxDir (papka + scxFileUrl),
@/utils (handleError, getInitials).
```

2026-09-04 (terminal atamalar tozalovi, 1–4-qadam ekranlari): legendalar bir tartib va bir so'z — kulrang → sariq → «✓ bajarildi» (`KromkaView` «qilingan / tomon · ✓ bajarildi», `PrisadkaView` SCX jadvali «kulrang — chek yo'q · sariq — chek chiqqan, skan kutilmoqda · ✓ bajarildi», ilgari «✓ tugadi · … 1/2 = skan»); texnolog ishi bo'lgan xabarlar ishchiga buyruq bermaydi (`CutmapView` xarita yo'q — «Texnologga ayting», «(TEMPLATE)» va mavjud bo'lmagan «oddiy vazifalar ro'yxati» ketdi; `PartCard` ro'yxatsiz qoldiq — «texnolog project faylni qayta yuklashi kerak»); `PrisadkaView` SCX papkasi ochilmasa saqlangan handle tozalanadi (`scxDir.clearSavedDir`) — keyingi bosishda tanlash dialogi qayta ochiladi (toast o'chirilgan «Papka tugmasi»ga yo'llardi); `PostQueueView.LABELS` dan o'lik `ready` ketdi.
