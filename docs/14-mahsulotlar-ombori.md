# 14. Mahsulotlar ombori — katalog

Tsexning katalogi: **material, furnitura va xizmat** pozitsiyalari, har birining
qat'iy kodi, artikuli, narxi va ombordagi qoldig'i. Manba — Google Sheets'dagi
`Katalog.xlsx`; MESda u `catalog_item` jadvalida va `/warehouse` sahifasida.

2026-09-25 holatiga **2662 pozitsiya**: M 2131, F 490, X 41.

## 1. Kodlash tizimi

Kod TO'RT qismdan iborat va **hech qachon o'zgarmaydi**:

```
M  –  LD  –  054  –  03
│     │     │      └── VARIANT  (2 raqam) — matritsa, rang yoki o'lcham
│     │     └───────── MODEL    (3 raqam) — dekor yoki model raqami
│     └─────────────── GURUH    (2 harf)  — LD, RC, PT …
└───────────────────── KATALOG  (1 harf)  — M / F / X
```

| Harf | Katalog | Nima kiradi |
| --- | --- | --- |
| `M` | Material | Plita, dekor, stolishnitsa, fasad paneli |
| `F` | Furnitura | Petlya, yo'naltirgich, tutqich, kromka, krepyoj |
| `X` | Xizmat | Raskroy, prisadka, kromkalash, montaj |

**Variant raqami** har bo'limda o'z ma'nosiga ega. `M-LD` va `M-LM` (LDSP va
LMDF dekorlari) da u MATRITSA va QAT'IY biriktirilgan:

| 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| glyanets | glatkiy | tekstura | shagren | kamin | koja | shpon | tomchi |

Qolgan bo'limlarda variant ketma-ket beriladi (01, 02, 03 …) va rang yoki
o'lchamni bildiradi.

Qat'iy qoidalar (katalog egasining qarori, varaqdagi «KODLASH TIZIMI» bo'limi):

- Kod bir marta beriladi va o'zgarmaydi — mahsulot sotuvdan chiqsa ham kodi band qoladi
- Bir kod = bir mahsulot; o'chirilgan pozitsiyaning kodi qayta ishlatilmaydi
- O'lcham har doim MM da (`2750x1830x16`, `350`)

## 2. Jadval — `catalog_item`

Migratsiya `6d9d9f645802`. **Bitta jadval**: M, F va X bir xil kod tuzilishiga va
bir xil narx/qoldiq ustunlariga ega, uchta jadval bo'lsa har so'rov `UNION`
bo'lardi va «bir kod = bir mahsulot» qoidasini hech kim ushlab turolmasdi — u
aynan shu jadvaldagi **unikal indeks** (`ix_catalog_item_code`).

| Ustun | Izoh |
| --- | --- |
| `code` | To'liq kod (`M-LD-054-03`) — unikal, katalogning yagona kaliti |
| `catalog`, `group_code`, `model_no`, `variant_no` | Kodning qismlari ALOHIDA ustun sifatida: kategoriya daraxti va saralash shulardan, matnni qayta bo'lish shart emas |
| `group_name` | Guruh nomi (`LDSP dekorlar`) — kodda yo'q, varaqdan keladi |
| `name`, `unit`, `size_text`, `thickness_mm`, `article` | Nomi, birligi (`list`/`dona`/`metr`), o'lchami, qalinligi, zavod artikuli |
| `decor_no`, `decor_name`, `matrix`, `image_url` | Dekor bo'yicha pozitsiyalar uchun (`M-LD`, `M-LM`) |
| `quantity`, `min_quantity`, `location` | Ombor: qoldiq, eng kam qoldiq (undan past — «kam qolgan»), javon |
| `purchase_price`, `sale_price`, `status` | Xarid/sotuv narxi (`Numeric`), `Aktiv` yoki `Arxiv` |
| `note`, `extra` | Izoh va varaqdagi qolgan maydonlar (`Rang`, `Xarakteristika`, `Nachinka`, `Model nomi`, `Tur`, `Variant`) JSONB da |

Alohida `catalog_group` jadvali **yo'q**: guruh 33 ta va nomi kod bilan birga
varaqdan keladi, daraxt esa `GROUP BY catalog, group_code` bilan quriladi.
Alohida jadval bo'lsa import har safar ikkitasini sinxronlashi kerak edi.

Nega `stock_item` emas: u (va `stock_move`, `sale`, `payment`) — olib tashlangan
materiallar ombori modulidan qolgan **yetim jadval**, prodda bo'sh turibdi va
`LEGACY_TABLES` da e'tiborsiz qoldiriladi (`docs/04` §4.4). Ustunlari boshqa
modelga tegishli edi.

## 3. Yuklash — `scripts/catalog_import.py`

Ikki qadam, ikki sabab:

```bash
# 1. Varaqdan CSV (faqat lokalda — xlsx binar, diff'i ko'rinmaydi)
cd backend && uv run python ../scripts/catalog_import.py --xlsx ../docs/Katalog.xlsx

# 2. CSV dan bazaga (lokalda yoki serverda — CSV deploy bilan boradi)
cd backend && uv run python ../scripts/catalog_import.py --apply
```

Serverda:

```bash
cd /opt/mebelix-mes && docker compose -f docker-compose.prod.yml exec -T api \
  python /app/scripts/catalog_import.py --apply
```

Qoidalar:

- **Upsert KOD bo'yicha.** Qayta yurgizish xavfsiz: mavjud pozitsiya yangilanadi,
  takror yozuv paydo bo'lmaydi.
- **`quantity`, `min_quantity`, `location` TEGILMAYDI.** Ular omborchining ishi va
  varaqda umuman yo'q — import ularning ustiga yozib ketsa, qoldiq har yuklashda
  nolga qaytardi.
- Kod qoidaga mos kelmasa satr **tashlanadi** va sababi `stderr` ga yoziladi:
  katalogning butun ma'nosi kodda, «deyarli to'g'ri» kod keyin hech narsaga ulanmaydi.
- Ma'lumot MIGRATSIYADA emas: katalog o'zgarib turadi, prodga qo'llangan
  migratsiya esa tahrirlanmaydi.

Varaqdan **olinmaydigan** ustunlar: `Nom holati` (hamma satrda bir xil matn —
legenda), `Nima tuzatildi` (varaqni tozalash jurnali), `Foyda` va `Marja %`
(sotuv − xarid), `1 list m²` (o'lchamdan kelib chiqadi). `Maxsulotlar`
varag'idagi `RASM` ustuni buzuq formula (`#ERROR!`) — rasm havolasi `Dekorlar`
varag'idan `Dekor №` bo'yicha ulanadi.

## 4. API — `/api/v1/catalog`

| Metod | Yo'l | Kim | Nima qiladi |
| --- | --- | --- | --- |
| GET | `/catalog/groups` | `WarehouseReadUser` | Kategoriya daraxti: katalog → guruh, har birida nechta pozitsiya + katalog bo'yicha jami |
| GET | `/catalog/items` | `WarehouseReadUser` | Ro'yxat. Filtrlar: `catalog`, `group_code`, `status`, `low_stock`, `search` (kod, nom, artikul, dekor nomi bo'ylab), `skip`/`limit` |
| PATCH | `/catalog/items/{id}` | `WarehouseUser` | Qoldiq, eng kam qoldiq, joylashuv, narxlar, holat, izoh. Kod/nom/o'lcham bu yerdan O'ZGARMAYDI — ular varaqdan keladi |

Rollar (`api/deps.py`):

- **O'qish** — menejer, texnolog, direktor, **skladchi**. Katalogda narx bor,
  shuning uchun tsex rollariga ochilmaydi.
- **Yozish** — menejer va **skladchi**. Texnolog va direktor katalogni ko'radi,
  lekin qoldiqni ular yuritmaydi.

⚠️ **`skladchi` ≠ `omborchi`.** `omborchi` — TAYYOR mahsulot ombori (TMO)
omborchisi: tsex roli, `POST_ROLES` da `PostCode.TMO` ga bog'langan, beyjik bilan
kiradi va `_layout` uni `/terminal` ga yuboradi — ya'ni u bu sahifani hech qachon
ocha olmaydi. Xomashyo ombori uchun 2026-09-25 da alohida OFIS roli qo'shildi:
**`skladchi`**, ekranda «Mahsulot omborchisi». U parol bilan kiradi, kirgach
to'g'ri `/warehouse` ga tushadi (yo'naltirish FAQAT o'z yo'llaridan tashqarida —
`_layout.tsx: OMBOR_YOLLARI` = `/warehouse`, `/sotuv`, `/settings`; ular ham `_layout`
ichida, shartsiz yo'naltirish cheksiz halqa berardi. `/settings` 2026-09-27 da qo'shildi —
ilgari «Sozlamalar» havolasi uni omborga qaytarardi, parolini o'zi almashtira olmasdi) va
menyuda ombor, uning uch kategoriyasi va sozlamalaridan boshqa band ko'rmaydi:
LIVE Tablo va Stanoklar tsex ekranlari, ombor ishiga aloqasi yo'q. Enum
`native_enum=False` bo'lgani uchun migratsiya kerak emas (`models/enums.py:8`).

## 5. Sahifa — `/warehouse`

`routes/_layout/warehouse.tsx`. Filtrlar kodning tuzilishini takrorlaydi:

- **Katalog harfi** — YON MENYUDA, «Mahsulotlar ombori» ostida
  (Material / Furnitura / Xizmat). Yopiq «Mahsulotlar ombori»ni bosish butun katalogni
  ochib bo'limlarni ko'rsatadi, ochiqni bosish bo'limlarni yopadi; boshqa sahifada menyu qisqa turadi. Sahifaning o'zida tab YO'Q: bitta tanlov ikki
  joyda ikki xil ko'rinishda turardi. Sahifa sukut bo'yicha HAMMASINI ko'rsatadi
  (`/warehouse` qidiruvsiz), kategoriya esa manzilga yoziladi —
  `/warehouse?katalog=M`. Tanlangani sarlavha ostida aytiladi
  («Material · 2131 pozitsiya»), aks holda qaysi ro'yxat ochiqligini hech narsa
  ko'rsatmasdi.
- **Guruh** — `SelectField` (35 ta, menyuga sig'maydi). Yorlig'i nomi,
  yonida kod va sanoq. Tanlov qiymati **to'liq kod** (`M-LG`), faqat guruh harfi
  emas: `LG` ikki katalogda ham bor — `M-LG` (LEGE fasad paneli) va `X-LG`
  (logistika), shuning uchun harfning o'zi bilan filtrlaganda katalog tanlanmagan
  (butun katalog) holatda boshqa katalogning pozitsiyalari qo'shilib ketardi.
- **Holat** va «**Kam qolgan**» — omborchining birinchi savoli «nimani buyurtma
  qilish kerak»; chegara qo'yilmagan pozitsiya bu ro'yxatga tushmaydi.

Chap ustunli daraxt ISHLATILMAYDI (2026-09-25 da almashtirildi): u 256 px joy
yeb, jadvalni gorizontal aylantirishga majbur qilardi — `Sotuv` ustuni ekrandan
chiqib ketgandi va filtr loyihaning qolgan sahifalariga o'xshamasdi.

Katalog va guruh MANZILDA (`?katalog=M&guruh=M-LD`, `validateSearch`): menyudagi
havola shu bilan ishlaydi va havola nusxalab yuborilsa ham o'sha ro'yxat
ochiladi. Holat va «Kam qolgan» esa sahifaning o'z holatida — ular o'tkinchi.

Jadval: kod (monoshrift, birinchi ustun — omborchi javonda aynan shuni izlaydi),
nomi (ostida guruh · o'lcham · matritsa), artikul, qoldiq, joy, xarid va sotuv
narxi. Chegaradan past qoldiq **qizil**, tooltip'da chegara ko'rsatiladi. Qalam
tugmasi (faqat yozish huquqi bo'lsa) ombor maydonlarini tahrirlaydigan dialogni
ochadi.

Tekshiruv: `scripts/oracles/catalog_oracle.py` — **36/36** (kod formati, takror
yo'qligi, rollar huquqi — skladchi o'qiydi va yozadi, texnolog faqat o'qiydi, TMO
omborchisi kirmaydi, daraxt sanoqlari, filtrlar va qidiruv, artikulning matn bo'lib
qolishi, dekor rasmining ulanishi, qoldiq yozilishi, «kam qolgan», qayta
importda qoldiqning saqlanishi).

## 6. Sotuv listi — `/sotuv`

Ombor sahifasidagi «**Sotuv listi**» tugmasi ochadi. Manba — tsexning qog'oz
namunasi (`docs/mebelix-sotuv-listi.html`, mustaqil prototip); MESga
ko'chirilganda ikki narsa o'zgardi:

1. **Ranglar MESniki** — prototip apelsin (`#ef7d1a`) edi, sahifa esa loyihaning
   o'z tokenlarida (kechki ko'k + oltin) va o'z komponentlarida (`Table`,
   `Input`, `SelectField`) yozilgan.
2. **Artikul HAQIQIY.** Prototipdagi `makeCode()` mahsulot nomidan
   `FUR-BEL-001` yasardi — omborda unday kod yo'q edi. Endi qator KATALOGDAN
   tanlanadi (`CatalogPicker` → `GET /catalog/items?search=`): kod, zavod
   artikuli, birlik va **sotuv narxi** o'zi to'ladi. Narx qulflanmaydi —
   chegirma va kelishuv narxi sotuvchining ishi.

Katalogda yo'q narsa uchun qator erkin matn bo'lib qolaveradi (bir martalik
xizmat, mijozning o'z materiali) — ostida «katalogda yo'q — erkin qator» deb
turadi.

Ikki ko'rinish, bitta ma'lumot:

| Ko'rinish | Nima | Qog'oz |
| --- | --- | --- |
| **List** | Mijoz va buyurtma kartalari, qatorlar (soni · narx · chegirma · summa), jami, imzo chiziqlari | A4 **ko'ndalang** — yetti ustun (ekrandagi o'chirish ustuni chop etilmaydi) |
| **Shartnoma** | Spesifikatsiya (kod · artikul ustuni bilan), jami summa **so'z bilan** (`lib/mes: moneyToWords`), alohida shartlar, imzo bloklari | A4 **bo'yiga**, serif shrift |

`@page` qoidasi ko'rinishga qarab almashadi; sahifadagi boshqaruvlar
`print-hide` bilan chop etishdan chiqariladi (`index.css` dagi umumiy qoida).

**Bazaga yozilmaydi** (2026-09-25): list brauzerda saqlanadi
(`localStorage`, `mebelix.sotuv-listi.v1`) va qog'oz hujjat sifatida chop
etiladi. Ya'ni u boshqa kompyuterda ko'rinmaydi va MES hisobotlariga kirmaydi.
Bazaga ko'chirilsa: `sale_sheet` + `sale_sheet_row` jadvallari, buyurtmaga
bog'lanish va saqlash kaliti versiyasini oshirish kerak.

## 8. «Qudrat Ombor» dizayni — 1-bosqich: Nomenklatura va narx boshqaruvi (2026-10-16)

Egasi `Ombor Dastur.html` (Claude dizayni, «Qudrat Ombor») asosida omborni TUBDAN qayta qurishni
so'radi — UX deyarli bir xil, lekin MES ichida (MES menyusi va komponentlari, dizayndagi joylashuv,
ustunlar va tugmalar). Uch bosqich, har biri alohida deploy:

1. **Nomenklatura + Boshqaruv paneli** (shu bo'lim) — narx sinflari, kurs, ustama, kartochka,
   yangi mahsulot, o'chirish, Excel import/eksport, ABC;
2. **Kirim va Sotuv hujjatlari** — FIFO partiyalar, harakat tarixi, qoralama → tasdiq, `F2`/`F4`/`F9`,
   «Hujjatlar»; `/sotuv` (brauzerdagi list) shu hujjatga almashadi, «Shartnoma» chop etish ko'chadi;
3. **Sex xo'jaligi va Inventarizatsiya.**

**Egasining qarorlari (2026-10-16):** bosqichma-bosqich; boshlang'ich qoldiq va narx — dizayn
fayli ichidagi katalogdan; `/sotuv` yangisiga almashadi; ko'rinish — MES ichida, dizayn tartibida.

### 8.1 Narx qoidalari (`backend/app/services/warehouse.py`)

Narx endi OMBORNIKI — katalog varag'i uni qayta yozmaydi (quyida 8.4). Qoidalar dizayndagi
`markupPrice` / `setTierPrice` / `setUsd` bilan bir xil:

| Kim | Sotuv narxi | Qachon qayta hisoblanadi |
|---|---|---|
| Furnitura (`F`) | `round(xarid × (1 + ustama/100) / 100) × 100` — 100 so'mgacha. Ustama: pozitsiyaniki → guruhniki → umumiy; hech biri yo'q — sotuv qo'lda qoladi | ustama, xarid yoki kurs o'zgarganda |
| LDSP / LMDF dekori (`M-LD`, `M-LM`) | sinf (Standart / Medium / Premium) belgilangan bo'lsa — shu sinfning BITTA list narxi | sinf yoki sinf narxi o'zgarganda — shu sinfdagi HAMMA dekor birdan |
| Xarid dollarda (`purchase_usd`) | so'mdagi xarid = `round($ × kurs)` | kurs o'zgarganda (so'mda qo'lda kiritilsa dollar narxi bekor bo'ladi) |

Sozlama bitta JSON — `system_setting.warehouse_pricing` (`WarehousePricing`: `usd_rate`, `tier_prices`,
`markup_all`, `markup_groups`). `PUT /catalog/pricing` uni saqlaydi va HAMMA pozitsiyaning narxini
qayta hisoblaydi (≈2 700 qator — bir zumda); o'zgarish auditga eski va yangi qiymat bilan yoziladi.

### 8.2 Jadvalga qo'shilgan ustunlar (`f3c8a2d6e915`)

`description` (tavsif — rang / o'lcham, dizayndagi `o`), `purchase_usd`, `tier` (S/M/P), `markup_pct`,
`tracked` (material «zaxiraga olingan»). Kam qoldiq ogohlantirishi materialda FAQAT zaxiraga
olinganlarda — 2 000+ dekorning hammasi omborda turmaydi, aks holda ro'yxat doim qizil bo'lardi.
Xizmatda qoldiq ham, chegara ham yo'q.

### 8.3 Kod berish va o'chirish

Yangi pozitsiya kodi serverda: guruhning keyingi modeli (`F-RC-104-01`) yoki tanlangan modelning keyingi
varianti (`F-RC-008-10`). O'chirish YUMSHOQ: pozitsiya ro'yxatdan chiqadi, kodi band qoladi va qayta
berilmaydi (o'chirilganlar ham hisobga olinadi). Qoldiqli pozitsiyani o'chirishda ogohlantirish chiqadi.

### 8.4 Varaq bilan munosabat (TODO #9 yopildi — «ombor egasi» varianti)

`scripts/catalog_import.py --apply` mavjud pozitsiyada endi faqat katalog ma'lumotini (guruh nomi,
o'lcham, dekor, rasm, artikul, `extra`) yangilaydi: nom, xarid, sotuv, holat, izoh, qoldiq, chegara va
joy — OMBORNIKI, yozilmaydi. O'chirilgan pozitsiyani varaq qayta tiriltirmaydi.

### 8.5 Boshlang'ich ma'lumot — `scripts/ombor_seed.py`

Dizayn fayli ichidagi katalogdan chiqarilgan `scripts/ombor_seed.json` (kodlar `scripts/catalog.csv`
bilan 2662/2662 mos). FAQAT BO'SH maydon to'ldiriladi — omborchi kiritgani hech qachon ustidan
yozilmaydi, skriptni ikki marta yurgizish ham xavfsiz. Lokal bazada: qoldiq 323 ta furniturada,
chegara 446 ta, tavsif 2 592 ta; xarid va sotuv narxlari dizaynda ham, varaqda ham AYNAN bir xil
(farq 0). `--apply` siz faqat hisobot beradi.

### 8.6 Sahifalar

- `/warehouse/panel` — **Boshqaruv paneli** (dizayndagi «Ombor holati»): sinf narxlari jadvali (LDSP / LMDF
  × S / M / P, ostida nechta dekor), dollar kursi, furnitura ustamasi — umumiy va 18 guruh bo'yicha.
  Maydon fokusdan chiqqanda saqlanadi.
- `/warehouse?katalog=M|F|X&guruh=…` — **Nomenklatura**: butun katalog bitta so'rovda
  (`GET /catalog/all`) va qidiruv/filtr brauzerda — darhol; ekranda 100 qator, «Yana ko'rsatish».
  Ustunlar: kod, nom (ostida tavsif), birlik, qoldiq, xarid, xarid $, min, (furniturada) ustama %
  — qatorning o'zida tahrirlanadi, (materialda) sinf, sotuv, sotuv $, ABC. Xizmatda — xarajat va sotuv.
  Kam qoldiq — qizil chap chiziq va pushti fon. Materialda: zaxira va sinf filtrlari,
  «Ko'rinayotgan N ta dekorga: Standart / Medium / Premium». Belgilanganlarga: sinf, zaxiraga olish /
  chiqarish, o'chirish. Jadval ustida «Yangi mahsulot» QATORI (kod oldindan ko'rinadi, saqlangach qator
  ochiq qoladi), «Excel'ga chiqarish» (CSV, `;`, UTF-8 BOM) va «Excel'dan yuklash» (shablon bo'yicha
  yangi pozitsiyalar — hammasi yoki hech biri).
- `/warehouse/item/$code` — **Tovar kartochkasi**: qoldiq, xarid (so'm va $), sotuv (qoldiq qiymati
  bilan), min, joy, ustama, kod tuzilmasi, tahrirlash va o'chirish. Partiyalar va harakat tarixi —
  2-bosqichda. Qoldiq hozircha shu yerda qo'lda tahrirlanadi — 2-bosqichdan faqat hujjat bilan.
- Sarlavhadagi qidiruv «Kod / nom — skaner»: `/` bilan fokus, Enter — kartochka.

Rasm yo'q: dizayndagi ekranlar skrinshotlari bilan solishtirildi (2026-10-16), farqi — MES menyusi va
komponentlari (egasining tanlovi). Dizaynda yangi qo'shilganlar ro'yxat tepasiga chiqadi — bizda kod
tartibida, guruh oxirida.

Tekshiruv — `scripts/oracles/ombor_nomenklatura_oracle.py` **23/23**: guruh / umumiy / pozitsiya ustamasi,
dollar narxi va kurs, sinf narxi (bitta, ko'plab, narx o'zgarganda hammasi), furnituraga sinf
berilmaydi, zaxira faqat materialda, kod berish (yangi model, variant, o'chirilgan kod qayta
berilmaydi), xizmatda qoldiq yo'q, noma'lum guruh 404, import hammasi-yoki-hech-biri, ABC, importer
narxni qayta yozmaydi. `catalog_oracle` 36/36 (holat endi omborniki — tekshiruv shunga moslandi).

## 9. 2-bosqich: Kirim va Sotuv hujjatlari, FIFO, Hujjatlar (2026-10-16)

### 9.1 Jadvallar (`a5d9e3c71f28`)

| Jadval | Nima |
|---|---|
| `stock_doc` | Hujjat: `no` (`KIR-2026-0148` / `CHQ-2026-0393`, turi va yili bo'yicha ketma-ket, unikal), `kind` (`kirim`/`chiqim`), `status` (`draft`/`confirmed`), `doc_date`, `head` JSONB (dizayndagi bosh maydonlar o'z nomi bilan: kirimda `supplier`, `phone`, `note`, `invoice`, `receiver`, `rate`, `due`; sotuvda `client`, `phone`, `addr`, `order`, `seller`, `due`), `rate` (kirim kursi — tasdiqda qotadi), `total` (so'm), `cogs` (sotuvning FIFO tannarxi), kim va qachon tasdiqlagan |
| `stock_doc_line` | Qator: `item_id` (qoralamada bo'sh bo'lishi mumkin — nom yozilgan, tanlanmagan), `name`, `qty`, `price` (kirimda $, sotuvda so'm), `discount`, `note`, `cost` (sotuv qatorining FIFO tannarxi) |
| `stock_lot` | FIFO partiyasi: `qty` / `qty_left`, `unit_cost` (so'm), `usd`, `rate`, `source` (kirim raqami / `Boshlang'ich` / `Tuzatish`); qisman indeks `ix_stock_lot_open (item_id, received_on, id) WHERE qty_left > 0` |
| `stock_movement` | Har qoldiq o'zgarishining izi: `kind` (`kirim`/`chiqim`/`tuzatish`), ishorali `qty`, keyingi `balance`, `amount`, `note`, hujjat va foydalanuvchi |

Nomlar ATAYLAB `stock_move`/`stock_item` emas — o'sha nomdagi eski bo'sh jadvallar prodda yotibdi (`LEGACY_TABLES`).

### 9.2 Qoidalar (`backend/app/services/stock.py`) — dizayndagi `confirmDoc` / `consume` / `lotsOf`

- **Qoralama** qoldiqqa ta'sir qilmaydi, tahrirlanadi va o'chiriladi. **Tasdiqlangan** hujjat
  QULFLANGAN: o'zgarmaydi, o'chmaydi.
- Tasdiqlash bitta tranzaksiya; rad etilsa hech narsa yozilmaydi. Rad sabablari (o'zbekcha, « · »
  bilan): yetkazib beruvchi / mijoz kiritilmagan; qator yo'q; «N-qator: «…» nomenklaturada yo'q —
  ro'yxatdan tanlang»; «soni kiritilmagan»; «xizmat kirim qilinmaydi»; sotuvda
  «{nom}: N {birlik} kerak, omborda M bor» (pozitsiya bo'yicha JAMI — ikki qatorda bo'lsa ham).
- Pozitsiyalar tasdiqda `FOR UPDATE` bilan qulflanadi — ikki sotuvchi bir vaqtda oxirgi qoldiqni sotolmaydi.
- **Kirim** (narx $): partiya tannarxi `round($ × kurs)` (kurs hujjatdagi, bo'lmasa Boshqaruv panelidagi);
  pozitsiyaning `purchase_usd`/`purchase_price` yangilanadi va furniturada ustamali sotuv qayta
  hisoblanadi; jami = `Σ soni × $ × kurs`.
- **Sotuv**: ENG ESKI partiyadan (FIFO) olinadi; qator va hujjat tannarxi yoziladi; foyda = jami − tannarx.
  Xizmat summaga kiradi, omborga ta'sir qilmaydi.
- **Boshlang'ich partiya**: 1-bosqichdan qolgan qoldiq (partiyasiz) birinchi harakatda «Boshlang'ich»
  partiya bo'ladi — tannarxi o'sha paytdagi xarid narxi, sanasi pozitsiya yaratilgan kun (FIFO da doim
  birinchi). Kartochkada u harakatdan OLDIN ham ko'rinadi (bazaga yozilmasdan).
- **Qo'lda tuzatish** (kartochkadagi «Qoldiq (tuzatish)» — `PATCH /catalog/items/{id}` `quantity`): ortiqchasi —
  yangi partiya (xarid narxida), kami — FIFO bo'yicha chiqim; ikkalasi ham `tuzatish` harakati. 3-bosqichdagi
  Inventarizatsiya shu yo'lni hujjat bilan qiladi.

### 9.3 Sahifalar

- `/warehouse/doc?turi=chiqim|kirim` — **Sotuv / Kirim listi**: bosh qism (mijoz yoki yetkazib beruvchi +
  buyurtma/hujjat), qatorlar, M/F/X bo'yicha jami (sotuvda), $ va so'mdagi jami (kirimda), «Tozalash»,
  «Saqlash (Ctrl+S)» — qoralama, «Tasdiqlash (F9)». Klaviatura oqimi dizayndagidek: nom → takliflar (kod,
  nom, dekor, artikul; ↑↓, Enter yoki Tab) → soni (fokus DARHOL o'tadi — skanerning keyingi belgisi nom
  maydoniga tushmasin, lokal sinovda topilgan) → Enter → keyingi qator; qator ostida «omborda 15 → 12»,
  yetmasa qizil. «Excel'dan yuklash» — kod (yoki to'liq nom) + soni ustunlari. Sotuvda «Shartnoma» — oldingi
  `/sotuv` dagi chop etiladigan shartnoma (huquqiy matn o'zgarmagan, `Warehouse/Shartnoma.tsx`).
  Saqlanmagan ish brauzerda (`mebelix.ombor.hujjat.<tur>`). Tasdiqlangach — toast (summa, FIFO tannarx,
  foyda) va yangi bo'sh list. `?id=` — qoralamani davom ettirish yoki tasdiqlanganni ko'rish (qulflangan).
  `?add=KOD` — kartochkadagi «Kirimga / Sotuv listiga qo'shish».
- `/warehouse/docs` — **Hujjatlar**: qoralamalar (o'chirish mumkin) va tasdiqlanganlar (summa, foyda),
  «Hujjatlarni / Harakatlarni Excel'ga chiqarish».
- Kartochka — **Partiyalar (FIFO)** (keyingi chiqim narxi, qoldiq qiymati) va **Harakat tarixi** (hujjatga havola).
- `F2` / `F4` — har ombor sahifasida yangi sotuv / kirim (`routes/_layout.tsx`); menyuda «Sotuv (chiqim) · F2»,
  «Kirim · F4», «Hujjatlar».
- `/sotuv` — eski manzil, yangi Sotuv hujjatiga yo'naltiradi. Brauzerda saqlangan eski listlar
  (`mebelix.sotuv-listi.v1`) ko'chirilmadi — ular bazaga hech qachon yozilmagan edi.

Tekshiruv — `scripts/oracles/ombor_hujjat_oracle.py` **21/21**: partiyasiz qoldiq «Boshlang'ich» bo'lib
ko'rinadi; qoralama qoldiqqa ta'sir qilmaydi; sotuv 10 × 5 100 − 1 000 + xizmat = 56 000, tannarx 36 600;
kirim $0.30 × 12 800 → partiya 3 840, xarid 3 840, sotuv 5 400 (40% ustama); FIFO 97 × 3 660 + 3 × 3 840 =
366 540; rad etishlar (qoldiqdan ko'p, mijozsiz, nomenklaturada yo'q, xizmat kirimi, soni yo'q, ikki qator
jami); tasdiqlangan hujjat o'zgarmaydi va o'chmaydi; qoralama o'chadi; qo'lda tuzatish +3/−5 partiya va
harakat bilan; partiyalar yig'indisi = qoldiq. Brauzerda (lokal): sotuv klaviatura bilan kiritilib F9 bilan
tasdiqlandi (16 200, foyda 4 680), kartochka tarixi, shartnoma, F4.

## 10. 3-bosqich: Sex xo'jaligi va Inventarizatsiya (2026-10-16)

### 10.1 Sex xo'jaligi — `S` katalogi

- To'rtinchi katalog harfi `S` (zapchast, asbob, kanselyariya, xo'jalik, upakovka) — sotilmaydi, sexga
  beriladi. Guruhlar varaqda yo'q, birinchi pozitsiya ochilganda nomi `SEX_GROUPS` dan olinadi
  (`services/warehouse.py` va `lib/warehouse.ts` — qo'lda oynalangan): `S-ZP`, `S-AS`, `S-KG`, `S-XJ`, `S-UP`.
- **Sexga kirim** hujjati (`kind=sex`, raqam `SEX-2026-0001`): bosh qismda `taker` (kim oldi — MAJBURIY,
  «Kim olgani kiritilmagan»), `equip` (uskuna/uchastka), `note`, `order`, `giver`. Qatorga `S` pozitsiyalar
  va furnituraning `F-AS`/`F-KL` guruhlari (asbob, kley) taklif qilinadi. Xizmat sexga berilmaydi.
- Tasdiqda FIFO bo'yicha chiqim; summa = tannarx (narx yo'q, chegirma yo'q, shartnoma yo'q). Harakat izohi
  «Sexga kirim · taker · equip».
- Sotuv hujjatida `S` pozitsiya rad etiladi: «… sex xo'jaligiga tegishli — sotilmaydi».

### 10.2 Inventarizatsiya

- `POST /stock/inventory` — sanalgan haqiqiy miqdorlar (`services/stock.inventory`): ortiqcha — yangi
  partiya (xarid narxida), kami — FIFO chiqim; ikkalasi `inv` harakati. Hujjat (`INV-2026-0001`) darhol
  TASDIQLANGAN yoziladi; qatorda `qty` — haqiqiy, `book_qty` — hisobdagi (migratsiya `b8e2f4a6c013`),
  `cost` — farqning summasi; `total` — ishorali jami farq.
- Sanalmagan (bo'sh qoldirilgan) pozitsiya hujjatga kirmaydi va qoldig'i o'zgarmaydi.

### 10.3 Sahifalar

- `/warehouse?katalog=S` — mahsulotlar va qoldiq, tepada tablar (`Warehouse/SexTabs.tsx`): «Mahsulotlar va
  qoldiq» · «Sexga kirim F3» (`/warehouse/doc?turi=sex`) · «Sex sarfi».
- `/warehouse/sex-sarfi` — tasdiqlangan sexga kirim qatorlari: qidiruv (usta, uskuna, tovar), usta filtri,
  jami va usta bo'yicha yig'indi, CSV, qatorni bosish — hujjat.
- `/warehouse/inv` — guruh tanlanadi (xizmatdan tashqari), «Pozitsiya / Farq topildi / Summada»; har qatorda
  haqiqiy miqdor (Enter/↓ — keyingisi, ↑ — oldingisi), «Excel'dan yuklash» (kod + soni), `F9` yoki «Tasdiqlash
  va qoldiqni to'g'rilash» — keyin Hujjatlar. Tasdiqlangan INV `/warehouse/doc?turi=inv&id=` da: Hisobda,
  Haqiqiy, Farq, Summa farqi.
- `F3` — har ombor sahifasida yangi sexga kirim; menyuda «Sex xo'jaligi · F3», «Inventarizatsiya».

Tekshiruv — `scripts/oracles/ombor_sex_inv_oracle.py` **16/16**. Brauzerda (lokal): F-RC guruhida 2 pozitsiya
sanab F9 (−95 dona, −347 700 so'm) — INV hujjati va kartochka qoldig'i; sex sarfi va SEX hujjati ko'rinishi
(FIFO tannarx 448 000); F3.
