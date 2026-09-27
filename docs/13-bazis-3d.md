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
(0.1–20 MB, 4 xil Bazis build'i, 2285 panel) o'lchab aniqlangan va 2026-09-23
auditida **460 faylli korpusda** (41 305 panel) qayta tekshirilgan — o'shanda
8-tur, yoy va kontur halqalaridagi uchta xato topilib tuzatildi (§2.2, §2.5).

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
| 8 | yo'q (belgi) | 0 |
| 9 | `int64` | 8 |
| 10 | `float32` | 4 |
| 11 | `int16` | 2 |

**8-tur — qiymatsiz tugun.** Ilgari u "teglangan qiymat" deb o'qilardi: keyingi
9 bayt `teg, teg2, ichki tur` sanalardi. Aslida ular KEYINGI tugunning sarlavhasi
(kalit, bolalar soni, tur): korpusdagi 5 355 "teg"ning hammasi haqiqiy kalit
nomi chiqdi (`MaterialName -> Thickness`, `CuttingInfo -> CutSections`, ...) va
ichki bolalar soni hammasida 0. O'sha tugun yutilgani uchun otasining bolalari
bittaga kam sanalib, keyingi hamma tugun bir qavat CHUQURROQ osilardi: 64/460
faylda (22 namunadan 4 tasida) panellar 13.7 m gacha noto'g'ri joyga tushardi —
oshxona 14 m balandlikda qiyshiq zinapoya bo'lib chizilardi. To'g'ri o'qilganda
460/460 daraxt fayl oxirida aniq yopiladi (ilgari 386/460).

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
  FurnList            furnitura geometriyasi: F{FastID} -> TriData — §2.9
  Model
    Obj (Type=1005)   guruh (shkaf, sektsiya, "animatsiya", ...)
      Trans           X Y Z Rx Ry Rz Rw  <- OTAGA nisbatan
      Anim            ochilish (eshik/tortma) — 2.7-bo'lim
      Objs
        Obj (...)     ichma-ich, 9 qavatgacha (460 faylda)
        Obj (Type=4002)   PANEL
        Obj (Type=2004)   PROFIL (cho'zilgan jism); 999 egilgan panel — §2.9
        Obj (Type=3001)   FURNITURA: FastID -> FurnList meshi — §2.9
  Undo                tahrirlash tarixi — faylning 13–90% i
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
| `TexDir` | tekstura TOLASI: `2` — kontur Y bo'ylab (27 357 panel), `1` — X bo'ylab (13 668, `TexAngle` = π/2 bilan birga), yo'q (280). Tik fasadlarning 5574/5600 tasida shu o'qish tik tola beradi |

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
| `0x12` | yoy | `cx cy x1 y1 x2 y2` (double) + 1 bayt yo'nalish | 50 |
| `0x14` | aylana | `cx cy r` (double) | 25 |

22 namunaning 2285 panelidagi **9675 segment**: chiziq 9555 (98.8%), yoy 110
(1.1%), aylana 9 + `0x14` 1. 460 faylda: chiziq 170 578, yoy 1478, aylana 131,
`0x14` 8 (7 panelda, hammasi 25 bayt, ichidagi teshik).

**Yoyda MARKAZ birinchi keladi.** 1478 yoyning hammasida birinchi nuqta qolgan
ikkitasidan teng uzoqlikda. Ilgari parser shu markazni ko'pburchak nuqtasi deb
olardi: burchagi yumaloq javon (`3-Garderob` 08_008) 87 944 mm² o'rniga 45 144
mm² — yarmi yo'q bo'lib chizilardi. Yo'nalish bayti `1` — soat miliga TESKARI
(Bazis `Arc2D.ArcDir`); yoy to'liq aylanaga 48 bo'lak zichligida nuqtalarga
bo'linadi.

**Kontur har doim bitta, tartib bilan yozilgan halqa EMAS.** 41 305 panelning
2166 tasida segmentlar aralash yoki teskari yozilgan, 495 tasida bir nechta
halqa bor — tashqi chegara va chiziqdan chizilgan ichki kesma (stoleshnitsadagi
rakovina). Boshlanish nuqtalarini yozilish tartibida ulash o'z-o'zini kesadigan
"kapalak" shakl berardi. Shuning uchun segmentlar UCHLARI bo'yicha (0.05 mm)
halqalarga ulanadi, kerak bo'lsa teskari o'giriladi; eng katta halqa — panel
chegarasi (`o`), uning ichidagilari — kesma (`h`). Chegaradan TASHQARIDAGI halqa
(korpusda bitta: ikki bo'lakli panel) chizilmaydi va "kontur to'liq o'qilmadi"
ogohlantirishi bilan bildiriladi. Segment soni NaN, cheksiz yoki 1000 km dan
katta bo'lsa ham shunday (noma'lum segment kabi kontur shu yerda uziladi):
ilgari u to'rning `math.floor` ida ValueError berib, yuklashni o'zbekcha 422
o'rniga 500 ga aylantirardi. 460 haqiqiy faylda bunday qiymat yo'q — bu qalqon,
xuddi `Anim` dagi kabi. Natija: 460 faylda o'z-o'zini kesadigan
chegara 0 ta, three.js triangulyatsiyasi 41 305 panelning hammasida "chegara −
kesmalar" maydonini beradi. Ilgari 843 panelda (71 tasi namunalarda)
triangulyatsiya konturning o'z maydonidan 2% dan ko'p farq qilardi — o'z-o'zini
kesishning belgisi — va 15 panel umuman shaklsiz qolardi.

Aylana odatda paneldagi KESMA (rozetka, kabel teshigi) — chegara ichidagisi `c`
ga tushadi. Konturda chiziq va yoy UMUMAN bo'lmasa, eng katta aylana panelning
O'ZI (yumaloq javon): u 48 nuqtali ko'pburchakka aylantiriladi, qolgan aylanalar
uning teshiklari, panel `is_round` bilan belgilanadi (`Butt.Elem` raqamlari endi
nuqtalarga mos kelmaydi). 460 faylda bunday panel 31 ta, namunalarda 1 ta.

### 2.6 Joylashuv

Joylashuv **iyerarxik**: panelning dunyodagi o'rni ildizdan barggacha
`Trans` larni ko'paytirib chiqariladi (460 faylda 9 qavatgacha). Bazisning
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
| `Shift` | ilgakda o'qning yerli `+Z` bo'yicha siljishi, mm (pastda o'lchov); surmada deyarli doim 0 |
| `Duration` | o'qilmaydi — sahifa harakatni o'z tezligida (460 ms) o'ynatadi |

22 namunada: **1162** ishchi `Anim` (o'qi ham, harakati ham nol emas; o'qi bor,
lekin burchagi 0 bo'lgan 96 ilgak — gaz lift — hisobga olinmagan), shundan ilgak 951, surma
211; ular jami **570 panelni** harakatlantiradi. 22 fayldan 20 tasida ochiladigan
detal bor, 2 tasida (oddiy javon) yo'q.

**460 faylda tekshirildi:** `AnimType` faqat `1`, `2` yoki yo'q (25 971 tugun),
chekli bo'lmagan `Limit` YO'Q, `Limit` ning eng ko'p uchraydigani `-90` (10 587)
va `90` (4722) — ya'ni manfiy burchak odatiy hol. Shunga qaramay parser har
sonni chekli ekaniga tekshiradi: buzuq faylda `NaN` butun modelni ko'rinmas
qilardi, `inf` esa 500 chiqarardi (modulda boshqa hamma nosozlik o'zbekcha 422).

**`Shift` — o'qning siljishi, O'LCHANGAN.** Bazis qo'llanmasi: "rotation axis
shift along the axis that is perpendicular to rotation axis" — qaysi
perpendikulyar ekani yozilmagan. 22 namunaning to'rtburchak eshiklarida
ochilganda boshqa panelga 3 mm dan chuqur kiradigan eshiklar sanaldi (yopiq
holatda kirmagan bo'lsa): `Shift` hisobga olinmasa 20 ta haqiqiy detalga va 4
ta xona yuzasiga; o'q yerli **+Z** ga `Shift` qadar surilsa — **0**; −Z ga
surilsa 90. Ya'ni `Shift` o'qni panel qalinligi tomonga suradi (odatda 16 mm).
Surmada (`AnimType=2`) `Shift` 6474 tugunning deyarli hammasida 0, siljish esa
o'q kesmasining o'zi (383, 252, 338 mm ...).

**O'q koordinatalari animatsiyali tugunning ICHKI fazosida.** O'lchab
aniqlangan: namunadagi ilgak o'qi `x = -310.5`, eshik konturi esa
`x = -309..17` — ya'ni o'q panelning chap chetiga tegib turibdi. Otasining
fazosida bo'lganida u 300 mm narida qolardi.

**Yo'nalish o'qning YO'NALISHIDAN** (o'ng qo'l qoidasi, `+Limit`): bir
shkafning chap va o'ng eshigida o'q qarama-qarshi tomonga yozilgan. Belgi
o'lchov bilan tasdiqlangan — yuqoridagi sanoqda to'g'ri belgida 0 ta eshik,
teskarisida 47 tasi (24 tasi haqiqiy detalga) boshqa panel ichiga kiradi.

Parser har panelning IKKI holatini hisoblaydi — yopiq va ochiq — va brauzerga
iyerarxiya emas, shu ikkitasi beriladi. Oraliq kadrlarni brauzer o'zi
hisoblaydi: eshik ikki holatdan ANIQ tiklangan o'q atrofida buriladi
(`frontend/src/components/Bazis/ilgak.ts`), tortma to'g'ri chiziq bo'ylab
suriladi. Ilgari eshik ham to'g'ri chiziq bo'ylab surilib, burilishi alohida
slerp qilinardi — uchlari to'g'ri, lekin harakat o'rtasida eshik ilgagidan
85 mm (median) va 223 mm gacha ko'chib, korpus ichidan o'tardi. Tiklangan o'q
backenddagi haqiqiy o'qdan 314 eshikda eng ko'pi 0.042 mm uzoqda.

### 2.8 Nimani o'qimaymiz

Ochilgan model **256 MB** bilan cheklangan (`_MAX_OCHILGAN`): zlib nolli
buferni 1000:1 siqadi, ya'ni chegarasiz 40 MB lik fayl 40 GB ga ochilib butun
backendni xotirasiz qoldirishi mumkin edi (bajarib tekshirilgan). Eng katta
haqiqiy namuna 32 MB ga ochiladi.

`Undo` — tahrirlash tarixi, fayl hajmining 13–90% i, `Document` ning bevosita
bolasi. Parser unga **kirmaydi**: o'qishdan to'xtaydi, chunki undan hech narsa
kerak emas va panellar undan OLDIN keladi. (Ilgari "6 namunada `Undo` o'qilmaydi"
deyilardi — bu 8-tur xatosining oqibati edi, u tuzatilgach `Undo` 460/460 faylda
toza o'qiladi.)

**Nima chizilMAYDI** (§2.9 dagi jadvaldan tashqari hamma tur): chizma
yordamchilari — yordamchi kontur va 3D matn (`8100`),
tutashuv chizig'i va gabarit ramkasi (`1001`), teshik (`3000`), chiziq/aylana
(`6000`, `8001`, `8002`); traektoriya bo'ylab jism (`2001`, 7 ta: duxovka
tutqichi, kir yuvish mashinasi halqasi, 2 karniz — profil o'qining ishorasi
faqat karnizlarda tasdiqlandi).

**O'lcham (`9000`, `Размер`) — geometriya emas, o'lcham qatlami** (§4 `d`, §7).
Kalitlari: `Trans` (panel kabi otaga nisbatan), `Size`, `Length`, `Value`,
`TextOffset`, `SignOffset`, `TextSize`, `Color`, `Params`. Uchlari o'z fazosida
(0,0,0) va (Size,0,0) — 22 namunada 254 uchdan 226 tasi panel yuzasidan 1 mm
ichida, `Value` 127/127 da `Size` ga teng. Chiziq +Y bo'ylab `Length` ga
surilgan: 460 faylda teng bo'lmagan 1905 holatning 1757 tasida (92%) aynan shu
tomon panellardan uzoqroq, ya'ni mahsulotdan tashqarida. `Vis` (qiymatsiz kalit)
o'zida yoki ajdodida bo'lsa — Bazisda YASHIRILGAN, o'qilmaydi (namunalarda 127
dan 3 tasi). `TextOffset`/`TextSize`/`Color` o'qilmaydi: ular Bazisning qotgan
kamerasi uchun.

### 2.9 Jismlar va furnitura

Muzlatkich, vityajka, mikroto'lqinli pech ilgari ko'rinmasdi: parser faqat
`4002` ni o'qirdi, ular esa boshqa turlardan yasalgan (460 faylda o'lchandi —
muzlatkichlarning 58/58 tasi `2004`, mikroto'lqinlilarning 16/16 tasi `999` +
`2004`, 43 vityajka `3001`). Endi:

| Tur | Nima | 460 faylda | Qanday chiziladi |
|---|---|---|---|
| `4002` | panel | 41 247 | kontur + `Thick` |
| `2004` | profil — cho'zilgan jism (muzlatkich korpusi, rels, truba, GOLA) | 4919 obyekt -> 6138 bo'lak | panel kabi, qalinligi `Thickness` |
| `999` | egilgan panel (rakovina kosasi, alyumin rels tutqich, SVCh yuzasi) | 172 -> 176 | panel kabi |
| `2002` | aylanma jism (Reginox rakovina kosasi) | 3 | mesh, kontur lokal Z atrofida 360° (256 nuqta va faylda 50 000 uchburchak chegarasi) |
| `3001` | furnitura (tutqich, oyoq, ilgak, vityajka, varochniy panel) | 51 810 meshli | `FurnList` meshi, FastID bo'yicha |
| `1004` | `Вычитание тел` (ayirish) | 85 | faqat BIRINCHI jism |
| `10000` | import qilingan mesh (SketchUp va h.k.) | 276, 5 faylda | furnitura kabi; `TriData` tugunning o'zida |

**Import qilingan mesh (10000)** — `TriData` furnitura blobi bilan bir xil
formatda, lekin `FurnList` da emas, tugunning O'ZIDA (276/276 o'qiladi). Blob
bo'yicha bir marta saqlanadi. `2-Oshxona` (ishlab chiqarish namunasi) da tortma
relslari va qulflari (`TANDEM с интегр. BLUMOTION`, 44 ta) — ilgari ko'rinmasdi.
Lekin `SP KUBO STANDART` (173) va `2 qavcatlik spalniy` (30) da import —
mahsulotning SketchUp NUSXASI: o'lchami aynan bir xil (817 x 850 x 2056 ga
812 x 850 x 2056), X bo'ylab 1113 / 2029 mm chetda; chizilsa yonida ikkinchi
mebel paydo bo'lardi. Qoida (`parser.py: _import_sarala`): fayldagi importlarning
BIRORTASI ham mahsulot qutisi (panellar, 50 mm zaxira) ichida bo'lmasa — hammasi
tashlanadi (meshlari ham), aks holda hammasi chiziladi (`Bolalar spalniysi` —
karavot, `BITAVOY MAGAZIN` — do'kon devorlari).

**Profil va egilgan panel — panelning o'zi.** Kontur o'z XY tekisligida (xuddi
shu blob formati), lokal Z bo'ylab `Thickness` ga cho'ziladi. Farqlari:

* `Thickness` ISHORALI — z `0..Thickness` (5091 dan 770 tasi manfiy). Brauzer
  musbat qalinlik kutadi, shuning uchun manfiyda boshlanish `R·(0,0,Th)` ga
  suriladi. Ishorani tashlab yuborish 770 dan 335 tasini mahsulotdan
  tashqariga chiqarardi. Tekshiruv: muzlatkich `Xolod 183 x 91 x 69` —
  **910 x 1830 x 672.5 mm**, `BAYFU 400 mm` relsi aynan 400 mm.
* Kontur bir nechta ALOHIDA bo'lak bo'lishi mumkin (ikki tayoqli profil,
  14 ta Ø5 shtift) — har biri o'z panelida (`_orollar`). Panel esa bitta bo'lak.
  Qoida juft-toq: halqa eng ichki o'rab turgan halqaga qaraydi — u bo'lak
  chegarasi bo'lsa kesma, kesma bo'lsa YANGI bo'lak. Ilgari har ichki halqa
  tashqi bo'lakning kesmasi bo'lardi: `ALLU` panjarasida (ramka ochig'ida 16
  reyka, 4 disk) kesma ichida kesma chiqib, three.js 56 profilda to'g'ri
  yuzadan 3.4-4 barobar ko'p to'ldirardi — panjara yaxlit plita bo'lib
  ko'rinardi. Panelda kesma ichidagi bo'lak (fasad yozuvidagi harf ko'zi,
  2 panel) chizilmaydi, ogohlantirishsiz.
* `ClipPlanes` — `[x, y, z, d]` tekisliklar (163 profil, normallar
  `(±0.7071, 0, ±0.7071)`), `n·p + d >= 0` qoladi: ramkaning 45° li burchagi.
  Brauzer uchni Z bo'ylab tekislikka suradi (`scene.ts: kes`) — 308/308 uch
  qo'shnisi bilan aynan tutashadi; tekisliksiz 0/308.
* Kodli profil (1163 ta, `05_008 L profil`) oddiy detal: qidiruvda topiladi.
  Kartochkadagi «N detal» esa panellar va KODLI jismlar (`part_count`) — kodsiz
  profil (muzlatkich korpusi) detal emas.

**Furnitura meshi — `FurnList/F{FastID}/TriData`** (4193 blob baytma-bayt
o'qildi, dumi 0 bayt). Tuzilishi: `u32` qismlar; har qism: `u32 n` + UTF-16
material nomi (`qora rang`, `GTV Nikel plated`, `Boyard Нержавеющая сталь`),
16 `f64` — TEKSTURA matritsasi (uchlarga QO'LLANMAYDI: xom uchlar `MinX..MaxZ`
ichida 4193/4193, qo'llansa tutqich ezilardi), `u8`, `u32` uchburchaklar,
har biri 112 bayt: 3 uch, 3 uch normali, yuza normali, UV, qirra bayroqlari.
Indeks bufer yo'q — parser bir xil uchlarni (uch VA normal) birlashtiradi.
Mesh FastID bo'yicha BIR MARTA saqlanadi, joylari alohida (bitta oshxonada
bir xil ilgak 59 marta).

Joyi — panellarniki bilan bir xil zanjir (`dunyo = pos + R·v`); DatumMode,
ParamOffset va qo'shimcha oyna kerak EMAS. Tekshiruv: 4007/4011 tutqich eshik
yuzasida va tashqariga qaragan, 8787/8787 ilgak kosasi eshik ichida,
2952/2952 oyoq polda, 43/43 vityajka stoleshnitsadan 680-810 mm yuqorida.
Eshikdagi tutqich eshik bilan birga ochiladi — birligi (`g`) eshikniki.

**Ilgak kosasi eshikka QATTIQ bog'lanadi** (`parser.py: _eshikka_bogla`).
Bazis kosaga eshikdan ALOHIDA `Anim` yozadi — eshik yig'masida emas, yonidagi
ilgak yig'masida (`Petlya ROBUST` > `Chashka`, `Limit = -90`, `Shift = 16`).
Burilishi eshiknikiga aynan teng, lekin `Shift` ning yerli +Z qoidasi (eshiklarda
o'lchangan, §2.7) kosa fazosida teskari tushadi: ochilganda kosa eshikdan
~45 mm chetda qolardi, birligi ham boshqa edi — kartochkadan bitta eshik
ochilsa kosalari joyida turardi. Endi yopiq holatda harakatlanuvchi panelga
tegib turgan (1 mm) va u bilan AYNAN bir xil BURILADIGAN furnitura panelning
birligini va qattiq harakatini oladi: 8871 kosa, 2007 `Фурнитура#`, 311
`Фиксатор на фасад`. Tuzatishdan keyin eshik birligidagi kosalarning
hammasi eshik bilan qattiq harakatlanadi (og'ish 0). Burilmaydigan harakat tegmaydi (`DONGA` relsi tortma bilan
teleskop bo'lib suriladi), gaz lift shtoki eshikka tegmaydi — ular o'z
`Anim` ida qoladi.
Mahkamlagichlarda (`Mix 2.5`, shurup, evrovint — 161 649 obyekt) mesh yo'q,
ular chizilmaydi ham. Obyektdagi `Color` — mahkamlagich turining belgisi
(evrovint `00FF00FF`), rang emas; rang qism NOMIDAN.

**`Вычитание тел` (1004): birinchi jismdan ikkinchisi ayiriladi** (Bazis
qo'llanmasi: "The second object will be subtracted from the first one").
Ikkinchisi — kesuvchi asbob, detal emas: ilgari u 58 faylda duxovka tagida qora
320 x 115 x 50 blok bo'lib chizilardi. Endi faqat birinchi jism chiziladi —
ayirishsiz (CSG yo'q), lekin u jismning ichki kemtigi, tashqi shakli emas.

**Televizor** — `TV-SAMSUNG` fragmenti: qora korpus va 2 mm `экран` paneli.
Ular ilgari ham chizilardi, lekin `экран` shisha qatorida 34% shaffof och-ko'k
parda edi — televizor ko'rinmasdi. Endi ekran deyarli qora va yaltiroq (§7).

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

**Kod mos, lekin fayl BOSHQA buyurtmaniki.** Bazis raqamlari mijozlar orasida
takrorlanadi: `2083 Ilyos aka` ham, `2083 Anvar` ham `208301` kodli (namuna
`01 tv zona.b3d` va `2083 Anvar.project`: 36 detal kodi mos, o'lchami 0/36).
Faqat kod bo'yicha bog'lansa boshqa mijozning TV zonasi bu buyurtmaning kupesi
deb ko'rsatilardi. Shuning uchun mahsulot NOMI ham solishtiriladi (katta-kichik
harf va bo'shliqlar hisobga olinmaydi): `.project` dagi nom ham, `.b3d` dagi
nom ham Bazisning `Article.Name` idan (GibLab eksport skripti,
`GibLabExport.js: getModelName()`), ya'ni to'g'ri faylda ular mos keladi.

**Nom farq qilsa — 409, hech narsa yozilmaydi.** Ilgari fayl ogohlantirish va
`matched=false` bilan baribir saqlanardi, ammo `matched` faqat bayroq edi:
model shu mahsulot kodi bilan ochiq sahifada chiqib, chekdagi Detal ID uning
panellarini AYNAN topardi — usta boshqa o'lchamdagi detalni ko'rardi, texnolog
esa «detallar bog'lanmadi» deb o'qirdi. Endi server ikkala nomni aytib 409
qaytaradi; texnolog panelida (`BazisPanel`) bir nechta fayldan nomi farq
qilganlari yig'ilib BITTA dialogda so'raladi, «Baribir yuklash» —
`tasdiq=true` bilan qayta yuborish (nom rostdan o'zgargan bo'lishi mumkin).
Tasdiqlangan model bog'lanadi (`matched=true`) va ogohlantirishda «texnolog
tasdiqlab yukladi» qoladi.

---

## 4. Oqim

```
Texnolog                     MES                              Usta / mijoz
   |                          |                                    |
   |-- .b3d yuklaydi -------->|                                    |
   |                          | read_b3d() -> ParsedBazis          |
   |                          | Product qidiradi (Code + nom, §3)  |
   |                          | diskka: .b3d + .json + .png        |
   |<-- kod, detal soni ------|                                    |
   |-- «Havolani ochish» ---->|                                    |
   |                          | order.share_token = uuid4          |
   |<-- token ----------------|                                    |
   |-- havola / QR ------------------------------------------------>|
   |                          |<-- GET /public/3d/{token} ----------|
   |                          |--- buyurtma raqami + mahsulotlar -->|
   |                          |<-- .../{code}/model ----------------|
   |                          |--- model JSON (0.1 KB–1.7 MB) ----->|
```

**Model yuklashda BIR MARTA yasaladi.** Ochiq so'rovda parser ishga
tushmaydi: 460 faylda 1.7 s gacha CPU ketadi (median 0.12 s), autentifikatsiyasiz bir necha
so'rov butun sexni sekinlashtirardi. Yuklashning o'zida ham parser, JSON va
eskiz (100–225 ms) oqimda (`run_in_threadpool`) bajariladi — event loop'da
bo'lsa TABLO va terminallar shu vaqtga muzlardi.

Diskda (`upload_root`):

```
bazis/{order_id}/{product_code}.b3d     manba (qayta ishlash uchun saqlanadi)
bazis/{order_id}/{product_code}.json    brauzer modeli
bazis/{order_id}/{product_code}.png     kartochka eskizi (qayta ishlangan)
```

Mahsulot kodi fayl nomiga aylanadi, shuning uchun `[^A-Za-z0-9_-]` tozalanadi
va 40 belgiga qisqartiriladi (yo'l bo'ylab chiqib ketishga qarshi). Bir xil
kodli fayl qayta yuklansa eskisining o'rnini oladi. Yangi faylda `Thumbnail`
bo'lmasa eski `.png` o'chiriladi (eskiz endpointi 404 beradi) — aks holda
yangi yozuv oldingi faylning eskizini ko'rsatardi.

### Model JSON

Kalitlar qisqa — 268 panelli mahsulotda uzun nomlar JSON'ni sezilarli
kattalashtiradi, sahifa esa telefonda ochiladi.

```json
{"v":2,"code":"208301","name":"01 TV ZONA","mats":["LDSP ...","1-19 kashmir"],
 "panels":[{"id":"01_023","n":"Fasad","m":0,"t":16,"s":[326,731],
            "p":[639.5,100,430],"q":[0,0,0,1],
            "o":[[17,0],[-309,0],[-309,731],[17,731]],
            "h":[[[40,60],[200,60],[200,160],[40,160]]],
            "po":[654,100,457.5],"qo":[0,0.70711,0,0.70711],
            "c":[[160,80,40]]}]}
```

`o` — tashqi chegara, `h` — chiziq/yoydan chizilgan ichki kesmalar (41 305
paneldan 494 tasida), `c` — aylana kesmalar `[cx, cy, r]` (§2.5). `po`/`qo` —
OCHILGAN holatdagi joylashuv va burilish; faqat harakatlanadigan panelda bo'ladi
(2285 dan 570 tasi), qolganida yozilmaydi. `g` — o'sha panelning HARAKAT
BIRLIGI (pastda, §7). `cp` — profil uchini kesuvchi tekisliklar, `r: 1` —
tekstura tolasi kontur X bo'ylab (§2.9). `m` — `mats` massivining indeksi
(materiallar takrorlanadi, indeks bilan JSON ikki barobar kichik).

`meshes` — furnitura geometriyasi, har biri qismlar ro'yxati
`[material, uchlar, normallar, uchburchak indekslari]` (uch 0.1 mm, normal 0.001
aniqlikda); `furn` — nusxalar `{k: mesh indeksi, n, p, q, po?, qo?, g?}`.
`d` (ixtiyoriy) — bazischining o'lchamlari `{v, a, b, o, g?}`: qiymat, o'lchangan
ikki nuqta, o'lcham chizig'ining surilishi (vektor) va harakat birligi (eshik
ichidagi o'lcham). Namunalarda faylga 154 B – 2.5 KB qo'shadi. Versiya
OSHIRILMADI: `d` siz eski model ham to'g'ri chiziladi, oshirilsa frontend
saqlangan hamma modelni «eskirgan» deb rad etardi (`3d.$token.tsx` qat'iy tenglik).
Parser o'zgargach saqlangan modellarni qayta yasash:
`python -m app.commands.rebuild_bazis_models` (docs/04 §5).

22 namunada o'lchangan hajm: median **92 KB**, eng kattasi **1.09 MB**, gzip'dan
keyin **0.5–170 KB** (Caddy `encode gzip` bilan beradi); 460 faylda eng kattasi
1.66 MB, gzip 263 KB. Katta modellarning
asosiy og'irligi — furnitura meshi: `SU02 Решетка для тарелок` (idish quritgich
panjara) bitta o'zi 12.5 ming uchburchak. Yuklash 0.75 s gacha.

**`v` — model versiyasi.** JSON yuklashda bir marta yoziladi, ya'ni shakli
o'zgarsa eski fayl diskda qoladi. Frontend (`model.ts: MODEL_VERSIYA`) boshqa
versiyani CHIZMAYDI va "Bu model eskirgan. Texnolog uni MESga qayta yuklasin"
deydi. `2` — `h`, `g`, `cp`, `r`, `meshes`, `furn` qo'shildi, kontur uchlari
bo'yicha ulanadi, yoy to'g'ri o'qiladi.

**Buzuq son JSON'ga tushmaydi.** `json.dumps` sukut bo'yicha `NaN` yozadi,
brauzerning `JSON.parse` esa uni rad etadi — yuklash "muvaffaqiyatli" bo'lib,
sahifa modelni ocholmay qolardi. `dump_model` `allow_nan=False` bilan yozadi,
yuklash esa o'zbekcha 422 qaytaradi.

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
| Ikkalasi `/3d/{token}` SAHIFASIDA ham (`frontend/nginx/index.conf`, `location ^~ /3d/`) | manzilning o'zida token bor; ilgari sarlavhalar faqat API javoblarida edi |
| `Cache-Control: no-cache` (API javoblari va sahifa) | model qayta yuklanganda token va manzil O'ZGARMAYDI, fayl o'sha joyda yangilanadi — brauzer eskisini qayta ishlatmasin, har safar ETag bo'yicha so'rasin |
| IP bo'yicha cheklov (60 / 5 daqiqa, faqat XATO urinish) | skanerlash shovqinini to'xtatadi. Hisob kaliti marshrut SHABLONI bo'yicha (`/public/3d/{token}`), real yo'l bo'yicha emas — aks holda har taxmin qilingan token o'z kalitini olib, cheklov umuman ishlamasdi (1000 urinish -> 1000 kalit, har birida 1). Uchala ochiq marshrutning har biri o'z 60 tasiga ega (jami 180); token 122 bitli, shuning uchun bu yetarli |
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

three.js faqat `/3d/$token` chunk'ida (`autoCodeSplitting`) — 644 KB, gzip 167 KB;
asosiy bundle'ga tegmaydi.

### 7.1 Mahsulot ro'yxati

Birinchi ekran — kartochkalar to'ri; bitta mahsulot bo'lsa u o'tkazib
yuboriladi va model darhol ochiladi. Kartochkada **eskiz, nom, mahsulot kodi va
detal soni** bor. Kod kerak: bitta buyurtmada bir xil nomli ikki mahsulot
bo'ladi (`01 Kuxniya` ikkita), ularni faqat kod ajratadi.

Nom `OrderFile.meta.product_name` dan: model MES mahsulotiga bog'lansa (kod va
nom mos, §3) — `Product.name`, aks holda `.b3d` sarlavhasidagi `Name` (ya'ni
texnolog Bazisda yozgani). Shu sababli boshqa buyurtmaning fayli bu buyurtma
mahsulotining nomi ostida ko'rinmaydi.

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
`RoomEnvironment` (PMREM) muhit xaritasi `environmentIntensity = 0.22` bilan,
ustiga ikkita yo'nalish yorug'ligi: asosiy (1.6, surilish `0.5, 0.9, 2.0`) va
to'ldiruvchi (0.7, `-0.6, -0.4, 1.2` — pastdan qaraganda ham soya tomoni qop-qora
bo'lmasin), ekspozitsiya 0.86. **Yorug'lik VA UNING NISHONI kameraga
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

**To'rtta ko'rinish holati, segmentli tanlov bilan** — «Yopiq / Ochiq /
Ichki / Ajratilgan». Ular bir-birini ISTISNO qiladi (ochiq eshikli ajratilgan
ko'rinish ma'nosiz), shuning uchun alohida tugmalar emas: joriy holat doim
ko'rinib turadi va istalganiga bitta bosishda o'tiladi. Ikki holatli
ko'ruvchilar (detalqr) bitta ▶ tugmasi bilan cheklanadi — bizda holat to'rtta.
Tor ekranda faqat FAOL holat nomi bilan, qolganlari ikonka (nomi `title` va
ekran o'quvchi uchun bor): to'rtta nom 360 px da tiklash tugmasi bilan bitta
qatorga sig'masdi. 356 px da o'lchandi — gorizontal aylantirish yo'q.

* **Ochiq** — fayldagi HAQIQIY harakat (§2.7). Yig'uvchiga eng kerakli
  ma'lumot: eshik qaysi tomonga ochilishi ilgakni qaysi chetga qo'yishni
  aytadi. Ochiladigan detali yo'q modelda bu segment umuman ko'rsatilmaydi —
  hech qachon yonmaydigan o'chiq tugma shovqindan boshqa narsa emas.
* **Ichki** — eshik va tortmalar yopiq, fasadlar esa faqat KONTURI bilan:
  usta korpus ichini (javon, tortma qutisi, relslar, ilgak plitasi) fasad
  qayerda turishi bilan BIRGA ko'radi. Fasadi yo'q modelda segment
  ko'rsatilmaydi. Batafsil — pastda.
* **Ajratilgan** — sun'iy: panel mahsulot markazidan tashqariga suriladi.
  Hech qaysi eshik ortida turmagan ichki detallarni ko'rsatadi.

Ikkala holat BITTA chaqiruvda beriladi (`setPose(ochiqBirliklar, explode)`):
ular bitta joylashtirishga olib keladi va kamera masofasi ikkalasidan
hisoblanadi (`1 + explode*0.5 + o*0.18`, `o` — harakatlanadigan panellarning
o'rtacha ochilganligi). Masofa eslab qolinmaydi — JORIY masofa nisbat bilan
kengaytiriladi, shuning uchun foydalanuvchining zoom'i har doim saqlanadi.
Harakatni sahnaning o'zi o'ynatadi (React har kadr holat yangilamaydi).

**«Ochiq» — KASKAD, birma-bir emas.** Holat tugmasi natijani darhol berishi
kerak, lekin 460 faylda ochiladigan birlik mahsulotda o'rtacha 11 ta (90% i
28 tagacha, eng ko'pi 104): hammasi bir vaqtda qimirlasa ko'z qaysi eshik
qayoqqa ochilganini ilg'amaydi, birma-bir ochish (har biri 460 ms) esa o'rtacha
5.1 s, eng uzuni 48 s bo'lardi — tugma filmga aylanardi. Shuning uchun
birliklar ekrandagi joyiga qarab TO'LQIN bo'lib boshlanadi: chapdan o'ngga,
tepadan pastga (`0.75·x + 0.25·y`), yopilishda teskari. Birinchi va oxirgisi
orasi 300 ms, birliklar SONIGA bog'liq emas — har qanday modelda hammasi
~0.76 s da ochiladi. Har birlik o'zi 460 ms, easeOutCubic. Holat o'rtada
almashsa har panel JORIY joyidan davom etadi. `prefers-reduced-motion` da
harakat yo'q — holat darhol almashadi (Chrome'da tekshirildi).

**Ichki mexanizm — ikkinchi bosqichda.** Paneli yo'q birlik (pantograf, shim
ilgichi, tortma savat — furnitura o'z `Anim` i bilan) eshiklar OCHILIB BO'LGACH
chiqadi, yopilishda esa BIRINCHI qaytadi. Bir vaqtda yursa u hali ochilayotgan
eshik ichidan o'tardi: `3-Garderob` da shim ilgichi, uning yo'naltiruvchisi va
pantograf richagi shisha eshik profilini oraliq kadrlarda kesib o'tardi (tugal
ochiq holatda kesishuv yo'q — ikkalasi ham skript bilan o'lchandi). Haqiqiy
`scene.ts` ni soxta renderer bilan yurgizib o'lchandi: ochishda eshiklar
10-260 ms da boshlanib 710 ms gacha tugaydi, mexanizmlar 920 ms dan; yopishda
mexanizmlar 610 ms gacha qaytadi, eshiklar 810 ms dan. Mexanizmi bor modelda
ochilish ~1.45 s.

**Harakat birligi (`g`).** Kaskad PANEL bo'yicha bo'lsa tortma harakat paytida
bo'laklarga ajralardi, shuning uchun birlik — bitta eshik yoki tortmaning
BARCHA panellari. Uni faqat parser biladi (`_panellar`): birlik — eng tashqi
harakatlanuvchi ajdod (ichma-ich animatsiyada, 460 faylda 17 ta, ichkisi
tashqisi bilan birga); bitta yig'mada (eng yaqin `Obj` ota) AYNAN bir xil
harakatlanadigan aka-ukalar ham bitta birlik — Bazis tortmaning qutisi
(`yashik`, 5 panel) va fasadiga alohida `Anim` yozadi. O'lchov: 460 faylda
790 juft birlashdi, hammasi SURMA; burilishda birorta ham birlashmadi, ya'ni
ikki eshikli shkafning eshiklari alohida qoladi. Jami 5 357 birlik, har
birining barcha panellari bir xil harakatlanadi (farq ≤ 0.01 mm). Brauzer
buni harakatdan taxmin qila olmasdi: birliklarning 37% i boshqasi bilan AYNAN
bir xil harakatlanadi (bir ilgak chizig'idagi ustma-ust eshiklar, bir
ustundagi tortmalar).

**Bitta eshikni ochish — kartochkadan.** Ustaning savoli odatda bitta eshik
haqida ("bu qayoqqa ochiladi, ilgak qaysi chetga?"): harakatlanadigan detal
tanlansa kartochkada «Ochish»/«Yopish» chiqadi va FAQAT o'sha birlik (nusxalari
bilan — chap va o'ng eshik bir xil kodli bo'lsa ikkalasi) kechikishsiz
ochiladi. Bu holatga NISBATAN almashtirish: «Yopiq» da ochilgan, «Ochiq» da
yopilgan eshiklar (`ModelViewer: almashgan`); holat almashsa tozalanadi.

**«Ichki» — fasad o'chirilmaydi, KONTURGA aylanadi.** DetalQR fasadni
butunlay yashiradi: ichi ko'rinadi, lekin qaysi eshik qaysi bo'shliqni
yopishi yo'qoladi — ilgak va tutqich joyi aynan shundan. Bizda fasad yuzasi
5% qoplamada (`kontur` holati, `depthWrite` siz), qirrasi alohida quyuq
chiziq (`konturMat`, 0.5 — dekor rangidan qat'i nazar: yuzasi deyarli
shaffof, chiziq och fonda ham ko'rinishi kerak). Fasad furniturasi (tutqich,
ilgak, qulf) butunlay YASHIRIN: qirra chizig'i yo'q, 5% dagi qora tutqich esa
kulrang dog' bo'lib qolardi (egasi ko'rib aytdi).
Kontur BOSILMAYDI va o'lchamni TO'SMAYDI: fasad ortidagi javon bosilsa javon
tanlanadi. Haqiqiy `scene.ts` ni soxta renderer bilan yurgizib o'lchandi —
tumba, kupe va oshxonada fasad markazidagi 48 bosishdan «Yopiq» da 47 tasi
fasadga, «Ichki» da 48 tasi ham ichki detalga tushdi; oshxonada ko'rinadigan
bazischi o'lchami 3 dan 5 taga chiqdi; Chrome'da ham tekshirildi. Qidiruv ishlaydi: fasadning O'ZI
topilsa yoki tanlansa — o'z rangida va bosiladi. Boshqa detal tanlanganda
fasad xira (0.16) emas, kontur qoladi — xira fasad ichkaridagi tanlangan
detalni pardalardi — qirrasi esa fonniki kabi juda xira (pastda, «Tanlanganda»).

Fasad NOMDAN emas, HARAKATDAN aniqlanadi (`model.ts: fasadlar`) — bazischi
nomni erkin yozadi (`Fasad`, `1-61 Фасад`, `Профиль`):

* burilib ochiladigan birlik — butunlay: fasad, shisha, ramka profili,
  tutqich, ilgak kosasi;
* surma (kupe) eshik — butunlay: birlikdagi eng katta varaq TIK turadi,
  harakat bo'ylab yotadi va harakatga qaragan varaqdan 5 barobardan katta
  (tortmaning tubi old paneldan 2-4 barobar katta, lekin yotiq);
* tortma — faqat OLD paneli (harakatga tik varaqlarning eng oldingisi) va
  uning markaz tekisligidan OLDINDA turgan furnitura: tutqich +7 mm, ichkaridagi
  `KARGO` −9 mm (u qoladi — usta uni o'rnatadi);
* harakatsiz, nomida «fasad/фасад» — to'ldiruvchi va burchak fasadlari;
* konturga aylangan varaqqa tegib turgan MAYDA furnitura (150 mm gacha): ilgak
  tanasi va plankasi, qulf, ekssentrik. Ilgak tanasi harakat birligiga kirmaydi
  — u yon devorda qoladi (§8), lekin ustaga ham, mijozga ham u fasadniki. 22
  namunada fasadga tegadigan 1268 furnituradan 571 tasi ko'rinib qolardi (525 i
  ilgak); endi 45 tasi — yo'naltiruvchi (400-450 mm), vityajka va `KARGO`, ular
  ichki mexanizm.

«Varaq» — qalinligi eni va bo'yidan kichik panel: profil ham panel bo'lib
keladi, `t` si esa uzunligi (`Профиль1` 9x33, t=383), va tortib
chiqariladigan shtanga aks holda "old panel" deb konturga aylanardi. 22
namunada o'lchandi: 250 eshik birligi, 3 surma eshik, 43 tortma (old panelining
nomi hammasida `Fasad`/`Фасад`), 60 shtanga birligi va 1 mm siljiydigan sokol
— fasad emas; tortmada ko'rinib qoladigan furnitura: qulf, `KARGO`, qoshiq
idish. Harakatsiz ko'zgu va dekor panel (`3-Garderob`: `Зеркало`, `ХДФ`)
fasad emas — ular yaxlit qoladi. Chegara: old varag'i yo'q, yon varaqlari tik
tortib chiqariladigan birlik ham surma eshik qoidasiga tushib, butunlay kontur
bo'lardi — 22 namunada bunday birlik yo'q.

**Aylantirish.** Pan **O'CHIRILGAN** (`enablePan = false`): mahsulot doim
markazda turadi, ikki barmoq faqat masshtab. Yoqilganda tasodifiy surish uni
ekran chetiga olib chiqib ketardi va «tiklash»dan boshqa yo'l qolmasdi.
Aylantirish esa CHEKLANMAGAN — tagini ham ko'rish mumkin (taglik qanday
biriktirilgani yig'uvchiga kerak bo'ladi). Masshtab `minDistance`/`maxDistance`
bilan chegaralangan: ichiga tushib ketib ham, nuqtaga aylantirib ham bo'lmaydi.
Yaqinlashtirish BARMOQ (kursor) tomonga (`zoomToCursor`): ilgari u doim
mahsulot markaziga borardi va usta chetdagi shkafga yaqinlasha olmasdi — faqat
o'rtadagisiga. Uzoqlashganda (sig'dirish masofasining 85% idan) nishon asta
mahsulot markaziga qaytadi — butun mahsulot ko'ringanda u baribir markazda
(Chrome'da tekshirildi).

**Kamera.** Gabarit KAMERA ramkasiga proyeksiyalanadi, sig'dirish sharidan
emas: yassi mahsulot (3.2 × 2.3 × 0.45 m) sharda ekranning yarmini bo'sh
qoldirardi. Telefonda chegaralovchi burchak gorizontal, shuning uchun ikki
burchakning kichigi olinadi. Ekran o'lchami o'zgarganda (telefon burilishi)
foydalanuvchining BURCHAGI saqlanadi va faqat masofa yetarlicha uzaytiriladi —
ilgari bu faqat "kameraga tegilmagan" bo'lsa ishlardi, ya'ni bir marta
aylantirgandan keyin burilish modelni kesib qo'yardi.

**Qidiruvdan tanlash kamerani OLIB BORADI** (`focusOn`): detal ichkarida,
boshqa panellar ortida bo'lishi mumkin va "qayerda?" savoli javobsiz qolardi.
Masofa sig'dirish masofasining 62% i — atrofi ko'rinib tursin. Nishon — BARCHA
nusxalarning umumiy markazi (ilgari birinchisi edi va telefonda 5 ta javonning
pastkisi kartochka ostida qolardi), JORIY pozadan olinadi, yopiq holatdan emas:
eshiklar ochiq bo'lsa detal yarim metrgacha siljigan bo'ladi. Fokus —
vaqtinchalik chekinish: kartochka yopilganda nishon ham, masofa ham qayerdan
kelingan bo'lsa o'shanga qaytadi. Faqat SHU (qidiruvdagi) fokus qaytariladi:
barmoq tomon yaqinlashtirilgan nishon foydalanuvchining o'zi tanlagani —
shkafga yaqinlashib detalni bosgan va kartochkani yopgan usta joyida qoladi.

**Pastki qatlam modelni to'smaydi.** Kartochka yoki qidiruv natijalari
egallagan balandlik sahnaga beriladi (`setPastkiBand`, `ResizeObserver` bilan)
va kadr uning yarmicha yuqoriga suriladi (`camera.setViewOffset`, 320 ms
tween) — markaz bo'sh joyning markaziga tushadi. Orbit markazi joyida qoladi,
faqat rasm suriladi; nur ham shu proyeksiyadan otiladi. Ilgari telefonda
08_008 ning 5 nusxasidan 2 tasi kartochka ostida qolardi.

**Panel va qirralar.** Panel — konturdan ekstruziya (`ExtrudeGeometry`): tashqi
chegara `o`, kesmalar `h` va aylanalar `c` — `Shape.holes` ga; yoy backendda
nuqtalarga bo'lingan (§2.5). Har panelda
`EdgesGeometry` qirra chizig'i: busiz bir xil rangdagi qo'shni panellar bitta
yaxlit blokka aylanib ko'rinadi. Tanlov va qidiruvda fon panelning qirra
chizig'i **juda xira** (`fonQirraMat`, 13%) chiziladi — to'liq kuchda u
tanlangan detal ustida "qafas" bo'lib qolardi. Xona yuzasida va yashirin
`zamena` qatlamida (topilmagan/tanlanmagan bo'lsa) qirra chizig'i yo'q.

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

**Xona yuzalari (`Devor`, `Pol`) doim XIRA va bosilmaydi**, gabaritga ham
kirmaydi. 460 modelda o'lchandi: 107 tasida (23%) xona bor va u yuzaning
50–100% ini egallaydi — 100 mm qalin berk quti bo'lib mahsulotni butunlay
yopardi, kamera esa oshxonani emas, xonani sig'dirardi. Qoida 140 material
nomidan ikkitasini tutadi, yolg'on ijobiysi yo'q (`model.ts: XONA_YUZASI`).

**Kafel (devor qoplamasi) — oddiy panel** (`model.ts: DEVOR_QOPLAMASI`).
`KAFEL 300x60 mm` (460 faylda 99 marta) — stoleshnitsa bilan ustki shkaflar
orasidagi 10 mm li fartuk, ilgari xona yuzasiga qo'shilgan edi: 16% shaffof,
teksturasiz va bosilmas — egasi: kartochka rasmida tekstura bor, modelda hech
narsa yo'q, bosib o'lchamini bilib bo'lmaydi. U berk quti yasamaydi va detal
kodi bor (`00_004`, 2660 × 800 × 10): endi katalog teksturasi bilan chiziladi,
bosiladi (kartochka, o'lchami) va qidiriladi. Mebel gabaritiga, haqiqiy
qirralarga va modullarga KIRMAYDI (`mebelEmas`) — oshxona chuqurligi devor
qoplamasi bilan oshib ketmasin (`01 Kuxniya` ilgarigidek 3360 × 2950 × 600).
Chrome'da tekshirildi.

**Qirra chizig'i ikki xil**: quyuq dekorda (`wenge`, `qora` — ishlatilishning
17.5% i) quyuq ko'k chiziqning kontrasti 1.05–1.20 ga tushib ko'rinmay
qolardi, holbuki chiziq aynan "qo'shni panellar bitta blokka aylanib
qolmasin" uchun bor. Material rangining yorqinligi 0.18 dan past bo'lsa OCH
chiziq (`#c9d1dc`) olinadi.

**`near` = 40 mm.** 24 bitli z-bufer aniqligi `near` ga teskari proporsional:
10 mm da 0.4 mm lik surilish sig'dirish masofasida atigi 2.3 birlik bo'lib,
yupqa detallar bir-birining ichiga kirib titrardi. 40 mm dan
yaqinga hech narsa tushmaydi — `minDistance` (`0.12 × eng katta o'lcham`) eng
kichik mahsulotda ham 52.8 mm (460 fayldagi 440 mm lik javon; namunalarda
164.6 mm).

**Bosish FAQAT birinchi barmoqda**: ikkinchi barmoq tushsa kutilayotgan bosish
bekor qilinadi. Busiz pinch paytida ikkinchi barmoqning `pointerup` i o'z
tushgan nuqtasidan 8 px narida bo'lgani uchun "bosish" deb hisoblanib,
tanlangan detalni YO'QOTARDI (telefonda takrorlanib tasdiqlandi). Barmoqlar
hisoblagich bilan emas, `pointerId` to'plami bilan sanaladi va `pointercancel`
ham tinglanadi: bekor qilingan barmoq (tizim imo-ishorasi, qo'ng'iroq oynasi)
`pointerup` bermaydi, hisoblagich 1 da qotib, keyingi har bosish "ikkinchi
barmoq" bo'lib, tanlash sahifa yangilanguncha o'lardi.

**Ko'rinish KATALOGDAN, topilmasa material nomidan.** Birinchi navbat
`matRang.gen.ts` jadvalida — u Bazis katalogidan (`BAZA 1.FDB`) va tekstura
rasmlaridan `scripts/bazis-material-colors.py` bilan yasaladi va **460 ta
haqiqiy modeldagi panellarning 74% ini qoplaydi** (profil bo'laklari bilan 47 561
dan; 215 yozuv, 15 KB — `MAT_TEX` bilan).

Rang manbai: teksturaning o'rtacha rangi, teksturasiz yozuvlarda katalogdagi
`PARAM_1`. Nomlar normallashtiriladi (texnolog plita kvadraturasini va
yetkazuvchini nomga qo'shadi: `LDSP DUB VOTAN 5.03 kv.  Khatdekor`), aniq
topilmagani so'zlar kesishuvi bo'yicha moslanadi — moslash GENERATSIYA
paytida hal qilinadi, brauzerda taxmin yo'q. `normMat` (`model.ts`) va
`norm()` (skript) QO'LDA oynalangan; 140 ta haqiqiy nomda ikkalasi bir xil
kalit berishi tekshirilgan.

Nega kerak edi: regexning o'zi bilan teksturasi bor materiallarning **28% i**
sezilarli xato rang olardi — `LDSP INTERNO ZOLOTA` oltin chiqardi (aslida oq
marmar, farq 183), `LDSP KASPIY TYOMNIY` jigarrang chiqardi (aslida ko'kish
kulrang, 87), `LMDF AZIYA` kulrang chiqardi (aslida to'q qizil-jigar, 285).
Katalog rangiga TEGILMAYDI — u taxmin emas, shuning uchun tafovut (pastda)
faqat regex zaxirasiga qo'llanadi.

**Zaxira — material NOMIDAN** (`model.ts`), indeksdan emas.
Kalit so'zlar 437 buyurtmadagi 162 material nomidan olingan (85 753
ishlatilish), o'ylab topilmagan: `oq` 25.4%, `glyanets` 10.7%, `mokriy` 9.0%,
`dub` 8.7%, `sasna` 8.5%, `qora` 8.5%, `matviy` 7.8%, `kashmir` 5.8%.
Yaltiroqlik ham shundan: `GLYANETS` -> 0.28, `MATVIY`/`SHAGREN` -> 0.85.
Kalit so'zlarning kirillchasi ham bor (`дуб`, `мокко`): Bazis nomni ruscha
yozishi mumkin (`ЛМДФ (Местный) 2750х1830 Дубь Честерфильд 16мм` — 460 faylda
304 panel, `Мокко` — 22) va ular betaraf kulrangga tushib, yog'och garderob
butunlay kulrang chiqardi.
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

**Katalogdagi `PARAM_1` ni yolg'iz ishlatib bo'lmaydi:** teksturali
materialda u ANDOZA — 108 yozuvdan 107 tasi bir xil `8369910` (`#f6b67f`).
Shuning uchun rang avval TEKSTURA rasmidan olinadi, `PARAM_1` esa teksturasiz
yozuvlarda va teksturasi diskda topilmagan yozuvlarda (andoza qiymati bundan
mustasno). U yerdagi `0` (qora) va `16777215` (oq) haqiqiy: bu
qiymatli teksturasiz yozuvlarning hammasi rostdan qora yoki oq buyum
(`1-19 qora`, `LDSP OQ GLYANETS`).

Qolgan 26% — katalogda umuman yo'q nomlar: `zamena material` (7.2%, ko'rinmaydi —
pastda), profil va furnitura (`ALLU` 3.0%, `BAYFU` relsi 2.0%), rang nomlari
(`oq rang` 2.6%, `kul rang` 1.2%); ular regex zaxirasiga tushadi.

**Tekstura — naqshli materialda rasmning o'zi.** Katalog rasmni SAQLAMAYDI:
`PARAM_TEXTURE.NAME_TEXTURE` — tekstura papkasiga nisbatan yo'l
(`stolishnitsa\N 111 Дуб Вотан (матовый).jpg`), `PARAM_2` — `UseColor` (1 bo'lsa
tekstura EMAS, rang: `LMDF BIR TOMON GOLI` oq, `110011.jpg` o'rtachasi emas),
`PARAM_12 x PARAM_13` — bitta tayl, mm (240 yozuvdan 215 tasida 1000 x 1000,
stoleshnitsada 600 x 3000), `PARAM_14` — burchak. Ma'nosi fayllarning Undo'sidagi
Bazis `Mt` yozuvlari bilan solishtirib aniqlangan. Generator (`scripts/
bazis-material-colors.py`) rasmida naqsh bor HAR materialni (qo'shni piksellar
o'rtacha farqi >= 0.7 — yog'och, marmar, beton, shagren; kromka turidagisi
bundan mustasno) JPEG q80 qilib `frontend/public/assets/tex/<xesh>.jpg` ga yozadi
— aniq naqshlisi (L* std >= 4) 1024 px, qolgani 512 px — va `MAT_TEX` jadvalini
chiqaradi: hozir 33 rasm, 3.1 MB (bitta model faqat o'z materiallarinikini
yuklaydi: `dub vatan` 110 KB). Katalogda yo'q nom uchun papkada dekor nomi AYNAN
mos rasm olinadi (`LDSP dub beliy` -> `dub beliy.jpg`, 68 panel). 460 faylda
qalin panellarning 42.2% i teksturali (ilgari 18.4%); 50.6% i bir tekis dekor
(`OQ`, `OQ GLYANETS`, `KASHMIR`, `MOKRIY`, `METALIK`, XDF orqa devor) — katalogda
rasmi yo'q yoki rasm bir tekis (`kapuchino.jpg`, `Кашемир.jpg` — farq 0.0), rang
rasmning o'rtachasi; 7.2% i katalogda umuman yo'q.

**Tayl chegarasidagi chiziq.** Rasmlarning ko'pi ulanuvchan tayl EMAS, oddiy
foto: takrorlanganda chegarada qattiq chiziq qoladi (`110026` dub vatan — TV
zonaning 2 m li yon devori 1000 mm balandlikda kesilgandek ko'rinardi).
Generator har o'qni alohida o'lchaydi: qarama-qarshi chetlar farqi / qo'shni
piksellar farqi. `*_diffuseOriginal.png` (haqiqiy tayl) 0.9-1.6, fotolar 2-11;
1.8 dan yuqori o'qda (`aksU`/`aksV`) brauzer rasmni KO'ZGU kabi ulaydi
(`MirroredRepeatWrapping`): chet o'zi bilan tutashadi, tola uzilmaydi, faqat
naqsh aks etadi. Taylni butun varaqqa (2800 mm) yoyish ham chokni yo'qotardi,
lekin tola 2.8 barobar yo'g'on chiqardi — `110026` dagi 5-6 taxta chizig'i
~380 mm li bo'lib. Shuning uchun tayl katalog o'lchamida, faqat rasm tomonlari
nisbati saqlanadi (uzun tomoni katalogdagi taylniki: 600 x 800 px rasm 750 x
1000 mm, katalogdagi andozaviy 1000 x 1000 ga cho'zilmaydi).

**Har panel varaqning boshqa joyidan** (`scene.ts: naqshSiljit`): rasm hamma
panelda konturning (0, 0) nuqtasidan boshlansa yonma-yon eshiklar aynan bir xil
naqshli chiqardi. UV panel BITTA tayl ichida qoladigan qilib siljitiladi
(barqaror tasodif — panel indeksidan): tayldan kichik detalga chegara ham, ko'zgu
chizig'i ham tushmaydi. 2000 ta sun'iy panelda three.js UV matritsasi bilan
tekshirildi: tayldan kichik 224 tadan 224 tasi bitta taylda, 219 xil boshlanish.

Chizish (`scene.ts: panelMaterial`): `ExtrudeGeometry` yuzalarining UV'si —
kontur mm, ya'ni `repeat = 1 / tayl`. Tola `TexDir` bo'yicha kontur X (`r`)
yoki Y bo'ylab; rasmdagi tola odatda bo'yi bo'ylab, stoleshnitsa fotosida esa
eni bo'ylab (`tolaU` — gradient energiyasidan: `N 111 Дуб Вотан` 3.2 ga 7.1).
Ikkisi farq qilsa 90° buriladi. Ilgari faqat `r` qaralardi va `N 111` li
stoleshnitsalarning 20 tadan 18 tasida (`TexDir` tolani uzun o'q bo'ylab
qo'ygan) tola ko'ndalang chiqardi. Yon devorlar (1-guruh) tekis rangda —
kromka chizilmaydi. Rasm yuklanguncha
yuza rasmning o'rtacha rangida (`MAT_RANG` aynan shu o'rtacha), ya'ni almashuv
ko'zga tashlanmaydi; tanlov/qidiruv holatida — tekis rang. `BoxGeometry`
zaxirasida (konturi yo'q panel) tekstura yo'q — uning UV'si 0..1.

**Uch xil yaltiroq yuza** (`model.ts: maxsusYuza`) — katalogda shaffoflik
yo'q (`PARAM_7` 240 yozuvda 0), ya'ni nomdan: SHISHA (`oyna`, `стекло`) — 34%
shaffof, ortidagi javon ko'rinsin; KO'ZGU (`зеркало`, `kozgu`) — shaffof EMAS,
metall kabi aks ettiradi (ilgari `Зеркало` shaffof, `Kozgu` mat buyum edi);
EKRAN (`экран`) — deyarli qora, yaltiroq; ZAMENA (`zamena material`) —
umuman ko'rinmaydi (pastda). Furnitura metali (`nikel`, `хром`,
`сталь`, alyumin `ALLU`) — `metalness 0.6`; `LDSP METALIK` kabi DEKOR nomi
metall emas.

**`zamena material` — shaffof qatlam, chizilmaydi.** Texnolog eshiklarni
alohida qo'yib, ustidan 0 mm li `zamena material` qatlami bilan hammasining
rangini bittaga keltiradi; Bazisda bu material SHAFFOF qilib qo'yiladi va
ostidagi fasadning asl rangi ko'rinadi. O'lchandi: 3447 panelning hammasi
0 mm, 91% i (3128) aynan haqiqiy fasad yoki orqa panel yuzasida yotadi;
fayllarda saqlangan hamma `Mt` yozuvida (3 fayl, 6 yozuv) `Transparency = 1`,
rangi oq. Ilgari u 1 mm li kulrang plita bo'lib chizilib, ostidagi fasadni
yopardi — `01 shkaf` eskizda qora, 3D da kulrang eshikli chiqardi. Endi oddiy
holatda ko'rinmaydi, qirra chizig'i ham yo'q va bosish ostidagi fasadga
o'tadi; qidiruvda topilsa yoki tanlansa — joyi bilinsin deb — rangda.

**Eskiz va 3D baribir farq qilishi mumkin — va buning sababi faylda yo'q.**
Eskizni Bazis loyihachining KOMPYUTERIDA, uning material kutubxonasi bilan
chizadi; `.b3d` esa faqat material NOMINI saqlaydi (rang/tekstura yozuvlari
faqat ba'zi fayllarning Undo tarixida qoladi va ular ham ishonchsiz: `qora
rang` 10 marta sariq, `БЕЛЫЙ` 15 marta to'q kulrang yozilgan). 3D rangni nom
bo'yicha kompaniya katalogidan (`BAZA 1.FDB`) oladi. Kutubxona nomga zid
ko'rinish bergan joyda ular ajraladi: `AKRIL 10312C2-08 Grey Hairline`
(kulrang akril) eskizda to'q yashil, `ЛМДФ Белый гладкий` (oq) eskizda
yog'och — bu fayllarda material yozuvi umuman yo'q.

QAROR (texnolog, 2026-09-23): sexda material NOMI bo'yicha kesiladi va
yig'iladi, Bazisdagi rang — loyihachining vizuali. Shuning uchun 3D nomga
ergashadi va eskizdan farqi — kutilgan holat: ustaning qo'lidagi plita
eskizdagiga emas, 3D dagiga o'xshaydi.

**Furnitura** (`meshes`/`furn`) — har nusxa `Group`, qismlari umumiy
`BufferGeometry` bilan. Harakat massivlari panellar va furniturani BIRGA
qamraydi (`harakatElementlari`): eshikdagi tutqich eshik bilan ochiladi. Bosish,
qidiruv va qirra chizig'i — faqat panellarda; tutqich ustida bosilsa eshik
tanlanadi.

**O'lchamlar — bosqichma-bosqich, standart holatda modelda chiziq YO'Q.**
DetalQR (raqobatchi, Chrome'da ko'rildi) Bazisning o'lcham obyektlarini doim
yoqilgan 3D chiziq va model tekisligidagi matn qilib chizadi: yozuvlar ustma-ust
tushadi, burchak ostida o'qilmaydi, shkaf ichidagisi shisha ortidan ko'rinadi.
Bu yerda uch qavat (dizayn 3 taklif + 3 hakam bilan tanlangan):

* HECH NARSA BOSMASDAN — sarlavhada gabarit matn bilan: `B-2026-001 · 3200 ×
  2300 × 450 mm` (`model.ts: gabarit` — yopiq holat, faqat panellar; xona yuzasi,
  `zamena` va furnitura kirmaydi: tutqich chuqurlikka 30 mm qo'shardi).
* DETAL TANLANGANDA (tugma shart emas) — uning ENI va BO'YI o'zining qirralarida,
  kameraga qaragan yuzada (`scene.ts: olchamYangila`). Kartochkadagi
  «347 × 481 × 16» qaysi tomonga tegishli ekanini ko'rsatadi. Qalinlik faqat
  kartochkada. Nusxalar ko'p bo'lsa — ekran markaziga eng yaqini (boshqasi 20%
  dan ko'proq yaqinlashmaguncha almashmaydi, sakramasin). Eni avval ekranda
  PASTDAGI qirraga, bo'yi O'NGDAGIsiga; joy bo'lmasa qarama-qarshisiga.
* BAZISCHINING O'LCHAMLARI (`Type=9000`, 460 faylda 257 tasida, 22 namunadan
  14 tasida) — tanlangan detalga TEGADIGANLARI (uchi uning yopiq qutisidan 1 mm
  ichida) tugmasiz: javon balandligi bazischining o'z raqami bilan, taxmin emas.
* «O'LCHAMLAR» tugmasi (chizg'ich, qidiruv yonida, 48 px; holati `localStorage`
  `mx3d-olcham` da, standart holatda o'chiq) — gabaritning uch o'lchami va
  bazischining BARCHA o'lchamlari (kattasi birinchi). Tanlov yoki qidiruv
  ro'yxati bo'lsa yashirin. Gabarit — sarlavhadagi qiymat, qutisi panellardan
  (xona, `zamena`, furniturasiz); eni va chuqurligi kameraga yaqin YUQORI
  qirrada (kamera pastdan qarasa — pastki qirrada), bo'yi old yuzaning narigi
  tik qirrasida. Ilgari eni va chuqurligi pastki qirrada polda edi: tsokoli
  ichkariga kirgan, oyoqli mebelda (`02 tumba`) uzatma chiziq pol sathidagi
  xayoliy burchakdan chiqib, o'lcham mebelga emas, polga bog'langandek
  ko'rinardi. Qirra va surilish yo'nalishi — pastda.

**Gabarit — HAQIQIY qirrada, quti qirrasida emas** (`model.ts:
gabaritQirralari`). Gabarit qutisining qirrasi mahsulotda bo'lishi shart emas:
`05 Kuxniya` (U shaklli) da old qirralar xona o'rtasida havoda (X bo'ylab old tepa
qirraning 4% ida mebel bor), ramkali `01 shkaf` da chuqurlik qirralari 3% da (16
mm li old ramka qutini 160 mm kengaytiradi). U yerga chizilgan o'lcham "fazoda
osilib" turardi — egasi 05 Kuxniya ni aylantirib ko'rdi. Baymard (e-savdo UX
tadqiqoti): "visually link each measurement to its location on the product";
L shaklda "the width could be very different depending on what part you're
looking at". Roomle rejalovchisi ham L shaklli obyektda umumiy quti emas, qism
qutilaridan foydalanadi. Endi har o'q va chorakda panellar bo'ylab deyarli butun
uzunlikka (80% qamrov, uchlari 150 mm gacha kemtik, 30 mm tegish) yotgan eng
TASHQI chiziq qidiriladi — oddiy qutisimon mebelda u aynan quti qirrasi, U
oshxonada eni orqa devor qatorida, chuqurligi yon qatorda. Kameraga yaqin
chorakda bunday chiziq bo'lmasa keyingisi; o'qning hech bir choragida bo'lmasa —
quti qirrasi (22 namunadan bittasi: `01 shkaf` 5214 mm, eni 78% gacha).

Qo'shimcha qoidalar (hammasi sahnada o'lchangan):
* o'lchamning o'zi kameraga qarab ketgan (o'qi ko'rish yo'nalishiga 30° dan
  yaqin) — chizilmaydi: orqadan qaralganda chuqurlik qisqa chiziq bo'lib qolardi;
  model-viewer ham kameraga teskari tomondagi o'lchamni yashiradi;
* kamera past (45° dan) bo'lsa, ekranda TIK ko'ringan eni/chuqurlik chizilmaydi —
  mijoz 3450 mm li tik chiziqni 2460 mm li ustun yonida bo'yi deb o'qiydi;
* boshqa o'lcham uchi 10 px ichida bo'lsa (bir 3D o'qdagi uchma-uch zanjirdan
  tashqari) nomzod tashlanadi — ikki strelka bitta burchakda "V" bo'lardi;
* yorliqda birlik: «3620 mm» (model-viewer va Roomle ham birlik bilan);
  sig'masa o'sha joyda faqat raqam («600») — sarlavhada «… mm» baribir bor.

Oldin va keyin, 60 ko'rinishda (6 model): chizig'ining 70% dan kami mebel
ustida bo'lgan gabarit o'lchami `05 Kuxniya` 109/164 → 0/144, `01 shkaf` 81/133 →
0/128, `3-Garderob` 152/164 → 0/135, `01 Kuxniya` 107/130 → 0/126; past kamerada
tik ko'ringan eni/chuqurlik 2-4 → 0; uchlari 6 px dan yaqin juft — 0. 22
namunaning hammasida gabarit bo'yicha to'qnashuv 0 (faqat gabarit bilan
o'lchandi). Telefonda old ko'rinishlarda eni 13-15/15, bo'yi 12-15/15.

Og'ir qism — bazischi o'lchamlari va gabarit — faqat TINCHLIKDA joylanadi
(kamera, eshik kaskadi, kamera tween'i va pastki panel animatsiyasi turganda),
harakat paytida yashirin. Kameraning qimirlashi kadrlar orasidagi siljishdan
o'lchanadi, `update()` dan emas: g'ildirak va ikki barmoqli zoom `update()` ni
hodisa ichida o'zi chaqiradi (`tick` dagisi o'zgarish ko'rmaydi), susayish dumi
esa ~1 s ko'rinmas sub-piksel siljish bilan `true` qaytaradi — u to'xtatiladi,
o'lchamlar aylantirish tugagan kadrdayoq chiqadi:
ular uchun har yorliqqa nur otiladi (ortida panel bormi) va har kadrda o'nlab
nur telefonni yerdi. Nur SHISHA va opaq panellarda to'xtaydi, xira (tanlovda),
`zamena` va xona yuzasida to'xtamaydi. Oqibati: `01 Kuxniya` dagi 9 o'lchamning
hammasi shkaf ICHIDA (seksiya balandligi 916, tortma fasadlari) — yopiq holatda
chizilmaydi (DetalQR ularni shisha ortidan ko'rsatardi), «Ochiq» da ochiq
eshiklar orasidan ko'rinadi. Eshik yoki tortma yig'masi ichidagi o'lcham (`g`)
o'sha birlik ochiq bo'lsa chizilmaydi — u yopiq holatda yozilgan, havoda qolardi.
«Ajratilgan» da faqat tanlangan detalning o'lchami. Tartib: tanlangan detal,
unga tegadigan bazischi o'lchami, gabarit, qolgan bazischi o'lchamlari —
yorliqlar shu tartibda joy oladi, joy topilmagani chizilmaydi.

**Chizma — chizmachilik standarti bo'yicha.** Egasi burchaklarda "siniq
chiziq" ko'rdi. Sababi uchta edi, uchalasi chizmachilik amaliyotiga zid
(tadqiqot manbalari sahifaning o'zidan `grep -F` bilan tekshirildi):

* **Surilish — yuza TEKISLIGIDA, bitta dunyo o'qi bo'ylab.** US Navy izometrik
  qoidasi: o'lcham, uzatma chiziq va strelka "must lie in the planes of the
  object to which they apply"; ISO 16792 ham annotatsiya tekisligini model
  koordinata tekisligiga parallel qiladi. Ilgari eni va chuqurligi 45°
  diagonalga surilardi — uzatma chiziq hech bir qirraga parallel emas edi (60
  ko'rinishda median 17°, eng ko'pi 44° og'ardi) va burchakdan sinib chiqqan
  qirradek o'qilardi. Endi: eni old yuzada tepaga (tepadan qaralsa — tepa
  yuzada oldinga), bo'yi old yuzada narigi chetga (yondan qaralsa — yon yuzada
  orqaga), chuqurligi tepa yuzada yonga (keyin pastki qirrada yonga, keyin yon
  yuzada pastga — kamera gorizontga yaqin bo'lsa gorizontal tekisliklar
  yonidan ko'rinadi). Bitta burchakka tegadigan ikki o'lcham HECH QACHON bir o'q
  bo'ylab surilmaydi — aks holda ikkala strelka bitta pikselga tushardi.
  Qaysi qirra — kamera markazning qaysi tomonida; tomon markazdan gabaritning
  5% idan ko'proq o'tgandagina almashadi (sustlik: aylantirganda sakramasin).
* **Uzatma chiziq obyektdan TIRQISH bilan** (3 px) va o'lcham chizig'idan 6 px
  oshib. Tirqishsiz, yuza tekisligidagi uzatma chiziq panel qirrasining
  davomiga aylanadi. Manbalar: Peachpit "This serves as a visual break between
  the object and the extension line"; NKBA (oshxona chizmalari standarti) "The
  extension line must not touch the wall or object"; Open Oregon tirqish ~1/16″,
  oshish ~1/8″; Cambridge — tirqish 1.5 mm, oshish 3 mm (strelka uzunligi).
  Surilishsiz o'lchamda (`Length` 0) uzatma chiziq yo'q.
* **Strelka har uchida O'Z masshtabi bilan** — 8 px uzun, yarim eni 2 px.
  Ilgari butun chiziqning o'rtacha masshtabi olinardi: perspektivada strelka
  7-18 px, bir o'lchamning ikki uchi 6.5 px gacha farq qilardi.

Qirradan uzoqligi: tanlangan detal 24 px, gabarit 32 px (tashqi qator;
Cambridge: birinchi qator obyektdan ~4 strelka uzunligida); har nomzod oxirida
16 px bilan yana bir bor sinaladi — telefon portretida mahsulot kenglikni
to'ldiradi va chetdagi yorliq ekrandan chiqib ketardi. Yorliq strelkani yopmaydi
— markazidan har uchigacha kamida yarim eni + 10 px, sig'masa o'lcham
chizilmaydi; qo'yilgan strelkalar ham band joy, keyingi yorliq ularni yopmaydi.
Masofa tik o'qning O'Z masshtabi bilan o'lchanadi (burchak ostida ikki o'q har
xil qisqaradi) va qirradan ekranda TIK masofa aynan shuncha px. Variant
tashlanadi, agar tik o'q o'lcham o'qidan 5 barobar ko'p qisqargan bo'lsa yoki
ekranda undan 20° dan kam og'gan bo'lsa — ikkalasida ham surilgan chiziq
qirraning o'zi ustiga tushardi (NISBAT, qat'iy px/mm emas: telefonda butun
oshxona ko'rinib turganda to'g'ri qaralgan yuzaning o'lchami ham yo'qolardi).
Bazischi o'lchamida surish fayldan, u tashlanmaydi; strelka qanotlari doim
ekranga tik tekislikda ochiladi.

Haqiqiy `scene.ts` ni soxta renderer bilan yurgizib o'lchandi (390x700, 60
ko'rinish: balandlik −10…70°, har 30°; `02 tumba`, `02 Tyumo`): uzatma
chiziqlarning 100% i quti qirrasiga parallel (ilgari 22-27%), tirqish 3.0 px,
strelka 8.1-8.5 px (bir o'lchamning ikki uchi farqi ≤ 0.4 px), ikki o'lcham uchi
6 px dan yaqin — 0 juft (ilgari 4). Telefonda old ko'rinishlarda (15 ta) eni
har doim, bo'yi 11-12 tasida (ilgari 8-10), chuqurligi o'zgarmadi yoki
ko'paydi. Tanlangan detalning o'lchami 3 modelda (81-165 holat) 4-8 holatda
kamroq chiziladi — 20° qoidasi: chiziq qirradan 6-8 px ga tushardi.

Qilinmagan (tadqiqotda bor): 1.5 px qalin chiziq (`LineSegments2`) — hozir
1 qurilma pikseli, DPR 2 da 0.5 CSS px; zanjirdagi umumiy nuqtada strelka
o'rniga nuqta; qisqa o'lchamda strelkani tashqariga chiqarish. Surilishsiz o'lchamning (`Length` 0, 460 faylda 9 ta, 8
tasi tik) yo'nalishi chiziqqa tik tanlanadi. Raqam — HTML yorliq
(`ModelViewer` dagi qatlam, `pointer-events: none`, 13 px): har burchakda tekis.
Yorliqlar Reactsiz, KADR bilan birga joylanadi (`tick` dagi `ozgardi || kir` —
alohida sikl yo'q). QOIDA: yorliq bilan chizig'i DOIM birga — chiziq ekranda
yorliqdan qisqa bo'lsa yoki yorliqqa joy topilmasa ikkalasi ham yashiriladi;
chiziqsiz raqam ham, raqamsiz chiziq ham yo'q. Joy chegarasi — tugmalar qatori
va pastki panel (kartochka + QIDIRUV + chekka), ikkalasi ekrandagi HAQIQIY
o'lchamidan (`setYorliqZona`, `ModelViewer` dagi `ResizeObserver`): ilgari faqat
kartochka hisobga olinib, yorliq qidiruv maydoni ostida qolardi, chizig'i esa
ko'rinardi (landshaftda 19 dan 11 tasi). Tuzatilgach 844x390 va 360x588 da 251
yorliqdan 0 tasi bu joylarga tushdi (haqiqiy `scene.ts` bilan o'lchandi). Qolgan detallar
tanlovda xira (`depthWrite` yo'q), ya'ni chiziqni hech narsa to'smaydi.
«Ochiq» va «Ajratilgan» da ham chiziladi — detalning joriy holatida.

Qilinmaganlar: doim yoqilgan o'lchamlar; ikki nuqtali chizg'ich (barmoq 16 mm
qirraga aniq tegmaydi, ustada ruletka bor); oraliq va «poldan balandlik»ni
hisoblash (oshxonalarda noto'g'ri raqam berdi — noto'g'ri raqam raqamsizlikdan
yomon); 3D matn.

**Shkaf (modul) darajasi.** Butun mahsulot gabariti ichkaridagi shkafga javob
bermaydi, bazischining o'lchamlari esa 22 namunadan 7 tasida umuman yo'q. Bazis
o'zi ham avtomatik o'lchamda "значение ширины всех моделей" (har modelning
enini) beradi. Modul — detal kodining birinchi bo'lagi (`13_005` → 13-modul,
`model.ts: modullar`); 22 namunada 231 guruhning 2143 juftidan 47 tasi (2.2%)
bir-biriga kirib turadi, ya'ni amalda alohida qutilar. Shkaf emaslari chiqarib
tashlanadi: `00` (stoleshnitsa, tsokol), kodsiz panellar (6.9%), 4 tadan kam
panelli guruh (planka, karniz, tsokol — 26 ta), 60 mm dan yupqa (anteresol
taxtasi, LED profil, ko'zgu); mahsulotda bitta modul bo'lsa (6 namuna) — daraja
yo'q. Qoladi 165 modul. Modul o'lchami faqat KARTOCHKADA — detal qaysi shkafda:
«Moduli №04 · 790 × 750 × 518 mm»; 3D ni to'ldirmaydi. Yaqinlashganda shkafni
rentgen quti va uning o'lchamlari bilan ko'rsatish sinab ko'rildi (Chrome'da
ishladi) — egasi yaxshi yechim emas dedi va u olib tashlandi. Ichki ARALIQ
(javonlar orasi, poldan balandlik) hisoblanmaydi — ilgari oshxonalarda noto'g'ri
raqam bergan, u faqat bazischining o'lchamidan.

**Tanlanganda — uch qavat, DetalQR dan farqli.** DetalQR bosilganda butun
modelni rentgenga o'tkazadi: barcha panel shisha, BARCHA qirra to'liq
chiziladi, tanlangan detal shaffof to'q sariq — 300 panelli oshxonada sim
to'ri, detal shu to'r ichida yo'qoladi; o'lcham va material esa sichqoncha
ustiga olib borilgandagina. Bizda:
* **tanlangan detal** — to'liq oltin rang, konturi (`tanlanganQirraMat`,
  `depthTest` siz, eng oxirida) boshqa panellar ORTIDAN ham ko'rinadi, o'lchami
  va kartochkasi darhol;
* **qo'shnilari** — unga tegib turgan panellar (yopiq holatdagi qutilar 2 mm
  ichida) 42% da, oddiy qirra bilan; unga o'rnatilgan furnitura — o'z rangida.
  Ustaning asosiy savoliga javob: «bu nimaga ulanadi». Javon uchun — ikki yon
  devor, orqa devor va javon ushlagichlari; eshik uchun — yon devor, tub,
  tutqich, ilgak (sahnada tekshirildi);
* **fon** — 16%, qirrasi juda xira (13%): tuzilish (qaysi shkaf, qaysi qavat)
  o'qiladi, lekin tanlangan detal ustida "qafas" yo'q.
Tanlov yopilganda barcha qirra asl holiga qaytadi (tekshirildi).

**Tanlash — bosish, surish emas:** 8 pikseldan ortiq surilgan bosish
aylantirish deb qabul qilinadi. Qidiruv faol bo'lsa faqat TOPILGANLAR
bosiladi: xira panel deyarli ko'rinmaydi, lekin nur uchun to'siq bo'lib
turardi va foydalanuvchi ko'rmagan detalini tanlab olardi. Xona yuzasi esa
hech qachon — nomi qidiruvga mos kelsa ham. Bosilganda detalning BARCHA
nusxalari tanlanadi (kodi, nomi va o'lchami bir xil — chap va o'ng eshik) va
kartochkada «2 nusxa» turadi; ilgari faqat bosilgani yonardi, qidiruv esa `×2`
ko'rsatardi. Tanlov qidiruvdan USTUN: qolgan topilganlar xira bo'ladi — ilgari
ular to'q ko'k bo'lib qolib, tanlangan detalni yopib qo'yardi.

**Qidiruv chekdagi Detal ID ni tushunadi** (`model.ts: matchPanel`). Chekda
faqat to'liq ID bosiladi — `{buyurtma}_{mahsulot}_{detal}[-N][_n]`, masalan
`B-2026-001_208301_23_002_2` (docs/11) — usta aynan shuni teradi. Buyurtma
prefiksi (`lib/mes.ts: ORDER_PREFIX`) va mahsulot kodi olib tashlanadi; mahsulot
kodi bo'lsa detal kodidan keyin faqat `-N` va `_n` qolishi mumkin. Ilgari faqat
`23_002` terilsa topilardi, to'liq ID esa "Bunday detal topilmadi" berardi.

Solishtirish `_` BO'LAKLARI bo'yicha, satr ichidan emas: ilgari `03_002`
normallashib `3_2` bo'lardi va `23_002`, `13_002` ham "topilardi" — usta "bu
detal qayerga?" deb so'raganda bir necha joy ko'rardi. Boshidagi nollar
hisobga olinmaydi (`23_2` = `23_002`), oxirgi bo'lak prefiks bo'lishi mumkin
(`23_0` terilayotganda ro'yxat bo'sh qolmasin). Kod AYNAN topilsa faqat o'sha
ko'rsatiladi, aks holda aniqrog'i yuqorida, keyin KOD tartibida raqam
sifatida (`03_002` -> `03_010`; ilgari fayl tartibida edi), kodsizlari oxirida.
Bir xil kodli nusxalar bitta qatorga yig'iladi (`×2`): chap va o'ng eshik bir
xil detal.

**Enter — birinchi natija** (u ajratib ko'rsatiladi): skaner kodni Enter bilan
yuboradi, telefonda esa klaviaturadagi «Qidirish» (`enterKeyHint="search"`).
Tanlangach klaviatura yopiladi — aks holda u modelning yarmini to'sib turardi.
**Esc** qidiruvni ham, tanlovni ham tozalaydi. Terish paytida kamera O'ZI
uchmaydi — ataylab: `3_20` terilayotganda `3_2` bir lahza `03_002` ga aynan
mos keladi va kamera noto'g'ri detalga uchib, keyin qaytardi. Ro'yxat
balandligi `min(19rem, 34dvh)`: telefonda u ekranning ~55% ini egallab,
topilganlarni o'zi yopib qo'yardi.

**Detal kartochkasi:** kod (tizimdagi boshqa jadvallar kabi Archivo `num`,
`font-mono` emas), nusxalar soni, nomi, o'lchami va materiali. Qalinligi 0 bo'lsa
u yozilmaydi — bu plita emas, fasad ustidagi shaffof `zamena material` qatlami
(41 305 paneldan 3 482 tasi, pastda), `× 0 mm` esa xatodek o'qilardi. Material nomi Bazis shovqinisiz
(`model.ts: materialKorinishi`): plita kvadraturasi, formati, qalinligi va
yetkazuvchisi olib tashlanadi — `ЛМДФ (Местный) 2750х1830 Дубь Честерфильд 16мм`
-> `ЛМДФ Дубь Честерфильд` (140 ta haqiqiy nomdan 63 tasi qisqaradi, bittasi
ham bo'sh qolmaydi). To'liq nom `title` da. `normMat` bilan birlashtirilmagan:
u katalog KALITI, bu esa ko'rsatish.

## 8. Chegaralar

* **Teshik va freza YO'Q** (1-bosqichdan ataylab chiqarilgan). `Hole` tugunlari
  faylda bor, lekin yig'uvchiga panelning O'RNI kerak, teshigi emas.
* **Traektoriya bo'ylab jism (`2001`, 7 ta) chizilmaydi** (§2.8) — duxovka
  tutqichi, kir yuvish mashinasi eshigi halqasi.
* **Ochiq holatda ichki mexanizm ochiq eshikka 7-10 mm kirib turishi mumkin** —
  Bazis faylining o'zidan. Eshik ichki qirrasi atrofida buriladi (`Shift = 0`,
  o'q eshikning orqa yuzasida), mexanizm (shim ilgichi relsi, pantograf, savat)
  to'liq chiqadi; haqiqiy ustquyma ilgak ochilishda eshikni tashqariga surgani
  uchun hayotda ular tegmaydi. 460 faylda 376 mexanizmdan 89 tasi (10 fayl,
  shundan 5 namuna — `3-Garderob`, `01 Kuxniya*`), chuqurlik median 7.5 mm, eng
  ko'pi 9.7 mm. Qaror (egasi, 2026-09-23): «Ochiq» faylni o'zgartirmasdan
  o'ynatadi — mexanizmni joyida qoldirish ham, eshikni sun'iy surish ham
  rad etildi.
* **Ochiq eshikda ilgak "uzilgan" ko'rinadi** — Bazis faylida ilgak ikki alohida
  obyekt: tana (tirsak + plita, `Petlya ROBUST`, 68 x 54 x 22 mm) yon devorda
  harakatsiz, kosa (`chashka`, 3 mm halqa) eshik bilan ochiladi; tirsakning
  ochiq holatdagi shakli faylda yo'q. `02 tumba` `01_022`: markazlar orasi yopiqda
  33 mm, ochiqda 76 mm. Qaror (egasi, 2026-09-23): faylda qanday bo'lsa —
  sun'iy tirsak chizilmaydi; yig'uvchiga kerak joylashuv (kosa va plita qayerda)
  to'g'ri ko'rinadi.
* **Harakat paytida eshik va tortmalar bir-biridan o'tishi mumkin** — kaskad
  faqat ichki mexanizmni keyinga suradi (§7). 460 faylning 70 tasida harakat
  paytida kesishgan juftlar bor (tugal holatlarda yo'q): asosan surma (kupe)
  eshiklar va ularning profillari (285 juft), burilib ochiladigan qo'shni fasadlar
  (30 juft, 21 fayl).
* **Ayirish (`1004`) natijasi emas, birinchi jism butunligicha** chiziladi —
  duxovka korpusining ichki kemtigi ko'rinmaydi (CSG yo'q).
* **Tekstura Bazisdagidan farq qiladi:** naqsh har panelda boshqa joydan
  boshlanadi, tayl chegarasi ko'zgu bilan ulanadi, rasm nisbati saqlanadi (§7) —
  maqsad realizm, Bazis eskiziga piksel-piksel moslik emas. Stoleshnitsa taylini
  (600 x 3000) Bazis yotiq rasmga qanday qo'yishi tekshirilmagan (~180 panel);
  bu yerda rasmning uzun tomoni 3000 mm. 562 fasaddagi `Plastics` bo'yoq qatlami
  (`RAL 9001`) hisobga olinmaydi.
* **Gabarit o'lchami qutining o'zini o'lchaydi** — L/U oshxonada ham qiymat
  umumiy eni/chuqurligi; har qatorning (devor bo'ylab) alohida uzunligi
  ko'rsatilmaydi. Oshxona rejalovchilarida (Mozaik, Bazis Salon) bu reja va
  yoyilma ko'rinishida — bizda hali yo'q.
* **Boshlang'ich kamera doim +X+Z burchakda** — mahsulotning old tomoni
  qayerdaligi aniqlanmaydi. 22 namunadan bittasida (`3-Garderob`, kiyinish
  xonasi: eshiklar ichkariga, asosan −X ga ochiladi) sahifa, mahsulot kartochkasi
  rasmi ham, orqa tomonni ko'rsatadi. Ochilish yo'nalishidan old tomonni topish
  mumkin, lekin surma eshik yon tomonga suriladi va bu o'lchovni buzadi — hali
  qilinmagan.
* **Kromka umuman ko'rsatilmaydi** — na 3D da, na detal kartochkasida.
  Ataylab: u chekda bor va detal sexdan kromkalangan holda keladi.
* `Anim.Duration` o'qilmaydi — sahifa harakatni o'z tezligida (460 ms) o'ynatadi.
* Ikki bo'lakli panelning ikkinchi bo'lagi chizilmaydi (41 305 panelda bitta) —
  texnolog "kontur to'liq o'qilmadi" ogohlantirishini ko'radi.
* Ochiq sahifa ishlab chiqarish holatini KO'RSATMAYDI. Ataylab: havolani mijoz
  ham ochadi, unga sexning ichki holati kerak emas.
