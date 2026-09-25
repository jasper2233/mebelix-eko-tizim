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
| **Performance hisobi** | `services/performance.py`, Hisobotlar → «Stanok vaqti» (§4.6, kromka — §4.9) | ✅ bor: Prisadka (2026-09-18) va Kromka (2026-09-20) |
| **Kromka o'lchovi ↔ detal** | `services/kromka.py`, Tizim sozlamalari → «Kromka o'lchovi» (§4.10) | ⚠️ hukm bor (mos/ortiqcha/nomos), lekin KUZATUV: datchik xato o'lchayapti, avtomatik brak o'chirilgan (2026-09-20) |
| **ROVER (CNC 2130) kuzatuvi** | `bridge-agent/agent.py` (v1.7.0), `andon_event.kind='rover'` (§4.13) | ✅ bor (2026-09-20): holat, to'xtash va Pico hodisalari; rele hali o'chiq |
| **Devordagi stanok taxtasi** | `/tablo/stanoklar`, `GET /tablo/machines` | ✅ bor (2026-09-21): jonli holat, smena, bugungi A·P·Q·OEE, sababsiz to'xtashlar, «aloqa yo'q» ajratilgan |
| **OEE kesim sanasi** | `settings_service.OEE_START_DATE`, Tizim sozlamalari → «Ish jadvali» (§4.12) | ✅ bor (2026-09-20): kesimdan oldingi kunlar hisobotga kirmaydi |
| **Quality hisobi** | `services/performance.py: quality_pct`, Hisobotlar → «Stanok vaqti» (§4.7, kromka — §4.11) | ✅ bor: Prisadka (2026-09-19) va Kromka (2026-09-20) |
| Brak | `part_defect` — terminal skan tasmasidagi BRAK tugmasi (§4.7) | ✅ bor (2026-09-19); qayta ishlab chiqarish (remake) YO'Q |
| **ROVER (CNC 2130) kuzatuvi** | `bridge-agent/agent.py` (v1.7.0), `andon_event.kind='rover'` (§4.13) | ✅ bor (2026-09-20): holat, to'xtash va Pico hodisalari; rele hali o'chiq |
| **Devordagi stanok taxtasi** | `/tablo/stanoklar`, `GET /tablo/machines` | ✅ bor (2026-09-21): jonli holat, smena, bugungi A·P·Q·OEE, sababsiz to'xtashlar, «aloqa yo'q» ajratilgan |
| **OEE kesim sanasi** | `settings_service.OEE_START_DATE`, Tizim sozlamalari → «Ish jadvali» (§4.12) | ✅ bor (2026-09-20): kesimdan oldingi kunlar hisobotga kirmaydi |
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
| Hisob | `services/downtimes.sync_machine` | HAR QANDAY to'xtash `stop_prompt_idle_minutes` dan uzoq davom etsagina sabab so'raydi (2026-09-20 tsex talabi): prisadkada qizil (FAULT), OFF va sariq (IDLE/STOPPED), kromka va roverda `uskuna` `holat=0` → `OFF`. Vaqt to'xtash BOSHLANGAN paytdan. Qisqa to'xtash HISOBGA baribir kiradi (Availability oraliqlardan), faqat sababi so'ralmaydi. Idempotent, sabab qayta hisobda tegilmaydi |
| Worker | `tasks.sync_downtimes` (5 daq) | terminal yopiq bo'lsa ham to'xtashlar yozilib, yopilib turadi |
| Terminal | `GET /terminal/downtimes/pending` (30 s + `andon.state` WS), `Terminal/DowntimeReason.tsx` | sababsiz to'xtash bo'lsa oyna o'zi chiqadi; faqat Pico ulangan ish markazida (`has_andon`) va smena ochiq bo'lsa; «Keyinroq» — 10 daqiqa |
| Qulf | `POST /terminal/downtimes/lock` | qulf tugmasi avval sabab so'raydi; qulf beyjik bilan ochilganda (`open_badge_session`) yopiladi, uning ostida boshlangan Pico to'xtashi sababni oladi |
| Bo'sh yurish (kromka) | `services/andon.split_idle` + `downtimes._bosh_yurish` | lenta YURYAPTI (RUN yoqiq), lekin `kromka_idle_minutes` (sukut 10) davomida bitta ham detal o'tmadi — bu ham to'xtash (`IDLE`): sabab so'raladi va o'sha vaqt «ishladi» dan chiqadi. Manba — o'lchovlar orasidagi tirqish: RUN kirishi «bo'sh yuryapti» deb aytmaydi |
| Sozlamalar | Tizim sozlamalari → «To'xtash sabablari» | chegara (sukut 5, 1..120), **kromka bo'sh yurishi** (sukut 10, 1..240) va IKKI ro'yxat — «Rejali» va «Rejasiz» alohida, har birining o'z qo'shish maydoni: nom, «Izoh majburiy», «Faol», narigi guruhga o'tkazish (o'chirish yo'q) |

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

Kromkada bo'sh yurish alohida chegara bilan (`kromka_idle_minutes`): to'xtash 5 daqiqada
so'raladi, bo'sh yurish esa uzunroq bo'lishi normal — detal almashtirish ritmi jazolanmasin.
Yo'qotish IKKI marta sanalmaydi: bo'sh yurish `run_s` dan chiqadi, ya'ni Performance maxraji
ham qisqaradi. **Bitta ham o'lchov bermagan stanok TEGILMAYDI**: datchigi buzuq yoki ulanmagan
stansiya butun kunni «bo'sh yurish» qilib ko'rsatardi — apparat nosozligi ishlab chiqarish
yo'qotishi bo'lib yozilardi va Availability nolga tushardi. O'lchov yo'qligi «lenta bo'sh»
emas, «bilmaymiz» degani (datchik nosozligini Pico `ogoh` bilan alohida aytadi).
Tekshiruv **12/12** — 2 soatlik jimlik `IDLE` yozuvi bo'ldi (boshlanishi oxirgi
o'lchovdan), terminal sabab so'radi, qayta hisobda ikkilanmadi, Availability 66.3%.

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
| To'xtash — §4.4 bilan BIR XIL: har qanday turi `stop_prompt_idle_minutes` dan uzoq bo'lsa | qisqa to'xtash — mikro-to'xtash: u Performance yo'qotishi, Availability emas |
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
o'lchaydi (alohida repo — `jasper2233/kromka-stansiya-OYY`, firmware **v1.22**). 1-bosqichda u
faqat KUZATILADI: hech narsa bloklanmaydi, skan oqimiga tegilmaydi. Foyda darhol —
**KROMKA uchun ham Availability** va o'lchov tarixi.

| Qism | Qayerda | Nima qiladi |
| --- | --- | --- |
| Tur aniqlash | `bridge-agent/agent.py: _andon_line` | Prisadka `MES event {...}` deb yozadi, kromka YALANG'OCH JSON (`{"ev":"olchov"}`) — birinchi tushunarli qatordan aniqlanadi, `ANDON_TUR` env bilan majburlash mumkin |
| Yurak urishi | o'sha faylda `_andon_session` | Kromka Pico'si 3 soniya BUYRUQ ko'rmasa hodisalarni RAM ga yig'a boshlaydi — unga har soniyada `HB`, prisadkaga 5 soniyalik `PING` |
| Kalit | `_kromka_xbxq`, `_kromka_kalit` | v1.22 dan kalit Pico'nikidir: `xb` (yonish belgisi) → `session`, `xq` → `seq`. Undan oldingi proshivkada agent o'zi beradi (har ulanishda yangi sessiya). Ikkala holatda ham serverdagi `(machine_id, session, seq)` unikal indeksi qayta yuborishni tashlaydi |
| Buferdan kelgani | `_kromka_line` | `eski_ms` — hodisa Pico xotirasida qancha kutgani; `ts = hozir − eski_ms`, aks holda tun bo'yi yig'ilgani bitta daqiqaga tiqilardi |
| Qabul | `POST /bridge-agents/andon` (o'sha endpoint) | `AndonEventIn.type` ga kromka turlari qo'shildi: `olchov`, `uskuna`, `tezlik`, `ogoh`, `avariya_toxtash`, `boot`, `tiqilish`. Yangi jadval YO'Q — xom hodisa `andon_event.payload` da |
| Joriy holat | agent har 30 s `HOLAT` so'raydi (`_kromka_holat`) | Kromka `uskuna` ni faqat RUN kirishi O'ZGARGANDA yuboradi — stanok ertalab yoqilib, agent kunduzi ulansa hech narsa kelmasdi. `HOLAT` javobidagi `uskuna` o'sha lahzadagi holat; **o'zgargan bo'lsagina** hodisa yoziladi (`manba: "holat"`), aks holda oraliqlar maydalanardi |
| Oraliqlar | `services/andon.py: uskuna_spans` | Kromka Pico'si holat DAVOMIYLIGINI o'lchamaydi (prisadkadagi `prev_duration_s` yo'q) — oraliq hodisalar orasidan quriladi: `holat=1` → PROCESSING, `0` → OFF. Oxirgi oraliq faqat agent hozir aloqada bo'lsa ochiq qoladi |
| Admin panel | `WorkCenters/KromkaLive` + `GET /machines/kromka-measurements` + WS `kromka.measure` | «Ish markazlari» sahifasi ostida JONLI oqim: detal o'tishi bilan qator chiqadi (vaqt, mm, HUKM, kutilgan o'lcham va farq, detal nomi + chek ID si, stanok), eng yangisi bir marta yashil uriladi. Pico kodi faqat `OK` bo'lmaganda ko'rsatiladi. Bitta partiyadan ko'pi bilan 5 ta xabar tarqatiladi — oflayn agent yuzlab yig'ilganini birdan yuborsa ekran ko'milmasin |
| Terminal | `Terminal/KromkaView: StationStrip` + `GET /terminal/kromka/measurements` | Sarlavha ostida oxirgi o'lchov: `mm`, hukm, kutilgan o'lcham, detal nomi va oldingi 7 tasi. `nomos` kelganda brak oynasi o'zi ochiladi (`routes/terminal.tsx`, WS `kromka.measure`). Stansiyasiz postda umuman chizilmaydi |

Ma'lumot sifatini o'lchash uchun `scripts/kromka_audit.sql` — faqat o'qiydigan SQL
(o'sha `oee_audit.sql` naqshi, 10 bo'lim): qamrov, kunlik sanoq, Pico kodlari taqsimoti
(`OK`/`FARQ`/`FAQAT1`/`FAQAT2`), D1−D2 farqi (median/p90/max), tezlik tarqoqligi, MAYDA
bo'laklar soni, ogohlantirishlar, kunlik ishlagan vaqt, uzilishlar va oxirgi 15 o'lchov.
Qayerda ishga tushirish — fayl boshida.

**Firmware v1.16 (2026-09-21) nimani o'zgartirdi va bizda nima qilindi:**

| Ularda | Bizda |
| --- | --- |
| **`tiqilish` hodisasi**: D1 va D2 dagi vaqtlar bir-biriga mos kelmasa (detallar birga o'tgan yoki biri datchik ostida turib qolgan) soxta o'lcham chiqarilmaydi — `{"ev":"tiqilish","sabab":"birga_otdi"\|"vaqt_mos_emas","n":N,"L2":…,"L1":[…]}` yuboriladi va avariya yonadi | Agent oq ro'yxatiga va `AndonEventIn.type` ga qo'shildi, xom holida `andon_event` ga tushadi; `scripts/kromka_audit.sql` §11 uni sanaydi. **Har tiqilish = o'lchanmay qolgan detal**, ya'ni Performance shuncha kam ko'rsatadi |
| Navbatdagi yozuv endi vaqt bo'yicha TASHLANMAYDI (muddat 5 barobar uzun, datchik ostida detal turganda umuman sanalmaydi) | O'zimizda o'zgarish shart emas: bu aynan biz 2026-09-19 da «avtomatik skanga o'tishdan oldin tuzatilsin» degan nuqson edi — navbat siljib, keyingi o'lchovlar boshqa detalning yozuvi bilan juftlanardi |
| Tezlik nominaldan uzoq chiqsa, uzunlik NOMINAL tezlik bilan hisoblanadi (ilgari o'lchangani ishlatilardi) | O'lchov endi tiqilishdan keyin ham ishonchli; `ogoh: tezlik_nomuvofiq` baribir keladi |
| Stansiya 3 soniya jim qolsa Pico USB ga UMUMAN yozmaydi (CDC buferi to'lib dastur qotmasin), muhim hodisalar RAM ga yig'iladi | Agent har soniyada `HB` yuboradi — bizda o'zgarish yo'q. Foydasi bor: agent to'xtaganda Pico endi qotmaydi |
| Qorovul (WDT 8 s) — faqat stansiya bilan ishlaganda yoqiladi | — |
| Avariya boshlanganda `{"ev":"holat","alarm":1}` keladi, ichida `uskuna` YO'Q | Agentdagi `_kromka_holat` bunday xabarni allaqachon e'tiborsiz qoldiradi (`if "uskuna" not in data`), ya'ni avariya «stanok to'xtadi» bo'lib yozilmaydi |

**1-bosqichga kirmagan**: QR bog'lash, kutilgan o'lcham va MOS/NOMOS verdikti — ular 2026-09-20
da qo'shildi (§4.10). Hali YO'Q: avtomatik skan (o'lchov skan o'rnini bosishi), kalibrlash UI si
va `SET` yuborish (Pico `kal.json` dagi oxirgi sozlama bilan ishlayveradi), sirena/lampa mantiqi.

Tekshiruv (bir martalik skript): **27/27** — ularning sinov bazasidan tiklangan 214 ta HAQIQIY
Pico qatori agent parseridan o'tdi (tur aniqlandi, `seq` uzluksiz, `eski_ms` vaqti tiklandi,
`CHOP` matni tashlandi, prisadka formati buzilmadi), 44 hodisa endpointga qabul qilindi va
takror yuborishda 0 ta yangi yozuv, xom maydonlar (`L`, `kod`) saqlandi, kunlik hisobotda
reja 9 soat / ishladi 7 soat / **Availability 77.8%**, Performance va Quality esa `—`
(Prisadka emas).

Ma'lum cheklov (ularning firmware'ida, bizda emas): shovqin chegarasi hamon VAQT bo'yicha
(`MIN_US = 50 ms` = 10 m/min da 8 mm), ya'ni mayda bo'lak D1→D2 navbatiga tushaveradi.
**Lekin v1.16 dan u zararsiz**: juftlash endi uzunliklarni solishtiradi va mos kelmasa
`tiqilish` beradi — soxta uzunlik chiqmaydi, navbat ham siljimaydi. Avtomatik skanga
o'tishdan oldin chegarani uzunlikka bog'lash hamon foydali bo'lardi (har mayda bo'lak
bekorga avariya yoqadi), lekin endi bu BLOKLOVCHI emas.

Tekshiruv (v1.16 o'zgarishlari, bir martalik skript): **11/11** — `tiqilish` hodisasi agent
oq ro'yxatidan o'tdi va xom holida bazaga tushdi (sabab, `L2`, `L1` ro'yxati), buferdan
kelgani `eski_ms` bo'yicha 30 soniya orqaga surildi, avariya xabari (`alarm=1`, `uskuna`siz)
soxta «to'xtadi» hodisasi yasamadi, firmware versiyasi `1.16` deb o'qildi, server hammasini
qabul qildi.

**Firmware v1.19–v1.22 (2026-09-22…24) nimani o'zgartirdi va bizda nima qilindi:**

| Ularda | Bizda |
| --- | --- |
| **v1.19 — navbat sig'imi masofadan hisoblanadi** (`D / 150 mm + 4`, ko'pi bilan 40; ilgari qotib qolgan 12 ta edi). Kalta detallar ketma-ket tiqilganda navbat to'lib, eng eski yozuv D2 tasdig'isiz chiqib ketardi (`FAQAT1`) va navbat siljirdi | Bu aynan biz 2026-09-21 da ko'rgan nuqson edi — bitta detal ikki marta (avval xato, keyin to'g'ri) yozilardi. Bizdagi javob (kirish vaqti bo'yicha juftlash, §4.10) o'z kuchida qoladi: u firmware nuqsonini emas, TRANZIT vaqtini hisobga oladi |
| **v1.19 — juftlash chegarasi torroq**: 25% o'rniga 3% yoki kamida 30 mm | 650 va 800 mm detallar endi «bir xil» deb juftlanmaydi, ya'ni soxta uzunlik kamayadi. Bizda o'zgarish shart emas |
| **v1.20 — OVOZ Pico'dan olib tashlandi** (GP16 PWM yo'q, oyoq doim past). Rele har almashganda `{"ev":"sig","r":"avariya\|qr\|test\|idle","on":0\|1,"ms":..}` keladi — tovushni MES o'z dinamigidan, AYNAN shu xabar bo'yicha chalishi kerak | `sig` agent oq ro'yxatiga QO'SHILMADI: u lampa fazasi, OEE yoki o'lchov tarixiga hech narsa qo'shmaydi, har miltillashda bitta hodisa bo'lib `andon_event` ni shishirardi. Tovush bizda YO'Q (stansiya sahifasi ularniki, MES terminali emas) |
| **v1.21 — qayta yuklanish sababi**: `boot` hodisasida `sabab` (`tok` — ta'minot, `wdt` — qorovul yoki qo'lda `reset`), `HOLAT` javobida esa `sabab` va `up` (yonganidan beri, ms) | Xom holida `andon_event.payload` ga tushadi (`extra="allow"`) — sxemaga tegilmadi. Kromka Pico'si kunduzi `wdt` bilan qayta yonsa, buni endi bazadan ko'rish mumkin |
| **v1.22 — hodisalar TASDIQ bilan**: `olchov`, `ogoh`, `avariya_toxtash`, `tiqilish`, `uskuna`, `boot` har biri `xb` (yonish belgisi, 8 hex) va `xq` (shu yonishdagi raqam) oladi va `ACK <xb> <xq…>` kelmaguncha RAM da qoladi (300 tagacha), har 5 soniyada 40 tagacha qayta yuboriladi | Agent **1.8.0**: kalit endi Pico'niki — `xb` → `session`, `xq` → `seq` (`_kromka_xbxq`). Qayta yuborilgani navbatga TUSHMAYDI (`seen` dan past), tasdiq esa FAQAT server 200 qaytargandan keyin beriladi (`_kromka_acked` → `_kromka_ack`), ya'ni internet uzilgan paytdagi o'lchov Pico'da ham o'chib, bizda ham yozilmay yo'qolmaydi. Yangi `xb` — hisob noldan. Eski proshivka avvalgidek agent kalitida ishlayveradi |

⚠️ **Agent 1.8.0 dan pastini v1.22 Pico bilan ishlatib bo'lmaydi**: u `ACK` yubormaydi, Pico
esa har 5 soniyada qayta yuboraveradi — agent har takrorni YANGI hodisa deb yozardi (bitta
o'lchov daqiqada 12 marta), Performance ham, o'lchov tarixi ham shishib ketardi.

**Bu prodda ro'y berdi.** Pico v1.22 ga 2026-09-24 10:16 da o'tgan (ularning stansiya
bazasidagi `boot` yozuvi: `"ver": "1.22"`, `"sabab": "wdt"`), prod agenti esa 1.7.1 edi —
«Ish markazlari» sahifasida bitta o'lchov (2026-09-24 18:40:12, 821.2 mm) 18 marta chiqdi.
O'sha kunlarda yig'ilgani **`scripts/kromka_dedup.sql`** bilan tozalanadi: kalit — Pico'ning
o'z `xb`/`xq` si, ya'ni takrorlik taxmin emas; har guruhdan eng birinchi yozuv qoladi,
qolgani YUMSHOQ o'chiriladi (`is_deleted`), `xb`/`xq` siz eski yozuvlarga tegilmaydi.
`-v faqat_hisobot=1` bilan avval faqat sanab ko'rsatadi.

Tekshiruv (v1.19–v1.22, bir martalik skript): **15/15** — Pico takror yuborgan ikkita o'lchov
navbatga bir marta tushdi, kalit `xb`/`xq` dan olindi, `boot` dagi `sabab: wdt` saqlandi,
`sig` va `yigilgan` yozilmadi, server yozmaguncha `ACK` yo'q, server yozgach bitta qator
(`ACK a1b2c3d4 1 2 3`) ketdi va ikkinchi marta takrorlanmadi, yangi `xb` da hisob noldan
boshlandi, `xb`/`xq` siz eski hodisaga agent o'zi kalit berdi; server partiyani ikki marta
olganda 3 accepted / 3 duplicates.

### 4.9 Kromka Performance (2026-09-20)

```
ideal vaqt (bitta o'tish) = L / v + oraliq
Performance               = Σ ideal vaqt ÷ ishlagan vaqt
```

Prisadkadagi kabi TAXMINIY koeffitsiyentlar to'plami kerak emas: kromkada mahsuldorlikni
lenta belgilaydi, `L` ni stansiyaning o'zi o'lchaydi, `v` ni (10/18 m/min) Pico yuboradi.
Sozlanadigan yagona qiymat — **detallar orasidagi bo'shliq** (`gap_s`, sukut 3 s): operator
keyingi detalni qo'yguncha ketadigan vaqt. Tizim sozlamalari → «Ideal sikl» → «Ideal sikl
(Kromka)» (`GET/PUT /settings/ideal-cycle-kromka`, kalit `ideal_cycle_kromka`).

| Qoida | Nega |
| --- | --- |
| Manba — STANSIYA o'lchovlari (`andon_event`, `kind='olchov'`), skanlar emas | o'lchov lentaning o'ziga bog'langan; skan esa odam harakatiga — operator kech skanerlasa Performance tushib ketardi |
| Har QIRRA alohida o'tish | to'rt qirrali detal to'rt marta o'tadi va to'rtalasi sanaladi — stanok rostdan shuncha ish qilgan (Prisadkadagi «bitta detal = bitta sikl» emas) |
| Faqat KUZATILGAN ish vaqtidagi o'tish | Prisadkadagi bilan bir xil qoida: ma'lumotsiz vaqt `run_s` ga kirmaydi, o'sha paytdagi detal ham sanalmasin |
| O'lchamsiz yoki tezliksiz hodisa tashlanadi | `FAQAT1/FAQAT2` da uzunlik bo'lishi mumkin, lekin `L` yo'q bo'lsa ideal vaqtni hisoblab bo'lmaydi |
| Kromkada Quality ham hisoblanadi (§4.11), ya'ni OEE to'liq | birlik ikkala tomonda ham QIRRA O'TISHI: kromkada bitta skan = bitta qirra (`per_instance`), o'lchov ham qirra bo'yicha keladi |
| `gap_s` o'zgarsa o'tgan kunlar qayta hisoblanadi | ideal vaqt saqlanmaydi — kalibrlashda butun tarix birdan to'g'rilanadi |

Tekshiruv (bir martalik skript, haqiqiy Postgres): **10/10** — 2000 mm @ 18 m/min bitta
o'tish 9.67 s; 200 o'tish sanaldi (smenadan oldingi, ma'lumotsiz vaqtdagi va o'lchamsiz
hodisalar sanalmadi); ideal 1933 s, ishladi 8 soat, Performance 6.7%; `gap_s` 3 → 6 qilinganda
ideal 2533 s ga o'sdi; Quality va OEE `—` bo'lib qoldi.

### 4.10 Kromka: o'lchovni detalga bog'lash (2026-09-20)

Stansiya uzunlikni o'lchaydi, lekin QAYSI detal ekanini bilmaydi. Bog'lash modeli —
**kirish lahzasi**: detal birinchi datchikka kirgan payt hisoblanadi
(`kirish = o'lchov vaqti − ish_ms`, `ish_ms` — Pico bergan D1→D2 yurish vaqti) va shu
lahza atrofidagi skanlar nomzod bo'ladi (`kromka_bind_window_s`, sukut ±20 s). Nomzodlar
ichidan O'LCHAMGA mos keladigani tanlanadi. «Joriy detal» degan alohida holat
saqlanmaydi — terminal qulasa yoki agent qayta ulansa ham skan bazada turaveradi.

> **Nega «oxirgi skan» emas (2026-09-21).** Prodda har detal ikki marta chiqdi: avval
> «mos emas», keyin «mos». Sabab — vaqt siljishi: detal datchiklar orasida 8–15 soniya
> yuradi (2553 mm, 10 yoki 18 m/min), operator esa 4–10 soniyada bir marta skanerlaydi,
> ya'ni endi kelgan o'lchov 2–4 ta skan OLDINGI detalniki. Xatoni stansiya egasi topdi va
> yechimini yozib berdi (`docs/onlayn_mes_hodisalar.md` o'z repolarida). Nomzod topilmasa
> o'lchov **brak deb belgilanmaydi** — `skanersiz` bo'ladi: bu ko'pincha juftlash xatosi,
> detal nuqsoni emas.

**Tomonlar guruh bo'yicha sanaladi, nom bo'yicha emas.** 430×520 detalning t/b qirrasi
520 mm, l/r qirrasi 430 mm; kutilgan to'plam — `{520, 520, 430, 430}` (`Part.edges` dan,
lentalanmaydigan tomon umuman kirmaydi). Bir xil uzunlikdagi ikki qirrani o'lchov ajrata
olmaydi va ajratishi SHART EMAS — ikkalasi ham lentalanadi. **Tartib ahamiyatsiz:**
operator qaysi tomonni oldin qo'ysa, o'sha guruhdan bitta joy yopiladi.

| Hukm | Qachon | Nima bo'ladi |
| --- | --- | --- |
| `mos` | guruhda bo'sh joy bor va \|o'lchangan − kutilgan\| ≤ dopusk | qirra yopiladi, tasmada «kutilgan 520» ko'rinadi |
| `ortiqcha` | o'lcham to'g'ri, lekin o'sha guruh kvotasi tugagan | faqat OGOHLANTIRISH: qayta lentalash normal hodisa, brak emas |
| `nomos` | hech bir guruhga dopusk ichida to'g'ri kelmadi | **hozircha hech narsa qilmaydi** — faqat ekranda ko'rinadi (quyidagi «Datchik ishonchsiz» bandiga qarang) |
| `shubhali` | Pico kodi `OK` emas (FARQ/FAQAT1/FAQAT2) yoki detalning o'lchami/qirra ro'yxati yo'q | hukm chiqarilmaydi — datchikka ishonib detalni ayblab bo'lmaydi |
| `skanersiz` | oyna ichida skan yo'q | tarixga yoziladi, hech kimni ayblamaydi |

Kvadratga yaqin detalda ikkala guruh ham dopuskka tushishi mumkin — bo'sh joyi bori
tanlanadi: operator o'lchov ajrata olmagan joyda ishni to'xtatib turgandan ko'ra qirrani
yopgani to'g'riroq.

**Sozlamalar** (Tizim sozlamalari → «Brak sabablari» → «Kromka o'lchovi»):
`kromka_tolerance_mm` (dopusk, sukut 3 mm, 1..50) — lenta detalni HARAKATDA o'lchaydi,
nol dopusk har detalni brak qilardi; `kromka_bind_window_s` (bog'lash oynasi, sukut **20 soniya**,
5..600) — kirish lahzasidan shuncha soniya oldin/keyin yozilgan skanlar nomzod bo'ladi.
Oyna ikki tomonlama: operator detalni lentaga qo'ygandan keyin ham skanerlashi mumkin.

> **Datchik ishonchsiz (2026-09-20).** Tsexda stansiya uzunlikka qarab xato o'lchayotgani
> aniqlandi, ya'ni `nomos` hukmining o'zi noto'g'ri bo'lishi mumkin. Shuning uchun
> **avtomatik brak O'CHIRILDI**: `nomos` na brak qaydini ochadi, na terminalda oyna
> chiqaradi. Brak faqat operator skandan keyin BRAK tugmasini bosganda yoziladi.
> O'sha paytgacha yozilgan avtomatik qaydlar `d4b8e1f37c92` ko'chirishida yumshoq
> o'chirilgan (faqat tasdiq kutayotganlari — menejer ko'rgan qarorga tegilmagan).
> O'lchov hozir KUZATUV: raqam, kutilgan o'lcham va farq ekranda ko'rinadi — aynan shu
> ko'rsatkichlar datchikni to'g'rilashda kerak bo'ladi. Datchik to'g'rilangach avtomatik
> brakni qaytarish uchun `services/kromka.py` dagi `_auto_defect` tiklanadi.

Hukm `kromka_measurement` jadvalida (xom hodisa `andon_event` da o'zgarmasdan qoladi),
mantiq `services/kromka.py` da, chaqiruv joyi — agent partiyasi qabul qilinadigan
`POST /bridge-agents/andon`. Faqat YANGI hodisalar bog'lanadi: agent partiyani qayta
yuborsa kvota ikkinchi marta yopilmasin.

Tekshiruv (bir martalik skript, haqiqiy Postgres, haqiqiy endpointlar): **23/23** —
eni birinchi o'tsa ham mos; 1.5 mm farq dopusk ichida; to'rt qirra yopilgach beshinchi
o'tish `ortiqcha`; 300 mm `nomos` va eng yaqin kutilgan (430) ko'rsatildi; ikki tomonli
detalda eni o'lchovi `nomos`; `FAQAT1` — `shubhali`; oynadan tashqaridagi va bekor
qilingan skan bog'lanmadi; takror partiya kvotani qayta yopmadi; terminal tasmasi va
admin oqimi hukm, detal nomi va kutilgan o'lchamni qaytardi. **Hal qiluvchi band:**
operator har 5 soniyada bitta detal skanerlagan, lenta esa har detalni 15 soniyada
o'tkazgan holatda to'rtala o'lchov O'Z skaniga bog'landi — bittasiga yopishib qolmadi.

### 4.11 Kromka Quality (2026-09-20)

```
Quality = (qirra o'tishlari − brak) ÷ qirra o'tishlari
```

Prisadkadagi formulaning AYNAN o'zi, faqat birlik boshqa: kromkada ish birligi detal emas,
**qirra o'tishi**. Maxraj — stansiya o'lchagan o'tishlar (Performance bilan bitta manba),
surat — o'sha o'tishlardagi brak. Ikkalasi bir xil birlikda, chunki KROMKA qadamida
`per_instance` = qirralar soni: operator har qirrani alohida skanerlaydi va `part_defect`
har skanga bittadan yoziladi.

**Brak qayerdan keladi.** Hozir bitta yo'l:

1. **Operator qo'lda** — skan tasmasidagi BRAK tugmasi (§4.7), prisadkadagi kabi. **Hozir
   YAGONA yo'l shu.**
2. ~~Stansiya o'zi (`nomos` o'lchov)~~ — 2026-09-20 da O'CHIRILDI: datchik uzunlikka qarab
   xato o'lchaydi, ya'ni avtomatik qaydlar soxta chiqdi (§4.10 dagi izoh). Datchik
   to'g'rilangach qaytariladi.

Yakuniy hakam — **menejer**: rad etilgan qayd Quality'ga kirmaydi, ya'ni soxta signal
(datchik shovqini, noto'g'ri bog'langan skan) hisobni buzmaydi.

| Qoida | Nega |
| --- | --- |
| Braklangan o'tish maxrajda QOLADI | ish qilingan (vaqt ketgan), mahsulot yaroqsiz — aks holda brak ikki marta jazolanardi (§4.7 dagi bilan bir xil qoida) |
| Bitta o'tishga bitta qayd | qirra ikki marta brak bo'lib Quality qo'sh tushmasin (`scan_id` bo'yicha tekshiriladi) |

Tekshiruv (bir martalik skript, haqiqiy Postgres, haqiqiy endpointlar): **18/18** — 10 nusxa ×
4 qirra = 40 o'tish, bittasi 300 mm bo'lib chiqdi: brak qaydi OCHILMADI (hukm esa yozildi va
o'sha skanga bog'landi), Quality 100%; operator BRAK tugmasini bosgach 40 o'tish / 1 brak /
**Quality 97.5%**, Availability 88.9%, OEE = A×P×Q; menejer rad etgach brak 0 va Quality 100%;
qo'lda qo'yilgan eski avtomatik qayd `d4b8e1f37c92` ko'chirishidan keyin brak ro'yxatidan ham,
Quality hisobidan ham chiqib ketdi.

### 4.12 OEE qaysi kundan hisoblanadi (2026-09-20)

Sozlamalar to'liq kiritilgunicha yig'ilgan qayd OEE ni pastga tortadi: ish jadvali yo'q kunda
reja vaqti 0, yarim ulangan stansiyada o'tishlar sanalmaydi, sinov ma'lumoti esa umuman ish
emas. Shuning uchun **kesim sanasi** bor: `oee_start_date` (Tizim sozlamalari → «Ish jadvali»
→ «OEE qaysi kundan hisoblanadi», `GET/PUT /settings/oee-start`).

- Undan oldingi kunlar «Stanok vaqti» hisobotiga **umuman kirmaydi** — qatorlar ham, kunlik
  yoyilma ham, Excel ham. So'ralgan oraliqning boshi kesimga **surib qo'yiladi**.
- Butun oraliq kesimdan oldin bo'lsa — bo'sh hisobot (xato emas).
- **Ma'lumot O'CHIRILMAYDI**: `andon_event`, `downtime`, `scan`, `part_defect` joyida qoladi;
  kesim faqat HISOBGA ta'sir qiladi va istalgan payt orqaga surilsa hamma narsa qaytadi.
- Bo'sh qiymat — cheklov yo'q (butun tarix), sukut holat shu.
- Hisobot sahifasi kesim qo'yilganda buni ochiq yozadi, aks holda «kecha ishlagan edik-ku»
  degan savol javobsiz qolardi.

Tekshiruv (bir martalik skript, haqiqiy Postgres): **15/15** — bir xil ikki kun (14 va
15-sentabr); kesimsiz 2 kun / 20 o'tish / reja 18 soat, kesim 15-sentabrga qo'yilgach 1 kun /
10 o'tish / reja 9 soat va `date_from` 15-sentabrga surildi; butunlay kesimdan oldingi oraliq
bo'sh hisobot qaytardi; kesim olib tashlanganda ikkala kun qaytdi.

### 4.13 ROVER (CNC 2130) — kuzatuv (2026-09-20, 1-bosqich)

Uchinchi Pico turi. Firmware ularniki (`jasper2233/cnc2130-oyy-mes`) va **tegilmaydi** —
moslashish agent tomonda. Undan oldingi ikkitasidan asosiy farqi: bu Pico **ikki
tomonlama** ishlaydi va gapirish uchun kompyuterni eshitishi kerak.

| Signal | Nimani bildiradi |
| --- | --- |
| `S_PWR` | stanok tarmoqqa ulangan (24 V, asosiy kalit orqasidan) |
| `S_RUN` | chastotnikning «ishlamoqda» chiqishi — **shpindel aylanyapti** |
| `S_HOME` | stanok 0 nuqtada (induktiv datchik) |
| `S_MAINT` | shkafdagi ta'mirlash kaliti — avtomatik o'chirishni bloklaydi |

Agent uchta narsani qiladi: har 10 soniyada **kompyuter vaqtini** yuboradi (Pico'da
soat moduli yo'q va 30 s jim qolsa u hodisalarni fleshga yig'a boshlaydi), server
yozgandan KEYIN **`ack`** qaytaradi, ulanishda bir marta **sozlama** yuboradi.

| Qoida | Nega |
| --- | --- |
| `ack` faqat server yozgach | erta tasdiqlansa, internet uzilgan paytdagi hodisa Pico'da o'chib, bizda ham yozilmay yo'qolardi |
| `run` o'zgarishi — kromkadagi BIR XIL `uskuna` hodisasi | to'xtash, bo'sh yurish va Availability zanjiri qayta yozilmaydi (`services/downtimes.py`) |
| Bir xil holat qayta yozilmaydi | `state` har 10 soniyada keladi: kuniga 8000 dan ortiq bir xil qator bazaga tushardi |
| Pico hodisasi xom holida saqlanadi (`kind="rover"`, asl turi `payload.rover_type`) | `POWER_ON`/`SPINDLE_IDLE`/`AUTO_SHUTDOWN` davomiyliklari Pico'ning o'z hisoblagichidan — agent o'chiq turgan davr uchun yagona manba |
| Takror kelgan hodisa navbatga bir marta tushadi | tasdiq kelmaguncha Pico uni har 10 soniyada qayta yuboradi |
| `t_reason` = 300 s yuboriladi | MES dagi umumiy chegara bilan bir xil; Pico'ning sukut qiymati (15 daqiqa) bilan undan qisqa to'xtash umuman yozilmasdi |
| `auto_shutdown` = **o'chiq** | rele stanokni o'chiradi: avval tsexda qancha bo'sh turish yig'ilayotgani ko'riladi, taymerlar real ritmga moslanadi (docs/12 §6) |

**Hozircha YO'Q:** rele (avtomatik o'chirish), ish markazi darajasidagi sozlama
paneli, rover hodisalaridan to'xtash yasash (sabab bizning `uskuna` zanjiridan
so'raladi — ikki manba bo'lsa operatordan bitta narsa uchun ikki marta so'ralardi),
`start_job`/`planned_stop` buyruqlari.

**Ma'lum cheklov:** agent o'chiq turgan davrda `state` kelmaydi, ya'ni o'sha vaqt
hisobotda «stanok o'chiq» bo'lib qoladi — Pico'ning o'zi esa o'sha davrni `POWER_ON`
hodisasi bilan bergan bo'ladi. Ikkalasini birlashtirish keyingi bosqichda.

Tekshiruv (bir martalik skript, haqiqiy Postgres): **23/23** — ULARNING firmware'i
kompyuterda yurgizildi (soxta `machine`/USB), chiqqan qatorlar BIZNING agent
parseridan o'tdi, natija haqiqiy `POST /bridge-agents/andon` handleriga berildi:
tur ROVER deb aniqlandi (kromka deb emas), sozlama bir marta ketdi va Pico uni
QABUL QILDI (300 s dan qisqa 200 s lik to'xtash hodisa bermadi, 360 s lik berdi),
`run` o'zgarishlari `uskuna` bo'lib yozildi (`0·1·0·1·0`), takror yuborilgan hodisa
navbatga bir marta tushdi, `POWER_ON` va `SPINDLE_IDLE` xom maydonlari bilan bazaga
tushdi, takror partiya 0 ta yangi yozuv berdi, RUN tushishidan to'xtash yozildi,
tasdiq esa FAQAT server yozgandan keyin va bir marta ketdi.

### 4.14 Orakllar qayerda turadi (2026-09-25)

Loyihada test yo'q (ataylab), ya'ni xulq haqidagi har bir da'vo bir martalik
SKRIPT bilan tasdiqlanadi. Ilgari ular `/tmp` da yozilardi va macOS tozalashi
ularni ikki marta yeb ketdi — OEE bo'yicha yig'ilgan hamma tekshiruv yo'qoldi.
Endi ular repoda: **`scripts/oracles/`** (CI ularni CHAQIRMAYDI — bu test to'plami
emas; yurgizish va ro'yxat — `scripts/oracles/README.md`).

| Skript | Qaysi bo'lim |
| --- | --- |
| `oee_oracle.py` (31/31) | §4.1, §4.5-4.7, §4.9, §4.12 — A/P/Q/OEE, tanaffus, to'xtash chegarasi, bo'sh yurish, kesim sanasi, rejaning hozirgacha kesilishi |
| `kromka_bind_oracle.py` (23/23) | §4.10 |
| `kromka_v116_oracle.py` (11/11) | §4.8 |
| `kromka_v122_oracle.py` (15/15) | §4.8, proshivka v1.19-v1.22 |
| `rover_oracle.py` (19/19) | §4.13 |
| `tablo_machines_oracle.py` (29/29) | `docs/05` — stanok taxtasi |
| `kromka_dedup_oracle.py` (17/17) | `scripts/kromka_dedup.sql` — v1.22 takrorlarini tozalash |

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
  2. **Stanok to'xtasa** — turidan QAT'I NAZAR (qizil/avariya, hamma chiroq o'chgani, sariq,
     kromka yoki rover lentasining to'xtashi) Tizim sozlamalaridagi «Uzoq to'xtash, daqiqa»
     (`stop_prompt_idle_minutes`, sukut 5, 1..120) o'tgach. Vaqtni SERVER to'xtash boshlangan
     paytdan sanaydi — Pico `idle_timeout_s` ga bog'liq emas, chegarani o'zgartirish uchun
     Pico'ga tegilmaydi.
  **2026-09-20 da o'zgardi:** ilgari qizil chiroq va «hamma chiroq o'chiq» DARHOL so'rardi.
  Tsexda bir daqiqalik kutishda ham oyna chiqib turgani uchun qoida bitta bo'ldi: hamma
  to'xtash bir xil chegaradan o'tadi. Qisqa to'xtash hisobdan chiqmaydi — faqat sababi
  so'ralmaydi.
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
