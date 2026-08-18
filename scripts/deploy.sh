#!/usr/bin/env bash
# Prod deploy avto-rollback bilan. CI chaqiradi: TAG=<git sha> bash scripts/deploy.sh
#
# Oqim: pull (yiqilsa eski stack joyida qoladi) -> yangi TAG'ga switch -> smoke.
# Image'lar CI'da (GitHub Actions) qurilib ghcr.io ga yuboriladi — bu server 1 vCPU,
# u yerda build qilish saytni sekinlashtirardi.
# Smoke yiqilsa oxirgi stable TAG'ga qaytariladi (.stable_tag fayli).
#
# Eslatma: rollback DB'ni downgrade QILMAYDI — migratsiyalar additiv (ustun/jadval
# qo'shish) bo'lishi shart, eski kod yangi ustunlarni e'tiborsiz qoldiradi.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${TAG:?TAG majburiy (masalan, git sha)}"
STABLE_FILE=".stable_tag"
COMPOSE="docker compose -f docker-compose.prod.yml"
# Smoke manzili .env dagi CADDY_HTTP_BIND bilan bitta manbadan — qotirilgan 8200
# port bind default 80 bo'lgan o'rnatishda har deployni yolg'ondan yiqitardi
BIND="$(grep -E '^CADDY_HTTP_BIND=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)"
BIND="${BIND:-80}"
case "$BIND" in *:*) ;; *) BIND="127.0.0.1:${BIND}" ;; esac
SMOKE_URL="${SMOKE_URL:-http://${BIND}/api/v1/ready}"

# `--max-time` MAJBURIY: usiz osilgan API (TCP qabul qiladi, javob bermaydi —
# aynan smoke tutishi kerak bo'lgan holat) `curl` ni CHEKSIZ kuttiradi, sikl
# birinchi iteratsiyadan chiqmaydi va avto-rollback hech qachon ishga tushmaydi.
# 5s ulanish + 10s to'liq javob: sog'lom `/ready` bundan ancha tez qaytadi.
smoke() {
    for _ in $(seq 1 30); do
        code=$(curl -s -o /dev/null -w '%{http_code}' \
            --connect-timeout 5 --max-time 10 "$SMOKE_URL" || true)
        [ "$code" = "200" ] && return 0
        sleep 5
    done
    return 1
}

STABLE="$(cat "$STABLE_FILE" 2>/dev/null || true)"

echo "==> Pull: TAG=$TAG"
TAG="$TAG" $COMPOSE pull

echo "==> Switch: TAG=$TAG"
TAG="$TAG" $COMPOSE up -d

# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`), ya'ni
# `up -d` uni O'ZGARGAN deb bilmaydi: compose faqat service ta'rifi (image, env,
# volumes RO'YXATI) o'zgarsa konteynerni qayta yaratadi, mount qilingan faylning
# MAZMUNI hisobga olinmaydi. Natijada rsync yangi konfigni serverga qo'ysa ham,
# Caddy eskisi bilan ishlab turaverardi — konfig o'zgarishlari deployda jimgina
# yo'qolardi.
#
# `caddy reload` zero-downtime va konfigni AVVAL tekshiradi: sintaksis buzuq
# bo'lsa eski konfig joyida qoladi va sayt yiqilmaydi. Shuning uchun `|| true`
# emas — reload yiqilsa smoke ham buni ko'rsin.
echo "==> Caddy konfigini qayta yuklash"
if ! $COMPOSE exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
    echo "==> CADDY RELOAD YIQILDI — konfig qo'llanmadi." >&2
    echo "    Sayt ESKI konfig bilan ishlab turibdi (reload buzuq konfigni rad etadi)," >&2
    echo "    ya'ni yangi image'lar ko'tarilgan, lekin caddy/Caddyfile o'zgarishi TUSHMAGAN." >&2
    echo "    Odatda sabab — Caddyfile sintaksisi; CI dagi 'Caddyfile validate' qadami buni" >&2
    echo "    tutishi kerak edi. Konfigni tuzatib qayta deploy qiling." >&2
    exit 1
fi

if smoke; then
    echo "$TAG" >"$STABLE_FILE"
    echo "==> Deploy OK, stable=$TAG"
    # Eski image'lar: joriy + oldingi stable qoladi (favqulodda zaxira), qolgani o'chadi
    # grep, --filter=reference emas: docker glob'i '/' dan o'tmaydi va
    # ghcr.io/<owner>/mebelix-mes-* nomlari hech qachon mos kelmasdi
    docker images --format '{{.Repository}}:{{.Tag}}' | grep 'mebelix-mes-' |
        grep -vE ":(${TAG}|${STABLE:-latest})$" | xargs -r docker rmi >/dev/null 2>&1 || true
    docker image prune -f >/dev/null
    exit 0
fi

echo "==> SMOKE FAILED: TAG=$TAG" >&2
if [ -n "$STABLE" ]; then
    echo "==> Rollback: stable=$STABLE" >&2
    TAG="$STABLE" $COMPOSE up -d
    if smoke; then
        echo "==> Rollback OK — tizim stable=$STABLE da ishlayapti" >&2
    else
        echo "==> ROLLBACK SMOKE HAM YIQILDI — qo'lda aralashuv kerak!" >&2
    fi
else
    echo "==> .stable_tag yo'q — hech narsa qilinmadi" >&2
fi
exit 1
