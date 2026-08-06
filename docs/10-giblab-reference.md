# 10 — GibLab: manba tizim ma'lumotnomasi

MebeliX buyurtma ma'lumotini o'zi yaratmaydi — uni **GibLab** dan `.project` fayl orqali oladi.
Bu hujjat GibLab ichida nima borligini yozadi: ma'lumot modeli, fayl formati, operatsiya turlari,
sozlamalar va integratsiyalar. Maqsad — parser nimaga tayanishini va nimani ataylab e'tiborsiz
qoldirishini asoslash.

Manba: `giblab.com` veb-ilovasi va uning `Справка` bo'limi (`/help/*.html`), 2026-07-27 holati.
Rasmiy format spetsifikatsiyasi: `/help/format_ru.html` — 31 jadval, 445 atribut qatori
(§7.1 dagi 289 — boshqacha sanalgan raqam, ikkalasi to'g'ridan-to'g'ri solishtirilmaydi).
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
eksportga ham bo'sh yozadi. Korpusdagi to'rtta faylda kodsiz detal bor: `2001_Nukriddin` da
hammasi (52/52), qolganlarida qisman — `kupe` 38/70, `kuxniya` 22/191, `TV_zonakupe` 47/49.
Nomida kod o'rniga `№` belgisi faqat `2001_Nukriddin` da turadi (52 tadan 48 tasida).

Shu sababli parser kodsiz detalga tartib raqamidan kod beradi (`001`, `002`, ...) va
ogohlantirish yozadi. Kod GibLab'da to'ldirilsa yorliqda `312001_01_003 bok` kabi ma'noli
qiymat chiqadi.

---

## 2. `.project` fayl formati

XML. Kodlash e'londa ko'rsatiladi (`UTF-8` yoki `windows-1251`). Ildiz — `<project>`.

**Element daraxti** (spetsifikatsiyaning "Дочерние элементы" bo'limlari):

```
<project>
├── <good typeId="product">        → <part>  — Detallar
│        typeId="sheet"           → <part>  — Zagotovka va qoldiqlar
│        typeId="band"            → <part>  — Zagotovka va qoldiqlar
│        typeId="simple" | "tool.cutting" | "tool.edgeline"   — bolasi yo'q
└── <operation>
     ├── <part>      — `id` bo'yicha good ichidagi detalga HAVOLA
     └── <material>  — good ga havola + operatsiyadagi vazifasi (`used`)
```

Ya'ni `<part>` **ikki xil vazifada** uchraydi: goodning ichida — ta'rif, operatsiya ichida —
havola. Parser detallarni faqat `typeId="product"` goodlaridan oladi. Korpusdagi taqsimot:
643 `part` mahsulotlarda, 41 tasi listlarda, 4 tasi pogonaj materiallarda.

**Zaxira zagotovka konventsiyasi:** `count="10000"` — cheksiz zaxira, `usedCount` — necha dona
ishlatilgan. Korpusdagi 4 pogonaj zagotovkasi (`l=3200` alyuminiy profil, quvur, LMDF)
`usedCount="0"` — ya'ni CL hech qachon optimallashtirilmagan; ular detal emas, shuning uchun
arrachiga tushmaydi.

`version` atributi — **build sanasi** `YYMMDDNN` ko'rinishida: `21052101` = 2021-05-21,
`23051701` = 2023-05-17. Korpusda ikkala versiya ham bor va ular **turlicha yozadi** —
2021 buildi detal kodlarini umuman bermaydi.

`<project>` atributlari: `version`, `currency`, **`date`** (tayyorlik sanasi, default bugun),
`description`, `costOperation`, `costMaterial`, `cost`. Real fayllarda bundan tashqari
`name` va `project.uuid` ham bor (spetsifikatsiyada yo'q, lekin biz ikkalasiga tayanamiz —
`uuid` fayl o'zligining yagona barqaror belgisi).

`product` goodida esa `orderDate`, `date`, `phone1`, `phone2`, `description` va `program`
(parametrik dastur) bor. **Biz o'qimaymiz:** buyurtma sanasi, mijoz va telefon menejer
kiritadigan ma'lumot, GibLab nusxasi eskirgan bo'lishi mumkin. Dizayner ularni to'ldirsa,
buyurtma formasini oldindan to'ldirish imkoniyati bor (hozircha ishlatilmaydi).

### 2.1 Tovarlar — `<good typeId="...">`

Bitta teg, oltita turdagi ma'lumot uchun:

| `typeId` | Nima | Bizda |
|---|---|---|
| `product` | Mahsulot (izdeliye). Ichida `<part>` lar | ✅ mahsulot + detallar |
| `sheet` | Listli material. `l`/`w`/`t` (default 2750×1830×18), `count` | ✅ material registri |
| `band` | Pogonaj material — kromka lentasi, profil, quvur. `w`/`t`, `count` metrda | ✅ material registri |
| `simple` | **Furnitura**: petlya, yevrovint, dasta, napravlyayushiye. `unit`, `count`, `cost` | ✅ material registri (`hardware`) |
| `tool.cutting` | Kesish dastgohi sozlamalari. **`swSawthick` — pilla qalinligi (kerf), default 4.4 mm** | ✅ faqat kerf |
| `tool.edgeline` | Kromkalash dastgohi. `elRestSide`, **`elWidthPreJoint` — prifugovka kengligi** | ❌ o'qilmaydi (qiymati hech qayerda ishlatilmasdi, 2026-08-05 da olib tashlandi) |

`tool.cutting` ning qolgan atributlari (`swPackageHeight`, `swMaxturns`, `swSort`,
`swSortInBand`, `swComplexBand`, `swMinSizeBand`, `swMaxSizeBand`, `swMaxLengthBand`,
`swMinPruning`) — **optimizator sozlamalari**: GibLab xaritani ular bilan hisoblagan. Biz
xaritani qayta hisoblamaymiz, shuning uchun o'qilmaydi. Korpusda eski eksportda `tool.cutting`
butunlay bo'sh keladi — o'shanda kerf spetsifikatsiyadagi standart 4.4 mm bo'ladi
(ilgari bu yerda 3.0 turardi, ya'ni arrachiga GibLab ishlatganidan boshqa raqam ko'rinardi).

`elWidthPreJoint` — §2.2 dagi `l/w` → `jl/jw` farqini tushuntiruvchi qiymat: kromkalash
dastgohi har tomondan shuncha mm oladi. Korpusda hamma joyda 1 mm.

### 2.1.1 `goods.xls` — sexning haqiqiy katalogi

Настройки → Каталог товаров. Sexdagi nusxa tekshirildi (`uploads/goods.xls`, BIFF/OLE2,
226 KB, 2 varaq). `Лист1` — katalogning o'zi, `A1:K888`:

| Ustun | Nima |
|---|---|
| `id` | Yozuv identifikatori |
| `paren_id` | Ota yozuv — katalog **iyerarxik** |
| `isfolder` | `1` = papka, `0`/bo'sh = tovar |
| `code` | **SKU** (`110083`, `КРМ1009`, `FB49`) |
| `name` | Nom (`Ясень`, `Кромка ПВХ ... 1х19 мм 101`) |
| `unit` | `шт` (list) yoki `м` (kromka) |
| `price` | **Sexda bo'sh — narx yuritilmaydi** |
| `Толщина` / `Длина` / `Ширина` | Qalinlik / uzunlik / kenglik |

GibLab interfeysi ombor va rasm ustunlarini ham ko'rsatadi — sexning faylida ular yo'q.
Nomlangan o'nta ustundan keyin sarlavhasiz o'n birinchi ustun (`K`) turadi: unda bitta
tasodifiy qiymat bor (603-qatorda `<tool.edgeline elWidthPreJoint="1"/>` — katalogga
adashib tushgan XML bo'lagi), qolgani bo'sh.

Tarkibi: **885 yozuv — 16 papka, 869 tovar**, ikki ildiz bo'limda:

- `Листовой материал` — 588 tovar (Cleaf, EGGER, Khat décor; 2800×2070 va 2750×1830; 16/18 mm)
- `Кромочные материалы` — 281 tovar (PVX kromka, `t=1`, `w=19` yoki `28`)

**Furnitura katalogda yo'q.** Ya'ni `simple` goodlari boshqa joydan (dizayner qo'lda) keladi —
faqat materiallar va kromka katalogdan olinadi. 812 tovarda kod bor, 57 tasida yo'q, ikki kod
(`UA01`, `B073`) takrorlanadi — kod yagona kalit deb qabul qilib bo'lmaydi.

**Sex katalogga yaqinda o'tgan.** Kodlarni loyiha fayllari bilan solishtirish:

| Fayl | Materiali katalogda topildi |
|---|---|
| `1160.project` (2026-07-30, 23051701) | **2/2** — `code="110083" name="Ясень"`, `code="КРМ1009"` |
| eski 8 fayl | 1/105 — dizayner lotincha nom yozgan (`LDSP DUB VATAN TEKSTURA`), kod bo'sh |

Shu sababli `material_usage` ga `code` ham yoziladi: katalog ishlatilgandan keyin barqaror
kalit **nom emas, kod**. Material hisoboti hozir `(name, kind)` bo'yicha yig'adi — bir material
eski va yangi nom bilan ikki qatorga bo'linadi. Kod bo'yicha yig'ishga o'tish tarixiy
hisobotlarni o'zgartiradi, shuning uchun alohida qaror talab qiladi.

Ikkinchi varaq (`Лист3`) — katalogni `dict_goods(id, parent_id, isfolder, code, name, unit,
thickness, length, width)` jadvaliga yuklaydigan **SQL-INSERT generatori** (formulali 5 qator,
`unit='м2'`). Ya'ni katalog qandaydir tashqi bazaga ham import qilinadi; MebeliX uchun
ahamiyati yo'q, lekin ustun sxemasi `Лист1` niki bilan bir xil ekanini tasdiqlaydi.

**O'lchov birliklari.** Fayllarda `unit` deyarli yozilmaydi (korpusdagi 105 material goodidan
50 tasida — barcha `sheet` va `band` da — bo'sh; furnitura esa doim `шт` beradi), shuning uchun
`material_usage` birligi turdan olinadi: `sheet → list` (fayldagi `шт`),
`band → metr` (fayldagi `м`; 1160 da 284 m), `hardware → dona` (fayldagi `шт`). List va kromka
mosligi 1160.project bilan, furnitura birligi korpusdagi 55 `simple` goodi bilan tekshirilgan.

### 2.1.2 Yangi eksportda qo'shilgan atributlar (spetsifikatsiyada yo'q)

`1160.project` (2026-07-30, build 23051701) rasmiy hujjatdan keyin qo'shilgan 13 atribut
yozadi — hammasi optimizator sozlamasi yoki qo'shimcha statistika:

| Element | Atribut | Izoh |
|---|---|---|
| `tool.cutting` | `swSawthickDiv`, `swTrimIncludeSaw` | Ajratuvchi pilla qalinligi (−1 = ishlatilmaydi), torsovka pilla qalinligini o'z ichiga oladimi |
| `CS` | `cCombiningParts`, `cGroupParts`, `cMaxPartsOnPattern`, `cPrefLargePacket`, `cSortPatterns` | Joylashtirish sozlamalari |
| `CS` | `cTrimWaste` | Spetsifikatsiyada `cTrimWaster` deb yozilgan — nomi o'zgargan |
| `CS` | `cPartsAmountP` | Spetsifikatsiyada `cPartAmountP` (`s` siz) |
| `CS` | `cutLength`, `cutCount` | **Yangi murakkab format:** `"0=92.86;1=9.06;2=83.8;"` — `0=` jami, `1=`/`2=` ikki yo'nalish (9.06 + 83.8 = 92.86 ✓). `cTrimLength`/`cTrimCount` esa mult bilan kengaytirilgan jami (176.66 / 177) |
| `EL` | `elMinDimDetail`, `elPreMillingEqual` | Minimal kromkalanadigan o'lcham, prifugovka bir xilmi |

`CS` operatsiyasi bundan tashqari listning `l`/`w`/`t` sini ham takrorlaydi (biz o'lchamlarni
blobdan olamiz).

**Mantiqiy qiymatlar ikki xil yoziladi.** Shu bitta faylda `csTexture="true"` yonida
`cCostByItem="1"` turadi. Shuning uchun parser `true`/`1` ni ham, `false`/`0` ni ham tushunadi
(`models.xml_bool`) — ilgari `enable="0"` bo'lsa GibLab o'chirgan teshik teshilardi, `av="1"`
bo'lsa teshik qatori noto'g'ri yo'nalishda chizilardi.

**Detal kodi majburiy emas — yangi eksportda ham.** `1160.project` da `<part>` larda `code`
yo'q (mahsulot nomi "01"), ya'ni bu eski buildga xos hodisa emas. Parser tartib raqamidan
kod beradi (`001`, `002`) va ogohlantiradi; QR va SCX nomlari shu raqamga bog'lanadi.

### 2.2 `<part>` — detal, zagotovka yoki qoldiq

**Bitta teg uch narsa uchun.** Farqi atributlarda: `waste="true"` → qoldiq,
qo'shimcha `business="true"` → deloviy qoldiq (qayta ishlatiladi), `sheetId` → qaysi listdan.

**To'rt juft o'lcham** (eng ko'p chalkashtiradigan joy). Qaysi biri MAJBURIY ekanini
CS operatsiyasining `cSizeMode` atributi belgilaydi:

| Juftlik | Ma'nosi | Majburiy |
|---|---|---|
| `l` / `w` | Zagotovka o'lchami | `cSizeMode=0` |
| `dl` / `dw` | Tayyor detal — kromka bilan | `cSizeMode=1` |
| `jl` / `jw` | Prifugovkadan **keyingi** zagotovka | `cSizeMode=2` |
| `cl` / `cw` | **Pilla o'lchami** (arra nimani kesadi) | majburiy emas |

Rasmiy misol (`help/format_ru.html`, `example1.png`) buni ochiq yozadi — har rejimda fayl
**faqat shu juftlikni** saqlashi mumkin:

```
cSizeMode=0   <part l="Длина заготовки"                  w="Ширина заготовки"/>
cSizeMode=1   <part dl="Длина гот. детали"               dw="Ширина гот. детали"/>
cSizeMode=2   <part jl="Длина заготовки после прифуговки" jw="Ширина ... после прифуговки"/>
```

Shu sababli parser zanjirsiz ishlamaydi: 0-rejimdagi faylda `dl` yo'q, 2-rejimda esa `l` ham,
`dl` ham bo'lmasligi mumkin.

Korpusdagi 8 faylda `cSizeMode="1"`, ya'ni `dl/dw` asosiy. Va 560 detal bo'yicha
**`cl/cw` doim `dl/dw` ga teng** — shu sababli bizning ko'rsatayotgan o'lcham amalda
pilla o'lchamiga mos tushadi.

Parser zanjir bilan oladi: `l/w` → `dl/dw` → `cl/cw` → `jl/jw`. Zanjir kerak, chunki
2-rejimdagi faylda faqat `jl/jw` bo'lishi mumkin va aks holda detal o'lchamsiz qolardi.
`jl/jw` alohida saqlanmaydi — u faqat zanjirning oxirgi zaxira qadami (ilgari
`part.saw_length/saw_width` ustunlarida turardi; hech qayerda o'qilmagani uchun
2026-08-05 migratsiyasida olib tashlangan).

Fizik ketma-ketlik (kuxniya.project, kromka 1 mm):
arra `cl`=2230 kesadi → prifugovka 1 mm oladi (`jl`=2229) → kromka 1 mm qo'shadi
(`dl`=2230 tayyor).

Rejimlar orasidagi munosabat (Настройки → Режимы ввода деталей):

| Rejim | Pilla o'lchami |
|---|---|
| Zagotovka bo'yicha | o'zgarmaydi |
| Detal bo'yicha (kromka bilan) | prifugovkaga oshadi, kromka qalinligiga kamayadi |
| Prifugovkadan keyin (kromkasiz) | prifugovkaga oshadi |

**Muhim:** GibLab o'z kesish xaritasiga `cl/cw` (= `dl/dw`) ni joylashtiradi. Bizning xarita
katakchalari blob qiymatlaridan olinadi (`cutmap.py`, `node.value`) — ya'ni GibLab nima
joylashtirgan bo'lsa shuni ko'rsatamiz. Manba tizim bilan farq yo'q.

`txt="true"` — tekstura qulfi: detalni listli kesishda **aylantirib bo'lmaydi**.
`business="true"` — deloviy qoldiq: qayta ishlatiladi va **material sarfiga kirmaydi**.

**Kromka tomon bo'yicha:** `elt` / `elb` / `ell` / `elr` — qiymati `@operation#N` ko'rinishida
EL operatsiyasiga havola; `eltMat` va boshqalar — lenta materiali nomi.
Tomonlar: `t`/`b` — **uzunlik bo'ylab**, `l`/`r` — **kenglik bo'ylab**.

**Paz tomon bo'yicha:** `grt` / `grb` / `grl` / `grr` — GR operatsiyasiga havola,
`grts`/`grbs`/`grls`/`grrs` — qaysi tomondan (yuz=true, orqa=false). **Biz o'qimaymiz** — pazni XNC dasturi ichidagi
`<gr>` elementlaridan aniqlaymiz. GR operatsiyasi ishlatilsa ogohlantirish chiqadi.

**O'qilmagan, lekin bilib turish kerak:**

| Atribut | Nima | Nega muhim |
|---|---|---|
| `allowanceT/B/L/R` | Ishlov qo'shimchasi tomon bo'yicha | Pilla o'lchamiga qo'shiladi, GibLab kartada **punktir chiziq** bilan chizadi. Bizda punktir yo'q → nolga teng bo'lmasa ogohlantiramiz |
| `minusCount` | Omborda tayyor turgan nusxalar | GibLab ularni kesishga qo'ymaydi, biz `count` bo'yicha hammasini ishlab chiqaramiz → ogohlantiramiz |
| `description` | Izoh **va/yoki ishlov dasturi kodi**: `#nom` — yuz tomon, `##nom` — orqa tomon, bo'shliqsiz | Shablon kutubxonasidan ishlov. Bunday holatda faylda XNC operatsiyasi bo'lmaydi va butun ishlov yo'qoladi → ogohlantiramiz. Korpusda ishlatilmagan |
| `dbId` | Ombor qoldig'ining 1C dagi ID'si | 1C integratsiyasi ishlatilsa paydo bo'ladi. Korpusda yo'q |
| `usedCount` | Ishlatilgan miqdor | Qoldiq inventarizatsiyasi uchun. Korpusda 595 detalda bor |
| `cTrimL` / `cTrimW` / `cTrimEL` / `cTrimEW` | **Faqat list/polosa uchun**: shu listning o'z torsovkasi. Manfiy (default −1) → operatsiyaning qiymati ishlatiladi | Bir listning torsovkasi boshqacha bo'lsa xarita sarlavhasidagi raqam shu list uchun xato bo'ladi. Korpusda ishlatilmagan |
| `groupInBlock` / `groupInBlockMC` / `groupInBlockMaxC` | Detallarni blokka guruhlash | Optimizator sozlamasi. Korpusda yo'q |

**Deloviy qoldiqlar — ishlatilmagan imkoniyat.** Korpusda 13 ta `waste="true" business="true"`
`<part>` bor va ular hammasi `good[typeId=sheet]` ichida yashaydi (detal ro'yxatiga tushmaydi,
soxta vazifa yaratmaydi). Ular GibLab'ning "shu kesishdan 688×1166 foydali qoldiq chiqadi"
degan xabari. Sklad moduli ularni qabul qilsa qoldiq hisobi avtomatlashadi — 1C protokoli
(§6) aynan shu ma'lumot bilan ishlaydi.

### 2.3 Detal nomi — sexning marshrut kodlari

**Sexning marshrut kodlari — FIGURALI qavsda.** Texnolog noodatiy detalning marshrutini
detal nomiga yozadi: `eshik {7;11;8}`. **Ajratgich — nuqtali vergul (`;`).** Ro'yxat
TARTIBLI: birinchi kod — jarayon boshlanadigan post, oxirgisi — tugaydigani. Odatdagi
detal arradan boshlanadi, `{...}` li detal esa qavsdagi BIRINCHI postdan — masalan
`{7;8}` roverda kesilib bo'yoqda tugaydi, arraga umuman tushmaydi.

Ajratgich sifatida **faqat `;`** qabul qilinadi (kodlar atrofidagi bo'shliq e'tiborsiz:
`{7; 8}` ham o'qiladi). Nuqta va vergul ATAYLAB qabul qilinmaydi — sexda yagona yozuv
shakli qolsin; noto'g'ri yozilgan qavs rad etiladi va texnologga ogohlantirish chiqadi.
Bir necha blok bo'lsa ketma-ket qo'shiladi.

Kodlar jadvalining manbasi — sexning "Jarayon uchun kodlar" varag'i (repoda saqlanmaydi,
sexda yuritiladi). Quyidagi jadval va `PROCESS_POSTS`
(`backend/app/services/giblab/models.py`) aynan shunga mos; sexda kod o'zgarsa
ikkalasi birga yangilanadi. Ziddiyat chiqsa — bajariladigan manba `PROCESS_POSTS`.

| Kod | Jarayon | Post |
|---|---|---|
| 1 | Raspil | ARRA |
| 2 | 45° kesish | ARRA |
| 3 | Kromka | KROMKA |
| 4 | Fasat kromka | KROMKA |
| 5 | Oval kromka | OVAL |
| 6 | Prisadka | PRISADKA |
| 7 | Rover | ROVER |
| 8 | Bo'yoq | BOYOQ |
| 9 | Baget | STOLYARKA |
| 10 | Utalshonka | STOLYARKA |
| 11 | G petlya o'ngdan | STOLYARKA |
| 12 | G petlya chapdan | STOLYARKA |
| 13 | V petlya o'ngdan | STOLYARKA |
| 14 | V petlya chapdan | STOLYARKA |

Paz uchun kod yo'q — paz alohida post emas, u frezer stanogida (ROVER) kesiladi.

**Validatsiya — hammasi yoki hech narsa.** Bitta token raqam bo'lmasa yoki jadvalda bunday
kod bo'lmasa BUTUN ro'yxat rad etiladi va detal odatdagi fayl bosqichlari bilan ketadi.
Yarim o'qilgan marshrut detalni bilintirmay bosqichdan chiqarib yuborardi; rad etilgani esa
matritsada ko'rinib turadi va ogohlantirish ham beriladi.

Marshrutning o'zi qanday qurilishi (fayl bosqichlari BUTUNLAY almashtiriladi, ARRA avtomatik
qo'shilmaydi, `per_instance` hisobi, qavs matni nomda qolishi) — [09-mes-domain.md](09-mes-domain.md) §2.

---

## 3. Operatsiyalar — `<operation typeId="...">`

GibLab "+Операция" ro'yxatida **to'qqiz tur** taklif qiladi:

| `typeId` | Nomi | MebeliX |
|---|---|---|
| `CS` | Листовой раскрой — listni kesish | ✅ kesish xaritasi + yorliq raqamlari |
| `EL` | Кромкооблицовка — kromkalash | ✅ kromka simvoli va materiali |
| `XNC` | Обработка — CNC ishlov | ✅ teshik → PRISADKA, paz va freza → ROVER bosqichi |
| `O` | Комплектация — furnitura komplekti | ataylab jim: sanoqlar `simple` goodlarida bor |
| `LB` | Этикетки — yorliq shablonlari | ataylab jim: tizim o'z yorlig'ini chiqaradi (TZ 5.2.8) |
| `CL` | Погонажный раскрой — profil kesish | ataylab jim + **ma'lumot yoziladi**: sexda profil kesish posti yo'q, profillar tayyor keladi |
| `CN` | Нестинговый раскрой — CNC nesting | ❌ ogohlantirish. GibLab'ga 2021-05 da qo'shilgan |
| `SP` | Обработка поверхности — yuza ishlovi | ❌ ogohlantirish |
| `GR` | Пазование — paz | ❌ ogohlantirish (paz XNC dan aniqlanadi, ROVER bosqichiga tushadi) |

`CN`, `SP`, `GR` korpusda umuman uchramaydi. `CL` esa `kupe.project` da 3 ta, `TV_zonakupe`
da 1 ta — ularning `<part>` lari `X1..X32` kodli alyuminiy profillar, 3200 mm zagotovkadan
kesiladi va listda umuman joylashtirilmaydi.

Har operatsiyada bo'ladigan umumiy atributlar: `id`, `typeId`, `typeName` (ko'rinadigan nom),
`description`, `costOperation`/`costMaterial`/`costTotal`, **`owner`** (operatsiya mahsulotga
yoki proyektga tegishli), `printable`, `startNewPage`. Oxirgi uchtasi chop etish sozlamasi;
`owner` korpusda yozilmaydi va bizning EL simvol biriktirish barcha mahsulotlarni ko'rib
chiqadi, ya'ni egasidan qat'i nazar to'g'ri ishlaydi.

### 3.0 Operatsiya materiali — `<material>`

`id` (goodga havola), `count` (miqdor) va **`used`** (operatsiyadagi vazifasi). Spetsifikatsiya
`used="base"` uchun ikki ma'no beradi:

- **kesishda** — asosiy listli material;
- **kromkalashda** — облицовочная лента, ya'ni **kley emas, lentaning o'zi**.

Shuning uchun parser materialni tartib bo'yicha emas, `used="base"` bo'yicha tanlaydi.
Korpusda kesish/kromkalash operatsiyalarida material doim bitta (`used` ham yozilmagan);
bittadan ko'p material faqat `O` (komplektatsiya) da uchraydi — 8/10/37 tagacha.

Kromka lentasining nomi odatda detalning `el{tomon}Mat` atributida bo'ladi, **lekin har doim
emas**: korpusdagi 779 kromkalangan qirradan 112 tasida u yozilmagan. Ikkisi ham bor bo'lgan
667 holatda EL operatsiyasining bazaviy materiali bilan **nomlar aynan bir xil**, shuning
uchun yozilmagan holatda operatsiyadan olinadi — aks holda yorliqdagi lenta katakchasi bo'sh
chiqib, kromkachi qaysi lentani olishini bilmasdi.

### 3.1 CS — kesish xaritasi

`data` atributi — **base64, shifrlanmagan big-endian binar blob**. Ichida naqshlar (patterns),
har birida daraxt ko'rinishidagi kesish yozuvlari. `csblob.py` uni ochadi.

Muhim tushunchalar:

- **Кратность (`mult`)** — bitta naqsh necha marta takrorlanadi. Xaritada `C:2` deb ko'rinadi
- **Torsovka** (`cTrimL`, `cTrimW`) — listning chetidan olinadigan qirqim, **spetsifikatsiya
  bo'yicha default 10 mm** (sexning fayllarida doim 2 mm yozilgan; eski eksportda umuman yo'q).
  `cTrimEL`/`cTrimEW` — pastdan va o'ngdan minimal chekinish, manfiy bo'lsa `cTrimL`/`cTrimW`
  ishlatiladi
- **Deloviy qoldiq** — `waste="true" business="true"` bo'lgan `<part>`; foydali o'lchami
  ta'rifda, xom o'lchami `rl`/`rw` da (parser `rl`/`rw` ni o'qimaydi)
- **`cPartCount`** — joylashtirilgan katakchalar soni. Parser blobni yettita statistika
  (`cMaterialCount`, `cPartCount`, `cCountPackets`, `cWasteAmount`, `cPartAmount`,
  `cTrimLength`, `cTrimCount`) bilan solishtiradi (`csblob.self_check`); mos kelmasa
  **butun fayl rad etiladi** — `ParseError("Kesish xaritasi mos kelmadi: ...")`,
  dastlabki 5 muammo sanab beriladi (`cutmap.py`)

CS operatsiyasida `<part>` ro'yxati bor, lekin **ro'yxatda bo'lish joylashtirilganini
bildirmaydi**: `usedCount="0"` bo'lsa GibLab uni ataylab joylashtirmagan (material yetmagan
yoki dizayner chiqarib tashlagan). `kuxniya.project` da uchta shunday detal bor.

**Mahsulot soni ko'paytmasi.** `<part count>` — BITTA mahsulotdagi soni; buyurtmadagi jami =
u × `<good typeId="product" count>`. Xarita jami nusxani joylashtiradi: 205-korpusda
`count="3"` li mahsulotning 3 detali xaritada 9 katak. 8-faylli korpusda mahsulot soni doim 1
edi, shuning uchun bu ko'rinmagan — 7 faylda xarita mos kelmay fayl rad etilardi.

**Slot torsovkasiz xaritada.** Blob slotining uchinchi ko'rinishi (205-korpusdagi XDF listlar,
torsovkasiz kesilgan): slot `type=2/3/4` — u yetakchi qirqim emas, **birinchi haqiqiy yozuvning
o'zi** (polosa/detal/qoldiq); vertikal boshlanish, daraxtga birinchi bo'lib qo'shiladi. Aks
holda birinchi polosa butun detallari bilan yo'qolardi.

**Blobsiz kesish operatsiyasi.** Optimallashtirilmagan faylda `data` umuman bo'lmaydi (korpusdagi
ikki eski faylda 10 ta shunday CS bor) — bunda fayl `template` deb belgilanadi va yuklashda
HTTP 422 bilan **rad etiladi** ("Bu fayl GibLabda hali optimizatsiya qilinmagan..." —
`orders.py`, upload). `processed` bo'lishi uchun blob bilan birga `project.uuid` ham bo'lishi
shart (`parser.py`). Lekin optimallashtirilgan faylda ham bitta materialni optimallashtirmaslik
mumkin: o'shanda uning detallari arrachiga tushib, xaritasi bo'lmaydi. Xarita quruvchi bunday
operatsiyani jimgina o'tkazib yuboradi (nusxa tekshiruvi nolni sanamaydi), shuning uchun parser
materialni **nomi bilan** aytadi.

**`draw` — xaritaning ikkinchi ko'rinishi.** `cSaveDrawCut="true"` bo'lsa GibLab xaritani
blobdan tashqari **o'qiladigan XML** ko'rinishida ham yozadi:

| Teg | Nima | Atributlar |
|---|---|---|
| `p` | Kesish kartasi | `l` list uzunligi, `w` kengligi, `c` listlar soni, `cm` izoh, `sheetId`, `tl`/`tw` torsovka |
| `c` | Rez | `x`, `y`, `l`, `w` |
| `d` | Detal | `x`, `y`, `l`, `w`, `id` (detalga havola) |
| `r` | Qoldiq | `x`, `y`, `l`, `w`, `id` |

Koordinatalar absolyut, ya'ni bu blobni ochmasdan xarita qurish uchun yetarli. Korpusdagi
8 faylda `cSaveDrawCut` doim `false` va `draw` hech qayerda yo'q, shuning uchun parser uni
o'qimaydi — blob yagona manba.

**Teshiklar xarita modelida.** Har detalning XNC dasturlari birlashtirilib (dublikatlar
olib tashlanadi, `merged_machining`) xarita modeliga `holes` bo'limi sifatida yoziladi
(`cutmap.py`). Bitta manbani ARRA terminal xaritasi (`CutmapView`/`SheetSvg`) ham,
yorliqdagi teshik eskizi (`labels.py`) ham o'qiydi.

Boshqa optimizator sozlamalari: `csDirectCut` (birinchi rez yo'nalishi: 0 ixtiyoriy, 1 uzunlik
bo'ylab, 2 kenglik bo'ylab, 3/4 afzal ko'rilgan), `csTexture` (tekstura hisobga olinadi,
default true), `cFillRep`, `cMinDimRegWaste1/2`, `cBusinessWaste`, `cTrimWaster`,
`cMinDimDetail` — hammasi GibLab xaritani qanday hisoblaganini bildiradi, natijaga emas.
`*P` bilan tugagan statistikalar (`cTrimLengthP`, `cPartCountP`, ...) — karta shakllangunga
qadar **oldindan hisob**; biz yakuniy qiymatlarni olamiz.

### 3.2 XNC — ishlov dasturi

`program` atributi — ichki XML hujjat (HTML-escape qilingan). Ba'zi eksportlarda
`<program>` alohida bola element sifatida keladi.

Ildiz atributlari: `dx`/`dy`/`dz` (yangi) yoki `l`/`w`/`thick` (eski).

**Operatsiya darajasidagi atributlar** — bular butun dasturga ta'sir qiladi:

| Atribut | Nima | Bizda |
|---|---|---|
| `side` | Detal tomoni, default `true` = yuz tomon. Eski eksport `1`/`0` deb yozadi | ✅ **tomonning asosiy manbasi** (yozilmasa — kod suffiksi) |
| `turn` | Burilish: 0=0°, 1=90°, 2=180°, 3=270° | ❌ ogohlantirish |
| `mirHor` / `mirVert` | Gorizontal / vertikal aks ettirish | ✅ geometriyaga qo'llanadi (`xnc.apply_mirror`) |
| `bySizeDetail` | Koordinatalar detal o'lchamiga nisbatan | korpusda 505/505 `true`; dastur `dx/dy` si detal o'lchamiga 501 holatda aynan teng |
| `count` | Detallar soni (detalga bog'langan bo'lsa detal sonidan olinadi) | detal sonini `<part>` dan olamiz |
| `code` | Dastur kodi | ✅ SCX nomi va identifikatsiya |
| `price*` / `count*` / `cost*` | Teshik/freza/rez narxi va soni | ❌ narx hisobi yo'q |

`side` ni o'qish shart edi, chunki kod suffiksi (`_2`) ishonchsiz:

- `2001_Nukriddin.project` — orqa tomon kodlari `x2` bilan tugaydi (`_2` emas): 16 dastur
  yuz tomon deb belgilanardi;
- `3052_Hikmat.project` — yuz va orqa dasturning kodi **aynan bir xil**: 10 detalda ikkalasi
  bitta SCX nomiga yozilib, biri o'chib ketardi.

Suffiks shunga qaramay **zaxira** bo'lib qoldi: operatsiyada `side` atributi bo'lmasa tomon
baribir kod oxiridagi `_2` bo'yicha aniqlanadi (`xnc.py`, `parse_xnc_program`). Korpusdagi
505 dasturning hammasida `side` bor, ya'ni bu zaxira qadam faqat boshqa eksportlarda
ishga tushadi.

`turn`/`mirHor`/`mirVert` korpusdagi 505 dasturda ham standart holatda (0 / false / false).
Ular ishlatilsa koordinatalarni o'zgartirmaymiz, ya'ni teshiklar boshqa joyga tushardi —
shuning uchun jimgina xato chiqarish o'rniga ogohlantiriladi.

Spetsifikatsiyadagi element to'plami:

| Teg | Nima | Bizda |
|---|---|---|
| `tool` | Asbob (`name`, `d` — diametr) | ✅ |
| `var` | O'zgaruvchi e'loni (`name`, `expr`) | ✅ |
| `bf` | Frontal teshik (`ac`/`as`/`av` bilan qator bo'lishi mumkin) | ✅ qator kengaytiriladi |
| `bt` / `bb` / `bl` / `br` | Qirra teshigi (tepa/past/chap/o'ng); qator chet bo'ylab | ✅ qator kengaytiriladi |
| `gr` | Paz | ✅ |
| `ms` | Freza kirish nuqtasi | ✅ |
| `ml` | To'g'ri chiziq bo'ylab frezalash | ✅ |
| `mac` | Markazi berilgan yoy bo'ylab frezalash | ✅ |
| `ma` | Yoy bo'ylab frezalash | ❌ ogohlantirish |
| `xy` | **Koordinata boshi** | ❌ ogohlantirish |
| `oq` / `oh` | Eski avlod arra/paz asboblari | ✅ (pazga o'giriladi) |

**Atribut merosi.** Spetsifikatsiya aniq aytadi: `dp`, `ac`, `as`, `z`, `x`, `y` kabi atribut
**yozilmasa "oldingi qiymat" olinadi**. Parser buni teg bo'yicha yuritadi (pazning chuqurligi
keyingi teshikka o'tib ketmasligi uchun). Ilgari `dp` yo'q bo'lsa ParseError chiqib **butun
fayl rad etilardi**.

**Teshik qatori.** `ac` (soni), `as` (qadam), `av` (vertikal=true / gorizontal=false) —
bitta element **teshik qatorini** bildiradi. 32 mm javon teshiklari aynan shunday beriladi.
Korpusda `ac` doim 1 (3382 holat), lekin qator ishlatilsa ilgari bitta teshik chizilardi va
**SCX faylga ham bittasi tushardi** — ya'ni dastgoh kam teshik teshardi. Endi kengaytiriladi.

**`enable="false"`** — element o'chirilgan (default `true`). Ilgari o'qilmasdi, ya'ni GibLab
ataylab o'chirgan teshik chizilib SCX'ga ham tushardi.

`xy` alohida xavfli: u koordinata boshini belgilaydi, ya'ni e'tiborsiz qolsa undan keyingi
**barcha teshik joylari xato** bo'ladi. Korpusda ikkalasi ham uchramaydi, lekin jimgina
buzilmaslik uchun ogohlantirish qo'shilgan.

**Pazning oxiri.** `gr` da `x2`/`y2` yozilmasa **shu elementning** `x1`/`y1` i olinadi — bu
umumiy "oldingi qiymat" merosidan farq qiladi. Parser atribut borligini alohida tekshiradi,
aks holda ikkinchi paz birinchisining oxirigacha cho'zilib detalni kesib yuborardi.

**Qirra teshigining balandligi.** `m` (Середина по Z, default `true`): `true` → teshik
qalinlik **markazida**, `z` e'tiborsiz; `false` → `z` **absolyut** balandlik. 205-korpus buni
bir ma'noda isbotlaydi: `m="false"` faqat markazdan chetlashganda yoziladi (z=7.5, 8.5, 10,
2.5...), `m="true"` da esa `z=16 dz=16` (yuzaning o'zida — fizik imkonsiz) ham uchraydi, ya'ni
GibLab `m=true` da `z` ni o'qimaydi. Eng katta real holat: 32 mm qo'shqavat plitada `z=8
m=true` — 310 teshik markazda (16 mm) burg'ulanadi, 8 mm da emas.

**O'qilmagan element atributlari:**

| Atribut | Nima | Nega o'qilmaydi |
|---|---|---|
| `comment` (barcha elementlarda) | Dizaynerning izohi, masalan `LED PAZ (H-4 G-5 dx-0)` | Ko'rsatadigan joy yo'q. Operator ekraniga chiqarish — kelajakdagi imkoniyat (korpusda 180 pazda va 44 frezada bor) |
| `ms.sdp` / `ms.sxy` | Chuqurlik va gorizontal qadam (bir necha o'tishda frezalash) | Dastgoh ishi; SCX konturni bir marta beradi. Korpusda `sxy` 32 marta, `sdp` yo'q |
| `ms.c` / `gr.c` | Radius korreksiyasi (0=markaz, 1=o'ng, 2=chap) | Korpusda `gr.c` 180 pazda ham **0 = markaz bo'yicha**, ya'ni bizning taxminimizga mos. `ms.c` esa SCX ga o'tadi |
| `ms.in` / `ms.out` | Kirish/chiqish turi | Dastgoh sozlamasi (korpusda 99 marta) |
| `ma.r` / `ma.dir` | Yoy radiusi (manfiy → yo'nalish teskari) va yo'nalishi | `ma` umuman o'qilmaydi — ogohlantirish |
| `ml.dp` / `mac.dp` | Segmentning o'z chuqurligi | GibLab hech qachon yozmaydi (korpusda 354 `ml` va 25 `mac` da ham yo'q); chuqurlik `ms.dp` dan |

**Spetsifikatsiyada yo'q atribut:** `gr.p` — korpusdagi 28 pazda (hammasi `3052_Hikmat` da:
20 tasi "LED PAZ", 8 tasi "bok paz") bor va doim `0`. Hujjatlashtirilmagan, o'zgarmas —
e'tiborsiz qoldirilgan.

**Standart konstantalar.** Yangi eksport ularni `<var>` bilan e'lon qiladi, eski (2021 buildi)
esa e'lonsiz ishlatadi. Qiymatlar korpusda hamma joyda bir xil:

```
throughBoreDepth = dz + 3.00     # teshib o'tuvchi teshik chuqurligi
throughCutDepth  = dz + 3.00     # teshib o'tuvchi frezalash chuqurligi
contMillDepth    = dz            # kontur bo'ylab frezalash
```

Parser ularni oldindan qo'yadi; fayl `<var>` bilan e'lon qilsa u ustun keladi.

Ifodalar (`dz+3` kabi) faqat oq ro'yxatdagi arifmetika bilan hisoblanadi: raqam,
identifikator, `+ - * / ( ) .`; `**` alohida taqiqlangan (`9**9**9` workerni osiltirib
qo'yardi — DoS himoyasi). Xavfsiz bo'lmagan yoki hisoblab bo'lmaydigan ifoda `ParseError`
beradi va fayl rad etiladi (`xnc.py`, `_eval_expr`).

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
termoprinter uchun. Ichida QR (`{productCode}_{partCode}` — yagona nusxa suffikssiz, takrorlanganda `_{n}`), matn qatorida ham shu nusxa ID (QR va SCX nomi bilan bir xil satr; matn qatori 20 belgigacha qisqartiriladi, QR to'liq — [11-detal-id-nomlash.md](11-detal-id-nomlash.md)), detal nomi, buyurtma,
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
o'lcham zanjiri), teshik/paz/freza (XNC), yorliq raqami, SCX generatsiyasi, detal nomidagi
marshrut kodlari (§2.3).

**Ataylab e'tiborsiz:** GibLab yorliq shablonlari (`LB`), optimizatsiya va narx parametrlari
(GibLab ichida ishlaydi, biz natijasini iste'mol qilamiz), arra postprotsessorlari,
profil kesish (`CL` — sexda bunday post yo'q).

**Ogohlantirish beradigan holatlar** (`parser.py`, `ingest.py`):

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
| XNC operatsiya noma'lum detalga ishora qiladi | shu dasturning BUTUN ishlovi (teshik, paz, freza) detalga biriktirilmaydi va yo'qoladi |
| `description` da `#kod` | ishlov shablon nomi bilan berilgan, o'qilmaydi |
| Xaritada joyi yo'q detal | arrachi ro'yxatiga tushmaydi |
| `turn` ≠ 0 | dastur aylantirilgan — aylantirish qo'llanmaydi, CNC'da tekshirish shart (`mirHor`/`mirVert` esa parse'da geometriyaga QO'LLANADI — `xnc.apply_mirror`) |
| Blobsiz kesish operatsiyasi | material optimallashtirilmagan, xaritasi yo'q |
| Nomdan olingan marshrut (§2.3) | N detalning marshruti nomdagi ro'yxatdan olindi, ular uchun fayl bosqichlari hisobga olinmadi |
| Nomdagi qavs o'qilmadi | qaysi detallar ekani sanaladi; qavs ichida faqat 1–14 oralig'idagi kodlar bo'lishi kerak |

Yarmi — 16 qatordan 8 tasi — `_advisories` da yig'iladi, qolgani boshqa joylarda: dastlabki
uchtasi detal qurilishida yoziladi (`_build_part`, `_dedupe_part_code`), "Blobsiz kesish
operatsiyasi" — `parse_project` generatsiyani aniqlaganda, "XNC operatsiya noma'lum detalga
ishora qiladi" — dasturlar detalga biriktirilayotganda (`parse_project`, `merge_xnc_ops` dan
oldin), "Xaritada joyi yo'q detal" esa xarita qurilgandan keyin `ingest.py` da.

Oxirgi ikkitasi — `_custom_route_warnings`, ataylab **yig'ma**: yuklash javobida ogohlantirishlarning
faqat dastlabki bir nechtasi ko'rsatiladi, har detalga bittadan yozilsa qolgani ko'rinmay ketardi.

Bu xabarlar yuklash javobida ko'rsatiladi (dastlabki 3 tasi, qolgani soni bilan) va
to'liq ro'yxat audit logga yoziladi (`POST /orders/{id}/upload`).

**Fayl butunlay rad etiladigan holatlar** (`ParseError` → HTTP 422, ogohlantirish emas):

- optimallashtirilmagan (`template`) fayl — §3.1;
- kesish xaritasi blob statistikasiga mos kelmasa — §3.1;
- ikki detal bir xil nusxa QR bersa (masalan `010` ×2 nusxa va `010_2` kodli detal) —
  `ingest.py` buni yozishdan OLDIN tekshiradi, unique-indeks 500 o'rniga do'stona xato;
- detal yoki mahsulot kodida `/`, `\` yoki `..` bo'lsa (`parser.py`) — kod QR/SCX fayl
  nomiga aylanadi, yo'l belgilari uploads tashqarisiga yozishga olib borardi; yuklangan
  fayl nomi ham faqat basename bilan saqlanadi (`ingest.py`);
- XNC ifodasi xavfsiz bo'lmasa yoki hisoblanmasa — §3.2.

### 7.1 Qamrov — spetsifikatsiyadagi 289 atribut

Rasmiy hujjat (`help/format_ru.html`) 31 blokda 289 atribut ta'riflaydi. Ulardan yarmiga
yaqini o'qiladi, qolgani ataylab tashlanadi (2026-08-05 refactor'ida o'qilib-u hech qayerda
ishlatilmaydigan maydonlar — `elRestSide`, `rl`/`rw`, `currency`, `version` — o'qishdan ham
olib tashlandi). Tashlanganlar to'rt guruhga bo'linadi:

| Guruh | Nechta | Nega |
|---|---|---|
| Narx va qiymat (`cost*`, `price*`, `cCost*`, `elCost`, `spCost`, `grCost`) | ~45 | Sex narxni MebeliX'dan tashqarida hisoblaydi |
| Optimizator sozlamalari (`sw*`, `cs*`, `cMinDim*`, `cFillRep`, `elRound*`, `elCalcMat`, `sp*`) | ~40 | GibLab xaritani ular bilan hisoblagan; biz **natijani** iste'mol qilamiz, qayta hisoblamaymiz |
| Oldindan hisob (`*P` bilan tugaganlar) va `cCPF` | ~10 | Karta shakllangunga qadar taxmin; yakuniy qiymatlar bor |
| Chop etish va maket (`LB` bo'limi, `printable`, `startNewPage`, `cSaveDrawCut`, `margin`, `border`) | ~25 | Tizim o'z yorlig'i va hujjatlarini chiqaradi |

Qolganlari — `comment`, `owner`, `typeName`, `usedCount`, `groupInBlock*`, per-list torsovka,
`draw`, `GR`/`SP` operatsiya parametrlari (`grWidth`, `grDepth`, `grOffset`, `grOffsetIncl`,
`grSawthick`, `grCuttingLength`) — **korpusda ishlatilmagan yoki ko'rsatadigan joyi yo'q**;
har biri yuqoridagi jadvallarda alohida izohlangan. `GR` paydo bo'lsa uning `grWidth`/`grDepth`/
`grOffset` i to'g'ridan-to'g'ri ROVER bosqichiga geometriya beradi — hozir esa faqat ogohlantirish.

`EL` operatsiyasidan `elSymbol` (xarita simvoli) o'qiladi; `elColor` (simvol rangi) va
`elLineMark` (markirovka chizig'i) o'qilmaydi — bizning xaritada kromka o'z uslubida
chiziladi. `elLength` (kromkalash uzunligi) ham o'qilmaydi: lenta sarfini material
registridan olamiz.

---

### 7.2 SCX eksport konvensiyasi (`scx.py`)

Qoidalar `D:\MebeliX\Scx` korpusidan keltirilgan (87 proyekt, 5286 etalon fayl; 10500 qirra
teshigi, 218 freza ovoz bergan) — GibLab'ning JORIY eksporti bilan semantik bir xil, sexdagi
Nanxing aynan shu formatni yeydi. 71/86 papka 100% mos; qolganlari .project fayl versiyasi
eksportdan farq qilgan holatlar (dizayner keyin o'zgartirgan), generator xatosi emas.

| Element | Qoida |
|---|---|
| Yuza teshik (Face 5) | `Y = Width − y_program`, X o'zgarmaydi |
| Qirra teshik Face | l→4, r→3, t→1, b→2; l/r: X=0/Length, Y=Width−pos; t: X=pos **Y=Width**; b: X=pos **Y=0** |
| Kromka lenta Face | qirra bilan bir xil (l4 r3 t1 b2); Edge'da `Pre_Milling`, `X`, `Y` atributlari |
| Orqa (`_2`) dastur | ALOHIDA FAYL EMAS — yuza elementlari `Face="6"` bilan asosiy nusxa-fayliga (transform old bilan bir xil `x, W−y`) |
| Qo'shqavat (2×plita) | eksport qalinligi plita bo'yicha (32→16), qirra Z ikki baravar kichik, yuza chuqurlik bir qatlamga kamayadi (35→19). Shart: dz ≈ 2×plita qalinligi (material bo'yicha, `ingest` dan) YOKI dz≈32; 18/26/40 o'zgarmaydi |
| Freza (Type 3) | KOMPENSATSIYALANGAN asbob-markazi yo'li: `ms.c`=2 harakatga chapga r, `c`=1 o'ngga, yoy radiusi mos o'zgaradi; `<Lines><Line Angle=…>` formati (Angle=0 chiziq, ±N yoy sweep'i); `c`=0 xom; panel cheti bo'ylab trim xom + `ToolOffset=右` |
| Atributlar | Machining'da ketma-ket `ID` (1000+) va `IsGenCode="2"`, Panel'da `MachiningPoint="1"` |
| Fayl nomi | har nusxaga bitta to'liq fayl, nom/Panel ID = nusxa QR — yagona nusxada suffikssiz (`100701_02_003.scx`), takrorlanganda `_1.._n` (`100701_02_003_1.scx`) — Nanxing skaneri va chekdagi kod bir xil |

Eski buyurtmalar fayllari diskda eski konvensiyada qolgan bo'lsa — buyurtma sahifasidagi
"SCX qayta yaratish" tugmasi (`POST /orders/{id}/scx/regenerate`). Birinchi yuklash ham,
qayta yaratish ham bitta yo'ldan o'tadi — `ingest.write_and_register_scx()` (fayl nomi/joyi
va `OrderFile` maydonlari bir joyda).

---

## 8. Bog'lanishlar

- Parser: `backend/app/services/giblab/parser.py` (tovarlar, detallar, operatsiyalar, advisory)
- Umumiy modellar: `models.py` (`ParsedProject`/`ParsedPart`, `PROCESS_POSTS`, `xml_bool`, `ParseError`)
- Blob: `csblob.py` (base64 binar + `self_check`), `cutmap.py` (vizual model + instance↔katakcha binding + `holes`)
- Ishlov: `xnc.py` (dastur XML), `scx.py` (CNC fayl generatsiyasi)
- DB'ga yozish: `ingest.py` (mahsulot/detal/nusxa/marshrut, material registri, sarf hisobi, SCX yozish)
- `giblab/__init__.py` faqat ikki nom eksport qiladi: `ParseError` va `parse_project`; `ingest`
  funksiyalari (`ingest_project`, `wipe_previous_parse`, `write_and_register_scx`) submoduldan
  to'g'ridan-to'g'ri olinadi (`orders.py`)
- Korpus fayllari git'ga tushmaydi (`.gitignore`: `uploads/`), lekin lokal `uploads/projects/`
  da turadi — parser o'zgarishida real .project fayllarga qarshi qo'lda tekshiriladi
- Hujjatdagi sanoqlar SAKKIZTA fayl bo'yicha o'lchangan: `01 shkaf`, `02 kitob javon`,
  `1007 Yangibozor`, `2001_Nukriddin`, `3052_Hikmat`, `kupe`, `kuxniya`, `TV_zonakupe`
  (yangi eksport — `uploads/1160.project` — alohida ko'rsatiladi). Papkada turgan
  `4273_Dilmurod.project` bu sanoqqa kirmaydi — u qo'shilsa hamma raqam o'zgaradi
- Domen tomoni: `docs/09-mes-domain.md`, API: `docs/03-backend-api.md`
