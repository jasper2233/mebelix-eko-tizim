#!/usr/bin/env bash
# dev bazasini PROD nusxasidan to'ldiradi va shaxsiy ma'lumotni tozalaydi.
# Serverda, qo'lda yurgiziladi:  bash /opt/mebelix-mes-dev/scripts/dev_refresh.sh
#
# Nega nusxa: sinov haqiqiy katalog, haqiqiy marshrut va haqiqiy kromka tarixisiz
# ma'nosiz — bo'sh bazada hech narsa takrorlanmaydi.
# Nega tozalash: dev prodga qaraganda zaifroq himoyalangan, u yerda mijozning
# haqiqiy ismi va telefoni yotmasligi kerak (`scripts/dev_anonymize.sql`).
#
# Parol HASHLARI ko'chiriladi — ya'ni dev'ga o'z parolingiz bilan kirasiz.
# Ularni "demo" parolga almashtirish dev'ni taxmin qilinadigan qilib qo'yardi.
#
# Agent tokenlari esa O'CHIRILADI: tsexdagi kompyuter adashib dev'ga ulanib
# qolmasin (ular baribir mes.mebelix.uz ga qarab turibdi, bu — ikkinchi qulf).
set -euo pipefail

PROD_DIR=/opt/mebelix-mes
DEV_DIR=/opt/mebelix-mes-dev
DUMP=/tmp/mebelix_prod_$(date +%Y%m%d_%H%M%S).dump

prod() { docker compose -f "$PROD_DIR/docker-compose.prod.yml" "$@"; }
dev() { docker compose -p mebelix-dev -f "$DEV_DIR/docker-compose.dev.yml" "$@"; }

env_get() { grep -E "^$1=" "$2" | tail -1 | cut -d= -f2- | tr -d '"'"'"'; }
PROD_USER="$(env_get POSTGRES_USER "$PROD_DIR/.env")"
PROD_DB="$(env_get POSTGRES_DB "$PROD_DIR/.env")"
DEV_USER="$(env_get POSTGRES_USER "$DEV_DIR/.env")"
DEV_DB="$(env_get POSTGRES_DB "$DEV_DIR/.env")"

echo "==> Prod dump ($PROD_DB)"
prod exec -T db pg_dump -U "$PROD_USER" -d "$PROD_DB" -Fc >"$DUMP"
ls -lh "$DUMP"

echo "==> Dev bazasi tozalanadi ($DEV_DB)"
# Faqat `public` sxema — bazani o'chirib qayta yaratish uchun ulanishlarni uzish kerak
dev exec -T db psql -U "$DEV_USER" -d "$DEV_DB" -c \
    "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO $DEV_USER;"

echo "==> Tiklash"
dev exec -T db pg_restore -U "$DEV_USER" -d "$DEV_DB" --no-owner --no-privileges <"$DUMP" || {
    # pg_restore `--no-owner` da ham egalik haqida ogohlantiradi — xato emas
    echo "    (pg_restore ogohlantirishlar bilan tugadi — quyidagi tekshiruv hal qiladi)"
}

echo "==> Shaxsiy ma'lumot tozalanadi"
dev exec -T db psql -U "$DEV_USER" -d "$DEV_DB" -v ON_ERROR_STOP=1 <"$DEV_DIR/scripts/dev_anonymize.sql"

echo "==> Tekshiruv"
dev exec -T db psql -U "$DEV_USER" -d "$DEV_DB" -c \
    "SELECT (SELECT count(*) FROM \"order\") AS buyurtma, (SELECT count(*) FROM catalog_item) AS katalog, (SELECT count(*) FROM client WHERE full_name NOT LIKE 'Mijoz %') AS tozalanmagan_mijoz;"

echo "==> Dev api qayta ishga tushadi (kesh va ulanishlar)"
dev restart api worker

rm -f "$DUMP"
echo "TAYYOR. https://dev.mebelix.uz"
