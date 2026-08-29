#!/usr/bin/env bash
# Kunlik backup: DB (.sql.gz.enc) + yuklangan fayllar (.tar.gz.enc) -> serverda
# saqlanadi va Telegramga yuboriladi.
# Cron (server, UTC): 0 18 * * * bash /opt/mebelix-mes/scripts/backup.sh >> /var/log/mebelix-backup.log 2>&1
#   18:00 UTC = 23:00 Toshkent — ish kuni tugagach, kunning o'z sanasi bilan.
#
# Shifr: openssl aes-256-cbc -pbkdf2, parol = .env dagi ADMIN_PASSWORD.
# Ochish:
#   DB      openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.sql.gz.enc  | gunzip > dump.sql
#   fayllar openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.tar.gz.enc  | tar -xz
#
# MUHIM: backup diskka yozilishi — asosiy yo'l. Telegram faqat qo'shimcha nusxa;
# u sozlanmagan yoki yiqilgan bo'lsa ham backup saqlanadi. Avval teskari edi va
# `.backup.env` yo'qligi sababli 15 kecha davomida birorta backup olinmagan.
set -euo pipefail
cd "$(dirname "$0")/.."

# `.env` ni SOURCE QILMAYMIZ: u pydantic uchun yozilgan va ichida bash uchun
# yaroqsiz qatorlar bor — masalan `CORS_ORIGINS=["http://a", "http://b"]`.
# Vergul ortidagi bo'shliq tufayli bash ikkinchi bo'lakni BUYRUQ deb o'qiydi va
# `set -e` ostida skript o'sha yerda, pg_dump'gacha yetmasdan o'ladi (exit 127).
# Docker va pydantic o'sha faylni muammosiz o'qiydi, ya'ni nosozlik faqat shu
# yerda ko'rinardi — jimgina, hech qanday backupsiz.
# Shuning uchun faqat KERAKLI kalitlar o'qiladi, qiymat qo'shtirnoqlardan tozalanadi.
env_get() { # $1 = kalit, $2 = fayl
    [ -f "$2" ] || return 0
    sed -n "s/^${1}=//p" "$2" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^"\(.*\)"$/\1/; s/^'"'"'\(.*\)'"'"'$/\1/'
}

export POSTGRES_USER="$(env_get POSTGRES_USER .env)"
export POSTGRES_DB="$(env_get POSTGRES_DB .env)"
export ADMIN_PASSWORD="$(env_get ADMIN_PASSWORD .env)"
# Telegram kalitlari ixtiyoriy: bo'lsa nusxa yuboriladi, bo'lmasa lokal backup yetarli
export TG_BOT_TOKEN="$(env_get TG_BOT_TOKEN .backup.env)"
export TG_CHAT_ID="$(env_get TG_CHAT_ID .backup.env)"

: "${POSTGRES_USER:?.env da POSTGRES_USER topilmadi}"
: "${POSTGRES_DB:?.env da POSTGRES_DB topilmadi}"
: "${ADMIN_PASSWORD:?.env da ADMIN_PASSWORD topilmadi — shifr paroli}"

# Deploy daraxtidan TASHQARIDA: CI `rsync --delete` bilan /opt/mebelix-mes ni
# repo bilan tenglashtiradi, ya'ni repoda yo'q katalogni o'chirib yuboradi.
BACKUP_DIR="${BACKUP_DIR:-/var/backups/mebelix}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
# Sana Toshkent bo'yicha: server UTC'da yuradi, backup esa ish kuni oxirida olinadi.
# `date +%F` bo'lsa cron soati bir oz surilishi bilan fayl nomi bir kun orqaga
# tushib qolardi (23:00 Toshkent = 18:00 UTC — hozircha bir xil kun, lekin chegara yaqin).
STAMP=$(TZ=Asia/Tashkent date +%F)
FILE="${BACKUP_DIR}/mebelix-${STAMP}.sql.gz.enc"
UP_FILE="${BACKUP_DIR}/mebelix-uploads-${STAMP}.tar.gz.enc"

mkdir -p "$BACKUP_DIR"

# Telegram — ixtiyoriy tashqi nusxa. Yiqilsa ogohlantiradi, lekin backup joyida.
# Bot `sendDocument` chegarasi 50 MB: fayl oshsa faqat shu yuborish yiqiladi,
# diskdagi nusxa va boshqa fayl baribir joyida qoladi.
send_tg() { # $1 = fayl, $2 = izoh
    [ -n "${TG_BOT_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ] || {
        echo "Telegram sozlanmagan (.backup.env yo'q) — faqat lokal: $(basename "$1")"
        return 0
    }
    local resp
    # `|| resp=...`: tarmoq xatosida (DNS/connect/timeout) curl non-zero qaytaradi
    # va `set -e` ostida BUTUN skript shu yerda to'xtardi — yuklangan fayllar
    # backupi va retention (`find -delete`) umuman bajarilmasdi.
    resp=$(curl -s --connect-timeout 10 --max-time 300 \
        -F chat_id="$TG_CHAT_ID" -F document=@"$1" -F caption="$2" \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendDocument") ||
        resp='{"ok":false,"description":"curl xatosi (tarmoq yoki timeout)"}'
    echo "$resp" | grep -q '"ok":true' &&
        echo "Telegramga yuborildi: $(basename "$1")" ||
        echo "OGOHLANTIRISH: Telegram yuborilmadi ($(basename "$1")): $resp — lokal nusxa joyida" >&2
}

# ---------- 1. DB (asosiy — yiqilsa script to'xtaydi) ----------
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
echo "DB backup saqlandi: $FILE ($SIZE)"
send_tg "$FILE" "MebeliX DB backup ${STAMP} (${SIZE}). Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in fayl | gunzip > dump.sql (parol: admin parol)"

# ---------- 2. Yuklangan fayllar (BEST-EFFORT) ----------
# DB'da faqat nisbiy yo'l saqlanadi (`OrderFile.path`) — fayl yo'qolsa buyurtma
# kartochkasi "Fayl diskda topilmadi" beradi, ya'ni DB dumpi YOLG'IZ O'ZI
# buyurtmani tiklamaydi: .project, SCX va anketa rasmlari ham kerak.
#
# Yiqilsa script TO'XTAMAYDI: DB backupi allaqachon olindi va yuborildi, uni
# uploads muammosi tufayli yo'qotish mantiqsiz.
if docker compose -f docker-compose.prod.yml exec -T api \
    tar -cz -C /app/backend uploads 2>/dev/null |
    openssl enc -aes-256-cbc -pbkdf2 -pass env:ADMIN_PASSWORD -out "$UP_FILE" &&
    [ "$(stat -c %s "$UP_FILE")" -gt 100 ]; then
    UP_SIZE=$(du -h "$UP_FILE" | cut -f1)
    echo "Fayllar backupi saqlandi: $UP_FILE ($UP_SIZE)"
    send_tg "$UP_FILE" "MebeliX fayllar backup ${STAMP} (${UP_SIZE}) — .project, SCX, anketa rasmlari. Ochish: openssl enc -d -aes-256-cbc -pbkdf2 -in fayl | tar -xz (parol: admin parol)"
else
    rm -f "$UP_FILE"
    echo "OGOHLANTIRISH: yuklangan fayllar backupi olinmadi (api konteyneri o'chikmi?) — DB backupi joyida" >&2
fi

# Ikkala tur ham bitta naqsh bo'yicha tozalanadi
find "$BACKUP_DIR" -name 'mebelix-*.enc' -mtime "+${KEEP_DAYS}" -delete
