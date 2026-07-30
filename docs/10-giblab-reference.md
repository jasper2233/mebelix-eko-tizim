# 10 — GibLab: manba tizim ma'lumotnomasi

MebeliX buyurtma ma'lumotini o'zi yaratmaydi — uni **GibLab** dan `.project` fayl orqali oladi.
Bu hujjat GibLab ichida nima borligini yozadi: ma'lumot modeli, fayl formati, operatsiya turlari,
sozlamalar va integratsiyalar. Maqsad — parser nimaga tayanishini va nimani ataylab e'tiborsiz
qoldirishini asoslash.

Manba: `giblab.com` veb-ilovasi va uning `Справка` bo'limi (`/help/*.html`), 2026-07-27 holati.
Rasmiy format spetsifikatsiyasi: `/help/format_ru.html` — 31 jadval, 445 atribut.
Bizning tomonimiz: `backend/app/services/giblab/` (parser, cutmap, csblob, xnc, scx, ingest).

---

## 1. GibLab nima va u qanday ishlatiladi

Veb-ilova (Java/GWT, `giblab.com`). Dizayner mebelni loyihalaydi, materialni tanlaydi, kesish
xaritasini **optimizatsiya qiladi** va natijani `.project` fayl sifatida eksport qiladi.
Kesish xaritasini GibLab hisoblaydi — MebeliX uni **qayta hisoblamaydi**, faqat o'qib chizadi.

Interfeys uch qatlamdan iborat:

| Qatlam | Nima |
|---|---|
| `#projects` | Proyektlar ro'yxati: ID, egasi, holati, sana, qiymati, nomi. Papkalarga bo'linadi |
| `#project` | Proyekt muharriri: yuqorida **Операции** va **Изделия** jadvallari, pastda tanlangan operatsiyaning tafsiloti |
| `#settings` | Akkaunt sozlamalari: katalog, postprotsessorlar, XNC muharriri, yorliq papkasi, buyurtma moduli |

Operatsiya tafsiloti to'rt tabdan iborat: **Параметры** (material va kesish sozlamalari),
**Детали** (detallar jadvali), **Листы и остатки** (list zaxirasi va deloviy qoldiqlar),
**Раскрой** (kesish xaritasi).

### Muhim kuzatuv: kod va nom majburiy emas

"Изделия" jadvalida mahsulotning `Код` maydoni bo'sh bo'lishi mumkin, "Детали" jadvalida esa
"Наименование" ustuni butunlay bo'sh qolishi mumkin. GibLab bunga to'sqinlik qilmaydi va
eksportga ham bo'sh yozadi. Bizning korpusdagi to'rtta fayl aynan shunday — detal kodlari yo'q,
nomida kod o'rniga `№` belgisi turadi.

Shu sababli parser kodsiz detalga tartib raqamidan kod beradi (`001`, `002`, ...) va
ogohlantirish yozadi. Kod GibLab'da to'ldirilsa yorliqda `312001_01_003 bok` kabi ma'noli
qiymat chiqadi.

---

## 2. `.project` fayl formati

XML. Kodlash e'londa ko'rsatiladi (`UTF-8` yoki `windows-1251`). Ildiz — `<project>`.

`version` atributi — **build sanasi** `YYMMDDNN` ko'rinishida: `21052101` = 2021-05-21,
`23051701` = 2023-05-17. Korpusda ikkala versiya ham bor va ular **turlicha yozadi** —
2021 buildi detal kodlarini umuman bermaydi.

### 2.1 Tovarlar — `<good typeId="...">`

Bitta teg, oltita turdagi ma'lumot uchun:

| `typeId` | Nima | Bizda |
|---|---|---|
| `product` | Mahsulot (izdeliye). Ichida `<part>` lar | ✅ mahsulot + detallar |
| `sheet` | Listli material. `l`/`w`/`t` (default 2750×1830×18), `count` | ✅ material registri |
| `band` | Pogonaj material — kromka lentasi, profil, quvur. `w`/`t`, `count` metrda | ✅ material registri |
| `simple` | **Furnitura**: petlya, yevrovint, dasta, napravlyayushiye. `unit`, `count`, `cost` | ✅ material registri (`hardware`) |
| `tool.cutting` | Kesish dastgohi sozlamalari. **`swSawthick` — pilla qalinligi (kerf)** | ✅ faqat kerf |
| `tool.edgeline` | Kromkalash dastgohi. `elRestSide` | ✅ faqat `elRestSide` |

`simple` goodlari sexning **`goods.xls`** katalogidan keladi (Настройки → Каталог товаров).
Katalog ustunlari: ID, ota-ID, papka, kod, nom, o'lchov birligi, narx, ombor, rasm, qalinlik,
uzunlik, kenglik. Ya'ni furnitura kodlari (`FNK100`, `PR teks 0`) haqiqiy SKU.

### 2.2 `<part>` — detal, zagotovka yoki qoldiq

**Bitta teg uch narsa uchun.** Farqi atributlarda: `waste="true"` → qoldiq,
qo'shimcha `business="true"` → deloviy qoldiq (qayta ishlatiladi), `sheetId` → qaysi listdan.

**Uch juft o'lcham** (eng ko'p chalkashtiradigan joy):

| Juftlik | Ma'nosi |
|---|---|
| `dl` / `dw` | Tayyor detal — kromka bilan |
| `jl` / `jw` | **Pilla o'lchami** (zagotovka) |
| `cl` / `cw` | Korpusda `dl/dw` bilan bir xil |

Bu juftliklar orasidagi munosabat **o'lcham kiritish rejimiga** bog'liq
(Настройки → Режимы ввода деталей):

| Rejim | Pilla o'lchami |
|---|---|
| Zagotovka bo'yicha | o'zgarmaydi |
| Detal bo'yicha (kromka bilan) | prifugovkaga oshadi, kromka qalinligiga kamayadi |
| Prifugovkadan keyin (kromkasiz) | prifugovkaga oshadi |

Korpusdagi fayllar ikkinchi rejimda kiritilgan: `kuxniya.project` da kromkalanadigan tomonda
`jw` = `dw` − 1 mm (kromka 1 mm).

**Muhim:** GibLab o'z kesish xaritasiga `dl/dw` ni joylashtiradi, `jl/jw` ni emas
(140 farqli detal bo'yicha tekshirilgan). Bizning xarita katakchalari blob qiymatlaridan
olinadi (`cutmap.py`, `node.value`) — ya'ni GibLab nima joylashtirgan bo'lsa shuni ko'rsatamiz.
Manba tizim bilan farq yo'q. `jl/jw` `Part.saw_length/saw_width` da saqlanadi.

**Kromka tomon bo'yicha:** `elt` / `elb` / `ell` / `elr` — qiymati `@operation#N` ko'rinishida
EL operatsiyasiga havola; `eltMat` va boshqalar — lenta materiali nomi.

**Paz tomon bo'yicha:** `grt` / `grb` / `grl` / `grr` — GR operatsiyasiga havola,
`grts`/`grbs`/`grls`/`grrs` — mantiqiy bayroq. **Biz o'qimaymiz** — pazni XNC dasturi ichidagi
`<gr>` elementlaridan aniqlaymiz. GR operatsiyasi ishlatilsa ogohlantirish chiqadi.

**O'qilmagan, lekin bilib turish kerak:**

| Atribut | Nima | Nega muhim |
|---|---|---|
| `allowanceT/B/L/R` | Ishlov qo'shimchasi tomon bo'yicha | Pilla o'lchamiga qo'shiladi, GibLab kartada **punktir chiziq** bilan chizadi. Bizda punktir yo'q → nolga teng bo'lmasa ogohlantiramiz |
| `minusCount` | Omborda tayyor turgan nusxalar | GibLab ularni kesishga qo'ymaydi, biz `count` bo'yicha hammasini ishlab chiqaramiz → ogohlantiramiz |
| `description` | Detal izohi | `Part.note` ni to'ldirishga yaroqli. Korpusda hamma joyda bo'sh |
| `dbId` | Ombor qoldig'ining 1C dagi ID'si | 1C integratsiyasi ishlatilsa paydo bo'ladi. Korpusda yo'q |
| `usedCount` | Ishlatilgan miqdor | Qoldiq inventarizatsiyasi uchun |

---

## 3. Operatsiyalar — `<operation typeId="...">`

GibLab "+Операция" ro'yxatida **to'qqiz tur** taklif qiladi:

| `typeId` | Nomi | MebeliX |
|---|---|---|
| `CS` | Листовой раскрой — listni kesish | ✅ kesish xaritasi + yorliq raqamlari |
| `EL` | Кромкооблицовка — kromkalash | ✅ kromka simvoli va materiali |
| `XNC` | Обработка — CNC ishlov | ✅ teshik, paz, freza → PRISADKA/PAZ/ROVER bosqichlari |
| `O` | Комплектация — furnitura komplekti | ataylab jim: sanoqlar `simple` goodlarida bor |
| `LB` | Этикетки — yorliq shablonlari | ataylab jim: tizim o'z yorlig'ini chiqaradi (TZ 5.2.8) |
| `CL` | Погонажный раскрой — profil kesish | ataylab jim + **ma'lumot yoziladi**: sexda profil kesish posti yo'q, profillar tayyor keladi |
| `CN` | Нестинговый раскрой — CNC nesting | ❌ ogohlantirish. GibLab'ga 2021-05 da qo'shilgan |
| `SP` | Обработка поверхности — yuza ishlovi | ❌ ogohlantirish |
| `GR` | Пазование — paz | ❌ ogohlantirish (PAZ bosqichi XNC dan aniqlanadi) |

`CN`, `SP`, `GR` korpusda umuman uchramaydi. `CL` esa `kupe.project` da 3 ta, `TV_zonakupe`
da 1 ta — ularning `<part>` lari `X1..X32` kodli alyuminiy profillar, 3200 mm zagotovkadan
kesiladi va listda umuman joylashtirilmaydi.

### 3.1 CS — kesish xaritasi

`data` atributi — **base64, shifrlanmagan big-endian binar blob**. Ichida naqshlar (patterns),
har birida daraxt ko'rinishidagi kesish yozuvlari. `csblob.py` uni ochadi.

Muhim tushunchalar:

- **Кратность (`mult`)** — bitta naqsh necha marta takrorlanadi. Xaritada `C:2` deb ko'rinadi
- **Torsovka** (`cTrimL`, `cTrimW`) — listning chetidan olinadigan qirqim, default 2 mm
- **Deloviy qoldiq** — `waste="true" business="true"` bo'lgan `<part>`; foydali o'lchami
  ta'rifda, xom o'lchami `rl`/`rw` da
- **`cPartCount`** — joylashtirilgan katakchalar soni; parser buni blob bilan solishtiradi

CS operatsiyasida `<part>` ro'yxati bor, lekin **ro'yxatda bo'lish joylashtirilganini
bildirmaydi**: `usedCount="0"` bo'lsa GibLab uni ataylab joylashtirmagan (material yetmagan
yoki dizayner chiqarib tashlagan). `kuxniya.project` da uchta shunday detal bor.

### 3.2 XNC — ishlov dasturi

`program` atributi — ichki XML hujjat (HTML-escape qilingan). Ba'zi eksportlarda
`<program>` alohida bola element sifatida keladi.

Ildiz atributlari: `dx`/`dy`/`dz` (yangi) yoki `l`/`w`/`thick` (eski).

Spetsifikatsiyadagi element to'plami:

| Teg | Nima | Bizda |
|---|---|---|
| `tool` | Asbob (`name`, `d` — diametr) | ✅ |
| `var` | O'zgaruvchi e'loni (`name`, `expr`) | ✅ |
| `bf` | Frontal teshik | ✅ |
| `bt` / `bb` / `bl` / `br` | Qirra teshigi (tepa/past/chap/o'ng) | ✅ |
| `gr` | Paz | ✅ |
| `ms` | Freza kirish nuqtasi | ✅ |
| `ml` | To'g'ri chiziq bo'ylab frezalash | ✅ |
| `mac` | Markazi berilgan yoy bo'ylab frezalash | ✅ |
| `ma` | Yoy bo'ylab frezalash | ❌ ogohlantirish |
| `xy` | **Koordinata boshi** | ❌ ogohlantirish |
| `oq` / `oh` | Eski avlod arra/paz asboblari | ✅ (pazga o'giriladi) |

`xy` alohida xavfli: u koordinata boshini belgilaydi, ya'ni e'tiborsiz qolsa undan keyingi
**barcha teshik joylari xato** bo'ladi. Korpusda ikkalasi ham uchramaydi, lekin jimgina
buzilmaslik uchun ogohlantirish qo'shilgan.

**Standart konstantalar.** Yangi eksport ularni `<var>` bilan e'lon qiladi, eski (2021 buildi)
esa e'lonsiz ishlatadi. Qiymatlar korpusda hamma joyda bir xil:

```
throughBoreDepth = dz + 3.00     # teshib o'tuvchi teshik chuqurligi
throughCutDepth  = dz + 3.00     # teshib o'tuvchi frezalash chuqurligi
contMillDepth    = dz            # kontur bo'ylab frezalash
```

Parser ularni oldindan qo'yadi; fayl `<var>` bilan e'lon qilsa u ustun keladi.

**Nechta dastur bo'lishi mumkin?** Korpusda detalga ko'pi bilan ikkita. Lekin GibLab ko'proq
beradi — yorliq shabloni `XNC1..XNC5` maydonlarini taklif qiladi. Shuning uchun parser
sonini cheklamaydi: hammasini saqlaydi va ikkitadan ko'p bo'lsa ogohlantiradi
(`stage_sides()` har operatsiyaga bir skan beradi).

---

## 4. Sozlamalar (`#settings`)

| Bo'lim | Nima | MebeliX uchun ahamiyati |
|---|---|---|
| **Режимы ввода деталей** | O'lcham kiritish rejimi (uchta) | `dl/dw` ning ma'nosini belgilaydi — §2.2 |
| **Постпроцессоры** | 19 ta arra dastgohi uchun programma generatori: HOLZMA (PTX, CadMatic3/4), SCM (WinCut, MaestroCut), Biesse (OSI, NC300), FELDER Format4, Homag, KDT-PreSize, Scheer, Nanxing, Shelling, ELMO 3, GlassGCODE | Bizda arra programmasi yo'q — arrachi xaritani ekranda ko'rib qo'lda kesadi. Avtomatik arra olinsa shu joy qayta ko'riladi |
| **XNC Редактор** + **Папка XNC шаблонов** | Ishlov dasturlari muharriri va shablonlar | Biz faqat natijani o'qiymiz |
| **Папка этикеток** | GibLab yorliq shablonlari (`part.lbl`, HOLZMA/SCM yo'llari) | Ataylab almashtirilgan — §5 |
| **Каталог товаров** | `goods.xls` — materiallar va furnitura katalogi | `simple` goodlarining manbasi |
| **Модуль заказов** | GibLab'ning o'z buyurtma moduli | MebeliX shu vazifani bajaradi |
| **GibLabLocal.ini** | Sozlamalarni yuklash/saqlash | — |

---

## 5. GibLab yorlig'i va bizning yorlig'imiz

GibLab shabloniga qo'yiladigan maydonlar (109 ta), guruhlar bo'yicha:

- **Proyekt**: `project.name`, `project.date`, `project.description`, `project.currency`,
  `project.crc16`, `project.crc32`
- **Mahsulot**: `product.index/name/code/count/description/date`, **`product.phone1`, `product.phone2`**
- **Material**: `material.name`, `material.code`
- **Detal**: `part.id`, `part.code`, `part.counter`, `name`, `description`, `index`,
  `indexInOperation`, `fullName`, `length`/`width` (pilla), **`detail.length`/`detail.width`**
  (tayyor), `thick`, `waste`, `business`, `txt`, `count`, `totalCount`, `usedCount`
- **Kromka tomon bo'yicha** (`et*`/`eb*`/`el*`/`er*`, har biri 5 maydon): kod, nom, simvol,
  qalinlik, `*j`
- **Paz tomon bo'yicha** (`grt*`/`grb*`/`grl*`/`grr*`, har biri 7 maydon): kod, nom, kenglik,
  chuqurlik, ofset, `*oi`, bayroq
- **Yuza**: `surfFront`, `surfBack`
- **Yig'ma**: `groove`, `drill`, `mill`
- **Ishlov**: `XNC1..XNC5` + `xncSide1..5` + `xncBSD1..5`

MebeliX o'z yorlig'ini chiqaradi (TZ 5.2.8, `services/labels.py`): 80×60 mm, 203 dpi, 1-bit
termoprinter uchun. Ichida QR (`{productCode}_{partCode}_{n}`), detal kodi va nomi, buyurtma,
material, o'lcham, qalinlik, kromka belgilari, teshik eskizi va burg'u ikonkasi.

Sabab: GibLab yorlig'i skan qilinadigan QR bermaydi va MebeliX'ning bosqichma-bosqich
kuzatuvi aynan shu QR ga tayanadi.

---

## 6. Integratsiyalar

### Import (GibLab'ga)

`3D Constructor 7`, `Базис Мебельщик`, `BCAD`, `Woody2`, `MS Excel`. Ya'ni dizayner boshqa
CAD'da ishlab, GibLab'ga o'tkazishi mumkin. MebeliX uchun farqi yo'q — natija baribir
`.project`.

### 1C Бухгалтерия 8 — qoldiq hisobi

GibLab HTTP POST orqali uch amal bajaradi:

| Turi | Nima |
|---|---|
| `load` | Omborda qanday qoldiqlar borligini so'raydi |
| `report` | Qaysi qoldiqlar ishlatilganini xabar qiladi |
| `save` | Kesishdan chiqqan yangi qoldiqlarni omborga qaytaradi |

Javob formati: `id, uzunlik, kenglik, miqdor [, izoh]` — har qatorda bir tur qoldiq.
Qoldiq ID'si XML'da **`dbId`** atributida saqlanadi.

Sex 1C ishlatmaydi — korpusda `dbId` yo'q. Agar mijoz 1C bilan ishlasa, qoldiq
inventarizatsiyasi kimda turishi (GibLab yoki MebeliX) alohida qaror talab qiladi.

---

## 7. Parser nimaga tayanadi — qisqa xulosa

**O'qiymiz:** mahsulot va detallar, o'lchamlar, kromka (tomon + material + simvol), material
registri (list/kromka/furnitura), kesish xaritasi (naqsh, kratlik, katakcha, deloviy qoldiq,
o'lcham zanjiri), teshik/paz/freza (XNC), yorliq raqami, SCX generatsiyasi.

**Ataylab e'tiborsiz:** GibLab yorliq shablonlari (`LB`), optimizatsiya va narx parametrlari
(GibLab ichida ishlaydi, biz natijasini iste'mol qilamiz), arra postprotsessorlari,
profil kesish (`CL` — sexda bunday post yo'q).

**Ogohlantirish beradigan holatlar** (`parser.py: _advisories`, `ingest.py`):

| Holat | Xabar |
|---|---|
| Detal kodlari yo'q (2021 build) | tartib raqamidan berildi |
| Detal kodi takrorlangan | `-2` qo'shib saqlandi |
| Manfiy o'lcham | moduli olindi |
| Ishlov qo'shimchasi (`allowance*`) | xaritada punktir chizilmaydi |
| `minusCount` > 0 | to'liq miqdor ishlab chiqariladi |
| `CL` operatsiyasi | profil kesish — ma'lumot, arrachiga bermaymiz |
| `CN`/`SP`/`GR` operatsiyasi | import qilinmaydi, bosqich yo'qoladi |
| XNC da noma'lum teg (`ma`, `xy`) | o'sha ishlov ko'rinmaydi |
| Detalda 2 tadan ko'p XNC | hammasi saqlandi, skan sonini tekshirish kerak |
| Xaritada joyi yo'q detal | arrachi ro'yxatiga tushmaydi |

Bu xabarlar fayl yuklanganda menejerga ko'rsatiladi va audit logga yoziladi
(`POST /orders/{id}/project`).

---

## 8. Bog'lanishlar

- Parser: `backend/app/services/giblab/parser.py` (tovarlar, detallar, operatsiyalar, advisory)
- Blob: `csblob.py` (base64 binar), `cutmap.py` (vizual model + instance↔katakcha binding)
- Ishlov: `xnc.py` (dastur XML), `scx.py` (CNC fayl generatsiyasi)
- DB'ga yozish: `ingest.py` (mahsulot/detal/nusxa/marshrut, material registri, sarf hisobi)
- Testlar: `backend/tests/test_giblab.py` — sintetik fayllar, korpus fayllari repoda yo'q
- Domen tomoni: `docs/09-mes-domain.md`, API: `docs/03-backend-api.md`
