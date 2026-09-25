-- =============================================================================
-- MebeliX — KROMKA: proshivka v1.22 tasdiqsiz qolganda yig'ilgan TAKROR yozuvlar.
--
-- NIMA BO'LGAN. Pico 2026-09-24 da v1.22 ga o'tdi: endi u har muhim hodisani
-- `ACK <xb> <xq>` kelmaguncha xotirada saqlaydi va HAR 5 SONIYADA qayta yuboradi.
-- Prodda esa agent 1.7.1 turardi — u tasdiq yubormaydi va kromka hodisasiga
-- kalitni O'ZI beradi, ya'ni har takror YANGI yozuv bo'lib tushgan. Natijada
-- bitta o'lchov o'nlab marta sanaldi: Performance ham, o'lchov tarixi ham shishdi
-- (misol: 2026-09-24 18:40:12, 821.2 mm — 18 marta).
--
-- Agent 1.8.0 dan bu takrorlanmaydi (`docs/12` §4.8, `bridge-agent/README.md`).
-- Bu skript esa O'SHA KUNLARDA yig'ilganini tozalaydi.
--
-- NIMA QILADI. Hech narsani O'CHIRMAYDI: `is_deleted = true` qo'yadi (yumshoq
-- o'chirish, hamma hisobot uni filtrlaydi) va `deleted_at` ga vaqt yozadi.
-- Qaytarish kerak bo'lsa — pastdagi «QAYTARISH» bo'limi.
--
-- Kalit: takror hodisalar bir xil `payload->>'xb'` (Pico yonish belgisi) va
-- `payload->>'xq'` (shu yonishdagi raqami) bilan keladi — ya'ni takrorlik
-- TAXMIN emas, Pico'ning o'zi aytgan fakt. Har guruhdan ENG BIRINCHI yozuv
-- (eng kichik `id`) qoladi.
--
-- Ishga tushirish (serverda, repo ildizida — fayl deploy bilan o'zi keladi):
--   cd /opt/mebelix-mes
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < scripts/kromka_dedup.sql > /tmp/kromka_dedup_natija.txt 2>&1
--
-- Avval FAQAT hisobotni ko'rish uchun (hech narsa o'zgarmaydi):
--   ... yuqoridagi buyruq, lekin oxiriga `-v faqat_hisobot=1` qo'shilgan holda
--   docker compose -f docker-compose.prod.yml exec -T db \
--     sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v faqat_hisobot=1' \
--     < scripts/kromka_dedup.sql
-- =============================================================================

SET statement_timeout = '120s';
\timing off
\pset pager off
\set ON_ERROR_STOP on
-- `faqat_hisobot` berilmagan bo'lsa — bo'sh qiymat (ya'ni tozalanadi)
\if :{?faqat_hisobot}
\else
  \set faqat_hisobot 0
\endif

\echo '=== 1. TAKROR HODISALAR: qaysi stanok, qaysi kun, nechta ortiqcha ==='
SELECT m.name AS stanok,
       (e.happened_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
       e.kind AS tur,
       count(*) - count(DISTINCT (e.payload->>'xb', e.payload->>'xq')) AS ortiqcha,
       count(DISTINCT (e.payload->>'xb', e.payload->>'xq')) AS haqiqiy
FROM andon_event e
JOIN machine m ON m.id = e.machine_id
WHERE NOT e.is_deleted
  AND e.payload ? 'xb' AND e.payload ? 'xq'
GROUP BY 1, 2, 3
HAVING count(*) > count(DISTINCT (e.payload->>'xb', e.payload->>'xq'))
ORDER BY 2, 1, 3;

\echo ''
\echo '=== 2. ENG KO''P TAKRORLANGAN 10 ta hodisa ==='
SELECT m.name AS stanok,
       e.happened_at AT TIME ZONE 'Asia/Tashkent' AS vaqt,
       e.kind AS tur,
       e.payload->>'xq' AS xq,
       round((e.payload->>'L')::numeric, 1) AS mm,
       count(*) AS nusxa
FROM andon_event e
JOIN machine m ON m.id = e.machine_id
WHERE NOT e.is_deleted
  AND e.payload ? 'xb' AND e.payload ? 'xq'
GROUP BY 1, 2, 3, 4, 5, e.payload->>'xb'
HAVING count(*) > 1
ORDER BY count(*) DESC, 2 DESC
LIMIT 10;

\echo ''
\echo '=== 3. O''LCHOV TARIXIDAGI takrorlar (kromka_measurement) ==='
SELECT m.name AS stanok,
       (k.measured_at AT TIME ZONE 'Asia/Tashkent')::date AS kun,
       count(*) - count(DISTINCT k.measured_at) AS ortiqcha,
       count(DISTINCT k.measured_at) AS haqiqiy
FROM kromka_measurement k
JOIN machine m ON m.id = k.machine_id
WHERE NOT k.is_deleted
  AND (k.machine_id, k.measured_at) IN (
        SELECT e.machine_id, e.happened_at
        FROM andon_event e
        WHERE e.kind = 'olchov' AND e.payload ? 'xb' AND e.payload ? 'xq'
        GROUP BY e.machine_id, e.happened_at, e.payload->>'xb', e.payload->>'xq'
        HAVING count(*) > 1)
GROUP BY 1, 2
ORDER BY 2, 1;

\if :faqat_hisobot
\echo ''
\echo '>>> FAQAT HISOBOT — hech narsa o''zgartirilmadi.'
\else

BEGIN;

\echo ''
\echo '=== 4. TOZALASH: o''lchov tarixi (avval — u hodisa vaqtiga tayanadi) ==='
WITH takror_vaqt AS (
    -- Pico QAYTA yuborgan hodisalarning aniq vaqtlari: shu lahzalardagina
    -- o'lchov nusxasi takror bo'lishi mumkin. Boshqa vaqtga tegilmaydi —
    -- ikki haqiqiy detal bir soniyada o'tolmaydi (tranzit 8-15 s), lekin
    -- tozalashni taxminga emas, Pico aytgan faktga bog'lab qo'yamiz.
    SELECT e.machine_id, e.happened_at
    FROM andon_event e
    WHERE e.kind = 'olchov' AND e.payload ? 'xb' AND e.payload ? 'xq'
    GROUP BY e.machine_id, e.happened_at, e.payload->>'xb', e.payload->>'xq'
    HAVING count(*) > 1
),
ortiqcha AS (
    SELECT k.id
    FROM (
        SELECT k.id,
               row_number() OVER (PARTITION BY k.machine_id, k.measured_at
                                  ORDER BY k.id) AS n
        FROM kromka_measurement k
        JOIN takror_vaqt t ON t.machine_id = k.machine_id AND t.happened_at = k.measured_at
        WHERE NOT k.is_deleted
    ) k
    WHERE k.n > 1
)
UPDATE kromka_measurement k
SET is_deleted = true, deleted_at = now()
FROM ortiqcha o
WHERE k.id = o.id;

\echo ''
\echo '=== 5. TOZALASH: xom hodisalar (andon_event) ==='
WITH ortiqcha AS (
    SELECT e.id
    FROM (
        SELECT e.id,
               row_number() OVER (PARTITION BY e.machine_id, e.payload->>'xb', e.payload->>'xq'
                                  ORDER BY e.id) AS n
        FROM andon_event e
        WHERE NOT e.is_deleted
          AND e.payload ? 'xb' AND e.payload ? 'xq'
    ) e
    WHERE e.n > 1
)
UPDATE andon_event e
SET is_deleted = true, deleted_at = now()
FROM ortiqcha o
WHERE e.id = o.id;

COMMIT;

\echo ''
\echo '=== 6. NATIJA: takror qolmadimi ==='
SELECT count(*) AS qolgan_takror_hodisa
FROM (
    SELECT 1
    FROM andon_event e
    WHERE NOT e.is_deleted AND e.payload ? 'xb' AND e.payload ? 'xq'
    GROUP BY e.machine_id, e.payload->>'xb', e.payload->>'xq'
    HAVING count(*) > 1
) t;

SELECT count(*) AS ochirilgan_hodisa
FROM andon_event WHERE is_deleted AND deleted_at >= now() - interval '5 minutes';

SELECT count(*) AS ochirilgan_olchov
FROM kromka_measurement WHERE is_deleted AND deleted_at >= now() - interval '5 minutes';

\endif

-- =============================================================================
-- QAYTARISH (noto'g'ri narsa o'chgan bo'lsa, shu skript yurgizilgan 10 daqiqa ichida):
--
--   UPDATE andon_event SET is_deleted = false, deleted_at = NULL
--   WHERE is_deleted AND deleted_at >= now() - interval '10 minutes';
--   UPDATE kromka_measurement SET is_deleted = false, deleted_at = NULL
--   WHERE is_deleted AND deleted_at >= now() - interval '10 minutes';
--
-- Undan keyin `deleted_at` ni aniq vaqt bilan cheklab qaytarish kerak — bazada
-- boshqa sabab bilan yumshoq o'chirilgan yozuvlar ham bor.
-- =============================================================================
