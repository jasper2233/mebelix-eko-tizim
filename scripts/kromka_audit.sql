-- =============================================================================
-- MebeliX — KROMKA stansiyasi ma'lumotining auditi.  FAQAT O'QISH.
--
-- Hech narsa yozmaydi: sessiya read-only rejimda, har so'rovga 60 s chegara.
--
-- Ishga tushirish (serverda, repo ildizida — fayl deploy bilan o'zi keladi):
--   cd /opt/mebelix-mes
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < scripts/kromka_audit.sql > /tmp/kromka_audit_natija.txt 2>&1
--
-- Nima uchun: 1-bosqich (kuzatuv, docs/12 §4.8) faqat YOZADI. Keyingi bosqichga
-- (QR bog'lash, avtomatik skan) o'tishdan oldin ma'lumot ishonchli ekaniga ishonch
-- kerak: datchiklar har detalni ko'ryaptimi, juftlash to'g'rimi, mayda bo'lak
-- navbatni siljityaptimi. Ularning prod ma'lumotida (2026-09-17) 8% detalni bitta
-- datchik ko'rmagan va 8 ta soxta «tezlik nomuvofiq» chiqqan edi — shu takrorlanmoqdami.
--
-- Davr: oxirgi 14 kun. Vaqtlar Toshkent vaqtida.
-- =============================================================================

SET default_transaction_read_only = on;
SET statement_timeout = '60s';
\timing off
\pset pager off

\echo '=== 1. QAMROV: qaysi ish markazidan nima keldi ==='
SELECT m.name AS stanok, e.kind AS tur, count(*) AS soni,
       min(e.happened_at AT TIME ZONE 'Asia/Tashkent') AS birinchi,
       max(e.happened_at AT TIME ZONE 'Asia/Tashkent') AS oxirgi
FROM andon_event e JOIN machine m ON m.id = e.machine_id
WHERE e.happened_at > now() - interval '14 days'
  AND e.kind IN ('olchov', 'uskuna', 'tezlik', 'ogoh', 'avariya_toxtash', 'boot', 'tiqilish')
GROUP BY 1, 2 ORDER BY 1, 3 DESC;

\echo ''
\echo '=== 2. KUNLIK: olchov, toxtash va ogoh soni ==='
SELECT (e.happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
       count(*) FILTER (WHERE e.kind = 'olchov') AS olchov,
       count(*) FILTER (WHERE e.kind = 'uskuna') AS uskuna_ozgarishi,
       count(*) FILTER (WHERE e.kind = 'ogoh')   AS ogoh,
       count(*) FILTER (WHERE e.kind = 'tiqilish') AS tiqilish,
       count(*) FILTER (WHERE e.payload ? 'eski_ms') AS buferdan
FROM andon_event e
WHERE e.happened_at > now() - interval '14 days' AND e.kind <> 'state'
GROUP BY 1 ORDER BY 1 DESC;

\echo ''
\echo '=== 3. PICO KODLARI: ikkala datchik kordimi ==='
\echo '    OK = ikkalasi mos; FARQ = chegaradan oshdi; FAQAT1/FAQAT2 = bitta datchik kormagan.'
\echo '    FAQAT* ulushi 2 foizdan oshsa: linza iflos yoki datchik siljigan.'
SELECT coalesce(e.payload->>'kod', '?') AS kod, count(*) AS soni,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS ulush_pct
FROM andon_event e
WHERE e.kind = 'olchov' AND e.happened_at > now() - interval '14 days'
GROUP BY 1 ORDER BY 2 DESC;

\echo ''
\echo '=== 4. D1 va D2 FARQI (mm): datchiklar bir xil olchayaptimi ==='
\echo '    p90 chegaraga (TD, sukut 12 mm) yaqin bolsa: kalibrlash yoki linza muammosi.'
SELECT count(*) AS juft_olchov,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY farq)::numeric, 2) AS median,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY farq)::numeric, 2) AS p90,
       round(max(farq)::numeric, 1) AS eng_katta
FROM (
  SELECT abs((payload->>'L1')::numeric - (payload->>'L2')::numeric) AS farq
  FROM andon_event
  WHERE kind = 'olchov' AND happened_at > now() - interval '14 days'
    AND payload->>'L1' IS NOT NULL AND payload->>'L2' IS NOT NULL
) t;

\echo ''
\echo '=== 5. TEZLIK: olchangani nominaldan qancha chetda ==='
\echo '    Tarqoqlik 1 foizdan katta bolsa: juftlash xatosi (mayda bolak navbatga tushgan).'
SELECT (payload->>'v_nom') AS nominal, count(*) AS soni,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY v)::numeric, 2) AS median,
       round(min(v)::numeric, 2) AS eng_kichik, round(max(v)::numeric, 2) AS eng_katta,
       count(*) FILTER (WHERE abs(v - (payload->>'v_nom')::numeric)
                              / nullif((payload->>'v_nom')::numeric, 0) > 0.2) AS chetda_20pct
FROM (
  SELECT payload, (payload->>'v_olch')::numeric AS v
  FROM andon_event
  WHERE kind = 'olchov' AND happened_at > now() - interval '14 days'
    AND payload->>'v_olch' IS NOT NULL
) t
GROUP BY 1 ORDER BY 1;

\echo ''
\echo '=== 6. MAYDA BOLAKLAR: 100 mm dan kalta detal ==='
\echo '    Firmware chegarasi VAQT boyicha (50 ms): 10 m/min da 8 mm. Qoldiq yoki bolak'
\echo '    navbatga tushsa keyingi detalning juftligi siljiydi. Kop bolsa: firmware tuzatilsin.'
SELECT (happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
       count(*) FILTER (WHERE (payload->>'L')::numeric < 100) AS kalta_100mm,
       count(*) FILTER (WHERE (payload->>'L')::numeric < 50)  AS kalta_50mm,
       count(*) AS jami
FROM andon_event
WHERE kind = 'olchov' AND happened_at > now() - interval '14 days'
  AND payload->>'L' IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;

\echo ''
\echo '=== 7. OGOHLANTIRISHLAR: datchik nosozligi ==='
SELECT payload->>'sabab' AS sabab, payload->>'ch' AS datchik, count(*) AS soni,
       max(happened_at AT TIME ZONE 'Asia/Tashkent') AS oxirgi
FROM andon_event
WHERE kind = 'ogoh' AND happened_at > now() - interval '14 days'
GROUP BY 1, 2 ORDER BY 3 DESC;

\echo ''
\echo '=== 8. STANOK VAQTI: kuniga qancha ishladi (uskuna hodisalaridan) ==='
SELECT kun, round(sum(soniya) FILTER (WHERE holat = 1) / 3600.0, 2) AS ishladi_soat,
            round(sum(soniya) FILTER (WHERE holat = 0) / 3600.0, 2) AS toxtadi_soat
FROM (
  SELECT (happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
         (payload->>'holat')::int AS holat,
         extract(epoch FROM (lead(happened_at) OVER (PARTITION BY machine_id ORDER BY happened_at)
                             - happened_at)) AS soniya
  FROM andon_event
  WHERE kind = 'uskuna' AND happened_at > now() - interval '14 days'
) t
WHERE soniya IS NOT NULL AND soniya < 86400
GROUP BY 1 ORDER BY 1 DESC;

\echo ''
\echo '=== 9. UZILISHLAR: hodisalar orasida 10 daqiqadan uzun jimlik ==='
\echo '    Ish vaqtidagi jimlik = Pico, agent yoki kompyuter ochgan. Hisobotda stanok ochiq boladi.'
SELECT (oldingi AT TIME ZONE 'Asia/Tashkent') AS jimlik_boshi,
       (happened_at AT TIME ZONE 'Asia/Tashkent') AS jimlik_oxiri,
       round(extract(epoch FROM (happened_at - oldingi)) / 60.0) AS daqiqa
FROM (
  SELECT happened_at, lag(happened_at) OVER (PARTITION BY machine_id ORDER BY happened_at) AS oldingi
  FROM andon_event
  WHERE kind <> 'state' AND happened_at > now() - interval '14 days'
) t
WHERE oldingi IS NOT NULL AND happened_at - oldingi > interval '10 minutes'
ORDER BY 1 DESC LIMIT 30;

\echo ''
\echo '=== 10. SONGGI 15 OLCHOV (koz bilan tekshirish uchun) ==='
SELECT (happened_at AT TIME ZONE 'Asia/Tashkent') AS vaqt,
       payload->>'L' AS mm, payload->>'kod' AS kod,
       payload->>'L1' AS d1, payload->>'L2' AS d2,
       payload->>'v_olch' AS tezlik, payload->>'navbat' AS navbatda
FROM andon_event
WHERE kind = 'olchov' AND happened_at > now() - interval '14 days'
ORDER BY happened_at DESC LIMIT 15;

\echo ''
\echo '=== 11. TIQILISH (proshivka v1.16): detallar birga otgan yoki datchik ostida qolgan ==='
\echo '    Har tiqilish = olchanmay qolgan detal(lar). Performance shuncha kam korsatadi.'
\echo '    sabab: birga_otdi = ikki detal qoshilib otgan; vaqt_mos_emas = D1 va D2 vaqti mos kelmadi.'
SELECT (happened_at AT TIME ZONE 'Asia/Tashkent') AS vaqt,
       payload->>'sabab' AS sabab,
       payload->>'n'     AS olchanmagan_detal,
       payload->>'L2'    AS d2_mm,
       payload->>'L1'    AS d1_mm_royxati
FROM andon_event
WHERE kind = 'tiqilish' AND happened_at > now() - interval '14 days'
ORDER BY happened_at DESC LIMIT 30;
