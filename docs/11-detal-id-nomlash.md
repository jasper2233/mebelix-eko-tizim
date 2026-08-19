# Detal ID nomlash qoidasi

Chekdagi yozuv, QR mazmuni, SCX fayl nomi, bazadagi `qr_text` va barcha UI
sahifalar — **hammasi bitta satr**. Bu Nanxing skan mosligi (skaner o'qigan
matn = fayl nomi) va operator adashmasligi uchun qat'iy qoida.

Bitta istisno: chekdagi odam o'qiydigan matn qatori 20 belgiga qisqartiriladi
(`labels.py` — `d.qr_text[:20]`); QR, SCX nomi va baza (`String(120)`) esa
to'liq satrni saqlaydi. Oddiy raqamli kodlarda farq sezilmaydi.

## Tuzilishi

```
{mahsulotKodi}_{detalKodi}[-N][_n]
   100701        03_002    -2   _1
```

| Qism | Qayerdan | Ma'nosi |
| --- | --- | --- |
| `100701` | .project dagi mahsulot `code` (bo'lmasa `name`, u ham bo'lmasa `PRODUCT`) | buyurtma ichidagi mahsulot (masalan 1007-buyurtma, 01-shkaf) |
| `03_002` | .project dagi detal `code` (GibLab sxemasi `{blok}_{tovar}`); faylda kod bo'lmasa parser tartib raqami beradi (`001`, `002`, ...) va ogohlantiradi | detal turi |
| `-2` | parser qo'shadi (`_dedupe_part_code`) | fayl NUQSONI belgisi: bitta mahsulotda IKKI detal bir xil kod bilan kelgan — ikkinchisi `-2` (uchinchisi `-3`, ...). Bu BOSHQA detal, nusxa emas: odatda ko'zgu juftlik (chap/o'ng bok — teshiklari qarama-qarshi) yoki kromka tomoni farqli juftlik |
| `_n` | ingest (`ParsedPart.qr_texts`) | nusxa raqami — FAQAT detal 1 dan ko'p nusxada bo'lsa (`_1.._count`). Yagona nusxada suffiks YO'Q |

## Misollar

| ID | O'qilishi |
| --- | --- |
| `100701_03_002` | yagona nusxa — suffikssiz |
| `100701_03_002-2` | fayl ichida kodi takrorlangan IKKINCHI detal (masalan o'ng bok), yagona nusxa |
| `100701_01_012_2` | `01_012` detalining 2-nusxasi (jami 3 ta bo'lsa `_1 _2 _3`) |
| `100701_01_010-2_1` | takror kodli ikkinchi detal, 1-nusxasi — ikkala suffiks birga kelishi normal |

## Qat'iy farq: `-` va `_`

- `-N` — **kod to'qnashuvi** (boshqa detal). Manba: dizayner GibLab'da bitta
  kodni ikki detalga bergan. Yuklashda ogohlantirish chiqadi
  ("Detal kodi takrorlangan: ..."). Ildiz yechim — GibLab'da har detalga o'z kodi.
- `_n` — **nusxa raqami** (o'sha detalning jismoniy donasi).
- `-2` ni `_2` qilib bo'lmaydi: `100701_01_010_2` "2-nusxa"mi yoki "2-detal"mi —
  ajratib bo'lmay qoladi, baza unique indeksi ham to'qnashadi.

## Himoya tekshiruvlari

- **Yo'l belgilariga taqiq**: detal yoki mahsulot kodida `\`, `/` yoki `..`
  bo'lsa parse `ParseError` bilan to'xtaydi ("... taqiqlangan belgi") — ID SCX
  fayl nomiga aylanadi, uploads tashqarisiga yozib bo'lmasin (`parser.py`).
- **ID to'qnashuvini oldindan aniqlash**: ikki HAR XIL detal bir xil QR bersa
  (masalan `010` kodli 2 nusxa va `010_2` kodli detal), ingest unique-indeks
  500 xatosi o'rniga do'stona `ParseError` beradi: "Detal ID to'qnashuvi: ..."
  (`ingest.py ingest_project`).
- **Skan format darvozasi**: `scanning.py` dagi `_QR_RE = ^.+_.+$` — kamida
  bitta `_` bo'lmagan QR bazaga murojaatdan oldin `E002` bilan rad etiladi.

## Qoida qo'llanadigan joylar (hammasida aynan bir satr)

| Joy | Manba kod |
| --- | --- |
| Bazadagi `part_instance.qr_text` | `ingest.py` (`ParsedPart.qr_texts`), matritsada son o'zgarsa `orders.py _resize_instances` |
| Chekdagi matn qatori va QR | `services/labels.py` (`qr_text`; `qr_part_code` — `scanning.py` dan import) |
| SCX fayl nomi va ichidagi Panel ID | `services/giblab/scx.py` (`build_scx_files`; nomlar ingestda parser bergan `qr_texts`dan, qayta yaratishda bazadagi QR'lardan) |
| Skan tekshiruvi | `services/scanning.py` (aynan moslik + eski `_1` yorliqlar uchun fallback); `api/routes/terminal.py` (`resolve_terminal_qr` — o'sha fallbackning ikkinchi nusxasi); `api/routes/pachka.py` (qadoqqa skan — FAQAT aynan moslik, fallback yo'q) |
| Terminal UI (banner, tarix, arra, kromka, prisadka) | `qr_text` to'g'ridan ko'rsatiladi, qismlarga ajratilmaydi; yagona istisno — `KromkaView` skan matnidan oxirgi `_1` ni kesib ham sinaydi (backend fallbackining frontend nusxasi) |

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
bazadagi QR'lardan qayta quradi (`orders.py regenerate_order_scx`, ingest
bilan umumiy `write_and_register_scx` helperi orqali).

## Merge qilinmasligi haqida

Ba'zi `-2` juftliklar hamma jihatdan bir xil bo'lishi mumkin (teshigi ham).
Ular ataylab birlashtirilmaydi: har qatorning o'z `label_num`i (kesish
xaritasidagi katak raqami) bor — birlashtirsak chekdagi `N` raqami xarita
bilan mos kelmay arrachi adashadi. Fayl nima bersa — tizim shuni aks ettiradi.
