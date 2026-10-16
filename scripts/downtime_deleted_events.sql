-- =============================================================================
-- MebeliX — yumshoq o'chirilgan andon hodisalaridan yasalgan TO'XTASHLAR (TODO.md #15).
--
-- NIMA BO'LGAN. `services/downtimes.sync_machine` 2026-10-16 gacha `andon_event`
-- ni `is_deleted` filtrisiz o'qirdi. `scripts/kromka_dedup.sql` yumshoq o'chirgan
-- v1.22 takrorlari (prodda ~258 ming) ham to'xtash yasagan. Hisobot ("Stanok
-- vaqti") ularni filtrlaydi, ya'ni terminal hisobotda YO'Q to'xtashga sabab
-- so'ragan, ochiq qolgani esa hisob oynasini (`since`) orqaga tortgan.
--
-- QACHON ISHLATILADI — FAQAT TUZATISH DEPLOY QILINGANDAN KEYIN. Eski kod
-- ochiq yozuvni har 5 daqiqada (`sync_downtimes`) qayta OCHADI
-- (`ended_at = NULL`), ya'ni deploy'dan oldin yopish befoyda.
--
-- Ikkinchi manba (2026-10-16 Rover OEE deploy'i): ROVER stanogida har bo'sh turish
-- IKKINCHI `idle-*` yozuv bo'lib tushgan, 3 daqiqalik pauza ham — tuzatish keyingi
-- deploy'da (`_bosh_yurish` endi faqat ishlayotgan oraliqni bo'ladi).
--
-- NIMA QILADI. Shu ikki manbadagi soxta `downtime` yozuvlari (`soxta` ko'rinishi):
--   - sababi KIRITILMAGAN — yumshoq o'chiriladi (soxta to'xtash, terminal ham,
--     tablodagi «sababsiz» soni ham uni boshqa ko'rmaydi);
--   - sababi KIRITILGAN (operator yozgan) — tegilmaydi, faqat OCHIQ bo'lsa
--     boshlangan lahzasida yopiladi (nol uzunlik: hisobotdagi sabab qidiruvi
--     ustma-ust tushishni so'raydi, ya'ni boshqa to'xtashga sabab bermaydi).
-- Hech narsa jismonan o'chirilmaydi. Qaytarish — pastdagi «QAYTARISH».
--
-- KROMKA bo'sh yurishi (`start_key = idle-...`) hodisaga emas, o'lchov VAQTIGA
-- bog'langan — uni bu kalit bilan topib bo'lmaydi. 2-bo'lim uzoq ochiq qolgan
-- HAMMA yozuvni ko'rsatadi; ulardan qaysini yopish — qo'lda qaror.
--
-- Ikkinchi yurgizish xavfsiz: soxta yozuv qolmagan bo'lsa hech narsa o'zgarmaydi.
-- Tekshiruv: `scripts/oracles/downtime_cleanup_oracle.py`.
--
-- Ishga tushirish (serverda, repo ildizida):
--   cd /opt/mebelix-mes
--   Avval FAQAT hisobot (hech narsa o'zgarmaydi):
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v faqat_hisobot=1' \
--     < scripts/downtime_deleted_events.sql
--   Keyin tozalash:
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < scripts/downtime_deleted_events.sql > /tmp/downtime_tozalash.txt 2>&1
-- =============================================================================

SET statement_timeout = '120s';
\timing off
\pset pager off
\set ON_ERROR_STOP on
\if :{?faqat_hisobot}
\else
  \set faqat_hisobot 0
\endif

-- Soxta to'xtashning IKKI manbasi:
-- (a) `start_key` = boshlagan hodisaning `session || '-' || seq` (`downtimes._runs`), hodisa
--     o'chirilgan. `(machine_id, session, seq)` unikal — kalit yo tirik, yo o'chirilganniki.
-- (b) ROVER stanogidagi `idle-*` (kromka bo'sh yurishi) yozuvi. Roverda o'lchov yo'q, ya'ni
--     bo'sh yurish bo'lishi mumkin emas: 2026-10-16 deploy'idagi xato (`_bosh_yurish` Rover'ning
--     o'z IDLE holatini ham olardi) har bo'sh turishni IKKINCHI yozuv qilgan, chegarasiz.
CREATE TEMP VIEW soxta AS
SELECT d.id, d.machine_id, d.kind, d.start_key, d.started_at, d.ended_at, d.reason_id,
       'o''chirilgan hodisa' AS manba
FROM downtime d
JOIN andon_event e
  ON e.machine_id = d.machine_id
 AND d.start_key = e.session || '-' || e.seq
WHERE NOT d.is_deleted
  AND e.is_deleted
  AND d.kind <> 'lock'
UNION ALL
SELECT d.id, d.machine_id, d.kind, d.start_key, d.started_at, d.ended_at, d.reason_id,
       'rover idle-*' AS manba
FROM downtime d
JOIN machine m ON m.id = d.machine_id
JOIN post p ON p.id = m.post_id
WHERE NOT d.is_deleted
  AND p.code = 'ROVER'
  AND d.start_key LIKE 'idle-%';

\echo '=== 1. SOXTA TO''XTASHLAR (o''chirilgan hodisadan va Rover idle-*) ==='
SELECT m.name AS stanok,
       s.manba,
       s.kind AS tur,
       count(*) AS jami,
       count(*) FILTER (WHERE s.ended_at IS NULL) AS ochiq,
       count(*) FILTER (WHERE s.reason_id IS NOT NULL) AS sababli,
       min(s.started_at AT TIME ZONE 'Asia/Tashkent') AS birinchi,
       max(s.started_at AT TIME ZONE 'Asia/Tashkent') AS oxirgi
FROM soxta s
JOIN machine m ON m.id = s.machine_id
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;

\echo ''
\echo '=== 2. 12 SOATDAN UZOQ OCHIQ TURGAN HAMMA TO''XTASH (bo''sh yurish ham) ==='
SELECT m.name AS stanok, d.id, d.kind AS tur, d.start_key,
       d.started_at AT TIME ZONE 'Asia/Tashkent' AS boshlangan,
       d.reason_id IS NOT NULL AS sababli,
       d.id IN (SELECT id FROM soxta) AS soxta
FROM downtime d
JOIN machine m ON m.id = d.machine_id
WHERE NOT d.is_deleted
  AND d.kind <> 'lock'
  AND d.ended_at IS NULL
  AND d.started_at < now() - interval '12 hours'
ORDER BY d.started_at;

\if :faqat_hisobot
  \echo ''
  \echo 'FAQAT HISOBOT — hech narsa o''zgartirilmadi.'
\else
  BEGIN;

  \echo ''
  \echo '=== 3. SABABSIZ SOXTA TO''XTASHLAR yumshoq o''chirildi ==='
  UPDATE downtime
  SET is_deleted = true, deleted_at = now()
  WHERE id IN (SELECT id FROM soxta WHERE reason_id IS NULL);

  \echo '=== 4. SABABLI, OCHIQ soxta to''xtashlar boshlangan lahzasida yopildi ==='
  UPDATE downtime
  SET ended_at = started_at
  WHERE id IN (SELECT id FROM soxta WHERE reason_id IS NOT NULL AND ended_at IS NULL);

  COMMIT;
\endif

-- =============================================================================
-- QAYTARISH (kerak bo'lsa, qo'lda; vaqtni /tmp/downtime_tozalash.txt dan oling):
--   UPDATE downtime SET is_deleted = false, deleted_at = NULL
--   WHERE deleted_at BETWEEN '<tozalash boshi>' AND '<tozalash oxiri>';
-- 4-bo'limda yopilganlar `ended_at = started_at` bilan ajraladi:
--   UPDATE downtime SET ended_at = NULL WHERE ended_at = started_at AND kind <> 'lock';
-- =============================================================================
