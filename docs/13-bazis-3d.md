# Bazis 3D modeli va yig'uvchiga ochiq havola

Texnolog `.project` yoniga Bazis `.b3d` faylini yuklaydi; MES undan brauzerga
tayyor model yasaydi va buyurtmaga **bitta ochiq havola** ochadi. Havolani usta
ham, mijoz ham ochadi — tizimga kirmasdan, telefon yoki planshetda. Namuna:
sanoatda shunga o'xshash ochiq xizmat — `detalqr.uz`.

Bu hujjat ikki narsani yozadi: **`.b3d` format** (Bazisda hujjati yo'q, teskari
muhandislik bilan aniqlangan) va **modulning o'zi** (oqim, himoya, UI).

---

## 1. Nega kerak

Yig'uvchi qo'lida detal bor: unda chek (Detal ID) yopishtirilgan. Savol bitta —
**bu detal qayerga ketadi?** Chizmada topish sekin, telefonga chizma yuborish
bundan ham yomon. Ochiq havolada u mahsulotni 3D da aylantirib ko'radi, kodni
terib qidiradi va detalning joyini ko'radi.

MESda bu ma'lumot YO'Q edi: `.project` faqat detal ro'yxati va kesish xaritasi,
uch o'lchovli joylashuv haqida unda hech narsa yo'q. Joylashuv faqat Bazisda.

---

## 2. `.b3d` format

Bazis formatni hujjatlashtirmagan. Quyidagi tavsif **22 ta namuna faylda**
(0.1–20 MB, 4 xil Bazis build'i, 2285 panel) o'lchab aniqlangan.

### 2.1 Konteyner

```
"BZ85"                     4 bayt — sehrli sarlavha
01 00 00 FF | 00           bo'lim ajratgichi + siqilganlik bayrog'i (00 = xom)
  <sarlavha daraxti>       siqilmagan
01 00 00 FF | 01           ikkinchi bo'lim, 01 = zlib
  <zlib(model daraxti)>    fayl oxirigacha
```

22 namunaning HAMMASIDA aynan shu ikki bo'lim va aynan shu ajratgich.
Parser shu sababli oqim ichidan zlib IZLAMAYDI — ofsetlar ketma-ket olinadi.

### 2.2 Daraxt kodlashi

Har bo'lim tanasi kalitlar jadvali bilan boshlanadi, keyin tugunlar:

```
kalitlar:   u32 son | (u32 uzunlik | ASCII nom) × son
tugun:      u32 kalit_indeksi | u32 bolalar_soni | u8 tur | qiymat
```

Tugunlar ketma-ket yoziladi; ichki tugunlar otasidan keyin darhol keladi
(prefiks tartibi), ya'ni daraxt bitta o'tishda tiklanadi.

| Tur | Qiymat | Uzunlik |
|---|---|---|
| 0, 1, 2 | yo'q (belgi) | 0 |
| 3 | `int8` | 1 |
| 4 | `int32` | 4 |
| 5 | `double` | 8 |
| 6 | UTF-16LE satr | `u32` belgi soni + 2×N |
| 7 | xom baytlar (blob) | `u32` + N |
| 8 | teglangan: `u32 teg`, `u32 teg2`, `u8 ichki tur`, ichki qiymat | 9 + ichki |
| 9 | `int64` | 8 |
| 10 | `float32` | 4 |
| 11 | `int16` | 2 |

**8-tur tuzoq:** bolalar soni TASHQI tugundan olinadi, teg ichidan emas.
Noto'g'ri o'qilsa daraxt shu yerdan siljib ketadi.

### 2.3 Sarlavha bo'limi

```
Header
  Version = 15
  Thumbnail = <PNG 256×256, 6–58 KB>
  Article
    Code = "208301"          <- Product.code AYNAN
    Name = "01 TV ZONA"
    OrderName = "2083 Ilyos aka"
    ID, Params, LDistance, Furniture, FileType, ExtraInfo, RotationList
```

`Thumbnail` — **tayyor PNG**, Bazisning o'zi chizgan. Ochiq sahifadagi
mahsulot kartochkasi shundan, hech narsa render qilinmaydi. Yuklashda
`viewer.thumbnail_png()` uni kartochkaga moslaydi — sababi §7.1 da.

### 2.4 Model bo'limi

```
Document
  VersionMajor, VersionMinor
  Estimate            smeta
  FurnList            furnitura ro'yxati
  Model
    Obj (Type=1005)   guruh (shkaf, sektsiya, "animatsiya", ...)
      Trans           X Y Z Rx Ry Rz Rw  <- OTAGA nisbatan
      Anim            ochilish (eshik/tortma) — 2.7-bo'lim
      Objs
        Obj (...)     ichma-ich, 25 qavatgacha
        Obj (Type=4002)   PANEL
    Undo              tahrirlash tarixi — faylning 13–90% i
  ModelParams, Camera, HardwareKey, AppVersion, DateTimeLastSaved
```

Panel tuguni:

| Kalit | Ma'no |
|---|---|
| `Type` | `4002` — panel |
| `Des` | detal kodi (`01_005`) = `.project` dagi `part code` |
| `Name` | nomi (`Fasad`, `polka`) |
| `Mat` | `"nom\rkod"` — material nomi va kodi bitta satrda |
| `Thick` | qalinlik, mm |
| `Contour` | blob — panelning o'z tekisligidagi kontur |
| `Trans` | joylashuv + kvaternion |
| `Butts` | `Butt` ro'yxati — kromka |
| `TexDir` | tekstura yo'nalishi |

`Butt`: `Mat`, `Thick`, `Width`, **`Elem`** (kontur segmenti raqami — kromka
qaysi chetda ekani shundan), `Sign`, `Overhung`, `Allowance`, `Clip`.

### 2.5 `Contour` blobi

```
u32 segment soni
segment: u8 turi | qiymatlar
```

| Turi | Ma'no | Qiymatlar | Uzunlik |
|---|---|---|---|
| `0x10` | chiziq | `x1 y1 x2 y2` (double) | 33 |
| `0x11` | aylana | `cx cy r` (double) | 25 |
| `0x12` | yoy | 6 double + 1 bayt yo'nalish | 50 |

22 namunaning 2285 panelidagi **9675 segment**: chiziq 9555 (98.8%), yoy 110
(1.1%), aylana 9 (0.09%), noma'lum `0x14` 1 ta (0.01%). Aylana odatda
paneldagi KESMA (rozetka, rakovina) — namunalarda 7 ta panelda uchradi.
Konturning O'ZI aylana bo'lsa bu yumaloq javon: u 48 nuqtali ko'pburchakka
aylantiriladi va panel `is_round` bilan belgilanadi, chunki `Butt.Elem`
raqamlari endi bu nuqtalarga mos kelmaydi. Namunalarda bunday panel yo'q —
himoya oldindan qo'yilgan.

### 2.6 Joylashuv

Joylashuv **iyerarxik**: panelning dunyodagi o'rni ildizdan barggacha
`Trans` larni ko'paytirib chiqariladi (namunalarda 25 qavatgacha). Bazisning
o'qlari three.js bilan bir xil — **Y tepaga**, o'lchov millimetr, ya'ni hech
narsa aylantirilmaydi.

**Ekstruziya yo'nalishi konturdan `+Z` bo'yicha `Thick` ga.** O'lchov bilan
aniqlangan: uch variantda (0..t, -t..0, markazdan) tegib turgan panel juftlari
sanaldi — 5191 / 1786 / 825. Mebel detallari tegib turadi, ya'ni birinchisi.

### 2.7 Ochilish (eshik va tortma)

**Harakatni BAZISCHI belgilaydi va u faylda saqlanadi** — MES uni faqat
o'ynatadi. `Anim` tuguni `Obj` guruhiga osiladi:

| Kalit | Ma'no |
|---|---|
| `AnimType` | `1` — ilgak (o'q atrofida burilish), `2` — surma (o'q bo'ylab siljish) |
| `AxisStart` / `AxisEnd` | o'q kesmasi, `{x, y, z}`; surmada kesmaning O'ZI harakat |
| `Limit` | burilish burchagi, gradus (`90`, `114.271`) |
| `Shift`, `Duration` | o'qilmaydi — pastda sabab |

22 namunada: **1258** ishchi `Anim` (o'qi nol emas), shundan `AnimType=1`
1047, `AnimType=2` 211; ular jami **570 panelni** harakatlantiradi. 20 fayldan
20 tasida ochiladigan detal bor, 2 tasida (oddiy javon) yo'q.

**437 faylda tekshirildi:** `AnimType` faqat `1`, `2` yoki yo'q (24 075 tugun),
chekli bo'lmagan `Limit` YO'Q, `Limit` ning eng ko'p uchraydigani `-90` (10 104)
va `90` (4468) — ya'ni manfiy burchak odatiy hol. Shunga qaramay parser har
sonni chekli ekaniga tekshiradi: buzuq faylda `NaN` butun modelni ko'rinmas
qilardi, `inf` esa 500 chiqarardi (modulda boshqa hamma nosozlik o'zbekcha 422).

**Ochilgan eshik korpusga kirishi — bu bizning xato EMAS.** 314 ilgakli paneldan
20 tasi (6.4%) boshqa panel ichiga 3 mm dan chuqur kiradi. Nuqtama-nuqta
tekshirdim: **16 tasi XONA devori yoki poli bilan** (burchak shkafning eshigi
devorga tegadi — hayotda ham shunday, Bazisning o'zi ham buni ko'rsatadi),
qolgan 4 tasi haqiqiy detal bilan va atigi 4–8 mm — ilgak kavramasi doirasida.

**O'q koordinatalari animatsiyali tugunning ICHKI fazosida.** O'lchab
aniqlangan: namunadagi ilgak o'qi `x = -310.5`, eshik konturi esa
`x = -309..17` — ya'ni o'q panelning chap chetiga tegib turibdi. Otasining
fazosida bo'lganida u 300 mm narida qolardi.

**Yo'nalish o'qning YO'NALISHIDAN** (o'ng qo'l qoidasi, `+Limit`): bir
shkafning chap va o'ng eshigida o'q qarama-qarshi tomonga yozilgan. Belgi
o'lchov bilan tasdiqlangan — to'g'ri belgida ochilgan eshiklarning korpus
bilan kesishuvi **0.0 litr**, teskarisida **1.4 litr** (eshiklar ichkariga
kirib ketadi).

`Shift` (667 tugunda 16 mm, ya'ni panel qalinligi) ATAYLAB e'tiborsiz:
uni ikki yo'nalishda ham qo'llab o'lchadim — ochilgan eshikning korpusga
kirishi 20 dan 45 (o'q bo'ylab) yoki 18 (yerli +Z) ga o'zgardi, ya'ni u bu
muammoni tushuntirmaydi. Qo'shmaslik soddaroq va natija yomonlashmaydi.

Parser har panelning IKKI holatini hisoblaydi — yopiq va ochiq — va brauzerga
iyerarxiya emas, shu ikkitasi beriladi. Brauzer faqat ular orasida
interpolyatsiya qiladi.

### 2.8 Nimani o'qimaymiz

Ochilgan model **256 MB** bilan cheklangan (`_MAX_OCHILGAN`): zlib nolli
buferni 1000:1 siqadi, ya'ni chegarasiz 40 MB lik fayl 40 GB ga ochilib butun
backendni xotirasiz qoldirishi mumkin edi (bajarib tekshirilgan). Eng katta
haqiqiy namuna 32 MB ga ochiladi.

`Undo` — tahrirlash tarixi, fayl hajmining 13–90% i. Parser unga **kirmaydi**:
o'qishdan to'xtaydi. Ikki sabab: (1) undan hech narsa kerak emas; (2) 22
namunadan 6 tasida uning ichki tuzilmasi o'qilmaydi va to'xtamasak o'sha 6 tasi
"buzilgan" hisoblanardi. Panellar `Undo` dan OLDIN keladi.

---

## 3. MES bilan bog'lanish

| `.b3d` | MES |
|---|---|
| sarlavha `Code` | `Product.code` (`208301`) |
| panel `Des` | `Part.code` (`01_005`) |
| ikkalasi birga | `PartInstance.qr_text` kaliti: `{buyurtma}_{Code}_{Des}[_n]` |

**Bitta `.b3d` = bitta MAHSULOT.** Bazis har mahsulotni alohida faylga
eksport qiladi, ya'ni bitta buyurtmada bir nechta fayl bo'ladi (prodda
o'lchandi: `2083` da uchta — `208301`, `208302`, `208303`).

**Detal kodi bo'yicha bog'lab BO'LMAYDI:** kodlar mahsulot ichida qayta
boshlanadi (`2083 Anvar.project` da `01_004` ikki mahsulotda ham bor), ya'ni
yagona ishonchli kalit — mahsulot kodi.

Kod mos kelmasligi ham bo'ladi: bitta namunada `Code = "1126"` (buyurtma
raqami, mahsulot suffiksisiz). Bunda model baribir ko'rinadi, lekin
`matched=false` va texnologga ogohlantirish chiqadi.

---

## 4. Oqim

```
Texnolog                     MES                              Usta / mijoz
   |                          |                                    |
   |-- .b3d yuklaydi -------->|                                    |
   |                          | read_b3d() -> ParsedBazis          |
   |                          | Product qidiradi (Code bo'yicha)   |
   |                          | diskka: .b3d + .json + .png        |
   |<-- kod, detal soni ------|                                    |
   |-- «Havolani ochish» ---->|                                    |
   |                          | order.share_token = uuid4          |
   |<-- token ----------------|                                    |
   |-- havola / QR ------------------------------------------------>|
   |                          |<-- GET /public/3d/{token} ----------|
   |                          |--- buyurtma raqami + mahsulotlar -->|
   |                          |<-- .../{code}/model ----------------|
   |                          |--- model JSON (4–53 KB) ----------->|
```

**Model yuklashda BIR MARTA yasaladi.** Ochiq so'rovda parser ishga
tushmaydi: namunalarda 2 soniyagacha CPU ketadi, autentifikatsiyasiz bir necha
so'rov butun sexni sekinlashtirardi.

Diskda (`upload_root`):

```
bazis/{order_id}/{product_code}.b3d     manba (qayta ishlash uchun saqlanadi)
bazis/{order_id}/{product_code}.json    brauzer modeli
bazis/{order_id}/{product_code}.png     kartochka eskizi (qayta ishlangan)
```

Mahsulot kodi fayl nomiga aylanadi, shuning uchun `[^A-Za-z0-9_-]` tozalanadi
va 40 belgiga qisqartiriladi (yo'l bo'ylab chiqib ketishga qarshi). Bir xil
kodli fayl qayta yuklansa eskisining o'rnini oladi.

### Model JSON

Kalitlar qisqa — 268 panelli mahsulotda uzun nomlar JSON'ni sezilarli
kattalashtiradi, sahifa esa telefonda ochiladi.

```json
{"v":1,"code":"208301","name":"01 TV ZONA","mats":["LDSP ...","1-19 kashmir"],
 "panels":[{"id":"01_023","n":"Fasad","m":0,"t":16,"s":[326,731],
            "p":[639.5,100,430],"q":[0,0,0,1],
            "o":[[17,0],[-309,0],[-309,731],[17,731]],
            "po":[654,100,457.5],"qo":[0,0.70711,0,0.70711],
            "c":[[160,80,40]]}]}
```

`po`/`qo` — OCHILGAN holatdagi joylashuv va burilish; faqat harakatlanadigan
panelda bo'ladi (2285 dan 570 tasi), qolganida yozilmaydi. `m` — `mats`
massivining indeksi (materiallar takrorlanadi, indeks bilan JSON ikki barobar
kichik). 22 namunada o'lchangan hajm: **4–51 KB**, gzip'dan keyin **0.4–8 KB**.

**KROMKA JSON'ga KIRMAYDI.** Fayldagi `Butts` o'qiladi (§2.5) va parserda
qoladi, lekin brauzerga berilmaydi: kromka materiali, eni va qaysi chetda
ekani ustaning qo'lidagi CHEKDA allaqachon bor — 2×2 jadval va eskizdagi
qalin chiziq bilan (`docs/09`, `render_label_png`). Detal sexdan kromkasi
yopishtirilgan, qadoqlangan holda keladi; 3D ning yagona vazifasi — **detal
qayerga ketishini** aytish. Takror ma'lumot JSON'ni 9% ga shishirardi va
`mats` ro'yxatiga faqat kromka uchun ishlatiladigan nomlarni qo'shardi.

---

## 5. Havola himoyasi

Havolani usta ham, mijoz ham ochadi; **kim ekani bilinmaydi** — ustalar
MESda umuman qayd etilmaydi. Shuning uchun himoya «imkoniyat-havola»
(capability URL) naqshiga quriladi:

| Qoida | Nima uchun |
|---|---|
| Manzilda `uuid4` token, buyurtma raqami EMAS | raqam bo'lsa havolani olgan odam uni o'zgartirib butun sexning buyurtmalarini ochardi |
| Har so'rov TOKEN bo'yicha buyurtmani topadi | `order_id` ochiq modulga tashqaridan hech qachon kirmaydi |
| Yopilgan token 404 (403 emas) | «bunday buyurtma bormi» degan savolga ham javob bermaymiz |
| Fayl yo'li DBdagi qatordan | manzildagi `code` diskka tegmaydi |
| Javobda faqat raqam + geometriya | mijoz nomi, telefoni, narx, ishlab chiqarish holati YO'Q |
| `X-Robots-Tag: noindex, nofollow` | qidiruv tizimi indekslamasin |
| `Referrer-Policy: no-referrer` | havola tashqi saytga oqib ketmasin |
| IP bo'yicha cheklov (60 / 5 daqiqa, faqat XATO urinish) | skanerlash shovqinini to'xtatadi. Hisob kaliti marshrut SHABLONI bo'yicha (`/public/3d/{token}`), real yo'l bo'yicha emas — aks holda har taxmin qilingan token o'z kalitini olib, cheklov umuman ishlamasdi (1000 urinish -> 1000 kalit, har birida 1) |
| Yangilash eski havolani o'ldiradi | havola begonaga tushib qolganda yagona chora |

Muddat YO'Q: yig'uv qachon bo'lishi oldindan ma'lum emas, muddat qo'yilsa
usta ish ustida havolasiz qolardi. Yopish va yangilash — qo'lda.

`api/routes/public.py` — MESdagi **yagona autentifikatsiyasiz modul**, shu
sababli `_protected` dan tashqarida ro'yxatga olinadi.

---

## 6. Endpointlar

| Metod | Path | Rol |
|---|---|---|
| GET | `/api/v1/orders/{id}/bazis` | `StaffReadUser` |
| POST | `/api/v1/orders/{id}/bazis` | `TexnologUser` |
| GET | `/api/v1/orders/{id}/bazis/{file_id}/thumb` | `StaffReadUser` |
| POST | `/api/v1/orders/{id}/bazis/share` | `ManagerOrTexnologUser` |
| DELETE | `/api/v1/orders/{id}/bazis/share` | `ManagerOrTexnologUser` |
| DELETE | `/api/v1/orders/{id}/bazis/{file_id}` | `TexnologUser` |
| GET | `/api/v1/public/3d/{token}` | — |
| GET | `/api/v1/public/3d/{token}/{code}/model` | — |
| GET | `/api/v1/public/3d/{token}/{code}/thumb` | — |

`share` marshrutlari `{file_id}` dan OLDIN e'lon qilinadi — aks holda
`DELETE .../bazis/share` `file_id` deb o'qilib 422 qaytarardi.

Yuklash `can_edit` ga bog'liq EMAS (`.project` dan farqi): model aynan yig'uv
paytida, ya'ni ishlab chiqarish tugagandan KEYIN kerak bo'ladi.

---

## 7. Frontend

| Fayl | Vazifasi |
|---|---|
| `components/Bazis/model.ts` | JSON tiplari (backend `viewer.py` bilan qo'lda oynalangan), material ranglari, qidiruv mosligi |
| `components/Bazis/scene.ts` | three.js sahnasi — Reactdan mustaqil |
| `components/Bazis/ModelViewer.tsx` | Kanvas + qidiruv + detal kartochkasi |
| `routes/3d.$token.tsx` | Ochiq sahifa (`_layout` dan TASHQARIDA) |
| `components/Orders/BazisPanel.tsx` | Texnolog tomoni: yuklash, ro'yxat, havola + QR |

Sarlavhada **to'liq logotip**, ikonka emas: sahifani MebeliX
xodimi emas, usta yoki mijoz ochadi va ular MX belgisini tanimaydi — havolani
kim bergani NOM bilan aytiladi (tablo sarlavhasida ham aynan shu aktiv oq fonda
turadi; ikonka esa loader, favicon va fon bezagi uchun qoladi). Logotip HAVOLA
EMAS: bosilsa mijoz kirish ekraniga tushib qolardi.

**Logotip rangi FONGA qarab tanlanadi**, brend "asosiy rangi" bo'yicha emas:

| fon | logotip | kontrast |
|---|---|---|
| oq `#ffffff` (bu sahifa, tablo) | `logo-navy.png` `#284868` | **9.47:1** |
| to'q navy `#243a59` (sidebar, login) | `logo-gold.png` `#f0a028` | **5.35:1** |

Teskarisi ishlamaydi: tilla oq fonda 2.15:1 (grafika uchun WCAG talab qiladigan
3:1 dan past — sexda, yorug' ekranda o'qilmaydi), navy esa sidebar fonida
1.22:1, ya'ni ko'rinmaydi. Ustiga tilla `#f0a028` 3D dagi TANLANGAN detal
rangi (`#f0a52f`) bilan deyarli bir xil (1.04) — sarlavhadagi tilla belgi
"men qidirayotgan detal" signalini suyultirardi. Navy esa `--primary` ning
o'zi (1.04), ya'ni sarlavha faol segment tugmasi bilan bitta oilada turadi.

three.js faqat `/3d/$token` chunk'ida (`autoCodeSplitting`) — 608 KB, gzip 154 KB;
asosiy bundle'ga tegmaydi.

### 7.1 Mahsulot ro'yxati

Birinchi ekran — kartochkalar to'ri; bitta mahsulot bo'lsa u o'tkazib
yuboriladi va model darhol ochiladi. Kartochkada **eskiz, nom, mahsulot kodi va
detal soni** bor. Kod kerak: bitta buyurtmada bir xil nomli ikki mahsulot
bo'ladi (`01 Kuxniya` ikkita), ularni faqat kod ajratadi.

Nom `OrderFile.meta.product_name` dan: MESda shu kodli mahsulot topilsa —
`Product.name`, aks holda `.b3d` sarlavhasidagi `Name` (ya'ni texnolog Bazisda
yozgani). Ikkalasi ham ustaga tanish.

**Eskiz uch bosqichdan o'tadi** (`viewer.thumbnail_png`, yuklashda bir marta):

1. **Oq fon shaffof qilinadi** — chetdan to'kish (`floodfill`, `thresh=10`),
   global rang almashtirish emas: ichkaridagi oq fasad saqlanib qolishi kerak.
2. **Hoshiya kesiladi.** 256×256 ning ichida mahsulot ~240×140 joy egallaydi;
   qolgani quruq fon (namunalarda 34–60%). Kartochkada model «xira» ko'rinishining
   ASOSIY sababi aynan shu edi — rang emas, o'lcham.
3. **2× Lanczos + yengil `UnsharpMask`**, so'ng **256 rangli palitra.**
   Kartochkadagi joy ~500 px: kattalashtirish baribir bo'ladi, brauzerga
   qoldirilsa chiziqlar xiralashadi. Palitra hajmni 206 KB dan 46 KB ga
   tushiradi (telefonda uchta kartochka birdan yuklanadi).

Kontrast ATAYLAB oshirilmaydi: u yog'ochni sarg'aytirib, materialni boshqacha
ko'rsatib qo'yadi. 75 ta haqiqiy faylda o'lchandi — 6–51 KB, 53–133 ms.
Eskizning o'zi bo'm-bo'sh chiqsa (75 tadan bittasi) asl bayt qaytariladi.

### Sahnadagi qarorlar

**Ko'rinish (studiya).** Fon — WebGL'da emas, `ModelViewer` dagi CSS radial
gradient: kanvas `alpha: true`, gradient brauzerda tekin chiziladi va markazda
yorug', chetga qarab quyuq bo'lib mahsulotni "o'tqizadi". Yorug'lik —
`RoomEnvironment` (PMREM) muhit xaritasi `environmentIntensity = 0.42` bilan,
ustiga bitta yo'nalish yorug'ligi. **Yorug'lik VA UNING NISHONI kameraga
biriktirilgan**: qo'zg'almas "quyosh"da modelni aylantirib orqa tomonga
o'tilganda butun model kulrangga aylanib qolardi, yig'uvchi esa aynan orqasini
ko'rmoqchi bo'ladi.

> Nishon ham kamerada bo'lishi SHART. three.js yo'nalishni
> `yorug'lik − nishon` dan oladi; nishon biriktirilmasa u dunyo markazida
> qoladi. Sahna millimetrda, ya'ni yorug'likning kameradagi 1.3 mm surilishi
> 2.8–17 metrlik kamera yelkasida yo'qolib, sof "chaqnoq" yoritgich qolardi —
> model yassi ko'rinishining asosiy sababi shu edi (o'qdan 8°, zoomga qarab
> 53° gacha suzardi). Hozir surilish (0.5, 0.9, 2.0) — o'qdan 27°, masofadan
> mustaqil.
Tone mapping — `NeutralToneMapping` (Khronos, mahsulot ko'ruvchilar uchun);
ACES kino uchun qilingan va bu yerda oq plita bilan yog'ochni bir-biriga
yaqinlashtirib, tanlangan detalning oltin rangini xiralashtirardi.

**Soya.** Mahsulot tagida yumshoq gradient dog' — `shadowMap` EMAS: 268 panelli
mahsulotda u har kadrda ikkinchi o'tish talab qilardi. Vazifasi bitta —
mahsulot polda turgandek ko'rinsin. AJRATILGANDA o'chadi, chunki
pastki detallar "pol" ostiga tushib, shaffof disk ularni bo'yab qo'yardi.

**Uchta ko'rinish holati, segmentli tanlov bilan** — «Yopiq / Ochiq /
Ajratilgan». Ular bir-birini ISTISNO qiladi (ochiq eshikli ajratilgan
ko'rinish ma'nosiz), shuning uchun uchta alohida tugma emas: joriy holat doim
ko'rinib turadi va istalganiga bitta bosishda o'tiladi. Ikki holatli
ko'ruvchilar (detalqr) bitta ▶ tugmasi bilan cheklanadi — bizda holat uchta.

* **Ochiq** — fayldagi HAQIQIY harakat (§2.7). Yig'uvchiga eng kerakli
  ma'lumot: eshik qaysi tomonga ochilishi ilgakni qaysi chetga qo'yishni
  aytadi. Ochiladigan detali yo'q modelda bu segment umuman ko'rsatilmaydi —
  hech qachon yonmaydigan o'chiq tugma shovqindan boshqa narsa emas.
* **Ajratilgan** — sun'iy: panel mahsulot markazidan tashqariga suriladi.
  Hech qaysi eshik ortida turmagan ichki detallarni ko'rsatadi.

Ikkala holat BITTA chaqiruvda beriladi (`setPose(ochiq, explode)`): ular bitta
joylashtirishga olib keladi va kamera masofasi ikkalasidan hisoblanadi
(`1 + explode*0.5 + ochiq*0.18`). Masofa eslab qolinmaydi — JORIY masofa
nisbat bilan kengaytiriladi, shuning uchun foydalanuvchining zoom'i har doim
saqlanadi.

**Aylantirish.** Pan **O'CHIRILGAN** (`enablePan = false`): mahsulot doim
markazda turadi, ikki barmoq faqat masshtab. Yoqilganda tasodifiy surish uni
ekran chetiga olib chiqib ketardi va «tiklash»dan boshqa yo'l qolmasdi.
Aylantirish esa CHEKLANMAGAN — tagini ham ko'rish mumkin (taglik qanday
biriktirilgani yig'uvchiga kerak bo'ladi). Masshtab `minDistance`/`maxDistance`
bilan chegaralangan: ichiga tushib ketib ham, nuqtaga aylantirib ham bo'lmaydi.

**Kamera.** Gabarit KAMERA ramkasiga proyeksiyalanadi, sig'dirish sharidan
emas: yassi mahsulot (3.2 × 2.3 × 0.45 m) sharda ekranning yarmini bo'sh
qoldirardi. Telefonda chegaralovchi burchak gorizontal, shuning uchun ikki
burchakning kichigi olinadi. Ekran o'lchami o'zgarganda (telefon burilishi)
foydalanuvchining BURCHAGI saqlanadi va faqat masofa yetarlicha uzaytiriladi —
ilgari bu faqat "kameraga tegilmagan" bo'lsa ishlardi, ya'ni bir marta
aylantirgandan keyin burilish modelni kesib qo'yardi.

**Qidiruvdan tanlash kamerani OLIB BORADI** (`focusOn`): detal ichkarida,
boshqa panellar ortida bo'lishi mumkin va "qayerda?" savoli javobsiz qolardi.
Masofa sig'dirish masofasining 62% i — atrofi ko'rinib tursin. Nishon panelning
JORIY pozasidan olinadi, yopiq holatdan emas: eshiklar ochiq bo'lsa detal yarim
metrgacha siljigan bo'ladi. Fokus — vaqtinchalik chekinish: kartochka
yopilganda nishon ham, masofa ham qayerdan kelingan bo'lsa o'shanga qaytadi.

**Panel va qirralar.** Panel — konturdan ekstruziya (`ExtrudeGeometry`), aylana
kesmalar `Shape.holes` ga, yoy vatar bilan almashtiriladi. Har panelda
`EdgesGeometry` qirra chizig'i: busiz bir xil rangdagi qo'shni panellar bitta
yaxlit blokka aylanib ko'rinadi. Xira holatda qirra chizig'i **yashiriladi** —
aks holda u tanlangan detal ustida "qafas" bo'lib qolardi.

**Kadr faqat KERAK BO'LGANDA chiziladi**: `OrbitControls` ning `change`
hodisasi "kir" bayrog'ini ko'taradi, qolgan holatlarda uni kod o'zi ko'taradi.
Qimirlamagan sahnani qayta chizish telefon batareyasini bekorga yeydi.

> `change` ga OBUNA SHART. G'ildirak va pinch `OrbitControls` ichida qayta
> ishlanadi va u `update()` ni O'ZI chaqiradi; shundan keyin `tick` dagi
> `update()` "o'zgarish yo'q" deb qaytaradi. Obunasiz kamera yaqinlashardi,
> ekran esa eski kadrda qolardi — 20 ta g'ildirak tiqillashidan keyin 0 ta
> draw call, keyin bitta piksel aylantirilganda ko'rinish birdan sakrardi
> (brauzerda o'lchandi). Aylantirishda susayish quyrug'i `update()` ni ~90
> kadr davomida `true` ushlab turgani uchun xato qo'lda sinaganda
> yashiringan edi.

**Xona yuzalari (`Devor`, `Pol`, `KAFEL`) doim XIRA va bosilmaydi**, gabaritga
ham kirmaydi. 460 modelda o'lchandi: 107 tasida (23%) xona bor va u yuzaning
50–100% ini egallaydi — 100 mm qalin berk quti bo'lib mahsulotni butunlay
yopardi, kamera esa oshxonani emas, xonani sig'dirardi. Qoida 140 material
nomidan uchtasini tutadi, yolg'on ijobiysi yo'q (`model.ts: XONA_YUZASI`).

**Qirra chizig'i ikki xil**: quyuq dekorda (`wenge`, `qora` — ishlatilishning
17.5% i) quyuq ko'k chiziqning kontrasti 1.05–1.20 ga tushib ko'rinmay
qolardi, holbuki chiziq aynan "qo'shni panellar bitta blokka aylanib
qolmasin" uchun bor. Material rangining yorqinligi 0.18 dan past bo'lsa OCH
chiziq (`#c9d1dc`) olinadi.

**`near` = 40 mm.** 24 bitli z-bufer aniqligi `near` ga teskari proporsional:
10 mm da 0.4 mm lik surilish sig'dirish masofasida atigi 2.3 birlik bo'lib,
yupqa detallar bir-birining ichiga kirib titrardi. 40 mm dan
yaqinga hech narsa tushmaydi — `minDistance` eng kichik mahsulotda ham 228 mm.

**Bosish FAQAT birinchi barmoqda**: ikkinchi barmoq tushsa kutilayotgan bosish
bekor qilinadi. Busiz pinch paytida ikkinchi barmoqning `pointerup` i o'z
tushgan nuqtasidan 8 px narida bo'lgani uchun "bosish" deb hisoblanib,
tanlangan detalni YO'QOTARDI (telefonda takrorlanib tasdiqlandi).

**Ko'rinish material NOMIDAN chiqariladi** (`model.ts`), indeksdan emas.
Kalit so'zlar 437 buyurtmadagi 162 material nomidan olingan (85 753
ishlatilish), o'ylab topilmagan: `oq` 25.4%, `glyanets` 10.7%, `mokriy` 9.0%,
`dub` 8.7%, `sasna` 8.5%, `qora` 8.5%, `matviy` 7.8%, `kashmir` 5.8%.
Yaltiroqlik ham shundan: `GLYANETS` -> 0.28, `MATVIY`/`SHAGREN` -> 0.85.
Kalitga tushmagan nom BETARAF kulrang oladi (ismining hash'idan barqaror) —
ataylab yog'och ham, bej ham emas: noma'lum material noma'lum bo'lib
ko'rinishi kerak. Ilgari zaxira palitrasida bej bor edi va `zamena material`
(ishlatilishning 3.9% i) kashmir bilan deyarli bir xil chiqib, tumbaning ikki
eshigi qolganidan ajralmay qolgan edi.

Bitta kalitga tushgan ikki material NOZIK tafovut oladi (yorqinlik ±7%,
ohang ±8°, nomdan barqaror): oila saqlanadi — `dub` baribir yog'och bo'lib
ko'rinadi — lekin panellar bir-biridan ajraladi.

Ilgari rang `mats` massividagi O'RINDAN olinardi — ya'ni aynan bir xil
material bir mahsulotda bej, boshqasida kulrang chiqardi va bitta
buyurtmaning ikki mahsulotini solishtirgan usta chalg'irdi.

**Nega Bazis katalogidan emas.** `BAZA 1.FDB` da rang bor (`PARAM_1`), lekin u
teksturali materialda ANDOZA: 90 yozuvdan 89 tasi bir xil `#F6B67F`
(o'lchandi). Haqiqiy rang faqat teksturasizlarida — 64 yozuv, 37 xil rang.
Ya'ni katalog bu qoidaning o'rnini bosmaydi; haqiqiy ko'rinish TEKSTURA
rasmida, va u alohida bosqich.

**Tanlash — bosish, surish emas:** 8 pikseldan ortiq surilgan bosish
aylantirish deb qabul qilinadi. Qidiruv faol bo'lsa faqat TOPILGANLAR
bosiladi: xira panel deyarli ko'rinmaydi, lekin nur uchun to'siq bo'lib
turardi va foydalanuvchi ko'rmagan detalini tanlab olardi.

**Qidiruvda bir xil kodli nusxalar bitta qatorga yig'iladi** (`×2`): chap va
o'ng eshik bir xil detal, ro'yxatda ikki marta chiqib xatodek ko'rinardi.
Qidiruv XOM ko'rinishni ham tekshiradi — faqat normallashtirilgani bilan
`01_0` kabi TUGALLANMAGAN kod hech narsa topmasdi.

## 8. Chegaralar

* **Teshik va freza YO'Q** (1-bosqichdan ataylab chiqarilgan). `Hole` tugunlari
  faylda bor, lekin yig'uvchiga panelning O'RNI kerak, teshigi emas.
* `0x14` kontur segmenti noma'lum — 2285 paneldan 1 tasida uchradi. Bunda
  kontur shu yerda uziladi va ogohlantirish qaytadi.
* **Kromka umuman ko'rsatilmaydi** — na 3D da, na detal kartochkasida.
  Ataylab: u chekda bor va detal sexdan kromkalangan holda keladi.
* `Anim.Shift` va `Duration` o'qilmaydi. `Shift` (odatda panel qalinligiga teng)
  eshikning ochilishdagi qo'shimcha siljishi bo'lsa kerak; usiz ham ochilgan
  eshiklarning korpus bilan kesishuvi 0.0 litr chiqdi, shuning uchun
  qo'shilmadi.
* Ochiq sahifa ishlab chiqarish holatini KO'RSATMAYDI. Ataylab: havolani mijoz
  ham ochadi, unga sexning ichki holati kerak emas.
