#!/usr/bin/env bash
# dev.mebelix.uz deployi. CI chaqiradi: TAG=<git sha> bash scripts/deploy-dev.sh
#
# Proddan farqi ATAYLAB: avto-rollback YO'Q va `.stable_tag` yuritilmaydi. Dev —
# sinov joyi: yiqilsa, yiqilgan holicha turib tursin, sabab shu yerda ko'rinadi.
# Prod deployi (`deploy.sh`) esa tsexni to'xtatmaslik uchun murakkab.
#
# Image'lar PROD BILAN BIR XIL: CI har `dev` push'ida ham sha bilan teglab
# ghcr.io ga yuboradi. Ya'ni dev'da sinalgan narsa `main` ga ff-merge qilinganda
# prodga AYNAN o'sha image tushadi — qayta qurilmaydi.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${TAG:?TAG majburiy (git sha)}"
COMPOSE="docker compose -p mebelix-dev -f docker-compose.dev.yml"

echo "==> Pull: TAG=$TAG"
TAG="$TAG" $COMPOSE pull

echo "==> Switch: TAG=$TAG"
TAG="$TAG" $COMPOSE up -d --remove-orphans

# Smoke prod Caddy orqali emas, TARMOQ ICHIDAN: dev vhost'i Caddy'da bo'lmasa ham
# (birinchi deploy) stek ko'tarilganini bilish kerak.
echo "==> Smoke: dev-api/ready"
for _ in $(seq 1 30); do
    code=$(docker run --rm --network mebelix-mes_default curlimages/curl:latest \
        -s -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 \
        http://dev-api:8000/api/v1/ready 2>/dev/null || true)
    [ "$code" = "200" ] && { echo "    ready: 200"; exit 0; }
    sleep 5
done

echo "XATO: dev-api 150 soniyada /ready bermadi." >&2
$COMPOSE ps >&2
$COMPOSE logs --tail 50 api >&2
exit 1
