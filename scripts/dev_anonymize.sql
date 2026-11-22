-- dev bazasidagi SHAXSIY ma'lumotni soxtaga almashtiradi (`scripts/dev_refresh.sh`).
-- FAQAT dev bazasida yurgiziladi — prodda yurgizish mijoz ma'lumotini yo'q qiladi.
--
-- Nimaga tegiladi: mijoz (ism, ikkala telefon, manzil, izoh), hodim (ism, telefon),
-- tizim hisoblari (ism va telefon; USERNAME va PAROL HASHI qoladi — dev'ga o'z
-- hisobingiz bilan kirasiz), agent va chek qurilmasi tokenlari (tsexdagi kompyuter
-- adashib dev'ga ulanmasin).
--
-- Nimaga TEGILMAYDI: buyurtma raqamlari, detallar, marshrutlar, skanlar, kromka
-- o'lchovlari, katalog — sinovning butun ma'nosi shularda.

BEGIN;

\echo '== mijozlar =='
UPDATE client
SET full_name = 'Mijoz ' || id,
    phone = CASE WHEN phone IS NULL THEN NULL ELSE '+998900000' || lpad((id % 1000)::text, 3, '0') END,
    phone_alt = NULL,
    address = CASE WHEN address IS NULL THEN NULL ELSE 'Toshkent, sinov manzili ' || id END,
    notes = NULL;

\echo '== hodimlar =='
UPDATE employee
SET full_name = 'Hodim ' || id,
    phone = CASE WHEN phone IS NULL THEN NULL ELSE '+998901000' || lpad((id % 1000)::text, 3, '0') END;

\echo '== tizim hisoblari (username va parol HASHI qoladi) =='
UPDATE "user"
SET full_name = 'Foydalanuvchi ' || id,
    phone = '+998902000' || lpad((id % 1000)::text, 3, '0');

\echo '== agent va chek qurilmasi tokenlari =='
-- Token hashi o'chadi: dev hech bir haqiqiy agentni tanimaydi, ya'ni tsexdagi
-- skaner yoki printer bu yerga ulanib qololmaydi.
UPDATE bridge_agent SET token_hash = NULL;
UPDATE terminal_device SET token_hash = NULL;

COMMIT;

\echo '== qolgan tozalanmagan yozuv (0 bo'lishi kerak) =='
SELECT (SELECT count(*) FROM client WHERE full_name NOT LIKE 'Mijoz %') AS mijoz,
       (SELECT count(*) FROM employee WHERE full_name NOT LIKE 'Hodim %') AS hodim,
       (SELECT count(*) FROM bridge_agent WHERE token_hash IS NOT NULL) AS agent_token;
