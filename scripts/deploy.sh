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

smoke() {
    for _ in $(seq 1 30); do
        [ "$(curl -s -o /dev/null -w '%{http_code}' "$SMOKE_URL")" = "200" ] && return 0
        sleep 5
    done
    return 1
}

STABLE="$(cat "$STABLE_FILE" 2>/dev/null || true)"

echo "==> Pull: TAG=$TAG"
TAG="$TAG" $COMPOSE pull

echo "==> Switch: TAG=$TAG"
TAG="$TAG" $COMPOSE up -d

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
