# Detal ID nomlash qoidasi

Chekdagi yozuv, QR mazmuni, SCX fayl nomi va bazadagi `qr_text` — **hammasi
bitta satr**. Bu Nanxing skan mosligi (skaner o'qigan matn = fayl nomi) va
operator adashmasligi uchun qat'iy qoida. UI sahifalarning ko'pi ham shu satrni
ko'rsatadi, lekin HAMMASI emas: KROMKA/PRISADKA jadvallarining «Kod» ustuni,
UPAKOVKA dagi ochiq qadoq ro'yxati, navbatdagi yig'ma bog'lami va WS orqali
kelgan begona skan banneri `_n` SIZ detal kalitini
(`{mahsulotKodi}_{detalKodi}`) chiqaradi — to'liq sanog'i «Qoida qo'llanadigan
joylar» bo'limida. Bu kalitning sxema maydoni har joyda bir xil atalmaydi:
KROMKA/PRISADKA jadvallarida `code`, qolganlarida `part_code`.

Satrning o'zi bitta joyda qisqaradi: chekdagi odam o'qiydigan matn qatori 20 belgiga
(`labels.py` — `d.qr_text[:20]`); QR, SCX nomi va baza (`String(120)`) esa
to'liq satrni saqlaydi. Oddiy raqamli kodlarda farq sezilmaydi.

## Tuzilishi

```
{mahsulotKodi}_{detalKodi}[-N][_n]
   100701        03_002    -2   _1
```

| Qism | Qayerdan | Ma'nosi |
| --- | --- | --- |
| `100701` | .project dagi mahsulot `code` (bo'lmasa `name`, u ham bo'lmasa `PRODUCT`); 50 belgidan uzun bo'lsa `ParseError` — `Product.code` ustuni `VARCHAR(50)` | buyurtma ichidagi mahsulot (masalan 1007-buyurtma, 01-shkaf) |
| `03_002` | .project dagi detal `code`, u bo'lmasa `part.code` atributi (GibLab sxemasi `{blok}_{part.position}` — `parser.py` izohi; namunaviy 5 faylda o'lchandi 2026-08-29: kodli 582 detalning 539 tasida oxirgi bo'lak aynan `part.position`. DIQQAT: `c9e5b2a41d78` migratsiyasining izohi buni `{blok}_{tovar}` deydi — o'sha izoh eskirgan, prod migratsiyasi tahrirlanmaydi); ikkalasi ham bo'lmasa parser tartib raqami beradi (`001`, `002`, ...) — ogohlantirish esa FAQAT mahsulotning BIRINCHI detali kodsiz bo'lganda chiqadi, o'rtadagi kodsiz detal jimgina raqamlanadi | detal turi |
| `-2` | parser qo'shadi (`_dedupe_part_code`) | bir xil mahsulot KODI ichida IKKI detal bir xil kod bilan kelgan — ikkinchisi `-2` (uchinchisi `-3`, ...). `seen` to'plami `product.code` bo'yicha, ya'ni kodi bir xil ikki alohida `<good>` ham bitta to'plamni bo'lishadi. Bu BOSHQA detal, nusxa emas: odatda ko'zgu juftlik (chap/o'ng bok — teshiklari qarama-qarshi) yoki kromka tomoni farqli juftlik |
| `_n` | ingest (`ParsedPart.qr_texts`) | nusxa raqami — FAQAT detal 1 dan ko'p nusxada bo'lsa (`_1.._count`). Yagona nusxada suffiks YO'Q |

## Misollar

| ID | O'qilishi |
| --- | --- |
| `100701_03_002` | yagona nusxa — suffikssiz |
| `100701_03_002-2` | kodi to'qnashgan IKKINCHI detal (masalan o'ng bok), yagona nusxa |
| `100701_01_012_2` | `01_012` detalining 2-nusxasi (jami 3 ta bo'lsa `_1 _2 _3`) |
| `100701_01_010-2_1` | takror kodli ikkinchi detal, 1-nusxasi — ikkala suffiks birga kelishi normal |

## Qat'iy farq: `-` va `_`

- `-N` — **kod to'qnashuvi** (boshqa detal). Ikki manbasi bor: (a) dizayner
  GibLab'da bitta kodni ikki detalga bergan; (b) uni parserning O'ZI hosil
  qilgan — kodsiz detalga beriladigan tartib raqami (`len(product.parts)+1`)
  dizayner bergan HAQIQIY kod bilan to'qnashsa. Ya'ni faylda takror kod
  ko'rinmasligi ham mumkin: `002` kodli birinchi va kodsiz ikkinchi detal
  `100701_002` va `100701_002-2` beradi. Ikkala holda ham yuklashda
  ogohlantirish chiqadi ("Detal kodi takrorlangan: ...") — texnolog GibLab'dan
  takror kod qidirishdan oldin ikkinchi detalda kod BOR-YO'QLIGINI tekshirsin.
  Ildiz yechim — GibLab'da har detalga o'z kodi.
- `_n` — **nusxa raqami** (o'sha detalning jismoniy donasi).
- `-2` ni `_2` qilib bo'lmaydi: `100701_01_010_2` "2-nusxa"mi yoki "2-detal"mi —
  ajratib bo'lmay qoladi, baza unique indeksi ham to'qnashadi.

## Nusxalar kesish xaritasida

Har nusxa xaritada **alohida katak** — jismonan ular listning turli joyida
kesiladi. Katak bog'lanishi `PartInstance.pattern_no` + `cell_index` da
saqlanadi, ya'ni `_1` aynan bitta katakka tegishli. Bog'lanish FAQAT ingestda,
kesish xaritasidan o'rnatiladi (`cutmap.py` → `InstanceCell` → `ingest.py`):
texnolog matritsada sonni KEYIN oshirsa, `orders/matrix.py _resize_instances`
yangi nusxani bog'lanishSIZ qo'shadi (`pattern_no`/`cell_index` = `None`) va
mavjudlarinikini qayta hisoblamaydi. Bunday nusxa xaritada umuman ko'rinmaydi
(`CutmapView` `pattern_no == null` bo'lganini o'tkazib yuboradi), demak uning
chekini xaritadan chiqarib ham bo'lmaydi. Nusxalar `№` (`label_num`)
ni BO'LISHADI — u detalning xaritadagi raqami, nusxaniki emas; farq faqat QR
suffiksida. Buni `-2` bilan chalkashtirmaslik kerak: u boshqa detal qatori,
o'z `label_num`i bilan (shuning uchun ular birlashtirilmaydi — birlashsa
chekdagi `N` xarita bilan mos kelmay arrachi adashadi).

Bir naqsh bir necha marta kesilsa (`sheet.mult > 1`) katakdagi nusxa soni
`mult` ga teng bo'ladi; frontend naqshni alohida list kartalariga yoyib har
kartaga bitta nusxani beradi (`CutmapView` → `slice(k, k+1)`). Natijada
**ekranda har katak = bitta jismoniy detal = bitta chek** — `PartCard` ham shu
sababli bitta chek ID si va bitta bekor qilish tugmasini ko'rsatadi
(`docs/06` → «Nega bitta chek, ro'yxat emas»). Prodda o'lchangan (2026-08-28):
2601 katakda `nusxa == mult`, istisno yo'q.

## Himoya tekshiruvlari

- **Yo'l belgilariga taqiq**: detal yoki mahsulot kodida `\`, `/` yoki `..`
  bo'lsa parse `ParseError` bilan to'xtaydi ("... taqiqlangan belgi") — ID SCX
  fayl nomiga aylanadi, uploads tashqarisiga yozib bo'lmasin (`parser.py`).
- **Mahsulot kodi uzunligi**: nom-zaxirasi ishlaganda kod 50 belgidan oshishi mumkin;
  `parser.py` uni yozishdan OLDIN tekshiradi ("Mahsulot kodi juda uzun ..."), aks holda
  `VARCHAR(50)` ustuni ingest paytida 500 berardi.
- **ID to'qnashuvini oldindan aniqlash**: ikki HAR XIL detal bir xil QR bersa
  (masalan `010` kodli 2 nusxa va `010_2` kodli detal), ingest unique-indeks
  500 xatosi o'rniga do'stona `ParseError` beradi: "Detal ID to'qnashuvi: ..."
  (`ingest.py ingest_project`). AYNAN shu tekshiruv matritsa yo'lida ham bor:
  `_resize_instances` yangi QR'larni yozishdan OLDIN buyurtmadagi BOSHQA
  detallarning tirik `qr_text` larini o'qiydi va to'qnashsa 422 beradi
  (`orders/matrix.py`) — son o'zgarishi ham xuddi shu juftlikni yasashi mumkin.
- **Buyurtmalararo to'qnashuv — faqat SKANDA ushlanadi**: QR buyurtmaga
  bog'lanmagan va yagona indeks `(order_id, qr_text)` bo'yicha, ya'ni bir xil
  GibLab kodlaridan yig'ilgan IKKI jonli buyurtma bitta QR ni ulashishi mumkin
  (ingest tekshiruvi faqat BITTA buyurtma ichida ishlaydi). `record_scan_at`
  mos keluvchi jonli qatorlarni oladi: PRODUCTION qatorlar birdan ko'p bo'lsa `E001`
  (CANCELLED faqat E003 xabari uchun — qayta yaratilgan buyurtma to'qnashuv emas) — "Bu
  QR bir nechta buyurtmada uchradi — managerga murojaat qiling". Ilgari
  `ORDER BY order.id DESC` bilan jimgina eng yangi buyurtmaga yozilardi. Bu
  himoya faqat skan dvijokida: `terminal.py resolve_terminal_qr` hali ham eng
  yangisini tanlaydi, chek esa buyurtma raqamini chizmaydi (`labels.py` —
  `LabelData` da `order_number` yo'q), shuning uchun operator faqat xato
  xabaridan biladi. To'liq yechim — QR ni buyurtma bilan prefikslash — SCX
  fayllarini qayta yaratish va chop etilgan cheklarni bekor qilishni talab
  qiladi, ataylab qilinmagan.
- **Skan format darvozasi**: `scanning.py` dagi `_QR_RE = ^.+_.+$` — kamida
  bitta `_` bo'lmagan QR bazaga murojaatdan oldin `E002` bilan rad etiladi.
  Shu sababli detal ID sidan ATAYLAB farqli prefiksli ikki QR turi bor:
  `ATX-{buyurtma}-{n}` (foydali qoldiq cheki) va `PK-{buyurtma}-{NN}` (qadoq
  kodi). Lekin ular darvozadan TURLICHA chetlanadi:
  - `ATX-` ni `POST /scans` ning O'ZI dvijokdan oldin ushlaydi (`scans.py` —
    `record_scan` chaqirilishidan avval), xato o'rniga `ATX` kodli ma'lumot
    qaytaradi.
  - `PK-` uchun `/scans` da bunday darvoza YO'Q. U faqat uch yo'lda dvijokka
    tushmaydi: TMO qabuli (`tmo.py` — qadoqni ochib ichidagi hamma nusxani
    bitta skanda qabul qiladi), stanok skan forvardi (`bridge_agents.py`
    ikkala prefiksni ham `SKIP` bilan jimgina chetlab o'tadi, aks holda butun
    chek "QR formati buzuq" berardi) va terminalda UPAKOVKA/TMO ekranining o'z
    sinki (`useTerminalScan` — `viewScanRef`). Boshqa post ekranida (ARRA,
    BOYOQ, ...) `viewScanRef` bo'sh: qadoq QR'i umumiy yo'ldan `/scans` ga
    ketadi va `_QR_RE` da `E002` oladi. Ya'ni `PK-` himoyasi marshrutlash
    bilan qilingan, dvijok darvozasi bilan emas.

## Qoida qo'llanadigan joylar (va uchraydigan istisnolar)

| Joy | Manba kod |
| --- | --- |
| Bazadagi `part_instance.qr_text` | `ingest.py` (`ParsedPart.qr_texts` — property `giblab/models.py` da), matritsada son o'zgarsa `orders/matrix.py _resize_instances` (o'sha PATCH ichida SCX fayllari ham `ingest.rebuild_order_scx` bilan qayta yaratiladi — nom QR bilan mos qolsin) |
| Chekdagi matn qatori va QR | `services/labels.py` (`qr_text`; `qr_part_code` — `scanning.py` dan import) |
| SCX fayl nomi va ichidagi Panel ID | `services/giblab/scx.py` (`build_scx_files`; nomlar ingestda parser bergan `qr_texts`dan, qayta yaratishda bazadagi QR'lardan) |
| Skan tekshiruvi | `services/scanning.py` (aynan moslik + eski `_1` yorliqlar uchun fallback); `api/routes/terminal.py` (`resolve_terminal_qr` — o'sha fallbackning ikkinchi nusxasi); `api/routes/pachka.py` (qadoqqa skan — FAQAT aynan moslik, fallback yo'q) |
| Terminal UI (banner, navbat, arra, kromka, prisadka, TMO) | Asosan `qr_text` to'g'ridan ko'rsatiladi, qismlarga ajratilmaydi: ARRA (`PartCard`), navbat (`PostQueueView`), TMO (`TmoView`), PRISADKA nusxa chiplari, `KromkaView` ning «Jarayonda» paneli va O'Z skani banneri (`terminal.tsx` — `code: r.qr_text`). To'rt istisno: (a) KROMKA va PRISADKA jadvallarining «Kod» ustuni backend qurgan `{product_code}_{part.code}` ni, ya'ni `_n` SIZ satrni chiqaradi (sxema maydoni `code`, `terminal.py`) — `KromkaView` nusxalarida esa faqat `№{instance_no}`, `qr_text` `title=` tooltipida qoladi; (b) WS orqali kelgan BEGONA skan bannerida `part_code` chiqadi (`terminal.tsx` — `code: String(p.part_code ?? "")`); (c) `KromkaView` skan matnidan oxirgi `_1` ni kesib ham sinaydi (backend fallbackining frontend nusxasi); (d) navbatdagi YIG'MA bog'lami — detal ostidagi `+ ...` qatori bolalar detallarini `{product_code}_{child.code} ×{count}` deb yozadi, ya'ni yana `_n` SIZ kalit (`terminal.py` `PostQueueRow.assembly` → `PostQueueView`) |
| Terminal UI (upakovka) | Ochiq qadoq ichidagi ro'yxat `part_code` ni (`pachka.py` — `f"{product_code}_{part.code}"`, `_n` SIZ), «Qadoqlanmagan» ro'yxati esa `qr_text` ni ko'rsatadi — bitta ekranda ikki xil satr. Skan esa aynan `qr_text` ni kutadi (fallback yo'q) |

Eski konvensiya (2026-08-02 gacha): yagona nusxada ham `_1` yozilardi.
Migratsiya `c9e5b2a41d78` mavjud bazani yangi qoidaga o'tkazgan; o'shagacha
chop etilgan `_1` li yorliqlarni skan qilish fallback bilan ishlayveradi —
lekin faqat post skani (`scanning.py`) va terminal QR qidiruvida
(`terminal.py`). Qadoqqa skanda (`pachka.py`) fallback yo'q: nusxani o'zi
aynan moslik bilan qidiradi va topolmay `E001` ("Bunday QR topilmadi") beradi,
ya'ni dvijokdagi fallbackka gal ham tegmaydi. Eski `_1` li yorliq boshqa
postlarda skan bo'lsa ham upakovkada o'tmaydi — chekni qayta chop etish kerak.

Eski buyurtmalarning SCX fayllarini yangi nomlarga o'tkazish uchun
`POST /orders/{order_id}/scx/regenerate` (texnolog huquqi) bor — fayllarni
bazadagi QR'lardan qayta quradi (`orders/files.py regenerate_order_scx` yupqa
qobiq, ish `giblab/ingest.py rebuild_order_scx` da). Matritsada detal soni
o'zgarganda `PATCH /orders/{id}/matrix` o'sha helperni O'ZI chaqiradi, ya'ni
yangi nusxa fayli darhol paydo bo'ladi va texnolog qo'lda qayta yaratishi shart
emas; `.project` diskda bo'lmasa qayta yaratish jim o'tkazib yuboriladi.

## Merge qilinmasligi haqida

Ba'zi `-2` juftliklar hamma jihatdan bir xil bo'lishi mumkin (teshigi ham).
Ular ataylab birlashtirilmaydi: har qatorning o'z `label_num`i (kesish
xaritasidagi katak raqami) bor — birlashtirsak chekdagi `N` raqami xarita
bilan mos kelmay arrachi adashadi. Fayl nima bersa — tizim shuni aks ettiradi.
