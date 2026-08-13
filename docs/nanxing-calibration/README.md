# Nanxing MH2026 — Face-kod kalibratsiyasi

> **Holat (2026-08-05): bu kalibratsiya ENDI SHART EMAS — arxiv.**
> Face-konvensiya `D:\MebeliX\Scx` korpusidan to'liq keltirildi (87 proyekt,
> 10500 qirra teshigi; commit `a633b28`): `backend/app/services/giblab/scx.py`
> dagi yagona `_EDGE_FACE = {l→4, r→3, t→1, b→2}` jadvali qirra teshigi uchun
> ham, kromka lenta uchun ham ishlaydi; to'rttala tomon korpus-tasdiqli
> (qarshi ovoz <0.5%). Eksport GibLab'niki bilan semantik bir xil — tsexdagi
> Nanxing shu formatni qabul qiladi. Eski `_EDGE_BORE_FACE`/`_EDGE_BAND_FACE`
> jadvallari o'chirilgan (qiymatlar ham o'zgargan: r 2→3, b 3→2).

Tarix: stanok `100701_02_003` faylida qirra teshiklarini (`Face="2"`)
**HolePositionWrong** deb rad etgan va H.Hole yuzasini "Upper" deb ko'rsatgan
edi — o'shanda faqat `l→4` korpus-tasdiqli bo'lib, qolganlarini shu kit bilan
aniqlash mo'ljallangan edi. Muammo korpus-konvensiyaga o'tish bilan hal bo'ldi;
protsedura quyida faqat stanok yana e'tiroz bildirsa kerak bo'ladi.

## Qanday o'tkaziladi (stanok yana e'tiroz bildirsagina, ~5 daqiqa)

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

4. Natijani Claude'ga yuboring — `_EDGE_FACE` jadvali
   (`backend/app/services/giblab/scx.py`) bir tuzatishda to'g'irlanadi va
   SCX'lar buyurtma sahifasidagi "Qayta yaratish" tugmasi
   (`POST /orders/{id}/scx/regenerate`) bilan yangilanadi.

Eslatma: panel 400×300×16. d5 teshik dastur koordinatasida "pos=100" nuqtada —
qirraning qaysi uchidan 100 mm ekani ham muhim (boshidanmi/oxiridanmi deb yozing).

## Kit fayllari joriy generatordan farqi

- FACE_*.scx fayllar joriy generator chiqishiga to'liq mos emas: generator endi
  har `Machining`ga ketma-ket ID (1000+) va `IsGenCode="2"`, `Panel`ga esa
  `MachiningPoint="1"` qo'shadi — kit fayllarida bular yo'q. Kit qayta
  yaratilsa yoki generator chiqishi bilan solishtirilsa shuni hisobga oling.
- Kit d5 zondni Face'dan qat'i nazar X=100 Y=100 ga qo'yadi; joriy generator
  esa qirra teshigi koordinatalarini boshqacha hisoblaydi: l/r → X=0/Length,
  Y=Width−pos; t → X=pos, Y=Width; b → X=pos, Y=0 (`scx.py`). Ya'ni kit
  fayllar real generator koordinatalarini illyustratsiya qilmaydi.
