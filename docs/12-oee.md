# 12 — OEE (Prisadka): holat, bajarilgan ishlar va reja

Holat: **2026-09-19**. OEE'ning uchala qismi ham hisoblanadi (Availability, Performance,
Quality) va hisobotda `A × P × Q` raqami chiqadi — lekin qiymatlar ma'lumot qamroviga va
TAXMINIY koeffitsiyentlarga bog'liq (§5, §4.6). Bu hujjat poydevor qayerda turganini,
prod ma'lumoti nimani ko'rsatganini va keyingi qadamlarni yozadi.

## 1. OEE nima va har qismi qayerdan olinadi

```
Reja vaqti   = smena vaqti − tanaffuslar − rejali to'xtashlar   (dam olish kunlarida 0)
Availability = ishlagan vaqt ÷ reja vaqti
Performance  = (ideal sikl × detallar soni) ÷ ishlagan vaqt
Quality      = yaroqli detallar ÷ jami detallar
OEE          = Availability × Performance × Quality
```

| Kerak | Manba | Holat |
|---|---|---|
| Smena, tanaffus, dam olish kunlari | Tizim sozlamalari → "Ish jadvali" (§4.1) | ✅ bor |
| Stanok holati va davomiyligi | Pico signal ustuni → `andon_event` (§3.1) | ✅ bor, qamrovi yetarli emas (§5) |
| To'xtash sababi | `downtime` + `downtime_reason`, terminal oynasi (§4.4) | ✅ bor; ro'yxatni admin kiritadi — egasining ro'yxati §4.4 da |
| **Availability hisobi** | `services/availability.py`, Hisobotlar → «Stanok vaqti» (§4.5) | ✅ bor (2026-09-18) |
| Detallar soni | MES skanlari (`scan`) + Pico sikllari | ✅ bor, o'zaro deyarli mos (§5) |
| Ideal sikl vaqti | `part.xnc_summary` (teshik/paz/freza) + koeffitsiyentlar (Tizim sozlamalari, §4.6) | ⚠️ bor, qiymatlar TAXMINIY — sekundomer bilan to'g'rilash kerak |
| **Performance hisobi** | `services/performance.py`, Hisobotlar → «Stanok vaqti» (§4.6) | ✅ bor (2026-09-18), faqat Prisadka |
| Brak | `part_defect` — terminal skan tasmasidagi BRAK tugmasi (§4.7) | ✅ bor (2026-09-19); qayta ishlab chiqarish (remake) YO'Q |
| **Quality hisobi** | `services/performance.py: quality_pct`, Hisobotlar → «Stanok vaqti» (§4.7) | ✅ bor (2026-09-19) |
| **OEE = A × P × Q** | `services/performance.py: oee_pct`, o'sha hisobot ustuni (§4.7) | ✅ bor (2026-09-19) |

## 2. Tarix

- **2026-08-21** — birinchi OEE moduli qurildi (qo'lda "To'xtash"/"Brak" tugmalari, ish markazida
  `planned_minutes_per_day`/`ideal_rate`, `stop_reason`/`machine_stop`/`defect` jadvallari) va o'sha
  kuni **qaytarildi** (`066cd22`): 1366×768 monoblokda terminal ustuniga tugmalar sig'madi, egasi
  "hozircha kerak emas" dedi. Migratsiyalari prodda qolgan, jadvallar `LEGACY_TABLES`/`LEGACY_COLUMNS`
  da (docs/04 §4.4). **Xulosa: operator ekraniga DOIMIY tugma qo'shilmaydi** — sabab va brakni smenadagi hodim kerak paytda chiqadigan oynada kiritadi (§7).
- **2026-09-13..14** — andon: Pico stanok chiroqlarini o'qiydi, MES agent v1.5.0 USB orqali olib
  `POST /bridge-agents/andon` ga yuboradi → `andon_event` (xom hodisalar) + Redis jonli holat;
  "Ish markazlari" sahifasida jonli holat, "Hisobotlar → Stanok vaqti" (2026-09-18 dan Availability bilan, §4.5).
- **2026-09-16** — prod ma'lumot auditi (§5) va ish jadvali sozlamalari (§4.1).

## 3. Ma'lumot manbalari

### 3.1 Pico signal ustuni

Firmware alohida repoda: `jasper2233/prisadka-mes-nanxing` (asosiy hujjati `docs/tz.md`,
mantiq `firmware/fsm.py`). Pico chiroqlarni optopara orqali o'qiydi, stanok boshqaruviga aralashmaydi.

| Chiroq | Holat | Izoh |
|---|---|---|
| Qizil (yoniq yoki miltillash) | `FAULT` | Avariya — to'xtash yozuvi ochiladi |
| Yashil miltillash | `AWAIT_PART` | QR skanerlandi, detal kutilmoqda |
| Yashil doimiy | `PROCESSING` | Ishlov |
| Sariq | `IDLE` | Kutish |
| Sariq, limitdan uzoq | `STOPPED` | Uzoq kutish — to'xtash yozuvi ochiladi |
| Hammasi o'chiq (5 s) | `OFF` | Stanok o'chirilgan — to'xtash yozuvi ochiladi |

Prioritet: qizil > yashil > sariq. Hodisalar:

- `state` — `prev_state`, `prev_duration_s` (davomiylikni Pico o'zi o'lchaydi), `lamps`.
  To'xtash ochilganda `downtime_id` (`MACHINE-session-seq`) + `reason_required`, yopilganda
  `closes_downtime_id`; STOPPED → FAULT bitta hodisada ikkalasini olib keladi.
- `cycle` — `wait_s` (skan → ishlov boshlanishi), `process_s` (sof ishlov, avariya vaqti kirmaydi),
  `completed` (`false` — detal ishlovsiz olingan yoki ishlov 5 s dan qisqa), `part_count`
  (Pico qayta yuklanganda nolga tushadi — sanoq qatorlardan olinadi).
- Kalit `(machine_id, session, seq)`: `session` har yuklanishda yangi, takroriy yuborish tashlanadi.

Firmware repodagi eski `PrisadkaMES.exe` prototipida to'xtash sababi ekrani, skan↔sikl FIFO
bog'lash (`mes/bridge.py`) va Telegram xabarlari bor edi. MES agent Pico portini egallash uchun
uni to'xtatadi (`andon-takeover.done`), ya'ni bu funksiyalar hozir ishlamaydi. **Prototipdagi
sabablar ro'yxati boshqa sohadan** (dozalash, nasos, aralashtirgich, retsept) — ishlatilmaydi.

### 3.2 MES ichidagi ma'lumot

- `andon_event` — xom hodisalar (payload to'liq saqlanadi), Redis `mes:andon:live:{machine_id}` — jonli holat.
- `scan` — PRISADKA skanlari; Nanxing skaneri o'qigan QR agent orqali forvard qilinadi.
- `part.xnc_summary` — detal ish hajmi: `bores`, `edge_bores`, `grooves`, `mills`.
- `work_session` — smena (kim ishlayapti).

## 4. Bajarilgan ishlar

### 4.1 Ish jadvali — Tizim sozlamalari (2026-09-16)

Admin panel → **Tizim sozlamalari → "Ish jadvali"**. Hamma ish markaziga umumiy.

- **Smenalar** — 1–4 ta, har biri: nom, boshlanish, tugash (`HH:MM`). Tungi smena (22:00–06:00)
  qo'llab-quvvatlanadi. Yangi smena oldingisi tugagan vaqtdan boshlanadi.
- **Tanaffuslar** — har smenaga 0–10 ta (nom, boshlanish, tugash); yonida "Sof ish vaqti".
- **Haftalik dam olish kunlari** — ISO 1 (dushanba) .. 7 (yakshanba).
- **Bayram va ishlanmaydigan kunlar** — sana + ixtiyoriy nom.
- **Server qoidalari** (`settings_service.schedule_error`): smena boshlanishi ≠ tugashi; smenalar
  sutka aylanasida ustma-ust tushmaydi; tanaffus smena ichida va boshqa tanaffus bilan ustma-ust
  emas; dam olish kuni va sana takrorlanmaydi. Xato adminga o'zbekcha matn bilan chiqadi.

Texnik: `GET/PUT /api/v1/settings/work-schedule` (`AdminUser`, docs/03), `system_setting`
jadvalining `work_schedule` kaliti — JSON (`schemas/settings.py: WorkSchedule`), `value` ustuni
`Text` ga o'tkazildi (migratsiya `c1e8a4b7d9f2`, docs/04). Backendda o'qish — `get_work_schedule(db)`.

Hozircha YO'Q (ataylab): kunga qarab har xil soat (masalan qisqa shanba) va ish markaziga alohida
jadval. Kerak bo'lsa `WorkSchedule` ga qo'shiladi.

### 4.2 Ma'lumot auditi — `scripts/oee_audit.sql` (2026-09-16)

Faqat o'qiydigan SQL (sessiya `default_transaction_read_only`, 60 s chegara), 15 bo'lim:
andon qamrovi, payload maydonlari, sessiyalar va yo'qolgan hodisalar, kechikish/soat farqi,
vaqt izchilligi, kunlik holat soatlari, holat o'tishlari, davomiylik taqsimoti, to'xtash
juftliklari, sikllar, sikl↔skan solishtiruvi, skan↔AWAIT_PART bog'lash, ish kuni chegaralari,
detal ish hajmi, eski OEE jadvallari. Ishga tushirish buyrug'i fayl boshida.

Sintetik Pico ma'lumotida (3 kun, reboot, yo'qolgan hodisa, oflayn bufer) haqiqiy PostgreSQL
bilan tekshirilgan: 24 so'rov xatosiz, 11 ta natija mustaqil hisob bilan mos.

### 4.3 Harakatsizlikdan chiqish va smena yopilishi (2026-09-17)

Muammo: kirish kechgacha ishlab ertasiga ham saqlanib qolardi, odam qayta kirmasdan ishlayverardi;
smena muddatsiz edi, ya'ni skanlar (va OEE bog'lanishi) eski smena egasiga yozilardi.

Qarorlar (egasi bilan): chegara faqat HARAKATSIZLIK — ish jadvali tugashi bilan kesilmaydi (smena
kechroq tugashi mumkin). Tsex (TERMINAL va post rollari) — 90 daqiqa (tushlik 1 soat smenani yopmasin),
ofis (admin, direktor, menejer, texnolog) — 240 daqiqa, TABLO — chiqarilmaydi; ikkalasi Tizim
sozlamalarida. Beyjikli postda chegara oshsa — TO'LIQ chiqish, login sahifasi, qayta kirish beyjik skani.

Faollik: brauzerdagi haqiqiy harakat (bosish, klaviatura, skaner) va shu ish markazidagi skan —
Prisadka operatori Nanxing'da ishlaydi, skan agent orqali keladi. Uch qatlam:

| Qatlam | Qayerda | Nima qiladi |
| --- | --- | --- |
| Brauzer | `hooks/useIdleLogout.ts` | chegara oshsa logout → `/login` (ekran ochiq qolgan bo'lsa ham) |
| Server | `POST /login/refresh` | hisob chegaradan eski bo'lsa refresh rad etiladi |
| Worker | `tasks.close_idle_sessions` (10 daq) | brauzersiz qolgan brigadani yopadi, `ended_at` = oxirgi faollik |

Logout endi qurilma hisobida (TERMINAL / texnik post hisobi) shu hisob ochgan brigadani ham yopadi —
ilgari beyjik bilan ochilgan smena chiqishda yopilmasdi.

### 4.4 To'xtash sabablari (2026-09-17)

§7 qarorlarining kodi. To'xtashlar `andon_event` dan chiqariladi, alohida Pico o'zgarishi kerak emas.

| Qism | Qayerda | Nima qiladi |
| --- | --- | --- |
| Jadvallar | `downtime_reason`, `downtime` (migratsiya `9e4b7c1d2a60`, docs/04) | sabablar ro'yxati; to'xtash: tur, boshlanish/tugash, sabab, izoh, kiritgan hodim |
| Hisob | `services/downtimes.sync_machine` | PRISADKA: qizil (FAULT) va OFF — darhol; sariq (IDLE/STOPPED) — `stop_prompt_idle_minutes` dan uzoq bo'lsa, vaqt sariq yongan paytdan. **KROMKA** (2026-09-20): `uskuna` hodisasi, `holat=0` → `OFF`, unga ham CHEGARA qo'llanadi — lenta detal qo'yish uchun qisqa to'xtaydi va har 40 soniyalik pauzada sabab so'ralsa operator oynani o'qimay yopishga o'rganardi. Qisqa to'xtash HISOBGA baribir kiradi (Availability oraliqlardan), faqat sababi so'ralmaydi. Idempotent, sabab qayta hisobda tegilmaydi |
| Worker | `tasks.sync_downtimes` (5 daq) | terminal yopiq bo'lsa ham to'xtashlar yozilib, yopilib turadi |
| Terminal | `GET /terminal/downtimes/pending` (30 s + `andon.state` WS), `Terminal/DowntimeReason.tsx` | sababsiz to'xtash bo'lsa oyna o'zi chiqadi; faqat Pico ulangan ish markazida (`has_andon`) va smena ochiq bo'lsa; «Keyinroq» — 10 daqiqa |
| Qulf | `POST /terminal/downtimes/lock` | qulf tugmasi avval sabab so'raydi; qulf beyjik bilan ochilganda (`open_badge_session`) yopiladi, uning ostida boshlangan Pico to'xtashi sababni oladi |
| Sozlamalar | Tizim sozlamalari → «To'xtash sabablari» | chegara (sukut 5, 1..120) va IKKI ro'yxat — «Rejali» va «Rejasiz» alohida, har birining o'z qo'shish maydoni: nom, «Izoh majburiy», «Faol», narigi guruhga o'tkazish (o'chirish yo'q) |

Faqat SHU SMENAGA tegishli to'xtash so'raladi (oldingi smenaniki sababsiz qoladi). Ro'yxat bo'sh
bo'lsa hech narsa so'ralmaydi, qulf sababsiz qulflanadi — ro'yxat kiritilmagani ishni to'smaydi.
Tekshiruv: bir martalik PGlite skripti (repoda saqlanmaydi) 22/22 — takrorlanmaslik, 12 soatlik
oynadan uzun to'xtash, IDLE hodisasi yo'qolib STOPPED birinchi kelgani, sessiya almashishi, chegara, qulfdan sabab
ko'chishi, smena filtri; brauzerda soxta API bilan terminal va sozlamalar oqimi.

Egasining ro'yxati (`oee to'xtalishlar.xlsx`, `Лист1` B4:C13; imlo to'g'rilangan, tartib faylnikidek):
- Rejali: Tushlik, Smena yo'q, Tanaffus, Majlis, Kofe tanaffusi, Tozalash, Arra almashtirish, Moylash,
  Sozlash, Sifat nazorati.
- Rejasiz: Elektr yo'q, Remont, Nosozlik, Avariya holati, Hojatxona, Operator yo'q, Buyurtma yo'q,
  Mahsulot yo'q, Mahsulot brak, Yangi buyurtmani olib kelish.
«Izoh majburiy» egasi belgilamagan. Ro'yxat kodga YOZILMAYDI (statik bo'lib qolmasin, 2026-09-18):
admin uni Tizim sozlamalarida shu ikki guruhga kiritadi va keyin o'zi yuritadi.

Kromka to'xtashlari tekshiruvi (bir martalik skript, haqiqiy Postgres): **15/15** — 2 daqiqalik
to'xtash yozilmaydi, 1 soatlik yoziladi (`OFF`), tugash vaqti to'g'ri, qayta hisobda yangi yozuv
chiqmaydi, ochiq to'xtash ochiq qoladi; sabab kiritilgach hisobotda REJALI bo'lib reja vaqtidan
chiqadi va taqsimotda o'z qatori bilan ko'rinadi.

Hali yo'q: sababni holatga (qizil/sariq) bog'lash. Ish vaqtidan tashqaridagi OFF ni avtomat «Smena tugadi»
qilish KERAK BO'LMADI — hisobot uni ish jadvali bilan o'zi kesadi (§4.5).

### 4.5 Availability hisoboti (2026-09-18)

OEE'ning birinchi hisoblangan qismi. Alohida endpoint EMAS — `GET /reports/machine-time` kengaytirildi
(Hisobotlar → «Stanok vaqti»; Excel eksport o'sha yo'ldan), hisob `services/availability.py` dagi sof funksiyalarda.

```
ish vaqti    = jadvaldagi smenalar − tanaffuslar              (dam olish kuni va bayramda 0, hozirgacha)
reja vaqti   = ish vaqti − REJALI sababli to'xtashlar
ishladi      = reja vaqti − rejasiz to'xtashlar − ma'lumotsiz vaqt
Availability = ishladi ÷ reja vaqti                           (reja vaqti 0 bo'lsa hisoblanmaydi)
```

| Qoida | Nega |
| --- | --- |
| To'xtash — §4.4 bilan BIR XIL: qizil va OFF darhol, sariq `stop_prompt_idle_minutes` dan uzoq bo'lsa | qisqa sariq — mikro-to'xtash: u Performance yo'qotishi, Availability emas |
| Ish vaqtida Pico'dan ma'lumot yo'q — TO'XTASH | §7 qarori; alohida «Ma'lumot yo'q» va «Qamrov» ustunlarida ko'rinadi, toki qamrov muammosi (§5) Availability'ni nega tushirayotgani ko'rinib tursin |
| Ish vaqtidan tashqaridagi holat hisobga kirmaydi | tungi OFF va tushlikdagi OFF jadval bilan o'zi kesiladi — «Smena tugadi» sababi va uni avtomat qo'yish KERAK EMAS |
| Sabab `downtime` dan VAQT bo'yicha olinadi (eng ko'p ustma-ust tushgan yozuv), to'xtashning o'zi esa `andon_event` dan | `downtime` jadvali 2026-09-18 da paydo bo'ldi — undan oldingi kunlar ham to'g'ri hisoblanadi; oraliq to'xtash o'rtasidan boshlansa ham sabab topiladi |
| LOCK yozuvlari kirmaydi | qulf vaqt tashimaydi: stanok to'xtaganini Pico yozadi, qulf ostida boshlangan to'xtash sababni `sync_machine` da allaqachon olgan |
| Smena BOSHLANGAN kuniga tegishli | 22:00 da boshlangan tungi smena ertasi dam olish kuni bo'lsa ham 06:00 gacha davom etadi; dam olish kuni kechqurun smena boshlanmaydi |
| Signal ustuni ulangan HAR ish markazi kiradi | butun davr jim turgan stanok hisobotdan tushib qolmay, 0% bo'lib ko'rinadi |
| Rang yo'q | maqsad foizi hali belgilanmagan («Ochiq») — chegarasiz yashil/qizil yolg'on baho bo'lardi |

Sahifada (2026-09-19 da SODDALASHTIRILDI — ortiqcha ustunlar olib tashlandi, arifmetika ko'rinib tursin):
**Stanok · Reja vaqti · To'xtash · Ishladi · Availability · Detallar · Performance · Brak · Quality · OEE**,
ya'ni `reja vaqti − to'xtash = ishladi`. «To'xtash» ustuni rejasiz to'xtashlar bilan stanok O'CHIQ turgan
vaqtni BIRGA beradi (ikkalasi ham reja ichidagi yo'qotish), sabablar taqsimoti esa ularni ajratadi:
«Jami to'xtash» qatori + har sabab + «Stanok o'chiq» qatori. «Qayd yo'q» degan tushuncha ekranda YO'Q
(egasining so'rovi, 2026-09-19): Pico jim bo'lsa stanok shunchaki o'chiq deb qabul qilinadi — kunlik
trekda ham bo'yalmagan qism O'CHIQ rangida, legendada alohida band yo'q. Olib tashlanganlar: «Ma'lumot yo'q» va «Qamrov» ustunlari, «Rejali to'xtash»
ustuni (sabablar jadvalida `Turi = Rejali` bo'lib turibdi) va butun «Chiroq holatlari» jadvali (PROCESSING/IDLE/…
soatlari BUTUN sutka bo'yicha edi — ikkinchi maxraj foizlarni chalkashtirardi; holatlar kunlik rangli trekda qoldi). **To'xtashlarning bittalab ro'yxati 2026-09-19 da OLIB TASHLANDI** (egasining
so'rovi): ketma-ket o'nlab qator o'qilmasdi, kerakli narsa — umumiy to'xtash vaqti va uning sabablari. Avariya SONI
jadvalda qoldi — u «necha marta» degan boshqa savol. Ish jadvali kiritilmagan bo'lsa qizil izoh chiqadi va foiz hisoblanmaydi.

Tekshiruv (bir martalik skriptlar, repoda saqlanmaydi): sof funksiyalar 31/31 — qo'lda hisoblangan kun (67.4%),
tungi smena va yarim tun bo'linishi, dam olish kunidan oldingi/keyingi smena, mikro-to'xtash, oraliq chegarasidagi
to'xtash, «hozir»gacha kesish, jadvalsiz holat; haqiqiy handler PGlite'da 18/18 — rejali sabab reja vaqtidan
chiqishi, LOCK sababi e'tiborsiz qolishi, jim stanok 0%, Pico'siz stanok kirmasligi, Excel; sahifa headless
Chrome'da 14/14 — sonlar backend javobi bilan bir xil, 1366 va 700 px'da toshmaydi.

Cheklov: chegara (`stop_prompt_idle_minutes`) o'zgartirilsa o'tgan kunlar ham yangi chegara bilan qayta hisoblanadi
(to'xtashlar saqlanmaydi, har safar hodisalardan chiqariladi).

### 4.6 Ideal sikl va Performance (2026-09-18)

```
ideal vaqt (detal) = har detalga + yuza teshik × s + qirra teshik × s + paz × s + freza × s
Performance        = Σ ideal vaqt (kuzatilgan ish vaqtida skanerlangan detallar) ÷ ishladi
```

Bitta raqam EMAS, formula: skanerlangan detalda teshiklar soni p10 = 2, p50 = 6, p90 = 15, eng ko'pi 40 (§5) — bitta
raqam operator tezligini emas, o'sha kungi mahsulot aralashmasini o'lchardi. Koeffitsiyentlar kodga qotmagan: admin
Tizim sozlamalari → «Ideal sikl (Prisadka)» da yuritadi (`GET/PUT /settings/ideal-cycle`, `system_setting` kaliti
`ideal_cycle_prisadka`). Hisob `services/performance.py`, natija `GET /reports/machine-time` da (Hisobotlar → «Stanok vaqti»).

**Boshlang'ich qiymatlar TAXMINIY** (egasi: «taxminiy raqamlar qo'yib tur») — 2026-09-16 auditidan chiqarilgan:

| Koeffitsiyent | Sukut | Asos |
| --- | --- | --- |
| Har detalga (skan, qo'yish, qisish, olish) | 15 s | median detal 6 teshik, median sikl 3 s kutish + ~24 s ishlov = 27 s → 27 − 6 × 2 |
| Yuza teshik | 2 s | ishlov vaqti p10 ≈ 15 s (kam teshikli) va median ≈ 24 s (6 teshik) orasidagi farq |
| Qirra teshik | 2.5 s | gorizontal shpindel pozitsiyalanadi — yuza teshikdan biroz sekin (taxmin) |
| Paz | 8 s | ~1 m o'tish + pozitsiyalash (taxmin) |
| Freza konturi | 12 s | taxmin |

Tsexda sekundomer bilan 5–10 detalni o'lchab to'g'rilash KERAK. Sahifa shunga yordam beradi: kartada jonli misol
(6 teshikli detal — 27 s), hisobotda «Performance kalibri» qatori — detallarning ideal vaqti va Pico o'lchagan sikl
vaqti (`wait_s + process_s`) yonma-yon. Performance 100% dan oshsa kesilmaydi — bu koeffitsiyentlar yumshoqligining belgisi.

| Qoida | Nega |
| --- | --- |
| Skan↔sikl bog'lash KERAK EMAS | yig'indi darajasida skanlar (detalga bog'langan) va ishlagan vaqt (§4.5) yetadi; bog'lash faqat koeffitsiyentlarni o'lchovdan aniq chiqarish uchun, keyinga |
| Faqat KUZATILGAN ish vaqtidagi skan sanaladi | ma'lumotsiz vaqt «ishladi» ga kirmaydi — o'sha paytdagi detal sanalsa foiz shishardi; tushlik va jadvaldan tashqari skan ham kirmaydi |
| Faqat posti PRISADKA bo'lgan ish markazi | formula teshik/paz/freza haqida — boshqa postga (kromka — metr) mos emas, u yerda «—» |
| Koeffitsiyentlar post bo'yicha BITTA to'plam | Pico hozir bitta Prisadkada; boshqa tezlikdagi ikkinchi stanok chiqsa sozlama `machine_id` bo'yicha lug'atga aylantiriladi (`ponytail:` izohi) |
| Koeffitsiyent o'zgarsa o'tgan kunlar ham qayta hisoblanadi | ideal vaqt saqlanmaydi, har safar hisoblanadi — kalibrlashda butun tarix birdan to'g'rilanadi |

Ma'lum kamchilik: ikki tomonli detal ag'dariladi (qo'shimcha vaqt), lekin bu belgi saqlanmaydi — parser orqa tomon
dasturini old tomonga qo'shib yuboradi. Kerak bo'lsa parserga maydon qo'shib, oltinchi koeffitsiyent kiritiladi.

Tekshiruv (bir martalik skriptlar): haqiqiy handler va sozlama endpointlari PGlite'da 22/22 — bekor qilingan, tushlikdagi,
ma'lumotsiz vaqtdagi va jim kundagi skanlar sanalmasligi, buzuq/tugallanmagan Pico sikllari, Kromka stanogida «—»,
saqlash + audit, yangi koeffitsiyent o'tgan kunga ta'siri, Excel; karta va hisobot headless Chrome'da 19/19.
§4.5 orakllari (31/31, 18/18) qayta o'tdi.

### 4.7 Brak va Quality (2026-09-19)

OEE'ning uchinchi qismi. Egasining qoidasi: **brak kiritilmasa Quality 100%**, kiritilsa
uning ulushi ayiriladi.

```
Quality = (detallar − brak) ÷ detallar        (detal sanalmagan bo'lsa hisoblanmaydi)
OEE     = Availability × Performance × Quality
```

| Qism | Qayerda | Nima qiladi |
| --- | --- | --- |
| Jadval | `part_defect` (migratsiya `b3f5c17a9d84`, docs/04) | brak qilingan NUSXA: buyurtma/detal/nusxa, skan, ish markazi, post, belgilagan hodim, sabab (MATN), izoh |
| Sabablar | Tizim sozlamalari → «Brak sabablari» (`system_setting.defect_reasons`, JSON ro'yxat) | alohida jadval EMAS: sabab yozuvga matn bo'lib ko'chiriladi, ya'ni ro'yxatdan olib tashlangani eski yozuvda o'qilaveradi |
| Terminal | `Terminal/DefectDialog.tsx` + skan tasmasidagi BRAK tugmasi | oxirgi MUVAFFAQIYATLI skan turganda tugma chiqadi; oyna sabab tugmalari va ixtiyoriy izoh; ro'yxat bo'sh bo'lsa tugma umuman chizilmaydi |
| API | `GET /terminal/defect-reasons`, `POST /terminal/defects`, `DELETE /terminal/defects/{id}` (docs/03) | belgilash va noto'g'ri bosilganini qaytarish (yumshoq o'chirish) |
| Menejer qarori | `/defects` sahifasi (`routes/_layout/defects.tsx`), `GET /defects`, `POST /defects/{id}/review` | tasdiqlaydi yoki «brak emas» deb rad etadi; aybdor QADAM (post emas) va qayta boshlash nuqtasi belgilanadi; sidebar belgisida kutayotganlar soni |
| Qayta ochish | `services/defects.py: reopen_from_step` (tasdiqda avtomatik) | tanlangan qadamdan KEYINGI skanlar `revoke_scan` bilan bekor qilinadi, qadoqdan chiqariladi, kesish postidan boshlansa chek ham qaytariladi |
| Hisob | `services/performance.py: quality_pct` / `oee_pct`, `GET /reports/machine-time` | «Stanok vaqti» dagi «Brak», «Quality» va «OEE» ustunlari, kunlik trekda ham |

| Qoida | Nega |
| --- | --- |
| QAYD skanni bekor qilmaydi, TASDIQ esa bekor qiladi | operator faqat o'lchov uchun belgilaydi; ishni qaytadan boshlash — menejer qarori. Shuning uchun qayta ochish `review` ichida, `mark_defect` da emas |
| Qayta ochish uchun ALOHIDA ro'yxat yozilmadi | har post o'z ishini MARSHRUTDAN o'qiydi: qadam yopilmagan bo'lsa detal o'sha postda turadi, oldingilari yopiq bo'lsa «tayyor», keyingilari E004 bilan kutadi. Skanlarni qaytarishning o'zi kifoya — detal ARRA'da bo'lsa faqat arrada, kromkaga o'tsa faqat kromkada ko'rinadi |
| Nusxa ID o'zgarmaydi (`-B1` YO'Q) | docs §7 da `-B1` rejalashtirilgan, lekin u yangi `PartInstance`, yangi SCX fayl va kesish xaritasidagi katak bog'lamini talab qiladi — alohida qadam. Hozir eski chek AMAL QILADI: arrachi o'sha katakdan yangi chek chiqaradi, kromkachi o'sha QR ni skanerlaydi |
| Yopiq qadoqdan ham chiqariladi | terminaldagi bekor qilish yopiq qadoqni rad etadi (qadoqlovchi o'zi qayta ochsin), bu esa MENEJER qarori — brak detal qadoqda qolsa omborga yaroqsiz buyum ketardi |
| Rad etish hech narsani tiklamaydi | jismoniy ish allaqachon qilingan; noto'g'ri tasdiqdan keyin skanlarni qo'lda qaytarish kerak |
| Quality REJECTED dan boshqasini sanaydi (kutayotgani ham kiradi) | tasdiq kechikkanda OEE aslidan yaxshi ko'rinib turardi; «brak emas» deb rad etilgani esa hisobdan chiqadi |
| Ayb POST emas, QADAM (`part_route`) bo'yicha | bitta post marshrutda ikki marta uchraydi (Kromka → Prisadka → Kromka) — «Kromka aybdor» degani qaysi o'tish ekanini aytmaydi. **NOSTANDART detalda ham xuddi shunday**: texnolog qo'lda chizgan qatorlar o'sha `part_route` jadvalida turadi, qaror ularni O'ZGARTIRMAYDI, remake esa yangi `-B1` nusxaga o'sha `part_id` ni beradi (§7 qarori) — saqlangan `restart_route_id` o'shanda ham to'g'ri qadamni ko'rsatadi |
| Texnolog O'CHIRGAN qadam (`is_enabled=false`) ro'yxatda yo'q va tanlanmaydi (422) | detal u yerdan o'tmagan: na ayb, na qayta boshlash nuqtasi bo'la oladi |
| Aybdor hodim tasdiqlashda SURATGA olinadi (`blame_employee_id`) | keyin skan bekor qilinsa yoki qayta skanerlansa ayb boshqa odamga ko'chib ketardi |
| Tasdiqda qayta boshlash qadami MAJBURIY, ayb ixtiyoriy | «qayerdan qayta boshlanadi» — qarorning o'zi; material nuqsonida esa ayb hech kimda emas |
| Qaror qayta o'zgartiriladi | noto'g'ri bosilgani tuzatilsin; operator esa menejer ko'rib chiqqan brakni o'chira olmaydi (422) |
| Braklar detallar bilan BIR XIL filtrda sanaladi (kuzatilgan ish vaqti) | aks holda surat va maxraj boshqa-boshqa vaqtdan yig'ilib, foiz «100 dan katta» yoki «manfiy» bo'lib chiqardi |
| Tasdiqlangan brakning BEKOR QILINGAN skani hisobda QOLADI (`defect_scan_ids`) | tasdiq nusxani qayta ochib skanini bekor qiladi; u sanoqdan tushib ketsa brak IKKI marta jazolanardi — detal Performance'dan ham chiqardi, Quality'dan ham ayirilardi. O'lchangan: tasdiqdan keyin ham `parts` 600, `ideal_s` 16200, Quality 93.3% |
| Brakni faqat SKAN yozilgan post belgilaydi (`scan.post_id != post.id` → 403) | bitta nusxa ikki postdan ikki marta brak qilinsa Quality ikki barobar tushardi |
| Bitta skan — bitta brak (takror urinish 422) | tugma katta, tasodifiy ikki marta bosish real |
| Sabab ro'yxatdan bo'lishi shart (422 «Sahifani yangilang») | terminal eskirgan ro'yxatni ko'rsatib turgan bo'lishi mumkin |
| Detal sanalmagan bo'lsa Quality `None` (—), 0% emas | 0% «hammasi brak» degan yolg'on baho bo'lardi |
| Brak detaldan ko'p chiqsa 0% da to'xtaydi | kechagi skan bugun brak qilinsa foiz manfiy bo'lib ketardi |
| Quality faqat PRISADKA ish markazida | detallar (maxraj) faqat o'sha yerda sanaladi (§4.6); brakni boshqa post ham belgilay oladi, lekin uning Quality ustuni hali yo'q |

Tekshiruv (bir martalik skriptlar, repoda saqlanmaydi): HAQIQIY Postgres'da to'liq hisobot
18/18 (bir kunlik ekilgan ma'lumot: reja 7.5 soat, ishladi 5.5 soat, A 73.3%, qamrov 87.5%,
P 81.8%, Q 90.0%, OEE 54.0%; tushlikdagi, ma'lumotsiz vaqtdagi va bekor qilingan skan
sanalmaydi, o'chirilgan brak ham) va tasdiqlash oqimi 15/15 (rad etilgani Quality'dan
chiqadi — 93.3%, aybdor hodim suratga olinadi, qadamsiz tasdiq va begona qadam 422, qaror
o'zgartiriladi, sidebar soni) va NOSTANDART marshrut 14/14 (`[Kromka(3), Prisadka(6),
Kromka(4)]` + o'chirilgan qadam: ro'yxat tartibi va amal kodlari, har qadamdagi hodim,
IKKINCHI Kromkani ayb qilib tanlash birinchisidan farq qiladi, o'chirilgan va begona
detalning qadami 422, marshrut qatorlari va `is_custom` bayrog'i tegilmagan) hamda QAYTA
OCHISH 15/15 (ARRA → KROMKA → PRISADKA → QADOQLASH to'liq bajarilgan, COMPLETED buyurtma,
yopiq qadoqdagi detal: ARRA'dan tasdiqlangach to'rtala hisoblagich 0 ga qaytdi, chek va
`label_post_id` tozalandi, qadoqdan chiqdi, buyurtma «jarayonda» bo'ldi; keyin KROMKA skani
E004 bilan rad etildi, ARRA skanidan SO'NG kromkada «tayyor» bo'ldi, PRISADKA esa yana E004
— ya'ni ish ketma-ket yuradi). Tasdiqlash oqilida (17/17) tasdiqdan
keyin ham `parts` 600 va `ideal_s` 16200 bo'lib qolishi alohida tekshiriladi. Sof funksiyalar 13/13 — brak yo'q → 100%,
2/10 → 80%, 1/3 → 66.7%, detalsiz → `None`, brak > detal → 0%, `A=75 · P=80 · Q=100` → OEE 60%,
uchtasidan biri `None` bo'lsa OEE ham `None`.

Hali yo'q: `-B1` yangi nusxa va uning SCX fayli (hozir eski ID va eski chek qayta
ishlatiladi), buyurtma kartasidagi «BRAK n» belgisi, brak bo'yicha Pareto/statistika
sahifasi, aybdor hodim kesimidagi hisobot.

### 4.8 Kromka stansiyasi — kuzatuv (2026-09-19, 1-bosqich)

Kromkada ikkinchi Pico bor: u chiroq emas, **detal uzunligini** ikkita to'siq datchigi bilan
o'lchaydi (alohida repo — `jasper2233/kromka-stansiya-OYY`, firmware v1.14). 1-bosqichda u
faqat KUZATILADI: hech narsa bloklanmaydi, skan oqimiga tegilmaydi. Foyda darhol —
**KROMKA uchun ham Availability** va o'lchov tarixi.

| Qism | Qayerda | Nima qiladi |
| --- | --- | --- |
| Tur aniqlash | `bridge-agent/agent.py: _andon_line` | Prisadka `MES event {...}` deb yozadi, kromka YALANG'OCH JSON (`{"ev":"olchov"}`) — birinchi tushunarli qatordan aniqlanadi, `ANDON_TUR` env bilan majburlash mumkin |
| Yurak urishi | o'sha faylda `_andon_session` | Kromka Pico'si 3 soniya BUYRUQ ko'rmasa hodisalarni RAM ga yig'a boshlaydi — unga har soniyada `HB`, prisadkaga 5 soniyalik `PING` |
| Kalit | `_kromka_kalit` | Kromka firmware'i `session`/`seq` ni yubormaydi — agent beradi (har ulanishda yangi sessiya), shuning uchun serverdagi `(machine_id, session, seq)` unikal indeksi qayta yuborishni o'zi tashlaydi |
| Buferdan kelgani | `_kromka_line` | `eski_ms` — hodisa Pico xotirasida qancha kutgani; `ts = hozir − eski_ms`, aks holda tun bo'yi yig'ilgani bitta daqiqaga tiqilardi |
| Qabul | `POST /bridge-agents/andon` (o'sha endpoint) | `AndonEventIn.type` ga kromka turlari qo'shildi: `olchov`, `uskuna`, `tezlik`, `ogoh`, `avariya_toxtash`, `boot`. Yangi jadval YO'Q — xom hodisa `andon_event.payload` da |
| Joriy holat | agent har 30 s `HOLAT` so'raydi (`_kromka_holat`) | Kromka `uskuna` ni faqat RUN kirishi O'ZGARGANDA yuboradi — stanok ertalab yoqilib, agent kunduzi ulansa hech narsa kelmasdi. `HOLAT` javobidagi `uskuna` o'sha lahzadagi holat; **o'zgargan bo'lsagina** hodisa yoziladi (`manba: "holat"`), aks holda oraliqlar maydalanardi |
| Oraliqlar | `services/andon.py: uskuna_spans` | Kromka Pico'si holat DAVOMIYLIGINI o'lchamaydi (prisadkadagi `prev_duration_s` yo'q) — oraliq hodisalar orasidan quriladi: `holat=1` → PROCESSING, `0` → OFF. Oxirgi oraliq faqat agent hozir aloqada bo'lsa ochiq qoladi |
| Admin panel | `WorkCenters/KromkaLive` + `GET /machines/kromka-measurements` + WS `kromka.measure` | «Ish markazlari» sahifasi ostida JONLI oqim: detal o'tishi bilan qator chiqadi (vaqt, mm, Pico kodi, D1/D2, tezlik, stanok), eng yangisi bir marta yashil uriladi. Bitta partiyadan ko'pi bilan 5 ta xabar tarqatiladi — oflayn agent yuzlab yig'ilganini birdan yuborsa ekran ko'milmasin |
| Terminal | `Terminal/KromkaView: StationStrip` + `GET /terminal/kromka/measurements` | Sarlavha ostida oxirgi o'lchov: `mm`, Pico kodi (OK/FARQ/FAQAT1/FAQAT2), D1/D2, tezlik va oldingi 7 tasi. Stansiyasiz postda umuman chizilmaydi |

Ma'lumot sifatini o'lchash uchun `scripts/kromka_audit.sql` — faqat o'qiydigan SQL
(o'sha `oee_audit.sql` naqshi, 10 bo'lim): qamrov, kunlik sanoq, Pico kodlari taqsimoti
(`OK`/`FARQ`/`FAQAT1`/`FAQAT2`), D1−D2 farqi (median/p90/max), tezlik tarqoqligi, MAYDA
bo'laklar soni, ogohlantirishlar, kunlik ishlagan vaqt, uzilishlar va oxirgi 15 o'lchov.
Qayerda ishga tushirish — fayl boshida.

**1-bosqichga kirmaydi**: QR bog'lash, kutilgan o'lcham, MOS/NOMOS verdikti, avtomatik skan,
avtomatik brak, kalibrlash UI si va `SET` yuborish (Pico `kal.json` dagi oxirgi sozlama bilan
ishlayveradi), sirena/lampa mantiqi.

Tekshiruv (bir martalik skript): **27/27** — ularning sinov bazasidan tiklangan 214 ta HAQIQIY
Pico qatori agent parseridan o'tdi (tur aniqlandi, `seq` uzluksiz, `eski_ms` vaqti tiklandi,
`CHOP` matni tashlandi, prisadka formati buzilmadi), 44 hodisa endpointga qabul qilindi va
takror yuborishda 0 ta yangi yozuv, xom maydonlar (`L`, `kod`) saqlandi, kunlik hisobotda
reja 9 soat / ishladi 7 soat / **Availability 77.8%**, Performance va Quality esa `—`
(Prisadka emas).

Ma'lum cheklov (ularning firmware'ida, bizda emas): mayda bo'lak (10 m/min da 8 mm dan uzun
har narsa) D1→D2 navbatiga tushib juftlikni siljitadi — prod ma'lumotida 8 ta soxta
«tezlik nomuvofiq» va bir nechta bema'ni uzunlik shundan. 1-bosqichda zararsiz (faqat
yoziladi), lekin **avtomatik skanga o'tishdan oldin tuzatilishi shart**.

## 5. Prod auditi natijalari (2026-09-16)

Davr: 2026-09-14 09:36 — 2026-09-16 15:16, faqat Prisadka (ish markazi 1, agent v1.5.0, `can_print=false`).

| Nima | Natija | Xulosa |
|---|---|---|
| Kunlik qayd | 4.1 / 4.0 / 2.5 soat, qolgani noma'lum | **OEE uchun yetarli emas** |
| Pico sessiyalari | 3 kunda 7 ta; 4 tasi uzoq kutishda (STOPPED) uzilgan | Pico quvvati Nanxing kompyuteri USB'sidan — kompyuter uxlasa/o'chsa Pico ham o'chadi, OFF yozilmaydi |
| Sessiya ichida yo'qolgan hodisa | 0 | Transport ishonchli |
| Kechikish (agent → server) | median 4 s, max 10 s, soat farqi yo'q | OK |
| Sikl ↔ MES skan (kunlik) | 134/127, 197/187, 158/157 | **Sanoq ishonchli** |
| Ishlov vaqti | median 20–28 s, p10 ~15 s | — |
| "Ishlovsiz" sikllar | 15–20% | Chiroq tasnifi artefakti bo'lishi mumkin (quyida) |
| ≤2 s lik PROCESSING → AWAIT_PART | 66 ta | Miltillash boshlanishi ishlov deb o'qilishi — miltillash davri `MIN_STATE_MS` ga mos kelmayotgan bo'lishi mumkin |
| AWAIT_PART'siz IDLE → PROCESSING | 108 ta | Dastur qayta skanersiz ishga tushirilgan yoki miltillash juda qisqa |
| IDLE → STOPPED chegarasi | 300 s | Firmware standarti 900 s — qurilmadagi sozlama farq qiladi |
| To'xtashlar (~2.2 kun) | 16 STOPPED (4 yopilmagan), 10 FAULT (median 12 s), 7 OFF (yuklanishda 21 s) | Kuniga ~12 ta — sabab kiritish yuki yengil |
| Smena (`work_session`) | 14 kunda Prisadkada yangi smena yo'q; 2026-09-05 dagi smena hali ochiq | **Stanok skanerining skanlari eski ochiq smena egasiga yozilyapti** — mahsuldorlik hisoboti Prisadka uchun noto'g'ri |
| Detal ish hajmi (teshik) | p10 2, median 6, p90 15, max 40 | Ideal sikl uchun bitta raqam yaramaydi — formula kerak |
| `stop_reason` / `machine_stop` | 0 / 0 qator | Egasining sabablari bazada yo'q, xlsx dan olinadi |

Skan↔AWAIT_PART bog'lash bo'limi natija bermadi: o'shanda zaxira 30 s edi, sikl esa ~25 s,
ya'ni keyingi detal skani ham sanalardi. SQL'da 5 s ga tuzatildi — qayta ishga tushirish kerak.

## 6. Keyingi qadamlar (tartib bilan)

1. **Qamrov** — Nanxing kompyuterida uyqu rejimini o'chirish; Pico'ni stanokning doimiy 24 V
   liniyasidan quvvatlash (firmware `docs/tz.md` §3.5), shunda OFF ham yoziladi.
2. **Smena** — harakatsizlikdan yopish qilindi (§4.3): deploy'dan keyingi birinchi cron 2026-09-05
   dan ochiq Prisadka smenasini ham yopadi (`ended_at` = oxirgi faollik). Qolgani — tsexda smena
   har kuni beyjik bilan ochilishini tekshirish.
3. **Chiroq tasnifi** — tsexda yashil miltillash davrini o'lchash, firmware `MIN_STATE_MS` /
   `BLINK_WINDOW_MS` ni moslash; `idle_timeout_s` ni mikro-to'xtash chegarasi bilan bir xil qilish.
4. **To'xtash sabablari** — kiritish qilindi, egasining ro'yxati keldi (§4.4). Qolgani: admin ro'yxatni
   prodda Tizim sozlamalariga kiritadi.
5. **Availability hisoboti** — qilindi (§4.5). Qolgani: prodda ish jadvali kiritilganini tekshirish (usiz foiz
   hisoblanmaydi); qamrov (1-band) tuzatilmaguncha foiz past chiqadi — «Ma'lumot yo'q» ustuni shuni ko'rsatadi.
6. **Performance** — qilindi (§4.6), koeffitsiyentlar TAXMINIY. Qolgani: tsexda sekundomer bilan o'lchab Tizim
   sozlamalarida to'g'rilash; keyin (ixtiyoriy) skan↔sikl FIFO bog'lash (prototip `mes/bridge.py` mantiqi) —
   koeffitsiyentlarni 2–4 haftalik o'lchovdan chiqarish uchun.
7. **Quality** — brak qaydi va MENEJER TASDIG'I qilindi (§4.7): terminalda BRAK tugmasi,
   `/defects` sahifasida tasdiq/rad va aybdor qadam, Quality va OEE hisobotda.
   Qolgani: admin sabablar ro'yxatini kiritsin; keyin qayta ishlab chiqarish oqimi (§7) —
   `-B1` nusxa, yangi chek va marshrutni qayta ochish.

## 7. Qarorlar

### Qabul qilingan (2026-09-17, egasi bilan)

- **Pico'dan ma'lumot kelmasa — stanok O'CHIQ.** Reja vaqti ichida bu to'xtash, "noma'lum" emas:
  Prisadka Nanxing kompyuterisiz ishlamaydi, Pico esa shu kompyuterdan quvvat oladi.
- **To'xtash sababini ham, brakni ham smenada ishlayotgan hodim kiritadi** — o'sha stanokdagi ochiq
  smena (`work_session`) egasi. Alohida "usta" roli YO'Q va qo'shilmaydi; brigadada kim kiritgani
  smenadan olinadi. Shuning uchun OEE bog'lanishi haqiqiy smenaga tayanadi (§4.3).
- **Terminalga doimiy tugmalar qo'shilmaydi** — 2026-08-21 dagi modul 1366×768 ekranga sig'magani
  uchun qaytarilgan; kiritish kerak bo'lganda chiqadigan oyna (dialog) bo'ladi.
- **Sabab qachon so'raladi** (uch yo'l):
  1. **Qulf tugmasi** (mavjud tugma) — hodim ketishdan oldin sababni o'zi tanlaydi, "Saqlash va
     qulflash" dan keyin ekran qulflanadi; sabab qulf ekranida ko'rinadi. To'xtash qulflangan
     paytdan beyjik bilan ochilguncha; shu oraliqda Pico ochgan to'xtash qayta so'ralmaydi.
  2. **Qizil yonsa** (FAULT) — oyna darhol chiqadi.
  3. **Stanok uzoq ishlamasa** (sariq) — Tizim sozlamalaridagi «Uzoq to'xtash, daqiqa»
     (`stop_prompt_idle_minutes`, sukut 5, 1..120) o'tgach. Vaqtni SERVER sariq yongan paytdan sanaydi —
     Pico `idle_timeout_s` ga bog'liq emas, chegarani o'zgartirish uchun Pico'ga tegilmaydi.
  Qizil yonsa — ~3–5 soniya (Pico 1.2 s barqarorlik + agent har 3 s yuboradi + WS).
- **Brak oqimi** (1-band 2026-09-19 da bajarildi — §4.7; qolgan bandlar hali yo'q)**:**
  1. **Hodim** detalni skanerlaydi, skan chizig'idagi BRAK tugmasini bosadi va faqat NIMA bo'lganini tanlaydi.
  2. Qayta ishlab chiqarish so'rovi **avtomat** yaratiladi ("Kutmoqda").
  3. **Menejer** (admin → Brak sahifasi, sidebar belgisida kutayotganlar soni) belgilaydi:
     - **aybdor** — marshrutdagi post va o'sha postda skanerlagan hodim, yoki "material nuqsoni";
     - **qayerdan qayta boshlanadi**.
     So'ng tasdiqlaydi yoki "brak emas" deb rad etadi.
  4. ARRA dan tanlansa, detal yangidan kesiladi. Alohida ro'yxat YO'Q: buyurtma ARRA "Buyurtmalar" ro'yxatida
     oddiy buyurtma kabi turadi (kartada qizil "BRAK n" belgisi, qoldiq +1). Kesish xaritasi odatdagidek ochiladi va
     faqat brak detal katagi kesilmagan (yashil emas) bo'lib turadi — o'sha katakka yangi nusxa `…-B1` bog'langan.
     Arrachi katakni bosib odatdagidek chek chiqaradi; eski nusxa yaroqsiz bo'ladi.
     **Yangi ID:** `{eski ID}-B1` (shu nusxa yana brak bo'lsa `-B2`, `-B1-B1` EMAS). Tasdiqlashda uning SCX fayli
     (`{ID}.scx`, Panel ID shu satr) AVTOMAT yaratiladi — Nanxing skanerlangan nomdagi faylni ochadi. Eski chek
     skanerlansa "Bu detal brak" deb rad etiladi. O'lchangan (2026-09-17): skan darvozasi, agent forvardi (64 belgi)
     va nusxasi ko'p detalda "Kod" ustuni `-B1` bilan to'g'ri ishlaydi; nusxasi bitta detalda "Kod" `…-B1` bo'lib
     chiqadi — docs/11 ga `-B{n}` qoidasi qo'shilishi kerak (`-N` bilan chalkashmasin).
     Keyingi postdan tanlansa (masalan KROMKA — qayta yopishtirish), shu detal ESKI ID bilan o'sha postga qaytadi,
     yangi chek yo'q: buyurtma o'sha post ro'yxatida "BRAK n" belgisi bilan chiqadi, detal qatorida faqat o'sha
     nusxa chipi qilinmagan (`0/4`) bo'ladi, operator eski chekni skanerlaydi. Keyingi bosqichlar (PRISADKA…) ham
     qayta ochiladi.
     ARRA dan qayta boshlanganda keyingi postlarda (masalan KROMKA) detal **KROMKA bosqichiga kelmaguncha umuman
     ko'rinmaydi** (2026-09-17 qarori): qoldiq ham, "BRAK" belgisi ham yo'q. ARRA yangi `-B1` chekni chiqargan paytda
     kromkada "BRAK n", qoldiq +1 va `№2 0/4` chiqadi; `-B1` chek skanerlanadi. Eski chek skanerlansa "topilmadi"
     emas, "Bu detal brak, yangi chek …-B1" bo'lishi kerak.
  5. Tasdiqlanmagan brak ish oqimini to'xtatmaydi, lekin yangi nusxa tasdiqdan keyingina chiqadi.
  6. **Tasdiqlash nima qiladi** (2026-09-17 kod tekshiruvi — xotira `brak-remake-conflicts`):
     - eski nusxa skanlari `revoke_scan` bilan **bosqichma-bosqich** bekor qilinadi. Qayta boshlash posti
       (masalan KROMKA) bo'lsa — o'sha va keyingilari darhol. ARRA bo'lsa — tasdiqda FAQAT ARRA skani, KROMKA va
       keyingilari esa ARRA yangi chekni chiqargan tranzaksiyada, ARRA skanidan OLDIN (tartib shart: teskari
       bo'lsa buyurtma erta "tayyor" bo'ladi). bir martalik PGlite skripti (repoda saqlanmaydi) bilan tekshirilgan, 7/7;
     - **nostandart detal marshruti saqlanadi** (2026-09-17 qarori). Marshrut detal TURIGA bog'langan
       (`part_route.part_id`, `seq` tartibi), yangi `-B1` nusxa o'sha `part_id` ni oladi — marshrut qatorlari
       o'zgartirilmaydi. Qayta boshlash va aybdor POST emas, QADAM (`seq`) bo'yicha: bir postdan ikki marta o'tadigan
       marshrutda (Kromka → Prisadka → Kromka) "3. Prisadka" tanlansa faqat seq≥3 ochiladi, 1-Kromka tegilmaydi.
       Birinchi qadam ARRA emas (masalan ROVER) bo'lsa yangi chek o'sha postdan chiqadi. PGlite orakli:
       bir martalik PGlite skripti, 8/8 (qat'iy tartib nostandart marshrut bo'yicha ham ishlaydi).
       ROVER dan qayta boshlash prototipda ko'rsatilgan: Rover ro'yxatida "BRAK 1", ro'yxat qatorida `…-B1` "Chek yo'q",
       rover xaritasida katak kesilmagan (binafsha); chek chiqqach yashil, "TAYYOR". **Tuzatish kerak:** qatordagi xarita
       belgisi detal KODI bo'yicha birinchi katakni belgilaydi (`CutmapView` `p.key === focusPartKey`) — brak nusxaning
       o'z katagini (kesilmaganini) belgilashi kerak.
     - bekor qilingan skan brak bilan belgilanadi (`scan.defect_id`, yangi ustun). **Hodimlarga ish hisoblanadi:**
       mahsuldorlik va dashboard hisobotlari bunday skanni sanaydi, marshrut va hisoblagich esa sanamaydi;
     - eski nusxa `is_deleted`, yangisi eski `instance_no` va katakni oladi;
     - detal qadoqda bo'lsa undan avtomat chiqariladi, yopiq qadoq cheki qayta chiqariladi;
     - yig'ma mayda detali: `-B1` mayda detal birikish postida TO'G'RIDAN skanerlanadi (asosiy detal qayta
       skanerlanmaydi — E008); asosiy detal remake bo'lsa undan hosil bo'lgan mayda skanlar bekor bo'ladi va yangi asosiy
       skan ularni qayta yopadi (bir martalik PGlite skripti, 25/25 — qadoq/TMO, yig'ma, Prisadka, `-B2`);
     - buyurtma "tayyor" bo'lsa "jarayonda" ga qaytadi. **"Topshirilgan" buyurtmada brak tasdiqlanmaydi.**
  Ko'rinishi lokal prototipda (soxta API bilan) egasiga ko'rsatilgan — repoga chiqarilmagan, haqiqiy kod hali yo'q.
- **To'xtash sabablari ro'yxati (2026-09-18, egasidan)** — `oee to'xtalishlar.xlsx`: 10 rejali, 10 rejasiz (§4.4).
  Kodga YOZILMAYDI — statik bo'lib qolmasin: admin Tizim sozlamalarida «Rejali» va «Rejasiz» ro'yxatlariga alohida kiritadi.
- **Ideal sikl (2026-09-18)** — bitta raqam emas, FORMULA; koeffitsiyentlar admin paneldan kiritiladi (§4.6).
  Boshlang'ich qiymatlar taxminiy qo'yildi (egasi shunday dedi) — tsexda o'lchab to'g'rilanadi.

### Ochiq

- Mikro-to'xtash chegarasi — Tizim sozlamalarida (sukut 5 daqiqa), tsexda sinab moslanadi.
- Juda qisqa avariyalar (prod median 12 s) ham so'ralsinmi yoki chegara qo'yilsinmi.
- Ideal sikl koeffitsiyentlarining HAQIQIY qiymatlari (hozir taxminiy, §4.6) — sekundomer o'lchovi.
- Brak sabablari ro'yxati; menejer uzoq tasdiqlamasa (masalan 1 soat) eslatma kerakmi.
- Qayta ishlab chiqarilgan detalning kesish joyi: qoldiq (atxot) varaqdanmi, yangi varaqdanmi.
- Maqsad OEE foizi (tablo/hisobot rangi uchun).

## 8. Xavflar

- **Sabablar kiritilmasa** "sababsiz" to'xtashlar ko'payadi va Pareto ma'nosiz bo'ladi — ma'sul
  shaxs smenadagi hodim, lekin smena ochilmasa (beyjiksiz ishlansa) kiritadigan odam ham yo'q.
- **Qamrov** — ma'lumotsiz vaqt O'CHIQ deb hisoblanadi (§7), ya'ni Pico yoki kompyuter elektr
  muammosi ham stanok to'xtashi bo'lib ko'rinadi; 1-qadam (doimiy quvvat) bajarilmaguncha Availability
  real holatdan past chiqadi.
- **Chiroq tasnifi** noto'g'ri bo'lsa Performance buziladi.
- **Ikki repo shartnomasi** — firmware hodisa formatini o'zgartirsa MebeliX jimgina buziladi
  (hodisalarda versiya maydoni yo'q); o'zgarish ikkala tomonda birga qilinadi.
- **Operator ekrani** — o'tgan OEE aynan tugmalar sig'magani uchun qaytarilgan; sabab va brak
  kiritish doimiy tugma emas, kerak paytda chiqadigan oyna.
- **Talqin** — signal ustuni faqat Prisadkada: bu "Prisadka OEE", tsex OEE emas.
