# Nanxing MH2026 — Face-kod kalibratsiyasi

Stanok `100701_02_003` faylida qirra teshiklarini (`Face="2"`) **HolePositionWrong**
deb rad etdi va H.Hole yuzasini "Upper" deb ko'rsatdi — demak bizning yon (Face)
kodlarimiz MH2026 talqiniga mos emas. `scx.py` dagi jadvalda faqat `l→4`
korpus-tasdiqli edi; qolganlari shu kit bilan aniqlanadi.

## Qanday o'tkaziladi (stanokda ~5 daqiqa)

1. Shu papkadagi `FACE_1.scx` … `FACE_6.scx` fayllarni stanok o'qiydigan papkaga
   ko'chiring.
2. MH2026 dasturida har birini birma-bir oching. Har faylda:
   - katta **d15 vertikal teshik** — panelning **chap-yuqori** burchagida
     (orientatsiya belgisi, X=50 Y=250);
   - bitta **d5 gorizontal teshik** (chuqurlik 20, balandlik Z=8) — biz
     tekshirayotgan Face qiymati.
3. Jadvalni to'ldiring — d5 teshik **qaysi qirrada** ko'rindi (yoki xato):

| Fayl   | Face | Ko'ringan qirra (chap/o'ng/old/orqa) yoki XATO |
|--------|------|-----------------------------------------------|
| FACE_1 | 1    |                                               |
| FACE_2 | 2    |                                               |
| FACE_3 | 3    |                                               |
| FACE_4 | 4    |                                               |
| FACE_5 | 5    | (V-teshik yuzasi — Upper/Back deb yozing)     |
| FACE_6 | 6    |                                               |

4. Natijani Claude'ga yuboring — `_EDGE_BORE_FACE` jadvali bir tuzatishda
   to'g'irlanadi va SCX'lar "Qayta yaratish" tugmasi bilan yangilanadi.

Eslatma: panel 400×300×16. d5 teshik dastur koordinatasida "pos=100" nuqtada —
qirraning qaysi uchidan 100 mm ekani ham muhim (boshidanmi/oxiridanmi deb yozing).
