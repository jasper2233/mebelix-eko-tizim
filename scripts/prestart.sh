#!/bin/bash

set -e

echo "Starting prestart script..."

echo "Running database migrations..."
# WORKDIR /app/backend, alembic.ini shu yerda. Yo'q bo'lsa start qattiq yiqilsin —
# migratsiyasiz sxema ustida API ko'tarilgandan ko'ra yaxshi.
#
# SKIP_MIGRATIONS=1 — faqat deploy.sh rollback'i: eski image YANGI sxema ustida
# ko'tariladi, uning alembic'i bazadagi yangi revision'ni tanimaydi va
# `upgrade head` yiqilardi. alembic_version'ga tegilmaydi (stamp qilinmaydi) —
# keyingi to'g'ri deploy `upgrade head` bilan shunchaki davom etadi.
if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
    echo "SKIP_MIGRATIONS=1 — migratsiya o'tkazib yuborildi (rollback rejimi)"
elif [ "${TENANCY_MODE:-single}" = "multi" ]; then
    # Obuna rejimi (EKO TIZIM TZ §2.4): platforma bazasi + har obunachi bazasi.
    # Admin va postlar obunachi yaratilganda qo'yiladi (`platforma create`), bu yerda emas.
    python -m app.commands.platforma init
    python -m app.commands.platforma migrate-all
else
    python -m alembic upgrade head
fi

if [ "${TENANCY_MODE:-single}" != "multi" ]; then
    echo "Creating first superuser..."
    python -m app.commands.create_first_superuser

    echo "Seeding defaults..."
    python -m app.commands.seed_defaults
fi

echo "Pre-start script finished successfully."
