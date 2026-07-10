# MebeliX MES — Implementatsiya TODO

TT manba: `docs/Mebelix_MES_TZ_v2.2.docx`. Arxitektura: `docs/01..08-*.md`.
Har faza tugagach: lint + mypy + migratsiya + client regen o'tishi shart. Ushbu fayl har qadam yangilanadi.

## Faza 1 — Data model (backend) ✅ (2026-07-10)
- [x] User modeliga `role` (ADMIN/DIRECTOR/MANAGER/TEXNOLOG/TERMINAL/TABLO) va `machine_id` (terminal/tablo bog'lash)
- [x] Organization (multi-tenant tayyor sxema, bitta org)
- [x] Post (6 bosqich: ARRA, KROMKA, PRISADKA, PAZ, ROVER, STOLYARKA; unit, order_index, flaglar) + seed
- [x] Machine (post FK, ip, capacity, status)
- [x] Employee (badge_id UUID, assigned_post_ids, status)
- [x] Client (jismoniy/yuridik, telefon, INN)
- [x] Material (sheet/band/hardware, avtomatik to'ldiriladi)
- [x] Order (status: DRAFT→TECHNICAL_REVIEW→PRODUCTION→COMPLETED→DELIVERED, CANCELLED; number B-YYYY-NNN)
- [x] Product / Part / PartInstance (QR: productCode_partCode_n) / PartRoute (bosqich qoldiqlari)
- [x] Scan (client_event_id idempotency, cancel), WorkSession (beyjik smena)
- [x] OrderFile (project/scx/pdf), AuditLog
- [x] Alembic migratsiya `1393a241b793` + seed (`app/commands/seed_defaults.py`, prestart/setup ga ulandi)

## Faza 2 — Backend domen API ✅ (2026-07-10)
- [x] Rol-based deps (`require_roles`, ManagerUser/TexnologUser/StaffReadUser/AdminUser)
- [x] CRUD API: clients (orders_count bilan), employees (beyjik regen), machines, posts, materials
- [x] Users API: role + machine_id maydonlari
- [x] Orders API: yaratish (B-YYYY-NNN retry bilan), reestr (status/search), kartochka (fayllar, countlar), bekor qilish, TOPSHIRILDI, matritsa (o'qish+texnolog tahriri), stanok biriktirish, submit-review, start (PRODUCTION)
- [x] Audit log yozish (log_action, tranzaksiya ichida) + ro'yxat API (filtrlar)
- [x] Smoke-test: login→CRUD→order lifecycle in-process ✅

## Faza 3 — File processor (parser) ✅ (2026-07-10) — `app/services/giblab/`
- [x] .project XML parse (to'la parser, regex YO'Q; windows-1251/UTF-8; 2 avlod: PROCESSED/TEMPLATE)
- [x] Kontekstli id qidiruv (good/operation/part alohida fazolar)
- [x] XNC merge (detalda 2 tagacha, program atribut ham bola element ham), bosqich aniqlash (bf/bt/bb/bl/br→PRISADKA, gr→PAZ, ms/ml/mac→ROVER)
- [x] Marshrut hisoblash (KROMKA tomonlar soni, qoldiq = count × tomonlar; XNC bosqichlarda tomon = op soni)
- [x] CS data blob dekoder (base64 big-endian, 15B yozuvlar, guillotine daraxt, dims+117 root-o'q sloti) + 5.7.4 self-check
- [x] CUTMAP JSON modeli (sheets/parts/cuts + holes overlay, rot/eW/eH, atxot foydali o'lcham, instance-cell binding)
- [x] SCX generatsiya (Y_scx = Width − y; var/expr xavfsiz hisoblash; _2 suffiks; Face kodlari ponytail-kalibr)
- [x] Yorliq raqami (num) CS tartibidan (fayl-global); TEMPLATE fayl 422 + aniq ogohlantirish matni
- [x] Upload endpoint (qayta yuklash PRODUCTION gacha, eski natijalar to'liq almashtiriladi) + fayl download endpoint
- [x] Testlar: `backend/tests/test_giblab.py` (sintetik blob enkoderi bilan) + API E2E (upload→matrix→start) ✅

## Faza 4 — Scan engine + sessiyalar + WebSocket ✅ (2026-07-10)
- [x] Beyjik auth (`/terminal/session`, post mosligi, eski smena avtoyopiladi), yakunlash, 12h timeout (E005)
- [x] Scan endpoint (`/scans`): instance-level tekshiruv, E001–E006 kodlari, idempotency (client_event_id unique), strict-order E004 (STRICT_STAGE_ORDER sozlama)
- [x] Bekor qilish 60s oynada (`DELETE /scans/{id}`), qoldiq qaytariladi, COMPLETED regress
- [x] Bosqich/buyurtma yakunlash triggerlari (order.stage_completed → order COMPLETED)
- [x] WebSocket `/ws/events`: JWT (cookie yoki ?token), Redis pub/sub fan-out (`app/core/ws.py`), rol/post/stanok filtrlash, pong heartbeat
- [x] SCX har scanda taqdim etiladi (`scx_file_ids` + `/terminal/files/{id}`); ARRA cutmap holati (`/terminal/orders/{id}/cutmap`), yorliq chop stub (`/terminal/labels/{id}` ARQ print_label)
- [x] E2E sinov: session→tasks→cutmap→scan→replay→undo→stage completion ✅
- Eslatma: 2s cooldown — terminal frontend (Faza 7); EZPL real chop — Faza 9

## Faza 5 — Frontend poydevor + dizayn tizimi ✅ (2026-07-10)
- [x] Dizayn tokenlar: post ranglari (--post-*), status ranglari, `.num` tabular raqamlar, Archivo; imzo element — StagePipeline (6 bosqich zanjiri)
- [x] Rolga qarab routing/sidebar (terminal→/terminal, tablo→/tablo redirect; menyu TZ 3.7 matritsa bo'yicha)
- [x] API client regen (12 servis) + query keys (`queries/mes.ts`)
- [x] Umumiy komponentlar: StatusBadge, StagePipeline, PageHeader; `lib/mes.ts` (uzbek labellar, formatlash)

## Faza 6 — Admin panel modullari (TT 10) — asosiylari ✅ (2026-07-10)
- [x] Dashboard: stanok kartalari (post rangi, holat, quvvat), aktiv buyurtmalar StagePipeline progress, LIVE indikator (WS)
- [x] Buyurtmalar: reestr (7 tab filtr, search), yangi buyurtma modal (mijoz lookup+yangi), kartochka (metadata, fayl yuklash, Tayyor/Uzatish/TOPSHIRILDI/Bekor qilish, fayllar ro'yxati + yuklab olish)
- [x] Texnolog matritsasi (interaktiv: bosqich checkboxlar, ARRA qulflangan, izohlar; progress katakchalar)
- [x] Stanok tanlovi (MachineAssign — requires_assignment_choice postlar)
- [x] Mijozlar, Hodimlar (beyjik QR ko'rish/chop/regen), Stanoklar (+post rang chiplar), Materiallar
- [x] Foydalanuvchilar (rol + terminal/tablo uchun stanok tanlash), Logs, Tranzaksiyalar (modul filtri)
- [ ] Efficiency % / ~tugatish vaqti prognozi (capacity formula) — Faza 9 hisobotlar bilan
- [ ] Kesish xaritasini admin panelda ko'rish + PDF chop (manager/texnolog, TT 10.3) 
- [ ] Excel eksport tugmalari — Faza 9

## Faza 7 — Operator terminali (TT 8) ✅ (2026-07-10)
- [x] /terminal route (rol guard), beyjik UUID → sessiya (bir input: beyjik ham QR ham), sessiya yakunlash
- [x] Asosiy ekran: header (post/stanok/soat), NAVBATDAGI VAZIFALAR (katta QOLDIQ), OXIRGI SKAN (yashil/qizil), TARIX (50, faqat-xatolar filtri), BEKOR QILISH (60s)
- [x] Avto-skan input (doimiy fokus har 2s, SKAN ON/OFF tumbler, lock), 2s cooldown
- [x] Audio (WebAudio 600/200/800Hz — lokal), vizual flash
- [x] ARRA kesish xaritasi: materiallar+statistika (KK/KD/KO/DR/KR/PZ), list kartochkalari (×mult), SVG list (detallar, nom-barqaror rang, tekstura chiziqlari, o'lchamlar+kromka belgilar, teshiklar overlay, kesim chiziqlari, atxot zebra), detal kartochkasi (katta QR + YORLIQ CHOP ETISH + nusxalar holati), ✓ real-time (WS)
- [x] PRISADKA/PAZ/ROVER: scan javobidagi scx_file_ids → avtomatik download
- [x] Offline: WS uzilsa ALOQA YO'Q, scan blok (E007)

## Faza 8 — TABLO (TT 9) ✅ asosiy (2026-07-10)
- [x] /tablo (umumiy + kontekstli: tablo user stanogi ustuni ajratiladi, boshqalari xira)
- [x] Matritsa (buyurtma × 6 bosqich), katakcha holatlari (✓ yashil / progress / qizil BOSHLANMADI muddat o'tganda), backend `/tablo/matrix`
- [x] HAJM/SONI/FOIZ rejimlar (hajm: ARRA m², KROMKA m; PAZ dona — ponytail ceiling), drill-down (detal × bosqich)
- [x] Real-time WS + auto-refresh 5min + OFFLINE indikator
- [ ] JAMI HAJM qatori (yuqori agregat) — keyingi iteratsiya

## Faza 9 — Hisobotlar, chop etish, yakuniy ✅ asosiy (2026-07-10)
- [x] Hisobotlar (`/reports/*`): mahsuldorlik (hodim reytingi, kun/soat o'rtacha), buyurtmalar holati (kechikkanlar, bekor sabablari), material sarfi (`order.material_usage` dan) — hammasi `?format=xlsx` Excel bilan (openpyxl)
- [x] Dashboard prognoz (`/reports/dashboard`): stanok navbati (scan + hajm), ~tugatish soat (TT 4.3 formula), bugungi scanlar — kartalarga ulandi
- [x] EZPL yorliq (`app/services/labels.py`): 80×60, QR (instance), kod/nom/material/o'lcham, kromka qatori, P/S/F ikonkalar, №num; `print_label` ARQ task (PRINTER_IP → TCP, aks holda Redis navbat)
- [x] Bridge-agent (`bridge-agent/agent.py` + README + systemd): outbound WS `/ws/bridge` (BRIDGE_TOKEN), lokal JSONL navbat, printer flusher; E2E sinaldi (job→agent→ack→navbat bo'sh)
- [x] Kesish xaritasi admin ko'rinishi (`/cutmap/$orderId`, TT 10.3) + PDF/chop (window.print + print CSS)
- [x] TABLO JAMI HAJM qatori
- [x] Docs: `docs/09-mes-domain.md` (yangi domen qatlami xaritasi), README jadval yangilandi
- [ ] Qolgan mayda: CSV eksport (audit), hodim mahsuldorlik grafigi (kartochkada), stanok ish tarixi grafigi — keyingi iteratsiya
- Eslatma: yorliq chop uchun ARQ worker shart (`make worker`); SCX/EZPL kalibr real qurilmalarda

## Holat jurnali
- 2026-07-10: TT + docs o'rganildi, TODO yaratildi. Faza 1 boshlandi.
- 2026-07-10: Faza 1–8 asosiylari yakunlandi. Backend: 17 jadval, 60+ endpoint, GibLab parser (blob dekoder testlar bilan), scan engine, WS (Redis pub/sub). Frontend: admin panel (7 modul), terminal (ARRA SVG xarita), TABLO. Gatelar: mypy ✅ ruff ✅ tsc ✅ biome ✅ build ✅ parser testlar ✅ API E2E ✅.
- Muhit: .env yaratildi (lokal, DB=mebelix host postgresda), redis konteyner `mebelix-mes-system_redis_1` ishlamoqda, dev serverlar (8000/5173) fonda.
- Qolgan (Faza 9): hisobotlar+Excel, EZPL yorliq+print queue, bridge-agent, kesish xaritasi PDF, admin cutmap ko'rish, JAMI HAJM, efficiency prognoz, docs yangilash.
- 2026-07-10 (kech): Faza 9 asosiylari yakunlandi — reports+xlsx, EZPL+bridge (E2E ✅), admin cutmap+print, JAMI HAJM, dashboard prognoz, docs/09. MUHIM FIX: eski uvicorn jarayoni WS routelarni bermasdi (stale process) — o'ldirilib qayta ishga tushirildi, /ws/events va /ws/bridge jonli tasdiqlandi. Yangi env: PRINTER_IP/PRINTER_PORT/BRIDGE_TOKEN.
