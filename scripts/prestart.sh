#!/bin/bash

set -e

echo "Starting prestart script..."

echo "Running database migrations..."
# Shartsiz: WORKDIR /app/backend, alembic.ini shu yerda. Yo'q bo'lsa start
# qattiq yiqilsin — migratsiyasiz sxema ustida API ko'tarilgandan ko'ra yaxshi.
python -m alembic upgrade head

echo "Creating first superuser..."
python -m app.commands.create_first_superuser

echo "Seeding defaults..."
python -m app.commands.seed_defaults

echo "Pre-start script finished successfully."
