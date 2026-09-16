# 12 — OEE (Prisadka): holat, bajarilgan ishlar va reja

Holat: **2026-09-16**. OEE hali hisoblanmaydi — bu hujjat poydevor qayerda turganini,
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
| To'xtash sababi | — | ❌ yo'q (ro'yxat ham, kiritish joyi ham) |
| Detallar soni | MES skanlari (`scan`) + Pico sikllari | ✅ bor, o'zaro deyarli mos (§5) |
| Ideal sikl vaqti | `part.xnc_summary` (teshik/paz/freza) + koeffitsiyentlar | ❌ koeffitsiyentlar yo'q |
| Brak | — | ❌ yo'q |

## 2. Tarix

- **2026-08-21** — birinchi OEE moduli qurildi (qo'lda "To'xtash"/"Brak" tugmalari, ish markazida
  `planned_minutes_per_day`/`ideal_rate`, `stop_reason`/`machine_stop`/`defect` jadvallari) va o'sha
  kuni **qaytarildi** (`066cd22`): 1366×768 monoblokda terminal ustuniga tugmalar sig'madi, egasi
  "hozircha kerak emas" dedi. Migratsiyalari prodda qolgan, jadvallar `LEGACY_TABLES`/`LEGACY_COLUMNS`
  da (docs/04 §4.4). **Xulosa: operator ekraniga tugma qo'shilmaydi** — hamma kiritish web orqali.
- **2026-09-13..14** — andon: Pico stanok chiroqlarini o'qiydi, MES agent v1.5.0 USB orqali olib
  `POST /bridge-agents/andon` ga yuboradi → `andon_event` (xom hodisalar) + Redis jonli holat;
  "Ish markazlari" sahifasida jonli holat, "Hisobotlar → Stanok vaqti" (VAQTINCHALIK, OEE emas).
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
2. **Smena** — Prisadkadagi 2026-09-05 dan ochiq smenani yopish, smena ochish tartibini hal qilish.
3. **Chiroq tasnifi** — tsexda yashil miltillash davrini o'lchash, firmware `MIN_STATE_MS` /
   `BLINK_WINDOW_MS` ni moslash; `idle_timeout_s` ni mikro-to'xtash chegarasi bilan bir xil qilish.
4. **To'xtash sabablari** — ro'yxat (nom, rejali/rejasiz, qaysi holatga mos, izoh majburiymi) va
   web sahifa: Pico ochgan har to'xtash avtomatik yoziladi, usta sababni tanlaydi; ish vaqtidan
   tashqaridagi OFF avtomatik "Smena tugadi".
5. **Availability hisoboti** — ish jadvali + to'xtashlar; "Stanok vaqti" tab'i o'rniga.
6. **Performance** — skan↔sikl FIFO bog'lash (prototip `mes/bridge.py` mantiqi), ideal sikl
   formulasi: yuklash + teshik × s + paz × s + freza × s, koeffitsiyentlar 2–4 hafta ma'lumotdan.
7. **Quality** — brak qaydi (sabab, aybdor post).

## 7. Ochiq qarorlar

- Egasining to'xtash sabablari fayli (`oee to'xtalishlar.xlsx`) va ularning qaysilari rejali.
- Mikro-to'xtash chegarasi (tavsiya: 5 daqiqa).
- Sababni kim va qachon kiritadi (tavsiya: usta, web, kun oxirida).
- Ideal sikl: formula (tavsiya) yoki bitta raqam.
- Brak qanday aniqlanadi va kim yozadi; birinchi bosqichda Quality kerakmi.
- Maqsad OEE foizi (tablo/hisobot rangi uchun).

## 8. Xavflar

- **Sabablar kiritilmasa** "sababsiz" to'xtashlar ko'payadi va Pareto ma'nosiz bo'ladi —
  ma'sul shaxs va kunlik eslatma kerak.
- **Qamrov** tuzatilmasa noma'lum vaqt stanok aybi bo'lib ko'rinadi — noma'lum alohida ko'rsatiladi,
  hech qachon taxmin qilinmaydi.
- **Chiroq tasnifi** noto'g'ri bo'lsa Performance buziladi.
- **Ikki repo shartnomasi** — firmware hodisa formatini o'zgartirsa MebeliX jimgina buziladi
  (hodisalarda versiya maydoni yo'q); o'zgarish ikkala tomonda birga qilinadi.
- **Operator ekrani** — o'tgan OEE aynan tugmalar sig'magani uchun qaytarilgan; terminalga hech
  narsa qo'shilmaydi.
- **Talqin** — signal ustuni faqat Prisadkada: bu "Prisadka OEE", tsex OEE emas.
