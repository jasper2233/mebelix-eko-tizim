# 12 — OEE (Prisadka): holat, bajarilgan ishlar va reja

Holat: **2026-09-17**. OEE hali hisoblanmaydi — bu hujjat poydevor qayerda turganini,
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
| Ideal sikl vaqti | `part.xnc_summary` (teshik/paz/freza) + koeffitsiyentlar | ❌ koeffitsiyentlar yo'q |
| Brak | — | ❌ yo'q |

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
| Hisob | `services/downtimes.sync_machine` | qizil (FAULT) va OFF — darhol; sariq (IDLE/STOPPED) — `stop_prompt_idle_minutes` dan uzoq bo'lsa, vaqt sariq yongan paytdan. Idempotent, sabab qayta hisobda tegilmaydi |
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

Sahifada: Availability jadvali (reja vaqti, ishladi, rejasiz to'xtash, ma'lumot yo'q, rejali to'xtash, qamrov, foiz),
to'xtash sabablari bo'yicha taqsimot (sababsizi alohida qator), kunlik trek yonida kun foizi; eski chiroq holatlari jadvali
va to'xtashlar ro'yxati pastda qoldi. Ish jadvali kiritilmagan bo'lsa qizil izoh chiqadi va foiz hisoblanmaydi.

Tekshiruv (bir martalik skriptlar, repoda saqlanmaydi): sof funksiyalar 31/31 — qo'lda hisoblangan kun (67.4%),
tungi smena va yarim tun bo'linishi, dam olish kunidan oldingi/keyingi smena, mikro-to'xtash, oraliq chegarasidagi
to'xtash, «hozir»gacha kesish, jadvalsiz holat; haqiqiy handler PGlite'da 18/18 — rejali sabab reja vaqtidan
chiqishi, LOCK sababi e'tiborsiz qolishi, jim stanok 0%, Pico'siz stanok kirmasligi, Excel; sahifa headless
Chrome'da 14/14 — sonlar backend javobi bilan bir xil, 1366 va 700 px'da toshmaydi.

Cheklov: chegara (`stop_prompt_idle_minutes`) o'zgartirilsa o'tgan kunlar ham yangi chegara bilan qayta hisoblanadi
(to'xtashlar saqlanmaydi, har safar hodisalardan chiqariladi).

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
6. **Performance** — skan↔sikl FIFO bog'lash (prototip `mes/bridge.py` mantiqi), ideal sikl
   formulasi: yuklash + teshik × s + paz × s + freza × s, koeffitsiyentlar 2–4 hafta ma'lumotdan.
7. **Quality** — brak qaydi (sabab, aybdor post); belgilovchi — smenada ishlayotgan hodim (§7).

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
- **Brak oqimi:**
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

### Ochiq

- Mikro-to'xtash chegarasi — Tizim sozlamalarida (sukut 5 daqiqa), tsexda sinab moslanadi.
- Juda qisqa avariyalar (prod median 12 s) ham so'ralsinmi yoki chegara qo'yilsinmi.
- Ideal sikl: formula (tavsiya) yoki bitta raqam.
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
