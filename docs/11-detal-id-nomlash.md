# Detal ID nomlash qoidasi

Chekdagi yozuv, QR mazmuni, SCX fayl nomi, bazadagi `qr_text` va barcha UI
sahifalar — **hammasi bitta satr**. Bu Nanxing skan mosligi (skaner o'qigan
matn = fayl nomi) va operator adashmasligi uchun qat'iy qoida.

## Tuzilishi

```
{mahsulotKodi}_{detalKodi}[-N][_n]
   100701        03_002    -2   _1
```

| Qism | Qayerdan | Ma'nosi |
| --- | --- | --- |
| `100701` | .project dagi mahsulot `code` | buyurtma ichidagi mahsulot (masalan 1007-buyurtma, 01-shkaf) |
| `03_002` | .project dagi detal `code` (GibLab sxemasi `{blok}_{pozitsiya}`) | detal turi |
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

## Qoida qo'llanadigan joylar (hammasida aynan bir satr)

| Joy | Manba kod |
| --- | --- |
| Bazadagi `part_instance.qr_text` | `ingest.py` (`ParsedPart.qr_texts`), matritsada son o'zgarsa `orders.py _resize_instances` |
| Chekdagi matn qatori va QR | `services/labels.py` (`qr_text` / `qr_part_code`) |
| SCX fayl nomi va ichidagi Panel ID | `services/giblab/scx.py` (`build_scx_files`, nomlar bazadagi QR'lardan) |
| Skan tekshiruvi | `services/scanning.py` (aynan moslik; eski `_1` yorliqlar uchun fallback) |
| Terminal UI (banner, tarix, kromka, prisadka) | `qr_text` to'g'ridan ko'rsatiladi, hech qayerda parse qilinmaydi |

Eski konvensiya (2026-08-02 gacha): yagona nusxada ham `_1` yozilardi.
Migratsiya `c9e5b2a41d78` mavjud bazani yangi qoidaga o'tkazgan; o'shagacha
chop etilgan `_1` li yorliqlarni skan qilish fallback bilan ishlayveradi.

## Merge qilinmasligi haqida

Ba'zi `-2` juftliklar hamma jihatdan bir xil bo'lishi mumkin (teshigi ham).
Ular ataylab birlashtirilmaydi: har qatorning o'z `label_num`i (kesish
xaritasidagi katak raqami) bor — birlashtirsak chekdagi `N` raqami xarita
bilan mos kelmay arrachi adashadi. Fayl nima bersa — tizim shuni aks ettiradi.
