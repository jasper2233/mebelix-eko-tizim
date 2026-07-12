#!/usr/bin/env bash
# Kunlik DB backup -> shifrlangan .sql.gz.enc -> Telegram botga yuboriladi.
# Cron (server): 0 2 * * * bash /opt/mebelix-mes/scripts/backup.sh >> /var/log/mebelix-backup.log 2>&1
#
# Shifr: openssl aes-256-cbc -pbkdf2, parol = .env dagi ADMIN_PASSWORD.
# Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc | gunzip > dump.sql
set -euo pipefail
cd "$(dirname "$0")/.."

# .env: POSTGRES_* va ADMIN_PASSWORD; .backup.env: TG_BOT_TOKEN, TG_CHAT_ID
set -a
source .env
source .backup.env
set +a

STAMP=$(date +%F)
FILE="/tmp/mebelix-${STAMP}.sql.gz.enc"

docker compose -f docker-compose.prod.yml exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" |
    gzip |
    openssl enc -aes-256-cbc -pbkdf2 -pass env:ADMIN_PASSWORD -out "$FILE"

SIZE=$(du -h "$FILE" | cut -f1)
resp=$(curl -s -F chat_id="$TG_CHAT_ID" -F document=@"$FILE" \
    -F caption="🗄 MebeliX DB backup ${STAMP} (${SIZE}). Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in fayl | gunzip > dump.sql (parol: admin parol)" \
    "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendDocument")

rm -f "$FILE"

echo "$resp" | grep -q '"ok":true' || {
    echo "Telegram yuborish yiqildi: $resp" >&2
    exit 1
}
echo "backup ${STAMP} yuborildi (${SIZE})"
