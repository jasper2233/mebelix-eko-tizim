#!/bin/bash

set -e

echo "Starting prestart script..."

echo "Running database migrations..."
if [ -f "alembic.ini" ]; then
    python -m alembic upgrade head
else
    echo "alembic.ini not found in $(pwd), skipping migrations."
fi

echo "Creating first superuser..."
python -m app.commands.create_first_superuser

echo "Seeding defaults..."
python -m app.commands.seed_defaults

echo "Pre-start script finished successfully."
