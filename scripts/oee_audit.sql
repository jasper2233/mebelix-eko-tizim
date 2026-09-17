-- =============================================================================
-- MebeliX — OEE oldidan andon (Pico) ma'lumot auditi.  FAQAT O'QISH.
--
-- Hech narsa yozmaydi: sessiya read-only rejimda, har so'rovga 60 s chegara.
-- Bazada jadval, indeks yoki sozlama yaratilmaydi / o'zgartirilmaydi.
--
-- Ishga tushirish (serverda, repo ildizida — fayl deploy bilan o'zi keladi):
--   cd /opt/mebelix-mes
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < scripts/oee_audit.sql > /tmp/oee_audit_natija.txt 2>&1
--
-- Natijalar va ularning talqini: docs/12-oee.md.
--
-- Davr: oxirgi 14 kun. O'zgartirish uchun faylda '14 days' ni almashtiring
-- (5-bo'limdagi '13 days' va '17 days' ham shunga mos o'zgaradi).
-- Vaqtlar Toshkent vaqtida ko'rsatiladi.
-- =============================================================================

\set ON_ERROR_STOP off
\pset pager off
SET default_transaction_read_only = on;
SET statement_timeout = '60s';
SET TIME ZONE 'Asia/Tashkent';


-- -----------------------------------------------------------------------------
\echo '== 0. Andon ulangan ish markazlari va ularning agentlari'
-- Nima ko'rish kerak: andon faqat Prisadkada bo'lishi kerak; oxirgi_qabul yangi
-- bo'lishi kerak; sessiyalar soni ko'p bo'lsa Pico tez-tez qayta yuklanyapti.
-- -----------------------------------------------------------------------------
SELECT m.id AS machine_id, m.name AS ish_markazi, p.code AS post, m.status,
       count(*) FILTER (WHERE e.kind = 'state') AS state_hodisa,
       count(*) FILTER (WHERE e.kind = 'cycle') AS cycle_hodisa,
       count(DISTINCT e.session) AS sessiyalar,
       min(e.happened_at) AS birinchi_hodisa,
       max(e.happened_at) AS oxirgi_hodisa,
       max(e.created_at) AS oxirgi_qabul
FROM andon_event e
JOIN machine m ON m.id = e.machine_id
JOIN post p ON p.id = m.post_id
WHERE NOT e.is_deleted
GROUP BY m.id, m.name, p.code, m.status
ORDER BY m.id;

SELECT a.id AS agent_id, a.name AS agent, a.version, a.can_print, a.last_seen_at,
       a.machine_id, m.name AS ish_markazi
FROM bridge_agent a
LEFT JOIN machine m ON m.id = a.machine_id
WHERE NOT a.is_deleted
  AND a.machine_id IN (SELECT DISTINCT machine_id FROM andon_event)
ORDER BY a.id;


-- -----------------------------------------------------------------------------
\echo '== 1. Payload ichida haqiqatda qaysi maydonlar keladi'
-- Kutilgan: state da downtime_id / closes_downtime_id / lamps / part_id;
-- cycle da wait_s / process_s / completed / part_count.
-- -----------------------------------------------------------------------------
SELECT e.kind, k.key AS maydon, count(*) AS hodisalar
FROM andon_event e
CROSS JOIN LATERAL jsonb_object_keys(e.payload) AS k(key)
WHERE NOT e.is_deleted
  AND e.happened_at >= now() - interval '14 days'
GROUP BY e.kind, k.key
ORDER BY e.kind, hodisalar DESC, k.key;

\echo '-- 1b. Har holatda chiroqlar kombinatsiyasi (holat togri aniqlanyaptimi)'
-- Kutilgan: PROCESSING = green on, AWAIT_PART = green blink, IDLE/STOPPED = yellow,
-- FAULT = red on/blink, OFF = hammasi off. Boshqacha juftlik — sozlama xatosi belgisi.
SELECT e.state, e.payload -> 'lamps' AS chiroqlar, count(*) AS soni
FROM andon_event e
WHERE e.kind = 'state' AND NOT e.is_deleted
  AND e.happened_at >= now() - interval '14 days'
GROUP BY e.state, e.payload -> 'lamps'
ORDER BY e.state, soni DESC;


-- -----------------------------------------------------------------------------
\echo '== 2. Sessiyalar (Pico qayta yuklanishi) va yoqolgan hodisalar'
-- seq sessiya ichida uzluksiz bo'lishi kerak. boshliqlar > 0 — hodisa yo'qolgan
-- (Pico RAM buferi 200 ta, kompyuter/agent uzoq uzilsa eng eskilari tashlanadi).
-- birinchi_seq > 1 — sessiya boshi yo'qolgan YOKI sessiya 14 kundan oldin boshlangan.
-- -----------------------------------------------------------------------------
WITH s AS (
    SELECT machine_id, session, seq, happened_at,
           lag(seq) OVER (PARTITION BY machine_id, session ORDER BY seq) AS oldingi_seq
    FROM andon_event
    WHERE NOT is_deleted
      AND happened_at >= now() - interval '14 days'
)
SELECT machine_id, session,
       min(happened_at) AS boshlandi,
       max(happened_at) AS tugadi,
       min(seq) AS birinchi_seq,
       max(seq) AS oxirgi_seq,
       count(*) AS qatorlar,
       count(*) FILTER (WHERE seq > oldingi_seq + 1) AS boshliqlar,
       coalesce(sum(seq - oldingi_seq - 1) FILTER (WHERE seq > oldingi_seq + 1), 0) AS yoqolgan_hodisa
FROM s
GROUP BY machine_id, session
ORDER BY machine_id, boshlandi;


-- -----------------------------------------------------------------------------
\echo '== 3. Yetkazish kechikishi va soat farqi (agent kompyuteri vs server)'
-- happened_at = agent kompyuteri soati, created_at = server qabul qilgan payt.
-- Median bir necha soniya bo'lishi kerak. kelajakdan > 0 — tsex kompyuteri soati
-- oldinda (sinxron emas). kech_5daq_dan — agent/internet uzilgan paytlar.
-- -----------------------------------------------------------------------------
SELECT machine_id, kind,
       count(*) AS hodisalar,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM created_at - happened_at)))::numeric, 1) AS kechikish_median_s,
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM created_at - happened_at)))::numeric, 1) AS kechikish_p90_s,
       round((percentile_cont(0.99) WITHIN GROUP (ORDER BY extract(epoch FROM created_at - happened_at)))::numeric, 1) AS kechikish_p99_s,
       round(max(extract(epoch FROM created_at - happened_at))::numeric, 0) AS kechikish_max_s,
       count(*) FILTER (WHERE created_at - happened_at > interval '5 minutes') AS kech_5daq_dan,
       count(*) FILTER (WHERE happened_at > created_at + interval '5 seconds') AS kelajakdan
FROM andon_event
WHERE NOT is_deleted
  AND happened_at >= now() - interval '14 days'
GROUP BY machine_id, kind
ORDER BY machine_id, kind;


-- -----------------------------------------------------------------------------
\echo '== 4. Vaqt izchilligi: holatlar zanjiri va davomiylik mosligi'
-- Ketma-ket ikki state hodisasi orasidagi vaqt keyingisining prev_duration_s iga
-- (Pico o'lchagan) ~teng bo'lishi kerak. Farq katta bo'lsa hodisalar vaqti
-- buzilgan: Pico oflayn buferidan kelgan hodisalarga agent o'qigan paytni qo'yadi,
-- ya'ni vaqtlar bir joyga siqiladi — kunlik hisob noto'g'ri kunga tushadi.
-- zanjir_uzilishi > 0 — hodisa yo'qolgan (2-bo'lim bilan solishtiring).
-- -----------------------------------------------------------------------------
WITH st AS (
    SELECT machine_id, session, seq, state, happened_at,
           lead(prev_state) OVER w AS keyingi_prev_state,
           lead(prev_duration_s) OVER w AS keyingi_davom_s,
           lead(happened_at) OVER w AS keyingi_vaqt
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND happened_at >= now() - interval '14 days'
    WINDOW w AS (PARTITION BY machine_id, session ORDER BY seq)
)
SELECT machine_id,
       count(*) AS juftlar,
       count(*) FILTER (WHERE keyingi_prev_state IS DISTINCT FROM state) AS zanjir_uzilishi,
       count(*) FILTER (WHERE abs(extract(epoch FROM keyingi_vaqt - happened_at) - keyingi_davom_s) > 5) AS vaqt_farqi_5s_dan,
       count(*) FILTER (WHERE abs(extract(epoch FROM keyingi_vaqt - happened_at) - keyingi_davom_s) > 60) AS vaqt_farqi_60s_dan,
       round(max(abs(extract(epoch FROM keyingi_vaqt - happened_at) - keyingi_davom_s))::numeric, 0) AS eng_katta_farq_s
FROM st
WHERE keyingi_vaqt IS NOT NULL
GROUP BY machine_id;

\echo '-- 4b. Eng katta 20 ta vaqt nomuvofiqligi'
WITH st AS (
    SELECT machine_id, session, seq, state, happened_at,
           lead(prev_duration_s) OVER w AS keyingi_davom_s,
           lead(happened_at) OVER w AS keyingi_vaqt
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND happened_at >= now() - interval '14 days'
    WINDOW w AS (PARTITION BY machine_id, session ORDER BY seq)
)
SELECT machine_id, session, seq, state, happened_at, keyingi_vaqt,
       round(extract(epoch FROM keyingi_vaqt - happened_at)::numeric, 0) AS jadvaldagi_oraliq_s,
       keyingi_davom_s AS pico_olchagan_s
FROM st
WHERE keyingi_vaqt IS NOT NULL
ORDER BY abs(extract(epoch FROM keyingi_vaqt - happened_at) - keyingi_davom_s) DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
\echo '== 5. Kunlik qamrov: har holatda necha soat va necha soat umuman qayd yoq'
-- qayd_yoq_soat — Pico/agent/kompyuter ishlamagan vaqt (noma'lum). Bugungi kun
-- hali tugamagan va davom etayotgan oxirgi holat kirmaydi — bugun katta chiqadi.
-- qayd_soat > 24 — vaqtlar ustma-ust tushgan (4-bo'lim muammosi).
-- -----------------------------------------------------------------------------
WITH kunlar AS (
    SELECT d::date AS kun
    FROM generate_series(
        (now() AT TIME ZONE 'Asia/Tashkent')::date::timestamp - interval '13 days',
        (now() AT TIME ZONE 'Asia/Tashkent')::date::timestamp,
        interval '1 day') AS d
),
oraliq AS (
    SELECT machine_id, prev_state AS holat,
           happened_at - make_interval(secs => prev_duration_s) AS boshi,
           happened_at AS oxiri
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND prev_duration_s IS NOT NULL
      AND prev_state IS NOT NULL AND prev_state <> 'BOOT'
      AND happened_at >= now() - interval '17 days'
),
kesilgan AS (
    SELECT o.machine_id, k.kun, o.holat,
           extract(epoch FROM
               least(o.oxiri, (k.kun + 1)::timestamp AT TIME ZONE 'Asia/Tashkent')
             - greatest(o.boshi, k.kun::timestamp AT TIME ZONE 'Asia/Tashkent')) AS soniya
    FROM oraliq o
    JOIN kunlar k
      ON o.boshi < (k.kun + 1)::timestamp AT TIME ZONE 'Asia/Tashkent'
     AND o.oxiri > k.kun::timestamp AT TIME ZONE 'Asia/Tashkent'
)
SELECT machine_id, kun,
       extract(isodow FROM kun) AS hafta_kuni,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'PROCESSING'), 0) / 3600)::numeric, 2) AS ishlov_soat,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'AWAIT_PART'), 0) / 3600)::numeric, 2) AS detal_kutish_soat,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'IDLE'), 0) / 3600)::numeric, 2) AS kutish_soat,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'STOPPED'), 0) / 3600)::numeric, 2) AS uzoq_kutish_soat,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'FAULT'), 0) / 3600)::numeric, 2) AS avariya_soat,
       round((coalesce(sum(soniya) FILTER (WHERE holat = 'OFF'), 0) / 3600)::numeric, 2) AS ochiq_soat,
       round((sum(soniya) / 3600)::numeric, 2) AS qayd_soat,
       round((24 - sum(soniya) / 3600)::numeric, 2) AS qayd_yoq_soat
FROM kesilgan
GROUP BY machine_id, kun
ORDER BY machine_id, kun;


-- -----------------------------------------------------------------------------
\echo '== 6. Holat otishlari va juda qisqa holatlar (chiroq tasnifi xatosi belgisi)'
-- oldingisi_2s_gacha ko'p bo'lsa (ayniqsa PROCESSING -> AWAIT_PART) — miltillash
-- davri firmware sozlamasiga (MIN_STATE_MS 1200) mos emas: soxta ishlov/detal.
-- -----------------------------------------------------------------------------
SELECT machine_id, prev_state AS oldingi, state AS keyingi,
       count(*) AS soni,
       count(*) FILTER (WHERE prev_duration_s <= 2) AS oldingisi_2s_gacha,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY prev_duration_s))::numeric, 0) AS oldingi_median_s
FROM andon_event
WHERE kind = 'state' AND NOT is_deleted
  AND happened_at >= now() - interval '14 days'
GROUP BY machine_id, prev_state, state
ORDER BY machine_id, soni DESC;


-- -----------------------------------------------------------------------------
\echo '== 7. Kutish va toxtashlar davomiylik taqsimoti (mikro-toxtash chegarasi uchun)'
-- Qaysi chegarada (1/5/15 daqiqa) vaqtning asosiy qismi to'planishini ko'rsatadi.
-- -----------------------------------------------------------------------------
SELECT machine_id, prev_state AS holat,
       CASE
           WHEN prev_duration_s < 60 THEN '1) 1 daqiqagacha'
           WHEN prev_duration_s < 300 THEN '2) 1-5 daqiqa'
           WHEN prev_duration_s < 900 THEN '3) 5-15 daqiqa'
           WHEN prev_duration_s < 3600 THEN '4) 15-60 daqiqa'
           ELSE '5) 60 daqiqadan kop'
       END AS davomiylik,
       count(*) AS soni,
       round((sum(prev_duration_s) / 3600.0)::numeric, 2) AS jami_soat
FROM andon_event
WHERE kind = 'state' AND NOT is_deleted
  AND prev_duration_s IS NOT NULL
  AND prev_state IN ('AWAIT_PART', 'IDLE', 'STOPPED', 'FAULT', 'OFF')
  AND happened_at >= now() - interval '14 days'
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;


-- -----------------------------------------------------------------------------
\echo '== 8. Toxtash yozuvlari: Pico ochgan va yopgan downtime_id juftligi'
-- yopilmagan ko'p bo'lsa — yopuvchi hodisa yo'qolgan yoki Pico to'xtash paytida
-- qayta yuklangan (yangi sessiya eski to'xtashni yopmaydi).
-- -----------------------------------------------------------------------------
WITH ochilgan AS (
    SELECT machine_id, session, payload ->> 'downtime_id' AS dt_id, state, happened_at AS boshlandi
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND payload ->> 'downtime_id' IS NOT NULL
      AND happened_at >= now() - interval '14 days'
),
yopilgan AS (
    SELECT payload ->> 'closes_downtime_id' AS dt_id, prev_duration_s
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND payload ->> 'closes_downtime_id' IS NOT NULL
      AND happened_at >= now() - interval '14 days'
)
SELECT o.machine_id, o.state AS holat,
       count(*) AS ochilgan,
       count(y.dt_id) AS yopilgan,
       count(*) - count(y.dt_id) AS yopilmagan,
       round((coalesce(sum(y.prev_duration_s), 0) / 3600.0)::numeric, 2) AS jami_soat,
       round(((percentile_cont(0.5) WITHIN GROUP (ORDER BY y.prev_duration_s)) / 60)::numeric, 1) AS median_daqiqa
FROM ochilgan o
LEFT JOIN yopilgan y USING (dt_id)
GROUP BY o.machine_id, o.state
ORDER BY o.machine_id, o.state;

\echo '-- 8b. Yopilmagan toxtashlar (oxirgi 50 ta)'
WITH ochilgan AS (
    SELECT machine_id, session, payload ->> 'downtime_id' AS dt_id, state, happened_at AS boshlandi
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND payload ->> 'downtime_id' IS NOT NULL
      AND happened_at >= now() - interval '14 days'
)
SELECT o.machine_id, o.dt_id, o.state AS holat, o.boshlandi,
       EXISTS (
           SELECT 1 FROM andon_event e
           WHERE e.machine_id = o.machine_id AND NOT e.is_deleted
             AND e.session <> o.session AND e.happened_at > o.boshlandi
       ) AS keyin_pico_qayta_yuklangan
FROM ochilgan o
WHERE NOT EXISTS (
    SELECT 1 FROM andon_event c
    WHERE c.kind = 'state' AND NOT c.is_deleted
      AND c.payload ->> 'closes_downtime_id' = o.dt_id
)
ORDER BY o.boshlandi DESC
LIMIT 50;


-- -----------------------------------------------------------------------------
\echo '== 9. Detal sikllari: kunlik soni va vaqtlari'
-- ishlovsiz — detal ishlovsiz olingan (completed=false). ishlov_30s_dan_qisqa ko'p
-- bo'lsa — soxta sikl (chiroq tasnifi). p10/p50/p90 orasidagi katta farq —
-- detallar ish hajmi har xil, bitta "ideal sikl" raqami yaramaydi.
-- -----------------------------------------------------------------------------
SELECT machine_id,
       (happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
       count(*) AS sikllar,
       count(*) FILTER (WHERE (payload ->> 'completed')::boolean) AS tugallangan,
       count(*) FILTER (WHERE NOT (payload ->> 'completed')::boolean) AS ishlovsiz,
       count(*) FILTER (WHERE (payload ->> 'completed')::boolean AND (payload ->> 'process_s')::int < 30) AS ishlov_30s_dan_qisqa,
       (percentile_cont(0.1) WITHIN GROUP (ORDER BY (payload ->> 'process_s')::int) FILTER (WHERE (payload ->> 'completed')::boolean))::int AS ishlov_p10_s,
       (percentile_cont(0.5) WITHIN GROUP (ORDER BY (payload ->> 'process_s')::int) FILTER (WHERE (payload ->> 'completed')::boolean))::int AS ishlov_p50_s,
       (percentile_cont(0.9) WITHIN GROUP (ORDER BY (payload ->> 'process_s')::int) FILTER (WHERE (payload ->> 'completed')::boolean))::int AS ishlov_p90_s,
       (percentile_cont(0.5) WITHIN GROUP (ORDER BY (payload ->> 'wait_s')::int) FILTER (WHERE (payload ->> 'completed')::boolean))::int AS kutish_p50_s,
       (percentile_cont(0.9) WITHIN GROUP (ORDER BY (payload ->> 'wait_s')::int) FILTER (WHERE (payload ->> 'completed')::boolean))::int AS kutish_p90_s
FROM andon_event
WHERE kind = 'cycle' AND NOT is_deleted
  AND happened_at >= now() - interval '14 days'
GROUP BY 1, 2
ORDER BY 1, 2;


-- -----------------------------------------------------------------------------
\echo '== 10. Pico sikllari vs MES skanlari (kunlik)'
-- farq ~0 bo'lishi kerak. Musbat — skansiz ishlangan detal (sinov, qayta teshish,
-- skan tushmagan). Manfiy — skanerlangan-u ishlanmagan yoki sikl yo'qolgan.
-- stanok_skaneridan — Nanxing skaneri orqali (agent) kelgan ulush: sikl-skan
-- bog'lash shu skanlar vaqtiga tayanadi.
-- agent_rad_etilgan — stanok skaneridan kelib rad etilgan (masalan E008 qayta
-- teshish). Terminal (brauzer) orqali rad etilganlar audit logda ish markazisiz
-- yoziladi, shuning uchun bu yerga kirmaydi.
-- -----------------------------------------------------------------------------
WITH andon_markaz AS (
    SELECT DISTINCT machine_id FROM andon_event WHERE NOT is_deleted
),
sikl AS (
    SELECT machine_id,
           (happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
           count(*) FILTER (WHERE (payload ->> 'completed')::boolean) AS sikllar
    FROM andon_event
    WHERE kind = 'cycle' AND NOT is_deleted
      AND happened_at >= now() - interval '14 days'
    GROUP BY 1, 2
),
skan AS (
    SELECT s.machine_id,
           (s.created_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
           count(*) FILTER (WHERE NOT s.is_cancelled) AS skanlar,
           count(*) FILTER (WHERE s.is_cancelled) AS bekor_qilingan,
           count(DISTINCT s.instance_id) FILTER (WHERE NOT s.is_cancelled) AS nusxalar,
           count(*) FILTER (WHERE NOT s.is_cancelled AND a.meta ? 'agent_id') AS stanok_skaneridan
    FROM scan s
    LEFT JOIN audit_log a
           ON a.module = 'scan' AND a.action = 'recorded'
          AND a.entity_type = 'scan' AND a.entity_id = s.id
          AND a.created_at >= now() - interval '15 days'
    WHERE s.machine_id IN (SELECT machine_id FROM andon_markaz)
      AND NOT s.is_deleted
      AND s.parent_scan_id IS NULL
      AND s.created_at >= now() - interval '14 days'
    GROUP BY 1, 2
),
rad AS (
    SELECT ag.machine_id,
           (a.created_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
           count(*) AS rad_etilgan,
           count(*) FILTER (WHERE a.meta ->> 'code' = 'E008') AS rad_e008
    FROM audit_log a
    JOIN bridge_agent ag ON ag.id = (a.meta ->> 'agent_id')::int
    WHERE a.module = 'scan' AND a.action = 'rejected'
      AND a.meta ? 'agent_id'
      AND a.created_at >= now() - interval '14 days'
      AND ag.machine_id IN (SELECT machine_id FROM andon_markaz)
    GROUP BY 1, 2
)
SELECT machine_id, kun,
       coalesce(sikl.sikllar, 0) AS pico_sikllar,
       coalesce(skan.skanlar, 0) AS mes_skanlar,
       coalesce(skan.nusxalar, 0) AS nusxalar,
       coalesce(skan.stanok_skaneridan, 0) AS stanok_skaneridan,
       coalesce(skan.bekor_qilingan, 0) AS bekor_qilingan,
       coalesce(rad.rad_etilgan, 0) AS agent_rad_etilgan,
       coalesce(rad.rad_e008, 0) AS rad_e008,
       coalesce(sikl.sikllar, 0) - coalesce(skan.skanlar, 0) AS farq
FROM sikl
FULL JOIN skan USING (machine_id, kun)
LEFT JOIN rad USING (machine_id, kun)
ORDER BY machine_id, kun;


-- -----------------------------------------------------------------------------
\echo '== 11. Sikl-skan boglash imkoniyati (har "detal kutilmoqda" oldidan nechta skan)'
-- Oyna: oldingi AWAIT_PART dan shu AWAIT_PART + 5 s gacha (agent->server kechikishi uchun
-- zaxira). 2026-09-16 da 30 s edi: Prisadka sikli ~25 s, ya'ni keyingi detal skani ham sanalardi.
-- bitta_skan ulushi yuqori bo'lsa FIFO bog'lash ishonchli. skansiz ko'p bo'lsa —
-- skanlar MES ga tushmayapti (rad etilgan yoki forvard yo'q); ikki_va_kop ko'p
-- bo'lsa — operator bir nechta chekni oldindan skanerlaydi (FIFO shuni hal qiladi).
-- Bekor qilingan skanlar ham sanaladi — jismoniy skan baribir bo'lgan.
-- -----------------------------------------------------------------------------
WITH kutish AS (
    SELECT machine_id, happened_at,
           lag(happened_at) OVER (PARTITION BY machine_id ORDER BY happened_at) AS oldingi
    FROM andon_event
    WHERE kind = 'state' AND state = 'AWAIT_PART' AND NOT is_deleted
      AND happened_at >= now() - interval '14 days'
),
bog AS (
    SELECT k.machine_id,
           (SELECT count(*)
              FROM scan s
             WHERE s.machine_id = k.machine_id
               AND NOT s.is_deleted
               AND s.parent_scan_id IS NULL
               AND s.created_at > coalesce(k.oldingi, k.happened_at - interval '4 hours')
               AND s.created_at <= k.happened_at + interval '5 seconds') AS skanlar
    FROM kutish k
)
SELECT machine_id,
       count(*) AS detal_kutish_hodisalari,
       count(*) FILTER (WHERE skanlar = 0) AS skansiz,
       count(*) FILTER (WHERE skanlar = 1) AS bitta_skan,
       count(*) FILTER (WHERE skanlar >= 2) AS ikki_va_kop
FROM bog
GROUP BY machine_id;


-- -----------------------------------------------------------------------------
\echo '== 12. Ish kuni chegaralari: smena ochilishi/yopilishi vs birinchi/oxirgi ishlov'
-- Ish jadvalini (reja vaqtini) belgilash uchun: haqiqatda qachon boshlab, qachon
-- tugatishadi, qaysi kunlar ishlanadi (hafta_kuni: 1=Du ... 7=Ya).
-- -----------------------------------------------------------------------------
WITH ishlov AS (
    SELECT machine_id,
           (happened_at - make_interval(secs => prev_duration_s)) AT TIME ZONE 'Asia/Tashkent' AS boshi,
           happened_at AT TIME ZONE 'Asia/Tashkent' AS oxiri
    FROM andon_event
    WHERE kind = 'state' AND NOT is_deleted
      AND prev_state = 'PROCESSING' AND prev_duration_s IS NOT NULL
      AND happened_at >= now() - interval '14 days'
),
kun_ish AS (
    SELECT machine_id, boshi::date AS kun,
           min(boshi)::time AS birinchi_ishlov,
           max(oxiri)::time AS oxirgi_ishlov,
           round((sum(extract(epoch FROM oxiri - boshi)) / 3600)::numeric, 2) AS ishlov_soat
    FROM ishlov
    GROUP BY 1, 2
),
smena AS (
    SELECT machine_id,
           (created_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
           min(created_at AT TIME ZONE 'Asia/Tashkent')::time AS smena_ochildi,
           max(ended_at AT TIME ZONE 'Asia/Tashkent')::time AS smena_yopildi,
           count(*) AS smenalar,
           count(*) FILTER (WHERE status = 'active') AS hali_ochiq
    FROM work_session
    WHERE NOT is_deleted
      AND machine_id IN (SELECT DISTINCT machine_id FROM andon_event)
      AND created_at >= now() - interval '14 days'
    GROUP BY 1, 2
)
SELECT machine_id, kun,
       extract(isodow FROM kun) AS hafta_kuni,
       smena.smena_ochildi,
       kun_ish.birinchi_ishlov,
       kun_ish.oxirgi_ishlov,
       smena.smena_yopildi,
       kun_ish.ishlov_soat,
       smena.smenalar,
       smena.hali_ochiq
FROM kun_ish
FULL JOIN smena USING (machine_id, kun)
ORDER BY machine_id, kun;


-- -----------------------------------------------------------------------------
\echo '== 13. Prisadkada ishlangan detallar ish hajmi (ideal sikl modeli uchun)'
-- teshik p10..p90 oralig'i keng bo'lsa — ideal sikl formulasi (teshik/paz/freza
-- soniga qarab) kerak, bitta raqam yaramaydi.
-- -----------------------------------------------------------------------------
SELECT count(*) AS skanlar,
       (percentile_cont(0.1) WITHIN GROUP (ORDER BY t.teshik))::int AS teshik_p10,
       (percentile_cont(0.5) WITHIN GROUP (ORDER BY t.teshik))::int AS teshik_p50,
       (percentile_cont(0.9) WITHIN GROUP (ORDER BY t.teshik))::int AS teshik_p90,
       max(t.teshik) AS teshik_max,
       count(*) FILTER (WHERE t.teshik = 0) AS teshiksiz,
       count(*) FILTER (WHERE t.paz > 0) AS pazli,
       count(*) FILTER (WHERE t.freza > 0) AS frezali,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY t.maydon_m2))::numeric, 2) AS maydon_p50_m2
FROM scan s
JOIN post po ON po.id = s.post_id
JOIN part p ON p.id = s.part_id
CROSS JOIN LATERAL (
    SELECT coalesce((p.xnc_summary ->> 'bores')::int, 0)
         + coalesce((p.xnc_summary ->> 'edge_bores')::int, 0) AS teshik,
           coalesce((p.xnc_summary ->> 'grooves')::int, 0) AS paz,
           coalesce((p.xnc_summary ->> 'mills')::int, 0) AS freza,
           coalesce(p.length, 0) * coalesce(p.width, 0) / 1000000.0 AS maydon_m2
) AS t
WHERE po.code = 'PRISADKA'
  AND NOT s.is_deleted AND NOT s.is_cancelled
  AND s.parent_scan_id IS NULL
  AND s.created_at >= now() - interval '14 days';


-- -----------------------------------------------------------------------------
\echo '== 14. Eski OEE modulidan qolgan malumot (qayta ishlatish mumkinmi)'
-- stop_reason — egasining to'xtash sabablari ro'yxati (2026-08-21 seed).
-- -----------------------------------------------------------------------------
SELECT id, name, kind, excludes_planned, order_index, is_active, is_deleted
FROM stop_reason
ORDER BY order_index, id;

SELECT count(*) AS machine_stop_qatorlar FROM machine_stop;

SELECT id, name, status, planned_minutes_per_day, ideal_rate
FROM machine
WHERE id IN (SELECT DISTINCT machine_id FROM andon_event);

\echo '== Audit tugadi. Bazada hech narsa ozgartirilmadi.'
