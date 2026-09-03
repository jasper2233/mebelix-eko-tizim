# Frontend Components (Clients, Common, Orders, Anketa, People, Sidebar, Terminal, UserSettings, ui)

Ushbu hujjat `frontend/src/components/` katalogidagi React komponentlarini va ularni yig'adigan anketa sahifasini (`routes/_layout/anketa.$orderId.tsx`) qamrab oladi. Stack: React + TypeScript, TanStack Router/Query, react-hook-form + zod, shadcn/ui (Radix UI + Tailwind CSS 4). Barcha komponentlar backend bilan avtomatik generatsiya qilingan `@/client` (UsersService, ClientsService, OrdersService, TerminalService va model turlari) orqali gaplashadi — chaqiruv shakli `@hey-api/client-axios` niki: argumentlar `{ path, query, body }` guruhlarida beriladi va path/query kalitlari backend'dagi XOM snake_case nomlar (`path: { user_id }`, `query: { employee_id }`), natija esa `AxiosResponse`, ya'ni foydali yuk `.data` da (`onSuccess: ({ data: client }) => ...`, `queryFn: async () => (await ...).data`); umumiy query'lar `@/queries/mes` dagi `queryOptions` fabrikalarida (getClients/getMachines/getPosts/getOrderMatrixQueryOptions va h.k.), domen konstantalari `@/lib/mes` da (yorliq/rang map'lari `satisfies` bilan generatsiya qilingan enumlarga bog'langan — yorliqsiz yangi backend qiymati build'ni yiqitadi: ROLE_LABELS, PRIORITY_LABELS, PRIORITY_DOT_CLASSES/PRIORITY_TEXT_CLASSES/PRIORITY_BADGE_CLASSES — prioritet ranglari yagona manbadan, POST_COLORS, ORDER_STATUS_LABELS/COLORS, chipColors/mixTint — chip rang formulasi, isCut, formatSize), buyurtma anketasi variantlari `@/lib/anketa` da; toast xabarlari to'g'ridan-to'g'ri sonner `toast.success/error` (`useCustomToast` hooki o'chirilgan), xatoliklar `handleError` utiliti orqali (`onError: handleError` — curry emas; imzosi `(err: unknown)`, chunki bu klient har qanday xatoni `AxiosError` qilib tashlaydi — eski `ApiError` klassi yo'q, server tanasi `err.response.data.detail` da); takrorlanuvchi toast+xato+invalidatsiya triosi `@/queries/mes` dagi `crudCallbacks()` da.

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
  `ofis` (4 ta, har biri `UserRole` ga ko'rsatadi), `boshqa` (nomi qo'lda — haydovchi,
  farrosh; post ham, hisob ham berilmaydi). Ko'rinadigan nom `ROLE_LABELS[role]` dan
  keladi, shuning uchun dialog va Hodimlar jadvalining "Lavozim" ustuni bir so'zni aytadi.
- **Hodim yozuvi hisobdan OLDIN yaratiladi**, hisob keyin ochilib
  `updateEmployee({user_id})` bilan bog'lanadi (`login._open_shift_for` aynan shu bog'lamdan
  hodimni topadi). Rol lavozim jadvalidan keladi (`POSITIONS[].role` — backend `POST_ROLES`
  bilan bir xil). Ikki so'rov bitta tranzaksiya EMAS: hodim yozuvi tushmasa hisob umuman
  ochilmaydi. Ilgari hisob avval ochilib, hodim tushmasa YETIM qolardi (tsex roli Hodimlar
  ro'yxatida yashiriladi — `employees.tsx`: `isDeviceAccount(u) || linked.has(...)`, qayta
  urinish `crud_users.exists(phone)` da 409 ga urilardi); kompensatsion `deleteUser` esa
  yaramasdi — post rolli hisobni `delete_user` guard'i 403 bilan qaytaradi.
- **Post lavozimdan keladi**: "Arrachi" tanlansa ARRA belgilanadi. Dialog OCHILGANDA ham
  hisoblanadi (`postsFor`), faqat almashtirilganda emas — ilgari admin tayyor turgan
  lavozimga tegmasdan saqlasa POSTSIZ hodim yaratilardi va uning beyjigi ishlamasdi.
  Dialogda post tanlagichi YO'Q: katalog lavozimi ko'pi bilan BITTA post beradi, faqat
  katalogda yo'q lavozim ("Boshqa") mavjud postlarni saqlaydi. Bir odamni ikki postga
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

- zod: `full_name` (min 2 belgi), `phone`/`phone_alt` (`optionalFormattedPhoneSchema`), `address` (ko'pi bilan 255 belgi — backend ustuni `String(255)`; maydonda `maxLength={255}` va `FormMessage` bor, aks holda uzun manzilda submit sababsiz jim bloklanardi), `notes` (cheklovsiz — backend `Text`); telefon inputlari yozish paytida `formatUzPhone` bilan "+998 90 123-45-67" ko'rinishida maskalanadi (placeholder esa "+998 90 123 45 67"); submitda `optionalFormattedPhoneSchema` probel/chiziqchalarni olib tashlab kanonik `+998901234567` ga o'tkazadi.
- Props: `trigger?` (default "+ Yangi mijoz" tugmasi o'rniga istalgan React node), `onCreated?(client)`, `client?` va `onClose?`. `Clients/ClientCombobox` popover footeri birinchi ikkitasidan foydalanib mijozni inline yaratadi va combobox'da avtomatik tanlaydi.
- **Bu ayni paytda TAHRIRLASH dialogi ham:** `client` propi berilsa forma boshqariladigan rejimda ochiladi (`ochiq = true`, yopilishi `onClose` orqali). Ikkinchi nusxa yozilmagan, chunki maydonlar va tekshiruvlar aynan bir xil — nusxa bo'lsa telefon formati bir joyda o'zgarib, ikkinchisida qolardi.
- Mutation: `client` berilmasa `ClientsService.createClient`, berilsa `ClientsService.updateClient` (`crudCallbacks` triosi — toast "Mijoz qo'shildi"/"Mijoz yangilandi" + xato + `["clients"]` invalidatsiyasi); muvaffaqiyatda reset, dialog yopiladi va FAQAT yaratishda `onCreated?.(client)` chaqiriladi. Yaratish rejimida dialog YOPILGANDA ham `form.reset()` bo'ladi — komponent unmount bo'lmagani uchun (faqat `DialogContent` ketadi) tashlab ketilgan qoralama va `onBlur` xatolari qayta ochilganda ko'rinib qolardi.

- Trigger tugmasi `Plus` ikonkasi bilan («+ Yangi mijoz» matni emas — «Yangi buyurtma» bilan bir xil); telefon placeholder'i formatter chiqishi bilan bir xil (`+998 90 123-45-67`).

### `frontend/src/components/Clients/ClientCard.tsx`

**Maqsadi:** mijoz kartochkasi — reyestrda qator ustiga bosilganda ochiladi (`clientId` berilsa `Dialog`, `sm:max-w-4xl`). Reyestrdagi savol "bu mijoz kim" emas, "bu mijoz nima buyurtma qilgan", shuning uchun asosiy joyni buyurtmalar jadvali egallaydi.

- Ma'lumot: `ClientsService.readClientDetail` (`["clients", "detail", clientId]`, `enabled: clientId !== null`); yuklanayotganda `Skeleton`.
- Sarlavhada ism + `Clients/ClientSegment`, tavsifda `N buyurtma · summa · aylanmaning X%`. Tepada kontakt qatori (telefon, qo'shimcha telefon, manzil, qo'shilgan sana, izoh) — ichki `Maydon` yordamchisi bilan.
- Pastda buyurtmalar jadvali (`ui/table`): raqam `Link to="/orders/$orderId"` (kartochka yakuniy manzil emas, o'tish joyi), `Common/StatusBadge`, prioritet, muddat, summa; bo'sh bo'lsa `Common/EmptyRow`.

- Buyurtmalar jadvali reestr bilan bir tilda: prioritet `PRIORITY_TEXT_CLASSES` rangida, muddat faol buyurtmada `deadlineTone` (o'tgan — qizil, bugun — amber), yangi **Qoldiq** ustuni (`remainingPayment`; ≤0 — «To'langan»); sarlavha tavsifida **qarz** — bekor qilinmagan buyurtmalar qoldiqlari yig'indisi (`ClientOrderRow.advance_payment` dan; «bizga qarzi bormi?» — kartochkadagi asosiy savol). Telefonlar `formatUzPhone` bilan.

### `frontend/src/components/Clients/ClientCombobox.tsx`

**Maqsadi:** server-qidiruvli mijoz tanlagich — ro'yxat backend `?search=` bilan filtrlanadi, mijozlar soni mingga yetsa ham ishlaydi.

- Qidiruv 300ms debounce (`useDebounced` hooki) bilan `getClientsQueryOptions(search)` ga uzatiladi (`enabled: open`); ArrowUp/ArrowDown/Enter klaviatura navigatsiyasi.
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

### Dialog kengligi qoidasi

`DialogContent` sukut bo'yicha `sm:max-w-lg` (512px). Ikki ustunli formalar (`grid-cols-2`) uni `sm:max-w-xl` (576px) qiladi: `sm:max-w-md` (448px) da ustun 194px bo'lib qolardi, eng uzun yorliq esa 166px (`Boshlang'ich to'lov (so'm)`, brauzerda o'lchangan) — maydon bilan yorliq bir-biriga tiqilardi. 576px da ustun 258px. Bu formalar: `Orders/AddOrder`, `Orders/EditOrder`, `Clients/AddClient`. Bitta ustunli qisqa dialoglar (`ConfirmDialog`, `PersonDialog`, `AddAgent`) `md` da qoladi — kenglik MAZMUNGA qarab tanlanadi, umumiy cheklov emas.

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

**Foydalanuvchilari:** `Anketa/RoomPhotos.tsx` (rasm o'chirish), `Clients/DeleteClient.tsx` (mijozni o'chirish), `People/PersonDialog.tsx` (lavozim turi o'zgarganda qarama-qarshi yozuv o'chirilishi), `routes/_layout/orders/$orderId.tsx`, `routes/_layout/anketa.$orderId.tsx` (xona o'chirish), `routes/_layout/employees.tsx`, `routes/_layout/work-centers.tsx` (ish markazini o'chirish), `routes/_layout/agents.tsx` (ish markazi bog'lash/uzish, chek chiqarish `can_print` switch'i, agentga yangi kod berish va agentni bekor qilish — to'rtta dialog), `routes/terminal.tsx`.

### `frontend/src/components/Common/EmptyRow.tsx`

**Maqsadi:** jadvalning bo'sh holati qatori (`colSpan` + markazlangan muted xabar — "topilmadi / hali yo'q") — har reyestrda qo'lda takrorlanadigan `TableRow`+`TableCell` naqshi bitta joyda. 8 faylda, 10 joyda ishlatiladi (clients, employees, logs, orders ro'yxati, printers, reports — uch marta, work-centers va `Clients/ClientCard`).

### `frontend/src/components/Common/Field.tsx`

Dialog maydoni yorlig'i — `useState` bilan yozilgan formalar uchun (`People/PersonDialog`, `employees.tsx` dagi `BadgeDialog`, `work-centers`). Maydon `<label>` ICHIDA turadi, ya'ni yorliqni bosish fokus beradi. react-hook-form ishlatiladigan joyda `ui/form` dagi `FormField`/`FormLabel` qoladi.

### `frontend/src/components/Common/RowAction.tsx`

Jadval qatoridagi amal tugmasi: `icon`/`title`/`onClick`, buzuvchi amalga `danger`. O'lcham bitta (`size="icon"` + `size-8`), `danger` odatda kulrang va faqat hoverda qizil. `aria-label` `title` dan olinadi.

### `frontend/src/components/Common/TablePagination.tsx`

Reyestr sahifalagichi: `page` (0 dan), `pageSize`, `total`, `onPage`. Tartib bitta — butun blok o'ngga tekislangan (`justify-end`): avval "N tadan X–Y", keyin `[Oldingi] [k / n] [Keyingi]`. `total === 0` da `null` qaytaradi. Hozircha yagona chaqiruvchi — `logs` (PAGE=50); sahifa hajmi baribir prop bo'lib qoladi, chunki u qator balandligiga bog'liq va har reyestrda boshqacha bo'lishi mumkin.

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

- Props: `processCode: number | null | undefined` va `postCode: string | null | undefined`. Kod endi detal NOMIDAN o'qilmaydi — nomdagi `{kodlar}` sintaksisi butunlay olib tashlangan; `process_code` marshrut qadamining o'zida saqlanadi va backend uni `KromkaPartRow` va `PostQueueRow` da beradi.
- `PROCESS_OPS` (`@/lib/mes` dan import — 16 kod (1–16), backend `PROCESS_POSTS` bilan bir xil bo'lishi shart) kodni amal nomi + postga o'giradi. Chip chizilmaydi, agar: kod noma'lum bo'lsa (xato nom emas, hech nima), kod boshqa postga tegishli bo'lsa yoki post bitta amalli bo'lsa (prisadka, rover, oval, bo'yoq — post nomi ekran sarlavhasida turibdi). Ya'ni chip faqat ARRA, KROMKA va STOLYARKA da ko'rinadi.
- Ishlatilish joylari: `Terminal/KromkaView` (`postCode={oval ? "OVAL" : "KROMKA"}`) va `Terminal/PostQueueView` (`postCode={data?.post_code}`).

### `frontend/src/components/Common/PageHeader.tsx`

**Maqsadi:** sahifa sarlavhasi — `title`, ixtiyoriy `description` va o'ng tomonda `actions` slot. Barcha `_layout` sahifalarida ishlatiladi (dashboard, orders ro'yxati va sahifasi, clients, employees, work-centers, reports, logs, printers, anketa, settings — 11 ta sahifa; `admin.tsx` sanoqqa kirmaydi — u endi redirect, chizadigan sarlavhasi yo'q); yagona istisno — `cutmap.$orderId.tsx`, unda sarlavha umuman yo'q (to'liq ekran).

- `description` `div` ichida (`<p>` emas) — `ReactNode` qabul qiladi, `<p>` ichida blok element HTML'da noto'g'ri bo'lardi.

- `titleAside?: ReactNode` — sarlavha bilan BIR QATORDA (`flex-wrap`, tor ekranda pastga buqiladi): buyurtma sahifasi holat/prioritet badge'lari va bosqichlar zanjirini beradi — alohida qator o'rniga.

### `frontend/src/components/Common/PostBadge.tsx`

**Maqsadi:** bosqich (post) kodi chipi (ARRA, KROMKA, ...) — `POST_COLORS` + `chipColors(color, 12)` (`@/lib/mes`) asosida: matn post rangining to'qroq variantida (`78%, black` — WCAG AA kontrasti, sof rang tint fonda o'tmasdi), fon 12% oq tint. Avval `employees.tsx` va `work-centers.tsx` da qo'lda takrorlangan edi.

### `frontend/src/components/Common/QueryError.tsx`

**Maqsadi:** so'rov yiqilganda ko'rsatiladigan `role="alert"` bloki — xato matni + ixtiyoriy "Qayta urinish" tugmasi (`onRetry`). Busiz sahifalar xato holatida abadiy skeletonda qotib qolardi.

### `frontend/src/components/Common/SearchInput.tsx`

**Maqsadi:** ichida `Search` ikonkasi bo'lgan qidiruv maydoni (`value`/`onChange`/`placeholder`/`className`) — reyestr sahifalarida (clients, employees, orders ro'yxati, logs) qo'lda takrorlanadigan `relative` div + absolyut ikonka + `pl-8` Input naqshi bitta joyda; kenglik/joylashuv `className` orqali chaqiruvchidan.

### `frontend/src/components/Common/SelectField.tsx`

**Maqsadi:** dialoglardagi tanlov maydoni. **Xom `<select>` ISHLATILMAYDI** — u ochilganda BRAUZERNING o'z ro'yxatini chizadi, uni CSS bilan o'zgartirib bo'lmaydi, ya'ni balandligi/burchagi/shrifti/fokus halqasi yonidagi `Input` va `Button` bilan mos kelmaydi va bitta shunday maydon butun formani "tayyor shablon" qilib ko'rsatadi. Radix `Select` ni har dialogda beshta komponent bilan yozish o'rniga shu o'ram: tanlov maydonining shakli BIR joyda.

- Props: `value`/`onChange`, `options: SelectOption[]` (`{ value, label, hint? }` — `hint` kod/telefon kabi ikkinchi darajali matn), `placeholder?`, `emptyLabel?`, `disabled?`, `className?`. `emptyLabel` — "tanlanmagan" varianti: Radix bo'sh `""` qiymatni qabul qilmaydi, shuning uchun ichki `EMPTY = "__empty__"` sentineli bilan ifodalanadi va tashqariga `""` qaytadi.
- **Qoida biome bilan mahkamlangan**: `correctness/noRestrictedElements` `<select>` va `<textarea>` ni taqiqlaydi va nima ishlatish kerakligini xato matnida aytadi. `src/components/ui/**` biome tekshiruvidan chiqarilgan, ya'ni shadcn primitivlarining o'zi bu qoidaga tushmaydi.
- Chaqiruvchilari: `Orders/CustomRoutes.tsx`, `Orders/MachineAssign.tsx`, `People/PersonDialog.tsx`, `routes/_layout/work-centers.tsx`.

### `frontend/src/components/Common/SectionTitle.tsx`

**Maqsadi:** sahifa ichidagi bo'lim sarlavhasi (`h2`, uppercase muted) — ierarxiya: `PageHeader` (h1) > `SectionTitle` (h2) > panel sarlavhalari (h3); avval bir daraja to'rt xil yozilgan edi.

### `frontend/src/components/Common/StagePipeline.tsx`

**Maqsadi:** ishlab chiqarish pipeline'i — ulangan progress kataklar zanjiri, loyihaning "signature" vizual elementi. Kataklar data-driven (`stages` propidan), hozir bazada 9 post (PAZ olib tashlangan; BOYOQ, UPAKOVKA va TMO qo'shilgan) — `POST_COLORS` da ham shu to'qqiz kalit.

- Props: yagona `stages: StageCell[]` (`{ code, done, total }`); har katak (`h-6 w-12`) `POST_COLORS[code]` rangida (`mixTint` fon + foizli progress chizig'i), ichida `done/total` (`--foreground` rangda — post rangi o'z tinti ustida AA dan o'tmasdi), tugallanganda "✓"; kataklar orasida ulovchi chiziqcha, `title` da `KOD: done/total (N%)`.
- Dashboard'da (`routes/_layout/index.tsx`) ishlatiladi; xuddi shu vizual grammatika `Orders/OrderMatrix` va TABLO ekranida takrorlanadi.

- `showLabels` — katak ostida post kodi (buyurtma sahifasida jadval ustunisiz turganda rangning o'zi bosqichni aytmaydi); dashboard jadvalida yo'q.

### `frontend/src/components/Common/StatusBadge.tsx`

**Maqsadi:** buyurtma holati pill'i — `ORDER_STATUS_LABELS`/`ORDER_STATUS_COLORS` (`@/lib/mes`) asosida rangli nuqta + matn. Besh chaqiruvchi: dashboard, buyurtmalar ro'yxati, buyurtma sahifasi, hisobotlar va `Clients/ClientCard` dagi buyurtmalar jadvali.

---

## Orders komponentlari — `frontend/src/components/Orders/`

Buyurtma sahifalari (`/orders`, `/orders/$orderId`) uchun dialog va jadval komponentlari.

### `frontend/src/components/Orders/orderForm.tsx`

**Maqsadi:** AddOrder va EditOrder uchun umumiy forma manbasi — ikkala dialog bitta backend kontraktiga tegadi, shuning uchun schema, payload va maydonlar bir joyda.

- Eksportlar: `formSchema` (zod: `client_id` majburiy, `deadline?`, `priority` enum low/medium/high/urgent, `amount` majburiy, `advance_payment?`, `notes?`; `.refine()` — boshlang'ich to'lov umumiy narxdan oshmasligi kerak), `FormValues`, `toRequestBody(data)` va `OrderFields({ control, notesPlaceholder? })`.
- `toRequestBody` — create va update bir xil payload kutadi: `client_id` `Number` ga, pul maydonlaridan probellar olib tashlanadi, bo'shlari `null`.
- `OrderFields` — ikkala dialogdagi bir xil maydonlar: topshirish sanasi (`ui/date-picker` DatePicker), prioritet `Select` (`PRIORITY_LABELS` yorliqlari, bandlarida `PRIORITY_DOT_CLASSES` rangli nuqtalar), umumiy narx va boshlang'ich to'lov (`formatMoneyInput` bilan ming ajratkichli) hamda izoh (`notesPlaceholder` propi bilan — faqat placeholder dialogga qarab farq qiladi). Mijoz maydoni dialoglarda qoladi: EditOrder'da `initialLabel` va `disabled` kerak.

### `frontend/src/components/Orders/AddOrder.tsx`

**Maqsadi:** yangi buyurtma dialogi ("+ Yangi buyurtma") — raqamni tizim beradi (B-YYYY-NNN), fayl keyin texnolog tomonidan yuklanadi.

- Forma `orderForm.tsx` dan: `formSchema` + `OrderFields` + `toRequestBody`; default `priority: "medium"`, qolgan maydonlar bo'sh.
- Mijoz maydoni — `Clients/ClientCombobox` (server-side qidiruvli; yangi mijoz combobox popover footeridagi inline `AddClient` orqali qo'shiladi); izoh `OrderFields` dan keladi, `notesPlaceholder="Maxsus talablar (masalan, qora kromka)"` bilan.
- Mutation: `OrdersService.createOrder`; muvaffaqiyatda toast va yangi buyurtma sahifasiga `navigate`.
- Dialog yopilganda (`onOpenChange`) forma `reset()` qilinadi. Busiz: mijoz tanlab dialog Escape/X bilan yopilsa `client_id` formada qolar, combobox esa unmount bo'lib qayta ochilganda "Mijozni tanlang" ko'rsatardi — menejer bo'sh ko'ringan formadan ko'rinmas mijozga buyurtma yaratardi.

### `frontend/src/components/Orders/EditOrder.tsx`

**Maqsadi:** buyurtmani tahrirlash dialogi (manager) — AddOrder bilan umumiy `orderForm.tsx` (schema, maydonlar, payload), qiymatlar `values:` orqali `order` dan olinadi (pul maydonlari `moneyToInput` bilan — u API'ning `"14000000.00"` Decimal-satridan avval kasr qismini kesib tashlaydi, keyin `formatMoneyInput` ni chaqiradi; to'g'ridan-to'g'ri `formatMoneyInput` nuqtani o'chirib summani 100 barobar oshirib yuborardi).

- Mijoz maydoni — `ClientCombobox` (`initialLabel={order.client_name}`, `disabled={!isDraft}`) — DRAFT dan keyin mijoz almashtirilmaydi ("faqat qoralamada almashtiriladi"; backend ham shu qoidani ushlaydi).
- Mutation: `OrdersService.updateOrder` (`crudCallbacks(queryClient, ["orders"], …)`); muvaffaqiyatda toast + dialog yopiladi. `onSaved` propi YO'Q: `["orders"]` prefiksi `["orders", id]` va `["orders", id, "matrix"]` ni ham qamraydi, chaqiruvchidagi ikkinchi invalidatsiya har saqlashda ortiqcha so'rov berardi.

### `frontend/src/components/Orders/MachineAssign.tsx`

**Maqsadi:** ish markazi tanlovi paneli — `requires_assignment_choice` bo'lgan postlar uchun stanokni odam aniq tanlaydi. Panelni manager ham, texnolog ham ko'radi (`orders/$orderId.tsx`: `(canManage || isTexnolog) && canEdit && order.project_uuid`) — marshrutni texnolog chizadi, ya'ni qaysi stanok qaysi ishni bajarishini yaxshiroq biladi.

- Bitta IXCHAM QATOR (karta emas — bitta select uchun sarlavhali karta sahifada og'ir turardi): «Ish markazi:» + har post uchun `POST_COLORS` rangli kod + faol ish markazlari selecti (`h-8 w-56`; `getPostsQueryOptions` + `getMachinesQueryOptions`) + `size="sm"` «Biriktirish». Faqat HAQIQIY tanlovda ko'rinadi — postda 2+ aktiv stanok bo'lsa (`withChoice`); bittasi bo'lsa qator yo'q, backend ishlab chiqarishga uzatishda o'zi biriktiradi (`start_production`) — bitta variantli select odamga ortiqcha majburiy qadam edi; `OrdersService.assignOrderMachines` ga saqlanadi (`crudCallbacks(queryClient, ["orders"], …)` — `onSaved` propi yo'q); tanlov talab qiluvchi post bo'lmasa `null` qaytaradi.
- Selectda `emptyLabel="Biriktirilmagan"` varianti bor — biriktirishni BEKOR qilish mumkin (bo'sh qiymatlar payload'dan tushadi, server esa `machine_assignments` dict'ini butunlay almashtiradi). "Biriktirish" tugmasi faqat tanlov boshlang'ich holatdan farq qilganda faol: aks holda bo'sh formada bosib hamma biriktirishni tasodifan o'chirib yuborish mumkin edi.

### `frontend/src/components/Orders/PartMapDialog.tsx`

**Maqsadi:** detalning kesish xaritasini SHU SAHIFADA ko'rish — `PartMapButton({ orderId, partKey })`: matritsa qatoridagi va nostandart kartochkasidagi xarita ikonkasi. Bosilganda katta dialog (`sm:max-w-[min(1400px,96vw)]`, `h-[88vh]`) ochilib ichida haqiqiy `Terminal/CutmapView` (`admin`, `focusPartKey=partKey` — detalning listi ochiladi, katagi belgilanadi; zoom/pan, listlar orasida o'tish ishlaydi) chiziladi; sarlavhada «To'liq sahifada» havolasi (`/cutmap/$orderId?part=`). Esc/tashqariga bosish yopadi; `onBack` (xarita yo'q — TEMPLATE) ham yopadi. Faqat ochiqda render — yopiqda xarita so'rovi ketmaydi (query keshi `["admin","cutmap",id]` — sahifa bilan umumiy).

- Nega dialog, «bosib turish» emas: ushlab turgan holda zoom/surish yo'q, jest taxmin qilinmaydi, sensorda kontekst-menyu/matn tanlashni chaqiradi. Nega sahifaga o'tish emas: texnolog marshrut chizayotganda «bu detal qayerda» deb qaraydi — dialog tahrir holatiga (`stageEdits`, `draft`) tegmaydi, orqaga qaytish yo'q.

### `frontend/src/components/Orders/OrderMatrix.tsx`

**Maqsadi:** texnolog matritsasi — qatorlar: detallar, ustunlar: STANDART detalning postlari, ya'ni `getPostsQueryOptions` ro'yxati `STANDARD_MATRIX_POSTS` (`@/lib/mes` — ARRA, KROMKA, PRISADKA) bo'yicha filtrlanadi. Rover/stolyarka/bo'yoq/oval ustunlari olib tashlangan: fayldan avtomatik marshrut faqat shu uch postni beradi (roverdan chiqqan detal keyin bo'yalishi mumkinligini fayl bilmaydi), qolgani hech qachon to'lmaydigan bo'sh ustun bo'lib turardi — ular endi "Nostandart detallar" tabida qo'lda chiziladi.

- O'qish rejimida har katak `total_done/total_required` progress (`POST_COLORS`, tugallanganda "✓"), o'chirilgan bosqich "—". Bitta post marshrutda BIR NECHA MARTA kelishi mumkin (kromka → prisadka → yana kromka), shuning uchun katak shu postdagi barcha qadamlarning yig'indisini ko'rsatadi.
- `editable` bo'lsa "Marshrutni tahrirlash" rejimi: bosqich checkboxlari + izoh inputlari + "Nostandart" katakchasi, hammasi bitta `OrdersService.editOrderMatrix` batchida saqlanadi (`crudCallbacks`). Checkbox locked bo'ladi ikki holatda: ARRA (standart detalda majburiy) va detal nostandart bo'lsa (uning marshruti bu yerda emas, alohida tabda chiziladi).
- **"Nostandart" ustuni** (post ustunlaridan keyin): o'qish rejimida amber "✓" yoki "—", tahrirlashda `Checkbox` → `MatrixPartEdit.is_custom`. Belgilangan detal fayldan avtomatik marshrut olmaydi (mavjud avtomatik qadamlar yumshoq o'chadi, bayroq qaytarilsa aynan tiklanadi), marshrutini texnolog `Orders/CustomRoutes` da chizadi. Katakcha almashtirilganda shu detalning KUTAYOTGAN bosqich tanlovlari `stageEdits` dan olib tashlanadi: katakchalar qulflanishi faqat keyingi bosishlarni to'xtatadi, oldin belgilanganlari esa o'sha batchda `is_custom` bilan birga ketib, backend endigina qayta qurgan marshrutga tegib ketardi.
- Boshqaruv qatorida detal qidiruvi ("Qidirish: kod yoki nom...") va `N / M detal` hisobi; jadval balandligi 70vh bilan chegaralangan, sarlavha sticky.
- Har detal kodi yonida Map-ikonka — `/cutmap/$orderId?part=...` havolasi: kesish xaritasida detalning listi ochilib katagi belgilanadi (`CutmapView` `focusPartKey` oqimi).
- Nom ostida ALOHIDA «Nostandart» belgisi YO'Q (u qatorni cho'zardi va ustun bilan takror edi). **«Nostandart» ustuni o'qish rejimida marshrutning O'ZINI ko'rsatadi** — BITTA satr «Raspil → Kromka → G petlya o'ngdan» (`routeStepNames`, `lib/mes`: `is_enabled` va dumsiz, `seq` bo'yicha jarayon NOMLARI; `truncate`, to'lig'i `title` da), nostandart-u marshruti hali chizilmaganida amber «marshrut yo'q» (`title` da tushuntirish), standart detalda «—»; ilgari «✓» turardi va u hech narsa demasdi (oraliq variant — raqamlangan chiplar — tor ustunda har biri alohida qatorga tushib qatorni cho'zardi). Tahrir rejimida o'sha ustun — `Checkbox`.
- Qidiruv — `Common/SearchInput` (lupa ikonkasi bilan, reestr bilan bir xil; oddiy `Input` topilishi qiyin edi). To'liq chek/QR satri ham qabul qilinadi: `B-2026-047_301401_01_001_2` dan buyurtma prefiksi (`^B-YYYY-NNN_`) va `_n` nusxa raqami (faqat 3 xonali detal kodidan keyin) tashlanadi → `301401_01_001` qatori topiladi. Qator = DETAL, nusxa emas — shuning uchun jadvalda ID prefiks va `_n` siz (`{product_code}_{code}`, docs/11 dagi «Kod» ustuni qoidasi bilan bir xil); to'liq serial nusxalarda — chek, skan, SCX, xarita kartochkasi. «Nostandart» ustun sarlavhasi tugma: bosilganda nostandart detallar YUQORIGA (`customFirst`, `aria-sort`, faol `ArrowUp`, nofaol xira `ChevronsUpDown`).
- `toolbarContainer?: HTMLElement | null` — boshqaruv qatori (qidiruv + hisob + «Marshrutni tahrirlash»/Saqlash) `createPortal` bilan shu elementga chiqadi; buyurtma sahifasi tab'lar qatorining o'ng tomonini beradi (`empty:hidden` slot), jadval ustida alohida qator qolmaydi. Berilmasa (manager/direktor — tab'siz ko'rinish) jadval ustida o'z qatorida.
- Izoh inputi CONTROLLED (`value={noteEdits[part.id] ?? part.note ?? ""}`): qidiruv filtri qatorni unmount qilib qaytarganda `defaultValue` bilan kiritilgan matn ekrandan yo'qolib, `noteEdits` da qolib ketardi — texnolog server izohini ko'rib turib, saqlash o'sha ko'rinmas matnni yozardi.
- Ma'lumot: `getOrderMatrixQueryOptions(orderId)`; o'lchamlar `formatSize` (`@/lib/mes`) bilan. So'rov yiqilsa Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`) — ilgari xato bo'sh holatga tushib, texnolog "Detallar yo'q — avval .project fayl yuklanishi kerak" degan yolg'on sababni o'qirdi.

- Soni 0 detal (GibLab faylida shunday keladi, prod bazasida 2 ta): soni xira, bosqich kataklari «—» — ilgari 0/0 «✓» bo'lib «tayyor» degan yolg'on taassurot berardi.

### `frontend/src/components/Orders/CustomRoutes.tsx`

**Maqsadi:** "Nostandart detallar" tabi — matritsada `is_custom` deb belgilangan detallarning marshrutini texnolog QO'LDA chizadi. Fayl bunday detalning yo'lini bilmaydi (nomdagi `{kodlar}` sintaksisi olib tashlangan, marshrut endi detal nomiga umuman bog'liq emas), shuning uchun yagona manba — texnologning shu ekrandagi tanlovi.

- Props: `{ orderId: number; editable: boolean }`. Ma'lumot — `OrderMatrix` bilan AYNAN bitta query (`getOrderMatrixQueryOptions(orderId)`, TanStack dedupe qiladi), `parts.filter(p => p.is_custom)`; nostandart detal bo'lmasa tushuntirish matni chiqadi ("Detallar matritsasida 'Nostandart' ustunidan belgilang"). So'rov xatosida (`isError`) bo'sh holat emas, `Common/QueryError` chiziladi — aks holda 500 "nostandart detal yo'q" bo'lib ko'rinardi.
- Kartochka sarlavhasining o'ngida marshrut XULOSASI — bitta satr, nomlar bilan: «Raspil → Kromka → G petlya o'ngdan» (`PROCESS_OPS`; Arra/Rover'dan boshlanmasa qizil; `truncate`, to'lig'i `title` da) — ilgari `1 / 3 / 11` kodlar edi. Tartibning o'zi TUGMALARDA: tanlangan tugma POST RANGIDA (`chipColors(POST_COLORS[post], 22)` — matritsa chiplari bilan bir til: ARRA apelsin, KROMKA ko'k-yashil, PRISADKA binafsha…; ilgari `primary` navy — tizim rang tiliga yot edi) va ichida qadam raqami + jarayon nomi + post kodi («1 Raspil ARRA») — «nechanchi bo'lib qaysi postga» tugmaning o'zida, ilgari post faqat `title`da edi. Kartochka sarlavhasida matritsadagi kabi xarita tugmasi (`PartMapButton` — shu sahifada dialog, qarang `Orders/PartMapDialog.tsx`). Tugmalar o'qish rejimida ham turadi (o'chirilgan) — texnolog shu ko'rinishga o'rgangan; ko'rsatma matni va biriktirish selecti (biriktirilmagan bo'lsa) faqat `editable` da. Kartochka `bg-card` — sahifa fonidan ajralib tursin.
- Har detal kartochkasida `PROCESS_OPS` ning 16 kodidan marshrut DUMI — `TAIL_CODES` (`@/lib/mes` — UPAKOVKA 15 va TMO 16) chiqarilib, qolgan 14 kodi tugma bo'lib chiziladi (`CODES` konstantasi, `title` da `kod · POST`) — qadoqlashni texnolog tanlamaydi, uni anketadagi "Upakovka qilish" bayrog'iga qarab backend oxirgi qadam qilib o'zi qo'shadi. Tugma bosilsa kod marshrut oxiriga QO'SHILADI va tanlangan tartibda raqamlanadi (1, 2, 3...); bitta jarayonni qayta bosish yangi qadam beradi (kromka → prisadka → yana kromka — shuning uchun tugmada `1,3` kabi bir necha raqam turishi mumkin), OXIRGI qadamni bosish esa uni bekor qiladi. O'ng tomonda joriy marshrut `7 / 11 / 8` ko'rinishida.
- Validatsiya: marshrut bo'sh bo'lmasligi va `ROUTE_START_POSTS` (`@/lib/mes` — ARRA yoki ROVER) dan boshlanishi shart — chek shu birinchi postda chiqadi. Buzilgan detal kartochkasi qizil ramkada, tepada nechta ekani sanaladi, "Saqlash" tugmasi bloklanadi (backend ham marshrutsiz detalni ishlab chiqarishga o'tkazmaydi).
- **Yig'ma buyum:** har nostandart detalni ASOSIY DETALGA biriktirish mumkin — kartochka pastida "Asosiy detalga biriktirish:" `SelectField` i (variantlar: o'zining oxirgi jarayoni bilan bir xil qadamga ega, hali hech kimga biriktirilmagan detallar). Biriktirilsa mayda detalning marshruti shu amalda TUGAYDI — qadoqlash/TMO faqat asosiy detalda. Bolalari bor detalda select o'rniga "Asosiy detal — `01_007 ×2` biriktirilgan" satri chiqadi. Tanlov `parents` state'da (`part_id -> assembly_parent_id`), saqlashda `edits[].assembly_parent_id` bo'lib ketadi (`0` = bog'lamni uzadi, backendga `null` yuboriladi).
- SAQLANGAN marshrutni o'qiyotganda (`codesOf`) dum kodlari filtrlanadi: backend `edits[].route_codes` ga dumni o'zi qo'shadi va uni qaytib qabul qilmaydi (`orders/matrix.py` — "Ruxsat etilgan: 1–14"), ya'ni filtrsiz qayta tahrir 403 berardi. Shu sababli "oxirgi qadam" (biriktirish variantlari filtri va "Marshrut … da tugaydi" matni) ham TMO emas, texnolog chizgan haqiqiy oxirgi amalni ko'rsatadi.
- Tahrirlar `draft` state'da (`part_id -> kodlar massivi`) yig'iladi, faqat tegilgan detallar; saqlash — `OrdersService.editOrderMatrix` (`edits[].route_codes`, `stages: {}`, kerak bo'lsa `assembly_parent_id`; `draft` va `parents` id'lari birlashtiriladi), muvaffaqiyatda ikkala state ham tozalanadi. "Bekor qilish" tugmasi ham ikkalasini birga tozalaydi — `dirty` ikkalasidan hisoblanadi. `editable=false` bo'lsa tugmalar `disabled`, saqlash paneli umuman chizilmaydi (ko'rish rejimi).
- `routes/_layout/orders/$orderId.tsx` da texnolog uchun DOIM ikkinchi tab sifatida turadi ("Nostandart detallar (N)").

---

## Anketa sahifasi — `frontend/src/routes/_layout/anketa.$orderId.tsx`

Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i) sahifasi — ~790 qator. Ilgari UI bo'laklari ham shu faylning o'zida turardi; hozir ular `components/Anketa/` da (`fields.tsx`, `RoomPhotos.tsx`, `RoomSummary.tsx`) — sahifa faqat holat, saqlash va bo'limlar tartibini yuritadi. Variantlar katalogi alohida: `frontend/src/lib/anketa.ts`.

**Ma'lumot oqimi:** `Order.survey` (JSONB) — `OrderSurvey { version, measured_at, measured_by, packaging, delivery, installation, rooms[] }`; xona `SurveyRoom` (materiallar, o'lchamlar, `walls: SurveyWall[]`, `modules: SurveyModule[]`). Saqlash `OrdersService.saveOrderSurvey` (`PUT /orders/{id}/survey`); xona rasmlari JSON'da emas, `OrderFile(kind=DOCUMENT, meta.room_id)` da (`OrdersService.uploadRoomPhoto` / `deleteRoomPhoto`) — shuning uchun avtosaqlash bilan aralashmaydi.

**Sahifa xulq-atvori (`AnketaPage`):**

- Server ma'lumoti **faqat bir marta** state'ga yuklanadi (`loaded` ref) — aks holda saqlashdan keyingi refetch menejer yozayotgan matn ustiga tushardi.
- Avtosaqlash: har tahrirdan 1.5s keyin (`dirty` bo'lsa va `canEdit` bo'lsa) `save.mutate`; `beforeunload` da ogohlantirish, unmount'da fire-and-forget `saveOrderSurvey`.
- `canEdit = isManager(currentUser)` (`@/lib/mes` — superuser yoki `role` `admin`/`manager`) — faqat ular formani ko'radi; qolganlar (texnolog/direktor) `RoomSummary` jamlanmasini ko'radi.
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

### `frontend/src/components/Sidebar/AppSidebar.tsx`

**Maqsadi:** ilovaning asosiy yon paneli — brend, navigatsiya va foydalanuvchi menyusini yig'adi.

- Modul darajasidagi `NAV_ITEMS` ro'yxati (rollar-modullar matritsasi, eksport — `routes/_layout.tsx` mobil sarlavhalari ham shu ro'yxatdan) 9 ta punkt beradi, har bandda `show(user)` predikati. Huquq predikatlari `@/lib/mes` dan — `isProductionStaff` / `isManagement` / `isAdmin`; **route guard'lar ham AYNAN shularni ishlatadi** (`lib/guards.requireAccess`), ya'ni menyuda ko'rinadigan sahifa albatta ochiladi. Bandlar: Boshqaruv paneli `/` va LIVE Tablo `/tablo` — hammaga (`show: => true`; TABLO tsex zalidagi TV ekran); Buyurtmalar `/orders`, Ish markazlari `/work-centers` — `isProductionStaff` (boshqaruv + texnolog); Mijozlar `/clients`, Hodimlar `/employees`, Hisobotlar `/reports` — `isManagement` (admin/manager/direktor); MES agentlar `/agents` (`MonitorCog` ikonkasi — `Printer` EMAS: agent tsex kompyuteri, chek printeri va stanok skaneri ko'prigi; Prisadka agenti umuman chek chiqarmaydi) va Loglar `/logs` (`ScrollText` ikonkasi) — `isAdmin` (superuser yoki `role === "admin"`); Foydalanuvchilar bandi OLIB TASHLANDI — u Hodimlar sahifasiga birlashtirildi (`/admin` endi redirect). **Rolga qarab navigatsiya**.
- Buyurtmalar bandida jonli badge — **TOPSHIRISHGA TAYYOR** buyurtmalar soni (`counts.completed`; yashil, 0 bo'lsa yo'q, hover'da «Topshirishga tayyor — tsex tugatgan buyurtmalar») — inbox belgisi kabi amalga undaydi; ilgari «faol buyurtmalar soni» (57) turardi — hech qanday amalga undamasdi va reestrdagi «Hammasi» bilan chalkashardi: `getOrderStatusCountsQueryOptions()` reyestr sahifasi bilan AYNAN bitta query key'da, ya'ni `/orders` da TanStack dedupe qiladi va sidebar qo'shimcha so'rov qo'shmaydi. Qolgan admin sahifalarida sidebar YAGONA obunachi — `refetchInterval: 30_000` pollni o'zi yuritadi (`queries/mes.ts`, `docs/05` §5 `queries/mes.ts`). `enabled` faqat `/orders` bandi ko'rinadigan rollarda.
- `<Sidebar collapsible="icon">`: yig'ilganda faqat ikonkalar qoladi. Header'da `Link to="/"` — ichida faqat to'liq logo (`/assets/logo/logo-gold.png`, `h-9 w-auto`, `alt="MebeliX — bosh sahifa"`; login ekrani bilan bir xil brend), matn tuguni yo'q. Yig'ilganda BUTUN havola `group-data-[collapsible=icon]:hidden` bilan yashiriladi — brend tab sarlavhasi, favicon va login ekranida qoladi, bosh sahifa havolasi esa menyuning birinchi qatorida ("Boshqaruv paneli"). `SidebarTrigger` yig'ilgan railda `group-data-[collapsible=icon]:mx-auto` bilan markazga tushadi.
- `SidebarContent` → `Main items={items}`; `SidebarFooter` → `User user={currentUser}`.

**Bog'lanishlar:** `@/hooks/useCurrentUser`, `ui/sidebar.tsx`, `Sidebar/Main.tsx`, `Sidebar/User.tsx`. Layout route ichida `SidebarProvider` + `SidebarInset` bilan ishlatiladi.

### `frontend/src/components/Sidebar/Main.tsx`

**Maqsadi:** navigatsiya menyusi ro'yxati.

- Eksport: `type Item = { icon: LucideIcon; title: string; path: string; badge?: number }` va `Main({ items })`; `badge` bo'lsa (0 emas) band yonida `SidebarMenuBadge` chiqadi.
- `useRouterState()` dan `currentPath` olinib faollik aniqlanadi: ildiz (`/`) uchun qat'iy tenglik, qolgan bandlar uchun prefiks moslik (`currentPath === item.path || currentPath.startsWith(item.path + "/")`) — shu tufayli `/orders/123` da ham "Buyurtmalar" yonib turadi; aktiv bandda chapdan 3px oltin chiziq `before:` pseudo-element bilan (`data-[active=true]:before:...w-[3px]...before:bg-sidebar-primary`) va ikonka `text-sidebar-primary` ga o'tadi — inset soya tugmaning rounded burchaklarida qirqilib ko'rinmasdi.
- Har band `SidebarMenuButton tooltip={item.title} asChild` ichida `RouterLink`; mobil rejimda bosilganda `setOpenMobile(false)` bilan panel yopiladi.

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

**Kartochka QOLDIQ uchun ham BITTA**: `PartCard` detalni ham, ro'yxatga olingan qoldiqni ham aynan bir tartibda ko'rsatadi — sarlavhada katta `№` va yonida nom yoki o'lcham (qoldiqda qo'shimcha «QOLDIQ» bayrog'i), sarlavha OSTIDA chek ID si (`qr_text`) va holati (`✓ kesildi` / `✓ chek chiqarilgan`); keyin chizma, QR + ma'lumot, eng pastda to'liq kenglikdagi qizil «Chekni bekor qilish» (`h-14 w-full`) va «Yopish». Ilgari qoldiq alohida shox edi: bekor qilish «Yopish» ustida, ID umuman yo'q, o'lcham sarlavhada — bitta xaritada ikki xil kartochka. Qoldiqda faqat kromka ko'rsatilmaydi (u material, ishlov berilmaydi).

**Nega bitta chek, ro'yxat emas.** `count>1` detalning nusxalari xaritada ALOHIDA kataklarda turadi, `mult>1` list esa render paytida alohida kartalarga yoyiladi (`CutmapView` → `sorted.slice(k, k+1)`) — ya'ni **har katak = bitta jismoniy detal = bitta chek**. Prodda o'lchangan (2026-08-28): katakdagi nusxa soni listning `mult` iga AYNAN teng, 2601 katakda istisno yo'q (2430×1, 169×2, 2×3). Shuning uchun ID mayda kaption emas, sarlavha ostidagi asosiy qiymat (chekdagi matn bilan solishtiriladi), bekor qilish esa siqilgan qatorda emas — to'liq kenglikda: ishchi 1-nusxa katagidan 2-nusxa chekini bekor qila olmaydi, chalkashish manbai yo'q. Render yo'li baribir `cheklar.map()` — kutilmagan ikkinchi chek yashirinib qolmaydi, tugma yonida `qr_text` bilan chiqadi.

- **Drill-down oqim (bitta sahifa, ikki holat):** `sheetIdx === null` bo'lsa jadval sahifasi — material tablari (bitta qator, `overflow-x-auto`, har tabda `bajarilgan/jami` list hisobi) + listlar gridi (`sm:grid-cols-3 lg:grid-cols-4`); har list kartochkasida №, `L×W` va `SheetSvg thumbnail` mini-xaritasi; hamma detali chiqarilgan list kartasi yashil tusda (belgisiz — ✓ glifi yo'q). `mult>1` naqshlar render paytida HAR JISMONIY LIST uchun alohida kartaga yoyiladi (№ `3c1` ko'rinishida) — ×mult badge yo'q. List bosilsa — to'liq maydonli xarita.
- **List egaligi (`postCode`):** giyotina kesimi listni chetdan chetgacha kesadi — bitta katakni chetlab o'tib bo'lmaydi, ya'ni list yo butunlay arraniki, yo butunlay roverniki (`sheet.rover`). ROVER postida faqat o'z listlari ko'rsatiladi (roversiz materiallar butunlay tushib qoladi); ARRA da rover listlari material ichida ham, material tablari orasida ham OXIRIGA suriladi va begona deb belgilanadi: material tabida `bajarilgan/jami` hisoblagich o'rniga "roverda", aralash materialda begona guruh ustida "Roverda kesiladi" ajratkichi (soni bilan), xarita ustida "Bu listni rover kesadi" satri; begona list kartasi to'lgan bo'lsa ham yashil bo'lmaydi. Xiralashtirish yoki yangi rang ataylab ishlatilmagan — 17" kioskda kontrast birinchi yo'qoladi va ekranda yashil/binafsha/ko'k allaqachon band, tartib va MATN ishlaydi. `admin` rejimida bu mantiq umuman ishlamaydi: texnolog fayl tartibini ko'radi, uning "o'z listi" degan tushunchasi yo'q.
- **Portal joylashuv:** `statsContainer` berilsa sarlavha `createPortal` bilan tashqariga chiqadi — terminalda ochiq list nomi (`№3 — 2750 × 1830 mm` + material) headerga, adminda (`routes/_layout/cutmap.$orderId.tsx`) breadcrumb dumi sahifaning bitta sarlavha qatoriga: `← Buyurtma` (route) `B-2026-066 › Kesish xaritalari`, list ochiq bo'lsa `B-2026-066 › Listlar › №3 — 2750 × 1830 mm · material` + o'ngda oldingi/keyingi list va «To'liq ko'rinish» (⤢) icon-tugmalari, undan keyin `PDF / Chop etish`. Zoom +/− webda yo'q — g'ildirak kursor nuqtasiga zoom qiladi, surish pan. `toolbarContainer` berilsa chap toolbar tugmalari terminalning umumiy chap ustuniga ko'chiriladi; portal berilmasa terminal rejimida toolbar `w-[68px]` ustunda qoladi, admin rejimida esa bu ustun umuman chizilmaydi.
- **Sarlavha qatori (`statsRow`):** ochiq list nomi va o'lchami (`№{disp} — L × W mm`) + material nomi. Reja ko'rsatkichlari (atxot `ko`, rez `dr`/`kr`, to'ldirish `fill`, arra `kerf`, tirim `trimL`/`trimW`) hech qayerda chizilmaydi va cutmap JSON'ga ham yozilmaydi (2026-09-03 qarori; `CutmapMaterial` = `name` + `sheets`).
- **Chap toolbar** (`TBtn` tugmalari): Orqaga (xarita ochiq bo'lsa listlar jadvaliga, aks holda `onBack()`), Oldingi/Keyingi list, Katta/Kichik/To'liq (`SheetSvg` `registerZoom` bergan `zin/zout/reset`), Chop etish — belgilangan detalning navbatdagi CHIQARILMAGAN nusxasini GoDEX navbatiga yuboradi (dialogsiz); hammasi chiqarilgan bo'lsa yozilmaydi, "avval bekor qiling" xabari. **Detal va qoldiq ikki xil endpointga boradi** — tugma bitta, mutatsiya ikkita. Detal nusxasi: umumiy `usePrintLabel("cutmap")` / `useCancelLabel()` (`Terminal/usePrintLabel.ts` — `printInstanceLabel`/`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi; PrisadkaView ham shularni chaqiradi). Belgilangan katak QOLDIQ bo'lsa (`markedWaste`) tugma CutmapView ichidagi lokal `wastePrint` / `wasteCancel` `useMutation` larga tushadi — `TerminalService.printWasteItemLabel` / `cancelWasteItemLabel` (`path: { waste_id }`, id `waste_items` dan `atx` raqami orqali topiladi). Ro'yxatga olinmagan qoldiqda ("eski yuklama") va allaqachon chiqarilgan chekda tugma jimgina o'chmaydi — sababini toast bilan aytadi.
- **Chek chiqarilgan = kesildi:** `isCut(i)` (`@/lib/mes` dan import — SheetSvg ham shu predikatni ishlatadi) — ARRA skan BOR yoki `label_printed_at` bor; statlar, list kartalari va kataklar shu o'lchovda. Xato chek: katakni ikki marta bosish (<450 ms) yoki ~600 ms bosib turish `PartCard` ni ochadi, undagi «Chekni bekor qilish» esa tasdiq dialogini beradi ("Ha, bekor qilinsin" / "Yo'q") va oxirgi CHEK CHIQARILGAN nusxani bekor qiladi. `done` holati to'sib qo'yilmaydi: kesish postida chek chiqarish avto-skan ham yozadi, ya'ni `!done` sharti jestni butunlay o'lik qilardi. Bu jest faqat terminal rejimida — `onOpenPart={admin ? undefined : setSelected}`, adminda kartochka BIR MARTA bosishda ochiladi (`onSelect` ichida `if (admin) setSelected(part)`); bekor qilish tugmasi ikkalasida ham kartochka ICHIDA, ya'ni jest buzg'unchi amalni o'zi bajarmaydi. Hamma detali chiqarilgan list kartasi yashil tusda (`border-green-500/60 bg-green-50 text-green-700`).
- **Tanlash semantikasi:** xaritada detal bosilsa `markedCell` moviy bo'lib qoladi (kartochka yopilgandan keyin ham) — terminalda tap faqat belgilaydi, chop etish chap toolbardan; `admin` bo'lsa qo'shimcha ravishda `PartCard` dialogi ochiladi.
- `instancesByCell` — `useMemo` bilan `pattern_no:cell_index` kalitli Map; `sheetDone(s)` list to'liq kesilganini (har bir waste bo'lmagan katakning barcha instansiyalari `done`) hisoblaydi.
- `printAllMaps` — barcha xaritalarni chop etish: `renderToStaticMarkup(<SheetSvg .../>)` bilan yangi oynaga yoziladi, har list o'z A4 landscape sahifasida (`@page size: A4 landscape`), "Material | №N — L × W mm" sarlavhasi bilan (listlar jismoniy nusxalarga yoyilgani uchun `× k list` yo'q); sahifadagi "PDF / Chop etish" tugmasiga `registerPrint` prop orqali ulanadi. `escapeHtml` bilan nom/raqam ekranlanadi. Brauzer popup'ni bloklab `window.open` `null` qaytarsa toast bilan sabab aytiladi.
- Xarita mavjud bo'lmasa (`data.model` yo'q — fayl GibLabda optimizatsiya qilinmagan, TEMPLATE) tushuntirish matni + "Orqaga" tugmasi.
- **Eksporti bitta:** `CutmapView`. `TBtn` va `PartCard` alohida fayllarga ajratilgan (pastda) — CutmapView ularni import qiladi.

### `frontend/src/components/Terminal/Serial.tsx`

**Maqsadi:** nusxa ID'ini (chekdagi satr bilan aynan bir xil) ko'rsatish — buyurtma prefiksi (`B-2026-047_`) **xira**, farqlovchi qism (`301401_01_001_1`) **qalin**, `whitespace-nowrap`, `title` da to'liq matn. ID `qr-serialization` bilan 32 belgigacha cho'zildi: prefiks har qatorda takrorlanadi va sarlavhada allaqachon turadi, ko'z farqlovchi qismga tushishi kerak. Prefikssiz eski ID regex'ga tushmaydi va o'zgarishsiz chiqadi. Ishlatiladi: `ScanStrip` (muvaffaqiyat kodi), `KromkaView` («Jarayonda»), `PrisadkaView` (nusxa katagi va SCX chiplari), `PostQueueView`, `TmoView` (uchala ro'yxat), `UpakovkaView` («Qadoqlanmagan»), `PartCard` (chek ID qatori va bekor qilish tugmasi). 2026-09-03 terminal auditida qo'shildi; o'sha auditda: detal KOD kataklari `whitespace-nowrap` (nostandart `…_016-2` ikki qatorga sinardi), KROMKA «N tomon» katagi nowrap, TMO tab'lari `h-12`, UPAKOVKA chiqarish/qayta ochish tugmalari `h-11`, PRISADKA xarita ikonkasi `size-10`, brigada chiplari va «+ Qo'shish» `h-10` (qo'lqop uchun ≥40px).

### `frontend/src/components/Terminal/TBtn.tsx`

Chap toolbar tugmasi: ikonka + `text-2xs` yozuv (`index.css` da 0.6875rem), `h-16 w-full`, `TBTN_TONES` rang kodlari — default (oq fon, primary matn) / primary (asosiy nav) / warn (qulf; amber FON ataylab yo'q — xarita apelsini bilan qo'shilib ketardi, faqat ikonka rangi) / danger (chiqish) / success. Uchta chaqiruvchi: `CutmapView` (butun chap toolbar), `PrisadkaView` (ROVER "Chop etish", portal orqali) va `routes/terminal.tsx` (to'rtta tugma: "Xarita" — ROVER kesish xaritasi, "Qulflash", va sessiya tugmasi "Chiqish"/"Yakunlash"). Skan tugmasi YO'Q — skan avto-fokusli inputdan keladi (`useScanFocus`/`useTerminalScan`).

### `frontend/src/components/Terminal/PartCard.tsx` (~397 qator)

**Maqsadi:** kesish xaritasidagi detal/qoldiq kartochkasi. `CutmapView` dan ajratilgan — yagona chaqiruvchi o'sha.

- `PartPreview` (ichki, eksport emas) — tanlangan detal mini-chizmasi (276×190 viewBox): o'lcham strelkalari, `holes` dan yuza (`bores`) va qirra (`edge`) teshiklari masshtablangan holda, aylantirilgan detalda ⟳.
- `PartCard` dialogi: sarlavha (`№` + nom) va ostida chek ID si + holati, `PartPreview`, katta QR (`qrcode.react` `QRCodeSVG` — kaptionsiz, ID yuqorida turibdi), o'lcham/kromka, so'ng `h-14 w-full` qizil "Chekni bekor qilish" (`LoadingButton variant="destructive"`) va `h-12` "Yopish". Bekor qilish sharti `c.printed && c.cancel` — kesish postida chek skan ham yozgani uchun `done` holati to'sib qo'yilmaydi; proyekt ARRA ro'yxatidan tushib bo'lgach texnolog xato chekni shu yerdan tuzatadi. Kartochka adminda bir marta bosishda, terminalda ikki marta bosish yoki uzoq bosishda ochiladi; unda chop etish tugmasi YO'Q — terminalda chop etish yo'li chap toolbardagi "Chop etish". Mutatsiya SHOXGA qarab: detal nusxasida `usePrintLabel.ts` dagi `useCancelLabel()` (`cancelInstanceLabel`), qoldiqda esa `cancel: () => onCancelWaste(wasteItem.id)` — ya'ni CutmapView dagi `wasteCancel` (`TerminalService.cancelWasteItemLabel`); `wasteCancelling` propi yuklanish holatini beradi.
- `onCancelRequest?` propi bekor qilish yo'lini belgilaydi: berilmasa (admin) bekor qilish DARHOL bajariladi, berilsa (terminal) chaqiruvchiga uzatiladi va tasdiq oynasi ochiladi — tsexda qo'lqopdagi barmoq bilan xato bosish adminning stoliga qaraganda ancha ehtimolli. Ro'yxatga olinmagan atxot (`part.waste && !part.atx`) kartochka umuman ochmaydi.

### `frontend/src/components/Terminal/SheetSvg.tsx` (~1110 qator)

**Maqsadi:** bitta listning to'liq SVG renderi — GibLabViewer'dan portlangan render qoidalari. `CutmapView` (interaktiv, thumbnail va print oqimi) ishlatadi.

**Props:** `sheet`, `holes`, `instancesByCell`, `onSelect(part)`, `onOpenPart?(part)` (detal kartochkasini ochadi — berilmasa jest umuman ulanmaydi, ya'ni admin rejimida o'chiq), `wastePrinted?: Set<number>` (cheki chiqarilgan qoldiqlarning `atx` raqamlari), `selectedCell`, `thumbnail?`, `registerZoom?({zin,zout,reset})`, `onSwipe?("next"|"prev")`.

- **Eksport qilingan geometriya yordamchilari** (`CutmapView/PartPreview` ham ishlatadi): `holeXY(part, H, bx, by)` — teshik lokal koordinatasini katakka o'giradi (`p.rot` da o'q almashinuvi, oynasiz), `edgeLocalXY(H, side, pos)` — qirra teshigining lokal nuqtasi (t/b/l/r), `edgeBoreRect(part, cx, cy, d, dp)` — eng yaqin chetdan ichkariga to'rtburchak (uzunligi = burg'u chuqurligi).
- **Ranglar/qoidalar:** barcha detallar `#e88b00` (to'q apelsin), TANLANGANI qalin ko'k KONTUR bilan belgilanadi (`#2596be`, 14px) — fon almashtirilmaydi: ilgari tanlov fonni butunlay bosib, katakning HOLATINI yopardi va chek chiqarilgach katak tanlangan holda qolgani uchun yashil rang faqat boshqa katak tanlanganda ko'rinardi ("chek chiqdi, hech narsa o'zgarmadi" shikoyati shundan). Qoldiq katagida tanlov ilgari umuman ko'rinmasdi — endi u ham shu konturni oladi, nostandart detal (`Part.is_custom` → barcha nusxalarida `custom` bayrog'i) kesilmagan holatda binafsha (`PART_CUSTOM = "#a78bfa"`), chek chiqarilgach odatdagidek yashil (`allDone` fondan ustun), bekor qilinsa yana binafsha; chegara barcha detallarda bir xil; atxot va list foni `zebra` pattern (`patternTransform rotate(45)`); **QOLDIQ (`business`, `atx` raqamli) katagi zebra SAQLANADI, rang holatni aytadi**: chek chiqarilmagan — apelsin-oq zebra (`zebraQoldiq`, detal apelsini tilida «chek chiqarish mumkin»), chek chiqarilgach — yashil-oq zebra (`zebraDone`), bekor qilinsa yana apelsin-oq; qaysi qoldiq chiqarilganini `wastePrinted: Set<number>` propi aytadi — CutmapView uni `waste_items` dagi `label_printed_at` bor yozuvlarning `atx` raqamlaridan yig'adi. Prop ochiq listga ham, ro'yxatdagi `thumbnail` mini-xaritaga ham, `printAllMaps` PDF'iga ham beriladi — uchalasida qoldiq holati bir xil (ilgari faqat ochiq list olardi: ro'yxatda chiqarilgan qoldiq apelsin zebra bo'lib qolardi). **QOLDIQ DETAL BILAN BIR XIL OQIMDA**: bir marta bosish belgilaydi va chap qatordagi «Chop etish» ishlaydi (qoldiqda u `printWasteItemLabel` ga boradi), ikki marta bosish/uzoq bosish `PartCard` ni ochadi — bekor qilish o'sha yerda. Alohida `onOpenWaste` propi va alohida dialog OLIB TASHLANDI: bitta xaritada ikki xil jest qoidasi operator uchun ortiqcha yuk edi. Ro'yxatga olinmagan atxot (atx yo'q) avvalgidek inert. Ilgari qoldiq shoxidan yuqorida turgan `if (p.waste) return` uni umuman o'lik kodga aylantirgan edi. Yo'l-yo'l naqsh «bu atxot» identligini saqlaydi. Oddiy (ro'yxatga olinmagan) atxot kulrang zebra bo'lib qoladi; qoldiq katagidagi O'LCHAM YOZUVI detalning "tight" rejimi bilan AYNAN bir xil qoidada hisoblanadi (`DIM_FS` gacha, faqat sig'masa kichrayadi, `DIM_MIN`/zoom chegarasi ham o'sha) — ilgari unda alohida formula turib, shrift 34 ga QOTIRILGAN edi va bir xil o'lchamli detal 48 olib, qoldiq 34 da qolardi; kesim chiziqlari (`sheet.cuts`) qora `#242424`; yozuvlar halo'siz (to'q apelsin fonda kerak emas).
- **Zoom/pan/swipe (Pointer Events):** g'ildirak zoom kursor nuqtasiga (native `wheel` listener, `passive: false`), bir barmoq pan (zoomda) yoki gorizontal swipe → `onSwipe` bilan list almashtirish (>80px, <600ms), ikki barmoqli pinch. `setPointerCapture` **ataylab ishlatilmaydi** — u keyingi `click`ni SVG'ga retarget qilib detal tanlashni o'ldiradi. G'ildirak, pinch va toolbar tugmalari bitta `zoomAt(f, ax, ay)` yordamchisiga tushadi (tugmalar markaz atrofida 1.5x, `zoomBy`), zoom chegarasi ham shu yerda — `base.w/14`; `viewBox` `base` dan kichik bo'lsagina `vb` state saqlanadi, list almashsa (`sheet.no`) tiklanadi.
- **Yozuv joylashtirish (GibSaw pariteti, `GibSaw.exe` dekompilyatsiyasidan portlangan):** shrift QATTIQ — `DIM_FS = 48` mm, tsexdagi GibSaw.ini `pattrenPartDim=48` bilan bir xil; glyph geometriyasi TAXMIN EMAS, jonli brauzerda `getBBox` bilan O'LCHANGAN konstantalar: Archivo 700 ascent 0.884em → `ASC = 0.9`, descent 0.201em → `DESC = 0.22`, raqam eni 0.596em → `CH = 0.6` (taxminiy 0.75em bilan mm darajasidagi chiqib ketishlar qolayotgan edi). Vertikal (rotate(90)) matnda glyph bazachiziqdan +x (o'ngga) tomon chiqadi — bazachiziq shunga mos qirradan `ASC` masofada qo'yiladi; ilgari bo'sh tomon hisoblanib, 13/72 yorliq qo'shni katakka kirib ketgani jonli o'lchovda aniqlangan; detalga qarab KICHRAYMAYDI (ilgari `min(kondalang*0.28, boylab/len)` bilan 6-8 mm gacha tushib o'qib bo'lmasdi). Sig'masa o'lcham emas, YO'NALISH almashadi (`dimFit`: 'h' → 'v' → chizilmaydi). Sig'ish sharti: matn uzunligi o'z o'qiga, glyph qalinligi (`(ASC+DESC)·fs + 4`) ko'ndalangiga — +4 aynan yozuvning qirradan ichkarilik masofasi, ya'ni joylashuv geometriyasining o'zi; ilgari +8 zaxira 60 mm li strip (60×1490, odatiy) da ikkala o'lchamni ham yo'qotib, uni markazdagi birlashgan `W×H` ga tushirar va qo'shni 100 mm li kataklardan farqli ko'rsatardi — endi 58 mm dan keng strip standart shaklda (eni pastki-chapda burab, bo'yi o'ng qirrada, nom markazda). Joylashuv: ENI pastki-chap burchakda gorizontal, BO'YI o'ng qirrada vertikal (yuqoridan pastga) — diagonal qarama-qarshi burchaklar, ikki o'lcham strukturaviy to'qnashmaydi. MITTI detalda (burchak box'lari baribir kesishadigan yoki o'lcham umuman sig'maydigan) markazda bitta birlashgan `W×H` — atxot yozuvi bilan bir xil shakl; GibSaw bu holatda ustma-ust chizadi yoki tashlab yuboradi, bizniki yaxshiroq. Nom (`№num nom`) markazda, shrift qoidasi pastda; mitti rejimda yoki katak 16×8 dan kichik bo'lsa nom chizilmaydi (ilgari `availW/availH` — o'lcham bandi butun en bo'ylab ayirilgan qiymat — tekshirilib, 60×1490 stripda nom sababsiz o'chirilardi; haqiqiy teginishni kesishish himoyasi ushlaydi). Teshiklar yozuvga TO'SIQ EMAS — o'lcham ham, nom ham teshik ustiga bemalol tushadi (tsex talabi; GibSaw ham tekshirmaydi). Ilgari teshik-chetlab o'tish yozuvni muqobil nomzodga sakratardi va bir xil detal turli listlarda TURLI joyda yozuv olib, "o'lcham siljigan" bo'lib ko'rinardi — endi har yozuv o'rni DETERMINISTIK. Nom O'LCHAM FONTIGACHA chiziladi (`DIM_FS` = 48) — alohida kichik cap YO'Q, `nomMax` olib tashlangan; ko'ndalang cap KATAKNING qisqa tomoniga glyph bbox sig'ishi (`(shortC-10)/(ASC+DESC)`), `shortA*0.55` EMAS — eski cap botB/rightB zaxirasini butun en bo'ylab ayirib, cho'zinchoq detalda (2390×100 o'lchandi: 22.7 mm) nomni sababsiz kichraytirardi, o'lcham esa faqat burchakda turadi — GibSaw'da nom ham `pattrenPartDim` fonti bilan chiziladi, alohida kichik font yo'q; ilgari `nomMax` cap katta katakda nomni sababsiz kichraytirardi. O'lchamga tegsa avval 0.72 pog'ona kichrayadi, baribir tegsa NOM chizilmaydi: kichik detalda katta o'lcham ostida ko'rinmay qolgandan ko'ra yo'q bo'lgani yaxshi (1192 Anvar N11/N15/N16 350×97-90 da aynan shu holat). Birlashgan `W×H` yozuvi yo'nalishi katak shakliga qarab tanlanadi (`fitAlong` — qaysi o'qda shrift kattaroq chiqsa): ingichka-uzun detal (60×1490) da vertikal, ~43 mm; ilgari doim gorizontal bo'lib 13 mm ga tushardi.
- **Tekstura yo'nalishi:** `p.txt` bo'lsa (va detal >60×40) matn ortida 3 chiziq — detalning `l` o'qi bo'ylab (`p.rot` bo'lsa vertikal, aks holda gorizontal). GibSaw xaritada teksturani UMUMAN chizmaydi (dekompilyatsiya: part-draw'da faqat XNC, kromka punktiri, o'lchamlar, nom) — bu belgi bizning qo'shimcha, chek eskizi bilan bitta qoidada.
- **Burilgan detal (rot) — HAQIQIY 90°, transpose emas:** `holeXY` lokal `(x,y)` ni katakka `(y, h−x)` bilan o'tkazadi — GibSaw.exe dekompilyatsiyasi bilan tasdiqlangan (`translate(0,h); rotate(-90)`). Ilgari `(y,x)` transpose edi — bu OYNA (transpose = burilish + aks, fizikada detal ag'darilmaydi): 1803 mm detalda teshik ~1 metr noto'g'ri joyda chiqardi. Prodda burilgan+teshikli katak 493 ta edi. Kromka belgilari (`cutmap._edge_markers`) va chek eskizi (`labels.py`) ham shu konvensiyada.
- **Teshiklar haqiqiy masshtabda:** `H.bores` — radiusi `d/2` doiralar, `H.edge` — `edgeBoreRect` to'rtburchaklari; hammasi `#fafafa` to'ldirish, `#202020` kontur.
- **O'lcham zanjirlari** (`sheet.dims`, `ax: "X"|"Y"`): chetda strelka, ichki chegarada kesim davomi + ✕ belgisi; qiymat 48px va GibSaw kabi zanjir chizig'i ICHIDA (oq halo chiziqni matn joyida uzadi — dekompilyatsiyada chiziq matn uchun ikki segmentga bo'linadi). `PAD = 68` — GibSaw zanjir chuqurligi band-font balandligiga teng (~55 mm); ilgari 110 edi va list shuncha kichik render bo'lardi. Zanjir faqat ROOT kesim tomonida (tepa yoki chap) — GibSaw ham faqat birinchi darajali striplarni chizadi. Fontlar GibSaw.ini bilan paritet: `pattrenPartDim=48`, `pattrenBandDim=48`.
- Barcha nusxalari "kesilgan" (skan yoki chek chiqarilgan — `isCut`, `@/lib/mes`) katak YASHIL (`PART_DONE = "#22c55e"`, Tailwind green-500 — tizimdagi boshqa "bajarildi" belgilari bilan bir ton) to'ldiriladi — belgisiz; `onOpenPart` prop berilsa IKKI jest ham uni chaqiradi va DETAL KARTOCHKASINI ochadi: katakni ikki marta bosish (<450 ms — Windows ning 500 ms oynasidan bir oz tor, qo'lqopdagi barmoq sekinroq) yoki ~600 ms bosib turish (`LP_SLOP = 30` px siljish yoki pinch uzoq bosishni bekor qiladi, keyingi click yutiladi; bosish davomida katak `animate-hold` bilan asta bo'yaladi — jest qabul qilinganini ko'rsatadi). Ikki marta bosish GibSaw'dagi eski odat, uzoq bosish esa sensor DRAYVERIGA bog'liq bo'lib chiqdi (bir panelda ishlaydi, boshqasida yo'q) — shuning uchun ikkalasi ham qoldirilgan. Chekni bekor qilish tugmasi kartochka ichida: jest buzg'unchi amalni o'zi bajarmaydi. `thumbnail` rejimda `pointer-events-none`.

### `frontend/src/components/Terminal/KromkaView.tsx`

**Maqsadi:** KROMKA/OVAL post sahifasi. (2026-09-03 dan BITTA to'liq kenglikdagi jadval — «Ikki panel» tavsifi eskirgan, pastdagi 2026-09-03 bandiga qarang.) Chapda arradan chiqqan (`arra_passed`), kromkasi tugamagan detallar (tugaganlari yashil bo'lib pastga tushadi), o'ngda "Jarayonda" — 2+ tomonli, boshlangan-u tugamagan nusxalar. Detal nomi ostida `Common/OperationChips` — noodatiy marshrutli detalda shu postga tegishli amal nomi chiplari (postCode: `oval ? "OVAL" : "KROMKA"`). Har skan darhol yoziladi (tomon = skan); `registerScan` prop orqali terminalga lokal tekshiruv beradi (`null` = yozish mumkin, `"NOTFOUND"` = bu proyektda yo'q, boshqa string = xato matni: arradan chiqmagan / allaqachon tugagan). Tekshiruv QR ga mos KELGAN HAMMA qatorni yig'adi, birinchisida to'xtamaydi: nostandart marshrutda (`[3, 6, 3]`) bitta detal KROMKA'ni ikki marta oladi va backend har qadamga alohida qator qaytaradi — birinchi qatorga qarab javob berilsa, birinchi o'tish tugagach ikkinchi o'tishning skani "allaqachon tugagan" deb LOKAL bloklanardi (server esa `scanning.py` da seq bo'yicha birinchi ochiq qadamni olib qabul qilardi). Endi qadamlardan bittasi ochiq bo'lsa skan o'tadi; yakuniy hakam baribir backend (E00x). `oval` prop: bir panel, tomonlar ustuni yo'q va `done/sides` o'rniga `–` chiziladi — OVAL marshrut qadamida `per_instance` doim 1, ya'ni bir detal bir skanda tugaydi (`c3d97a1e5b02` gacha kod xato ravishda qirralar sonini berardi). Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + markazga avto-scroll (`useScanFlash` hooki — xuddi shu mexanizm `PrisadkaView` da ham). «Kromka» ustuni (faqat `!oval`) — `{sides} tomon` va qirralarning GibLab EL SIMVOLLARI (`edges[side].symbol`, takrorlanmaydi, belgisiz qirra `•`). Tomon NOMI (Chap/O'ng/Tepa/Past) ATAYLAB berilmaydi: yorliq eskizi uzun tomonni doim vertikal chizadi, ya'ni `l/r/t/b` ning eskizdagi joyi `length > width` bo'lganda almashadi (`services/labels.py` `burilgan` xaritasi) — qat'iy jadval odatiy uzun detalda operatorga eskizga 90° zid nom ko'rsatardi. Qator kaliti, DOM id (`kv-row-…`) va `useScanFlash` kaliti — hammasi `route_id`, `part_id` emas: nostandart marshrutda (masalan `[3, 6, 3]`) bitta detal KROMKA'ni ikki marta oladi, o'shanda `part_id` DOM id'ni takrorlab xatcho'pni noto'g'ri qatorga tushirardi. Ma'lumot: `readTerminalKromka` (`refetchInterval: 30_000` + har skanda invalidatsiya); so'rov yiqilsa Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`) — ilgari xato jim yutilib, jadval "Arradan kelgan detal yo'q" bo'sh holatiga tushardi va kromkachi kelmagan detallarni kutib turardi.

2026-09-03: (0) O'ng «Jarayonda» paneli OLIB TASHLANDI — u «Holat» ustunidagi nusxa chiplarini takrorlar va jadvalni yarim kenglikka siqib, ko'p nusxali qatorlarda chiplarni ustma-ust (qator 4 barobar baland) qilib yuborardi. Endi jadval to'liq kenglikda; qatorlar uch pog'onada (`tier`): jarayondagi (2+ tomonli, bir tomoni skan qilingan) TEPADA `bg-amber-50/70`, keyin boshlanmaganlar, tugaganlari pastda `bg-green-50`; `PostHeader`da «Jarayonda N» sariq hisob. (1) `OperationChips` ga `defaultCode` (KROMKA 3, OVAL 5) — postning odatdagi amali chip sifatida chizilmaydi, faqat farqlisi («Fasat kromka»); ilgari har qatorda «Kromka» chipi sarlavhani takrorlardi. (2) `EdgeGlyph` — KROMKA ustunida kichik eskiz: qaysi tomonlarga kromka (amber qalin chiziq), CHEKDAGI rasm bilan bir konvensiya (`labels.py` `burilgan`: uzun tomon `length` bo'lsa eskiz tik, t→chap, b→o'ng, l→past, r→tepa). Kromkachi chekdagi rasm bilan solishtiradi — yozuv («2 tomon A») yo'nalishni aytmaydi.

### `frontend/src/components/Terminal/PrisadkaView.tsx`

**Maqsadi:** PRISADKA va ROVER post sahifasi: detallar + SCX fayllari, "Hammasini yuklab olish" tugmasi. Props: `orderId`, `onBack`, `showScx?` (default `true`; `routes/terminal.tsx` ROVER postida `false` beradi — SCX fayllar kerak emas), `onShowOnMap?(partCode)` (ROVER: detalni kesish xaritasida ochish — tugma faqat `!p.arra_route` detallarda chiqadi, chunki arradan kelgani rover xaritasida umuman yo'q), `toolbarContainer?` (ROVER "Chop etish" tugmasi terminalning umumiy chap ustuniga portal qilinadi). Ma'lumot: `readTerminalPrisadka` (`refetchInterval: 30_000`).

- SCX oqimi (`showScx`): `lib/scxDir.ts` bilan — File System Access API `showDirectoryPicker` BIR MARTA, tanlangan papka IndexedDB'da (`mebelix-terminal/kv/scx-dir`), keyingi yuklab olishlar so'roqsiz; papka ichida proyekt nomli subpapka (`project_name`, taqiqlangan belgilar `_` ga) ochilib fayllar shu yerga yoziladi (URL — `scxFileUrl(id)`). API bo'lmasa `<a download>` fallback — bu yo'lda natijani BILIB BO'LMAYDI (server 404 bersa yoki brauzer yuklashni bloklasa ham `click()` jim qaytadi), shuning uchun toast "N ta SCX yuklash boshlandi — brauzer yuklamalarini tekshiring" deydi, "yuklab olindi" deb yolg'on va'da bermaydi (FSA yo'li esa aksincha aniq sanaydi va kamomad bo'lsa `toast.error` beradi). **SKAN hech qanday fayl yuklamaydi** — `saveScxToDir` yagona joydan, "Hammasini yuklab olish" tugmasi ortidagi `downloadAll` dan chaqiriladi: yuklash operator xohlaganda bo'ladi. Yuklab olishda tugmada jonli progress ("Yuklanmoqda… 12/81"); papka tugmasi yozuvli ("Papka" — sensorli ekranda hover yo'q).
- **Papka bosqichi jim yiqilmaydi:** `downloadAll` ning `try` bloki `catch` bilan yopiladi — saqlangan papka o'chirilgan/ko'chirilgan yoki flesh olib qo'yilgan bo'lsa (`getDirectoryHandle` → `NotFoundError`) operator "SCX papkasini ochib bo'lmadi — Papka tugmasi bilan qayta tanlang" toastini ko'radi; `AbortError` (foydalanuvchi dialogni bekor qilgani) jim o'tkaziladi. Ilgari faqat `try/finally` bor edi va xato unhandled rejection bo'lib ketardi: tugma jimgina qaytardi. Subpapka nomi ham qo'riqlangan — `projectFolder(...) || "scx"`, chunki `projectFolder` faqat taqiqlangan belgilarni tozalaydi va " " kabi nomdan bo'sh satr qaytarib, `getDirectoryHandle("")` ni yiqitardi.
- **So'rov xatosi JIM yutilmaydi:** `isError` da Skeleton'dan keyin `Common/QueryError` chiziladi (`isError, refetch`). Ilgari faqat `isLoading` tekshirilardi va birinchi yuklash yiqilganda bo'sh `parts` yolg'on bo'sh holatga aylanardi — PRISADKA shoxida "Bu buyurtmada prisadka detallari yo'q", ROVER shoxida "Bu buyurtmada bu postga detal yo'q".
- Jadval ish-navbat tartibida: qilinmaganlar tepada, tugaganlar (✓ yashil) pastda; oxirgi skan bo'lgan qator KEYINGI skangacha chap chetdagi xatcho'p bilan ajralib turadi (`border-l-4 border-l-primary` — holat rangini bosmasin deb ataylab chetga chiqarilgan) va markazga avto-scroll bo'ladi (`useScanFlash` hooki — `done` o'zgargan qatorni topadi: lokal skan ham, ish markazidan skan-forvard ham). Chiplar nusxa (`instances`) darajasida: `done` — yashil ✓, `label_printed` — amber, aks holda kulrang; nusxa umuman bo'lmaganda faqat kulrang fayl nomlari chiziladi (holatsiz). Qator kaliti, DOM id (`pv-row-…`) va `useScanFlash` kaliti — hammasi `route_id`, `part_id` emas (KromkaView'dagi bilan bir xil qoida): nostandart marshrutda bitta detal shu postni ikki marta oladi va `part_id` ikki qatorni bitta kalitga siqib, har refetchda yolg'on "skan bo'ldi" xatcho'pini berardi. ROVER jadvalida qator NUSXA darajasida — u yerdagi kalit `route_id:instance_id` juftligi (`instKey`, DOM id `pv-inst-…`, `selectedId` ham shu satr): yolg'iz `instance_id` bilan takroriy qadamda tanlov ham, xatcho'p ham ikkala qatorga birdan tushardi.
- **QR chekni chiqarish** (`usePrintLabel("prisadka")`): marshrutida ARRA bo'lmagan (`arra_route=false`) detal jarayonni shu postdan boshlaydi — cheki shu yerdan chiqariladi. ROVER rejimida (`showScx=false`) qator (nusxa) tanlanadi va chapdagi katta "Chop etish" `TBtn` (portal) bosiladi; PRISADKA rejimida chek chiqarish tugmasi instansiya chipining ichida (printer ikonkasi, faqat `!done && !label_printed && !arra_route` nusxalarda).
- **Chekni bekor qilish** (ROVER jadvalida): `label_printed` bo'lgan VA cheki SHU POSTDA chiqarilgan (`ownLabel(p)` — `Boolean(onShowOnMap) && !p.arra_route`, ya'ni chek ikonkasi bilan aynan bir shart) nusxa qatorini ~600 ms bosib turish tasdiq dialogini ochadi ("Chekni bekor qilasizmi?" → "Ha, bekor qilinsin" / "Yo'q") va `useCancelLabel()` ni chaqiradi — ARRA xaritasidagi uzoq bosish bilan bir xil imo-ishora (u yerda esa jest avval `PartCard` ni ochadi va tasdiq undagi tugmadan keladi). Alohida tugma ataylab qilinmagan: qatorlar tor, tasodifiy bosish chekni o'chirib yuborardi; imo-ishora ko'rinmas bo'lgani uchun jadval tepasida bir marta "Chekni bekor qilish: qatorni bosib turing" yozuvi turadi (har qatorga takrorlanmaydi).

2026-09-03 (terminal 3-qadam): (1) nusxa chipi YARIM YO'Lni ko'rsatadi — backend `PrisadkaInstance.scans/need` (`per_instance`: prisadkada bir nusxa 2 skan talab qilishi mumkin): «1/2» sariq; ilgari chip faqat done/undone edi va «Bajarildi 1/2» ustuni «2 nusxadan 1» deb o'qilardi. (2) Ustun sarlavhalari o'z izohi bilan (kioskda hover yo'q): «Detal ID · SCX — ✓ tugadi · sariq — chek chiqqan / yarim · 1/2 = skan», «Skanlar — qilingan / jami» (ilgari «Bajarildi»). (3) SCX papkasi — o'rnatish sozlamasi, operator amali emas: tanlangan bo'lsa sarlavhada xira «Papka: NOMI» izohi (`getSavedDir().name`), tugma YO'Q — papka birinchi yuklashda bir marta so'raladi va eslab qolinadi; almashtirish — brauzer sayt ma'lumotini tozalash. Yuklash tugmasi «SCX → papkaga (N)» (ilgari «Hammasini yuklab olish»). (4) ROVER (nusxa rejimi) «Holat»: rover o'zi kesadigan (`ownLabel`) detalda «Chek yo'q» → «✓ Bajarildi» (chek chiqishi = avto-skan = bajarildi; oraliq sariq «Chek chiqarilgan» faqat avto-skan yiqilganda), arradan kelgan detalda «Bajarilmagan» → «✓ Bajarildi» (skan bilan). Sarlavha legendasiz — chiplarning o'zi yetarli, oqimni roverchi biladi. Chekni bekor qilish — ARRA bilan BIR XIL DIALOG: qatorni ikki marta bosish yoki uzoq bosish (~600 ms) → `onShowOnMap(code, true)` → xarita shu detalga o'tadi (`CutmapView focusPartKey` + yangi `openFocusedCard`) va o'sha `PartCard` kartochkasi ochiladi (chizma, QR, «Chekni bekor qilish»). Roverning o'z tasdiq dialogi va `useCancelLabel` olib tashlandi; sarlavhadagi «qatorni bosib turing» ishorasi ham yo'q. (5) Qatorlar Kromka bilan bir qoidada (`partTier`): yarim qolganlar tepada `bg-amber-50/70`, keyin boshlanmaganlar, tugaganlar pastda yashil.

### `frontend/src/components/Terminal/PostQueueView.tsx`

**Maqsadi:** BOYOQ va STOLYARKA post sahifasi — NUSXA darajasidagi navbat (`readTerminalPostQueue`, `refetchInterval: 30_000`). Umumiy "Navbatdagi vazifalar" jadvali detal darajasida agregat berardi ("qoldiq 6/6") va navbatni hisobga olmasdi: operator hali arradan chiqmagan detalni ko'rib, skanerlab E004 olardi.

- Uch guruh: **kelgan** (`ready && !done`) — asosiy ish ro'yxati; **bajarilgan** (`done`, yashil ✓); yetib KELMAGANLARI ro'yxatda umuman ko'rsatilmaydi, faqat "yana N detal tsexda" satri (ularni skanerlab bo'lmaydi, izlash ham vaqt yo'qotish).
- Sarlavhalar postga moslanadi, ammo FAQAT "kelgan" sarlavhasi (`LABELS`: BOYOQ → "Bo'yashga kelgan", STOLYARKA → "Stolyarkaga kelgan"; noma'lum post → "Ishga tayyor"). Bajarilganlar guruhi sarlavhasi kodda QATTIQ "Bo'yalgan" yozilgan — `LABELS` dagi `done` maydoni hech qayerda o'qilmaydi, ya'ni STOLYARKA postida ham "Bo'yalgan" chiqadi ("Bajarilgan" o'rniga). Kod xatosi, tuzatilmagan.
- Qatorda: QR (yirik), detal nomi, **material** (bo'yoqchi uchun bu RANG — amber), texnolog izohi, `Common/OperationChips` (stolyarkada olti xil amal, noto'g'ri petlya eshikni brak qiladi), yig'ma buyum biriktirilgan mayda detallari (`+ 01_007 ×2`), o'lcham va oxirgi bajarilgan bosqich.
- Skan alohida yo'l talab qilmaydi — terminalning umumiy skan mutatsiyasidan o'tadi, qator `done` bo'lib pastga tushadi.
- **So'rov xatosi JIM yutilmaydi:** `isError` da `Common/QueryError` chiziladi. Ilgari faqat `isLoading` tekshirilardi va xatoda `rows` bo'sh qolib "Bu proyektda bu postga tegishli detal yo'q." chiqardi — operator postni ishsiz deb tashlab ketardi.

### `frontend/src/components/Terminal/UpakovkaView.tsx`

**Maqsadi:** QADOQLASH post sahifasi. Chapda ochiq qadoq (kod, detallar soni, `~kg` — taxminiy, bloklamaydi), o'ngda "Qadoqlanmagan" va "Yakunlangan". Oqim: "Qadoq yaratish" → detallarni birma-bir skanerlash → "Qadoqni yakunlash" (chek QR bilan chiqadi). Har qatorda o'chirish tugmasi — xato skan qaytariladi va UPAKOVKA skani ham bekor bo'ladi. `registerScan` prop orqali terminalga skan qabul qiluvchi beradi: detal qaysi QADOQqa tushishini faqat shu ekran biladi.

- **Skan javobini ekranning o'zi beradi** (ovoz + toast) — `registerScan` yo'li terminalning umumiy ovoz+banner oqimini chetlab o'tadi: muvaffaqiyatda `playSuccess()` + `toast.success("Qadoqqa qo'shildi: …")`, ochiq qadoq bo'lmasa `playWarning()` + "Avval qadoq yarating", xatoda (skan, qadoq yaratish/chiqarish/yakunlash — hammasi) `playError()` + `detailMessage`.
- **So'rov yiqilsa `QueryError`** (`isError` → "Qayta urinish"): busiz kiosk "Ochiq qadoq yo'q" va "Hammasi qadoqlangan." deb yolg'on tinch holat ko'rsatardi.

### `frontend/src/components/Terminal/TmoView.tsx`

**Maqsadi:** TMO post sahifasi, ikki tab (ikki xil ish bir ekranda aralashmasin).

- **Qabul** — TMO ga yetib kelganlar (qadoq kodi bilan), skan `PK-...` bo'lsa qadoq ichidagi hammasini birdan qabul qiladi. Pastda "Tsexda" ro'yxati: har detalga ishi TUGAGAN post yozilgan (`stage`) — omborchi buyumni aynan o'sha yerdan topadi.
- **Qabul qilingan** — SERVERDAN keladigan ro'yxat (`TmoOrderState.done`): qabul qilingan nusxa, qadoq cheki (bo'lsa) va qabul vaqti, eng oxirgisi tepada. Ilgari bu ro'yxat faqat React state'da edi va sahifa yangilanganda YO'QOLARDI — omborchi o'zi qabul qilgan detallarni ko'rmasdi.
- **Alohida "Qadoqlar" tabi YO'Q.** Qadoq faqat yorliq: har detal qatorida qaysi chek bilan kelgani yoziladi. Qadoq cheki (`PK-...`) skanerlansa `accept_into_tmo` ichidagi HAMMA nusxani birdan qabul qiladi, ya'ni natija baribir detal ro'yxatida ko'rinadi — omborchi uchun chek va yakka detal bir xil ishlaydi.
- **"Buyurtmani topshirish" tugmasi OLIB TASHLANDI** (`deliver_tmo_order` endpointi bilan birga). TMO buyurtmani topshirmaydi: hamma detal TMO dan o'tgach buyurtma `record_scan_at` da o'zi TAYYOR (COMPLETED) bo'ladi, TOPSHIRILDI esa managerning amali (`/orders/{id}`, faqat TAYYOR holatdan).
- **So'rov xatosi JIM yutilmaydi:** `isError` da `Common/QueryError` chiziladi. Ilgari
  faqat `isLoading` tekshirilardi va xatoda bo'sh ro'yxat yashil "Hammasi qabul qilindi."
  ga aylanardi — omborchi yiqilgan so'rovni tugallangan ish deb o'qirdi.
- Sarlavhada `TMO ga keldi: arrived/total` va `Qabul qilindi: accepted/total` — omborchi oldida qancha ish turganini ko'rishi uchun (bitta progress bar faqat skanerlanganini ko'rsatardi).
- `registerScan` HAR QANDAY skanni QABULGA yo'naltiradi (`accept.mutate(qr)`) — aktiv tab bunga ta'sir qilmaydi; qadoq cheki (`PK-...`) bo'lsa server `accept_into_tmo` ichida hamma nusxani birdan qabul qiladi.
- **Skan javobini ekranning o'zi beradi** (ovoz + toast, `ScanStrip` WS orqali kechikib to'lganidan oldin): takror qabulda `playWarning()` + `toast.error("Allaqachon qabul qilingan: …")`, muvaffaqiyatda `playSuccess()` + `toast.success` (qadoq bo'lsa nechta detal qabul qilingani), xatoda `playError()` + serverdan kelgan xabar (`detailMessage`).

### `frontend/src/components/Terminal/OrderPicker.tsx`

**Maqsadi:** proyekt tanlagichi — HAMMA post sahifasi shundan boshlanadi. Kartada raqam, loyiha nomi, prioritet badge'i, materiallar, `done/total` progress va qoldiq, listlar soni, muddat rangi. `done/total` va `sheets_total` post semantikasida (backend `/terminal/orders` hisoblaydi: ARRA — chek∪skan, o'z listlari; KROMKA — detal bo'yicha). Props: `onPick`, `title?`, `showCutmapBadge?`.

### `frontend/src/components/Terminal/PostHeader.tsx`

**Maqsadi:** post ekranlarining umumiy sarlavhasi — "Orqaga" tugmasi + buyurtma raqami + loyiha nomi. Ilgari beshta ekran shu blokni so'zma-so'z ko'chirib yozgan va bir-biridan uzoqlashgan edi (loyiha nomi ba'zisida tushib qolgandi).

- Props: `onBack`, `orderNumber`, `projectName?` (sxemasida bu maydon yo'q post — KROMKA — bermaydi, o'shanda satr chizilmaydi), `className?`, `children?` (o'ngdagi farqlar: progress, tugmalar, badge).
- Chaqiruvchilar: `TmoView`, `UpakovkaView`, `KromkaView`, `PrisadkaView` (ROVER va SCX shoxlari), `PostQueueView`. Raqam `min-w-0`/`truncate` ichida — uzun raqamda ellips.

### `frontend/src/components/Terminal/PostProgress.tsx`

**Maqsadi:** post ekranining yagona UZOQDAN o'qiladigan raqami — qancha ish qoldi. Beshta ekran (kromka, prisadka, rover, post navbati, TMO) shu bitta komponentdan foydalanadi.

- O'lcham sanoat HMI qoidasidan: qulay o'qish masofasi ≈ harf balandligi × 150…200. 17" monoblokda piksel qadami ~0.26 mm, ya'ni `text-base` (16px) ≈ 3 mm ≈ 0.5 m (operator terminalga borishi kerak edi), `text-5xl` (48px) ≈ 9 mm ≈ 1.5 m. Qolgan hamma narsa — qatorlar, o'lchamlar, kodlar — qo'l uzunligida o'qiladi va kattalashtirilmaydi.
- Raqam **qoldiq**, "bajarildi" emas: operatorning savoli "yana qancha qoldi?", `4/25` dan uni hisoblab olish qo'lqopda va arra shovqinida ortiqcha ish. Bajarilgan/jami kichik shriftda yonida (kontekst).
- Hammasi bajarilganda raqam o'rniga yashil **TAYYOR**.

### `frontend/src/components/Terminal/ScanStrip.tsx`

**Maqsadi:** oxirgi skan natijasi + BEKOR QILISH tugmasi, har post ekranining tepasida (`PostScreen` orqali). Tsex shovqinida ovoz signaliga ishonib bo'lmaydi. `LastScan` tipi ham shu yerda eksport qilinadi. Props: `scan`, `canUndo` (60 s oynasi — taymer chaqiruvchida), `onUndo`, `birlik?` (KROMKA'da "qirra" — qoldiq nimada o'lchanishini aytadi). Chek chiqarishdan tug'ilgan AVTO-skanda muvaffaqiyat banneri ko'rsatilmaydi — filtr `scan.recorded` payload'idagi `auto` bayrog'i bo'yicha (server `finalize_scan(auto=True)` bilan qo'yadi), POST NOMI bo'yicha emas: ROVER ham chek chiqaradi (roverda kesiladigan detal), ham qo'lda skan oladi (arradan kelganning rover qadami) — farq skanning kelib chiqishida. Katakning yashil bo'lishi o'zi tasdiq, banner dublikat edi, undagi BEKOR QILISH esa yarim-tuzoq — skanni qaytarib chek bayrog'ini qoldirardi (to'liq bekor — katak dialogida). Qo'l skani va xato/rad hamma postda ko'rinaveradi.

### `frontend/src/components/Terminal/ShiftGate.tsx`

**Maqsadi:** "Kim ishlayapti?" — smenaning o'zi, login ekrani emas. Monoblok TERMINAL hisobi bilan bir marta, o'rnatishda kirgan va boshqa hech qachon parol termaydi (tsexda klaviatura yo'q); bu yerda esa KIM ishlayotgani yoziladi — autentifikatsiya emas, atributsiya. `routes/terminal.tsx` ikkala eksportni ham ishlatadi.

- `ShiftGate({ employees, pending, onStart, onCancel? })` — brigada bo'sh bo'lganda ish maydonini yopadigan `absolute inset-0 z-30` to'siq: postga biriktirilgan hodimlar `h-20` katta tugmalarda (ism + `position`), pastda "Yoki beyjikni skanerlang". Hodim biriktirilmagan bo'lsa yo'l ko'rsatuvchi matn ("Admin Hodimlar bo'limida postni belgilashi kerak"). `onCancel` berilsa pastda "Bekor qilish" tugmasi chiqadi — "+ Qo'shish" oqimidan orqaga yo'l; qurilma hisobida ekran smenasiz ishlay olmaydi, o'shanda berilmaydi. Qulf va to'liq ekran to'siqlari (`KioskOverlays`) bundan ustunroq.
- `CrewChips({ crew, onEnd, onAdd })` — sarlavhadagi brigada (`md:` dan yuqorida): ikki kishi bir ish markazida ishlashi mumkin, shuning uchun SHERIK ismlari doim ko'rinib turadi — ketgan odam o'chirishni unutsa, qolgani begona ismni ko'radi va bosib qo'yadi. Kirgan odamning O'ZI ro'yxatda yo'q (`crew.filter((s) => !s.is_me)`): u kimligini login allaqachon aytgan. Qurilma hisobida (TERMINAL) hech kim `is_me` bo'lmaydi, ya'ni u yerda hamma ism chiqadi — monoblokda kim ishlayotganini faqat shu ro'yxat aytadi. Ism bosilsa o'sha smena yakunlanadi (`onEnd`), "+ Qo'shish" keyingi tanlovni `join` rejimiga o'tkazadi (`onAdd`).

### `frontend/src/components/Terminal/KioskOverlays.tsx`

**Maqsadi:** ikkita to'siq ekrani — majburiy to'liq ekran (`requestFullscreen` user-gesture talab qiladi, shuning uchun tugma) va qulf. Ikkalasi bitta ichki `Overlay` maketidan. `requestFullscreen()` rad etilishi mumkin (iframe, brauzer sozlamasi), shuning uchun promise `.catch` bilan tutiladi va operator "To'liq ekranga o'tib bo'lmadi" toast'ini ko'radi — aks holda jim unhandled rejection bo'lardi.

### `frontend/src/components/Terminal/useKiosk.ts`

**Maqsadi:** kiosk qobig'i. `useKioskShell(canReload)` — kontekst menyusini o'chirish (sensorda long press chekni bekor qilish uchun kerak), to'liq ekran holati (Fullscreen API yoki `display-mode`), yangi build tekshiruvi (`/` HEAD ETag, 5 daqiqada) va XAVFSIZ paytda avto-reload (`canReload()` — xarita yopiq va `QUIET_MS`=2 daqiqa skan bo'lmagan). `useScanFocus(enabled, inputRef)` — avto-skan inputini fokusda ushlash (2 s interval) va fokussiz terilgan birinchi belgida fokusni qaytarish. `terminal.tsx` `enabled` ni ARRA xaritasi ochiqda (input yashirin) VA tasdiq dialogi ochiqda (`logoutOpen`/`endFor`/`undoFor`) o'chiradi: input modaldan tashqarida, ya'ni aks holda interval fokusni tortadi, Radix fokus tuzog'i darhol qaytaradi — bemaqsad focus/blur churn. Dialog yopilgach effekt qayta yoqiladi va `focus()` darhol chaqiriladi.

### `frontend/src/components/Terminal/useTerminalScan.ts`

**Maqsadi:** skan yo'naltirgichi — bitta QR to'rt manzilga ketishi mumkin: beyjik UUID → smena (u ham 2 s duplikat to'sig'i ostida — skanerning takror o'qishi ikkita `POST /terminal/session` yuborardi; `routes/terminal.tsx` da `startShift.isPending` ikkilamchi to'siq); ekranning o'z sinki (`viewScanRef` — qadoqlash/TMO, chunki detal qaysi qadoqqa tushishini faqat o'sha ekran biladi va qadoq QR'i `PK-...` umumiy yo'lda rad etilardi); KROMKA/OVAL lokal tekshiruvi (`kromkaScanRef`, 5 s to'siq, picker ochiq bo'lsa `/qr/{qr}/order` bilan proyektni o'zi ochadi); qolgani umumiy skan (2 s duplikat to'sig'i). KROMKA/OVAL to'sig'i HAR urinishni hisoblaydi, faqat muvaffaqiyatlisini emas: ilgari u faqat yozilgan skanda o'rnatilardi, ya'ni rad etilgan QR to'siqni umuman ishga tushirmasdi va skanerning takror o'qishi har safar yangi `/qr/{qr}/order` so'rovi bilan yangi toast berardi (o'lchandi: bir xil QR 3 marta → 3 so'rov, 3 bip; endi 1 so'rov + 2 ta "endigina skan qilindi").

### `frontend/src/components/Terminal/usePrintLabel.ts`

**Maqsadi:** yorliq chop etish mutatsiyasi — `CutmapView` (ARRA xaritasi) va `PrisadkaView` (ROVER/PRISADKA) baham ko'radi: `TerminalService.printInstanceLabel` + toast + `handleError`; `scope` ("cutmap" | "prisadka") qaysi terminal keshi (`["terminal", scope]`) yangilanishini belgilaydi. Shu fayl `useCancelLabel()` ni ham eksport qiladi (`cancelInstanceLabel`, ikkala kesh — terminal va admin — invalidatsiyasi) — uni ham CutmapView, ham PrisadkaView chaqiradi.

### `frontend/src/components/Terminal/audio.ts`

**Maqsadi:** skan ovoz signallari (tsex shovqinida majburiy) — WebAudio, internetsiz ishlaydi: `playSuccess` (600 Hz qisqa), `playError` (200 Hz uzun), `playWarning` (2×800 Hz). `AudioContext` birinchi bipda yaratiladi va har bipdan oldin `state === "suspended"` bo'lsa `resume()` qilinadi — stanok posti kiosk rejimida brauzer foydalanuvchi bosmasdan ochiladi, autoplay siyosati bo'yicha kontekst to'xtatilgan holda tug'iladi va resume'siz WS orqali kelgan majburiy signal jim qolardi. Uchta chaqiruvchi bor: `routes/terminal.tsx` (skan natijasi — `E008` va ATX qoldiq QR'ida `playWarning`, qolgan xatolarda `playError`; smena ochish success/error; bekor qilish → `playWarning`; oflayn `E007` → `playError`), `useTerminalScan.ts` (qulflangan ekran va KROMKA/OVAL 5 s to'siqda `playWarning`, KROMKA/OVAL skani topilmasa/xato bo'lsa `playError`) `TmoView.tsx` (qabul javobi) va `UpakovkaView.tsx` (qadoqqa skan javobi).

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

- zod: `current_password` va `new_password` (IKKALASI ham `passwordSchema`), `confirm_password` + mos kelish refine'i; `mode: "onSubmit"`. Joriy parol ham kuchlilik tekshiruvidan o'tadi, ya'ni eski zaif parol so'rov yuborilishidan oldin klientda rad etiladi.
- Mutation: `UsersService.updatePasswordMe({ body })`; muvaffaqiyatda toast + `form.reset()`.
- Uchchala maydon `PasswordInput` (ko'rish/yashirish ko'zchali) bilan, `aria-invalid={fieldState.invalid}` uzatiladi.

---

## ui komponentlari — `frontend/src/components/ui/`

shadcn/ui asosidagi 25 ta primitiv. Ko'pchiligi standart generatsiya; quyidagi jadvalda qaysilari o'zgartirilgani ko'rsatilgan.

**Tizim faqat light rejimda ishlaydi.** shadcn generatsiyasidan kelgan 23 ta `dark:` utility klass yettita fayldan olib tashlangan (`badge` 3, `button` 7, `checkbox` 3, `dropdown-menu` 1, `input` 2, `select` 3, `tabs` 4). Shu bilan birga `src/index.css` dagi `@custom-variant dark (&:where(.dark, .dark *));` qatori ham o'chirilgan — u faqat `dark:` klasslarni `prefers-color-scheme` dan uzib, o'lik `.dark` klassiga bog'lash uchun kerak edi; qo'llanadigan `dark:` klass qolmagach hack'ning ma'nosi yo'q (`index.css` da o'rniga qisqa izoh turibdi). Toaster ham `theme="light"` da qattiq belgilangan, tema tokenlari dark uchun qayta belgilanmagan.

| Fayl | Komponent(lar) | Asos | Custom o'zgartirish |
|---|---|---|---|
| `avatar.tsx` | Avatar, AvatarImage, AvatarFallback | Radix Avatar | Yo'q (standart) |
| `badge.tsx` | Badge, badgeVariants | cva | Deyarli standart (`rounded-full` shakl); `dark:` klasslar olib tashlangan |
| `button.tsx` | Button, buttonVariants | cva + Slot | **Qo'shimcha o'lchamlar**: `icon-sm` (size-8), `icon-lg` (size-10); `dark:` klasslar olib tashlangan |
| `card.tsx` | Card, `cardSurface` konstanta | native div | **Soddalashtirilgan custom**: faqat yuza (`rounded-xl border bg-card`), shadcn'ning 5 qismli Header/Title/... API'si ataylab yo'q; `<ul>`/`<details>` kabi teglar uchun `cardSurface` klassi ham eksport |
| `checkbox.tsx` | Checkbox | Radix Checkbox | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `date-picker.tsx` | DatePicker | react-day-picker + Popover | **To'liq custom** (pastda) |
| `dialog.tsx` | Dialog, DialogContent, DialogHeader/Footer/Title/Description, ... | Radix Dialog | Yo'q (`showCloseButton` prop — yangi shadcn standarti) |
| `dropdown-menu.tsx` | DropdownMenu* (Item `variant="destructive"` bilan), 15 ta eksport | Radix DropdownMenu | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `form.tsx` | Form, FormField, FormItem/Label/Control/Message, useFormField | react-hook-form + Radix Label | Yo'q |
| `input.tsx` | Input | native `<input>` | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `label.tsx` | Label | Radix Label | Yo'q |
| `loading-button.tsx` | LoadingButton (`ButtonProps` — fayl ichida, eksport emas) | `buttonVariants` (button.tsx dan import) | **To'liq custom** (pastda) |
| `password-input.tsx` | PasswordInput | `Input` + Button | **To'liq custom** (pastda) |
| `popover.tsx` | Popover, PopoverTrigger, PopoverContent | Radix Popover | Deyarli standart (`rounded-xl`, `p-3`, `align="start"`) |
| `select.tsx` | Select, SelectTrigger/Content/Item/..., 10 ta eksport | Radix Select | `dark:` klasslar olib tashlangan; `SelectContent` default'i `align="start"` (shadcn'da `center`) + `sideOffset={4}` — boshqa suzuvchi qatlamlar bilan bir xil |
| `separator.tsx` | Separator | Radix Separator | Yo'q |
| `sheet.tsx` | Sheet, SheetContent (side: top/right/bottom/left), ... | Radix Dialog | Yo'q; mobil sidebar shu orqali |
| `sidebar.tsx` | 24 ta eksport: SidebarProvider, Sidebar, SidebarTrigger, SidebarMenu*, useSidebar, ... | shadcn sidebar block | **Ha, o'zgartirilgan** (pastda) |
| `skeleton.tsx` | Skeleton | div + animate-pulse | Yo'q |
| `sonner.tsx` | Toaster | sonner kutubxonasi | **Kichik custom**: `theme="light"` qattiq belgilangan (next-themes yo'q), lucide ikonkalar to'plami (success/info/warning/error/loading), CSS o'zgaruvchilar mapping'i |
| `switch.tsx` | Switch | Radix Switch | Yo'q (butun frontendda YAGONA chaqiruvchi — `agents.tsx` dagi chek chiqarish `can_print` almashtirgichi) |
| `table.tsx` | Table, TableHeader/Body/Footer/Row/Head/Cell/Caption | native table | **Stil custom**: konteyner `rounded-lg border`, TableHeader `bg-muted/50`, TableHead `h-11 text-xs font-semibold uppercase tracking-wider`, TableCell `px-4 py-3 whitespace-nowrap` |
| `tabs.tsx` | Tabs, TabsList, TabsTrigger, TabsContent | Radix Tabs | `dark:` klasslar olib tashlangan (boshqasi standart) |
| `textarea.tsx` | Textarea | native `<textarea>` | Yo'q (standart shadcn; anketa "Qo'shimcha izoh" maydoni uchun qo'shilgan) |
| `tooltip.tsx` | Tooltip, TooltipTrigger/Content/Provider | Radix Tooltip | Yo'q (delayDuration=0) |

### `frontend/src/components/ui/sidebar.tsx` (custom tafsilotlari)

Eng katta ui fayl (~740 qator, 24 eksport). shadcn'ning rasmiy sidebar blokiga asoslangan, quyidagi o'zgarishlar bilan:

- **Cookie'dan boshlang'ich holatni o'qish**: standart shadcn faqat cookie'ga *yozadi*; bu yerda `getInitialOpen()` funksiyasi `sidebar_state` cookie'sini o'qib, sahifa yangilanganda ochiq/yopiq holatni tiklaydi (`useState(getInitialOpen)` lazy initializer).
- `SidebarTrigger` sr-only matni dinamik va o'zbekcha: `open ? "Menyuni yig'ish" : "Menyuni ochish"`; mobil `Sheet` ning sr-only sarlavhasi "Yon menyu", tavsifi "Mobil yon menyu".
- `sidebarMenuButtonVariants` o'lchamlari brendga moslangan: `default: "h-8 text-sm rounded-lg"`, `lg: "... rounded-xl data-[state=closed]:rounded-lg"`.
- `SidebarHeader` (`p-2 pb-3`) va `SidebarFooter` (`gap-3 p-2`) padding'lari sozlangan; `SidebarInset` `bg-transparent` va **`min-w-0` SHART**: u flex elementi va sukut `min-width: auto` bilan keng kontent (loglar jadvali, chip qatori) SAHIFANI kengaytirib yubordi — sarlavhadagi tugmalar ekrandan chiqib ketdi va skroll sahifa darajasida paydo bo'lib, ichkaridagi `overflow-x-auto` konteynerlari ishlamay qoldi.
- Muhim konstantalar: `SIDEBAR_WIDTH = "16rem"`, `SIDEBAR_WIDTH_ICON = "3rem"`, `SIDEBAR_WIDTH_MOBILE = "18rem"`, klaviatura yorlig'i **Ctrl/Cmd+B** (`SIDEBAR_KEYBOARD_SHORTCUT = "b"`).
- Mobil rejimda `Sheet` ichida render qilinadi (`useIsMobile` — `@/hooks/useMobile`); `useSidebar()` hooki `{ state, open, setOpen, openMobile, setOpenMobile, isMobile, toggleSidebar }` kontekstini beradi — `Sidebar/Main.tsx` va `Sidebar/User.tsx` shundan foydalanadi.

### `frontend/src/components/ui/dialog.tsx` (custom qism)

`DialogContent` ga `max-h-[calc(100dvh-2rem)] overflow-y-auto` qo'shilgan (2026-09-03): shadcn default'ida balandlik chegarasi yo'q edi — terminaldagi `PartCard` dialogi (chizma + QR + tugmalar, ~790px) 17" monoblokning 768px ekraniga sig'may, SARLAVHASI (№ va nusxa ID) ekrandan tepaga chiqib ketar va aylantirib ham bo'lmasdi. Endi har qanday uzun dialog ichida aylanadi.

### `frontend/src/components/ui/loading-button.tsx` (custom)

shadcn'da yo'q, loyihaga qo'shilgan komponent. `buttonVariants` ni `button.tsx` dan import qiladi (BITTA manba — avvalgi copy-paste nusxa divergensiya bergani uchun birlashtirilgan; `icon-sm`/`icon-lg` o'lchamlari ham ishlaydi) va ustiga `loading` prop qo'shadi.

```tsx
function LoadingButton({ loading = false, disabled, asChild = false, ... }: ButtonProps)
// loading=true -> disabled + <Loader2 className="mr-2 h-5 w-5 animate-spin" />
```

Barcha mutation submit tugmalarida ishlatiladi — jami 20 fayl (PersonDialog, AddClient, AddOrder, EditOrder, MachineAssign, OrderMatrix, CustomRoutes, CutmapView, PartCard, PrisadkaView, UpakovkaView, ConfirmDialog, ChangePassword, UserInformation, login formasi, anketa saqlash paneli, employees beyjik dialogi (`BadgeDialog` — "Chop etish" va "Yo'qolgan — yangi beyjik berish"), work-centers ish markazi formasi, buyurtma sahifasi amallari, printers agent qo'shish formasi) va uzoq davom etadigan amallarda — `PrisadkaView` dagi SCX "Hammasini yuklab olish" tugmasi jonli progress yozuvi bilan ("Yuklanmoqda… 12/81").

### `frontend/src/components/ui/password-input.tsx` (custom)

shadcn'da yo'q. `ui/input` ni compose qiladi (`pr-10` bilan), o'ng tomonida ghost `Button size="icon-sm"` — `Eye`/`EyeOff` ikonkasi bilan parolni ko'rsatish/yashirish (`showPassword` state, `type` almashadi; aria-label "Parolni yashirish/ko'rsatish"). `React.ComponentProps<"input">` propslarini o'tkazadi (forwardRef yo'q — React 19 uslubi); `aria-invalid` ni chaqiruvchi o'zi uzatadi. `UserSettings/ChangePassword.tsx`, `routes/login.tsx` va `People/PersonDialog.tsx` da ishlatiladi — jami uchta chaqiruvchi; oddiy `Input type="password"` frontendda umuman qolmagan.

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

routes (settings)                               routes (__root / layout)
  ├─ UserInformation                              ├─ SidebarProvider (ui/sidebar)
  └─ ChangePassword                               ├─ AppSidebar (NAV_ITEMS eksporti)
                                                  │    ├─ Main (rolga qarab bandlar)
                                                  │    └─ User (avatar + logout)
                                                  └─ NotFound / ErrorComponent

Tashqi bog'liqliklar: @/client (UsersService, ClientsService, OrdersService, TerminalService va
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
