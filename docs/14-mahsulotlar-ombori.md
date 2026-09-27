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
to'g'ri `/warehouse` ga tushadi (yo'naltirish FAQAT boshqa sahifadan — `/warehouse`
ning o'zi ham `_layout` ichida, shartsiz yo'naltirish cheksiz halqa berardi) va
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
  (logistika), shuning uchun harfning o'zi bilan filtrlaganda «Hammasi» tabida
  boshqa katalogning pozitsiyalari qo'shilib ketardi.
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

Tekshiruv: `scripts/oracles/catalog_oracle.py` — **32/32** (kod formati, takror
yo'qligi, daraxt sanoqlari, filtrlar va qidiruv, artikulning matn bo'lib
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
| **List** | Mijoz va buyurtma kartalari, qatorlar (soni · narx · chegirma · summa), jami, imzo chiziqlari | A4 **ko'ndalang** — sakkiz ustun |
| **Shartnoma** | Spesifikatsiya (kod · artikul ustuni bilan), jami summa **so'z bilan** (`lib/mes: moneyToWords`), alohida shartlar, imzo bloklari | A4 **bo'yiga**, serif shrift |

`@page` qoidasi ko'rinishga qarab almashadi; sahifadagi boshqaruvlar
`print-hide` bilan chop etishdan chiqariladi (`index.css` dagi umumiy qoida).

**Bazaga yozilmaydi** (2026-09-25): list brauzerda saqlanadi
(`localStorage`, `mebelix.sotuv-listi.v1`) va qog'oz hujjat sifatida chop
etiladi. Ya'ni u boshqa kompyuterda ko'rinmaydi va MES hisobotlariga kirmaydi.
Bazaga ko'chirilsa: `sale_sheet` + `sale_sheet_row` jadvallari, buyurtmaga
bog'lanish va saqlash kaliti versiyasini oshirish kerak.
