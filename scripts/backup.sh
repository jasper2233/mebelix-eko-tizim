#!/usr/bin/env bash
# Kunlik DB backup -> shifrlangan .sql.gz.enc -> serverda saqlanadi (+ ixtiyoriy Telegram).
# Cron (server): 0 2 * * * bash /opt/mebelix-mes/scripts/backup.sh >> /var/log/mebelix-backup.log 2>&1
#
# Shifr: openssl aes-256-cbc -pbkdf2, parol = .env dagi ADMIN_PASSWORD.
# Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc | gunzip > dump.sql
#
# MUHIM: backup diskka yozilishi — asosiy yo'l. Telegram faqat qo'shimcha nusxa;
# u sozlanmagan yoki yiqilgan bo'lsa ham backup saqlanadi. Avval teskari edi va
# `.backup.env` yo'qligi sababli 15 kecha davomida birorta backup olinmagan.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env # POSTGRES_* va ADMIN_PASSWORD
# Telegram kalitlari ixtiyoriy: bo'lsa nusxa yuboriladi, bo'lmasa lokal backup yetarli
[ -f .backup.env ] && source .backup.env
set +a

# Deploy daraxtidan TASHQARIDA: CI `rsync --delete` bilan /opt/mebelix-mes ni
# repo bilan tenglashtiradi, ya'ni repoda yo'q katalogni o'chirib yuboradi.
BACKUP_DIR="${BACKUP_DIR:-/var/backups/mebelix}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP=$(date +%F)
FILE="${BACKUP_DIR}/mebelix-${STAMP}.sql.gz.enc"

mkdir -p "$BACKUP_DIR"
docker compose -f docker-compose.prod.yml exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" |
    gzip |
    openssl enc -aes-256-cbc -pbkdf2 -pass env:ADMIN_PASSWORD -out "$FILE"

# Bo'sh/juda kichik fayl = dump yiqilgan (pipefail quvurni tutadi, bu ikkinchi to'siq)
[ "$(stat -c %s "$FILE")" -gt 1000 ] || {
    echo "XATO: backup fayli juda kichik, dump yiqilgan: $FILE" >&2
    rm -f "$FILE"
    exit 1
}

SIZE=$(du -h "$FILE" | cut -f1)
echo "backup saqlandi: $FILE ($SIZE)"

find "$BACKUP_DIR" -name 'mebelix-*.sql.gz.enc' -mtime "+${KEEP_DAYS}" -delete

# Telegram — ixtiyoriy tashqi nusxa. Yiqilsa ogohlantiradi, lekin backup joyida.
if [ -n "${TG_BOT_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ]; then
    resp=$(curl -s -F chat_id="$TG_CHAT_ID" -F document=@"$FILE" \
        -F caption="MebeliX DB backup ${STAMP} (${SIZE}). Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in fayl | gunzip > dump.sql (parol: admin parol)" \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendDocument")
    echo "$resp" | grep -q '"ok":true' &&
        echo "Telegramga ham yuborildi" ||
        echo "OGOHLANTIRISH: Telegram yuborilmadi ($resp) — lokal backup joyida" >&2
else
    echo "Telegram sozlanmagan (.backup.env yo'q) — faqat lokal backup"
fi
