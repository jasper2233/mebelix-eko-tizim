# TODO — ochiq ishlar

To'liq audit sanasi — **2026-09-27**. Kod bazasi — **`e4dc7fb`**. Tuzatishlar
(`4bc2c9c`, `3b574e5` va keyingi hujjat commit'lari) 2026-09-27 da `main` ga
qo'shilib prodga chiqdi (`a45977b`).

Bu ro'yxat eski TODO.md o'rnini bosadi (81 band, baza `e234cf2`). Eski bandlarning
har biri joriy kodda qayta tekshirildi:

| Eski band | Soni | Nima bo'ldi |
| --- | ---: | --- |
| tuzatildi | 67 | audit commit'larida; 5 tasi boshqa band bilan bir xil edi |
| shu ro'yxatga o'tdi | 8 | 1, 3, 6, 7, 9, 10, 31, 32 |
| tuzatildi (CLAUDE.md) | 1 | 47 |
| rad etildi | 3 | 58, 76, 81 — pastdagi bo'limda |
| yopildi | 1 | 52 (avvalroq tuzatilgan) |
| serverda tuzatildi | 1 | 80 — journald drop-in yo'q edi, 2026-09-27 da qayta yaratildi |

**Qanday tekshirildi.** Git kuzatadigan 335 kod/konfig va 24 hujjat fayli
auditorga boshidan oxirigacha o'qitildi. O'qilgan qatorlar agent
transkriptlaridan skript bilan sanaldi. Quyidagilar o'qilmadi:
- generatsiya qilingan fayllar (18 ta);
- binar va lock fayllar (60 ta);
- prodga qo'llangan migratsiyalar (61 ta; ular faqat docs/04 ni tekshirishda manba bo'ldi);
- `scripts/catalog.csv`.

Topilmani ikkinchi, mustaqil agent qayta tekshirdi va tasdiqladi. Xulq haqidagi har da'vo bir martalik skript bilan
ishga tushirildi: vaqtinchalik Postgres/Redis, haqiqiy endpoint funksiyalari.
Quyidagi "Dalil" qatorlari o'sha chiqishlardan olingan. Bu yerga faqat
**qaror talab qiladigan** bandlar kiritildi: mahsulot qarori, prod ma'lumotini
tekshirish, migratsiya yoki API o'zgarishi. Xavfsiz tuzatishlar allaqachon
qilingan.

Tuzatishlar branch orqali boradi; `main` ga push = tsexga deploy (19:00 dan keyin).

| Og'irlik | Soni |
| --- | ---: |
| yuqori | 1 |
| o'rta | 8 |
| past | 9 |

---

## Yuqori

### 1. Asosiy detal marshruti tahrirlansa, unga biriktirilgan mayda detal tekshirilmaydi (eski #1)

- **Joy:** `backend/app/api/routes/orders/matrix.py:156` (`to_check`), `_check_assembly_match` — `:307`
- **Muammo:** Invariant: mayda detalning oxirgi amali asosiy detal marshrutida bo'lishi
  shart. Bu invariant faqat BOLA tomonidan tekshiriladi, chunki `to_check` ga faqat
  o'zi ota detalga ega detal tushadi. Faqat asosiy detal marshrutini qayta chizgan
  PATCH qabul qilinadi, garchi bolaning birikish amali endi unda bo'lmasa ham.
  Skanda `_close_assembly_children` (`services/scanning.py:462`) bunday bolani
  o'tkazib yuboradi. Birikkan bolaning dumi (UPAKOVKA/TMO) yo'q. Natijada u hech
  qachon yopilmaydi. `start_order_production` ham birikish nuqtasini tekshirmaydi.
- **Dalil** (haqiqiy `edit_order_matrix`, vaqtinchalik DB):
  ```
  step1 A: [7, 11, 16] B: [7, 11]
  step2 (faqat A ga PATCH route_codes=[7,8]) ACCEPTED
  after: A: [7, 8, 16] B: [7, 11] B.parent: 1 B last op 11 in A? False
  nazorat: bola PATCH [7,12] -> 403 «A marshrutida «G petlya chapdan» yo'q ...»
  ```
  Skandagi oqibat kodni o'qib aniqlangan, ishga tushirilmagan.
- **Taklif:** Detalning o'z marshruti o'zgarsa, uning tirik bolalarini ham `to_check`
  ga qo'shing (`Part.assembly_parent_id == part.id`, `is_deleted == False`). Marshrut
  o'zgarishi deganda `route_codes`, `parent_changed` qayta qurish va `stages` toggle
  tushuniladi. Tekshiruv batch oxirida (`:218`) ishlaydi, shuning uchun ota va
  bolani birga qayta chizgan PATCH baribir o'tadi. `start_order_production` ga ham
  shu tekshiruvni qo'shish mumkin.
- **Nega hozir emas:** Texnolog qaysi UX'ni istashini aytishi kerak: rad etish yoki
  ogohlantirish. Bu o'zgarish skandagi yig'ma yopilishga bog'liq.

## O'rta

### 2. `is_custom` qayta belgilansa `ix_part_route_part_seq` buziladi — 500 (eski #3)

- **Joy:** `backend/app/api/routes/orders/matrix.py:124-137`
- **Muammo:** `is_custom` almashganda "restore" manbasining soft-delete qilingan
  HAMMA qatorlari tiklanadi. Detal standart turganda bosqich toggle'i
  `max(seq)+1` da TIRIK MANUAL qator qo'shadi. Qayta belgilashda bu qator
  o'chirilmaydi (drop = AUTO), eski MANUAL qatorlar esa qaytadi. Oqibatda bitta
  `(part_id, seq)` ga ikki tirik qator to'g'ri keladi → `UniqueViolationError` →
  500. Frontend aynan shu ketma-ketlikni yuboradi: `OrderMatrix.tsx` `is_custom`
  va `stages` ni alohida saqlaydi. `ccd241f` redraw yo'lini tuzatgan edi, bu yo'l
  esa qolgan.
- **Dalil** (haqiqiy `edit_order_matrix`; qatorlar `(seq, code, source, is_deleted)`):
  ```
  1 tick+draw [1,7]: (1,1,auto,T) (2,16,auto,T) (1,1,manual,F) (2,7,manual,F) (3,16,manual,F)
  2 untick:          (1,1,auto,F) (2,16,auto,F) (1,1,manual,T) (2,7,manual,T) (3,16,manual,T)
  3 BOYOQ yoqildi:   ... (2,8,manual,F)
  4 re-tick RAISED: UniqueViolationError ... "ix_part_route_part_seq"
  ```
- **Taklif:** Yalpi tiklashni to'xtating. Ikki yo'l bor:
  - (a) skansiz tirik MANUAL qatorlarni avval hard-delete qiling, keyin faqat
    to'qnashmaydigan avlodni tiklang;
  - (b) qayta belgilashda tiklamang, qo'lda chizilgan marshrutni joriy kodlardan
    `_set_custom_route` bilan qayta quring.

  Eng oxirgi chora — unique xatoni ushlab, o'zbekcha 409 qaytarish.
- **Nega hozir emas:** Real buyurtmalarda qaysi marshrut qatorlari tirilishini
  hal qiladi. Bu tiklash semantikasi bo'yicha qaror.

### 3. Bekor qilingan buyurtmani o'chirish: brak/kromka o'lchovi bo'lsa 500

- **Joy:** `backend/app/api/routes/orders/lifecycle.py:378` (`delete_order`, CANCELLED shoxi)
- **Muammo:** Superuser hard-delete quyidagilarni o'chiradi: `pachka_item`, `pachka`,
  `scan`, `waste_item`, `order_file`, `part_route`, `part_instance`, `part`,
  `product`. U `part_defect` va `kromka_measurement` ga tegmaydi. Bu jadvallarning
  FK'lari NO ACTION. Oqibatlar:
  - buyurtmada bitta brak qatori bo'lsa (skansiz bo'lsa ham) → `ForeignKeyViolation`
    → 500;
  - bekor qilingan skanga bog'langan Pico o'lchovi bo'lsa ham xuddi shunday.

  Bundan tashqari faqat `.b3d` o'chiriladi: Bazis'ning `.json`/`.png` yondosh
  fayllari diskda qoladi.
- **Dalil:** Vaqtinchalik DB'da CANCELLED buyurtma yaratildi va haqiqiy `delete_order`
  chaqirildi:
  ```
  none           -> OK "Buyurtma o'chirildi"
  defect_noscan  -> ForeignKeyViolation "part_defect_instance_id_fkey"
  defect         -> ForeignKeyViolation "part_defect_scan_id_fkey"
  kromka         -> ForeignKeyViolation "kromka_measurement_scan_id_fkey"
  ```
- **Taklif:** DELETE'dan oldin bog'liq qatorlarni hal qiling. Variantlar:
  - (a) buyurtmada `part_defect` bo'lsa, o'zbekcha 403 bilan rad etish;
  - (b) `part_defect WHERE order_id=:id` ni o'chirish;
  - (c) `kromka_measurement` dagi `scan_id`/`instance_id`/`order_id` ni NULL qilish.

  Qaysi variant tanlansa ham Bazis yondosh fayllarini ham o'chiring
  (`model_paths`). docs/03 dagi `DELETE /api/v1/orders/{id}` qatorini moslang.
- **Nega hozir emas:** Brak va Pico tarixini saqlash, o'chirish yoki o'chirishni
  bloklash — prod ma'lumoti bo'yicha mahsulot qarori.

### 4. Mijozni o'chirish oynasi backend rad etadigan yo'lni maslahat beradi

- **Joy:** `frontend/src/components/Clients/DeleteClient.tsx:34`, `backend/app/api/routes/clients.py:252`
- **Muammo:** Ikkala matn bir xil maslahat beradi: buyurtmalarni "boshqa mijozga
  o'tkazing yoki bekor qiling". Amalda bu maslahat ko'p hollarda ishlamaydi:
  - mijozni almashtirish faqat DRAFT holatida mumkin (boshqa holatda 403);
  - bekor qilingan buyurtma `is_deleted=False` bo'lib qoladi, shuning uchun
    `delete_client` uni sanaydi va 409 qaytaradi.

  Amalda ishlaydigan yo'llar ikkita:
  - qoralamani o'chirish yoki boshqa mijozga o'tkazish;
  - buyurtmani bekor qilish, keyin superuser uni o'chiradi (tirik skan bo'lmasa).
- **Dalil:**
  ```
  production:       move 403 | cancel OK | delete client 409 «... 1 ta buyurtma bor»
  technical_review: move 403 | cancel OK | delete client 409
  draft:            move OK  | cancel 403 «Qoralama bekor qilinmaydi» | delete client OK
  ```
- **Taklif:** Ikki yo'ldan birini tanlang:
  - ikkala matnni haqiqiy yo'lga moslang;
  - yoki `delete_client` CANCELLED buyurtmani sanamasin.

  Qaysi biri tanlansa ham ikkala matn birga o'zgaradi.
- **Nega hozir emas:** Qaror kerak: qoida qoladimi yoki bekor qilingan buyurtma
  o'chirishni to'smaydimi.

### 5. "Boshqa" lavozimdagi hodimni tahrirlash uning postlarini o'chiradi (eski #7)

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:216`
- **Muammo:** Misol: hodimning postlari bor, lavozimi esa katalogda yo'q erkin matn
  ("Katta arrachi", "Haydovchi").
  - `positionOf()` uni "Boshqa" deb ko'rsatadi.
  - `postsFor()` postlarini formada ATAYLAB saqlaydi (`:85-87`).
  - Payload esa `kind === "boshqa"` da `assigned_post_ids: []` yuboradi.
  - `switching` false bo'lgani uchun tasdiq oynasi chiqmaydi.

  Oynani ochib telefonni tuzatish kifoya: postlar o'chadi. Shundan keyin badge
  terminalda E006 bilan rad etiladi (`services/scanning.py:191`).
- **Dalil:** Haqiqiy `positionOf`/`postsFor` va payload ifodasi node'da ishga tushirildi:
  `{"stored":[1],"position":"Katta arrachi","shown":"Boshqa","formPosts":[1],"assigned_post_ids":[]}`.
- **Taklif:** Bitta qoidani tanlang:
  - (a) postlar saqlanadi — `form.posts` ni har doim yuboring; qo'lda "Boshqa" ga
    o'tilganda esa `[]` bering;
  - (b) "Boshqa" da post yo'q — `postsFor` dagi fallback'ni olib tashlang.

  docs/06 hozir joriy xulqni yozadi (postlar o'chadi). (a) tanlansa, docs/06 ham
  o'zgaradi.
- **Nega hozir emas:** Badge/terminal ruxsatini o'zgartiradi. Mahsulot qarori kerak.

### 6. Hisob yaratish: yetim hodim, dublikat hodim, parol/login klientda tekshirilmaydi (eski #6, #9, #10)

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:226` (`createEmployee`), `:278` (parol), `frontend/src/lib/validation.ts:5`
- **Muammo:** Uch bog'liq nuqson bor.
  - **Hodim hisobdan oldin yaratiladi.** Sex hodimi login bilan yaratilganda avval
    `createEmployee` commit bo'ladi, keyin `createUser` chaqiriladi. `createUser`
    422/409 qaytarsa, oyna ochiq qoladi, `person` esa `null`. Qayta bosishda
    `createEmployee` yana chaqiriladi va ikkinchi hodim paydo bo'ladi. Birinchisida
    badge bor, hisob yo'q.
  - **Parol tekshirilmaydi.** Parol faqat bo'sh emasligi tekshiriladi.
    `passwordSchema` ni faqat `ChangePassword.tsx` ishlatadi.
  - **Login tekshirilmaydi.** Login uchun frontend tekshiruvi umuman yo'q (backend:
    kamida 2 belgi, `^[a-z0-9]+$`).

  Serverning 422 ro'yxati `utils.ts:75` da umumiy "Kiritilgan ma'lumot noto'g'ri"
  bo'lib chiqadi, ya'ni admin qaysi qoida buzilganini ko'rmaydi. Maydon ostida
  statik ko'rsatma bor.
- **Dalil:**
  - Haqiqiy `mutationFn` stub servislar bilan ishga tushirildi:
    `calls: createEmployee, createUser, createEmployee, createUser, updateEmployee`,
    `employee rows created: 2`.
  - `UserCreate(password='12345678')` → 422 "Parolda kamida bitta kichik harf bo'lsin".
  - `'Sherzod'`, `'a'`, `'a.b'` loginlari → 422 ro'yxat.
- **Taklif:**
  - Yaratilgan `employeeId` ni `useRef` da saqlang: qayta urinishda `updateEmployee`
    chaqirilsin.
  - `missing` zanjiriga `passwordSchema.safeParse` qo'shing (tahrirda "bo'sh —
    o'zgarmaydi" qoidasi saqlanadi).
  - `validation.ts` ga `_USERNAME_FIELD` oynasini qo'shing (trim, 2–20,
    `/^[a-z0-9]+$/`, o'zbekcha xabar).
- **Nega hozir emas:** Hisob/badge yaratish oqimi. Xabar matni va qayta urinish
  dizayni kelishilishi kerak.

### 7. Ko'paytirilgan (`mult>1`) raskroy listidagi biznes qoldiqlari bitta yorliqqa tushadi

- **Joy:** `frontend/src/components/Terminal/CutmapView.tsx:259`, `backend/app/services/giblab/ingest.py` (atx sikli)
- **Muammo:**
  - Ingest har pattern katagiga bitta `WasteItem` yaratadi, `mult` necha bo'lishidan
    qat'i nazar.
  - CutmapView `mult>1` pattern'ni `mult` ta jismoniy list kartasiga yoyadi
    (`1c1`, `1c2`, ...). Hammasida bir xil `atx` turadi.
  - Oqibatda N ta jismoniy qoldiqqa bitta QR va bitta yorliq to'g'ri keladi.
  - `wastePrinted` faqat `atx` bo'yicha kalitlangan. Bittasi chop etilsa, hamma
    nusxa yashil bo'ladi va qolganlari "Bu qoldiq chiqarilgan..." bilan rad etiladi.
  - `w.sheet_no === sheet?.no` yoyilgan listlarda hech qachon mos kelmaydi
    (`1` va `"1c1"`).
- **Dalil:** `ingest.py` ning haqiqiy atx qatorlari stub DB bilan bajarildi. Model:
  bitta `mult=3` pattern ichida bitta biznes qoldig'i. Natija: `physical sheets: 3`,
  `WasteItem rows: 1`; har karta `green True sheet_no_match False`. Frontend qismi
  TSX mantig'ining Python takrori, brauzerda emas.
- **Taklif:** Har jismoniy qoldiqqa bitta yorliq kerak bo'lsa:
  - ingest `mult` ta `WasteItem` yaratsin va nusxa indeksini saqlasin;
  - CutmapView kartani `(atx, nusxa)` bo'yicha topsin;
  - `wastePrinted` ham `(atx, nusxa)` bo'yicha kalitlansin.

  Mavjud buyurtmalar uchun backfill qarori ham kerak.
- **Nega hozir emas:** Ingest ma'lumot modeli va QR raqamlanishini o'zgartiradi.
  Mahsulot qarori kerak.

### 8. ✅ ESKIRDI (2026-10-16): Sotuv listi: kasr miqdorni terib bo'lmaydi — "1,5" 15 bo'ladi

- **Holat:** `sotuv.tsx` endi faqat `/warehouse/doc?turi=chiqim` ga yo'naltiradi; yangi hujjatda
  miqdor/narx/chegirma matn bo'lib saqlanadi (`doc.tsx` `Line`), son faqat hisobda `parseNum` bilan olinadi.

- **Joy:** `frontend/src/routes/_layout/sotuv.tsx:500` (`RaqamKatak`)
- **Muammo:** Input boshqariladi va `korinish` son qiymatdan quriladi. "1," terilsa
  `son("1,")` 1 beradi. Input "1" bo'lib qayta chiziladi va vergul yo'qoladi.
  Keyingi "5" natijani 15 qiladi. `kasr` faqat miqdor ustunida bor. Qator summasi
  va chop etiladigan shartnoma jami 10 barobar oshib ketadi. Nuqta bilan ham shunday.
  Joylashtirish (paste) ishlaydi.
- **Dalil:** jsdom va repo'ning React'i bilan klavishma-klavish terildi. Natija:
  `"1" -> 1`, `"," -> input "1"`, `"5" -> 15`.
- **Taklif:** Fokusda xom matnni saqlang: `const [draft, setDraft] = useState<string | null>(null)`.
  `value={draft ?? korinish}`; onChange'da `setDraft(v); onChange(son(v))`;
  onBlur'da `setDraft(null)`.
- **Nega hozir emas:** Shartnoma chop etadigan forma. Brauzerda qo'lda tekshirish kerak.

### 9. ✅ HAL QILINDI (2026-10-16, «ombor egasi»): `catalog_import --apply` omborchi o'zgartirgan narx/holat/izohni qaytarib yozadi

- **Hal:** `bazaga()` mavjud qatorda nom, narx, holat va izohni yozmaydi, o'chirilganni tiklamaydi — docs/14 §8.4.

- **Joy:** `scripts/catalog_import.py:225`
- **Muammo:** `PATCH /catalog/items/{id}` da omborchi `purchase_price`, `sale_price`,
  `status` va `note` ni o'zgartira oladi (`CatalogEdit.tsx`). Import esa mavjud
  qatorda HAMMA CSV maydonlarini `setattr` qiladi. Faqat `quantity`, `min_quantity`
  va `location` saqlanadi. `CatalogItemUpdate` docstring'idagi qoidaga ko'ra import
  yozadigan maydon PATCH'ga kirmaydi — bu yerda qoida buzilgan.
- **Dalil:** import → PATCH (12345 / 99999 / Arxiv / izoh / quantity=7) → qayta import.
  Natija: `F-AK-001-01 976.00 1317.00 Aktiv None 7.000`, ya'ni faqat miqdor saqlandi.
- **Taklif:** Egasini tanlang:
  - (a) varaq egasi — to'rt maydonni PATCH'dan va `CatalogEdit.tsx` dan olib tashlash,
    so'ng `make frontend-gen`;
  - (b) ombor egasi — `bazaga()` ularni faqat yangi qatorda yozadi.

  Qaysi biri tanlansa ham docs/14 §3 va §4 moslanadi.
- **Nega hozir emas:** Narx va holat egasi kimligi — mahsulot qarori.

## Past

10-band (Bazis yuklashda takror mahsulot kodi — 500) 2026-09-27 da hal qilindi: yuklash
endi kod va nomi mos mahsulotni oladi. 15-band (downtime sinxroni yumshoq o'chirilgan
andon hodisalaridan to'xtash yasardi) 2026-10-16 da hal qilindi: `sync_machine`,
`_bosh_yurish` va `sync_downtimes` `is_deleted` ni filtrlaydi; prodda qolgan soxta
yozuvlar deploy'dan KEYIN `scripts/downtime_deleted_events.sql` bilan tozalanadi.
Raqamlar ataylab o'zgartirilmadi — kod va hujjatlar «TODO.md #N» deb havola qiladi.

### 11. `GET /tmo/orders/{order_id}` ni hech kim chaqirmaydi

- **Joy:** `backend/app/api/routes/tmo.py:192`
- **Muammo:** 2026-09-04 dan TMO sahifasi faqat `acceptIntoTmo` ni chaqiradi.
  Frontend, bridge-agent va skriptlarda `read_tmo_order` chaqiruvchisi yo'q.
  Docstring'lar 2026-09-27 da to'g'rilandi, endpoint esa qoldi.
- **Taklif:** Endpoint'ni o'chiring. docs/03 qatorini va docs/04 dagi eslatmani
  olib tashlang, so'ng `make frontend-gen` ni ishga tushiring.
- **Nega hozir emas:** Ochiq API/klient yuzasini o'zgartiradi. docs/03 uni ataylab
  saqlagan.

### 12. `FileKind.LABEL_PDF` hech qachon yaratilmaydi va o'qilmaydi

- **Joy:** `backend/app/models/enums.py:167`
- **Taklif:** Avval prod'da tekshiring: `SELECT count(*) FROM order_file WHERE kind='label_pdf'`
  0 bo'lishi kerak. Keyin a'zoni, `lib/mes.ts` dagi yorliqni va docs/04 dagi
  qiymatni o'chiring, so'ng `make frontend-gen`. Ustun VARCHAR
  (`native_enum=False`), migratsiya kerak emas.
- **Nega hozir emas:** Qolgan qator enum orqali yuklanmay qoladi, shuning uchun avval
  prod tekshiruvi.

### 13. O'lik `pachka.shipped_at` va `PachkaStatus.SHIPPED` — va'da qilingan migratsiya yozilmagan

- **Joy:** `backend/app/models/pachka.py:33`, `backend/app/models/enums.py:83`
- **Muammo:** Ustun va status'ni hech qaysi kod yozmaydi ham, o'qimaydi ham. Model
  izohi ularni migratsiya bilan tushirishni va'da qiladi, lekin bunday migratsiya yo'q.
- **Taklif:** Avval prod'da tekshiring: `status='shipped'` yoki `shipped_at IS NOT NULL`
  qatorlar 0 bo'lishi kerak. Keyin YANGI migratsiya bilan ustunni tushiring,
  model va enum'dan olib tashlang, `make frontend-gen` ni ishga tushiring va
  docs/04, docs/09 ni moslang.
- **Nega hozir emas:** Migratsiya va prod tekshiruvi kerak.

### 14. Buyurtma summasida `max_digits` yo'q — 10^12 dan katta summa 500 beradi (eski #31)

- **Joy:** `backend/app/schemas/orders.py:118-119`, `:129-130`
- **Muammo:** Sxema istalgan manfiy bo'lmagan `Decimal` ni qabul qiladi, ustun esa
  `Numeric(14,2)`. Overflow `DBAPIError` bo'lib chiqadi va uni hech narsa ushlamaydi.
  Natija: o'zbekcha 422 o'rniga 500. Frontend inputni cheklaydi, shuning uchun
  xatoga faqat to'g'ridan-to'g'ri API chaqiruvi bilan yetib boriladi.
- **Dalil:** haqiqiy `create_order` → `NumericValueOutOfRangeError: numeric field overflow`.
- **Taklif:** `Field(default=None, ge=0, max_digits=14, decimal_places=2)` yoki
  `le=Decimal("999999999999.99")`, keyin `make frontend-gen`.
- **Nega hozir emas:** OpenAPI o'zgaradi. `decimal_places=2` hozir jim yaxlitlanayotgan
  qiymatlarni rad eta boshlaydi, shuning uchun chegara qarori kerak.

### 16. XNC: teshik qatori soni `ac` chegarasiz; `nan`/`inf` koordinata jim o'tadi

- **Joy:** `backend/app/services/giblab/xnc.py:93` (`_hole_array`), `_eval_expr` (`:59`)
- **Muammo:**
  - `ac` sikl soni sifatida chegarasiz ishlatiladi: 12 baytlik atribut millionlab
    bore dict yasaydi. `parse_project` web jarayonining threadpool'ida ishlaydi.
    Korpusda `ac` doim 1. Faqat texnolog yuklay oladi.
  - `float("nan")`, `"inf"` va `1e308*10` ifodalari ParseError bermaydi:
    koordinata/chuqurlik `nan`/`inf` bo'lib o'tadi.
- **Dalil:**
  - `ac="1000000"` → `1000000 bores 2.62 s 229 MiB peak`.
  - Joriy kodda: `x="nan"` → `bores=[(nan, 50.0, 10.0)]`; `x="1e308*10"` → `inf`;
    `dp="nan"` → chuqurlik `nan`.
  - Buning keyingi oqibati (JSON/SCX) tekshirilmagan.
- **Taklif:**
  - `_hole_array` da chegaradan katta `count` ni rad eting (yoki
    `(count-1)*step > dx/dy` bo'lsa): `ParseError(f"XNC: teshik qatori juda katta (ac={count})")`.
  - `num()` natijasi `math.isfinite` bo'lmasa, ParseError bering.
- **Nega hozir emas:** Chegara (eng uzun haqiqiy 32 mm javon qatori) egasi bilan
  kelishilishi kerak. Noto'g'ri chegara real yuklashni rad etadi.

### 17. «Asl hajmda yangi oynada ochish» havolasi rasmni ochmaydi, yuklab oladi (eski #32)

- **Joy:** `frontend/src/components/Anketa/RoomPhotos.tsx:224`, `backend/app/api/routes/orders/files.py:247`
- **Muammo:** `FileResponse(filename=...)` `content-disposition: attachment` yuboradi.
  Yuqori darajadagi navigatsiya bunday faylni yuklab oladi. Havola matni va docs/06
  esa ochishni va'da qiladi.
- **Dalil:** `FileResponse` sarlavhalari chiqarildi:
  `content-disposition: attachment; filename="mijoz_namuna.jpg"`. Brauzerda ishga
  tushirilmagan (RFC 6266).
- **Taklif:** Ikki yo'l bor:
  - (a) `image/*` uchun `content_disposition_type="inline"`;
  - (b) havola matnini "yuklab olish" ga o'zgartirish.

  Qaysi biri tanlansa ham docs/06 moslanadi.
- **Nega hozir emas:** Mahsulot tanlovi. (a) umumiy yuklash endpoint'iga tegadi.

### 18. `TablePagination` oxirgi sahifadan o'tib ketganda teskari oraliq ko'rsatadi

- **Joy:** `frontend/src/components/Common/TablePagination.tsx:29`
- **Muammo:** `page` `pages - 1` ga qisilmaydi. Misol: `/clients` oxirgi sahifasidagi
  yagona mijoz o'chirildi. Natija: "100 tadan 101–100" va "2 / 1", jadval bo'sh,
  qaytishning yagona yo'li «Oldingi».
- **Dalil:** Haqiqiy komponent `react-dom/server` bilan chizildi:
  `page=1 total=100: 100 tadan 101–100 Oldingi 2 / 1 Keyingi`.
- **Taklif:** Komponentda `if (total > 0 && page >= pages) onPage(pages - 1)` effekt,
  yoki uch chaqiruvchida (clients/warehouse/logs) qisish.
- **Nega hozir emas:** Uch reestr sahifasi. Dizayn tanlovi kerak.

### 19. KromkaLive har WS o'lchovini keyingi 60 s refetch'dan keyin ikki marta ko'rsatadi

- **Joy:** `frontend/src/components/WorkCenters/KromkaLive.tsx:53`
- **Muammo:** WS `kromka.measure` `live` ga qo'shiladi va o'sha yerda qoladi. Xuddi shu
  qator DB'ga yozilgan, shuning uchun refetch uni `data` da ham qaytaradi. Birlashtirish
  dedup qilmaydi, kalitlar esa farq qiladi (`+00:00` va `Z`).
- **Dalil:** Haqiqiy `bind_measurement` + `read_kromka_measurement_feed` natijasiga
  KromkaLive'ning 49 va 53-qatorlari qo'llandi: `rows: 2`, ikkalasi bitta o'lchov.
- **Taklif:** `data` kelganda u qamragan `live` qatorlarini tashlang: bir stanok
  bo'yicha eng yangi `data` vaqtigacha, yoki `dataUpdatedAt` bo'yicha `live` ni
  tozalang.
- **Nega hozir emas:** Dedup qoidasi bir soniyadagi takrorlarni va agentning eski
  vaqtli offline batch'larini hisobga olishi kerak.

### 20. Ish markazini o'chirish tugmasi kechadan qolgan ochiq smenani ko'rmaydi

- **Joy:** `frontend/src/routes/_layout/work-centers.tsx:100` (`blockers()`)
- **Muammo:** Ochiq smena to'sig'i `overview.on_shift` dan olinadi, u esa faqat BUGUN
  ochilgan sessiyalarni sanaydi. Server `_blockers` `crew_sessions` ni ishlatadi, u
  HAMMA ACTIVE sessiyani sanaydi va sessiya muddati yo'q. Oqibat: tugma faol
  ko'rinadi, server esa 409 beradi. Izoh 2026-09-27 da to'g'rilandi.
- **Dalil:** Sessiya `created_at = now() - 26h` qilindi. Natija:
  - `server _blockers(1): ['ochiq smena: 1 ta']`
  - `frontend blockers(): []`
- **Taklif:** `MachineOverview` ga muddatsiz `open_sessions` qo'shing (`crew_sessions`
  bilan bir xil so'rov), `make frontend-gen` ni ishga tushiring va `blockers()` da
  shu sonni ishlating.
- **Nega hozir emas:** API javob sxemasi o'zgaradi. Server baribir 409 beradi, ya'ni
  zarar faqat noto'g'ri ko'rsatma.

---

## Mahsulotlar ombori — qilinadigan ishlar (2026-10-16)

«Qudrat Ombor» dizaynining uch bosqichi prodda (`7a1228c`, `1336686`, `24d2277` — docs/14 §8–10).
Quyidagilar keyingi ish. Lokal muhit, orakllar va deploy tartibi — `CLAUDE.md`.

### O1. Prodda Sex xo'jaligi (`S`) katalogi bo'sh

- `ombor_seed.py` faqat M/F/X ni to'ldirgan. Sex tovarlarini (zapchast, asbob, kanselyariya, xo'jalik,
  upakovka) kiritish kerak: Nomenklatura → «Sex xo'jaligi» → «Yangi mahsulot» yoki «Excel'dan yuklash»
  (shablonda `S-ZP`/`S-KG` namunalari bor). Ro'yxatni ombor egasi beradi.
- Kiritilgach qoldiq — Inventarizatsiya yoki Kirim hujjati bilan (qo'lda emas).

### O2. 3-bosqichni prodda brauzerda tekshirish

- Lokalda tekshirilgan (docs/14 §10.3 oxiri), prodda — yo'q. Tekshirish: menyuda «Sex xo'jaligi · F3» va
  «Inventarizatsiya»; F3 → sexga kirim → F9; «Sex sarfi» CSV; bitta kichik guruhda inventarizatsiya
  (faqat haqiqiy sanash bilan — tasdiqlangan INV qoldiqni o'zgartiradi va qaytarilmaydi).

### O3. Inventarizatsiya qoralamasi yo'q

- `/warehouse/inv` da kiritilgan sonlar faqat sahifa xotirasida: yangilansa yoki guruh almashsa yo'qoladi.
  Katta guruhni (LDSP — 1 000+ pozitsiya) bir o'tirishda sanash qiyin.
- Taklif: sotuv/kirimdagidek `localStorage` (`mebelix.ombor.inv.<guruh>`) yoki `stock_doc` da `inv`
  qoralamasi. Birinchisi — kichik, faqat bitta brauzer.

### O4. Inventarizatsiyada materiallar

- `M` guruhida zaxiraga olinmagan (`tracked=false`) dekorlar ham chiqadi. Kerak bo'lsa — faqat `tracked`
  yoki qoldig'i bor pozitsiyalar filtri. Ombor egasi bilan kelishish.

### O5. Sex sarfi chegarasi

- `GET /stock/sex-log` sukut bo'yicha oxirgi 5 000 qator, sahifa sana filtri yo'q. Yil oxirida sana
  oralig'i (`from`/`to`) kerak bo'ladi.

### O7. Dekorlarga sinf berilmagan — dekor sotib bo'lmaydi (2026-10-17, prodda o'lchangan)

- `warehouse_pricing.tier_prices` bo'sh, 2 131 `M` pozitsiyasidan **0 tasiga** sinf berilgan, ya'ni
  dekorning sotuv narxi hisoblanmaydi. Omborchi `/warehouse/panel` da oltita raqamni (LDSP/LMDF × S/M/P)
  kiritib, Nomenklaturada dekorlarga sinf berishi kerak (docs/14 §8.1).
- `markup_all` ham qo'yilmagan: furnitura sotuvi faqat qo'lda kiritilgan `p` dan keladi.

### O8. Prodda `skladchi` hisobi yo'q (2026-10-17)

- Prodda `omborchi` degan hisob bor, lekin u **boshqa odam**: `UserRole.OMBORCHI` — TAYYOR mahsulot
  (TMO) omborchisi, tsex roli (`models/enums.py:26`). Mahsulotlar ombori roli — `skladchi`. Ya'ni
  `0cac878` dagi to'liq (tekis) ombor menyusini hozir hech kim ko'rmaydi; boshqaruv faqat
  «Mahsulotlar ombori» → `/warehouse/hisobot` bandini ko'radi (docs/14 §11.2).
- Kerak: `UserRole.SKLADCHI` roli bilan hisob ochish (Hisoblar sahifasidan, ombor egasi hal qiladi).

### O9. Prodda 7 furnitura narxsiz + bo'sh maydonlar (2026-10-17)

- `F-AK-029-01`, `F-RC-015-05`, `F-RC-025-11`, `F-RC-026-12`, `F-RL-015-01/02/03` — dizayn katalogida
  bor, lekin narxsiz, shuning uchun `ombor_seed.json` ga ham tushmagan. Narxni egasi beradi.
- Qolgan bo'sh maydonlar uchun prodda `ombor_seed.py --apply` yurgizish mumkin: `070b3bd` dan keyin u
  sotilib nolga tushgan qoldiqni qaytarib tiriltirmaydi (docs/14 §8.5).

### O6. Eski brauzer listlari

- 2026-10-16 gacha `/sotuv` da `localStorage` (`mebelix.sotuv-listi.v1`) da qolgan listlar ko'chirilmadi
  (docs/14 §9.3). Omborchi so'rasa — qo'lda qayta kiritiladi; kod kerak emas.

---

## Tekshirilib rad etilganlar

Bu topilmalar ikkinchi tekshiruvda rad etildi. Qayta ko'tarishdan oldin sababini o'qing.

- **`KromkaMeasurement` Numeric ustunlari `float` deb annotatsiya qilingan, lekin `Decimal`
  bo'lib yuklanadi** (`backend/app/models/kromka.py:40`). Nomuvofiqlik haqiqiy, lekin
  hozir nuqson emas. Har o'quvchi qiymatni `float()`/`son()` ga o'raydi
  (`terminal.py` buni izohda aytadi), yozuvchi esa faqat qiymat beradi. Tuzatish
  jonli kromka/tablo yo'lida runtime turini o'zgartirardi.
- **docs/02 `rate_limit.py` bo'limi `rate_limiter.client` ning boshqa ishlatilishini
  aytmaydi** (eski #58). Bo'limda yolg'on gap yo'q. jti tombstone ishlatilishi
  docs/03 da hujjatlangan.
- **Telefon qoidasi to'rtta `_check_phone` validator orqali ulangan, `_Phone` alias'i
  bor** (eski #76). Bu nuqsonsiz takrorlanish. Hammasi bitta `validate_phone` ni
  chaqiradi, JSON Schema va xatolar bir xil (ishga tushirib tekshirildi).
- **Raskroy xaritasida kesilgan/kesilmagan faqat rang bilan farqlanadi** (eski #81).
  Bu UX taklifi, nuqson emas. Rang ataylab tanlangan (`SheetSvg.tsx` izohlari),
  list darajasida «List tugadi» belgisi ham bor.
